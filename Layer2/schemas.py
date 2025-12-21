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

    #for reviewer
    reviewer_suggestions: str

    #reviewr max retry
    retry_count: int

    ROOT_PATH: str

