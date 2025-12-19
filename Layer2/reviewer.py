from .schemas import AgentState

def review(state: AgentState) -> AgentState:
    print("🧪 Reviewer running")

    doc = state["draft_doc"]

    # Simple validation rule
    if doc and "Code:" in doc:
        state["review_passed"] = True
    else:
        state["review_passed"] = False

    return state
