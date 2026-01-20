"""Module-level documentation and review prompts."""

from typing import List


def get_module_documentation_prompt(file: str,
                                     deps: List[str],
                                     dependency_context: str,
                                     code_context: str,
                                     reviewer_suggestions: str = None) -> str:
    """
    Generate LLM prompt for module-level documentation.

    Args:
        file: Module filename
        deps: List of imported dependencies
        dependency_context: Formatted dependency documentation
        code_context: Source code chunks
        reviewer_suggestions: Optional feedback from previous review

    Returns:
        Formatted LLM prompt for module documentation
    """
    return f"""
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

Module Classification:
- If filename matches test_*.py, *_test.py, or is in tests/ folder: this is a TEST FILE
- For test files: document as "Test Utility" and note it's not production code
- For test files: do NOT elevate test helpers to "core components" status

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


def get_review_prompt(file: str,
                      code: str,
                      deps: List[str],
                      dependency_context: str,
                      docs_to_review: str) -> str:
    """
    Generate LLM prompt for documentation review/validation.

    Args:
        file: Module filename
        code: Source code to review against
        deps: List of imported dependencies
        dependency_context: Formatted dependency documentation
        docs_to_review: Generated documentation to validate

    Returns:
        Formatted LLM prompt for review
    """
    return f"""
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
      "category": "factual_error | missing_info | vague_language | dependency_confusion | invented_behavior | test_as_production",
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
- test_as_production: Elevates test utilities to production component status (for test_*.py files)

Guidelines for Output:
- If the documentation is fully correct and clear, set review_passed = true and review_suggestions = [].
- If there are any issues:
  - set review_passed = false
  - provide structured suggestions with category, issue, and fix
- Do NOT rewrite the documentation.
- Ensure the JSON is well-formed and parsable.
"""
