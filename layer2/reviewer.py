from .schemas import AgentState
from .llmprovider import LLMProvider
from .prompt_router import get_review_prompt
import json
import re

llm = LLMProvider()

def parse_review_json(text: str) -> dict:
    """Extracts JSON from an LLM response"""
    cleaned = re.sub(r"```json|```", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse reviewer JSON: {e}\nRaw text:\n{text}")

def review(state: AgentState) -> AgentState:
    # print("🧪 Reviewer running")

    file = state["file"]
    code = state["code_chunks"]
    deps = state["dependencies"]
    deps_docs = state["dependency_docs"]
    docs_to_review = state["draft_doc"]
    
    dependency_context = (
        "\n\n".join(
            f"[Dependency Documentation]\n{doc}"
            for doc in deps_docs
        )
        if deps_docs
        else "None"
    )
    
    # Get prompt from centralized router
    prompt = get_review_prompt(
        file=file,
        code=code,
        deps=deps,
        dependency_context=dependency_context,
        docs_to_review=docs_to_review
    )
    
    response = llm.generate(prompt)
    result = parse_review_json(response)
    
    state["reviewer_suggestions"] = result["review_suggestions"]
    state["review_passed"] = result["review_passed"]
    state["retry_count"] += 1

    return state