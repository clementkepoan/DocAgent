from typing import List, Dict, Any
from pathlib import Path
import tree_sitter_python as tsp
from tree_sitter import Language, Parser, Node

class CodeChunker:
    def __init__(self, root_path: Path):
        # Build language parser once
        self.lang = Language(tsp.language())
        self.parser = Parser(self.lang)
        self.root_path = root_path
    
    def parse_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Parse Python file into structured chunks.
        Returns: List of chunk dicts with code, metadata, and tree-sitter node info.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        code_bytes = file_path.read_bytes()
        tree = self.parser.parse(code_bytes)
        
        chunks = []
        self._walk_tree(tree.root_node, code_bytes, file_path, chunks)
        file_docstring = self._extract_file_docstring(tree.root_node, code_bytes)
        imports = self._extract_imports(tree.root_node, code_bytes)
        
        for chunk in chunks:
            chunk["file_docstring"] = file_docstring
            chunk["imports"] = imports
        return chunks
    
    def _walk_tree(self, node: Node, code_bytes: bytes, file_path: Path, chunks: List[Dict], parent_stack: List[str] = None):
        parent_stack = parent_stack or []
        
        if node.type in ("function_definition", "class_definition"):
            chunk = self._extract_chunk(node, code_bytes, file_path, parent_stack)
            if chunk:
                chunks.append(chunk)
                
                # For classes, recurse into their body with updated parent stack
                if node.type == "class_definition":
                    new_stack = parent_stack + [chunk["name"]]
                    body_node = node.child_by_field_name("body")
                    if body_node:
                        for child in body_node.children:
                            self._walk_tree(child, code_bytes, file_path, chunks, new_stack)
                    return  # Don't recurse further into classes
        
        # Recurse into children
        for child in node.children:
            self._walk_tree(child, code_bytes, file_path, chunks, parent_stack)
    
    def _extract_chunk(self, node: Node, code_bytes: bytes, file_path: Path, parent_stack: List[str] = None) -> Dict[str, Any]:
        """Extract code slice and metadata from a node"""
        start_byte = node.start_byte
        end_byte = node.end_byte
        code = code_bytes[start_byte:end_byte].decode("utf-8")
        
        # Extract name
        name_node = node.child_by_field_name("name")
        name = name_node.text.decode("utf-8") if name_node else "unnamed"
        
        # Extract docstring (if exists)
        docstring = self._extract_docstring(node, code_bytes)

        # For classes, extract method names
        methods = []
        if node.type == "class_definition":
            body_node = node.child_by_field_name("body")
            if body_node:
                for child in body_node.children:
                    if child.type == "function_definition":
                        method_name_node = child.child_by_field_name("name")
                        if method_name_node:
                            methods.append(method_name_node.text.decode("utf-8"))

        if parent_stack:
            qualified_name = ".".join(parent_stack + [name])
        else:
            qualified_name = name

        parent_context = f"{'.'.join(parent_stack)}" if parent_stack else ""

        entity_type = "method" if parent_stack else node.type.replace("_definition", "")

        # Detect test functions more accurately
        is_test_func = (
            name.startswith("test_") or 
            name.endswith("_test") or 
            "test" in name.lower() and "unittest" in (docstring or "").lower()
        )
        
        # Detect test files
        file_path_lower = str(file_path).lower()
        is_test_file = any(x in file_path_lower for x in [
            "test_", "_test", "tests/", "/test", "conftest.py", "usage.py"  # ← Add usage.py here if it's your test file
        ])

        return {
            "name": name,
            "type": node.type,  # "function_definition" or "class_definition"
            "code": code,
            "file_path": str(file_path.relative_to(self.root_path)),
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "docstring": docstring,
            "byte_range": (start_byte, end_byte),
            "methods": methods,
            "qualified_name": qualified_name,
            "parent_class": parent_stack[-1] if parent_stack else None,
            "parent_context": parent_context,
            "parent_stack": parent_stack or [],
            "entity_type": entity_type,
            "folder_path": str(file_path.parent.relative_to(self.root_path)),
            "is_test": is_test_func or is_test_file
        }
    
    def _extract_docstring(self, node: Node, code_bytes: bytes) -> str:
        """Extract docstring from function/class body"""
        body_node = node.child_by_field_name("body")
        if not body_node or not body_node.children:
            return ""
        
        # Look for first string expression
        for child in body_node.children:
            if child.type == "expression_statement":
                expr = child.child(0)
                if expr and expr.type == "string":
                    return expr.text.decode("utf-8").strip('"\'')
        
        return ""
    
    def _extract_imports(self, root_node: Node, code_bytes: bytes) -> List[str]:
        """Extract import statements for context"""
        imports = []
        
        def walk(node):
            if node.type in ("import_statement", "import_from_statement"):
                imports.append(code_bytes[node.start_byte:node.end_byte].decode("utf-8").strip())
            
            for child in node.children:
                walk(child)
        
        walk(root_node)
        return imports

    def _extract_file_docstring(self, root_node: Node, code_bytes: bytes) -> str:
        """Extract module-level docstring"""
        # Look for first expression statement with a string
        for child in root_node.children:
            if child.type == "expression_statement":
                expr = child.child(0)
                if expr and expr.type == "string":
                    return expr.text.decode("utf-8").strip('"\'')
        return ""