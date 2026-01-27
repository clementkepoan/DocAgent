from openai import OpenAI
from typing import List, Union
import tiktoken
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DocGenConfig

cfg = DocGenConfig.from_env().embedding

class EmbeddingGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=cfg.openai_api_key)
        self.model = cfg.embedding_model
        self.tokenizer = tiktoken.encoding_for_model(self.model)
        self.max_tokens = cfg.max_chunk_tokens
    
    def generate(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Generate embeddings for one or multiple texts.
        Handles batching and token limit validation.
        """
        if isinstance(texts, str):
            texts = [texts]
        
        # Validate token counts
        for i, text in enumerate(texts):
            tokens = len(self.tokenizer.encode(text))
            if tokens > self.max_tokens:
                raise ValueError(
                    f"Text {i} has {tokens} tokens, exceeds limit of {self.max_tokens}. "
                    f"First 100 chars: {text[:100]}..."
                )
        
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        
        return [data.embedding for data in response.data]
    
    def count_tokens(self, text: str) -> int:
        """Helper to check token count before embedding"""
        return len(self.tokenizer.encode(text))