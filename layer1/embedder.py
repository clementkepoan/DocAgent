import json
from typing import Any, Dict, List
import torch

def generate_embeddings(
    chunks: List[Dict[str, Any]],
    embedder: Any,
    isLocal: bool,
    device: str = "cpu",
    batch_size: int = 50,
) -> List[Dict[str, Any]]:
    """Converts chunks into vector embeddings with metadata.
    
    Args:
        chunks: Output from chunker containing code and metadata.
        embedder: Embedding model instance (local or API-based).
        isLocal: Whether to use local model with PyTorch.
        device: Device for local model execution.
        batch_size: Number of chunks to process per batch.
    
    Returns:
        List of dictionaries containing chunk IDs, vectors, and metadata.
    """
    if isLocal:
        embedder.to(device)

    print(f"\n🔢 Generating embeddings for {len(chunks)} chunks...")
    
    texts = [chunk["content"] for chunk in chunks]
    all_embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        batch_number = i // batch_size + 1
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        print(f"  Processing batch {batch_number}/{total_batches} ({len(batch_texts)} chunks)...")
        
        if isLocal:
            batch_embeddings = embedder.encode(
                batch_texts,
                convert_to_tensor=True,
                normalize_embeddings=True,
                device=device,
                show_progress_bar=True
            )
        else:
            batch_embeddings = embedder.embed_documents(texts=batch_texts)
        
        all_embeddings.extend(batch_embeddings)
    
    if isLocal:
        embeddings_tensor = torch.cat(all_embeddings, dim=0)
        all_embeddings = embeddings_tensor.cpu().numpy().tolist()
    
    vector_entries = []
    for chunk, embedding in zip(chunks, all_embeddings):
        chunk_id = str(chunk["id"])
        
        metadata = {
            "content": chunk["content"],
            "file_path": chunk["file_path"],
            "module_name": chunk["module_name"],
            "type": chunk["type"],
            "name": chunk["name"],
            "line_start": chunk["line_start"],
            "line_end": chunk["line_end"],
            "dependencies": json.dumps(chunk["dependencies"]),
            "arg_names": json.dumps(chunk.get("arg_names", [])),
            "return_type": chunk.get("return_type", ""),
            "docstring": chunk.get("docstring", ""),
            "has_decorators": str(chunk.get("has_decorators", False))
        }
        
        vector_entries.append({
            "id": chunk_id,
            "vector": embedding,
            "metadata": metadata
        })
    
    print(f"✅ Generated {len(vector_entries)} embeddings")
    return vector_entries