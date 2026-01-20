"""Documentation planning and execution prompts."""


def get_documentation_plan_prompt(
    folder_structure: str,
    folder_docs: dict,
    total_modules: int,
    total_folders: int,
    cycle_count: int,
    has_cli: bool,
    has_cli_framework: bool = False,
    cli_frameworks: str = None,
    main_py_preview: str = None,
    has_tests: bool = False,
    config_files: str = None,
    reviewer_feedback: str = None
) -> str:
    """Generate prompt for documentation planning agent"""

    folder_summary = "\n".join([
        f"- {folder}: {doc[:150]}..."
        for folder, doc in list(folder_docs.items())[:10]
    ])

    feedback_section = f"\n\nREVIEWER FEEDBACK (from previous attempt):\n{reviewer_feedback}\n\nPlease address the feedback above in your revised plan.\n" if reviewer_feedback else ""
    
    config_section = f"\n\nCONFIGURATION FILES AVAILABLE:\n{config_files}\n" if config_files else "\n\nNo configuration files found.\n"
    
    # Build CLI classification info
    cli_info = f"""- Has main.py entrypoint: {has_cli}
- Has CLI framework (argparse/click/typer): {has_cli_framework}"""
    if cli_frameworks:
        cli_info += f"\n- CLI frameworks detected: {cli_frameworks}"
        
    main_py_section = ""
    if main_py_preview:
        main_py_section = f"\n\nENTRY POINT PREVIEW (main.py):\n```python\n{main_py_preview}\n```\n"

    return f"""
You are a technical documentation architect. Your task is to analyze a Python codebase and design the optimal documentation structure.

CODEBASE ANALYSIS
-----------------
- Total modules: {total_modules}
- Total folders: {total_folders}
- Dependency cycles: {cycle_count}
{cli_info}
- Has tests: {has_tests}

FOLDER STRUCTURE:
{folder_structure}

FOLDER SUMMARIES (sample):
{folder_summary}
{config_section}{main_py_section}

═══════════════════════════════════════════════════════════════════════════════
CRITICAL: PROJECT TYPE CLASSIFICATION
═══════════════════════════════════════════════════════════════════════════════

Use these criteria to classify the project:

• "CLI tool" = ONLY if has_cli_framework=True (argparse, click, typer detected)
  → Requires actual command-line argument parsing
  → Has user-facing commands like "myapp command --flag"

• "library" = Importable Python package for other developers
  → main.py alone does NOT make it a CLI tool
  → No CLI framework = likely a library or framework

• "framework" = Provides structure/patterns for building applications
  → Usually has layers, plugins, or extensibility points
  → This project appears to be a FRAMEWORK for documentation generation

• "utility" = Simple scripts or tools without full CLI interface
  → Run with "python script.py" but no complex arg parsing

IMPORTANT: This codebase has has_cli_framework={has_cli_framework}
→ If False, do NOT classify as "CLI tool"
→ If False, do NOT plan "CLI Usage" sections with command examples

TESTING SECTIONS:
→ has_tests={has_tests}
→ If has_tests=False, do NOT plan "Testing Strategy" or "Quality Assurance" sections
→ A single test_*.py file is NOT a "comprehensive test suite"
→ Only plan testing sections if tests/ directory exists with multiple test files
{feedback_section}
YOUR TASK
---------
Design a documentation plan that:
1. Identifies the project type CORRECTLY based on above criteria
2. Determines target audience (end users, developers, contributors)
3. Creates an optimal section structure (not just generic README template)
4. Specifies which context each section needs (avoid loading everything)
5. Orders sections logically (dependencies between sections)

Output JSON with this schema:

{{
  "project_type": "CLI tool | library | web service | framework | utility | data pipeline",
  "target_audience": "end-users | library-users | contributors | all",
  "primary_use_case": "1-sentence description of what this project does",
  "architecture_pattern": "layered | plugin-based | monolith | microservices | pipeline | mvc",

  "sections": [
    {{
      "section_id": "unique-id",
      "title": "Section Title",
      "purpose": "What this section explains and why it's needed",
      "required_context": ["layer1", "layer2/writer.py", "all_folders", "environment.yml"],
      "style": "tutorial | reference | architecture | guide | api-docs",
      "max_tokens": 500,
      "dependencies": ["other-section-id"]
    }}
  ],

  "glossary": [
    {{"term": "DocAgent", "definition": "AI-based documentation generator"}}
  ]
}}

REQUIRED_CONTEXT OPTIONS:
- Folder paths: "layer1", "layer2/services" - loads folder documentation
- Module paths: "layer1/parser.py" - loads specific module documentation  
- Config files: "environment.yml", "requirements.txt", "README.md" - loads file content
- Special keywords:
  - "all_folders" - all folder summaries
  - "top_level_folders" - only root-level folders
  - "project_structure" - full project tree
  - "priority_config" - all key config files (environment.yml, requirements.txt, etc.)
  - "config_files" - all configuration files

GUIDELINES:
- Tailor sections to THIS codebase (don't use generic template)
- If it's a CLI tool, include Quick Start and Usage prominently
- If it's a library, emphasize API Reference and Integration Guide
- If there are cycles, include Architecture section early
- Only include sections that add value (skip generic boilerplate)
- Specify minimal required_context per section (not "all")
- IMPORTANT: For Installation/Setup sections, ALWAYS include relevant config files like "environment.yml" or "requirements.txt" in required_context
- Order: overview → setup → usage → architecture → contributing
- NEVER include "Testing Strategy" section unless has_tests=True AND tests/ directory exists
- NEVER include "Quality Assurance" section based on inference from single files

Generate the plan now.
"""


def get_section_generation_prompt(
    section: dict,
    context_data: str,
    plan_context: str
) -> str:
    """Generate prompt for creating a single documentation section"""
    
    # Check if context is empty or minimal
    context_warning = ""
    if not context_data or len(context_data.strip()) < 50:
        context_warning = """
⚠️ WARNING: LIMITED CONTEXT AVAILABLE
The context provided is minimal or empty. You MUST:
- Only describe what can be inferred from the section purpose and project type
- NOT invent specific features, commands, APIs, or code examples
- Keep the section brief and factual
- State clearly if specific details are not available
"""

    return f"""
You are generating a specific section of a project's documentation.

DOCUMENTATION PLAN CONTEXT:
{plan_context}

SECTION TO GENERATE:
- Title: {section['title']}
- Purpose: {section['purpose']}
- Style: {section['style']}
- Max tokens: {section['max_tokens']}

RELEVANT CONTEXT (filtered for this section only):
{context_data if context_data else "[NO SPECIFIC CONTEXT PROVIDED]"}
{context_warning}

═══════════════════════════════════════════════════════════════════════════════
CRITICAL ANTI-HALLUCINATION RULES (MUST FOLLOW):
═══════════════════════════════════════════════════════════════════════════════

You MUST use ONLY factual information from the RELEVANT CONTEXT above.

DO NOT INVENT OR FABRICATE:
✗ CLI commands, flags, or arguments (like --help, --config, init, build, deploy)
✗ Configuration file options not shown in actual config files
✗ API endpoints, function signatures, or class methods not in the code
✗ Installation commands beyond what's shown (e.g., don't invent "pip install pkg-name")
✗ Features, capabilities, or behaviors not evidenced in the context

IF CONTEXT IS MISSING OR INSUFFICIENT:
- Write a SHORT, honest paragraph explaining the general purpose
- Do NOT pad with generic/placeholder content
- Say "See the source code for implementation details" rather than inventing details

EXECUTE vs IMPORT RULE (FOR USAGE SECTIONS):
- Determine if the codebase is an APPLICATION (runnable) or a LIBRARY (importable).
- IF RUNNABLE (scripts, servers):
    - Document how to RUN it (e.g., `python main.py`, `uvicorn app:app`).
    - Do NOT invent a wrapper script (like run_agent.py) to import the main class.
- IF LIBRARY:
    - Document how to IMPORT it.

WHAT YOU CAN DO:
- Describe actual code, classes, functions shown in context
- Quote or reference actual config file contents
- Explain architecture based on actual folder/module structure
- Provide accurate installation steps if environment.yml or requirements.txt is shown

═══════════════════════════════════════════════════════════════════════════════
GROUNDING & TRACEABILITY:
═══════════════════════════════════════════════════════════════════════════════

Every factual claim SHOULD be traceable to specific context provided.
- When describing a component, reference its location: "The ImportGraph class (layer1/parser.py)..."
- If you cannot trace a claim to provided context, either omit it or prefix with "Based on common patterns..."

═══════════════════════════════════════════════════════════════════════════════
INFERENCE LIMITATIONS:
═══════════════════════════════════════════════════════════════════════════════

Do NOT extrapolate organizational practices from limited evidence:
- One test file (test_*.py) does NOT establish a "comprehensive test suite"
- One script does NOT establish a "CLI tool" without argparse/click/typer
- Do NOT describe testing strategies unless a tests/ directory with multiple test files exists
- Do NOT describe CI/CD unless .github/workflows/ or similar CI config exists
- Do NOT describe "quality assurance processes" unless explicitly documented

RULE: "One file does not establish a pattern"

═══════════════════════════════════════════════════════════════════════════════
PRODUCTION vs TEST CODE:
═══════════════════════════════════════════════════════════════════════════════

- Only document classes/functions from PRODUCTION files as core components
- Files matching test_*.py, *_test.py, or in tests/ are TEST UTILITIES, not production
- If a class only exists in test files, label it as "Test Utility" or omit from architecture
- Verify: if a class is not imported in main entry points, question its centrality

═══════════════════════════════════════════════════════════════════════════════
INSUFFICIENT CONTEXT GUIDANCE:
═══════════════════════════════════════════════════════════════════════════════

- Prefer SHORT, accurate sections over LONG, padded sections
- If context supports only 50 tokens of facts, write 50 tokens (not 500 of padding)
- Acceptable responses when context is thin:
  ✓ "See the source code for implementation details"
  ✓ "Testing approach not documented in available context"
  ✓ A 2-3 sentence factual summary

BAD EXAMPLE (DO NOT GENERATE):
✗ "The project uses a comprehensive test suite with unit and integration tests"
  (Unless tests/ directory actually exists with multiple test files)

GOOD EXAMPLE:
✓ "Testing approach not formally documented. The test_local_embedder.py file
   provides a manual verification script for the embedding pipeline."

═══════════════════════════════════════════════════════════════════════════════

YOUR TASK:
Write ONLY the "{section['title']}" section following these rules:
1. Write in {section['style']} style
2. Focus ONLY on: {section['purpose']}
3. Keep it under {section['max_tokens']} tokens
4. Use markdown formatting (headers, code blocks, lists)
5. Do NOT repeat content from other sections
6. Start with a level 2 heading (## {section['title']})

Generate the section content now.
"""


def get_plan_review_prompt(plan: dict, analyzer, folder_docs: dict) -> str:
    """Generate prompt for plan validation"""

    sections_summary = "\n".join([
        f"- {s['section_id']}: {s['title']} ({s['style']})"
        for s in plan['sections']
    ])

    return f"""
Review this documentation plan for a Python project.

PROJECT TYPE: {plan['project_type']}
TARGET AUDIENCE: {plan['target_audience']}

PLANNED SECTIONS:
{sections_summary}

Evaluate:
1. Are sections appropriate for this project type?
2. Is the order logical (dependencies respected)?
3. Are required_context specifications realistic?
4. Are any critical sections missing?
5. Are there unnecessary sections?

Return JSON:
{{
  "plan_valid": boolean,
  "feedback": "Detailed suggestions or empty if valid",
  "missing_sections": ["section-id"],
  "unnecessary_sections": ["section-id"],
  "ordering_issues": "Description or empty"
}}
"""
