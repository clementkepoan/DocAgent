"""
Configuration File Reader
==========================

Indexes and reads non-Python configuration files for documentation context.
Supports: .yml, .yaml, .md, .json, .txt, .toml, .ini, .cfg, requirements.txt
"""

from pathlib import Path
from typing import Dict, List, Optional, Set
import os


class ConfigFileReader:
    """
    Indexes and reads non-Python configuration files.
    
    This provides the documentation generator access to files like:
    - environment.yml / requirements.txt (dependencies)
    - README.md (existing docs)
    - pyproject.toml / setup.py (project metadata)
    - package.json (if hybrid project)
    """
    
    # File extensions to index
    SUPPORTED_EXTENSIONS: Set[str] = {
        '.yml', '.yaml', '.md', '.json', '.txt', 
        '.toml', '.ini', '.cfg', '.rst'
    }
    
    # Priority files that are especially important for documentation
    PRIORITY_FILES: Set[str] = {
        'environment.yml', 'environment.yaml',
        'requirements.txt', 'requirements-dev.txt',
        'setup.py', 'setup.cfg',
        'pyproject.toml',
        'README.md', 'README.rst', 'README.txt',
        'CONTRIBUTING.md', 'CHANGELOG.md',
        'package.json', 'Makefile',
        '.env.example', 'docker-compose.yml',
        'Dockerfile'
    }
    
    # Directories to ignore
    IGNORE_DIRS: Set[str] = {
        '__pycache__', '.git', '.hg', '.svn',
        'node_modules', '.venv', 'venv', 'env',
        '.tox', '.pytest_cache', '.mypy_cache',
        'dist', 'build', 'egg-info', '.eggs',
        'chroma_db', 'outputs', 'output'
    }
    
    # Max file size to read (avoid huge files)
    MAX_FILE_SIZE: int = 50_000  # 50KB
    
    def __init__(self, root_folder: str):
        """
        Initialize the config file reader.
        
        Args:
            root_folder: Root directory of the project to scan.
        """
        self.root_folder = Path(root_folder).resolve()
        self.file_index: Dict[str, Path] = {}
        self._scanned = False
    
    def scan(self) -> None:
        """
        Scan the project directory for configuration files.
        Populates the file_index with filename -> path mappings.
        """
        if self._scanned:
            return
        
        self.file_index = {}
        
        # First, scan root directory for priority files
        for item in self.root_folder.iterdir():
            if item.is_file():
                if item.name in self.PRIORITY_FILES:
                    self.file_index[item.name] = item
                elif item.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    self.file_index[item.name] = item
        
        # Then scan subdirectories (but not too deep)
        for item in self.root_folder.rglob('*'):
            if not item.is_file():
                continue
            
            # Skip ignored directories
            if any(ignored in item.parts for ignored in self.IGNORE_DIRS):
                continue
            
            # Skip Python files (handled by ImportGraph)
            if item.suffix == '.py':
                continue
            
            # Check if it's a supported file
            if item.name in self.PRIORITY_FILES or item.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                # Use relative path as key for nested files
                rel_path = str(item.relative_to(self.root_folder))
                if rel_path not in self.file_index:
                    self.file_index[rel_path] = item
        
        self._scanned = True
    
    def get_file_content(self, filename: str) -> Optional[str]:
        """
        Read and return the content of a specific file.
        
        Args:
            filename: The filename or relative path to read.
            
        Returns:
            File content as string, or None if not found/readable.
        """
        if not self._scanned:
            self.scan()
        
        # Try exact match first
        if filename in self.file_index:
            path = self.file_index[filename]
        else:
            # Try to find by basename
            for key, path in self.file_index.items():
                if Path(key).name == filename or key.endswith(filename):
                    break
            else:
                # Try direct path from root
                direct_path = self.root_folder / filename
                if direct_path.exists() and direct_path.is_file():
                    path = direct_path
                else:
                    return None
        
        try:
            # Check file size
            if path.stat().st_size > self.MAX_FILE_SIZE:
                # Read first portion only
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read(self.MAX_FILE_SIZE)
                return content + "\n\n... [truncated due to size]"
            
            return path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            return f"[Error reading file: {e}]"
    
    def get_files_by_extension(self, ext: str) -> List[Path]:
        """
        Get all indexed files with a specific extension.
        
        Args:
            ext: File extension (with or without leading dot).
            
        Returns:
            List of Path objects matching the extension.
        """
        if not self._scanned:
            self.scan()
        
        if not ext.startswith('.'):
            ext = '.' + ext
        
        return [
            path for filename, path in self.file_index.items()
            if path.suffix.lower() == ext.lower()
        ]
    
    def get_all_config_files(self) -> Dict[str, Path]:
        """
        Get all indexed configuration files.
        
        Returns:
            Dict mapping filename/path to Path objects.
        """
        if not self._scanned:
            self.scan()
        
        return self.file_index.copy()
    
    def get_priority_files(self) -> Dict[str, Path]:
        """
        Get only the priority/important configuration files.
        
        Returns:
            Dict of priority files that exist in the project.
        """
        if not self._scanned:
            self.scan()
        
        return {
            name: path for name, path in self.file_index.items()
            if Path(name).name in self.PRIORITY_FILES
        }
    
    def get_summary(self) -> str:
        """
        Get a summary of available config files for LLM context.
        
        Returns:
            Formatted string listing available config files.
        """
        if not self._scanned:
            self.scan()
        
        if not self.file_index:
            return "No configuration files found."
        
        lines = ["Available configuration files:"]
        
        # Group by priority
        priority = []
        other = []
        
        for name, path in sorted(self.file_index.items()):
            size = path.stat().st_size if path.exists() else 0
            size_str = f"{size / 1024:.1f}KB" if size > 1024 else f"{size}B"
            entry = f"  - {name} ({size_str})"
            
            if Path(name).name in self.PRIORITY_FILES:
                priority.append(entry)
            else:
                other.append(entry)
        
        if priority:
            lines.append("\nKey files:")
            lines.extend(priority)
        
        if other:
            lines.append("\nOther config files:")
            lines.extend(other[:10])  # Limit to first 10
            if len(other) > 10:
                lines.append(f"  ... and {len(other) - 10} more")
        
        return "\n".join(lines)
