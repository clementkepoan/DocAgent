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

    # Generate nested folder structure (showing subfolders with their contents)
    nested_structure = _generate_nested_structure(analyzer)

    # Auto-detect important subfolders (folders with many .py files)
    important_subfolders = _detect_important_subfolders(analyzer)

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
        reviewer_feedback=reviewer_feedback,
        nested_structure=nested_structure,
        important_subfolders=important_subfolders
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
                "required_context": ["tree"],
                "style": "introduction",
                "max_tokens": 800,
                "dependencies": []
            },
            {
                "section_id": "installation",
                "title": "Installation",
                "purpose": "Setup instructions",
                "required_context": ["deps", "configs"],
                "style": "tutorial",
                "max_tokens": 500,
                "dependencies": []
            },
            {
                "section_id": "architecture",
                "title": "Architecture",
                "purpose": "System design overview",
                "required_context": ["all_folders", "tree"],
                "style": "architecture",
                "max_tokens": 1500,
                "dependencies": ["overview"]
            },
            {
                "section_id": "api-reference",
                "title": "API Reference",
                "purpose": "Public API documentation",
                "required_context": ["entry_points"],
                "style": "api-docs",
                "max_tokens": 1200,
                "dependencies": ["architecture"]
            }
        ],
        "glossary": []
    }


def _generate_nested_structure(analyzer) -> str:
    """
    Generate a nested folder structure showing subfolders and their .py files.
    This helps the planner see components like watchdogs, LLM providers, etc.
    """
    from pathlib import Path
    from collections import defaultdict

    # Group modules by their parent folders
    folder_contents = defaultdict(list)

    for module_name, file_path in analyzer.module_index.items():
        try:
            rel_path = file_path.relative_to(analyzer.root_folder)
            parent = str(rel_path.parent) if rel_path.parent != Path('.') else '.'
            folder_contents[parent].append(file_path.stem)
        except:
            pass

    # Build nested structure string
    lines = []
    sorted_folders = sorted(folder_contents.keys(), key=lambda x: (x.count('/'), x))

    for folder in sorted_folders[:40]:  # Limit to 40 folders
        depth = folder.count('/') if folder != '.' else 0
        indent = "  " * depth
        folder_display = folder if folder != '.' else '(root)'

        modules = folder_contents[folder]
        if len(modules) > 0:
            lines.append(f"{indent}📁 {folder_display}/ ({len(modules)} modules)")
            # Show first 8 modules in the folder
            for mod in sorted(modules)[:8]:
                lines.append(f"{indent}  • {mod}")
            if len(modules) > 8:
                lines.append(f"{indent}  ... and {len(modules) - 8} more")

    return "\n".join(lines) if lines else None


def _detect_important_subfolders(analyzer) -> str:
    """
    Auto-detect subfolders with many .py files that likely contain important components.
    Examples: watchdogs/, providers/, handlers/, models/, etc.
    """
    from pathlib import Path
    from collections import defaultdict

    # Count .py files per folder
    folder_counts = defaultdict(int)
    folder_modules = defaultdict(list)

    for module_name, file_path in analyzer.module_index.items():
        try:
            rel_path = file_path.relative_to(analyzer.root_folder)
            parent = str(rel_path.parent) if rel_path.parent != Path('.') else '.'
            folder_counts[parent] += 1
            folder_modules[parent].append(file_path.stem)
        except:
            pass

    # Find folders with 4+ modules (likely important component collections)
    important = []
    for folder, count in sorted(folder_counts.items(), key=lambda x: -x[1]):
        if count >= 4 and folder != '.':
            modules = folder_modules[folder]
            # Show folder with its module names
            module_list = ', '.join(sorted(modules)[:10])
            if len(modules) > 10:
                module_list += f", ... ({len(modules)} total)"
            important.append(f"• {folder}/ ({count} modules): {module_list}")

    return "\n".join(important[:15]) if important else None
