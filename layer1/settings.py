import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from .env file
load_dotenv()

# Core settings (direct variable assignments, no Pydantic)
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "codebase_chunks")

CROSS_ENCODER_MODEL: str = os.getenv("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
MAX_CHUNK_TOKENS: int = int(os.getenv("MAX_CHUNK_TOKENS", "2000"))

SAME_FOLDER_BOOST = 1.5
SAME_FILE_BOOST = 2.0
TEST_PENALTY = 0.01     

# Validation
if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY must be set in .env file")