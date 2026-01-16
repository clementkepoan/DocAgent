from .schemas import AgentState
from .llmprovider import LLMProvider
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
    
    # IMPROVEMENT: More specific error categories
    prompt = f"""
You are a strict documentation reviewer for an AI-generated module description.

Your task is to REVIEW the generated documentation for the file **{file}**.

You are NOT allowed to rewrite the documentation directly.

You must evaluate whether the documentation is:
- Factually correct with respect to the source code
- Consistent with dependency documentation
- Focused on this module's responsibility (not its dependencies)
- Free of invented behavior or unsupported claims

Rules:
- Assume dependency documentation is correct and authoritative.
- Do NOT suggest re-documenting dependency internals.
- Be conservative: if something is unclear or unverifiable, mark it as an issue.
- Prefer rejecting over approving incorrect or vague documentation.

Inputs
------
Module Name:
{file}

Dependencies (imported modules):
{deps if deps else "None"}

Dependency Documentation (context only):
{dependency_context}

Source Code (authoritative):
Language: python
{code}

Generated Documentation (to review):
{docs_to_review}

Your Output
-----------
Return a JSON object with EXACTLY this schema:

{{
  "review_passed": "boolean",
  "review_suggestions": [
    {{
      "category": "factual_error | missing_info | vague_language | dependency_confusion | invented_behavior",
      "issue": "Specific description of the problem",
      "fix": "Concrete suggestion for how to correct it"
    }}
  ]
}}

Categories explained:
- factual_error: Documentation contradicts the code (e.g., wrong function name, incorrect parameter)
- missing_info: Important responsibility is not documented
- vague_language: Documentation is too generic ("handles data", "manages things")
- dependency_confusion: Re-documents dependency behavior instead of this module's usage
- invented_behavior: Claims functionality not present in the code

Guidelines for Output:
- If the documentation is fully correct and clear, set review_passed = true and review_suggestions = [].
- If there are any issues:
  - set review_passed = false
  - provide structured suggestions with category, issue, and fix
- Do NOT rewrite the documentation.
- Ensure the JSON is well-formed and parsable.
"""
    
    response = llm.generate(prompt)
    result = parse_review_json(response)
    
    state["reviewer_suggestions"] = result["review_suggestions"]
    state["review_passed"] = result["review_passed"]
    state["retry_count"] += 1

    return state