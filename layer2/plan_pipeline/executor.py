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
from typing import Dict, List, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from config import LLMConfig, DocGenConfig

_default_llm = None


def get_llm(config: "LLMConfig" = None) -> LLMProvider:
    """Get LLM provider instance, optionally with custom config."""
    global _default_llm
    if config is not None:
        return LLMProvider(config)
    if _default_llm is None:
        _default_llm = LLMProvider()
    return _default_llm


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
    Validate context is sufficient for the section type.
    Different section types have different requirements.

    Returns:
        (is_sufficient, warning_message)
    """
    section_style = section.get('style', '').lower()
    section_id = section.get('section_id', '').lower()
    section_title = section.get('title', '').lower()
    context_size = len(context_data.strip()) if context_data else 0

    # Check what's actually in the context
    has_source_code = '```python' in context_data or 'def ' in context_data or 'class ' in context_data
    has_config = '```\n' in context_data and any(x in context_data.lower() for x in ['requirements', 'dependencies', 'install', 'environment', 'pyproject'])
    has_structure = '## Folder' in context_data or '📁' in context_data or '📦' in context_data

    # Sections that can have minimal context
    overview_sections = {'overview', 'introduction', 'about', 'summary', 'contributing'}
    is_overview = any(s in section_id or s in section_title for s in overview_sections)

    # Tutorial/Quickstart sections NEED source code
    is_tutorial = (
        section_style in ['tutorial', 'quickstart'] or
        'quickstart' in section_id or
        'quick' in section_id or
        'quick start' in section_title or
        'getting started' in section_title
    )

    if is_tutorial:
        if not has_source_code:
            return False, "MISSING SOURCE CODE - Tutorial/Quickstart needs actual code. Add 'entry_points' or 'source:{module}' to required_context."
        if context_size < 500:
            return False, f"INSUFFICIENT CONTEXT ({context_size} chars) - Tutorials need substantial code examples"

    # API Reference sections NEED code signatures
    is_api_docs = section_style == 'api-docs' or 'api' in section_id or 'reference' in section_title
    if is_api_docs:
        if not has_source_code:
            return False, "MISSING API SIGNATURES - API docs need 'api:{module}' or 'source:{module}' in required_context"

    # Installation sections SHOULD have config files
    is_install = 'install' in section_id or 'setup' in section_id or 'installation' in section_title
    if is_install:
        if not has_config and context_size < 200:
            return True, f"LIMITED CONFIG CONTEXT - Consider adding 'deps' or 'configs' to required_context"

    # General size checks
    if context_size == 0:
        return False, "NO CONTEXT - Section based only on inference (high hallucination risk)"
    elif context_size < 100 and not is_overview:
        return False, f"MINIMAL CONTEXT ({context_size} chars) - Very high hallucination risk"
    elif context_size < 300 and not is_overview:
        return True, f"LIMITED CONTEXT ({context_size} chars) - Some hallucination risk"

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
    generated_sections: dict = None,
    use_reasoner: bool = True,  # Use DeepSeek Reasoner for better quality
    llm_config: "LLMConfig" = None
) -> Tuple[str, str, Optional[str]]:
    """
    Generate a single documentation section.

    Args:
        use_reasoner: If True, uses DeepSeek Reasoner model for complex reasoning.
                      Recommended for final documentation generation.
        llm_config: Optional LLM configuration.

    Returns:
        (section_id, content, warning)
    """
    llm = get_llm(llm_config)

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

    # Call LLM with semaphore - use reasoner for complex generation
    async with semaphore:
        if use_reasoner:
            content = await llm.generate_with_reasoner_async(prompt)
        else:
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
    enable_logging: bool = True,
    use_reasoner: bool = None,
    config: "DocGenConfig" = None
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
        use_reasoner: If True, use DeepSeek Reasoner model for section generation.
                      If None, uses config.generation.use_reasoner or defaults to True.
        config: Optional DocGenConfig for LLM settings.

    Returns:
        Complete documentation markdown
    """
    # Resolve use_reasoner from config or default
    if use_reasoner is None:
        use_reasoner = config.generation.use_reasoner if config else True

    llm_config = config.llm if config else None

    output_dir = os.path.join(str(analyzer.root_folder), "output")

    # Initialize logger
    logger = None
    if enable_logging:
        logger = GenerationLogger(output_dir)
        logger.start(plan)

    plan_context = f"Project type: {plan['project_type']}, Audience: {plan['target_audience']}"

    # Get model name for logging
    if llm_config:
        model_name = llm_config.reasoner_model if use_reasoner else llm_config.chat_model
    else:
        model_name = "deepseek-reasoner" if use_reasoner else "deepseek-chat"
    print(f"📝 Executing documentation plan ({len(plan['sections'])} sections) using {model_name}...")
    
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
                        generated_sections=sections_dict.copy(),
                        use_reasoner=use_reasoner,
                        llm_config=llm_config
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
                    generated_sections=sections_dict,
                    use_reasoner=use_reasoner,
                    llm_config=llm_config
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
    generated_sections: dict = None
) -> str:
    """
    Robust context gathering with explicit vocabulary and fallbacks.

    Supports prefixed context types for clarity:
    - folder:{path}, module:{name}, source:{module}, api:{module}
    - config:{filename}, configs, deps
    - section:{id}, sections
    - tree, all_folders, entry_points

    Also handles legacy unprefixed requests with smart resolution.
    """
    required = section.get('required_context', [])
    context_parts = []

    # Lazy-loaded config reader
    _config_reader = None
    def get_config_reader():
        nonlocal _config_reader
        if _config_reader is None:
            _config_reader = ConfigFileReader(str(analyzer.root_folder))
            _config_reader.scan()
        return _config_reader

    def read_source_file(module_name: str, max_chars: int = 8000) -> Optional[str]:
        """Read source code for a module with multiple resolution strategies."""
        # Strategy 1: Direct module index lookup
        file_path = analyzer.module_index.get(module_name)
        if file_path and file_path.exists():
            try:
                source = file_path.read_text(encoding='utf-8')
                if len(source) > max_chars:
                    source = source[:max_chars] + f"\n\n... [truncated at {max_chars} chars]"
                return source
            except:
                pass

        # Strategy 2: Try with dots replaced by path separators (partial match)
        alt_name = module_name.replace('.', '/')
        for name, path in analyzer.module_index.items():
            if name.endswith(module_name) or name.endswith(module_name.replace('/', '.')) or alt_name in str(path):
                try:
                    source = path.read_text(encoding='utf-8')
                    if len(source) > max_chars:
                        source = source[:max_chars] + f"\n\n... [truncated]"
                    return source
                except:
                    pass

        # Strategy 3: Direct file path attempt
        for suffix in ['', '.py']:
            try:
                direct_path = analyzer.root_folder / f"{module_name}{suffix}"
                if direct_path.exists():
                    source = direct_path.read_text(encoding='utf-8')
                    if len(source) > max_chars:
                        source = source[:max_chars] + f"\n\n... [truncated]"
                    return source
            except:
                pass

        # Strategy 4: Search by filename
        target_file = module_name.split('.')[-1] + '.py'
        for name, path in analyzer.module_index.items():
            if path.name == target_file:
                try:
                    source = path.read_text(encoding='utf-8')
                    if len(source) > max_chars:
                        source = source[:max_chars] + f"\n\n... [truncated]"
                    return source
                except:
                    pass

        return None

    def extract_public_api(module_name: str) -> Optional[str]:
        """Extract public class and function signatures from a module."""
        source = read_source_file(module_name, max_chars=50000)
        if not source:
            return None

        try:
            import ast
            tree = ast.parse(source)
            signatures = []

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef) and not node.name.startswith('_'):
                    # Get class with its public methods
                    methods = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and not item.name.startswith('_'):
                            args = [a.arg for a in item.args.args if a.arg != 'self'][:4]
                            args_str = ', '.join(args)
                            if len(item.args.args) > len(args) + 1:
                                args_str += ', ...'
                            methods.append(f"{item.name}({args_str})")

                    sig = f"class {node.name}:"
                    if methods:
                        sig += "\n    " + "\n    ".join(f"def {m}" for m in methods[:10])
                    signatures.append(sig)

                elif isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
                    args = [a.arg for a in node.args.args][:5]
                    args_str = ', '.join(args)
                    if len(node.args.args) > 5:
                        args_str += ', ...'
                    signatures.append(f"def {node.name}({args_str})")

            return "\n\n".join(signatures) if signatures else None
        except:
            return None

    def get_entry_points() -> List[str]:
        """Detect common entry point modules."""
        entry_names = ['main', '__main__', 'app', 'cli', 'api', 'server', 'run', 'client', 'core']
        found = []

        # Check standard entry point names
        for name in entry_names:
            if name in analyzer.module_index:
                found.append(name)

        # Check for package's main __init__.py or primary module
        root_modules = []
        for name, path in analyzer.module_index.items():
            # Find modules directly under root
            try:
                rel_path = path.relative_to(analyzer.root_folder)
                if len(rel_path.parts) == 1:  # Direct child of root
                    root_modules.append(name)
            except:
                pass

        # Add primary package __init__ if it looks like main entry
        for name in root_modules:
            if name not in found and name not in ['__init__', 'setup', 'conftest']:
                found.append(name)

        return found[:4]  # Limit to 4 entry points

    # Process each context requirement
    for ctx in required:
        if not ctx:
            continue
        ctx = ctx.strip()

        # ═══════════════════════════════════════════════════════════════
        # PREFIXED CONTEXT TYPES (explicit vocabulary)
        # ═══════════════════════════════════════════════════════════════

        if ctx.startswith("folder:"):
            folder_path = ctx[7:]
            if folder_path in folder_docs:
                context_parts.append(f"## Folder: {folder_path}\n{folder_docs[folder_path]}\n")
                # Include immediate children
                if folder_path in folder_tree:
                    for child in folder_tree[folder_path].get('children', [])[:5]:
                        if child in folder_docs:
                            context_parts.append(f"### Subfolder: {child}\n{folder_docs[child][:600]}\n")

        elif ctx.startswith("module:"):
            module_name = ctx[7:]
            # Try exact match, then partial match
            doc = module_docs.get(module_name)
            if not doc:
                for key in module_docs:
                    if key.endswith(module_name) or module_name in key:
                        doc = module_docs[key]
                        module_name = key
                        break
            if doc:
                context_parts.append(f"## Module: {module_name}\n{doc}\n")

        elif ctx.startswith("source:"):
            module_name = ctx[7:]
            source = read_source_file(module_name)
            if source:
                context_parts.append(f"## Source Code: {module_name}\n```python\n{source}\n```\n")

        elif ctx.startswith("api:"):
            module_name = ctx[4:]
            api = extract_public_api(module_name)
            if api:
                context_parts.append(f"## Public API: {module_name}\n```python\n{api}\n```\n")

        elif ctx.startswith("config:"):
            filename = ctx[7:]
            reader = get_config_reader()
            content = reader.get_file_content(filename)
            if content:
                if len(content) > 3000:
                    content = content[:3000] + "\n... [truncated]"
                context_parts.append(f"## Config: {filename}\n```\n{content}\n```\n")

        elif ctx.startswith("section:"):
            section_id = ctx[8:]
            if generated_sections and section_id in generated_sections:
                content = generated_sections[section_id]
                preview = content[:2000] if len(content) > 2000 else content
                context_parts.append(f"## Reference: {section_id}\n{preview}\n")

        # ═══════════════════════════════════════════════════════════════
        # KEYWORD CONTEXT TYPES
        # ═══════════════════════════════════════════════════════════════

        elif ctx == "tree" or ctx == "project_structure":
            from layer1.grouper import FolderProcessor
            processor = FolderProcessor(analyzer)
            context_parts.append(f"## Project Structure\n{processor.get_folder_structure_str(include_modules=True)}\n")

        elif ctx == "all_folders":
            for folder_path in sorted(folder_tree.keys(), key=lambda f: folder_tree[f]['depth']):
                doc = folder_docs.get(folder_path, "")
                if doc:
                    indent = "  " * folder_tree[folder_path]['depth']
                    context_parts.append(f"{indent}## {folder_path}\n{doc[:1000]}\n")

        elif ctx == "top_level_folders":
            for folder_path, info in folder_tree.items():
                if info['depth'] == 0:
                    doc = folder_docs.get(folder_path, "")
                    context_parts.append(f"## Folder: {folder_path}\n{doc}\n")

        elif ctx == "entry_points":
            for ep in get_entry_points():
                source = read_source_file(ep, max_chars=6000)
                if source:
                    context_parts.append(f"## Entry Point: {ep}\n```python\n{source}\n```\n")

        elif ctx == "configs" or ctx == "config_files":
            reader = get_config_reader()
            for filename in list(reader.get_all_config_files().keys())[:8]:
                content = reader.get_file_content(filename)
                if content:
                    preview = content[:1200] if len(content) > 1200 else content
                    context_parts.append(f"## {filename}\n```\n{preview}\n```\n")

        elif ctx == "priority_config":
            reader = get_config_reader()
            for filename, path in reader.get_priority_files().items():
                content = reader.get_file_content(filename)
                if content:
                    if len(content) > 2000:
                        content = content[:2000] + "\n\n... [truncated]"
                    context_parts.append(f"## {filename}\n```\n{content}\n```\n")

        elif ctx == "deps":
            reader = get_config_reader()
            dep_files = ['requirements.txt', 'pyproject.toml', 'setup.py', 'environment.yml', 'Pipfile', 'setup.cfg']
            for filename in dep_files:
                content = reader.get_file_content(filename)
                if content:
                    if len(content) > 2500:
                        content = content[:2500] + "\n... [truncated]"
                    context_parts.append(f"## {filename}\n```\n{content}\n```\n")

        elif ctx == "sections" or ctx == "previous_sections":
            if generated_sections:
                for sid, content in generated_sections.items():
                    preview = content[:1500] if len(content) > 1500 else content
                    context_parts.append(f"## Previous: {sid}\n{preview}\n")

        # ═══════════════════════════════════════════════════════════════
        # LEGACY/FALLBACK RESOLUTION (backwards compatibility)
        # ═══════════════════════════════════════════════════════════════

        elif ctx.endswith('.py'):
            # Legacy: "layer1/parser.py" → try as source code
            module_name = ctx[:-3].replace('/', '.')
            source = read_source_file(module_name)
            if source:
                context_parts.append(f"## Source: {ctx}\n```python\n{source}\n```\n")
            # Also try module docs
            if module_name in module_docs:
                context_parts.append(f"## Module Doc: {ctx}\n{module_docs[module_name]}\n")

        elif ctx.endswith(('.yml', '.yaml', '.json', '.toml', '.ini', '.md', '.txt', '.cfg', '.rst')):
            # Legacy: config file by extension
            reader = get_config_reader()
            content = reader.get_file_content(ctx)
            if not content:
                # Try basename only
                basename = ctx.split('/')[-1] if '/' in ctx else ctx
                content = reader.get_file_content(basename)
            if content:
                if len(content) > 3000:
                    content = content[:3000] + "\n... [truncated]"
                context_parts.append(f"## {ctx}\n```\n{content}\n```\n")

        elif '/' in ctx or '.' in ctx:
            # Legacy: could be folder path or module path
            found_something = False

            # Try as folder first
            if ctx in folder_docs:
                context_parts.append(f"## Folder: {ctx}\n{folder_docs[ctx]}\n")
                if ctx in folder_tree:
                    for child in folder_tree[ctx].get('children', [])[:3]:
                        if child in folder_docs:
                            context_parts.append(f"### {child}\n{folder_docs[child][:500]}\n")
                found_something = True

            # Also try as module (source code)
            module_name = ctx.replace('/', '.')
            source = read_source_file(module_name)
            if source:
                context_parts.append(f"## Source: {ctx}\n```python\n{source}\n```\n")
                found_something = True

            # Try module docs
            if module_name in module_docs and not found_something:
                context_parts.append(f"## Module: {ctx}\n{module_docs[module_name]}\n")

    # ═══════════════════════════════════════════════════════════════
    # AUTO-INJECT: Dependencies from section dependencies field
    # ═══════════════════════════════════════════════════════════════

    dependencies = section.get('dependencies', [])
    if dependencies and generated_sections:
        dep_parts = []
        for dep_id in dependencies:
            if dep_id in generated_sections:
                content = generated_sections[dep_id]
                preview = content[:1500] if len(content) > 1500 else content
                dep_parts.append(f"## From: {dep_id}\n{preview}\n")
        if dep_parts:
            context_parts.append("\n--- DEPENDENT SECTIONS ---\n" + "\n".join(dep_parts))

    # ═══════════════════════════════════════════════════════════════
    # AUTO-INJECT: Entry points for tutorial/quickstart (safety net)
    # ═══════════════════════════════════════════════════════════════

    section_style = section.get('style', '').lower()
    section_id = section.get('section_id', '').lower()
    section_title = section.get('title', '').lower()

    is_tutorial = (
        section_style in ['tutorial', 'quickstart'] or
        'quickstart' in section_id or
        'quick' in section_id or
        'quick start' in section_title or
        'getting started' in section_title
    )

    current_context = '\n'.join(context_parts)
    has_source_code = '```python' in current_context

    if is_tutorial and not has_source_code:
        # No source code yet - auto-inject entry points as safety net
        context_parts.append("\n--- AUTO-INCLUDED ENTRY POINTS (for code examples) ---\n")
        for ep in get_entry_points()[:2]:
            source = read_source_file(ep, max_chars=5000)
            if source:
                context_parts.append(f"## Entry Point: {ep}\n```python\n{source}\n```\n")

    # Build final context with summary header
    final_context = '\n'.join(context_parts)

    # Add context summary at the top
    has_source = '```python' in final_context
    has_config = '```\n' in final_context and ('requirements' in final_context.lower() or 'environment' in final_context.lower())
    has_folders = '## Folder' in final_context
    has_api = '## Public API' in final_context

    summary_parts = []
    if has_source:
        summary_parts.append("SOURCE CODE")
    if has_api:
        summary_parts.append("API SIGNATURES")
    if has_config:
        summary_parts.append("CONFIG FILES")
    if has_folders:
        summary_parts.append("FOLDER DOCS")

    if summary_parts:
        context_header = f"[Context includes: {', '.join(summary_parts)}]\n\n"
    else:
        context_header = "[Context includes: MINIMAL/NO SPECIFIC DATA]\n\n"

    return context_header + final_context

