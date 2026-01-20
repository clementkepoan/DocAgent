"""Folder-level documentation prompts."""

from typing import Dict, Any


def get_folder_documentation_prompt(context: Dict[str, Any],
                                     module_descriptions: str,
                                     child_folder_descriptions: str = "") -> str:
    """
    Generate LLM prompt for folder-level documentation.

    Args:
        context: Folder context dict with path, depth, metrics, modules, child_folders
        module_descriptions: Formatted descriptions of modules in this folder
        child_folder_descriptions: Formatted descriptions of child folders (if any)

    Returns:
        Formatted LLM prompt for folder documentation
    """
    folder_path = context['folder_path']
    parent_path = context['parent_path']
    file_count = context['file_count']
    modules = context['modules']
    metrics = context['metrics']
    child_folders = context.get('child_folders', [])

    # Format child folder information
    child_info = ""
    if child_folders:
        child_info = f"\n\nSUBFOLDERS: {', '.join(child_folders)}"
        if child_folder_descriptions:
            child_info += f"\nSUBFOLDER DESCRIPTIONS:{child_folder_descriptions}"

    # Add subfolder context to description instructions
    subfolder_instruction = " (including how it organizes functionality through subfolders)" if child_folders else ""

    return f"""
Explain the Python folder `{folder_path}`.

SCOPE: {"Root-level package" if not parent_path else f"Subfolder of {parent_path}"}
FILES: {file_count} Python modules
METRICS: {metrics}

MODULES: {', '.join(modules)}
MODULE DESCRIPTIONS:{module_descriptions if module_descriptions else " (None generated yet)"}{child_info}

Describe:
1. This folder's responsibility and purpose
2. Its role in the broader architecture{subfolder_instruction}
3. Key patterns or abstractions in its modules
4. Coupling concerns (high external imports = likely unstable)

═══════════════════════════════════════════════════════════════════════════════
ACCURACY RULES (MUST FOLLOW):
═══════════════════════════════════════════════════════════════════════════════

- Only describe modules actually listed in MODULES above
- Do NOT invent testing practices, CI/CD pipelines, or organizational patterns not evidenced
- Do NOT extrapolate from single files (one test file ≠ "comprehensive test suite")
- Mark inferences explicitly: "high external imports suggests potential instability"
- If module descriptions are missing, state "Documentation not yet generated" rather than inventing

Answer in 5-7 sentences.
"""
