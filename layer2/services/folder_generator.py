"""Folder-level documentation generation service."""

from layer2.services.llm_provider import LLMProvider
from typing import TYPE_CHECKING
import asyncio

if TYPE_CHECKING:
    from config import LLMConfig

_default_llm = None


def get_llm(config: "LLMConfig" = None) -> LLMProvider:
    """Get LLM provider instance, optionally with custom config."""
    global _default_llm
    if config is not None:
        return LLMProvider(config)
    if _default_llm is None:
        _default_llm = LLMProvider()
    return _default_llm


async def generate_folder_docs_async(analyzer, final_docs: dict, semaphore: asyncio.Semaphore, llm_config: "LLMConfig" = None) -> tuple:
    """
    Generate folder-level documentation from module docs (async version).

    Bottom-up approach: Process deepest folders first, then work up.
    Within each depth level, process folders in parallel.

    Args:
        analyzer: ImportGraph analyzer with codebase structure
        final_docs: Dict mapping module names to their documentation
        semaphore: Semaphore for rate limiting LLM calls

    Returns:
        (folder_docs, folder_tree) - docs dict and hierarchical tree structure
    """
    print("\n📁 Generating folder-level documentation (bottom-up, parallel per level)...\n")

    # Get LLM instance
    llm = get_llm(llm_config)

    # Import dependencies for dynamic prompt generation
    from layer2.prompts.folder_prompts import get_folder_documentation_prompt
    from layer1.grouper import FolderProcessor

    processor = FolderProcessor(analyzer)

    # Group folders by depth (bottom-up)
    folders_by_depth = {}
    for folder in processor.get_folders_bottom_up():
        if folder.file_count == 0:
            continue
        depth = folder.depth
        if depth not in folders_by_depth:
            folders_by_depth[depth] = []
        folders_by_depth[depth].append(folder)

    # Sort depths from deepest to shallowest
    sorted_depths = sorted(folders_by_depth.keys(), reverse=True)

    folder_docs = {}
    folder_tree = {}  # Store hierarchical structure for condenser

    # Process each depth level sequentially
    for depth in sorted_depths:
        level_folders = folders_by_depth[depth]
        print(f"  📂 Depth {depth}: {len(level_folders)} folder(s)")

        # Create task for each folder at this level
        async def process_folder(folder_info):
            # Get context with child folders included
            context = processor.get_llm_context(folder_info.folder_path)

            # Format module descriptions
            module_descriptions = ""
            for module in sorted(context['modules']):
                if module in final_docs:
                    module_descriptions += f"\n- {module}: {final_docs[module][:200]}..."

            # Format child folder descriptions (if children already processed)
            child_folder_descriptions = ""
            child_folders = context.get('child_folders', [])
            for child_path in sorted(child_folders):
                if child_path in folder_docs:
                    # Truncate to first 300 chars for context
                    child_desc = folder_docs[child_path][:300]
                    child_folder_descriptions += f"\n- {child_path}: {child_desc}..."

            # Generate prompt with all available context
            prompt = get_folder_documentation_prompt(
                context,
                module_descriptions,
                child_folder_descriptions
            )

            # Use semaphore to respect MAX_CONCURRENT_TASKS
            async with semaphore:
                description = await llm.generate_async(prompt)

            return folder_info.folder_path, description, context

        # Run all folders at this depth in parallel (respecting semaphore)
        tasks = [process_folder(folder) for folder in level_folders]
        results = await asyncio.gather(*tasks)

        # Collect results and build tree structure
        for folder_path, description, context in results:
            folder_docs[folder_path] = description
            print(f"    ✓ {folder_path}")

            # Build tree structure for condenser access
            folder_tree[folder_path] = {
                'description': description,
                'depth': context['depth'],
                'parent': context.get('parent_path'),
                'children': context.get('child_folders', []),
                'modules': context.get('modules', [])
            }

    print(f"\n✓ Generated documentation for {len(folder_docs)} folders\n")
    return folder_docs, folder_tree
