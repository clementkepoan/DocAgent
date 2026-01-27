from layer2.schemas.agent_state import AgentState
from layer2.services.llm_provider import LLMProvider
from layer2.prompts.module_prompts import get_review_prompt
from typing import TYPE_CHECKING, Optional
import json
import re
import asyncio
import time

if TYPE_CHECKING:
    from config import LLMConfig
    from layer2.services.retrieval_tools import RetrievalToolExecutor

_default_llm = None

DEFAULT_REVIEW_TIMEOUT = 60  # seconds


def get_llm(config: "LLMConfig" = None) -> LLMProvider:
    """Get LLM provider instance, optionally with custom config."""
    global _default_llm
    if config is not None:
        return LLMProvider(config)
    if _default_llm is None:
        _default_llm = LLMProvider()
    return _default_llm


def parse_review_json(text: str) -> dict:
    """Extracts JSON from an LLM response"""
    cleaned = re.sub(r"```json|```", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse reviewer JSON: {e}\nRaw text:\n{text}")


async def review(state: AgentState, llm_config: "LLMConfig" = None, timeout: int = None) -> AgentState:
    """Review generated documentation."""

    llm = get_llm(llm_config)
    if timeout is None:
        timeout = DEFAULT_REVIEW_TIMEOUT

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

    start = time.time()
    try:
        response = await asyncio.wait_for(llm.generate_async(prompt), timeout=timeout)
    except asyncio.TimeoutError:
        state["reviewer_suggestions"] = f"Review timed out after {timeout}s"
        state["review_passed"] = False
        state["last_review_time"] = timeout
        state["retry_count"] += 1
        return state
    except Exception as e:
        state["reviewer_suggestions"] = f"Review failed: {e}"
        state["review_passed"] = False
        state["last_review_time"] = time.time() - start
        state["retry_count"] += 1
        return state

    try:
        result = parse_review_json(response)
    except Exception as e:
        state["reviewer_suggestions"] = f"Failed to parse review response: {e}"
        state["review_passed"] = False
        state["last_review_time"] = time.time() - start
        state["retry_count"] += 1
        return state

    state["reviewer_suggestions"] = result.get("review_suggestions", "")
    state["review_passed"] = result.get("review_passed", False)
    state["last_review_time"] = time.time() - start
    state["retry_count"] += 1

    return state


async def review_adaptive(
    state: AgentState,
    llm_config: "LLMConfig" = None,
    tool_executor: "RetrievalToolExecutor" = None,
    timeout: int = None
) -> AgentState:
    """
    Review generated documentation with automatic context expansion on failure.

    This function runs a normal review first. If the review fails, it attempts
    to extract missing entity names from the reviewer's suggestions and
    automatically queries for more context using the retrieval tools.

    Args:
        state: AgentState with draft_doc to review
        llm_config: Optional LLM configuration
        tool_executor: RetrievalToolExecutor for auto-expansion
        timeout: Optional timeout for review

    Returns:
        Updated AgentState with review results and possibly expanded_context
    """
    # Run normal review first
    state = await review(state, llm_config, timeout)

    # If review passed, we're done
    if state["review_passed"]:
        return state

    # Review failed - try to extract missing entities and expand context
    if not tool_executor:
        # No tool executor, can't expand
        return state

    # Extract missing entities from reviewer suggestions
    missing_entities = extract_missing_entities(
        state["reviewer_suggestions"],
        state["file"]
    )

    if not missing_entities:
        # Couldn't identify specific missing entities
        return state

    # Auto-query for missing context
    expanded_context = []

    for entity in missing_entities:
        try:
            entity_name = entity["name"]
            entity_type = entity["type"]  # "function" or "class"

            # Call appropriate tool
            if entity_type == "function":
                result = await tool_executor.execute_tool_call(
                    "get_function_details",
                    {"module": state["file"], "function_name": entity_name}
                )
            elif entity_type == "class":
                result = await tool_executor.execute_tool_call(
                    "get_class_details",
                    {"module": state["file"], "class_name": entity_name}
                )
            else:
                # Unknown type, try module overview
                result = await tool_executor.execute_tool_call(
                    "get_module_overview",
                    {"module": state["file"], "top_k": 5}
                )

            expanded_context.append(result)

        except Exception as e:
            # Tool execution failed - log and continue
            print(f"⚠️ Failed to retrieve context for {entity.get('name', 'unknown')}: {e}")
            continue

    # Store expanded context for next write attempt
    if expanded_context:
        state["expanded_context"] = expanded_context
        print(f"📊 Auto-expanded context for {state['file']} with {len(expanded_context)} queries")

    return state


def extract_missing_entities(
    reviewer_suggestions: str,
    module_name: str
) -> list:
    """
    Extract entity names that need more documentation from reviewer feedback.

    This function looks for patterns in the reviewer's suggestions that indicate
    specific functions or classes are missing documentation or need more detail.

    Args:
        reviewer_suggestions: Review feedback text
        module_name: Current module name (for context)

    Returns:
        List of dicts with {"name": str, "type": str} for missing entities
    """
    if not reviewer_suggestions:
        return []

    missing_entities = []

    # Pattern 1: "missing info about function X" or "function X not documented"
    function_patterns = [
        r"(?:function|method|def\s+)[\s'`]*(\w+)['\s]*",
        r"missing\s+(?:info|documentation)\s+(?:about\s+)?(?:function|method)?[\s'`]*(\w+)['\s]*",
        r"(\w+)\s+(?:function|method)\s+(?:not\s+documented|missing)",
        r"document\s+(?:the\s+)?function\s+[\`']?(\w+)[\`']?",
    ]

    for pattern in function_patterns:
        matches = re.finditer(pattern, reviewer_suggestions, re.IGNORECASE)
        for match in matches:
            entity_name = match.group(1)
            if entity_name and len(entity_name) > 2:  # Filter out short matches
                missing_entities.append({"name": entity_name, "type": "function"})

    # Pattern 2: "class X not documented" or "missing details about class Y"
    class_patterns = [
        r"class\s+[\`']?(\w+)['\`]?",
        r"missing\s+(?:info|documentation)\s+(?:about\s+)?class\s+[\`']?(\w+)['\`]?",
        r"(\w+)\s+class\s+(?:not\s+documented|missing)",
    ]

    for pattern in class_patterns:
        matches = re.finditer(pattern, reviewer_suggestions, re.IGNORECASE)
        for match in matches:
            entity_name = match.group(1)
            if entity_name and len(entity_name) > 2:
                # Check if it's not a Python builtin
                if entity_name[0].isupper() or entity_name.startswith("_"):
                    missing_entities.append({"name": entity_name, "type": "class"})

    # Pattern 3: Look for specific code references in backticks
    backtick_refs = re.findall(r'`([^`\s]+)`', reviewer_suggestions)
    for ref in backtick_refs:
        # Skip if already found
        if any(e["name"] == ref for e in missing_entities):
            continue

        # Heuristic: if it's uppercase or has underscores, likely a class/function
        if ref and len(ref) > 2 and (ref[0].isupper() or "_" in ref):
            # Guess type based on naming
            if ref[0].isupper():
                missing_entities.append({"name": ref, "type": "class"})
            else:
                missing_entities.append({"name": ref, "type": "function"})

    # Deduplicate while preserving order
    seen = set()
    unique_entities = []
    for entity in missing_entities:
        key = (entity["name"], entity["type"])
        if key not in seen:
            seen.add(key)
            unique_entities.append(entity)

    return unique_entities

