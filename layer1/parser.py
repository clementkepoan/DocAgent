import ast
from pathlib import Path
from typing import Dict, Set, List, Optional

import networkx as nx


class ImportGraph:
    def __init__(self, root_folder: str):
        self.root_folder = Path(root_folder).resolve()
        self.imports: Dict[str, Set[str]] = {}
        self.imported_by: Dict[str, Set[str]] = {}
        self.cycles: List[List[str]] = []
        self.module_index: Dict[str, Path] = {}
        self.package_to_modules: Dict[str, Set[str]] = {}
        self.packages: Set[str] = set()
        self.module_metadata: Dict[str, Dict] = {}
        self.package_metadata: Dict[str, Dict] = {}

    def analyze(self) -> None:
        """Performs comprehensive import analysis on the codebase."""
        self.module_index = self._build_module_index()
        
        for module_name, file_path in self.module_index.items():
            self._parse_imports(module_name, file_path)
        
        self._build_imported_by()
        self.cycles = self._detect_cycles()

    def to_networkx(self) -> nx.DiGraph:
        """Creates a directed graph representing module imports."""
        G = nx.DiGraph()
        G.add_nodes_from(self.module_index.keys())
        for importer, deps in self.imports.items():
            for imported in deps:
                G.add_edge(importer, imported)
        return G

    def topo_order_independent_first(self) -> List[str]:
        """Returns modules sorted from most independent to most dependent."""
        G = self.to_networkx()
        sccs = list(nx.strongly_connected_components(G))
        node_to_scc = {}
        for i, scc in enumerate(sccs):
            for node in scc:
                node_to_scc[node] = i
        
        scc_graph = nx.DiGraph()
        scc_graph.add_nodes_from(range(len(sccs)))
        
        for node in G.nodes():
            node_scc = node_to_scc[node]
            for neighbor in G.successors(node):
                neighbor_scc = node_to_scc[neighbor]
                if node_scc != neighbor_scc:
                    scc_graph.add_edge(node_scc, neighbor_scc)
        
        try:
            scc_order = list(nx.topological_sort(scc_graph.reverse()))
        except nx.NetworkXUnfeasible:
            scc_order = list(range(len(sccs)))
        
        result = []
        for scc_idx in scc_order:
            scc = sccs[scc_idx]
            scc_modules = sorted(scc, key=lambda m: (
                len(self.imports.get(m, set())),
                -len(self.imported_by.get(m, set())),
                m
            ))
            result.extend(scc_modules)
        
        return result

    def get_sorted_by_dependency(self, reverse: bool = False) -> List[str]:
        """Returns modules sorted by dependency order."""
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
            # Show the actual imported module names (local targets only)
            imports_list = sorted(self.imports.get(mod, []))
            if imports_list:
                # Truncate if very long for readability
                imports_display = ", ".join(imports_list)
                if len(imports_display) > 200:
                    imports_display = imports_display[:197] + "..."
                print(f"       -> imports: {imports_display}")

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
        """Retrieves the import chain for a given module."""
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

    def get_dependencies(self, module: str) -> List[str]:
        """Returns direct dependency modules for a given module."""
        return sorted(self.imports.get(module, []))

    def get_sccs(self) -> List[Set[str]]:
        """Returns all Strongly Connected Components (cycle groups)."""
        G = self.to_networkx()
        sccs = list(nx.strongly_connected_components(G))
        return sccs
    
    def get_module_scc(self, module: str) -> Optional[Set[str]]:
        """Returns the SCC containing the given module."""
        if module not in self.module_index:
            return None
        
        G = self.to_networkx()
        sccs = list(nx.strongly_connected_components(G))
        
        for scc in sccs:
            if module in scc:
                if len(scc) == 1:
                    return None
                return scc
        return None
    
    def is_in_cycle(self, module: str) -> bool:
        """Returns True if the module is part of a cycle."""
        return self.get_module_scc(module) is not None

    def _build_module_index(self) -> Dict[str, Path]:
        """Builds an index of local modules from the filesystem."""
        index: Dict[str, Path] = {}
        self.packages = set()
        
        for path in self.root_folder.rglob("*.py"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            
            rel = path.relative_to(self.root_folder)
            
            if rel.name == "__init__.py":
                package_name = ".".join(rel.parent.parts)
                if package_name:
                    self.packages.add(package_name)
                
                content = path.read_text(encoding="utf-8").strip()
                if not content or content.startswith("#"):
                    continue
                mod = ".".join(rel.parent.parts) if rel.parent.parts else ""
                if mod:
                    index[mod] = path
                continue
            
            mod = ".".join(rel.with_suffix("").parts)
            index[mod] = path
        
        self.package_to_modules = {pkg: set() for pkg in self.packages}
        
        for module_name in index:
            if module_name in self.packages:
                continue
            
            last_dot_pos = module_name.rfind('.')
            if last_dot_pos == -1:
                continue
            
            parent_package = module_name[:last_dot_pos]
            
            if parent_package in self.packages:
                self.package_to_modules[parent_package].add(module_name)
        
        for module_name, path in index.items():
            parts = module_name.split(".")
            self.module_metadata[module_name] = {
                "depth": len(parts) - 1,
                "is_root_module": len(parts) == 1,
                "file_path": str(path),
                "parent_package": ".".join(parts[:-1]) if len(parts) > 1 else None,
            }
        
        for pkg in self.packages:
            pkg_parts = pkg.split(".")
            self.package_metadata[pkg] = {
                "depth": len(pkg_parts) - 1,
                "is_root_package": len(pkg_parts) == 1,
                "module_count": len(self.package_to_modules.get(pkg, [])),
                "path": str(self.root_folder.joinpath(*pkg_parts)),
            }
        
        return index

    def _parse_imports(self, module_name: str, file_path: Path) -> None:
        """Parses imports from a Python file."""
        self.imports[module_name] = set()
        self.imported_by.setdefault(module_name, set())
        
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            raise SystemError(f"Error parsing {file_path}: {e}")

        def exists_locally(dotted: str) -> bool:
            """Return True if dotted path is a local module or package."""
            return dotted in self.module_index or dotted in self.packages

        def resolve_dotted_path(dotted: str) -> Optional[str]:
            """Try 'a.b.c', then 'a.b', then 'a' - but only if they exist."""
            parts = dotted.split(".")
            for i in range(len(parts), 0, -1):
                candidate = ".".join(parts[:i])
                if exists_locally(candidate):
                    return candidate
            return None

        def record_import(importer: str, target: str) -> None:
            """Record that importer imports target, expanding packages."""
            if target in self.packages:
                self.imports[importer].update(self.package_to_modules.get(target, set()))
            elif target in self.module_index:
                self.imports[importer].add(target)

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

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = try_resolve_absolute(alias.name) or try_resolve_fallback(alias.name)
                    if resolved:
                        record_import(module_name, resolved)
            
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    if not node.module:
                        continue
                    
                    resolved_base = try_resolve_absolute(node.module) or try_resolve_fallback(node.module)
                    if not resolved_base:
                        continue
                    
                    for alias in node.names:
                        if alias.name == "*":
                            record_import(module_name, resolved_base)
                            continue
                        
                        candidate = f"{resolved_base}.{alias.name}"
                        resolved_sub = resolve_dotted_path(candidate)
                        if resolved_sub:
                            record_import(module_name, resolved_sub)
                        else:
                            if resolved_base in self.module_index or resolved_base in self.packages:
                                self.imports[module_name].add(resolved_base)
                
                else:
                    abs_base = self._resolve_from_import_base(module_name, node)
                    if not abs_base:
                        continue
                    
                    resolved_base = resolve_dotted_path(abs_base)
                    if not resolved_base:
                        continue
                    
                    for alias in node.names:
                        if alias.name == "*":
                            record_import(module_name, resolved_base)
                            continue
                        
                        candidate = f"{abs_base}.{alias.name}"
                        resolved_sub = resolve_dotted_path(candidate)
                        if resolved_sub:
                            record_import(module_name, resolved_sub)
                        else:
                            if resolved_base in self.module_index or resolved_base in self.packages:
                                self.imports[module_name].add(resolved_base)
        
        self.imports[module_name].discard(module_name)

    def _resolve_absolute_module(self, dotted: str) -> Optional[str]:
        """Resolves a dotted path to the best matching local module."""
        parts = dotted.split(".")
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in self.module_index:
                return candidate
        return None

    def _resolve_from_import_base(self, importer: str, node: ast.ImportFrom) -> Optional[str]:
        """Computes the absolute base module for from-import statements."""
        if node.level == 0:
            if not node.module:
                return None
            return node.module
        
        importer_parts = importer.split(".")
        up = node.level
        if up > len(importer_parts):
            return None
        
        base_parts = importer_parts[:-up]
        base = ".".join(base_parts)
        
        if node.module:
            return f"{base}.{node.module}" if base else node.module
        else:
            return base if base else None

    def _build_imported_by(self) -> None:
        """Builds reverse import mapping."""
        self.imported_by = {m: set() for m in self.module_index.keys()}
        for importer, deps in self.imports.items():
            for dep in deps:
                if dep in self.imported_by:
                    self.imported_by[dep].add(importer)

    def _detect_cycles(self) -> List[List[str]]:
        """Detects circular dependencies."""
        G = self.to_networkx()
        return [list(c) for c in nx.simple_cycles(G)]

    def print_module_structure(self):
        """
        Print module structure using EXACTLY the same logic
        as _build_module_index (no re-scanning).
        """

        if not self.module_index:
            raise ValueError("⚠️ Module index is empty. Run analyze() first.")

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