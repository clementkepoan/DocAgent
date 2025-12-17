from schemas import AgentState

def retrieve(state: AgentState) -> AgentState:
    print("🔍 Retriever running")

    file = state["file"]

    # Fake retrieval (replace with Chroma later)
    state["code_chunks"] = [
        f"def example_function():",
        f"    print('Hello from {file}')"
    ]

    return state
