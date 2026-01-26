# usage.py (modified)
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import settings as cfg
from chunking import CodeChunker
from enrichment import ChunkEnricher
from embeddings import EmbeddingGenerator
from storage import QdrantStorage
from retrieval import HybridRetriever
from indexer import FolderIndexer  # Add this import

def storing(folder_path: Path, export_path: Path, reindex: bool = True):
    embedder = EmbeddingGenerator()
    storage = QdrantStorage()

    print(f"\nIndexing folder: {folder_path}")
    indexer = FolderIndexer(
        folder_path=folder_path,
        storage=storage, 
        embedder=embedder,
        export_path=export_path
    )
    if reindex:
        storage.clear_collection()
    stats = indexer.index_folder()

    if stats["chunks_created"] == 0:
        print("❌ No chunks were indexed. Check for errors above.")
        return

def retrieving(query: Union[List[str], str], top_k: int,):
    embedder = EmbeddingGenerator()
    storage = QdrantStorage()
    retriever = HybridRetriever(storage, embedder)
    
    print(f"\nretrieving...")
    for q in query:
        print(f"\n{'='*60}")
        print(f"📝 Query: '{q}'")
        print(f"{'='*60}")
        
        results = retriever.retrieve(q, top_k=top_k)
        
        if not results:
            print("   ❌ No results found")
            continue
        
        for i, hit in enumerate(results, 1):
            payload = hit["payload"]
            print(f"\n   {i}. 🔗 {payload['file_path']}:{payload['start_line']}")
            print(f"      📁 Folder: {payload['folder_path']}")  # ← ADD
            print(f"      📊 Score: {hit['score']:.3f}")  # ← ADD: Show boosted score
            print(f"      🎯 {payload['entity_type']}: '{payload['name']}'")  # ← ADD: Show entity type
            if payload.get("is_test"):
                print(f"      ⚠️  TEST FILE")  # ← ADD: Flag test files
            print(f"      💡 {payload['enriched_text']}")
    
    print("\n" + "="*60)
    print("PIPELINE COMPLETE")
    print("="*60)


def test_pipeline():
    """Test the full retrieval pipeline with folder indexing"""
    # Step 1: Index entire folder
    test_folder = Path(__file__).parent
    export_path=Path(__file__).parent / "chunks.json"
    reindex = True
    storing(test_folder, export_path, reindex)
    
    # Step 2: Run test queries
    test_queries = [
        # "How do I calculate price with tax?",
        # "Where do we apply discounts?",
        # "Show me order validation logic",
        # "How to connect to database?",
        # "What are the user validation rules?",
        "how does the chunking work?",
        "what model is being used for embedding?",
        "how the enriching process work?"
    ]
    retrieving(test_queries, 3)
    

if __name__ == "__main__":
    import httpx
    
    try:
        response = httpx.get(f"{cfg.QDRANT_URL}/", timeout=2.0)
        if response.status_code == 200:
            test_pipeline()
        else:
            print(f"❌ Qdrant responded with status: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")