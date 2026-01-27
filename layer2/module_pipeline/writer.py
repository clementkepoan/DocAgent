from layer2.schemas.agent_state import AgentState
from layer2.services.llm_provider import LLMProvider
from layer2.prompts.module_prompts import get_module_documentation_prompt
from typing import TYPE_CHECKING, Optional
import json
import re

if TYPE_CHECKING:
    from config import LLMConfig
    from layer2.services.retrieval_tools import RetrievalToolExecutor

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
    rag_context = state.get("rag_context", None)

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
        reviewer_suggestions=reviewer_suggestions,
        rag_context=rag_context
    )

    response = await llm.generate_async(prompt)

    # Parse structured response
    try:
        doc_data = parse_doc_json(response)

        # Store both structured and formatted versions
        state["draft_doc"] = format_structured_doc(file, doc_data)
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


async def module_write_adaptive(
    state: AgentState,
    llm_config: "LLMConfig" = None,
    tool_executor: "RetrievalToolExecutor" = None,
    max_turns: int = 3
) -> AgentState:
    """
    Generate documentation with adaptive RAG retrieval via tool calling.

    This function implements a multi-turn conversation where the LLM can
    request more context by calling retrieval tools. This replaces the
    AST-based code dumping approach with intelligent, just-in-time retrieval.

    Args:
        state: AgentState with module info
        llm_config: Optional LLM configuration
        tool_executor: RetrievalToolExecutor for executing tool calls
        max_turns: Maximum number of tool call rounds (default: 3)

    Returns:
        Updated AgentState with draft_doc and tool_calls_made
    """
    from layer2.services.retrieval_tools import RETRIEVAL_TOOLS

    llm = get_llm(llm_config)

    file = state["file"]
    deps = state["dependencies"]
    deps_docs = state["dependency_docs"]
    reviewer_suggestions = state.get("reviewer_suggestions")
    scc_context = state.get("scc_context")
    rag_context = state.get("rag_context")

    # Get initial entities list (if available from RAG)
    initial_entities = state.get("initial_entities", [])

    # Build dependency context
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

    # Import the new initial prompt function
    from layer2.prompts.module_prompts import get_initial_documentation_prompt

    # Build initial prompt with MINIMAL context
    initial_prompt = get_initial_documentation_prompt(
        file=file,
        dependencies=deps,
        dependency_context=dependency_context,
        module_docstring=_extract_docstring(state),
        entity_names=initial_entities,
        rag_context=rag_context
    )

    # Initialize messages list
    messages = [{"role": "user", "content": initial_prompt}]

    # Multi-turn conversation with tools
    for turn in range(max_turns):
        try:
            # Call LLM with tools
            response = await llm.generate_async_with_tools(
                messages=messages,
                tools=RETRIEVAL_TOOLS
            )

            # Check if LLM wants to call tools
            if hasattr(response, 'tool_calls') and response.tool_calls:
                # Add assistant response with tool calls
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": response.tool_calls
                })

                # Execute each tool call
                for tool_call in response.tool_calls:
                    try:
                        # Parse arguments
                        arguments = json.loads(tool_call.function.arguments)

                        # Execute tool
                        result = await tool_executor.execute_tool_call(
                            tool_call.function.name,
                            arguments
                        )

                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result
                        })

                    except Exception as e:
                        # Tool execution failed - continue with error
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"Error executing tool: {str(e)}"
                        })

                # Continue to next turn (LLM will see tool results)
                continue

            # LLM is done - no more tool calls
            # Add final assistant message
            if response.content:
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

            # Parse final documentation
            final_content = response.content

            try:
                doc_data = parse_doc_json(final_content)
                state["draft_doc"] = format_structured_doc(file, doc_data)
            except ValueError:
                # Fallback: store raw response
                print(f"⚠️ Failed to parse adaptive doc for {file}, using raw response")
                state["draft_doc"] = f"Module Documentation for {file}:\n{final_content}\n"

            # Track how many turns we used
            state["tool_calls_made"] = turn + 1

            return state

        except Exception as e:
            print(f"⚠️ Error in adaptive write turn {turn + 1} for {file}: {e}")
            # If we fail on a later turn, try to use what we have
            if turn > 0:
                # Try to extract content from last assistant message
                for msg in reversed(messages):
                    if msg.get("role") == "assistant" and msg.get("content"):
                        try:
                            doc_data = parse_doc_json(msg["content"])
                            state["draft_doc"] = format_structured_doc(file, doc_data)
                            state["tool_calls_made"] = turn + 1
                            return state
                        except ValueError:
                            state["draft_doc"] = f"Module Documentation for {file}:\n{msg['content']}\n"
                            state["tool_calls_made"] = turn + 1
                            return state

            # If we fail on first turn, raise the exception
            raise

    # Max turns reached - shouldn't get here, but handle gracefully
    state["draft_doc"] = f"Module Documentation for {file}:\n(Max tool rounds reached)\n"
    state["tool_calls_made"] = max_turns
    return state


def _extract_docstring(state: AgentState) -> Optional[str]:
    """
    Extract module docstring from code chunks if present.

    Args:
        state: AgentState with code_chunks

    Returns:
        Module docstring or None
    """
    if not state.get("code_chunks"):
        return None

    first_chunk = state["code_chunks"][0]

    # Try to extract docstring
    for quote in ('"""', "'''"):
        if quote in first_chunk:
            parts = first_chunk.split(quote)
            if len(parts) >= 2:
                potential_docstring = parts[1].strip()
                # Only return if it looks like a docstring (not empty, reasonable length)
                if len(potential_docstring) > 10:
                    return potential_docstring[:500]  # Truncate long docstrings

    return None

