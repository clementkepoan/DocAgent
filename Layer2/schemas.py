from typing import TypedDict, List, Optional

class AgentState(TypedDict):
    # which file we are documenting
    file: str

    # retrieved raw code chunks (from vector DB in real version)
    code_chunks: List[str]

    # Output from layer 1.
    dependency: List[str]

    # dependency docs (loaded markdown summaries)
    dependency_docs: List[str]

    # generated documentation draft
    draft_doc: Optional[str]

    # did reviewer approve?
    review_passed: bool
