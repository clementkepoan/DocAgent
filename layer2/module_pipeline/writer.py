from layer2.schemas.agent_state import AgentState
from layer2.services.llm_provider import LLMProvider
from layer2.prompts.module_prompts import get_module_documentation_prompt
from typing import TYPE_CHECKING
import json
import re

if TYPE_CHECKING:
    from config import LLMConfig

_default_llm = None


def get_llm(config: "LLMConfig" = None) -> LLMProvider:
    """Get LLM provider instance, optionally with custom config."""
    global _default_llm
    if config is not None:
        return LLMProvider(config)
    if _default_llm is None:
        _default_llm = LLMProvider()
    return _default_llm

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

def format_scc_context(scc_data: dict) -> str:
    """Convert SCC overview data to readable markdown"""

    abstractions = ", ".join([f"`{a}`" for a in scc_data.get("key_abstractions", [])])
    entry_points = ", ".join([f"`{e}`" for e in scc_data.get("entry_points", [])])
    utilities = ", ".join([f"`{u}`" for u in scc_data.get("utilities", [])])
    concerns = "\n".join([f"  - {c}" for c in scc_data.get("architectural_concerns", [])])

    return f"""
## Cycle Architecture: {scc_data.get('cycle_pattern', 'Interdependent Modules')}

**Pattern:** {scc_data.get('cycle_pattern', 'N/A')}

**Collective Responsibility:** {scc_data.get('collective_responsibility', 'N/A')}

**Interdependency Explanation:** {scc_data.get('interdependency_explanation', 'N/A')}

**Key Abstractions:** {abstractions if abstractions else "None"}

**Entry Points:** {entry_points if entry_points else "None"}

**Utilities:** {utilities if utilities else "None"}

**Architectural Concerns:**
{concerns if concerns else "  - None"}

**Summary:** {scc_data.get('summary', 'N/A')}

---
"""

async def module_write(state: AgentState, llm_config: "LLMConfig" = None) -> AgentState:
    """Generate documentation for a single module (async version)"""

    llm = get_llm(llm_config)

    file = state["file"]
    code = state["code_chunks"]
    deps = state["dependencies"]
    deps_docs = state["dependency_docs"]
    reviewer_suggestions = state["reviewer_suggestions"]
    scc_context = state.get("scc_context", None)

    dependency_context = (
        "\n\n".join(
            f"[Dependency Documentation]\n{doc}"
            for doc in deps_docs
        )
        if deps_docs
        else "None"
    )

    # Include SCC context if module is in a cycle
    if scc_context:
        dependency_context = f"[SCC Architecture Context]\n{scc_context}\n\n{dependency_context}"

    code_context = "\n".join(code)

    # Get prompt from centralized router
    prompt = get_module_documentation_prompt(
        file=file,
        deps=deps,
        dependency_context=dependency_context,
        code_context=code_context,
        reviewer_suggestions=reviewer_suggestions
    )

    response = await llm.generate_async(prompt)

    # Parse structured response
    try:
        doc_data = parse_doc_json(response)

        # Store both structured and formatted versions
        state["doc_data"] = doc_data  # Store structured JSON for indexing
        state["draft_doc"] = format_structured_doc(file, doc_data)  # Keep formatted for output
    except ValueError as e:
        # Fallback: store raw response if JSON parsing fails
        print(f"⚠️ Failed to parse structured doc for {file}: {e}")
        state["draft_doc"] = f"Module Documentation for {file}:\n{response}\n"

    return state


async def scc_context_write(scc_modules: list, code_chunks_dict: dict, llm_config: "LLMConfig" = None) -> str:
    """
    Generate high-level coherence documentation for a cycle (SCC).

    Args:
        scc_modules: List of module names in the cycle
        code_chunks_dict: Dict mapping module names to their source code
        llm_config: Optional LLM configuration

    Returns:
        Formatted SCC context markdown
    """
    llm = get_llm(llm_config)
    try:
        response = await llm.generate_scc_overview_async(scc_modules, code_chunks_dict)
        scc_data = parse_doc_json(response)
        return format_scc_context(scc_data)
    except ValueError as e:
        print(f"⚠️ Failed to parse SCC overview: {e}")
        return f"Cycle Architecture Overview:\n{response}\n"
