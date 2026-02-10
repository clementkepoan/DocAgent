from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from qdrant_client.http import models as rest
from typing import List, Dict, Any, Optional
import uuid
import hashlib
import settings as cfg

class QdrantStorage:
    def __init__(self):
        self.client = QdrantClient(
            url=cfg.QDRANT_URL,
            api_key=cfg.QDRANT_API_KEY,
            prefer_grpc=False  # Use HTTP for compatibility
        )
        self.collection_name = cfg.COLLECTION_NAME
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        collections = self.client.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=cfg.EMBEDDING_DIMENSIONS,
                    distance=Distance.COSINE
                )
            )
            print(f"Created Qdrant collection: {self.collection_name}")
    
    def upsert(self, chunks: List[Dict[str, Any]], vectors: List[List[float]]):
        """Store chunks with deterministic IDs to prevent duplicates"""
        points = []
        for chunk, vector in zip(chunks, vectors):
            # Deterministic ID: hash of file_path:start_line
            id_string = f"{chunk['file_path']}:{chunk['start_line']}"
            point_id = hashlib.md5(id_string.encode()).hexdigest()
            
            payload = {
                "name": chunk["name"],
                "code": chunk["code"],
                "file_path": chunk["file_path"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "docstring": chunk["docstring"],
                "type": chunk["type"],
                "entity_type": chunk.get("entity_type", chunk["type"]),
                "enriched_text": chunk["enriched_text"],
                "folder_path": chunk.get("folder_path", ""),
                "is_test": chunk.get("is_test", False)
            }
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        return len(points)
    
    def search(self, query_vector: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        """Vector search - returns raw results using query_points"""
        try:
            # Modern qdrant-client API (v1.x)
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                with_payload=True
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

    def clear_collection(self):
        """Delete and recreate collection to clear all points (most reliable)"""
        try:
            # Delete entire collection
            self.client.delete_collection(self.collection_name)
            print(f"🗑️  Deleted collection: {self.collection_name}")
        except Exception as e:
            print(f"⚠️  Collection might not exist: {e}")
        
        # Recreate it fresh
        self._ensure_collection()
        print(f"✅ Recreated collection: {self.collection_name}")