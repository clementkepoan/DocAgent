from pathlib import Path
import ast
from typing import List
from .schemas import AgentState

# Path to your Dummy folder
DUMMY_ROOT = Path("/Users/mulia/Desktop/Projects/CodebaseAI/Dummy")


def retrieve(state: AgentState) -> AgentState:
    #Fake non chroma implementation
    ###########################################################################################
    print("🔍 Retriever running")

    module = state["file"]
    file_path = DUMMY_ROOT / f"{module}.py"

    if not file_path.exists():
        print(f"⚠️ File not found: {file_path}")
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

    #print(f"✅ Retrieved {len(chunks)} code chunks from {module}")
    #print(f"Chunks: {chunks}")
    ###########################################################################################
    return state
