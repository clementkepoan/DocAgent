"""
Parent-Child Indexer for RAG Architecture
==========================================

Implements two-tier indexing:
- Parents: Module documentation (semantic anchors)
- Children: Code chunks (retrievable context, linked by module_id)

Uses Chonkie for token-controlled chunking with hybrid approach:
tree-sitter for boundary detection, Chonkie for size control.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
from config import get_config
from layer1.storage import QdrantStorage
from layer1.embeddings import EmbeddingGenerator

try:
    from chonkie import CodeChunker
    CHONKIE_AVAILABLE = True
except ImportError:
    CHONKIE_AVAILABLE = False
    print("Warning: chonkie not installed. Using fallback chunking.")


@dataclass
class ParentPayload:
    """Schema for parent documents (module documentation)."""
    module_id: str
    summary: str
    responsibility: str
    full_doc_json: str
    exports: List[str]
    key_function_names: List[str]
    file_path: str


@dataclass
class ChildPayload:
    """Schema for child documents (code chunks)."""
    parent_module_id: str
    chunk_type: str  # "function", "class", "method", "module_header"
    name: str
    text: str
    enriched_text: str
    start_line: int
    end_line: int
    token_count: int
    file_path: str


class ParentChildIndexer:
    """
    Two-tier indexer for Parent-Child RAG architecture.

    - Index module docs as parents (semantic search anchors)
    - Index code chunks as children (linked by parent_module_id)
    """

    def __init__(self, root_path: str = "./"):
        self.root_path = Path(root_path)
        self._config = get_config()
        self.embedder = EmbeddingGenerator()

        # Initialize collections
        self.parent_storage = QdrantStorage(self._config.qdrant.parent_collection_name)
        self.child_storage = QdrantStorage(self._config.qdrant.child_collection_name)

        # Chonkie chunker for AST-aware code chunking
        if CHONKIE_AVAILABLE:
            self.chunker = CodeChunker(
                language="python",
                chunk_size=self._config.rag.chunk_size,
                tokenizer="gpt2"  # Compatible tokenizer
            )
        else:
            self.chunker = None

        # Track indexed modules
        self._indexed_parents: Set[str] = set()
        self._indexed_children: Set[str] = set()

    def _extract_code_entities(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extract code entities (functions, classes) using AST.
        Returns list of entities with name, type, code, line numbers.
        """
        import ast

        entities = []
        try:
            source = file_path.read_text(encoding='utf-8')
            tree = ast.parse(source)

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.FunctionDef):
                    entities.append({
                        "type": "function",
                        "name": node.name,
                        "start_line": node.lineno,
                        "end_line": node.end_lineno or node.lineno,
                        "code": ast.get_source_segment(source, node) or ""
                    })
                elif isinstance(node, ast.AsyncFunctionDef):
                    entities.append({
                        "type": "async_function",
                        "name": node.name,
                        "start_line": node.lineno,
                        "end_line": node.end_lineno or node.lineno,
                        "code": ast.get_source_segment(source, node) or ""
                    })
                elif isinstance(node, ast.ClassDef):
                    class_code = ast.get_source_segment(source, node) or ""
                    entities.append({
                        "type": "class",
                        "name": node.name,
                        "start_line": node.lineno,
                        "end_line": node.end_lineno or node.lineno,
                        "code": class_code
                    })
                    # Also extract methods
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            entities.append({
                                "type": "method",
                                "name": f"{node.name}.{item.name}",
                                "start_line": item.lineno,
                                "end_line": item.end_lineno or item.lineno,
                                "code": ast.get_source_segment(source, item) or ""
                            })

            # If no entities found, treat whole file as one entity
            if not entities:
                lines = source.split('\n')
                entities.append({
                    "type": "module",
                    "name": file_path.stem,
                    "start_line": 1,
                    "end_line": len(lines),
                    "code": source[:8000] if len(source) > 8000 else source
                })

        except Exception as e:
            print(f"AST parsing failed for {file_path}: {e}")
            try:
                source = file_path.read_text(encoding='utf-8')
                entities.append({
                    "type": "module",
                    "name": file_path.stem,
                    "start_line": 1,
                    "end_line": len(source.split('\n')),
                    "code": source[:8000] if len(source) > 8000 else source
                })
            except:
                pass

        return entities

    def _chunk_large_entity(self, entity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Split large code entity into token-controlled chunks using Chonkie.
        Preserves entity metadata across chunks.
        """
        code = entity.get("code", "")
        token_count = self.embedder.count_tokens(code)

        # If small enough, return as-is
        if token_count <= self._config.rag.chunk_size:
            return [entity]

        # Use Chonkie to split
        if self.chunker:
            try:
                chunks = self.chunker.chunk(code)
                result = []
                current_line = entity.get("start_line", 1)

                for i, chunk in enumerate(chunks):
                    chunk_text = chunk.text if hasattr(chunk, 'text') else str(chunk)
                    chunk_lines = chunk_text.count('\n') + 1

                    result.append({
                        "type": entity["type"],
                        "name": f"{entity['name']}[{i}]" if len(chunks) > 1 else entity["name"],
                        "start_line": current_line,
                        "end_line": current_line + chunk_lines - 1,
                        "code": chunk_text
                    })
                    current_line += chunk_lines

                return result
            except Exception as e:
                print(f"Chonkie chunking failed: {e}, using fallback")

        # Fallback: split by lines
        lines = code.split('\n')
        max_lines_per_chunk = max(10, self._config.rag.chunk_size // 10)  # Rough estimate
        chunks = []

        for i in range(0, len(lines), max_lines_per_chunk):
            chunk_lines = lines[i:i + max_lines_per_chunk]
            chunk_text = '\n'.join(chunk_lines)
            chunks.append({
                "type": entity["type"],
                "name": f"{entity['name']}[{i // max_lines_per_chunk}]",
                "start_line": entity.get("start_line", 1) + i,
                "end_line": entity.get("start_line", 1) + i + len(chunk_lines) - 1,
                "code": chunk_text
            })

        return chunks

    def _create_enriched_text(self, entity: Dict[str, Any], module_id: str) -> str:
        """Create enriched text for better semantic embedding."""
        entity_type = entity.get("type", "code")
        name = entity.get("name", "unknown")
        code = entity.get("code", "")

        # Extract docstring if present
        docstring = ""
        if '"""' in code:
            try:
                start = code.index('"""') + 3
                end = code.index('"""', start)
                docstring = code[start:end].strip()
            except:
                pass
        elif "'''" in code:
            try:
                start = code.index("'''") + 3
                end = code.index("'''", start)
                docstring = code[start:end].strip()
            except:
                pass

        # Build enriched description
        parts = [
            f"Module: {module_id}",
            f"Type: {entity_type}",
            f"Name: {name}"
        ]
        if docstring:
            parts.append(f"Description: {docstring}")

        # Add first few lines of code for context
        code_preview = code[:500] if len(code) > 500 else code
        parts.append(f"Code:\n{code_preview}")

        return "\n".join(parts)

    async def index_all_code_chunks(self, module_index: Dict[str, Path]) -> int:
        """
        Index all code chunks as children.

        Args:
            module_index: Dict mapping module names to file paths

        Returns:
            Number of chunks indexed
        """
        print(f"Indexing code chunks for {len(module_index)} modules...")

        all_chunks = []
        all_texts = []

        for module_id, file_path in module_index.items():
            if module_id in self._indexed_children:
                continue

            if not file_path.exists() or not file_path.suffix == '.py':
                continue

            # Extract code entities
            entities = self._extract_code_entities(file_path)

            # Chunk large entities
            chunked_entities = []
            for entity in entities:
                chunked_entities.extend(self._chunk_large_entity(entity))

            # Build child payloads
            for entity in chunked_entities:
                enriched = self._create_enriched_text(entity, module_id)
                token_count = self.embedder.count_tokens(entity.get("code", ""))

                # Skip if too large for embedding
                if token_count > self._config.embedding.max_chunk_tokens:
                    continue

                payload = ChildPayload(
                    parent_module_id=module_id,
                    chunk_type=entity.get("type", "code"),
                    name=entity.get("name", ""),
                    text=entity.get("code", ""),
                    enriched_text=enriched,
                    start_line=entity.get("start_line", 0),
                    end_line=entity.get("end_line", 0),
                    token_count=token_count,
                    file_path=str(file_path)
                )

                all_chunks.append(asdict(payload))
                all_texts.append(enriched)

            self._indexed_children.add(module_id)

        if not all_chunks:
            print("No chunks to index")
            return 0

        # Batch embed and upsert
        print(f"Embedding {len(all_chunks)} code chunks...")
        batch_size = 100
        total_indexed = 0

        for i in range(0, len(all_chunks), batch_size):
            batch_chunks = all_chunks[i:i + batch_size]
            batch_texts = all_texts[i:i + batch_size]

            try:
                vectors = self.embedder.generate(batch_texts)
                indexed = self.child_storage.upsert(batch_chunks, vectors)
                total_indexed += indexed
            except Exception as e:
                print(f"Error indexing batch {i // batch_size}: {e}")

        print(f"Indexed {total_indexed} code chunks to {self._config.qdrant.child_collection_name}")
        return total_indexed

    async def index_module_docs(self, module_id: str, doc_data: Dict[str, Any]) -> bool:
        """
        Index a single module's documentation as a parent.

        Args:
            module_id: Module identifier (e.g., "layer1.parser")
            doc_data: Documentation data dict with summary, responsibility, etc.

        Returns:
            True if indexed successfully
        """
        if module_id in self._indexed_parents:
            return True

        try:
            # Extract key info for parent payload
            summary = doc_data.get("summary", doc_data.get("description", ""))
            responsibility = doc_data.get("responsibility", doc_data.get("purpose", ""))

            # Extract exports/functions from doc
            exports = doc_data.get("exports", [])
            if isinstance(exports, str):
                exports = [e.strip() for e in exports.split(',')]

            key_functions = doc_data.get("key_functions", doc_data.get("functions", []))
            if isinstance(key_functions, str):
                key_functions = [f.strip() for f in key_functions.split(',')]
            elif key_functions and isinstance(key_functions[0], dict):
                # Handle list of dicts with 'name' field
                key_functions = [f.get("name", str(f)) for f in key_functions if isinstance(f, dict)]

            # Get file path
            file_path = doc_data.get("file_path", "")

            payload = ParentPayload(
                module_id=module_id,
                summary=summary[:2000] if summary else "",
                responsibility=responsibility[:2000] if responsibility else "",
                full_doc_json=json.dumps(doc_data)[:10000],
                exports=exports[:20] if exports else [],
                key_function_names=key_functions[:20] if key_functions else [],
                file_path=str(file_path)
            )

            # Create text for embedding (semantic representation)
            embed_text = f"""
Module: {module_id}
Summary: {summary}
Responsibility: {responsibility}
Exports: {', '.join(exports[:10])}
Key Functions: {', '.join(key_functions[:10])}
""".strip()

            # Embed and store
            vectors = self.embedder.generate([embed_text])
            self.parent_storage.upsert_with_payload(
                payloads=[asdict(payload)],
                vectors=vectors,
                id_field="module_id"
            )

            self._indexed_parents.add(module_id)
            return True

        except Exception as e:
            print(f"Error indexing module doc for {module_id}: {e}")
            return False

    async def index_module_docs_batch(self, module_docs: Dict[str, Dict[str, Any]]) -> int:
        """
        Index multiple module docs as parents in batch.

        Args:
            module_docs: Dict mapping module_id to doc_data

        Returns:
            Number of modules indexed
        """
        print(f"Indexing {len(module_docs)} module docs as parents...")

        payloads = []
        embed_texts = []

        for module_id, doc_data in module_docs.items():
            if module_id in self._indexed_parents:
                continue

            try:
                summary = doc_data.get("summary", doc_data.get("description", ""))
                responsibility = doc_data.get("responsibility", doc_data.get("purpose", ""))

                exports = doc_data.get("exports", [])
                if isinstance(exports, str):
                    exports = [e.strip() for e in exports.split(',')]

                key_functions = doc_data.get("key_functions", doc_data.get("functions", []))
                if isinstance(key_functions, str):
                    key_functions = [f.strip() for f in key_functions.split(',')]
                elif key_functions and isinstance(key_functions[0], dict):
                    # Handle list of dicts with 'name' field
                    key_functions = [f.get("name", str(f)) for f in key_functions if isinstance(f, dict)]

                file_path = doc_data.get("file_path", "")

                payload = ParentPayload(
                    module_id=module_id,
                    summary=summary[:2000] if summary else "",
                    responsibility=responsibility[:2000] if responsibility else "",
                    full_doc_json=json.dumps(doc_data)[:10000],
                    exports=exports[:20] if exports else [],
                    key_function_names=key_functions[:20] if key_functions else [],
                    file_path=str(file_path)
                )

                embed_text = f"""
Module: {module_id}
Summary: {summary}
Responsibility: {responsibility}
Exports: {', '.join(exports[:10])}
Key Functions: {', '.join(key_functions[:10])}
""".strip()

                payloads.append(asdict(payload))
                embed_texts.append(embed_text)
                self._indexed_parents.add(module_id)

            except Exception as e:
                print(f"Error preparing {module_id}: {e}")

        if not payloads:
            return 0

        # Batch embed and upsert
        batch_size = 50
        total_indexed = 0

        for i in range(0, len(payloads), batch_size):
            batch_payloads = payloads[i:i + batch_size]
            batch_texts = embed_texts[i:i + batch_size]

            try:
                vectors = self.embedder.generate(batch_texts)
                indexed = self.parent_storage.upsert_with_payload(
                    payloads=batch_payloads,
                    vectors=vectors,
                    id_field="module_id"
                )
                total_indexed += indexed
            except Exception as e:
                print(f"Error indexing parent batch {i // batch_size}: {e}")

        print(f"Indexed {total_indexed} module docs to {self._config.qdrant.parent_collection_name}")
        return total_indexed

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics for both collections."""
        return {
            "parents": self.parent_storage.get_collection_info(),
            "children": self.child_storage.get_collection_info()
        }

    def clear_all(self):
        """Clear both parent and child collections."""
        self.parent_storage.clear_collection()
        self.child_storage.clear_collection()
        self._indexed_parents.clear()
        self._indexed_children.clear()
        print("Cleared all RAG collections")
