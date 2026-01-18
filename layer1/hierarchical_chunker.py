import ast
from typing import Any, Dict, List
import tiktoken
from tiktoken import Encoding
from chunker import CodeChunker


class HierarchicalChunker:
    """Splits large code chunks into smaller windows while preserving metadata."""
    
    def __init__(self, base_chunker: CodeChunker, max_tokens: int = 2048, overlap_frac: float = 0.5) -> None:
        """Initializes the hierarchical chunker.
        
        Args:
            base_chunker: Base chunker instance.
            max_tokens: Maximum tokens per window.
            overlap_frac: Fraction of overlap between windows.
        """
        self.base_chunker = base_chunker
        self.max_tokens = max_tokens
        self.overlap_frac = overlap_frac
        self.tokenizer: Encoding = tiktoken.get_encoding("cl100k_base")
    
    def extract_chunks(self) -> List[Dict[str, Any]]:
        """Extracts and splits chunks hierarchically.
        
        Returns:
            List of chunk dictionaries.
        """
        base_chunks = self.base_chunker.extract_chunks()
        all_windows = []
        
        for chunk in base_chunks:
            if self._is_giant(chunk):
                windows = self._split_into_windows(chunk)
                all_windows.extend(windows)
            else:
                all_windows.append(chunk)
        
        return all_windows
    
    def _is_giant(self, chunk: Dict[str, Any]) -> bool:
        """Checks if chunk exceeds token budget.
        
        Args:
            chunk: Chunk dictionary.
        
        Returns:
            True if chunk is too large.
        """
        token_count = len(self.tokenizer.encode(chunk["content"]))
        return token_count > self.max_tokens
    
    def _split_into_windows(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Splits a large chunk into overlapping windows.
        
        Args:
            chunk: Large chunk dictionary.
        
        Returns:
            List of window chunks.
        """
        try:
            tree = ast.parse(chunk["content"])
        except SyntaxError:
            return [chunk]
            
        if not isinstance(tree.body[0], (ast.FunctionDef, ast.ClassDef)):
            return [chunk]
        
        func_node = tree.body[0]
        body_stmts = func_node.body
        
        if not body_stmts:
            return [chunk]
        
        all_lines = chunk["content"].splitlines()
        absolute_offset = chunk["line_start"] - 1
        
        windows: List[Dict[str, Any]] = []
        window_index = 0
        start_idx = 0
        
        while start_idx < len(all_lines):
            token_budget_used = 0
            end_idx = start_idx
            window_lines: List[str] = []
            
            while end_idx < len(all_lines) and token_budget_used < self.max_tokens:
                stmt = all_lines[end_idx]
                stmt_tokens = len(self.tokenizer.encode(stmt))

                if token_budget_used + stmt_tokens > self.max_tokens and window_lines:
                    break
                
                window_lines.append(stmt)
                token_budget_used += stmt_tokens
                end_idx += 1
                
            if not window_lines:
                if end_idx < len(body_stmts):
                    window_lines = [body_stmts[start_idx]]
                    end_idx = start_idx + 1
                else:
                    break
            
            window_chunk = {
                "id": f"{chunk['id']}:win{window_index:02d}",
                "content": "\n".join(window_lines),
                "file_path": chunk["file_path"],
                "module_name": chunk["module_name"],
                "type": chunk["type"],
                "name": chunk["name"],
                "line_start": absolute_offset + start_idx,
                "line_end": absolute_offset + end_idx,
                "file_dependencies": chunk["file_dependencies"],
                "dependencies": chunk["dependencies"],
                "arg_names": chunk.get("arg_names", []),
                "return_type": chunk.get("return_type"),
                "docstring": chunk.get("docstring"),
                "has_decorators": chunk.get("has_decorators", False),
                "original_id": chunk["id"],
                "window_index": window_index,
                "window_line_start": start_idx,
                "window_line_end": end_idx,
            }
            windows.append(window_chunk)
            
            stride = max(1, len(window_lines) // 2)
            start_idx = max(end_idx - stride, start_idx + 1)
            window_index += 1

            if end_idx + absolute_offset == chunk["line_end"]:
                break
            
            if start_idx < 0:
                break
        
        return windows