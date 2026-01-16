from langgraph.graph import StateGraph, END
from layer2.schemas import AgentState
from layer2.retriever import retrieve
from layer2.writer import module_write, folder_write, condenser_write
from layer2.reviewer import review
from layer1.parser import ImportGraph
from tqdm import tqdm
import time



MAX_RETRIES = 1

def review_router(state: AgentState) -> str:
    

    if state["review_passed"]:
        return END

    if state["retry_count"] >= MAX_RETRIES:
        # print("⚠️ Max retries reached. Accepting best-effort doc.")
        return END

    return "write"



def build_graph():
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("retrieve", retrieve)
    graph.add_node("write", module_write)
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
    print("\n" + "="*80)
    print("🚀 DocAgent Runnning yeee")
    print("="*80 + "\n")
    
    app = build_graph()

    ROOT_PATH = "./"

    print("📊 Analyzing codebase structure...")
    analyzer = ImportGraph(ROOT_PATH)
    analyzer.analyze()
    print(f"✓ Found {len(analyzer.module_index)} modules\n")

    topo_order = analyzer.get_sorted_by_dependency(reverse=False)
    final_docs = {}

    print("📝 Generating module documentation...\n")
    for module in tqdm(topo_order, desc="Modules", unit="module", colour="blue"):
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
        final_docs[module] = result["draft_doc"]
    
    print("\n✓ Module documentation complete\n")

    # Generate folder-level documentation
    print("📁 Generating folder-level documentation...")
    folder_docs = folder_write(analyzer, final_docs)
    print("✓ Folder documentation complete\n")
    
    # # Generate comprehensive markdown documentation
    # print("📚 Generating comprehensive documentation...")
    # condenser_write(analyzer, final_docs, folder_docs)
    # print("✓ Comprehensive documentation complete\n")
    
    # print("="*80)
    # print("✨ DOCUMENTATION GENERATION SUCCESSFUL!")
    # print("="*80)
    # print("\n📂 Output files:")
    # print("  - DOCUMENTATION.md (Comprehensive markdown)")



    


