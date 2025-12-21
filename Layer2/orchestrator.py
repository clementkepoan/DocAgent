from langgraph.graph import StateGraph, END
from .schemas import AgentState
from .retriever import retrieve
from .writer import write
from .reviewer import review
from layer1.parser import ImportGraph

MAX_RETRIES = 3

def review_router(state: AgentState):
    

    if state["review_passed"]:
        return END

    if state["retry_count"] >= MAX_RETRIES:
        print("⚠️ Max retries reached. Accepting best-effort doc.")
        return END

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


    ROOT_PATH = "/Users/mulia/Desktop/Projects/CodebaseAI/Dummy"

    analyzer = ImportGraph(ROOT_PATH)
    analyzer.analyze()

    topo_order = analyzer.get_sorted_by_dependency(reverse=False)
    final_docs = {}

    for module in topo_order:
        dependencies = analyzer.get_dependencies(module)

        state: AgentState = {
            "file": module,
            "dependencies": dependencies,
            "code_chunks": [],
            "dependency_docs": [
                final_docs[d] for d in dependencies if d in final_docs
            ],
            "draft_doc": None,
            "review_passed": False,
            "reviewer_suggestions": None,
            "retry_count": 0,
        }

        
        

        result = app.invoke(state)
        final_docs[module] = result["draft_doc"] #finaldocs indexed by module name
        print(f"Final doc for {module}:\n{result['draft_doc']}\n{'-'*40}\n")

    # Make a final output of all docs in output.txt
    with open("output_3_retries.txt", "w") as f:
        for module, doc in final_docs.items():
            f.write(f"File: {module}\n")
            f.write(doc)
            f.write("\n" + "="*80 + "\n")
    


