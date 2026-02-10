from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from qdrant_client.http import models as rest  # Import for scroll
import settings as cfg
import numpy as np

class HybridRetriever:
    def __init__(self, storage, embedder):
        self.storage = storage
        self.embedder = embedder
        self.cross_encoder = CrossEncoder(cfg.CROSS_ENCODER_MODEL)
        self.bm25 = None
        self.bm25_chunks = []

    def retrieve(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Full hybrid retrieval with hierarchical boosting.
        """
        # Get more candidates to give boosting room to work
        candidates = self.hybrid_retrieve(query, top_k=50)
        
        # Apply hierarchical boosting
        boosted = self.hierarchical_boost(candidates)
        
        # Sort by boosted scores and take top candidates for reranking
        boosted.sort(key=lambda x: x["score"], reverse=True)
        
        # Rerank top candidates
        reranked = self._rerank(query, boosted[:top_k * 2])
        
        return reranked[:top_k]
    
    def hybrid_retrieve(self, query: str, top_k: int = 10) -> List[Dict]:
        """Full hybrid retrieval with deduplication"""
        query_vector = self.embedder.generate(query)[0]
        
        # Get candidates
        semantic_results = self.storage.search(query_vector, limit=top_k * 3)
        lexical_results = self._bm25_search(query, top_k * 3)
        
        # Combine and deduplicate
        all_candidates = semantic_results + lexical_results
        unique_candidates = self._deduplicate_by_content(all_candidates)
        
        # Rerank top unique candidates
        unique_candidates.sort(key=lambda x: x["score"], reverse=True)
        candidates_to_rerank = unique_candidates[:top_k * 2]
        
        reranked = self._rerank(query, candidates_to_rerank)
        return reranked[:top_k]
    
    def hierarchical_boost(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Boost items that share hierarchy with top result, demote tests"""
        if not candidates:
            return candidates
        
        top_payload = candidates[0]["payload"]
        top_folder = top_payload.get("folder_path", "")
        top_file = top_payload["file_path"]
        
        for candidate in candidates:
            payload = candidate["payload"]
            
            # Same folder → 1.5x boost
            if payload.get("folder_path", "") == top_folder:
                candidate["score"] *= cfg.SAME_FOLDER_BOOST
            
            # Same file → 2x boost
            if payload["file_path"] == top_file:
                candidate["score"] *= cfg.SAME_FILE_BOOST
            
            # Test file → 0.01x penalty (demote heavily)
            if payload.get("is_test", False):
                candidate["score"] *= cfg.TEST_PENALTY
        
        return candidates
    
    def _bm25_search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Lexical search using BM25 on chunk names and code"""
        if not self.bm25:
            self._build_bm25_index()
        
        if not self.bm25:
            return []
        
        query_tokens = query.lower().split()
        scores = self.bm25.get_scores(query_tokens)
        top_indices = np.argsort(scores)[-limit:][::-1]
        
        return [
            {
                "id": f"bm25_{i}",
                "score": float(scores[i]),
                "payload": self.bm25_chunks[i]
            }
            for i in top_indices if scores[i] > 0
        ]
    
    def _build_bm25_index(self):
        """Build BM25 index from all chunks in Qdrant"""
        all_points = []
        offset = None
        
        while True:
            try:
                # Use scroll API
                scroll_result = self.storage.client.scroll(
                    collection_name=self.storage.collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True
                )
                
                # Handle both tuple and object return types
                if isinstance(scroll_result, tuple):
                    results, next_offset = scroll_result
                else:
                    # It's a ScrollResult object
                    results = scroll_result.points
                    next_offset = scroll_result.next_page_offset
                
                all_points.extend(results)
                if not next_offset:
                    break
                offset = next_offset
            except Exception as e:
                print(f"Scroll error: {e}")
                break
        
        corpus = []
        self.bm25_chunks = []
        
        for point in all_points:
            payload = point.payload
            text = f"{payload['name']} {payload['code']} {payload['file_path']}"
            corpus.append(text.lower().split())
            self.bm25_chunks.append(payload)
        
        if corpus:
            self.bm25 = BM25Okapi(corpus)
    
    def _merge_results(self, semantic: List[Dict], lexical: List[Dict]) -> List[Dict]:
        """Merge results using Reciprocal Rank Fusion"""
        by_id = {}
        
        for rank, hit in enumerate(semantic):
            by_id[hit["id"]] = {
                "semantic_score": hit["score"],
                "lexical_score": 0.0,
                "payload": hit["payload"],
                "semantic_rank": rank
            }
        
        for rank, hit in enumerate(lexical):
            if hit["id"] in by_id:
                by_id[hit["id"]]["lexical_score"] = hit["score"]
            else:
                by_id[hit["id"]] = {
                    "semantic_score": 0.0,
                    "lexical_score": hit["score"],
                    "payload": hit["payload"],
                    "semantic_rank": 999
                }
        
        for item in by_id.values():
            item["rrf_score"] = self._rrf_score(item["semantic_score"], item["semantic_rank"], item["lexical_score"])
        
        return sorted(
            by_id.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )
    
    def _rrf_score(self, semantic_score: float, semantic_rank: int, lexical_score: float, k: int = 60) -> float:
        """Reciprocal Rank Fusion scoring"""
        semantic_rank_weight = 1 / (semantic_rank + k)
        lexical_score_weight = lexical_score * 0.1
        return semantic_score + lexical_score_weight + semantic_rank_weight
    
    def _rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """Rerank candidates using cross-encoder"""
        if not candidates:
            return []
        
        pairs = []
        for hit in candidates:
            payload = hit["payload"]
            chunk_text = (
                f"{payload['name']} - "
                f"{payload['type']} - "
                f"{payload.get('enriched_text', '')[:300]} - "
                f"{payload['file_path']}:{payload['start_line']}"
            )
            pairs.append([query, chunk_text])
        
        scores = self.cross_encoder.predict(pairs)

        # print(f"DEBUG - Query: '{query}'")
        # for i, (hit, score) in enumerate(zip(candidates, scores)):
        #     print(f"  {i+1}. {hit['payload']['name']}: {score:.3f}")

        import numpy as np
        scores = np.exp(scores) / np.sum(np.exp(scores))
        
        scored_candidates = []
        for hit, score in zip(candidates, scores):
            hit_copy = hit.copy()  # Don't mutate original
            hit_copy["rerank_score"] = float(score * 10)
            scored_candidates.append(hit_copy)
        
        return sorted(scored_candidates, key=lambda x: x["rerank_score"], reverse=True)
    
    def _deduplicate_by_content(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicates based on file_path + start_line"""
        seen = set()
        unique = []
        
        for hit in results:
            payload = hit["payload"]
            key = (payload["file_path"], payload["start_line"])
            
            if key not in seen:
                seen.add(key)
                unique.append(hit)
        
        return unique