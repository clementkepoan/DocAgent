from .schemas import AgentState
from .llmprovider import LLMProvider
import json
import re

llm = LLMProvider()

def parse_doc_json(text: str) -> dict:
    """Extracts JSON from LLM response"""
    cleaned = re.sub(r"```json|```", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse documentation JSON: {e}\nRaw text:\n{text}")
    

def format_structured_doc(file: str, doc_data: dict) -> str:
    """Convert structured doc data to readable markdown"""
    
    key_funcs = "\n".join([
        f"  - `{func['name']}`: {func['purpose']}"
        for func in doc_data.get("key_functions", [])
    ])
    
    exports = ", ".join([f"`{e}`" for e in doc_data.get("exports", [])])
    
    return f"""
## Module: `{file}`

**Summary:** {doc_data.get('summary', 'N/A')}

**Responsibility:** {doc_data.get('responsibility', 'N/A')}

**Key Functions:**
{key_funcs if key_funcs else "  - None"}

**Dependency Usage:** {doc_data.get('dependency_usage', 'No dependencies')}

**Exports:** {exports if exports else "None"}

---
"""

def write(state: AgentState) -> AgentState:
    print("✍️ Writer running")

    file = state["file"]
    code = state["code_chunks"]
    deps = state["dependencies"]
    deps_docs = state["dependency_docs"]
    reviewer_suggestions = state["reviewer_suggestions"]

    print(f"deps for {file}: {deps}")

    dependency_context = (
        "\n\n".join(
            f"[Dependency Documentation]\n{doc}"
            for doc in deps_docs
        )
        if deps_docs
        else "None"
    )

    code_context = "\n".join(code)

    # KEY IMPROVEMENT: Structured output preserves more information
    prompt = f"""
You are an automated documentation agent for a module.

Your task is to write **structured, accurate documentation** for the file **{file}**.

Rules:
- Do NOT re-document functionality already covered by dependencies.
- Assume dependency documentation is always correct and authoritative.
- Focus on THIS module's unique responsibility and how it uses dependencies.
- Do NOT invent behavior not present in the code.
- If reviewer suggestions exist, incorporate them to improve accuracy.
- If source code is missing or incomplete, note that in the documentation.
- If source code is empty, generate empty module documentation.

Dependencies (imported modules):
{deps if deps else "None"}

Dependency Documentation (for context only):
{dependency_context}

Source Code:
Language: python
{code_context}

Reviewer Suggestions:
{reviewer_suggestions if reviewer_suggestions else "None"}

Your Output
-----------
Return a JSON object with EXACTLY this schema:

{{
  "summary": "2-3 sentence high-level overview of this module's purpose",
  "responsibility": "What this module does (its core responsibility)",
  "key_functions": [
    {{
      "name": "function_name",
      "purpose": "what it does in 1 sentence"
    }}
  ],
  "dependency_usage": "How this module uses its dependencies (if any)",
  "exports": ["list of main classes/functions this module provides to others"]
}}

Guidelines:
- summary: User-facing overview (what someone reading the codebase needs to know)
- responsibility: Technical description of the module's role in the system
- key_functions: List 3-5 most important functions/classes (not every helper)
- dependency_usage: Explain the relationship pattern (e.g., "Uses X for Y, delegates Z to W")
- exports: What other modules can import from this one

Ensure the JSON is well-formed and parsable.
"""

    response = llm.generate(prompt)
    
    # Parse structured response
    try:
        doc_data = parse_doc_json(response)
        
        # Store both structured and formatted versions
        state["draft_doc"] = format_structured_doc(file, doc_data)
    except ValueError as e:
        # Fallback: store raw response if JSON parsing fails
        print(f"⚠️ Failed to parse structured doc: {e}")
        state["draft_doc"] = f"Module Documentation for {file}:\n{response}\n"

    return state


