"""RAG usage tracker for logging retrieval operations."""

import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import Counter
import asyncio


class RAGUsageTracker:
    """Tracks and logs RAG retrieval operations during documentation generation."""

    def __init__(self, output_dir: str = "./output"):
        """
        Initialize RAG usage tracker.

        Args:
            output_dir: Directory to write rag_usage.txt
        """
        self.output_dir = output_dir
        self.entries: List[Dict[str, Any]] = []
        self.start_time = datetime.now()
        self.lock = asyncio.Lock()

    async def log_initial_query(
        self,
        module: str,
        strategy: str,
        top_k: int,
        chunks_retrieved: int,
        chunks: List[Dict[str, Any]]
    ):
        """Log initial RAG query for a module."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "module": module,
            "operation": "initial_query",
            "strategy": strategy,
            "top_k_requested": top_k,
            "chunks_retrieved": chunks_retrieved,
            "sources": self._summarize_sources(chunks)
        }

        async with self.lock:
            self.entries.append(entry)

    async def log_tool_call(
        self,
        module: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result_summary: str
    ):
        """Log a tool call during adaptive RAG."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "module": module,
            "operation": "tool_call",
            "tool_name": tool_name,
            "arguments": arguments,
            "result_summary": result_summary
        }

        async with self.lock:
            self.entries.append(entry)

    async def log_review_expansion(
        self,
        module: str,
        missing_entities: List[Dict[str, str]],
        chunks_retrieved: int
    ):
        """Log automatic context expansion after review failure."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "module": module,
            "operation": "review_expansion",
            "missing_entities": missing_entities,
            "chunks_retrieved": chunks_retrieved
        }

        async with self.lock:
            self.entries.append(entry)

    async def log_module_complete(
        self,
        module: str,
        total_queries: int,
        total_tool_calls: int,
        total_chunks: int,
        mode: str
    ):
        """Log completion of documentation for a module."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "module": module,
            "operation": "module_complete",
            "total_queries": total_queries,
            "total_tool_calls": total_tool_calls,
            "total_chunks": total_chunks,
            "mode": mode
        }

        async with self.lock:
            self.entries.append(entry)

    def _summarize_sources(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Summarize the sources of retrieved chunks."""
        if not chunks:
            return []

        # Count chunks per file
        file_counts = Counter(chunk.get("file_path", "unknown") for chunk in chunks)

        # Get entity types
        entity_types = Counter(chunk.get("entity_type", "unknown") for chunk in chunks)

        return [
            {
                "unique_files": len(file_counts),
                "total_chunks": len(chunks),
                "top_files": dict(file_counts.most_common(5)),
                "entity_types": dict(entity_types)
            }
        ]

    def write_report(self) -> str:
        """
        Write RAG usage report to rag_usage.txt.

        Returns:
            Path to the report file
        """
        output_file = os.path.join(self.output_dir, "rag_usage.txt")

        try:
            with open(output_file, "w") as f:
                f.write("=" * 80 + "\n")
                f.write("RAG USAGE REPORT\n")
                f.write("=" * 80 + "\n")
                f.write(f"Start Time: {self.start_time.isoformat()}\n")
                f.write(f"End Time: {datetime.now().isoformat()}\n")
                f.write(f"Total Operations: {len(self.entries)}\n")
                f.write("\n")

                # Group entries by module
                modules: Dict[str, List[Dict]] = {}
                for entry in self.entries:
                    module = entry.get("module", "unknown")
                    if module not in modules:
                        modules[module] = []
                    modules[module].append(entry)

                f.write(f"Modules Processed with RAG: {len(modules)}\n")
                f.write("\n")

                # Detailed per-module logs
                for module, module_entries in sorted(modules.items()):
                    f.write("-" * 80 + "\n")
                    f.write(f"Module: {module}\n")
                    f.write("-" * 80 + "\n")

                    # Get summary from module_complete entry
                    complete_entry = next(
                        (e for e in module_entries if e["operation"] == "module_complete"),
                        None
                    )

                    if complete_entry:
                        mode = complete_entry.get("mode", "unknown")
                        f.write(f"Mode: {mode}\n")
                        f.write(f"Total Queries: {complete_entry.get('total_queries', 0)}\n")
                        f.write(f"Total Tool Calls: {complete_entry.get('total_tool_calls', 0)}\n")
                        f.write(f"Total Chunks Retrieved: {complete_entry.get('total_chunks', 0)}\n")
                        f.write("\n")

                    # Log each operation
                    for entry in module_entries:
                        if entry["operation"] == "initial_query":
                            f.write("  ⚡ Initial Query:\n")
                            f.write(f"     Strategy: {entry['strategy']}\n")
                            f.write(f"     Requested: {entry['top_k_requested']} chunks\n")
                            f.write(f"     Retrieved: {entry['chunks_retrieved']} chunks\n")
                            if entry.get("sources"):
                                src = entry["sources"][0]
                                f.write(f"     From {src['unique_files']} files:\n")
                                for file, count in src.get("top_files", {}).items():
                                    f.write(f"       - {file}: {count} chunks\n")
                                f.write(f"     Entity Types: {src.get('entity_types', {})}\n")

                        elif entry["operation"] == "tool_call":
                            f.write(f"  🔧 Tool Call: {entry['tool_name']}\n")
                            args_str = ", ".join(f"{k}={v}" for k, v in entry['arguments'].items())
                            f.write(f"     Arguments: {args_str}\n")
                            # Truncate long results
                            result = entry['result_summary']
                            if len(result) > 200:
                                result = result[:200] + "..."
                            f.write(f"     Result: {result}\n")

                        elif entry["operation"] == "review_expansion":
                            f.write("  🔄 Review Expansion:\n")
                            entities = ", ".join(f"{e['name']} ({e['type']})" for e in entry['missing_entities'])
                            f.write(f"     Missing Entities: {entities}\n")
                            f.write(f"     Chunks Retrieved: {entry['chunks_retrieved']}\n")

                    f.write("\n")

                # Summary statistics
                f.write("=" * 80 + "\n")
                f.write("SUMMARY STATISTICS\n")
                f.write("=" * 80 + "\n")

                total_queries = sum(
                    e.get("total_queries", 0) for e in self.entries
                    if e["operation"] == "module_complete"
                )
                total_tool_calls = sum(
                    e.get("total_tool_calls", 0) for e in self.entries
                    if e["operation"] == "module_complete"
                )
                total_chunks = sum(
                    e.get("total_chunks", 0) for e in self.entries
                    if e["operation"] == "module_complete"
                )

                f.write(f"Total RAG Queries: {total_queries}\n")
                f.write(f"Total Tool Calls: {total_tool_calls}\n")
                f.write(f"Total Chunks Retrieved: {total_chunks}\n")

                # Operation breakdown
                operation_counts = {}
                for entry in self.entries:
                    op = entry["operation"]
                    operation_counts[op] = operation_counts.get(op, 0) + 1

                f.write("\nOperations Breakdown:\n")
                for op, count in sorted(operation_counts.items()):
                    f.write(f"  - {op}: {count}\n")

                f.write("\n")
                f.write("=" * 80 + "\n")

            print(f"✓ RAG usage report written to {output_file}")
            return output_file

        except Exception as e:
            print(f"⚠️  Failed to write RAG usage report: {e}")
            import traceback
            traceback.print_exc()
            return output_file
