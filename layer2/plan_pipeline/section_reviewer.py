"""Section-level reviewer for Final Condensed.md quality control.

This module implements Tier 2 of the two-tier RAG architecture:
- Reviews each section of the final documentation
- Identifies missing context and suggests RAG queries
- Enables targeted context expansion for failed sections
"""

from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass
import json
import re

if TYPE_CHECKING:
    from config import LLMConfig
    from layer2.services.rag_retriever import RAGService


@dataclass
class ReviewResult:
    """Result of section review."""
    passed: bool
    feedback: str
    missing_modules: List[str]  # Module names that need more context
    missing_entities: List[Dict[str, str]]  # {"name": str, "type": str, "module": str}
    suggested_queries: List[Dict[str, Any]]  # Tool call suggestions for RAG


def get_llm(config: "LLMConfig" = None):
    """Get LLM provider instance."""
    from layer2.services.llm_provider import LLMProvider
    if config is not None:
        return LLMProvider(config)
    return LLMProvider()


async def review_section(
    section_content: str,
    section_metadata: Dict[str, Any],
    available_module_docs: Dict[str, str],
    rag_service: Optional["RAGService"] = None,
    llm_config: "LLMConfig" = None
) -> ReviewResult:
    """
    Review a documentation section and identify missing context.

    Args:
        section_content: Generated section markdown content
        section_metadata: Section info (title, purpose, required_context, style)
        available_module_docs: Dict of module_name -> module documentation
        rag_service: Optional RAGService for entity lookup
        llm_config: Optional LLM configuration

    Returns:
        ReviewResult with passed/failed status and suggested RAG queries
    """
    from layer2.prompts.plan_prompts import get_section_review_prompt

    llm = get_llm(llm_config)

    # Build context about available modules
    module_list = list(available_module_docs.keys())[:50]  # Limit for prompt size

    # Generate review prompt
    prompt = get_section_review_prompt(
        section_title=section_metadata.get("title", "Unknown"),
        section_purpose=section_metadata.get("purpose", ""),
        section_style=section_metadata.get("style", ""),
        section_content=section_content,
        available_modules=module_list
    )

    # Call LLM for review
    try:
        response = await llm.generate_async(prompt)
        result = _parse_review_response(response)
    except Exception as e:
        # On error, pass the section (don't block pipeline)
        return ReviewResult(
            passed=True,
            feedback=f"Review skipped due to error: {e}",
            missing_modules=[],
            missing_entities=[],
            suggested_queries=[]
        )

    # If review passed, return success
    if result.passed:
        return result

    # Review failed - enhance suggestions with RAG entity lookup
    if rag_service and result.missing_modules:
        result = await _enhance_with_rag_entities(result, rag_service)

    return result


def _parse_review_response(response: str) -> ReviewResult:
    """Parse LLM review response into ReviewResult."""
    # Try to extract JSON
    try:
        # Remove markdown code blocks if present
        cleaned = re.sub(r"```json|```", "", response).strip()
        data = json.loads(cleaned)

        return ReviewResult(
            passed=data.get("passed", True),
            feedback=data.get("feedback", ""),
            missing_modules=data.get("missing_modules", []),
            missing_entities=data.get("missing_entities", []),
            suggested_queries=_build_suggested_queries(
                data.get("missing_modules", []),
                data.get("missing_entities", [])
            )
        )
    except (json.JSONDecodeError, KeyError):
        # Fallback: try to extract key information from text
        passed = "pass" in response.lower() and "fail" not in response.lower()

        # Extract module names mentioned
        module_pattern = r"module[:\s]+[`'\"]?(\w+(?:\.\w+)*)[`'\"]?"
        modules = re.findall(module_pattern, response, re.IGNORECASE)

        return ReviewResult(
            passed=passed,
            feedback=response[:500],
            missing_modules=list(set(modules))[:5],
            missing_entities=[],
            suggested_queries=_build_suggested_queries(modules, [])
        )


def _build_suggested_queries(
    missing_modules: List[str],
    missing_entities: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """Build tool call suggestions from missing context."""
    queries = []

    # Add module overview queries
    for module in missing_modules[:3]:  # Limit to 3
        queries.append({
            "tool": "get_module_overview",
            "args": {"module": module, "top_k": 5}
        })

    # Add entity-specific queries
    for entity in missing_entities[:5]:  # Limit to 5
        entity_type = entity.get("type", "function")
        module = entity.get("module", "")

        if entity_type == "class":
            queries.append({
                "tool": "get_class_details",
                "args": {"module": module, "class_name": entity["name"]}
            })
        else:
            queries.append({
                "tool": "get_function_details",
                "args": {"module": module, "function_name": entity["name"]}
            })

    return queries


async def _enhance_with_rag_entities(
    result: ReviewResult,
    rag_service: "RAGService"
) -> ReviewResult:
    """Enhance review result with entity information from RAG."""
    import asyncio

    enhanced_entities = list(result.missing_entities)

    for module in result.missing_modules:
        try:
            # Get entities from RAG index
            entities = await asyncio.to_thread(
                rag_service.list_module_entities,
                module
            )

            # Add top entities as suggestions
            for entity in entities[:3]:
                enhanced_entities.append({
                    "name": entity["name"],
                    "type": entity["type"],
                    "module": module
                })
        except Exception:
            # Skip if RAG lookup fails
            continue

    # Rebuild suggested queries with enhanced entities
    result.missing_entities = enhanced_entities[:10]  # Limit total
    result.suggested_queries = _build_suggested_queries(
        result.missing_modules,
        result.missing_entities
    )

    return result


async def fetch_missing_context(
    suggested_queries: List[Dict[str, Any]],
    tool_executor
) -> Dict[str, str]:
    """
    Execute suggested RAG queries to fetch missing context.

    Args:
        suggested_queries: List of tool call suggestions from review
        tool_executor: RetrievalToolExecutor instance

    Returns:
        Dict mapping query description to retrieved content
    """
    expanded_context = {}

    for query in suggested_queries:
        tool_name = query.get("tool", "")
        args = query.get("args", {})

        try:
            result = await tool_executor.execute_tool_call(tool_name, args)

            # Create descriptive key
            if tool_name == "get_module_overview":
                key = f"module:{args.get('module', 'unknown')}"
            elif tool_name == "get_class_details":
                key = f"class:{args.get('module', '')}.{args.get('class_name', '')}"
            elif tool_name == "get_function_details":
                key = f"function:{args.get('module', '')}.{args.get('function_name', '')}"
            else:
                key = f"{tool_name}:{json.dumps(args)}"

            expanded_context[key] = result

        except Exception as e:
            # Log and continue on individual query failures
            print(f"    ⚠️ Failed to fetch context for {tool_name}: {e}")
            continue

    return expanded_context
