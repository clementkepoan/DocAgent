from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from vector_storing import load_embedding_model


def delete_chroma_collection(
    collection_name: str,
    persist_directory: str,
) -> bool:
    """Deletes a ChromaDB collection.
    
    Args:
        collection_name: Name of collection to delete.
        persist_directory: Directory where database is persisted.
    
    Returns:
        True if deletion was successful, False otherwise.
    """
    try:
        client = chromadb.PersistentClient(path=persist_directory)
        client.delete_collection(name=collection_name)
        return True
    except Exception:
        return False


def get_chroma_vectorstore(
    embedder: Any,
    collection_name: str,
    persist_directory: str,
) -> Chroma:
    """Retrieves an existing ChromaDB vectorstore via LangChain.
    
    Args:
        embedder: Embedding function to use for vectorization.
        collection_name: Name of the collection.
        persist_directory: Directory where database is persisted.
    
    Returns:
        LangChain Chroma vectorstore instance.
    """
    client = chromadb.PersistentClient(path=persist_directory)
    return Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=embedder,
    )


def query_chroma_db(
    vectorstore: Chroma,
    query: str,
    top_k: int = 5,
    filter_dict: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Queries the ChromaDB vectorstore and returns formatted results.
    
    Args:
        vectorstore: LangChain Chroma vectorstore instance.
        query: Query string.
        top_k: Number of results to return.
        filter_dict: Optional metadata filters.
    
    Returns:
        List of dictionaries containing content, metadata, and similarity scores.
    """
    results = vectorstore.similarity_search_with_score(
        query=query,
        k=top_k,
        filter=filter_dict,
    )
    
    formatted_results = []
    for doc, score in results:
        formatted_results.append({
            "content": doc.page_content,
            "metadata": doc.metadata,
            "similarity_score": 1 - score,
        })
    
    return formatted_results


def batch_query_chroma_db(
    vectorstore: Chroma,
    queries: List[str],
    top_k: int = 5,
) -> List[List[Dict[str, Any]]]:
    """Performs batch queries against the ChromaDB vectorstore.
    
    Args:
        vectorstore: LangChain Chroma vectorstore instance.
        queries: List of query strings.
        top_k: Number of results per query.
    
    Returns:
        List of results for each query.
    """
    all_results = []
    for idx, query in enumerate(queries, 1):
        print(f"Querying {idx}/{len(queries)}: {query[:50]}...")
        results = query_chroma_db(vectorstore, query, top_k)
        all_results.append(results)
    
    return all_results


def query(
    k: int,
    embedder: Any,
    query: Optional[str] = None,
    batch_query: Optional[List[str]] = None,
    collection_name: str = "codebase_embeddings",
    chroma_path: str = "./chroma_db",
) -> Any:
    """Main query entry point for ChromaDB vectorstore operations.
    
    Args:
        query: Single query string for individual search. Provide this or batch_query.
        batch_query: List of query strings for batch search. Provide this or query.
        env_path: Path to environment file containing API keys.
        model_name: Name of the OpenAI embedding model.
        collection_name: Name of the ChromaDB collection.
        chroma_path: Directory path for ChromaDB persistence.
    
    Raises:
        IOError: If both query and batch_query are empty.
    """
    vectorstore = get_chroma_vectorstore(
        embedder=embedder,
        collection_name=collection_name,
        persist_directory=chroma_path,
    )
    
    if query:
        results = query_chroma_db(
            vectorstore=vectorstore,
            query=query,
            top_k=k,
        )

        for i, result in enumerate(results, 1):
            print(f"\n--- Result {i} (score: {result['similarity_score']:.3f}) ---")
            print(f"File: {result['metadata']['file_path']}")
            print(f"Name: {result['metadata']['name']}")
            print(f"Content preview:\n{result['content'][:200]}...")
    elif batch_query:
        results = batch_query_chroma_db(
            vectorstore=vectorstore,
            queries=batch_query,
            top_k=k,
        )

        for query, result in zip(batch_query, results):
            print(f"\n--- Query: '{query}' ---")
            for i, resul in enumerate(result, 1):
                print(f"  {i}. {resul['metadata']['name']} (score: {resul['similarity_score']:.3f})")
    else:
        raise IOError("Empty parameter 'query' or 'batch_query'")
    
    return results

if __name__ == "__main__":
    embedding_model = load_embedding_model(model_type="openai",
                model_name="text-embedding-3-small",
                )
    query(k=2,
          query="how does the parsing process work?",
          embedder=embedding_model,
          )