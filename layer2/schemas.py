from typing import TypedDict, List, Optional

class AgentState(TypedDict):
    # which file we are documenting
    file: str

    # Output from layer 1.
    dependencies: List[str]

    # retrieved raw code chunks (from vector DB in real version)
    code_chunks: List[str]

    # dependency docs (loaded markdown summaries)
    dependency_docs: List[str]

    # generated documentation draft
    draft_doc: Optional[str]

    # did reviewer approve?
    review_passed: bool

    # for reviewer
    reviewer_suggestions: str

    # reviewer max retry
    retry_count: int

    ROOT_PATH: str

    # High-level coherence doc for modules in cycles
    scc_context: Optional[str]

    # Whether this module is part of a cycle (SCC size > 1)
    is_cyclic: bool


