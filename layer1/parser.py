import os
import ast
from pathlib import Path
from typing import Dict, Set, List, Optional
import networkx as nx
import matplotlib.pyplot as plt
from heapq import heappush, heappop


class ImportGraph:
    def __init__(self, root_folder: str):
        self.root_folder = Path(root_folder).resolve()

        # module -> set(modules it imports)
        self.imports: Dict[str, Set[str]] = {}

        # module -> set(modules that import it)
        self.imported_by: Dict[str, Set[str]] = {}

        self.cycles: List[List[str]] = []

        # Local module index built from filesystem:
        # e.g. {"auth": ".../auth.py", "pkg.utils": ".../pkg/utils.py", "pkg": ".../pkg/__init__.py"}
        self.module_index: Dict[str, Path] = {}

    # -----------------------------
    # Public API
    # -----------------------------
    def analyze(self):
        """Main analysis method"""
        print(f"Scanning folder: {self.root_folder}")

        # Build module index once (no heuristics)
        self.module_index = self._build_module_index()
        print(f"Indexed {len(self.module_index)} local modules/packages")

        # Parse imports for each local module
        for module_name, file_path in self.module_index.items():
            self._parse_imports(module_name, file_path)

        # Build imported_by map
        self._build_imported_by()

        # Detect cycles
        self.cycles = self._detect_cycles()

        print(f"Analysis complete. Found {len(self.cycles)} circular dependencies.")

    def to_networkx(self) -> nx.DiGraph:
        """Graph direction: importer -> imported (matches your arrow meaning)."""
        G = nx.DiGraph()
        G.add_nodes_from(self.module_index.keys())
        for importer, deps in self.imports.items():
            for imported in deps:
                G.add_edge(importer, imported)
        return G

    def topo_order_independent_first(self) -> List[str]:
        """
        Returns modules from most independent -> most dependent (dependencies first).
        Since our edges are importer->imported (dependent->dependency), we topo sort on reversed graph.
        """
        G = self.to_networkx()
        try:
            return list(nx.topological_sort(G.reverse()))
        except nx.NetworkXUnfeasible:
            # cycles exist; return a stable node list
            return list(G.nodes)

    # def topo_order_independent_first(self) -> List[str]:
    #     """
    #     Returns modules from most independent -> most dependent (dependencies first).
    #     Sorting key:
    #     1. Topological constraint: A module can only appear after all modules it imports are already in the list
    #     2. Import count (ascending): Among eligible modules, those with fewer imports come first
    #     3. Deterministic tie-break: If import counts are equal, sort by module name
    #     """
    #     # Calculate remaining dependencies for each module
    #     remaining_deps = {module: len(deps) for module, deps in self.imports.items()}
        
    #     # Priority queue: (import_count, module_name)
    #     # Modules become eligible when remaining_deps == 0, and are sorted by import count
    #     heap = []
        
    #     # Seed heap with modules that have no dependencies
    #     for module in self.imports:
    #         if remaining_deps[module] == 0:
    #             heappush(heap, (len(self.imports[module]), module))
        
    #     result = []
    #     visited = set()
        
    #     # Process modules in dependency-respecting priority order
    #     while heap:
    #         import_count, module = heappop(heap)
            
    #         if module in visited:
    #             continue
                
    #         result.append(module)
    #         visited.add(module)
            
    #         # Update all importers that depend on this module
    #         for importer in self.imported_by.get(module, []):
    #             if importer in remaining_deps:  # Only consider local modules
    #                 remaining_deps[importer] -= 1
                    
    #                 # When all dependencies satisfied, add to queue
    #                 if remaining_deps[importer] == 0:
    #                     heappush(heap, (len(self.imports[importer]), importer))
        
    #     # Append any remaining modules (in cycles) in deterministic order
    #     if len(result) != len(self.imports):
    #         remaining = [m for m in self.imports if m not in result]
    #         remaining.sort()  # Deterministic order for cyclical modules
    #         result.extend(remaining)
        
    #     return result

    def get_sorted_by_dependency(self, reverse: bool = False) -> List[str]:
        """
        Same behavior as your original intention:
        - reverse=False: most independent first
        - reverse=True: most dependent first
        """
        order = self.topo_order_independent_first()
        if reverse:
            order = list(reversed(order))
        return order

    def print_sorted_dependencies(self, reverse: bool = False) -> List[str]:
        sorted_files = self.get_sorted_by_dependency(reverse=reverse)

        print("\n" + "=" * 70)
        print("FILES SORTED BY DEPENDENCY (" + ("Most Dependent First" if reverse else "Most Independent First") + ")")
        print("=" * 70)

        print(f"\nTotal files: {len(sorted_files)}")
        print("\nOrder:")

        for i, mod in enumerate(sorted_files, 1):
            deps = len(self.imports.get(mod, set()))
            importers = len(self.imported_by.get(mod, set()))
            cycle_indicator = " 🔄" if any(mod in c for c in self.cycles) else ""
            print(f"  {i:3d}. {mod:<40s} [imports: {deps:2d}, imported_by: {importers:2d}]{cycle_indicator}")

        print("\n" + "=" * 70)
        return sorted_files

    def print_summary(self):
        print("\n" + "=" * 60)
        print("IMPORT ANALYSIS SUMMARY")
        print("=" * 60)

        print(f"\nTotal modules analyzed: {len(self.module_index)}")

        print("\nTop 10 most imported modules:")
        sorted_imports = sorted(self.imported_by.items(), key=lambda x: len(x[1]), reverse=True)
        for mod, importers in sorted_imports[:10]:
            print(f"  {mod}: {len(importers)} importers")

        print("\nTop 10 modules with most dependencies:")
        sorted_deps = sorted(self.imports.items(), key=lambda x: len(x[1]), reverse=True)
        for mod, deps in sorted_deps[:10]:
            print(f"  {mod}: {len(deps)} imports")

        if self.cycles:
            print(f"\nCircular Dependencies Found ({len(self.cycles)}):")
            for i, cycle in enumerate(self.cycles, 1):
                print(f"  Cycle {i}: {' → '.join(cycle)} → {cycle[0]}")
        else:
            print("\nNo circular dependencies found.")

    def get_import_chain(self, start_file: str, max_depth: int = 10) -> List[str]:
        """
        Shows what modules start_file imports (its dependencies).
        """
        if start_file not in self.imports:
            return [f"Module '{start_file}' not found in analysis."]

        chain: List[str] = []
        visited: Set[str] = set()

        def dfs(mod: str, depth: int):
            if depth > max_depth:
                chain.append(f"{'  ' * depth}{mod} (max depth reached)")
                return
            if mod in visited:
                chain.append(f"{'  ' * depth}{mod} (cycle detected)")
                return

            visited.add(mod)
            chain.append(f"{'  ' * depth}{mod}")

            for dep in sorted(self.imports.get(mod, [])):
                dfs(dep, depth + 1)

        dfs(start_file, 0)
        return chain

    def visualize(self, output_file: str = "import_graph.png", highlight_cycles: bool = True):
        """
        Arrow points from importer → imported.
        """
        G = self.to_networkx()
        if len(G.nodes) == 0:
            print("No imports to visualize.")
            return

        plt.figure(figsize=(14, 10))
        pos = nx.spring_layout(G, k=1.5, iterations=50, seed=42)

        cycle_edges = set()
        if highlight_cycles and self.cycles:
            for cycle in self.cycles:
                for i in range(len(cycle)):
                    cycle_edges.add((cycle[i], cycle[(i + 1) % len(cycle)]))

        regular_edges = [(u, v) for u, v in G.edges() if (u, v) not in cycle_edges]

        if regular_edges:
            nx.draw_networkx_edges(
                G, pos,
                edgelist=regular_edges,
                edge_color='#4a90e2',
                width=1.5,
                arrows=True,
                arrowsize=20,
                arrowstyle='->',
                connectionstyle="arc3,rad=0.1",
                alpha=0.7,
                node_size=2000
            )

        if cycle_edges:
            nx.draw_networkx_edges(
                G, pos,
                edgelist=list(cycle_edges),
                edge_color='#e74c3c',
                width=2.5,
                arrows=True,
                arrowsize=30,
                arrowstyle='->',
                connectionstyle="arc3,rad=0.2",
                alpha=0.9,
                node_size=2000
            )

        node_colors = []
        for node in G.nodes():
            if any(node in cycle for cycle in self.cycles):
                node_colors.append('#ffcccc')
            else:
                node_colors.append('#e6f2ff')

        nx.draw_networkx_nodes(
            G, pos,
            node_color=node_colors,
            node_size=2500,
            edgecolors='#333333',
            linewidths=1.5
        )

        nx.draw_networkx_labels(
            G, pos,
            font_size=9,
            font_weight='bold',
            font_family='sans-serif'
        )

        plt.title(
            "Python Import Dependencies (Arrow points from importer → imported)",
            fontsize=14,
            fontweight='bold',
            pad=20
        )

        legend_elements = [
            plt.Line2D([0], [0], color='#4a90e2', lw=2, label='Normal Import'),
            plt.Line2D([0], [0], color='#e74c3c', lw=2, label='Circular Import'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#ffcccc',
                       markersize=10, label='Module in Cycle')
        ]
        plt.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1, 1))

        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Visualization saved to {output_file}")
        print(f"→ Arrows indicate direction: [importer] → [imported module]")

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _build_module_index(self) -> Dict[str, Path]:
        """
        Builds local module names based on filesystem:
        - foo.py => "foo"
        - pkg/__init__.py => "pkg"
        - pkg/utils.py => "pkg.utils"
        
        For folders WITHOUT __init__.py, modules are treated as top-level
        (not prefixed with folder name).
        
        Skips __pycache__ directories.
        """
        index: Dict[str, Path] = {}

        for path in self.root_folder.rglob("*.py"):
            if not path.is_file():
                continue

            # Skip __pycache__ directories
            if "__pycache__" in path.parts:
                continue

            rel = path.relative_to(self.root_folder)

            # package module
            if rel.name == "__init__.py":
                # Skip if __init__.py is empty or only has comments
                content = path.read_text(encoding="utf-8").strip()
                if not content or content.startswith("#"):
                    continue
                
                mod = ".".join(rel.parent.parts) if rel.parent.parts else ""
                if mod:
                    index[mod] = path
                continue

            # Check if parent directory is a package (has __init__.py)
            parent_dir = path.parent
            has_init = (parent_dir / "__init__.py").exists()
            
            if has_init and parent_dir != self.root_folder:
                # It's a proper package - use full dotted path
                mod = ".".join(rel.with_suffix("").parts)
            else:
                # It's a loose module - just use the filename (not the folder prefix)
                mod = rel.with_suffix("").name
            
            index[mod] = path

        return index

    def _parse_imports(self, module_name: str, file_path: Path):
        """
        Parse imports from a file; resolve them ONLY if they map to local modules.
        """
        self.imports[module_name] = set()
        self.imported_by.setdefault(module_name, set())

        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return

        for node in ast.walk(tree):
            # import x, import x.y
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = self._resolve_absolute_module(alias.name)
                    if resolved:
                        self.imports[module_name].add(resolved)

            # from x import y  / from .x import y / from . import y
            elif isinstance(node, ast.ImportFrom):
                abs_base = self._resolve_from_import_base(module_name, node)
                if not abs_base:
                    continue

                # Prefer submodule if it exists locally: from pkg import utils => pkg.utils
                for alias in node.names:
                    # skip star imports for dependency edges (optional)
                    if alias.name == "*":
                        # treat as base dependency only
                        resolved = self._resolve_absolute_module(abs_base)
                        if resolved:
                            self.imports[module_name].add(resolved)
                        continue

                    candidate = f"{abs_base}.{alias.name}"
                    resolved = self._resolve_absolute_module(candidate) or self._resolve_absolute_module(abs_base)
                    if resolved:
                        self.imports[module_name].add(resolved)

        # Remove self-loop if any
        self.imports[module_name].discard(module_name)

    def _resolve_absolute_module(self, dotted: str) -> Optional[str]:
        """
        Given an import like "a.b.c", return the best matching LOCAL module:
        - if "a.b.c" exists, return it
        - else if "a.b" exists, return it
        - else if "a" exists, return it
        - else None
        """
        parts = dotted.split(".")
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in self.module_index:
                return candidate
        return None

    def _resolve_from_import_base(self, importer: str, node: ast.ImportFrom) -> Optional[str]:
        """
        Compute the absolute base module for 'from X import Y', respecting relative level.
        """
        # Absolute import: from pkg.mod import x
        if node.level == 0:
            if not node.module:
                return None
            return node.module

        # Relative import: from .foo import x, from ..bar import x, from . import x
        importer_parts = importer.split(".")

        # If importer is "pkg.mod", level=1 means base is "pkg"
        # level=2 means base is "" (go up 2 from pkg.mod -> "")
        up = node.level
        if up > len(importer_parts):
            return None

        base_parts = importer_parts[:-up]
        base = ".".join(base_parts)

        if node.module:
            return f"{base}.{node.module}" if base else node.module
        else:
            # from . import x  => base is the parent package
            return base if base else None

    def _build_imported_by(self):
        self.imported_by = {m: set() for m in self.module_index.keys()}
        for importer, deps in self.imports.items():
            for dep in deps:
                if dep in self.imported_by:
                    self.imported_by[dep].add(importer)

    def _detect_cycles(self) -> List[List[str]]:
        G = self.to_networkx()
        return [list(c) for c in nx.simple_cycles(G)]
    

    def get_dependencies(self, module: str) -> List[str]:
        """
        Return direct dependency modules for a given module.
        """
        return sorted(self.imports.get(module, []))



if __name__ == "__main__":
    analyzer = ImportGraph("./backend/")

    analyzer.analyze()
    #print(analyzer.get_dependencies("orchestrator"))
    analyzer.print_summary()

    sorted_files = analyzer.print_sorted_dependencies(reverse=False)

    print(analyzer.get_dependencies("app"))


    try:
        analyzer.visualize("import_graph.png", highlight_cycles=True)
    except ImportError:
        print("\nNote: Install networkx and matplotlib for visualization: pip install networkx matplotlib")

    #print("\nImport chain for 'app' (showing dependencies):")
    #chain = analyzer.get_import_chain("app")
    #for item in chain:
    #    print(item)
