import torch
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import numpy as np

class CodeEmbedder:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", use_gpu: bool = True):
        """
        Initialize the embedding model.
        
        Args:
            model_name: Model to use (bge-small-en-v1.5 is default for MVP)
            use_gpu: Use CUDA if available (set to False to force CPU)
        """
        print(f"🔧 Loading embedding model: {model_name}")
        
        # Load model (downloads automatically on first run)
        self.model = SentenceTransformer(model_name)
        
        # Move to GPU if available and requested
        if use_gpu and torch.cuda.is_available():
            self.device = "cuda"
            self.model.to(self.device)
            print(f"⚡ Using GPU (CUDA) - Embedding will be fast!")
        else:
            self.device = "cpu"
            print(f"🐌 Using CPU - Embedding will be slower")
        
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        print(f"📏 Embedding dimension: {self.embedding_dim}")
        
    def generate_embeddings(
        self, 
        chunks: List[Dict[str, Any]], 
        batch_size: int = 100,
        normalize: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Convert chunks into vector embeddings with metadata.
        
        Args:
            chunks: Output from your chunker.py
            batch_size: Number of chunks to process at once (adjust for GPU memory)
            normalize: Whether to normalize vectors (CRITICAL - always True for RAG)
        
        Returns:
            List of dicts ready for ChromaDB:
            [
                {
                    "id": "auth:login_user",
                    "vector": [0.123, -0.456, ...],
                    "metadata": { ... }
                },
                ...
            ]
        """
        print(f"\n🔢 Generating embeddings for {len(chunks)} chunks...")
        
        # Extract text content for embedding
        texts = [chunk["content"] for chunk in chunks]
        
        # Process in batches to avoid GPU memory issues
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_number = i // batch_size + 1
            total_batches = (len(texts) + batch_size - 1) // batch_size
            
            print(f"  Processing batch {batch_number}/{total_batches} ({len(batch_texts)} chunks)...")
            
            # Generate embeddings for this batch
            # show_progress_bar=True shows a nice progress bar
            batch_embeddings = self.model.encode(
                batch_texts,
                convert_to_tensor=True,  # Returns PyTorch tensor for GPU efficiency
                normalize_embeddings=normalize,  # CRITICAL: ensures cosine similarity works
                device=self.device,
                show_progress_bar=True
            )
            
            all_embeddings.append(batch_embeddings)
        
        # Combine all batches into one tensor
        embeddings_tensor = torch.cat(all_embeddings, dim=0)
        
        # Convert to list of numpy arrays (ChromaDB prefers lists)
        embeddings_list = embeddings_tensor.cpu().numpy().tolist()
        
        # Attach metadata to each embedding
        vector_entries = []
        for chunk, embedding in zip(chunks, embeddings_list):
            # Create a unique ID (already done by chunker, but ensure it's string)
            chunk_id = str(chunk["id"])
            
            # Prepare metadata (ChromaDB will store this alongside the vector)
            # IMPORTANT: Convert any nested dicts/lists to strings for ChromaDB compatibility
            metadata = {
                "content": chunk["content"],
                "file_path": chunk["file_path"],
                "module_name": chunk["module_name"],
                "type": chunk["type"],
                "name": chunk["name"],
                "line_start": chunk["line_start"],
                "line_end": chunk["line_end"],
                "dependencies": json.dumps(chunk["dependencies"]),  # Convert list to string
                "arg_names": json.dumps(chunk.get("arg_names", [])),
                "return_type": chunk.get("return_type", ""),
                "docstring": chunk.get("docstring", ""),
                "has_decorators": str(chunk.get("has_decorators", False))  # Convert bool to string
            }
            
            vector_entries.append({
                "id": chunk_id,
                "vector": embedding,
                "metadata": metadata
            })
        
        print(f"✅ Generated {len(vector_entries)} embeddings")
        return vector_entries
    
    def calculate_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors (0 to 1).
        Useful for testing and debugging.
        """
        # Convert to tensors for efficient computation
        v1 = torch.tensor(vector1, device=self.device)
        v2 = torch.tensor(vector2, device=self.device)
        
        # Cosine similarity = dot product / (norm1 * norm2)
        # Since vectors are normalized, this simplifies to dot product
        similarity = torch.dot(v1, v2).item()
        
        return similarity

# ==================== TESTING ====================
if __name__ == "__main__":
    from chunker import CodeChunker
    from parser import ImportGraph
    import json
    
    print("=" * 60)
    print("CODE EMBEDDING TEST")
    print("=" * 60)
    
    # 1. Parse
    print("\n1. Parsing codebase...")
    analyzer = ImportGraph("./backend")
    analyzer.analyze()
    
    # 2. Chunk
    print("\n2. Chunking code...")
    chunker = CodeChunker(analyzer)
    chunks = chunker.extract_chunks()
    
    # 3. Embed
    print("\n3. Generating embeddings...")
    embedder = CodeEmbedder(use_gpu=True)
    vector_entries = embedder.generate_embeddings(chunks, batch_size=100)
    
    # 4. Test similarity
    # print("\n4. Testing similarity search...")
    
    # Find two chunks to compare
    # chunk_a = vector_entries[0]  # database:Database
    # chunk_b = vector_entries[2]  # auth:login_user (depends on database)
    
    # similarity = embedder.calculate_similarity(
    #     chunk_a["vector"], 
    #     chunk_b["vector"]
    # )
    # print(f"   Similarity between '{chunk_a['id']}' and '{chunk_b['id']}': {similarity:.4f}")
    
    # Should be relatively high (~0.6-0.8) since auth:login_user uses Database
    
    # 5. Save embeddings
    print("\n5. Saving embeddings...")
    
    # Convert to JSON-serializable format
    embeddings_json = []
    for entry in vector_entries:
        embeddings_json.append({
            "id": entry["id"],
            "vector": entry["vector"],  # List of floats
            "metadata": entry["metadata"]
        })
    
    with open("embeddings_test.json", "w") as f:
        json.dump(embeddings_json, f, indent=2)
    
    print(f"   Saved {len(embeddings_json)} embeddings to 'embeddings_test.json'")
    # print("\n✅ Embedding test complete!")
    
    # 6. Preview first vector (first 5 numbers)
    # print(f"\n📊 Sample vector (first 5 dimensions): {vector_entries[0]['vector'][:5]}")