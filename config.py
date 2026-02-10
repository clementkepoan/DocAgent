"""Centralized configuration for documentation generator."""

from dataclasses import dataclass, field
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class LLMConfig:
    """LLM provider settings."""
    api_key: Optional[str] = None
    base_url: str = "https://api.deepseek.com"
    chat_model: str = "deepseek-chat"
    reasoner_model: str = "deepseek-reasoner"
    temperature: float = 0.7

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.environ.get("DEEPSEEK_KEY")


@dataclass
class ProcessingConfig:
    """Batch processing and concurrency settings."""
    max_concurrent_tasks: int = 20
    max_retries: int = 1
    retrieve_timeout: int = 10  # seconds
    review_timeout: int = 60    # seconds
    max_plan_retries: int = 2
    scc_max_retries: int = 3


@dataclass
class GenerationConfig:
    """Documentation generation settings."""
    use_reasoner: bool = True
    enable_logging: bool = True
    parallel_execution: bool = True


@dataclass
class OutputConfig:
    """Output paths and filenames."""
    output_dir: str = "./output"
    module_docs_file: str = "Module level docum.txt"
    folder_docs_file: str = "Folder Level docum.txt"
    scc_contexts_file: str = "scc_contexts.txt"
    condensed_file: str = "Final Condensed.md"


@dataclass
class EmbeddingConfig:
    """Embedding and vector storage settings."""
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    max_chunk_tokens: int = 2000
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __post_init__(self):
        if not self.openai_api_key:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")


@dataclass
class QdrantConfig:
    """Qdrant vector database settings."""
    url: str = "http://localhost:6333"
    api_key: Optional[str] = None
    collection_name: str = "codebase_chunks"
    parent_collection_name: str = "module_docs_parents"
    child_collection_name: str = "code_chunks_children"


@dataclass
class RAGConfig:
    """Parent-Child RAG settings."""
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k_parents: int = 3
    top_k_children: int = 5
    max_tool_iterations: int = 3
    same_folder_boost: float = 1.5
    same_file_boost: float = 2.0
    test_penalty: float = 0.01


@dataclass
class DocGenConfig:
    """Root configuration combining all settings."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)

    @classmethod
    def from_env(cls) -> "DocGenConfig":
        """Create config from environment variables."""
        return cls(
            llm=LLMConfig(
                base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                chat_model=os.environ.get("DEEPSEEK_CHAT_MODEL", "deepseek-chat"),
                reasoner_model=os.environ.get("DEEPSEEK_REASONER_MODEL", "deepseek-reasoner"),
                temperature=float(os.environ.get("LLM_TEMPERATURE", "0.7")),
            ),
            processing=ProcessingConfig(
                max_concurrent_tasks=int(os.environ.get("MAX_CONCURRENT_TASKS", "20")),
                max_retries=int(os.environ.get("MAX_RETRIES", "1")),
                retrieve_timeout=int(os.environ.get("RETRIEVE_TIMEOUT", "10")),
                review_timeout=int(os.environ.get("REVIEW_TIMEOUT", "60")),
                max_plan_retries=int(os.environ.get("MAX_PLAN_RETRIES", "2")),
                scc_max_retries=int(os.environ.get("SCC_MAX_RETRIES", "3")),
            ),
            generation=GenerationConfig(
                use_reasoner=os.environ.get("USE_REASONER", "true").lower() == "true",
                enable_logging=os.environ.get("ENABLE_LOGGING", "true").lower() == "true",
                parallel_execution=os.environ.get("PARALLEL_EXECUTION", "true").lower() == "true",
            ),
            output=OutputConfig(
                output_dir=os.environ.get("OUTPUT_DIR", "./output"),
            ),
            embedding=EmbeddingConfig(
                openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
                embedding_model=os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small"),
                embedding_dimensions=int(os.environ.get("EMBEDDING_DIMENSIONS", "1536")),
                max_chunk_tokens=int(os.environ.get("MAX_CHUNK_TOKENS", "2000")),
                cross_encoder_model=os.environ.get("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
            ),
            qdrant=QdrantConfig(
                url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
                api_key=os.environ.get("QDRANT_API_KEY"),
                collection_name=os.environ.get("COLLECTION_NAME", "codebase_chunks"),
                parent_collection_name=os.environ.get("PARENT_COLLECTION_NAME", "module_docs_parents"),
                child_collection_name=os.environ.get("CHILD_COLLECTION_NAME", "code_chunks_children"),
            ),
            rag=RAGConfig(
                chunk_size=int(os.environ.get("CHUNK_SIZE", "512")),
                chunk_overlap=int(os.environ.get("CHUNK_OVERLAP", "50")),
                top_k_parents=int(os.environ.get("RAG_TOP_K_PARENTS", "3")),
                top_k_children=int(os.environ.get("RAG_TOP_K_CHILDREN", "5")),
                max_tool_iterations=int(os.environ.get("RAG_MAX_TOOL_ITERATIONS", "3")),
                same_folder_boost=float(os.environ.get("SAME_FOLDER_BOOST", "1.5")),
                same_file_boost=float(os.environ.get("SAME_FILE_BOOST", "2.0")),
                test_penalty=float(os.environ.get("TEST_PENALTY", "0.01")),
            ),
        )


# Global config instance - lazy loaded
_config: Optional[DocGenConfig] = None


def get_config() -> DocGenConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = DocGenConfig.from_env()
    return _config
