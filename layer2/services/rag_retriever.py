"""RAG retrieval service for supplementary code context."""

from typing import List, Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path
import sys

if TYPE_CHECKING:
    from config import DocGenConfig
    from layer2.schemas.agent_state import AgentState


class RAGService:
    """Wrapper service for layer1 RAG retrieval."""

    def __init__(self, config: "DocGenConfig"):
        self.config = config
        self._initialized = False
        self._storage = None
        self._embedder = None
        self._retriever = None

    def _lazy_init(self):
        """Lazy initialization to avoid import issues when RAG disabled."""
        if self._initialized:
            return

        # Add layer1 to path for imports
        layer1_path = Path(__file__).parent.parent.parent / "layer1"
        if str(layer1_path) not in sys.path:
            sys.path.insert(0, str(layer1_path))

        from embeddings import EmbeddingGenerator
        from storage import QdrantStorage
        from retrieval import HybridRetriever

        self._embedder = EmbeddingGenerator()
        self._storage = QdrantStorage()
        self._retriever = HybridRetriever(self._storage, self._embedder)
        self._initialized = True

    def index_codebase(self, root_path: Path, reindex: bool = True) -> Dict[str, Any]:
        """Index the target codebase into Qdrant."""
        self._lazy_init()

        # Add layer1 to path for indexer import
        layer1_path = Path(__file__).parent.parent.parent / "layer1"
        if str(layer1_path) not in sys.path:
            sys.path.insert(0, str(layer1_path))

        from indexer import FolderIndexer

        indexer = FolderIndexer(
            folder_path=root_path,
            storage=self._storage,
            embedder=self._embedder,
            export_path=None  # No JSON export needed
        )

        if reindex:
            self._storage.clear_collection()

        return indexer.index_folder()

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve semantically similar code chunks."""
        self._lazy_init()

        results = self._retriever.retrieve(query, top_k=top_k)

        # Transform to simplified format for AgentState
        return [
            {
                "code": hit["payload"]["code"],
                "file_path": hit["payload"]["file_path"],
                "start_line": hit["payload"]["start_line"],
                "end_line": hit["payload"]["end_line"],
                "enriched_text": hit["payload"].get("enriched_text", ""),
                "name": hit["payload"]["name"],
                "entity_type": hit["payload"].get("entity_type", "unknown"),
                "score": hit.get("rerank_score", hit.get("score", 0)),
            }
            for hit in results
        ]

    def retrieve_by_entity_name(
        self,
        module: str,
        entity_name: str,
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve specific function/class by name from a module.

        Args:
            module: Module name (e.g., 'layer1.parser')
            entity_name: Function or class name to retrieve
            entity_type: Optional filter ('function' or 'class')

        Returns:
            List of matching code chunks with metadata
        """
        self._lazy_init()

        # Build targeted query
        query = f"{module} {entity_name}"

        # Retrieve with larger top_k for filtering
        results = self._retriever.retrieve(query, top_k=20)

        # Filter by module and entity name
        module_path = module.replace(".", "/")
        filtered = [
            hit for hit in results
            if hit["payload"]["name"] == entity_name
            and module_path in hit["payload"]["file_path"]
        ]

        # Optional entity type filter
        if entity_type:
            filtered = [
                hit for hit in filtered
                if hit["payload"].get("entity_type") == entity_type
            ]

        # Transform to standard format
        return [
            {
                "code": hit["payload"]["code"],
                "file_path": hit["payload"]["file_path"],
                "start_line": hit["payload"]["start_line"],
                "end_line": hit["payload"]["end_line"],
                "enriched_text": hit["payload"].get("enriched_text", ""),
                "name": hit["payload"]["name"],
                "entity_type": hit["payload"].get("entity_type", "unknown"),
                "score": hit.get("rerank_score", hit.get("score", 0)),
            }
            for hit in filtered
        ]

    def retrieve_module_top_k(
        self,
        module: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get top-k chunks from a specific module only.

        Args:
            module: Module name (e.g., 'layer1.parser')
            top_k: Number of chunks to retrieve

        Returns:
            Top-k chunks from that module by relevance score
        """
        self._lazy_init()

        # Query for the module
        query = module

        # Retrieve with higher top_k for post-filtering
        results = self._retriever.retrieve(query, top_k=top_k * 3)

        # Filter to only this module's file(s)
        module_path = module.replace(".", "/")
        module_results = [
            hit for hit in results
            if module_path in hit["payload"]["file_path"]
        ]

        # Return top-k by score
        module_results.sort(
            key=lambda x: x.get("rerank_score", x.get("score", 0)),
            reverse=True
        )

        # Transform to standard format
        return [
            {
                "code": hit["payload"]["code"],
                "file_path": hit["payload"]["file_path"],
                "start_line": hit["payload"]["start_line"],
                "end_line": hit["payload"]["end_line"],
                "enriched_text": hit["payload"].get("enriched_text", ""),
                "name": hit["payload"]["name"],
                "entity_type": hit["payload"].get("entity_type", "unknown"),
                "score": hit.get("rerank_score", hit.get("score", 0)),
            }
            for hit in module_results[:top_k]
        ]

    def retrieve_usage_patterns(
        self,
        entity_name: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find where a function or class is used in other parts of the codebase.

        Args:
            entity_name: Function or class name to search for
            limit: Max number of usage examples to return

        Returns:
            Code chunks showing usage patterns
        """
        self._lazy_init()

        # Query for usage patterns
        query = f"using {entity_name} import {entity_name}"

        # Retrieve usage examples
        results = self._retriever.retrieve(query, top_k=limit * 2)

        # Filter out definitions (we want usages)
        usage_results = [
            hit for hit in results
            if hit["payload"]["name"] != entity_name  # Not the definition itself
            and entity_name.lower() in hit["payload"]["code"].lower()
        ]

        # Transform to standard format
        return [
            {
                "code": hit["payload"]["code"],
                "file_path": hit["payload"]["file_path"],
                "start_line": hit["payload"]["start_line"],
                "end_line": hit["payload"]["end_line"],
                "enriched_text": hit["payload"].get("enriched_text", ""),
                "name": hit["payload"]["name"],
                "entity_type": hit["payload"].get("entity_type", "unknown"),
                "score": hit.get("rerank_score", hit.get("score", 0)),
            }
            for hit in usage_results[:limit]
        ]

    def retrieve_dependency_context(
        self,
        dependency_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get main exports and public API from a dependency module.

        Args:
            dependency_name: Dependency module name (e.g., 'layer2.services.llm_provider')

        Returns:
            Top-3 chunks showing the dependency's public interface
        """
        self._lazy_init()

        # Query for public exports
        query = f"{dependency_name} class function export API"

        # Retrieve with focus on the dependency
        results = self._retriever.retrieve(query, top_k=10)

        # Filter to only this dependency
        dep_path = dependency_name.replace(".", "/")
        dep_results = [
            hit for hit in results
            if dep_path in hit["payload"]["file_path"]
        ]

        # Prioritize classes and public functions (likely exports)
        def export_priority(hit):
            entity_type = hit["payload"].get("entity_type", "")
            name = hit["payload"]["name"]
            score = hit.get("rerank_score", hit.get("score", 0))

            # Classes and functions are more likely to be exports
            if entity_type in ("class", "function"):
                score *= 1.2

            # Public names (no leading underscore) are more likely exports
            if name and not name.startswith("_"):
                score *= 1.1

            return score

        dep_results.sort(key=export_priority, reverse=True)

        # Return top 3 exports
        return [
            {
                "code": hit["payload"]["code"],
                "file_path": hit["payload"]["file_path"],
                "start_line": hit["payload"]["start_line"],
                "end_line": hit["payload"]["end_line"],
                "enriched_text": hit["payload"].get("enriched_text", ""),
                "name": hit["payload"]["name"],
                "entity_type": hit["payload"].get("entity_type", "unknown"),
                "score": hit.get("rerank_score", hit.get("score", 0)),
            }
            for hit in dep_results[:3]
        ]


def build_query(state: "AgentState", strategy: str) -> str:
    """Build RAG query based on configured strategy."""
    module_name = state["file"]

    if strategy == "code_preview":
        code_preview = state["code_chunks"][0][:200] if state["code_chunks"] else ""
        return f"{module_name}: {code_preview}"

    elif strategy == "dependencies":
        deps = ", ".join(state["dependencies"][:5]) if state["dependencies"] else "standalone"
        return f"{module_name} uses {deps}"

    elif strategy == "docstring_first":
        # Extract module docstring from first code chunk if present
        first_chunk = state["code_chunks"][0] if state["code_chunks"] else ""
        if first_chunk.startswith('"""'):
            parts = first_chunk.split('"""')
            if len(parts) >= 2:
                docstring = parts[1][:200]
                return f"{module_name}: {docstring}"
        elif first_chunk.startswith("'''"):
            parts = first_chunk.split("'''")
            if len(parts) >= 2:
                docstring = parts[1][:200]
                return f"{module_name}: {docstring}"
        # Fallback to code preview
        return f"{module_name}: {first_chunk[:200]}"

    # Default fallback
    return module_name


def rag_retrieve(
    state: "AgentState",
    rag_service: RAGService,
    top_k: int = 5,
    strategy: str = "code_preview"
) -> "AgentState":
    """
    Add rag_context to state. Filters out same-file results.

    This function is ADDITIVE - it does not modify existing code_chunks.
    """
    query = build_query(state, strategy)
    results = rag_service.retrieve(query, top_k=top_k)

    # Filter out results from the same file (we already have that code)
    current_file = state["file"].replace(".", "/") + ".py"
    filtered_results = [
        r for r in results
        if not r["file_path"].endswith(current_file)
    ]

    state["rag_context"] = filtered_results
    return state
