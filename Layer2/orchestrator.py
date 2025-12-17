from langgraph.graph import StateGraph, END
from schemas import AgentState
from retriever import retrieve
from writer import write
from reviewer import review

def review_router(state: AgentState):
    if state["review_passed"]:
        return END
    else:
        return "write"

def build_graph():
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("retrieve", retrieve)
    graph.add_node("write", write)
    graph.add_node("review", review)

    # Entry point
    graph.set_entry_point("retrieve")

    # Flow
    graph.add_edge("retrieve", "write")
    graph.add_edge("write", "review")

    # Conditional loop
    graph.add_conditional_edges("review", review_router)

    return graph.compile()

if __name__ == "__main__":
    app = build_graph()

    initial_state: AgentState = {
        "file": "auth.py",
        "code_chunks": [],
        "dependency_docs": ["database.py manages DB connection"],
        "draft_doc": None,
        "review_passed": False
    }

    final_state = app.invoke(initial_state)

    print("\n✅ FINAL DOC OUTPUT:")
    print(final_state["draft_doc"])
