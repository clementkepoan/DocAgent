import os
import ast
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional
from collections import deque
import networkx as nx
import matplotlib.pyplot as plt


class ImportGraph:
    def __init__(self, root_folder: str):
        self.root_folder = Path(root_folder).resolve()
        self.imports: Dict[str, Set[str]] = {}  # file -> set of files it imports
        self.imported_by: Dict[str, Set[str]] = {}  # file -> set of files that import it
        self.cycles: List[List[str]] = []
        
    def analyze(self):
        """Main analysis method"""
        print(f"Scanning folder: {self.root_folder}")
        
        # First pass: find all Python files and parse imports
        python_files = self._find_python_files()
        print(f"Found {len(python_files)} Python files")
        
        # Build initial import maps
        for file_path in python_files:
            self._parse_imports(file_path)
        
        # Second pass: resolve import paths and build relationships
        self._resolve_imports()
        
        # Detect cycles
        self.cycles = self._detect_cycles()
        
        print(f"Analysis complete. Found {len(self.cycles)} circular dependencies.")
        
    def _find_python_files(self) -> List[Path]:
        """Recursively find all Python files"""
        return [p for p in self.root_folder.rglob("*.py") if p.is_file()]
    
    def _parse_imports(self, file_path: Path):
        """Parse import statements from a Python file using AST"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(file_path))
            
            relative_path = file_path.relative_to(self.root_folder)
            module_name = str(relative_path.with_suffix('')).replace(os.sep, '.')
            
            self.imports[module_name] = set()
            self.imported_by[module_name] = set()
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.imports[module_name].add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        if node.level > 0:  # Relative import
                            # Will resolve later
                            self.imports[module_name].add(f".{'..' * (node.level-1)}{node.module}")
                        else:
                            self.imports[module_name].add(node.module)
                            
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
    
    def _resolve_imports(self):
        """Convert module names to file paths and build imported_by relationships"""
        # Create a mapping of module names to file paths
        module_to_file = {}
        for file_path in self._find_python_files():
            relative_path = file_path.relative_to(self.root_folder)
            module_name = str(relative_path.with_suffix('')).replace(os.sep, '.')
            module_to_file[module_name] = module_name
        
        # Resolve imports
        for importer, imported_modules in self.imports.items():
            resolved_imports = set()
            
            for module in imported_modules:
                # Resolve relative imports
                if module.startswith('.'):
                    resolved = self._resolve_relative_import(importer, module)
                    if resolved:
                        resolved_imports.add(resolved)
                # Check if it's a local module (not a standard library/package)
                elif self._is_local_module(module):
                    # Try to find the module in the project
                    possible_path = module.replace('.', os.sep)
                    if (self.root_folder / f"{possible_path}.py").exists() or \
                       (self.root_folder / possible_path / "__init__.py").exists():
                        resolved_imports.add(module)
            
            self.imports[importer] = resolved_imports
            
            # Build imported_by map
            for imported in resolved_imports:
                if imported not in self.imported_by:
                    self.imported_by[imported] = set()
                self.imported_by[imported].add(importer)
    
    def _resolve_relative_import(self, importer: str, module: str) -> Optional[str]:
        """Resolve a relative import path to absolute module name"""
        parts = importer.split('.')
        level = module.count('.') - 1  # Number of levels to go up
        
        if level >= len(parts):
            return None
        
        base = '.'.join(parts[:-level]) if level > 0 else importer
        rest = module.lstrip('.')
        
        return f"{base}.{rest}" if rest else base
    
    def _is_local_module(self, module: str) -> bool:
        """Check if a module is likely a local file (not stdlib or site-packages)"""
        # Simple heuristic: if it contains the root folder name or is a relative path
        return not module.startswith(('sys', 'os', 'json', 're', 'collections', 'typing', 
                                      'datetime', 'time', 'math', 'random', 'string'))
    
    def _detect_cycles(self) -> List[List[str]]:
        """Detect circular dependencies using DFS"""
        G = self.to_networkx()
        cycles = list(nx.simple_cycles(G))
        return [list(cycle) for cycle in cycles]
    
    def to_networkx(self) -> nx.DiGraph:
        """Convert to NetworkX directed graph"""
        G = nx.DiGraph()
        
        # Add all files as nodes
        all_files = set(self.imports.keys()) | set(self.imported_by.keys())
        G.add_nodes_from(all_files)
        
        # Add edges for imports
        for importer, imported_files in self.imports.items():
            for imported in imported_files:
                G.add_edge(importer, imported)
        
        return G
    
    def visualize(self, output_file: str = "import_graph.png", highlight_cycles: bool = True):
        """
        Create a visualization with clear arrowed edges showing import direction.
        Arrow points from the importer to the imported file.
        """
        G = self.to_networkx()
        
        if len(G.nodes) == 0:
            print("No imports to visualize.")
            return
        
        plt.figure(figsize=(14, 10))
        
        # Use spring layout but with more spacing for clarity
        pos = nx.spring_layout(G, k=1.5, iterations=50, seed=42)
        
        # Prepare cycle edges for highlighting
        cycle_edges = set()
        if highlight_cycles and self.cycles:
            for cycle in self.cycles:
                for i in range(len(cycle)):
                    source = cycle[i]
                    target = cycle[(i + 1) % len(cycle)]
                    cycle_edges.add((source, target))
        
        # Draw regular edges (non-cyclic) with arrows
        regular_edges = [(u, v) for u, v in G.edges() if (u, v) not in cycle_edges]
        
        if regular_edges:
            nx.draw_networkx_edges(
                G, pos,
                edgelist=regular_edges,
                edge_color='#4a90e2',  # Professional blue
                width=1.5,
                arrows=True,
                arrowsize=20,
                arrowstyle='->',  # Classic arrow head
                connectionstyle="arc3,rad=0.1",  # Slight curve to avoid overlap
                alpha=0.7,
                node_size=2000
            )
        
        # Draw cycle edges with prominent red arrows
        if cycle_edges:
            nx.draw_networkx_edges(
                G, pos,
                edgelist=list(cycle_edges),
                edge_color='#e74c3c',  # Warning red
                width=2.5,
                arrows=True,
                arrowsize=30,
                arrowstyle='->',  # Classic arrow head
                connectionstyle="arc3,rad=0.2",  # More curve for visibility
                alpha=0.9,
                node_size=2000
            )
        
        # Draw nodes
        node_colors = []
        for node in G.nodes():
            if any(node in cycle for cycle in self.cycles):
                node_colors.append('#ffcccc')  # Light red for nodes in cycles
            else:
                node_colors.append('#e6f2ff')  # Light blue for normal nodes
        
        nx.draw_networkx_nodes(
            G, pos,
            node_color=node_colors,
            node_size=2500,
            edgecolors='#333333',
            linewidths=1.5
        )
        
        # Draw labels
        nx.draw_networkx_labels(
            G, pos,
            font_size=9,
            font_weight='bold',
            font_family='sans-serif'
        )
        
        # Add a subtle title with arrow direction explanation
        plt.title(
            "Python Import Dependencies (Arrow points from importer → imported)",
            fontsize=14,
            fontweight='bold',
            pad=20
        )
        
        # Add legend
        legend_elements = [
            plt.Line2D([0], [0], color='#4a90e2', lw=2, label='Normal Import'),
            plt.Line2D([0], [0], color='#e74c3c', lw=2, label='Circular Import'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#ffcccc', 
                      markersize=10, label='File in Cycle')
        ]
        plt.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1, 1))
        
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Visualization saved to {output_file}")
        print(f"→ Arrows indicate direction: [importer] → [imported file]")
    
    def get_import_chain(self, start_file: str, max_depth: int = 10) -> List[str]:
        """
        Get the import chain for a specific file.
        Shows what files the start_file imports (dependencies).
        """
        if start_file not in self.imports:
            return [f"File '{start_file}' not found in analysis."]
        
        chain = []
        visited = set()
        
        def dfs(file: str, depth: int):
            if depth > max_depth or file in visited:
                if file in visited:
                    chain.append(f"{'  ' * depth}{file} (cycle detected)")
                return
            
            visited.add(file)
            indent = "  " * depth
            chain.append(f"{indent}{file}")
            
            # Get files that this file imports
            dependencies = sorted(self.imports.get(file, []))
            for imported_file in dependencies:
                dfs(imported_file, depth + 1)
        
        dfs(start_file, 0)
        return chain

    def get_sorted_by_dependency(self, reverse: bool = False) -> List[str]:
        """
        Sort files by dependency order with isolation priority.
        
        Algorithm:
        1. Group files by "import count" (0 imports first)
        2. Within each group, sort by "imported_by count" ascending
        3. This ensures completely isolated files appear at the very beginning
        """
        if not self.imports:
            return []
        
        # Build dependency graph and in-degrees
        in_degree = {file: len(deps) for file, deps in self.imports.items()}
        adjacency = {file: set() for file in self.imports}
        
        # Build reverse graph: imported -> importers (for traversal)
        for importer, imported_files in self.imports.items():
            for imported in imported_files:
                if imported in self.imports:
                    adjacency[imported].add(importer)
        
        # Group 1: Files with 0 imports (most independent)
        zero_import_files = [f for f, deg in in_degree.items() if deg == 0]
        # Sort by imported_by count: files with 0 importers come first
        zero_import_files.sort(key=lambda f: len(self.imported_by.get(f, set())))
        
        # Kahn's algorithm starting from zero-import files
        result = []
        visited = set()
        queue = deque(zero_import_files)
        
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
                
            result.append(current)
            visited.add(current)
            
            # Process dependents
            for dependent in adjacency.get(current, []):
                in_degree[dependent] -= 1
                # Only add to queue when all dependencies are resolved
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # Handle remaining files (circular dependencies)
        if len(result) != len(self.imports):
            remaining = [f for f in self.imports if f not in result]
            print(f"Warning: {len(remaining)} files in cycles will be appended arbitrarily.")
            result.extend(remaining)
        
        if reverse:
            result.reverse()
        
        return result
    
    def print_sorted_dependencies(self, reverse: bool = False) -> List[str]:
        """
        Print files sorted by dependency order with statistics.
        
        Args:
            reverse: If True, print most dependent files first.
        """
        sorted_files = self.get_sorted_by_dependency(reverse=reverse)
        
        print("\n" + "="*70)
        if reverse:
            print("FILES SORTED BY DEPENDENCY (Most Dependent First)")
        else:
            print("FILES SORTED BY DEPENDENCY (Most Independent First)")
        print("="*70)
        
        print(f"\nTotal files: {len(sorted_files)}")
        print("\nOrder:")
        
        for i, file in enumerate(sorted_files, 1):
            # Count dependencies
            deps = len(self.imports.get(file, set()))
            importers = len(self.imported_by.get(file, set()))
            
            # Add cycle indicator
            cycle_indicator = ""
            if any(file in cycle for cycle in self.cycles):
                cycle_indicator = " 🔄"
            
            print(f"  {i:3d}. {file:<40s} "
                  f"[imports: {deps:2d}, imported_by: {importers:2d}]{cycle_indicator}")
        
        print("\n" + "="*70)

        return sorted_files
    
    def print_summary(self):
        """Print a summary of the analysis"""
        print("\n" + "="*60)
        print("IMPORT ANALYSIS SUMMARY")
        print("="*60)
        
        print(f"\nTotal files analyzed: {len(self.imports)}")
        
        # Most imported files
        print("\nTop 10 most imported files:")
        sorted_imports = sorted(self.imported_by.items(), key=lambda x: len(x[1]), reverse=True)
        for file, importers in sorted_imports[:10]:
            print(f"  {file}: {len(importers)} importers")
        
        # Files with most dependencies
        print("\nTop 10 files with most dependencies:")
        sorted_deps = sorted(self.imports.items(), key=lambda x: len(x[1]), reverse=True)
        for file, deps in sorted_deps[:10]:
            print(f"  {file}: {len(deps)} imports")
        
        # Circular dependencies
        if self.cycles:
            print(f"\nCircular Dependencies Found ({len(self.cycles)}):")
            for i, cycle in enumerate(self.cycles, 1):
                print(f"  Cycle {i}: {' → '.join(cycle)} → {cycle[0]}")
        else:
            print("\nNo circular dependencies found.")
        
        # print("\n" + "="*60)


# Example usage
if __name__ == "__main__":
    # Create analyzer for the Dummy folder
    analyzer = ImportGraph("./Dummy")
    
    # Run analysis
    analyzer.analyze()
    
    # Print summary
    analyzer.print_summary()
    
    # Print sorted dependency list (most independent → most dependent)
    sorted_files = analyzer.print_sorted_dependencies(reverse=False)

    # print(sorted_files)
    
    # Visualize the graph with clear arrows
    try:
        analyzer.visualize("./Layer1/import_graph.png", highlight_cycles=True)
    except ImportError:
        print("\nNote: Install networkx and matplotlib for visualization: pip install networkx matplotlib")
    
    # Get import chain for a specific file
    print("\nImport chain for 'app' (showing dependencies):")
    chain = analyzer.get_import_chain("app")
    for item in chain:
        print(item)