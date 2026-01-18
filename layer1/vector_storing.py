import torch
from typing import List, Dict, Any

from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
import json
from langchain_chroma import Chroma
import chromadb


import shutil

from parser import ImportGraph
from chunker import CodeChunker
from hierarchical_chunker import HierarchicalChunker
from API_embedder import generate_embeddings

from sentence_transformers import SentenceTransformer

def load_embedding_model(
                model_type: str,
                model_name: str,
                env_path: str = "./.env",
                ):
    if model_type not in ['local', 'openai']:
        raise IOError("invalid 'type' parameter. use 'local' or 'openai'")
    
    if model_type == "openai":
        load_dotenv(Path(env_path))
        embedding = OpenAIEmbeddings(  
            model=model_name, # usually use "text-embedding-3-small"
            )
    else:
        embedding = SentenceTransformer(model_name_or_path=model_name)
        
    return embedding

def store_embeddings_in_chromadb(
    chunks: List[Dict[str, Any]],
    embedder: Any,
    collection_name: str = "code_embeddings",
    persist_directory: str = "./chroma_db",
    batch_size: int = 50
) -> Chroma:
    """
    Complete pipeline: generate embeddings and store in ChromaDB via LangChain.
    
    Args:
        chunks: Chunks from hierarchical_chunker.py
        collection_name: Name of the ChromaDB collection
        persist_directory: Directory to persist the database
        batch_size: Batch size for embedding generation
    
    Returns:
        Chroma: LangChain Chroma vectorstore instance
    """
    # Generate embeddings
    embeddings_list = generate_embeddings(chunks=chunks, isLocal=False, batch_size=batch_size, embedder=embedder)
    
    # Create persistent client
    client = chromadb.PersistentClient(path=persist_directory)
    
    # Create or get collection
    try:
        collection = client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    except Exception:
        collection = client.get_collection(name=collection_name)
    
    # Prepare data for insertion
    ids = [item["id"] for item in embeddings_list]
    vectors = [item["vector"] for item in embeddings_list]
    metadatas = [item["metadata"] for item in embeddings_list]
    documents = [item["metadata"]["content"] for item in embeddings_list]
    
    # Add to collection in batches
    for i in range(0, len(ids), batch_size):
        end_idx = min(i + batch_size, len(ids))
        collection.add(
            ids=ids[i:end_idx],
            embeddings=vectors[i:end_idx],
            metadatas=metadatas[i:end_idx],
            documents=documents[i:end_idx]
        )
        print(f"  Stored batch {i//batch_size + 1}/{(len(ids) + batch_size - 1)//batch_size}")
    
    # Create LangChain wrapper
    # embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    vectorstore = Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=embedder
    )
    
    print(f"✅ Stored {len(embeddings_list)} embeddings in ChromaDB collection '{collection_name}'")
    return vectorstore

def store_vector(codebase_path: str,
                 embeddings: Any,
                 collection_name: str = "codebase_embeddings",
                 chroma_path: str = "./chroma_db",
                 ):

    if Path(chroma_path).exists():
        shutil.rmtree(chroma_path)

    # Run analysis
    analyzer = ImportGraph(codebase_path)
    analyzer.analyze()
    
    # Generate chunks
    base_chunker = CodeChunker(analyzer)
    hier_chunker = HierarchicalChunker(base_chunker)
    chunks = hier_chunker.extract_chunks()
    
    # 2. Store in ChromaDB
    vectorstore = store_embeddings_in_chromadb(
        chunks=chunks,
        collection_name=collection_name,
        persist_directory=chroma_path,
        embedder = embeddings,
    )
    
    print("\n✅ Vector database built successfully!")
    print("You can now query it using retrieval.py")

if __name__ == "__main__":
    embedding_model = load_embedding_model(model_type="openai",
                model_name="text-embedding-3-small",
                )
    store_vector(codebase_path="./",
                 embeddings=embedding_model,
                 )