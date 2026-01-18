import ast
from pathlib import Path
from typing import Any, Dict, List

from parser import ImportGraph


class CodeChunker:
    """Extracts code chunks from Python source files for embedding."""
    
    def __init__(self, parser_instance: ImportGraph) -> None:
        """Initializes the chunker with an ImportGraph instance.
        
        Args:
            parser_instance: Analyzed ImportGraph object.
        """
        self.parser = parser_instance
    
    def extract_chunks(self) -> List[Dict[str, Any]]:
        """Extracts chunks from all modules in the parser's index.
        
        Returns:
            List of chunk dictionaries containing code and metadata.
        """
        all_chunks = []
        
        for module_name, file_path in self.parser.module_index.items():
            try:
                content = file_path.read_text(encoding="utf-8")
                file_chunks = self._chunk_single_file(module_name, file_path, content)
                all_chunks.extend(file_chunks)
            except Exception:
                continue
        
        return all_chunks
    
    def _chunk_single_file(self, module_name: str, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Chunks a single Python file into functions and classes.
        
        Args:
            module_name: Name of the module.
            file_path: Path to the file.
            content: File content as string.
        
        Returns:
            List of chunk dictionaries.
        """
        chunks = []
        file_dependencies = sorted(self.parser.imports.get(module_name, []))
        
        try:
            rel_path = str(file_path.relative_to(self.parser.root_folder))
        except ValueError:
            rel_path = str(file_path)
        
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return [{
                "id": f"{module_name}:file",
                "content": content,
                "file_path": rel_path,
                "module_name": module_name,
                "type": "file",
                "name": module_name,
                "line_start": 1,
                "line_end": len(content.splitlines()),
                "file_dependencies": file_dependencies,
                "dependencies": file_dependencies,
                "arg_names": [],
                "return_type": "None",
                "docstring": "",
                "has_decorators": False,
            }]

        alias_map = self._build_alias_map(tree, module_name)
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                metadata = self._extract_node_metadata(node, content)
                dependencies = self._extract_node_dependencies(node, alias_map, file_dependencies)
                
                lines = content.splitlines()
                start_lineno = node.lineno

                if hasattr(node, 'decorator_list') and node.decorator_list:
                    decorator_lines = [d.lineno for d in node.decorator_list]
                    start_lineno = min(decorator_lines)

                chunk_lines = lines[start_lineno - 1:node.end_lineno]
                chunk_content = "\n".join(chunk_lines)
                
                chunk = {
                    "id": f"{module_name}:{node.name}",
                    "content": chunk_content,
                    "file_path": rel_path,
                    "module_name": module_name,
                    "type": "function" if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "class",
                    "name": node.name,
                    "line_start": start_lineno,
                    "line_end": node.end_lineno,
                    "file_dependencies": file_dependencies,
                    "dependencies": dependencies,
                    **metadata
                }
                chunks.append(chunk)
        
        if not chunks:
            chunks.append({
                "id": f"{module_name}:file",
                "content": content,
                "file_path": rel_path,
                "module_name": module_name,
                "type": "file",
                "name": module_name,
                "line_start": 1,
                "line_end": len(content.splitlines()),
                "file_dependencies": file_dependencies,
                "dependencies": file_dependencies,
                "arg_names": [],
                "return_type": "None",
                "docstring": "",
                "has_decorators": False,
            })
        
        return chunks

    def _extract_node_metadata(self, node: ast.AST, content: str) -> Dict[str, Any]:
        """Extracts metadata from a function or class node.
        
        Args:
            node: AST node representing function or class.
            content: Source code content.
        
        Returns:
            Dictionary containing metadata.
        """
        metadata = {
            "arg_names": [],
            "return_type": "None",
            "docstring": "",
            "has_decorators": len(getattr(node, 'decorator_list', [])) > 0,
        }
        
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = []
            for arg in node.args.args:
                arg_name = arg.arg
                if arg_name not in ['self', 'cls']:
                    args.append(arg_name)
            
            if node.args.vararg:
                args.append(f"*{node.args.vararg.arg}")
            if node.args.kwarg:
                args.append(f"**{node.args.kwarg.arg}")
            
            metadata["arg_names"] = args
            
            if node.returns:
                metadata["return_type"] = ast.unparse(node.returns)
        
        docstring = ast.get_docstring(node)
        if docstring:
            metadata["docstring"] = docstring.strip()
        
        return metadata
    
    def _extract_node_dependencies(self, node: ast.AST, alias_map: Dict[str, str], file_dependencies: List[str]) -> List[str]:
        """Extracts dependencies used within a node.
        
        Args:
            node: AST node to analyze.
            alias_map: Mapping of alias names to module names.
            file_dependencies: List of file-level dependencies.
        
        Returns:
            List of dependencies used in the node.
        """
        if not alias_map:
            return []
        
        used_imports = set()
        
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id in alias_map:
                if alias_map[child.id] in file_dependencies:
                    used_imports.add(alias_map[child.id])
            
            elif isinstance(child, ast.Attribute):
                root = child.value
                while isinstance(root, ast.Attribute):
                    root = root.value
                
                if isinstance(root, ast.Name) and root.id in alias_map:
                    if alias_map[root.id] in file_dependencies:
                        used_imports.add(alias_map[root.id])
        
        return sorted(list(used_imports))
    
    def _build_alias_map(self, tree: ast.AST, current_module_name: str) -> Dict[str, str]:
        """Builds alias mapping for imported names in a module.
        
        Args:
            tree: AST of the module.
            current_module_name: Full module name.
        
        Returns:
            Dictionary mapping alias names to module names.
        """
        alias_map = {}
        current_module_parts = current_module_name.split('.')
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split('.')[0]
                    alias_map[alias.asname or name] = name
            
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    base_parts = current_module_parts[:-1]
                    
                    if node.level > 1:
                        base_parts = base_parts[:-(node.level - 1)]
                    
                    if node.module:
                        base_parts.append(node.module)
                    
                    target_module = '.'.join(base_parts) if base_parts else ''
                else:
                    target_module = node.module
                
                if target_module:
                    for alias in node.names:
                        alias_map[alias.asname or alias.name] = target_module
        
        return alias_map