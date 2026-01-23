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
class DocGenConfig:
    """Root configuration combining all settings."""
    llm: LLMConfig = field(default_factory=LLMConfig)
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
        )
