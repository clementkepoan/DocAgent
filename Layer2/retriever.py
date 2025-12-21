from pathlib import Path
import ast
from typing import List
from .schemas import AgentState
from layer1.parser import ImportGraph


# Cache the analyzer to avoid rebuilding on every call
_analyzer_cache = None

def get_analyzer(root_path: Path) -> ImportGraph:
    """Get or create a cached ImportGraph analyzer."""
    global _analyzer_cache
    if _analyzer_cache is None:
        _analyzer_cache = ImportGraph(str(root_path))
        # Build the module index without analyzing imports
        _analyzer_cache.module_index = _analyzer_cache._build_module_index()
    return _analyzer_cache


def retrieve(state: AgentState) -> AgentState:
    """
    Retrieves code chunks from a file using the parser's folder structure.
    """
    print("🔍 Retriever running")

    module_name = state["file"]
    root_path = Path("/Users/mulia/Desktop/Projects/CodebaseAI/Dummy")
    
    # Get the analyzer with folder structure
    analyzer = get_analyzer(root_path)
    
    # Look up the file path
    file_path = analyzer.module_index.get(module_name)
    
    if not file_path or not file_path.exists():
        print(f"⚠️ File not found for module: {module_name}")
        print(f"   Available modules: {list(analyzer.module_index.keys())}")
        state["code_chunks"] = []
        return state

    print(f"📄 Reading file: {file_path}")

    source = file_path.read_text(encoding="utf-8")

    # Parse AST
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"❌ Syntax error in {file_path}: {e}")
        state["code_chunks"] = [source]
        return state

    chunks: List[str] = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            start = node.lineno - 1
            end = node.end_lineno
            func_source = source.splitlines()[start:end]
            chunks.append("\n".join(func_source))

        elif isinstance(node, ast.ClassDef):
            start = node.lineno - 1
            end = node.end_lineno
            class_source = source.splitlines()[start:end]
            chunks.append("\n".join(class_source))

    # Fallback: whole file
    if not chunks:
        chunks.append(source)

    state["code_chunks"] = chunks

    print(f"✅ Retrieved {len(chunks)} code chunks from {module_name}")
    
    return state