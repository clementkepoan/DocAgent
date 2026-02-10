from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from qdrant_client.http import models as rest
from typing import List, Dict, Any, Optional
import uuid
import hashlib
from config import get_config, QdrantConfig, EmbeddingConfig


class QdrantStorage:
    def __init__(self, collection_name: str = None, qdrant_config: QdrantConfig = None, embedding_config: EmbeddingConfig = None):
        """
        Initialize Qdrant storage with optional collection name.

        Args:
            collection_name: Name of the collection. If None, uses default from config.
            qdrant_config: Qdrant configuration. If None, uses global config.
            embedding_config: Embedding configuration for vector dimensions. If None, uses global config.
        """
        config = get_config()
        self._qdrant_config = qdrant_config or config.qdrant
        self._embedding_config = embedding_config or config.embedding

        self.client = QdrantClient(
            url=self._qdrant_config.url,
            api_key=self._qdrant_config.api_key,
            prefer_grpc=False  # Use HTTP for compatibility
        )
        self.collection_name = collection_name or self._qdrant_config.collection_name
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        collections = self.client.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self._embedding_config.embedding_dimensions,
                    distance=Distance.COSINE
                )
            )
            print(f"Created Qdrant collection: {self.collection_name}")

    def upsert(self, chunks: List[Dict[str, Any]], vectors: List[List[float]]):
        """Store chunks with deterministic IDs to prevent duplicates"""
        points = []
        for chunk, vector in zip(chunks, vectors):
            # Deterministic ID: hash of file_path:start_line or module_id for parents
            if "module_id" in chunk:
                # Parent document (module doc)
                id_string = f"parent:{chunk['module_id']}"
            else:
                # Child document (code chunk)
                id_string = f"{chunk.get('file_path', '')}:{chunk.get('start_line', 0)}"
            point_id = hashlib.md5(id_string.encode()).hexdigest()

            # Build payload from chunk, excluding the vector itself
            payload = {k: v for k, v in chunk.items() if k != 'vector'}
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        return len(points)

    def upsert_with_payload(self, payloads: List[Dict[str, Any]], vectors: List[List[float]], id_field: str = "module_id"):
        """
        Store documents with explicit payload and ID field specification.

        Args:
            payloads: List of payload dictionaries
            vectors: Corresponding embedding vectors
            id_field: Field to use for deterministic ID generation
        """
        points = []
        for payload, vector in zip(payloads, vectors):
            id_value = payload.get(id_field, str(uuid.uuid4()))
            point_id = hashlib.md5(f"{id_field}:{id_value}".encode()).hexdigest()
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        return len(points)

    def search(self, query_vector: List[float], limit: int = 10,
               filter_conditions: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Vector search with optional filtering.

        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            filter_conditions: Optional filter dict, e.g., {"parent_module_id": "layer1.parser"}

        Returns:
            List of search results with id, score, and payload
        """
        try:
            # Build filter if conditions provided
            query_filter = None
            if filter_conditions:
                must_conditions = []
                for key, value in filter_conditions.items():
                    if isinstance(value, list):
                        # OR condition for multiple values
                        must_conditions.append(
                            rest.FieldCondition(
                                key=key,
                                match=rest.MatchAny(any=value)
                            )
                        )
                    else:
                        must_conditions.append(
                            rest.FieldCondition(
                                key=key,
                                match=rest.MatchValue(value=value)
                            )
                        )
                query_filter = rest.Filter(must=must_conditions)

            # Modern qdrant-client API (v1.x)
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                with_payload=True,
                query_filter=query_filter
            )

            return [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload
                }
                for hit in results.points
            ]
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def search_by_parent_ids(self, query_vector: List[float], parent_module_ids: List[str],
                              limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for children filtered by parent module IDs.

        Args:
            query_vector: Query embedding vector
            parent_module_ids: List of parent module IDs to filter by
            limit: Maximum number of results

        Returns:
            List of search results filtered to specified parents
        """
        return self.search(
            query_vector=query_vector,
            limit=limit,
            filter_conditions={"parent_module_id": parent_module_ids}
        )

    def delete_by_file(self, file_path: str):
        """Delete all chunks from a file (for re-indexing)"""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="file_path",
                        match=rest.MatchValue(value=file_path)
                    )
                ]
            )
        )

    def delete_by_module_id(self, module_id: str):
        """Delete all documents for a specific module ID"""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="module_id",
                        match=rest.MatchValue(value=module_id)
                    )
                ]
            )
        )

    def clear_collection(self):
        """Delete and recreate collection to clear all points (most reliable)"""
        try:
            # Delete entire collection
            self.client.delete_collection(self.collection_name)
            print(f"Deleted collection: {self.collection_name}")
        except Exception as e:
            print(f"Collection might not exist: {e}")

        # Recreate it fresh
        self._ensure_collection()
        print(f"Recreated collection: {self.collection_name}")

    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "status": info.status
            }
        except Exception as e:
            return {"error": str(e)}
