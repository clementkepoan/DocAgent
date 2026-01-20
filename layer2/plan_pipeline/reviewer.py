"""
Plan Review Agent
==================

Validates documentation plans for completeness and coherence.
"""

from layer2.services.llm_provider import LLMProvider
from layer2.prompts.plan_prompts import get_plan_review_prompt
from layer2.schemas.documentation import DocumentationPlan
import json
import re
import asyncio

llm = LLMProvider()


def parse_review_json(text: str) -> dict:
    """Extract review JSON from LLM response"""
    cleaned = re.sub(r"```json|```", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse review: {e}")


async def review_documentation_plan(
    plan: DocumentationPlan,
    analyzer,
    folder_docs: dict,
    semaphore: asyncio.Semaphore
) -> tuple:
    """
    Review the documentation plan for completeness and coherence.

    Args:
        plan: Documentation plan to review
        analyzer: Codebase analyzer
        folder_docs: Folder documentation
        semaphore: Rate limiting for LLM calls

    Returns:
        (plan_valid, feedback) tuple
    """

    prompt = get_plan_review_prompt(plan, analyzer, folder_docs)

    print("🔍 Reviewing documentation plan...")

    # Use semaphore to respect rate limits
    async with semaphore:
        response = await llm.generate_async(prompt)

    try:
        review = parse_review_json(response)
        valid = review.get("plan_valid", False)
        feedback = review.get("feedback", "")

        if valid:
            print("✓ Plan approved")
        else:
            print(f"⚠️  Plan needs revision: {feedback[:100]}...")

        return valid, feedback
    except ValueError as e:
        print(f"⚠️  Review parsing failed: {e}")
        return False, str(e)
