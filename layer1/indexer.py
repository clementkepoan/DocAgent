# core/indexer.py
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import json
import hashlib
from rich.progress import Progress, TaskID
from rich.console import Console
import traceback

from chunking import CodeChunker
from enrichment import ChunkEnricher
from embeddings import EmbeddingGenerator
from storage import QdrantStorage

class FolderIndexer:
    """
    Indexes an entire folder of Python files into Qdrant.
    Handles errors per-file so one bad file doesn't crash the whole process.
    """
    
    DEFAULT_EXCLUDES = [
        "__pycache__",
        "venv", ".venv", "env", ".env",
        ".git", "node_modules", "build", "dist",
        "*.pyc", "*.pyo", "*.pyd", "*.so",
        "test_*.py", "*_test.py", "tests/", "test/",
    ]
    
    def __init__(
        self,
        folder_path: Path,
        storage: QdrantStorage,
        embedder: EmbeddingGenerator,
        exclude_patterns: List[str] = None,
        export_path: Optional[Path] = None
    ):
        self.folder_path = folder_path
        self.chunker = CodeChunker(folder_path)
        self.enricher = ChunkEnricher()
        self.storage = storage
        self.embedder = embedder
        self.exclude_patterns = exclude_patterns or self.DEFAULT_EXCLUDES
        
        self.console = Console()
        self.stats = {
            "files_processed": 0,
            "files_skipped": 0,
            "chunks_created": 0,
            "embedding_tokens": 0,
            "errors": [],
        }

        self.export_path = export_path
        self.export_chunks = []
    
    def index_folder(self, batch_size: int = 50) -> Dict[str, Any]:
        """
        Recursively index all Python files in a folder.
        
        Args:
            folder_path: Root folder to index
            batch_size: How many files to embed in one API call
            
        Returns:
            Statistics dictionary
        """
        if not self.folder_path.is_dir():
            raise ValueError(f"Path is not a directory: {self.folder_path}")
        
        # Discover all Python files
        python_files = list(self._discover_files())
        
        if not python_files:
            self.console.print(f"[yellow]No Python files found in {self.folder_path}[/yellow]")
            return self.stats
        
        self.console.print(f"[blue]Found {len(python_files)} Python files to index[/blue]")
        
        # Process files with progress bar
        with Progress() as progress:
            task = progress.add_task("[cyan]Indexing files...", total=len(python_files))

            # Process in batches to avoid memory issues
            for batch_start in range(0, len(python_files), batch_size):
                batch = python_files[batch_start:batch_start + batch_size]
                self._process_batch(batch, progress, task)
        
        self._print_summary()
        
        if self.export_path and self.export_chunks:
            self._export_chunks()
        
        return self.stats
    
    
    def _discover_files(self) -> List[Path]:
        """Find all Python files, respecting exclude patterns"""
        python_files = []
        
        for py_file in self.folder_path.rglob("*.py"):
            # Skip excluded paths
            if self._should_exclude(py_file):
                continue
            
            # Skip empty files
            if py_file.stat().st_size == 0:
                continue
                
            python_files.append(py_file)
        
        return python_files
    
    def _should_exclude(self, file_path: Path) -> bool:
        """Check if file/path matches exclude patterns"""
        path_str = str(file_path)
        
        for pattern in self.exclude_patterns:
            if pattern in path_str:
                return True
        
        return False
    
    def _process_batch(self, batch: List[Path], progress: Progress, task: TaskID):
        """Process a batch of files"""
        all_chunks = []
        
        for file_path in batch:
            try:
                # Parse and enrich
                chunks = self._process_file(file_path)
                all_chunks.extend(chunks)
                
                self.stats["files_processed"] += 1
                progress.update(task, advance=1)
                
            except Exception as e:
                self.stats["errors"].append({
                    "file": str(file_path),
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                self.console.print(f"[red]❌ Failed {file_path}: {e}[/red]")
                progress.update(task, advance=1)
        
        # Batch generate embeddings
        if all_chunks:
            self._embed_and_store(all_chunks)
    
    def _process_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse and enrich a single file"""
        chunks = self.chunker.parse_file(file_path)
        
        for chunk in chunks:
            chunk["enriched_text"] = self.enricher.enrich(chunk)
            
            # Add chunk to export list (before embeddings)
            if self.export_path:
                self.export_chunks.append(chunk.copy())  # Copy to avoid mutations
        
        return chunks
    
    def _embed_and_store(self, chunks: List[Dict[str, Any]]):
        """Generate embeddings and store in Qdrant"""
        # Extract enriched texts
        enriched_texts = [c["enriched_text"] for c in chunks]
        
        # Count tokens
        total_tokens = sum(
            self.embedder.count_tokens(text) 
            for text in enriched_texts
        )
        self.stats["embedding_tokens"] += total_tokens
        
        # Generate embeddings in one batch API call
        vectors = self.embedder.generate(enriched_texts)
        
        # Store
        stored_count = self.storage.upsert(chunks, vectors)
        self.stats["chunks_created"] += stored_count
    
    def _print_summary(self):
        """Print indexing statistics"""
        self.console.print("\n" + "="*60)
        self.console.print("[bold green]INDEXING COMPLETE[/bold green]")
        self.console.print("="*60)
        self.console.print(f"📁 Files processed: {self.stats['files_processed']}")
        self.console.print(f"📄 Chunks created: {self.stats['chunks_created']}")
        self.console.print(f"🪙 Embedding tokens: {self.stats['embedding_tokens']:,.0f}")
        
        if self.stats["files_skipped"]:
            self.console.print(f"⏭️  Files skipped: {self.stats['files_skipped']}")
        
        if self.stats["errors"]:
            self.console.print(f"\n[red]❌ Errors ({len(self.stats['errors'])})[/red]")
            for error in self.stats["errors"][:3]:  # Show first 3
                self.console.print(f"   {error['file']}: {error['error']}")
        
        self.console.print("="*60)

    def _export_chunks(self):
        """Export all chunks to JSON file"""
        export_data = []
        
        for chunk in self.export_chunks:
            export_data.append({
                "file_path": chunk["file_path"],
                "name": chunk["name"],
                "type": chunk["type"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "docstring": chunk["docstring"],
                "code": chunk["code"],
                "enriched_text": chunk["enriched_text"]
            })
        
        # Write to file
        self.export_path.parent.mkdir(parents=True, exist_ok=True)
        self.export_path.write_text(json.dumps(export_data, indent=2))
        
        self.console.print(f"\n[green]📄 Exported {len(export_data)} chunks to {self.export_path}[/green]")