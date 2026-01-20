"""
Plan Execution Agent
=====================

Executes documentation plan by generating sections with focused context.
"""

from .llmprovider import LLMProvider
from .prompt_router import get_section_generation_prompt
from .doc_schemas import DocumentationPlan, DocumentationSection
import asyncio

llm = LLMProvider()


async def execute_documentation_plan(
    plan: DocumentationPlan,
    analyzer,
    folder_docs: dict,
    folder_tree: dict,
    module_docs: dict,
    semaphore: asyncio.Semaphore
) -> str:
    """
    Execute the documentation plan by generating each section.

    Args:
        plan: Documentation plan to execute
        analyzer: Codebase analyzer
        folder_docs: Folder documentation
        folder_tree: Hierarchical folder structure
        module_docs: Module documentation
        semaphore: Rate limiting for LLM calls

    Returns:
        Complete documentation markdown
    """

    print(f"📝 Executing documentation plan ({len(plan['sections'])} sections)...")

    sections_content = []

    # Generate title and intro
    title = f"# {plan['primary_use_case']}\n\n"
    sections_content.append(title)

    # Generate each section sequentially (some may depend on previous)
    for idx, section in enumerate(plan['sections'], 1):
        print(f"  [{idx}/{len(plan['sections'])}] Generating: {section['title']}")

        # Gather required context
        context_data = gather_section_context(
            section,
            analyzer,
            folder_docs,
            folder_tree,  # Use hierarchical structure
            module_docs
        )

        # Generate section
        prompt = get_section_generation_prompt(
            section=section,
            context_data=context_data,
            plan_context=f"Project type: {plan['project_type']}, Audience: {plan['target_audience']}"
        )

        # Use semaphore to respect rate limits
        async with semaphore:
            section_content = await llm.generate_async(prompt)

        sections_content.append(section_content)
        sections_content.append("\n\n")

    # Combine all sections
    final_doc = "".join(sections_content)

    print("✓ Documentation generation complete")
    return final_doc


def gather_section_context(
    section: DocumentationSection,
    analyzer,
    folder_docs: dict,
    folder_tree: dict,
    module_docs: dict
) -> str:
    """
    Gather only the context needed for this specific section.

    This is KEY to avoiding hallucination - we don't dump everything.
    Uses folder_tree to access hierarchical structure efficiently.
    """

    required = section['required_context']
    context_parts = []

    for ctx in required:
        if ctx == "all_folders":
            # Include all folder summaries in hierarchical order
            # Use folder_tree to present in logical structure
            for folder_path in sorted(folder_tree.keys(), key=lambda f: folder_tree[f]['depth']):
                doc = folder_docs.get(folder_path, "")
                depth_indent = "  " * folder_tree[folder_path]['depth']
                context_parts.append(f"{depth_indent}## Folder: {folder_path}\n{doc}\n")

        elif ctx == "top_level_folders":
            # Only top-level folders
            for folder_path, info in folder_tree.items():
                if info['depth'] == 0:
                    doc = folder_docs.get(folder_path, "")
                    context_parts.append(f"## Folder: {folder_path}\n{doc}\n")

        elif ctx.endswith(".py"):
            # Include specific module
            if ctx in module_docs:
                context_parts.append(f"## Module: {ctx}\n{module_docs[ctx]}\n")

        elif "/" in ctx or "." in ctx:
            # Include specific folder and optionally its children
            if ctx in folder_docs:
                context_parts.append(f"## Folder: {ctx}\n{folder_docs[ctx]}\n")

                # Include children if they exist
                if ctx in folder_tree:
                    for child in folder_tree[ctx]['children']:
                        if child in folder_docs:
                            context_parts.append(f"### Subfolder: {child}\n{folder_docs[child]}\n")

        else:
            # Generic context type
            if ctx == "project_structure":
                from layer1.grouper import FolderProcessor
                processor = FolderProcessor(analyzer)
                context_parts.append(processor.get_folder_structure_str(include_modules=True))

    return "\n".join(context_parts)
