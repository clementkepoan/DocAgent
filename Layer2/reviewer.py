from .schemas import AgentState

def review(state: AgentState) -> AgentState:
    print("🧪 Reviewer running")

    

    #placeholder logic: always pass review
    state["review_passed"] = True
    

    return state
#Later need to inject LLM based review logic (CODE + DOCS COMPARISON)