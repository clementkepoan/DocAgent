from layer2.schemas.agent_state import AgentState
from layer2.services.llm_provider import LLMProvider
from layer2.prompts.module_prompts import get_review_prompt
from typing import TYPE_CHECKING
import json
import re
import asyncio
import time

if TYPE_CHECKING:
    from config import LLMConfig

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
