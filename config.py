"""Centralized configuration for documentation generator."""

from dataclasses import dataclass, field
from typing import Optional
import os


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
class EmbeddingConfig:
    """Embedding and vector store settings (Layer 1)."""
    openai_api_key: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    collection_name: str = "codebase_chunks"
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    max_chunk_tokens: int = 2000
    same_folder_boost: float = 1.5
    same_file_boost: float = 2.0
    test_penalty: float = 0.01

    def __post_init__(self):
        if self.openai_api_key is None:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        if self.qdrant_api_key is None:
            self.qdrant_api_key = os.environ.get("QDRANT_API_KEY")


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
    # RAG integration settings (DEPRECATED - use enable_adaptive_rag instead)
    enable_rag: bool = False  # Opt-in for supplementary RAG
    rag_top_k: int = 5  # Number of RAG results per query
    rag_reindex: bool = True  # Whether to reindex on each run
    rag_query_strategy: str = "code_preview"  # "code_preview" | "dependencies" | "docstring_first"
    # Adaptive RAG settings (NEW - primary retrieval method)
    enable_adaptive_rag: bool = False  # Enable adaptive RAG-only retrieval
    adaptive_rag_max_rounds: int = 3  # Max tool call rounds per doc generation
    adaptive_rag_auto_expand: bool = True  # Auto-expand context on review failure
    adaptive_rag_initial_top_k: int = 3  # Initial RAG query chunk count


@dataclass
class OutputConfig:
    """Output paths and filenames."""
    output_dir: str = "./output"
    module_docs_file: str = "Module level docum.txt"
    folder_docs_file: str = "Folder Level docum.txt"
    scc_contexts_file: str = "scc_contexts.txt"
    condensed_file: str = "Final Condensed.md"


@dataclass
class DocGenConfig:
    """Root configuration combining all settings."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

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
            embedding=EmbeddingConfig(
                embedding_model=os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small"),
                embedding_dimensions=int(os.environ.get("EMBEDDING_DIMENSIONS", "1536")),
                qdrant_url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
                collection_name=os.environ.get("COLLECTION_NAME", "codebase_chunks"),
                cross_encoder_model=os.environ.get("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
                max_chunk_tokens=int(os.environ.get("MAX_CHUNK_TOKENS", "2000")),
                same_folder_boost=float(os.environ.get("SAME_FOLDER_BOOST", "1.5")),
                same_file_boost=float(os.environ.get("SAME_FILE_BOOST", "2.0")),
                test_penalty=float(os.environ.get("TEST_PENALTY", "0.01")),
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
                enable_rag=os.environ.get("ENABLE_RAG", "false").lower() == "true",
                rag_top_k=int(os.environ.get("RAG_TOP_K", "5")),
                rag_reindex=os.environ.get("RAG_REINDEX", "true").lower() == "true",
                rag_query_strategy=os.environ.get("RAG_QUERY_STRATEGY", "code_preview"),
                enable_adaptive_rag=os.environ.get("ENABLE_ADAPTIVE_RAG", "false").lower() == "true",
                adaptive_rag_max_rounds=int(os.environ.get("MAX_TOOL_ROUNDS", "3")),
                adaptive_rag_auto_expand=os.environ.get("AUTO_EXPAND_ON_REVIEW_FAIL", "true").lower() == "true",
                adaptive_rag_initial_top_k=int(os.environ.get("INITIAL_TOP_K", "3")),
            ),
            output=OutputConfig(
                output_dir=os.environ.get("OUTPUT_DIR", "./output"),
            ),
        )
