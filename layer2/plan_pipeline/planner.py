"""
Documentation Planning Agent
=============================

Analyzes codebase structure and generates optimal documentation plan.
"""

from layer2.services.llm_provider import LLMProvider
from layer2.prompts.plan_prompts import get_documentation_plan_prompt
from layer2.schemas.documentation import DocumentationPlan
from layer1.config_reader import ConfigFileReader
import json
import re
import asyncio

llm = LLMProvider()


def parse_plan_json(text: str) -> dict:
    """Extract JSON plan from LLM response"""
    cleaned = re.sub(r"```json|```", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse plan JSON: {e}\nRaw text:\n{text}")


async def generate_documentation_plan(
    analyzer,
    folder_docs: dict,
    folder_tree: dict,
    module_docs: dict,
    semaphore: asyncio.Semaphore,
    reviewer_feedback: str = None
) -> DocumentationPlan:
    """
    Generate a structured documentation plan based on codebase analysis.

    Args:
        analyzer: ImportGraph analyzer with codebase structure
        folder_docs: Folder-level documentation summaries
        folder_tree: Hierarchical folder structure
        module_docs: All module documentation
        semaphore: Rate limiting for LLM calls
        reviewer_feedback: Optional feedback from previous plan review

    Returns:
        Structured DocumentationPlan with sections and context requirements
    """

    # Build codebase summary
    from layer1.grouper import FolderProcessor
    processor = FolderProcessor(analyzer)
    folder_structure = processor.get_folder_structure_str(include_modules=True)  # Changed to True

    # Key metrics
    total_modules = len([m for m in analyzer.module_index if m not in analyzer.packages])
    total_folders = len(folder_docs)
    cycles = [scc for scc in analyzer.get_sccs() if len(scc) > 1]
    
    # Detect actual CLI frameworks (not just main.py existence)
    cli_frameworks_detected = []
    for module_name, file_path in analyzer.module_index.items():
        try:
            content = file_path.read_text(encoding='utf-8')
            if 'import argparse' in content or 'from argparse' in content:
                cli_frameworks_detected.append('argparse')
            if 'import click' in content or 'from click' in content:
                cli_frameworks_detected.append('click')
            if 'import typer' in content or 'from typer' in content:
                cli_frameworks_detected.append('typer')
            if 'import fire' in content or 'from fire' in content:
                cli_frameworks_detected.append('fire')
        except:
            pass
    
    has_cli_framework = len(set(cli_frameworks_detected)) > 0
    cli_framework_names = ', '.join(set(cli_frameworks_detected)) if cli_frameworks_detected else None
    
    # Read main.py preview for better context
    main_py_preview = None
    main_path = analyzer.module_index.get("main") or analyzer.module_index.get("__main__")
    if main_path and main_path.exists():
        try:
            main_py_preview = main_path.read_text(encoding='utf-8')[:1500]  # First 1500 chars
        except:
            pass
    
    # Scan for config files
    config_reader = ConfigFileReader(str(analyzer.root_folder))
    config_reader.scan()
    config_files_summary = config_reader.get_summary()

    # Build prompt
    prompt = get_documentation_plan_prompt(
        folder_structure=folder_structure,
        folder_docs=folder_docs,
        total_modules=total_modules,
        total_folders=total_folders,
        cycle_count=len(cycles),
        has_cli=(main_path is not None),
        has_cli_framework=has_cli_framework,
        cli_frameworks=cli_framework_names,
        main_py_preview=main_py_preview,
        has_tests=any("test" in str(p) for p in analyzer.module_index.values()),
        config_files=config_files_summary,
        reviewer_feedback=reviewer_feedback
    )

    print("📋 Generating documentation structure plan...")

    # Use semaphore to respect rate limits
    async with semaphore:
        response = await llm.generate_async(prompt)

    try:
        plan_data = parse_plan_json(response)
        print(f"✓ Plan generated with {len(plan_data['sections'])} sections")
        return plan_data
    except ValueError as e:
        print(f"⚠️  Failed to parse plan: {e}")
        # Fallback to default plan
        return generate_default_plan()


def generate_default_plan() -> DocumentationPlan:
    """Fallback plan if LLM planning fails"""
    return {
        "project_type": "Python project",
        "target_audience": "developers",
        "primary_use_case": "Unknown",
        "architecture_pattern": "Unknown",
        "sections": [
            {
                "section_id": "overview",
                "title": "Overview",
                "purpose": "High-level project description",
                "required_context": [],
                "style": "introduction",
                "max_tokens": 500,
                "dependencies": []
            },
            {
                "section_id": "installation",
                "title": "Installation",
                "purpose": "Setup instructions",
                "required_context": [],
                "style": "tutorial",
                "max_tokens": 300,
                "dependencies": []
            },
            {
                "section_id": "architecture",
                "title": "Architecture",
                "purpose": "System design overview",
                "required_context": ["all_folders"],
                "style": "architecture",
                "max_tokens": 1000,
                "dependencies": ["overview"]
            }
        ],
        "glossary": []
    }
