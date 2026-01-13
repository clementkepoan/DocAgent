import ast
from pathlib import Path
from typing import List, Dict, Any
# from langchain.text_splitter import Language, RecursiveCharacterTextSplitter

class CodeChunker:
    def __init__(self, parser_instance):
        """
        parser_instance: Your ImportGraph object (after analyze() is called)
        """
        self.parser = parser_instance
    
    def extract_chunks(self) -> List[Dict[str, Any]]:
        """
        Returns list of chunks ready for embedding:
        [
            {
                "id": "auth.py:create_user",
                "content": "def create_user(...)...\n    ...",
                "file_path": "src/auth.py",
                "module_name": "auth",
                "type": "function",
                "name": "create_user",
                "line_start": 15,
                "line_end": 42,
                "dependencies": ["database", "utils"]  # From parser.imports
            },
            ...
        ]
        """
        all_chunks = []
        
        # Process each module your parser found
        for module_name, file_path in self.parser.module_index.items():
            try:
                content = file_path.read_text(encoding="utf-8")
                file_chunks = self._chunk_single_file(module_name, file_path, content)
                all_chunks.extend(file_chunks)
            except Exception as e:
                print(f"⚠️ Skipping {file_path}: {e}")
        
        print(f"\n✅ Generated {len(all_chunks)} chunks")
        return all_chunks
    
    def _chunk_single_file(self, module_name: str, file_path: Path, content: str) -> List[Dict]:
        chunks = []
        file_dependencies = sorted(self.parser.imports.get(module_name, []))
        
        # Get relative path for cleaner metadata
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
                "file_path": rel_path,  # Use relative path
                "module_name": module_name,
                "type": "file",
                "name": module_name,
                "line_start": 1,
                "line_end": len(content.splitlines()),
                "dependencies": file_dependencies,
                # Optional metadata (empty for syntax errors)
                "arg_names": [],
                "return_type": None,
                "docstring": None,
                "has_decorators": False,
            }]
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Extract enhanced metadata
                metadata = self._extract_node_metadata(node, content)
                
                # Get source code boundaries
                lines = content.splitlines()
                chunk_lines = lines[node.lineno - 1:node.end_lineno]
                chunk_content = "\n".join(chunk_lines)
                
                chunk = {
                    "id": f"{module_name}:{node.name}",
                    "content": chunk_content,
                    "file_path": rel_path,
                    "module_name": module_name,
                    "type": "function" if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "class",
                    "name": node.name,
                    "line_start": node.lineno,
                    "line_end": node.end_lineno,
                    "dependencies": file_dependencies,
                    # Enhanced metadata
                    **metadata
                }
                chunks.append(chunk)
        
        # Fallback for files with no functions/classes
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
                "dependencies": file_dependencies,
                "arg_names": [],
                "return_type": None,
                "docstring": None,
                "has_decorators": False,
            })
        
        return chunks

    def _extract_node_metadata(self, node: ast.AST, content: str) -> Dict[str, Any]:
        """Extract function/class metadata from AST node."""
        metadata = {
            "arg_names": [],
            "return_type": None,
            "docstring": None,
            "has_decorators": len(getattr(node, 'decorator_list', [])) > 0,
        }
        
        # Extract arguments (skip 'self' and 'cls')
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = []
            for arg in node.args.args:
                arg_name = arg.arg
                if arg_name not in ['self', 'cls']:
                    args.append(arg_name)
            
            # Add *args and **kwargs if present
            if node.args.vararg:
                args.append(f"*{node.args.vararg.arg}")
            if node.args.kwarg:
                args.append(f"**{node.args.kwarg.arg}")
            
            metadata["arg_names"] = args
            
            # Extract return type annotation
            if node.returns:
                # Convert AST node to string representation
                metadata["return_type"] = ast.unparse(node.returns)
        
        # Extract docstring
        docstring = ast.get_docstring(node)
        if docstring:
            metadata["docstring"] = docstring.strip()
        
        return metadata

# ==================== TESTING ====================
if __name__ == "__main__":
    # Your existing parser usage
    from parser import ImportGraph
    
    # 1. Run your parser (unchanged)
    analyzer = ImportGraph("./backend")
    analyzer.analyze()
    
    # 2. Chunk it
    chunker = CodeChunker(analyzer)
    chunks = chunker.extract_chunks()
    
    # 3. Verify output
    # print(f"\n✅ Generated {len(chunks)} chunks")
    
    # Print first 3 chunks as samples
    for i, chunk in enumerate(chunks[:3]):
        print(f"\n--- Chunk {i+1}: {chunk['id']} ---")
        print(f"Type: {chunk['type']}")
        print(f"Dependencies: {chunk['dependencies']}")
        print(f"Content preview:\n{chunk['content'][:200]}...")
    
    # Save to JSON for inspection
    import json
    with open("chunks_test.json", "w") as f:
        # Convert Path objects to strings for JSON
        json.dump(chunks, f, indent=2, default=str)
    print("\n📄 Full chunks saved to 'chunks_test.json'")