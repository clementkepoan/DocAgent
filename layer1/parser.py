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
        # e.g. {"auth": ".../auth.py", "pkg.utils": ".../pkg/utils.py"}
        self.module_index: Dict[str, Path] = {}

        # Local packages
        self.package_to_modules: Dict[str, Set[str]] = {}  # NEW
        self.packages: Set[str] = set()  # NEW

        #Package metadata
        self.module_metadata: Dict[str, Dict] = {}
        self.package_metadata: Dict[str, Dict] = {}




    # -----------------------------
    # Public API
    # -----------------------------
    def analyze(self):
        """Main analysis method"""
        # print(f"Scanning folder: {self.root_folder}")

        # Build module index once (no heuristics)
        self.module_index = self._build_module_index()
        print(f"✅ Indexed {len(self.module_index)} local modules")
        # for mod in self.module_index:
        #     print(mod)
            
        print(f"✅ Indexed {len(self.packages)} local packages")
        # print(self.packages)

        # for pkg in self.package_to_modules:
        #     print(pkg, self.package_to_modules[pkg])

        # Parse imports for each local module
        for module_name, file_path in self.module_index.items():
            self._parse_imports(module_name, file_path)

        # for mod in self.imports:
        #     print(mod, self.imports[mod])

        # Build imported_by map
        self._build_imported_by()

        # Detect cycles
        self.cycles = self._detect_cycles()

        print(f"✅ Analysis complete. Found {len(self.cycles)} circular dependencies.")

    def to_networkx(self) -> nx.DiGraph:
        """Graph direction: importer -> imported (matches your arrow meaning)."""
        G = nx.DiGraph()
        G.add_nodes_from(self.module_index.keys())
        for importer, deps in self.imports.items():
            for imported in deps:
                G.add_edge(importer, imported)
        return G

    # def topo_order_independent_first(self) -> List[str]:
    #     """
    #     Returns modules from most independent -> most dependent (dependencies first).
    #     Since our edges are importer->imported (dependent->dependency), we topo sort on reversed graph.
    #     """
    #     G = self.to_networkx()
    #     try:
    #         return list(nx.topological_sort(G.reverse()))
    #     except nx.NetworkXUnfeasible:
    #         # cycles exist; return a stable node list
    #         return list(G.nodes)

    def topo_order_independent_first(self) -> List[str]:
        """
        Returns modules from most independent -> most dependent (dependencies first).
        Properly handles cyclic dependencies by:
        1. Detecting strongly connected components (SCCs)
        2. Creating a DAG of SCCs
        3. Topologically sorting SCCs
        4. Within each SCC, ordering by import count
        """
        import networkx as nx
        from itertools import chain
        
        # Build the dependency graph
        G = self.to_networkx()
        
        # Find strongly connected components (SCCs)
        # Each SCC is a set of nodes that form a cycle (or singleton)
        sccs = list(nx.strongly_connected_components(G))
        
        # Create a mapping: node -> SCC index
        node_to_scc = {}
        for i, scc in enumerate(sccs):
            for node in scc:
                node_to_scc[node] = i
        
        # Build a DAG of SCCs (collapsed graph)
        scc_graph = nx.DiGraph()
        scc_graph.add_nodes_from(range(len(sccs)))
        
        for node in G.nodes():
            node_scc = node_to_scc[node]
            for neighbor in G.successors(node):
                neighbor_scc = node_to_scc[neighbor]
                if node_scc != neighbor_scc:  # Edge between different SCCs
                    scc_graph.add_edge(node_scc, neighbor_scc)
        
        # Topologically sort the SCC graph
        # This gives us the order in which to process SCCs
        try:
            scc_order = list(nx.topological_sort(scc_graph.reverse()))
        except nx.NetworkXUnfeasible:
            # Should never happen since scc_graph is a DAG
            scc_order = list(range(len(sccs)))
        
        # Within each SCC, order modules by:
        # 1. Import count (ascending) - fewer imports first
        # 2. Imported_by count (descending) - more importers first
        # 3. Module name (alphabetical) - deterministic tie-breaker
        result = []
        
        for scc_idx in scc_order:
            scc = sccs[scc_idx]
            
            # Sort modules within this SCC
            scc_modules = sorted(scc, key=lambda m: (
                len(self.imports.get(m, set())),           # Fewer imports first
                -len(self.imported_by.get(m, set())),      # More importers first
                m                                           # Alphabetical
            ))
            
            result.extend(scc_modules)
        
        return result

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

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _build_module_index(self) -> Dict[str, Path]:
        """
        Builds local module names based on filesystem:
        - foo.py => "foo"
        - pkg/__init__.py => "pkg"
        - pkg/utils.py => "pkg.utils"
        
        Every module gets a full dotted path relative to root.
        Skips __pycache__ directories and empty __init__.py files.
        """
        index: Dict[str, Path] = {}
        self.packages = set()

        for path in self.root_folder.rglob("*.py"):
            # Skip __pycache__ directories
            if not path.is_file() or "__pycache__" in path.parts:
                continue

            rel = path.relative_to(self.root_folder)
            # print(rel.name)

            # Handle __init__.py files (they represent the package itself)
            if rel.name == "__init__.py":
                # Add package into self.packages
                package_name = ".".join(rel.parent.parts)
                if package_name:  # Skip root-level __init__.py
                    self.packages.add(package_name)
                
                # Skip empty or comment-only __init__.py files
                content = path.read_text(encoding="utf-8").strip()
                if not content or content.startswith("#"):
                    continue
                mod = ".".join(rel.parent.parts) if rel.parent.parts else ""
                if mod:
                    index[mod] = path
                continue

            # For all other .py files, ALWAYS use full dotted path
            mod = ".".join(rel.with_suffix("").parts)
            index[mod] = path
        
        # Initialize with empty sets for each package
        self.package_to_modules = {pkg: set() for pkg in self.packages}
        
        # Assign each module to its direct parent package
        for module_name in index:
            # Skip packages themselves - they are not modules of their parent
            if module_name in self.packages:
                continue
                
            # Find parent package (everything before the last dot)
            last_dot_pos = module_name.rfind('.')
            if last_dot_pos == -1:
                # Top-level module (no parent package)
                continue
                
            parent_package = module_name[:last_dot_pos]
            
            # Only add if parent is a recognized package
            if parent_package in self.packages:
                self.package_to_modules[parent_package].add(module_name)

        

        # -----------------------------
        # Build metadata (FACTS ONLY)
        # -----------------------------

        # Module metadata
        for module_name, path in index.items():
            parts = module_name.split(".")
            self.module_metadata[module_name] = {
                "depth": len(parts) - 1,
                "is_root_module": len(parts) == 1,
                "file_path": str(path),
                "parent_package": ".".join(parts[:-1]) if len(parts) > 1 else None,
            }

        # Package metadata
        for pkg in self.packages:
            pkg_parts = pkg.split(".")
            self.package_metadata[pkg] = {
                "depth": len(pkg_parts) - 1,
                "is_root_package": len(pkg_parts) == 1,
                "module_count": len(self.package_to_modules.get(pkg, [])),
                "path": str(self.root_folder.joinpath(*pkg_parts)),
            }


        return index

    def _parse_imports(self, module_name: str, file_path: Path):
        """
        Parse imports from a file; resolve them ONLY if they map to local modules/packages.
        Handles package expansion: importing a package adds all its modules.
        """
        self.imports[module_name] = set()
        self.imported_by.setdefault(module_name, set())

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return

        # Helper: Check if path exists EXACTLY (no parent matching)
        def exists_locally(dotted: str) -> bool:
            """Return True if dotted path is a local module or package."""
            return dotted in self.module_index or dotted in self.packages

        # Helper: Resolve dotted path to most specific local target
        def resolve_dotted_path(dotted: str) -> Optional[str]:
            """Try 'a.b.c', then 'a.b', then 'a' - but only if they exist."""
            parts = dotted.split(".")
            for i in range(len(parts), 0, -1):
                candidate = ".".join(parts[:i])
                if exists_locally(candidate):
                    return candidate
            return None

        # Helper: Record import with package expansion
        def record_import(importer: str, target: str):
            """Record that importer imports target, expanding packages."""
            if target in self.packages:
                self.imports[importer].update(self.package_to_modules.get(target, set()))
            elif target in self.module_index:
                self.imports[importer].add(target)

        # Extract importer's package context for fallback
        module_parts = module_name.split(".")
        package_prefix = ".".join(module_parts[:-1]) if len(module_parts) > 1 else None

        def try_resolve_absolute(dotted_path: str) -> Optional[str]:
            """Try resolving as absolute path only."""
            return resolve_dotted_path(dotted_path) if exists_locally(dotted_path) else None

        def try_resolve_fallback(dotted_path: str) -> Optional[str]:
            """Try package-relative resolution (e.g., 'pkg.os')."""
            if not package_prefix:
                return None
            candidate = f"{package_prefix}.{dotted_path}"
            return resolve_dotted_path(candidate) if exists_locally(candidate) else None

        # Process all import nodes
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                # Conditions 1-3: import module/package
                for alias in node.names:
                    # Try absolute first, then fallback
                    resolved = try_resolve_absolute(alias.name) or try_resolve_fallback(alias.name)
                    if resolved:
                        record_import(module_name, resolved)

            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:  # Absolute from-import
                    if not node.module:
                        continue
                    
                    # Resolve the source module/package
                    resolved_base = try_resolve_absolute(node.module) or try_resolve_fallback(node.module)
                    if not resolved_base:
                        continue
                    
                    for alias in node.names:
                        if alias.name == "*":
                            # Conditions 6-7: from x import *
                            record_import(module_name, resolved_base)
                            continue
                        
                        # Try resolving submodule
                        candidate = f"{resolved_base}.{alias.name}"
                        resolved_sub = resolve_dotted_path(candidate)
                        if resolved_sub:
                            # Conditions 4-5: from pkg import submodule
                            record_import(module_name, resolved_sub)
                        else:
                            # Conditions 8-9: from pkg/module import name
                            # Record source only (no expansion)
                            if resolved_base in self.module_index or resolved_base in self.packages:
                                self.imports[module_name].add(resolved_base)
                
                else:  # Relative imports (level > 0)
                    abs_base = self._resolve_from_import_base(module_name, node)
                    if not abs_base:
                        continue
                    
                    resolved_base = resolve_dotted_path(abs_base)
                    if not resolved_base:
                        continue
                    
                    for alias in node.names:
                        if alias.name == "*":
                            # Condition 13: from . import *
                            record_import(module_name, resolved_base)
                            continue
                        
                        candidate = f"{abs_base}.{alias.name}"
                        resolved_sub = resolve_dotted_path(candidate)
                        if resolved_sub:
                            # Conditions 10-12, 14: relative submodule imports
                            record_import(module_name, resolved_sub)
                        else:
                            # Importing a name from relative base
                            if resolved_base in self.module_index or resolved_base in self.packages:
                                self.imports[module_name].add(resolved_base)

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

    def print_module_structure(self):
            """
            Print module structure using EXACTLY the same logic
            as _build_module_index (no re-scanning).
            """

            if not self.module_index:
                print("⚠️ Module index is empty. Run analyze() first.")
                return

            # Build a tree from module names
            tree = {}

            for module in self.module_index.keys():
                parts = module.split(".")
                node = tree
                for part in parts:
                    node = node.setdefault(part, {})

            def walk(node: dict, prefix: str = "", is_last: bool = True):
                keys = list(node.keys())
                for i, key in enumerate(keys):
                    last = i == len(keys) - 1
                    connector = "└── " if last else "├── "
                    print(prefix + connector + key)

                    extension = "    " if last else "│   "
                    walk(node[key], prefix + extension, last)

            print("\n📦 Module Structure (derived from module_index)")
            walk(tree)



if __name__ == "__main__":
    analyzer = ImportGraph("./sourcecode")

    analyzer.analyze()
    #print(analyzer.get_dependencies("orchestrator"))
    analyzer.print_summary()

    sorted_files = analyzer.print_sorted_dependencies(reverse=False)

    # print(analyzer.get_dependencies("idm_vton.preprocess.humanparsing.mhp_extension.detectron2.detectron2.modeling.proposal_generator.rrpn"))

    # analyzer.print_module_structure()
    
