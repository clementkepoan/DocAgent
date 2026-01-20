from pathlib import Path
import ast
from typing import List
from layer2.schemas.agent_state import AgentState
from layer1.parser import ImportGraph




def name_to_path(name: str, root_path: Path) -> Path:
    """Convert file name to filepath , by converting dots to slashes and adding .py"""
    parts = name.split(".")
    return root_path.joinpath(*parts).with_suffix(".py")



def retrieve(state: AgentState) -> AgentState:
    """
    Retrieves code chunks from a file using the parser's folder structure.
    """
    # print("🔍 Retriever running")

    module_name = state["file"]
    root_path = state["ROOT_PATH"]



    # Look up the file path
    file_path = name_to_path(module_name, Path(root_path))

    if not file_path or not file_path.exists():
        print(f"⚠️ File not found for module: {module_name}")
        state["code_chunks"] = []
        return state

    # print(f"📄 Reading file: {file_path}")

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

    # print(f"✅ Retrieved {len(chunks)} code chunks from {module_name}")

    return state
