"""
Parent-Child Retriever for RAG Architecture
============================================

Two-stage retrieval:
1. Search parent index (module docs) for semantic matches
2. For matched modules, retrieve children (code chunks)

This approach leverages that module descriptions embed better semantically
than raw code, while still retrieving relevant code for context.
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from config import get_config
from layer1.storage import QdrantStorage
from layer1.embeddings import EmbeddingGenerator


@dataclass
class CodeChunk:
    """Represents a retrieved code chunk (child)."""
    chunk_type: str
    name: str
    text: str
    start_line: int
    end_line: int
    file_path: str
    score: float = 0.0


@dataclass
class RAGResult:
    """
    Result from parent-child RAG retrieval.

    Contains parent module info plus relevant code chunks.
    """
    module_id: str
    module_summary: str
    module_responsibility: str
    parent_score: float
    relevant_chunks: List[CodeChunk] = field(default_factory=list)
    full_doc: Optional[Dict[str, Any]] = None

    def to_context_string(self, max_chunks: int = 5, include_code: bool = True) -> str:
        """
        Format result as context string for LLM consumption.

        Args:
            max_chunks: Maximum number of code chunks to include
            include_code: Whether to include actual code snippets

        Returns:
            Formatted string suitable for LLM context
        """
        parts = [
            f"## Module: {self.module_id}",
            f"**Summary**: {self.module_summary}" if self.module_summary else "",
            f"**Responsibility**: {self.module_responsibility}" if self.module_responsibility else "",
        ]

        if self.relevant_chunks and include_code:
            parts.append("\n### Relevant Code:")
            for i, chunk in enumerate(self.relevant_chunks[:max_chunks]):
                chunk_header = f"\n**{chunk.chunk_type}: {chunk.name}** (lines {chunk.start_line}-{chunk.end_line})"
                parts.append(chunk_header)
                if chunk.text:
                    # Truncate very long chunks
                    code = chunk.text if len(chunk.text) <= 2000 else chunk.text[:2000] + "\n... [truncated]"
                    parts.append(f"```python\n{code}\n```")

        return "\n".join(filter(None, parts))


class ParentChildRetriever:
    """
    Two-stage retriever for Parent-Child RAG architecture.

    Flow:
    1. Embed query
    2. Search parent index (module docs)
    3. For matched parents, retrieve children (code chunks)
    4. Return combined RAGResults
    """

    def __init__(
        self,
        parent_storage: Optional[QdrantStorage] = None,
        child_storage: Optional[QdrantStorage] = None,
        embedder: Optional[EmbeddingGenerator] = None
    ):
        """
        Initialize retriever with storage instances.

        Args:
            parent_storage: Storage for parent docs. Created if None.
            child_storage: Storage for child chunks. Created if None.
            embedder: Embedding generator. Created if None.
        """
        self._config = get_config()
        self.parent_storage = parent_storage or QdrantStorage(self._config.qdrant.parent_collection_name)
        self.child_storage = child_storage or QdrantStorage(self._config.qdrant.child_collection_name)
        self.embedder = embedder or EmbeddingGenerator()

    async def retrieve(
        self,
        query: str,
        top_k_parents: int = None,
        top_k_children: int = None,
        min_parent_score: float = 0.3
    ) -> List[RAGResult]:
        """
        Two-stage retrieval: parents first, then children.

        Args:
            query: Natural language query (e.g., "how does dependency analysis work?")
            top_k_parents: Number of parent docs to retrieve. Defaults to settings.
            top_k_children: Number of children per parent. Defaults to settings.
            min_parent_score: Minimum similarity score for parents (0-1)

        Returns:
            List of RAGResult objects with module context and code chunks
        """
        top_k_parents = top_k_parents or self._config.rag.top_k_parents
        top_k_children = top_k_children or self._config.rag.top_k_children

        # Stage 1: Embed query and search parents
        query_vector = self.embedder.generate([query])[0]

        parent_results = self.parent_storage.search(
            query_vector=query_vector,
            limit=top_k_parents
        )

        if not parent_results:
            return []

        # Filter by minimum score
        parent_results = [
            p for p in parent_results
            if p.get("score", 0) >= min_parent_score
        ]

        if not parent_results:
            return []

        # Stage 2: For each parent, retrieve children
        results = []
        parent_module_ids = [p["payload"]["module_id"] for p in parent_results]

        # Search children filtered by parent IDs
        child_results = self.child_storage.search_by_parent_ids(
            query_vector=query_vector,
            parent_module_ids=parent_module_ids,
            limit=top_k_children * len(parent_module_ids)  # Get enough for all parents
        )

        # Group children by parent
        children_by_parent: Dict[str, List[Dict]] = {}
        for child in child_results:
            parent_id = child["payload"].get("parent_module_id")
            if parent_id:
                if parent_id not in children_by_parent:
                    children_by_parent[parent_id] = []
                children_by_parent[parent_id].append(child)

        # Build RAGResults
        for parent in parent_results:
            payload = parent.get("payload", {})
            module_id = payload.get("module_id", "")

            # Parse full doc if available
            full_doc = None
            full_doc_json = payload.get("full_doc_json", "")
            if full_doc_json:
                try:
                    full_doc = json.loads(full_doc_json)
                except:
                    pass

            # Get children for this parent
            parent_children = children_by_parent.get(module_id, [])[:top_k_children]

            chunks = [
                CodeChunk(
                    chunk_type=c["payload"].get("chunk_type", "code"),
                    name=c["payload"].get("name", ""),
                    text=c["payload"].get("text", ""),
                    start_line=c["payload"].get("start_line", 0),
                    end_line=c["payload"].get("end_line", 0),
                    file_path=c["payload"].get("file_path", ""),
                    score=c.get("score", 0)
                )
                for c in parent_children
            ]

            result = RAGResult(
                module_id=module_id,
                module_summary=payload.get("summary", ""),
                module_responsibility=payload.get("responsibility", ""),
                parent_score=parent.get("score", 0),
                relevant_chunks=chunks,
                full_doc=full_doc
            )
            results.append(result)

        return results

    async def retrieve_for_concept(
        self,
        concept: str,
        include_code: bool = True
    ) -> str:
        """
        Convenience method that returns formatted context string.

        Args:
            concept: What to search for (e.g., "dependency analysis")
            include_code: Whether to include code snippets

        Returns:
            Formatted context string ready for LLM consumption
        """
        results = await self.retrieve(concept)

        if not results:
            return f"No relevant modules found for: {concept}"

        context_parts = []
        for result in results:
            context_parts.append(result.to_context_string(include_code=include_code))

        return "\n\n---\n\n".join(context_parts)

    def retrieve_sync(
        self,
        query: str,
        top_k_parents: int = None,
        top_k_children: int = None
    ) -> List[RAGResult]:
        """
        Synchronous wrapper for retrieve().

        Use this when not in an async context.
        """
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, create new loop in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.retrieve(query, top_k_parents, top_k_children)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                self.retrieve(query, top_k_parents, top_k_children)
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get retriever statistics."""
        return {
            "parent_collection": self.parent_storage.get_collection_info(),
            "child_collection": self.child_storage.get_collection_info()
        }


# Convenience function for quick retrieval
async def search_codebase(query: str, top_k: int = 3) -> str:
    """
    Quick search function for agentic tool use.

    Args:
        query: What to search for
        top_k: Number of parent modules to return

    Returns:
        Formatted context string
    """
    retriever = ParentChildRetriever()
    results = await retriever.retrieve(query, top_k_parents=top_k)

    if not results:
        return f"No relevant code found for query: {query}"

    return "\n\n---\n\n".join([r.to_context_string() for r in results])
