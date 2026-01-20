"""Layer2 Prompts: Centralized LLM prompt templates."""

from layer2.prompts.module_prompts import (
    get_module_documentation_prompt,
    get_review_prompt
)
from layer2.prompts.folder_prompts import get_folder_documentation_prompt
from layer2.prompts.plan_prompts import (
    get_documentation_plan_prompt,
    get_section_generation_prompt,
    get_plan_review_prompt
)

__all__ = [
    "get_module_documentation_prompt",
    "get_review_prompt",
    "get_folder_documentation_prompt",
    "get_documentation_plan_prompt",
    "get_section_generation_prompt",
    "get_plan_review_prompt",
]
