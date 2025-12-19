from .schemas import AgentState
from .llmprovider import LLMProvider

llm = LLMProvider()

def write(state: AgentState) -> AgentState:
    print("✍️ Writer running")

    file = state["file"]
    code = state["code_chunks"]
    deps = state["dependency_docs"]

    prompt = f"""
You are documenting {file}.

Dependencies:
{deps if deps else "None"}

Code:
{code}

Write a short module-level description.
"""

    state["draft_doc"] = "Code:" #placeholder to make it stop
    return state
