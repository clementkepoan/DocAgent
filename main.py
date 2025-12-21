from langgraph.graph import StateGraph, END
from layer2.schemas import AgentState
from layer2.retriever import retrieve
from layer2.writer import write
from layer2.reviewer import review
from layer1.parser import ImportGraph

MAX_RETRIES = 1

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


    ROOT_PATH = "./backend/"

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
            "ROOT_PATH": ROOT_PATH,
        }

        
        

        result = app.invoke(state)
        final_docs[module] = result["draft_doc"] #finaldocs indexed by module name
        print(f"Final doc for {module}:\n{result['draft_doc']}\n{'-'*40}\n")

    # Make a final output of all docs in output.txt
    with open("output_2_retries.txt", "w") as f:
        for module, doc in final_docs.items():
            f.write(f"File: {module}\n")
            n = 100
            formatted_doc = "\n".join([doc[i:i+n] for i in range(0, len(doc), n)])
            f.write(formatted_doc + "\n")
            f.write("\n" + "="*80 + "\n")
    


