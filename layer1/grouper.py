"""
Folder Processor for Python Codebases
=====================================

Simple, correct, bottom-up folder processing for LLM documentation.
No classification, no rules, just metrics and grouping.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Any
from collections import defaultdict
import json

@dataclass
class FolderInfo:
    """Clean data structure for LLM consumption"""
    folder_path: str  # Physical path like "httpie/output/ui"
    depth: int        # Depth from root
    modules: Set[str] = field(default_factory=set)  # Module names like "httpie.output.ui.palette"
    is_package: bool = False
    file_count: int = 0
    
    # Import metrics (from analyzer)
    external_imports: int = 0
    internal_imports: int = 0
    imported_by: int = 0
    
    # Internal metrics (siblings)
    sibling_imports: int = 0
    sibling_importers: int = 0
    
    # For traversal
    parent_path: str = None
    child_folders: Set[str] = field(default_factory=set)


class FolderProcessor:
    """
    Processes folders bottom-up for LLM documentation.
    Uses parser data directly—no complex rules.
    """
    
    def __init__(self, analyzer: Any):
        self.analyzer = analyzer
        self.root_path = analyzer.root_folder
        self.folders: Dict[str, FolderInfo] = {}
        self._build_folder_index()
    
    def _build_folder_index(self):
        """Discover all folders and group modules, creating ALL parent folders"""
        for module_name, file_path in self.analyzer.module_index.items():
            # Physical folder relative to root
            folder = str(file_path.parent.relative_to(self.root_path))
            
            # Initialize this folder if first time
            if folder not in self.folders:
                self._init_folder(folder)
            
            # Add module to this folder
            self.folders[folder].modules.add(module_name)
            self.folders[folder].file_count += 1
            
            # Recursively create and link ALL parent folders
            self._ensure_parent_folders(folder)
        
        # Compute metrics for each folder
        self._compute_all_metrics()

    def _init_folder(self, folder_path: str):
        """Initialize a single folder"""
        folder_dir = self.root_path / folder_path
        init_file = folder_dir / "__init__.py"
        is_package = init_file.exists()
        
        # Compute depth (count slashes)
        depth = folder_path.count("/") + 1 if folder_path != "." else 0
        
        # Find parent folder
        parent = str(folder_dir.parent.relative_to(self.root_path)) if folder_path != "." else None
        if parent == ".":
            parent = None
        
        self.folders[folder_path] = FolderInfo(
            folder_path=folder_path,
            depth=depth,
            is_package=is_package,
            parent_path=parent
        )

    def _ensure_parent_folders(self, folder_path: str):
        """Recursively create parent folders even if they contain no .py files"""
        if folder_path == ".":
            return
        
        parent = str((self.root_path / folder_path).parent.relative_to(self.root_path))
        if parent == ".":
            parent = None
        
        if parent and parent not in self.folders:
            # Initialize parent folder
            self._init_folder(parent)
            
            # Link parent-child relationship
            self.folders[parent].child_folders.add(folder_path)
            self.folders[folder_path].parent_path = parent
            
            # Recurse up the tree
            self._ensure_parent_folders(parent)
        elif parent:
            # Parent exists, just add to child set
            self.folders[parent].child_folders.add(folder_path)
            self.folders[folder_path].parent_path = parent
    
    def _compute_all_metrics(self):
        """Compute import metrics for each folder"""
        for folder, info in self.folders.items():
            # Reset counters
            external = set()
            internal = set()
            importers = set()
            
            for module in info.modules:
                # What this module imports
                for dep in self.analyzer.imports.get(module, set()):
                    # If dep starts with same folder path, it's internal
                    if dep.startswith(info.folder_path.replace("/", ".") + "."):
                        internal.add(dep)
                    else:
                        external.add(dep)
                
                # What imports this module
                for importer in self.analyzer.imported_by.get(module, set()):
                    importers.add(importer)
            
            # Count metrics
            info.external_imports = len(external)
            info.internal_imports = len(internal)
            info.imported_by = len(importers)
            
            # Sibling metrics (within parent)
            if info.parent_path:
                parent = self.folders[info.parent_path]
                parent_folder_prefix = parent.folder_path.replace("/", ".") + "."
                
                for module in info.modules:
                    for dep in self.analyzer.imports.get(module, set()):
                        # If dep is in parent but not in this folder
                        if (dep.startswith(parent_folder_prefix) and 
                            not dep.startswith(info.folder_path.replace("/", ".") + ".")):
                            info.sibling_imports += 1
                    
                    for importer in self.analyzer.imported_by.get(module, set()):
                        # If importer is in parent but not in this folder
                        if (importer.startswith(parent_folder_prefix) and 
                            not importer.startswith(info.folder_path.replace("/", ".") + ".")):
                            info.sibling_importers += 1
    
    def get_folders_bottom_up(self) -> List[FolderInfo]:
        """Return folders sorted by depth (deepest first)"""
        return sorted(
            self.folders.values(),
            key=lambda f: (-f.depth, f.folder_path)
        )
    
    def get_llm_context(self, folder_path: str) -> Dict[str, Any]:
        """Get clean context dict for LLM"""
        if folder_path not in self.folders:
            raise KeyError(f"Folder '{folder_path}' not found. Available: {list(self.folders.keys())[:10]}...")
        
        info = self.folders[folder_path]
        
        return {
            "folder_path": info.folder_path,
            "depth": info.depth,
            "is_package": info.is_package,
            "parent_path": info.parent_path,
            "child_count": len(info.child_folders),
            
            "file_count": info.file_count,
            "modules": sorted(info.modules),
            
            "metrics": {
                "external_imports": info.external_imports,
                "internal_imports": info.internal_imports,
                "imported_by": info.imported_by,
                "sibling_coupling": {
                    "imports": info.sibling_imports,
                    "importers": info.sibling_importers
                }
            }
        }
    
    def print_summary(self, include_modules: bool = False):
        """Print folders bottom-up for human review"""
        print("\n" + "=" * 80)
        print("FOLDERS BOTTOM-UP (FOR LLM PROCESSING)")
        print("=" * 80)
        
        for folder in self.get_folders_bottom_up():
            if folder.file_count == 0:  # Skip pure containers
                continue
            
            indent = "  " * folder.depth
            pkg_icon = "📦" if folder.is_package else "📁"
            
            print(f"\n{indent}{pkg_icon} {folder.folder_path}/")
            print(f"{indent}   {folder.file_count} modules")
            print(f"{indent}   Imports: {folder.external_imports + folder.internal_imports} "
                  f"({folder.external_imports} external)")
            print(f"{indent}   Imported by: {folder.imported_by} modules")
            
            if folder.sibling_imports > 0 or folder.sibling_importers > 0:
                print(f"{indent}   Sibling coupling: {folder.sibling_importers}↑ {folder.sibling_imports}↓")
            
            if include_modules:
                print(f"{indent}   Files: {', '.join(folder.modules)}")
    
    def get_folder_structure_str(self, include_modules: bool = False) -> str:
        """Return folder structure as a formatted string"""
        lines = []
        lines.append("=" * 80)
        lines.append("FOLDER STRUCTURE")
        lines.append("=" * 80)
        
        for folder in self.get_folders_bottom_up():
            if folder.file_count == 0:  # Skip pure containers
                continue
            
            indent = "  " * folder.depth
            pkg_icon = "📦" if folder.is_package else "📁"
            
            lines.append("")
            lines.append(f"{indent}{pkg_icon} {folder.folder_path}/")
            lines.append(f"{indent}   {folder.file_count} modules")
            lines.append(f"{indent}   Imports: {folder.external_imports + folder.internal_imports} "
                        f"({folder.external_imports} external)")
            lines.append(f"{indent}   Imported by: {folder.imported_by} modules")
            
            if folder.sibling_imports > 0 or folder.sibling_importers > 0:
                lines.append(f"{indent}   Sibling coupling: {folder.sibling_importers}↑ {folder.sibling_imports}↓")
            
            if include_modules:
                lines.append(f"{indent}   Files: {', '.join(folder.modules)}")
        
        return "\n".join(lines)


def generate_llm_prompts(analyzer: Any, final_docs: Dict[str, str] = None) -> List[Dict[str, Any]]:
    """Generate prompts for all folders bottom-up"""
    processor = FolderProcessor(analyzer)
    prompts = []
    
    if final_docs is None:
        final_docs = {}
    
    for folder in processor.get_folders_bottom_up():
        if folder.file_count == 0:
            continue
        
        context = processor.get_llm_context(folder.folder_path)
        
        # Include module descriptions from final_docs
        module_descriptions = ""
        for module in sorted(context['modules']):
            if module in final_docs:
                module_descriptions += f"\n- {module}: {final_docs[module][:200]}..."
        
        prompt = f"""
Explain the Python folder `{context['folder_path']}`.

SCOPE: {"Root-level package" if not context['parent_path'] else f"Subfolder of {context['parent_path']}"}
FILES: {context['file_count']} Python modules
METRICS: {json.dumps(context['metrics'], indent=2)}

MODULES: {', '.join(context['modules'])}
MODULE DESCRIPTIONS:{module_descriptions if module_descriptions else " (None generated yet)"}

Describe:
1. This folder's responsibility and purpose
2. Its role in the broader architecture
3. Key patterns or abstractions in its modules
4. Coupling concerns (high external imports = likely unstable)

Answer in 2-3 sentences.
        """.strip()
        
        prompts.append({
            "folder": folder.folder_path,
            "depth": folder.depth,
            "prompt": prompt,
            "context": context
        })
    
    # Sort back to top-down for LLM processing (explain children first)
    return sorted(prompts, key=lambda p: -p['depth'])


def main():
    import argparse
    import json
    from layer1.parser import ImportGraph
    
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--modules", action="store_true")
    parser.add_argument("--llm", action="store_true")
    
    args = parser.parse_args()
    
    analyzer = ImportGraph("/Users/mulia/Desktop/Projects/CodebaseAI/Dummy")
    analyzer.analyze()
    
    processor = FolderProcessor(analyzer)
    
    if args.llm:
        prompts = generate_llm_prompts(analyzer)
        print(f"\nGenerated {len(prompts)} prompts bottom-up")
        print(f"First prompt (deepest):\n")
        print(prompts[0]['prompt'])
    else:
        processor.print_summary(include_modules=args.modules)


if __name__ == "__main__":
    main()