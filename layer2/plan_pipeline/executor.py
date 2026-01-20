"""
Plan Execution Agent
=====================

Executes documentation plan by generating sections with focused context.
Supports both sequential and parallel generation modes.
"""

from layer2.services.llm_provider import LLMProvider
from layer2.prompts.plan_prompts import get_section_generation_prompt
from layer2.schemas.documentation import DocumentationPlan, DocumentationSection
from layer1.config_reader import ConfigFileReader
import asyncio
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional

llm = LLMProvider()


class GenerationLogger:
    """Logs generation context and prompts to a file for debugging."""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.log_path = os.path.join(output_dir, "generation.txt")
        os.makedirs(output_dir, exist_ok=True)
        self._file = None
    
    def start(self, plan: DocumentationPlan):
        """Start logging session."""
        self._file = open(self.log_path, 'w', encoding='utf-8')
        self._write("=" * 80)
        self._write("DOCUMENTATION GENERATION LOG")
        self._write("=" * 80)
        self._write(f"\nTimestamp: {datetime.now().isoformat()}")
        self._write(f"Project Type: {plan['project_type']}")
        self._write(f"Target Audience: {plan['target_audience']}")
        self._write(f"Primary Use Case: {plan['primary_use_case']}")
        self._write(f"Total Sections: {len(plan['sections'])}")
        self._write("\nPlanned Sections:")
        for idx, s in enumerate(plan['sections'], 1):
            self._write(f"  {idx}. {s['title']} ({s['style']}) - {s['purpose'][:60]}...")
        self._write("\n")
    
    def log_section(self, idx: int, total: int, section: dict, 
                    context_data: str, prompt: str, response: str,
                    context_warning: str = None):
        """Log a single section generation."""
        self._write("\n" + "=" * 80)
        self._write(f"SECTION {idx}/{total}: {section['title']}")
        self._write("=" * 80)
        
        self._write(f"\nSection ID: {section['section_id']}")
        self._write(f"Purpose: {section['purpose']}")
        self._write(f"Style: {section['style']}")
        self._write(f"Required Context: {section['required_context']}")
        
        if context_warning:
            self._write(f"\n⚠️ CONTEXT WARNING: {context_warning}")
        
        self._write(f"\n--- CONTEXT GATHERED ({len(context_data)} chars) ---")
        self._write(context_data)
        
        self._write(f"\n\n--- PROMPT SENT TO LLM ({len(prompt)} chars) ---")
        self._write(prompt)
        
        self._write(f"\n\n--- LLM RESPONSE ({len(response)} chars) ---")
        self._write(response)
        
        self._write("\n")
    
    def finish(self, success: bool = True):
        """Finish logging session."""
        self._write("\n" + "=" * 80)
        self._write(f"GENERATION {'COMPLETE' if success else 'FAILED'}")
        self._write(f"Timestamp: {datetime.now().isoformat()}")
        self._write("=" * 80)
        if self._file:
            self._file.close()
            self._file = None
        print(f"📋 Generation log saved to {self.log_path}")
    
    def _write(self, text: str):
        """Write to log file."""
        if self._file:
            self._file.write(text + "\n")


def validate_context_sufficiency(section: dict, context_data: str) -> Tuple[bool, str]:
    """
    Validate if the gathered context is sufficient for the section.
    
    Returns:
        (is_sufficient, warning_message)
    """
    # Sections that can have minimal context
    overview_sections = {'overview', 'introduction', 'about', 'summary'}
    section_id = section.get('section_id', '').lower()
    section_title = section.get('title', '').lower()
    
    # Check if this is an overview-type section (can have less context)
    is_overview = any(s in section_id or s in section_title for s in overview_sections)
    
    # Check context size
    context_size = len(context_data.strip()) if context_data else 0
    
    if context_size == 0:
        return False, "NO CONTEXT - Section will be based only on general project info"
    elif context_size < 100 and not is_overview:
        return False, f"MINIMAL CONTEXT ({context_size} chars) - May produce generic content"
    elif context_size < 500 and not is_overview:
        return True, f"LIMITED CONTEXT ({context_size} chars) - Consider adding more required_context"
    
    return True, None


def group_sections_by_dependency(sections: List[dict]) -> Dict[int, List[dict]]:
    """
    Group sections by dependency level for parallel execution.
    
    Sections with no dependencies are level 0.
    Sections depending on level N sections are level N+1.
    """
    # Build dependency map
    section_ids = {s['section_id'] for s in sections}
    levels = {}
    
    for section in sections:
        deps = section.get('dependencies', [])
        # Filter to only internal dependencies
        valid_deps = [d for d in deps if d in section_ids]
        
        if not valid_deps:
            levels[section['section_id']] = 0
        else:
            # Will be calculated in second pass
            levels[section['section_id']] = -1
    
    # Calculate levels for sections with dependencies
    max_iterations = len(sections)
    for _ in range(max_iterations):
        changed = False
        for section in sections:
            if levels[section['section_id']] != -1:
                continue
            
            deps = section.get('dependencies', [])
            valid_deps = [d for d in deps if d in section_ids]
            
            dep_levels = [levels.get(d, -1) for d in valid_deps]
            if all(l >= 0 for l in dep_levels):
                levels[section['section_id']] = max(dep_levels) + 1
                changed = True
        
        if not changed:
            break
    
    # Handle any remaining (circular deps) - put at last level
    max_level = max(l for l in levels.values() if l >= 0) if any(l >= 0 for l in levels.values()) else 0
    for section_id, level in levels.items():
        if level == -1:
            levels[section_id] = max_level + 1
    
    # Group sections by level
    grouped = {}
    for section in sections:
        level = levels[section['section_id']]
        if level not in grouped:
            grouped[level] = []
        grouped[level].append(section)
    
    return grouped


async def generate_single_section(
    section: dict,
    analyzer,
    folder_docs: dict,
    folder_tree: dict,
    module_docs: dict,
    plan_context: str,
    semaphore: asyncio.Semaphore,
    logger: Optional[GenerationLogger] = None,
    section_idx: int = 0,
    total_sections: int = 0,
    generated_sections: dict = None  # NEW: Previously generated sections
) -> Tuple[str, str, Optional[str]]:
    """
    Generate a single documentation section.
    
    Returns:
        (section_id, content, warning)
    """
    # Gather context (now includes generated_sections for dependency access)
    context_data = gather_section_context(
        section, analyzer, folder_docs, folder_tree, module_docs,
        generated_sections=generated_sections
    )
    
    # Validate context sufficiency
    is_sufficient, warning = validate_context_sufficiency(section, context_data)
    
    if warning:
        print(f"    ⚠️  {warning}")
    
    # Generate prompt
    prompt = get_section_generation_prompt(
        section=section,
        context_data=context_data,
        plan_context=plan_context
    )
    
    # Call LLM with semaphore
    async with semaphore:
        content = await llm.generate_async(prompt)
    
    # Log if logger provided
    if logger:
        logger.log_section(
            idx=section_idx,
            total=total_sections,
            section=section,
            context_data=context_data,
            prompt=prompt,
            response=content,
            context_warning=warning
        )
    
    return section['section_id'], content, warning


async def execute_documentation_plan(
    plan: DocumentationPlan,
    analyzer,
    folder_docs: dict,
    folder_tree: dict,
    module_docs: dict,
    semaphore: asyncio.Semaphore,
    parallel: bool = True,
    enable_logging: bool = True
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
        parallel: If True, generate sections in parallel where possible
        enable_logging: If True, log context and prompts to generation.txt

    Returns:
        Complete documentation markdown
    """
    output_dir = os.path.join(str(analyzer.root_folder), "output")
    
    # Initialize logger
    logger = None
    if enable_logging:
        logger = GenerationLogger(output_dir)
        logger.start(plan)
    
    plan_context = f"Project type: {plan['project_type']}, Audience: {plan['target_audience']}"
    
    print(f"📝 Executing documentation plan ({len(plan['sections'])} sections)...")
    
    sections_dict = {}  # section_id -> content (also used as generated_sections)
    
    try:
        if parallel:
            # Group sections by dependency level
            grouped = group_sections_by_dependency(plan['sections'])
            print(f"   Using parallel mode: {len(grouped)} dependency levels")
            
            section_idx = 0
            for level in sorted(grouped.keys()):
                level_sections = grouped[level]
                print(f"   Level {level}: Generating {len(level_sections)} sections in parallel...")
                
                # Create tasks for all sections at this level
                # Note: sections at the same level run in parallel, but they all have access
                # to previously generated sections from lower levels
                tasks = []
                for section in level_sections:
                    section_idx += 1
                    task = generate_single_section(
                        section=section,
                        analyzer=analyzer,
                        folder_docs=folder_docs,
                        folder_tree=folder_tree,
                        module_docs=module_docs,
                        plan_context=plan_context,
                        semaphore=semaphore,
                        logger=logger,
                        section_idx=section_idx,
                        total_sections=len(plan['sections']),
                        generated_sections=sections_dict.copy()  # Pass previous levels' content
                    )
                    tasks.append(task)
                
                # Execute all tasks at this level concurrently
                results = await asyncio.gather(*tasks)
                
                # Store results (available for next level)
                for section_id, content, warning in results:
                    sections_dict[section_id] = content
                    print(f"    ✓ {section_id}")
        else:
            # Sequential mode - each section has access to ALL previous sections
            for idx, section in enumerate(plan['sections'], 1):
                print(f"  [{idx}/{len(plan['sections'])}] Generating: {section['title']}")
                
                section_id, content, warning = await generate_single_section(
                    section=section,
                    analyzer=analyzer,
                    folder_docs=folder_docs,
                    folder_tree=folder_tree,
                    module_docs=module_docs,
                    plan_context=plan_context,
                    semaphore=semaphore,
                    logger=logger,
                    section_idx=idx,
                    total_sections=len(plan['sections']),
                    generated_sections=sections_dict  # Pass all previous sections
                )
                sections_dict[section_id] = content
        
        # Combine sections in original order
        sections_content = [f"# {plan['primary_use_case']}\n\n"]
        for section in plan['sections']:
            content = sections_dict.get(section['section_id'], '')
            if content:
                sections_content.append(content)
                sections_content.append("\n\n")
        
        final_doc = "".join(sections_content)
        
        if logger:
            logger.finish(success=True)
        
        print("✓ Documentation generation complete")
        return final_doc
        
    except Exception as e:
        if logger:
            logger.finish(success=False)
        raise


def gather_section_context(
    section: DocumentationSection,
    analyzer,
    folder_docs: dict,
    folder_tree: dict,
    module_docs: dict,
    generated_sections: dict = None  # NEW: Previously generated sections
) -> str:
    """
    Gather only the context needed for this specific section.

    This is KEY to avoiding hallucination - we don't dump everything.
    Uses folder_tree to access hierarchical structure efficiently.
    Supports: config files, source code, previous sections.
    """

    required = section['required_context']
    context_parts = []
    
    # Initialize config reader for file access (lazy - only used if needed)
    config_reader = None
    
    def get_config_reader():
        nonlocal config_reader
        if config_reader is None:
            config_reader = ConfigFileReader(str(analyzer.root_folder))
            config_reader.scan()
        return config_reader

    for ctx in required:
        if ctx == "all_folders":
            # Include all folder summaries in hierarchical order
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
            # Include specific Python module
            # Fix: Strip .py extension for module lookup
            module_name = ctx[:-3] if ctx.endswith(".py") else ctx
            
            # Also handle path-like names (layer1/parser.py -> layer1.parser)
            if "/" in module_name:
                module_name = module_name.replace("/", ".")
            
            # Try to find the module documentation
            found = False
            if module_name in module_docs:
                context_parts.append(f"## Module: {ctx}\n{module_docs[module_name]}\n")
                found = True
            elif ctx in module_docs:
                context_parts.append(f"## Module: {ctx}\n{module_docs[ctx]}\n")
                found = True
            
            # Also include actual source code for the module
            try:
                file_path = analyzer.module_index.get(module_name)
                if file_path and file_path.exists():
                    source = file_path.read_text(encoding='utf-8')
                    # Include source up to 8000 chars for key files
                    max_source = 8000
                    if len(source) > max_source:
                        source = source[:max_source] + "\n\n... [source truncated]"
                    context_parts.append(f"## Source Code: {ctx}\n```python\n{source}\n```\n")
                    found = True
            except Exception as e:
                pass
            
            if not found:
                # Try direct file read as fallback
                try:
                    direct_path = analyzer.root_folder / ctx
                    if direct_path.exists():
                        source = direct_path.read_text(encoding='utf-8')
                        if len(source) > 8000:
                            source = source[:8000] + "\n\n... [source truncated]"
                        context_parts.append(f"## Source Code: {ctx}\n```python\n{source}\n```\n")
                except:
                    pass
        
        # Handle config file extensions
        elif ctx.endswith(('.yml', '.yaml', '.md', '.json', '.txt', '.toml', '.ini', '.cfg', '.rst')):
            reader = get_config_reader()
            content = reader.get_file_content(ctx)
            if content:
                if len(content) > 3000:
                    content = content[:3000] + "\n\n... [truncated]"
                context_parts.append(f"## File: {ctx}\n```\n{content}\n```\n")
            else:
                # Try without path prefix
                basename = ctx.split('/')[-1] if '/' in ctx else ctx
                content = reader.get_file_content(basename)
                if content:
                    if len(content) > 3000:
                        content = content[:3000] + "\n\n... [truncated]"
                    context_parts.append(f"## File: {basename}\n```\n{content}\n```\n")
        
        # Include all config files summary
        elif ctx == "config_files":
            reader = get_config_reader()
            for filename, path in reader.get_all_config_files().items():
                content = reader.get_file_content(filename)
                if content:
                    preview = content[:800] if len(content) > 800 else content
                    context_parts.append(f"## Config: {filename}\n```\n{preview}\n```\n")
        
        # Include only priority config files
        elif ctx == "priority_config":
            reader = get_config_reader()
            for filename, path in reader.get_priority_files().items():
                content = reader.get_file_content(filename)
                if content:
                    if len(content) > 2000:
                        content = content[:2000] + "\n\n... [truncated]"
                    context_parts.append(f"## {filename}\n```\n{content}\n```\n")
        
        # NEW: Include all previously generated sections
        elif ctx == "previous_sections" and generated_sections:
            for sid, content in generated_sections.items():
                # Include up to 2000 chars of each previous section
                preview = content[:2000] if len(content) > 2000 else content
                context_parts.append(f"## Previous Section: {sid}\n{preview}\n")
        
        # NEW: Include a specific previous section by ID (e.g., "section:overview")
        elif ctx.startswith("section:") and generated_sections:
            ref_id = ctx.split(":", 1)[1]
            if ref_id in generated_sections:
                content = generated_sections[ref_id]
                context_parts.append(f"## Reference: {ref_id}\n{content}\n")
        
        # NEW: Include source code directly (e.g., "source:main" or "source:layer1.parser")
        elif ctx.startswith("source:"):
            module_name = ctx.split(":", 1)[1]
            try:
                file_path = analyzer.module_index.get(module_name)
                if file_path and file_path.exists():
                    source = file_path.read_text(encoding='utf-8')
                    if len(source) > 10000:
                        source = source[:10000] + "\n\n... [source truncated]"
                    context_parts.append(f"## Source: {module_name}\n```python\n{source}\n```\n")
            except:
                pass

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
    
    # NEW: Automatically include dependent sections' content
    dependencies = section.get('dependencies', [])
    if dependencies and generated_sections:
        dep_content_added = False
        for dep_id in dependencies:
            if dep_id in generated_sections:
                if not dep_content_added:
                    context_parts.append("\n--- PREVIOUSLY GENERATED (for context) ---\n")
                    dep_content_added = True
                dep_content = generated_sections[dep_id]
                # Show first 1500 chars of dependent section
                preview = dep_content[:1500] if len(dep_content) > 1500 else dep_content
                context_parts.append(f"## From: {dep_id}\n{preview}\n")

    return "\n".join(context_parts)

