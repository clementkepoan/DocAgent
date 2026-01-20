"""
Centralized LLM Prompt Router
==============================

Single source of truth for all LLM prompts used in the documentation pipeline.
Prompts are organized by component and easily maintainable/versionable.

Structure:
- Module documentation prompts
- Review validation prompts
- Folder-level analysis prompts
"""

from typing import Dict, List, Set, Any


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
      "category": "factual_error | missing_info | vague_language | dependency_confusion | invented_behavior",
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

Guidelines for Output:
- If the documentation is fully correct and clear, set review_passed = true and review_suggestions = [].
- If there are any issues:
  - set review_passed = false
  - provide structured suggestions with category, issue, and fix
- Do NOT rewrite the documentation.
- Ensure the JSON is well-formed and parsable.
"""


def get_folder_documentation_prompt(context: Dict[str, Any],
                                     module_descriptions: str) -> str:
    """
    Generate LLM prompt for folder-level documentation.
    
    Args:
        context: Folder context dict with path, depth, metrics, modules
        module_descriptions: Formatted descriptions of modules in this folder
    
    Returns:
        Formatted LLM prompt for folder documentation
    """
    folder_path = context['folder_path']
    parent_path = context['parent_path']
    file_count = context['file_count']
    modules = context['modules']
    metrics = context['metrics']
    
    return f"""
Explain the Python folder `{folder_path}`.

SCOPE: {"Root-level package" if not parent_path else f"Subfolder of {parent_path}"}
FILES: {file_count} Python modules
METRICS: {metrics}

MODULES: {', '.join(modules)}
MODULE DESCRIPTIONS:{module_descriptions if module_descriptions else " (None generated yet)"}

Describe:
1. This folder's responsibility and purpose
2. Its role in the broader architecture
3. Key patterns or abstractions in its modules
4. Coupling concerns (high external imports = likely unstable)

Answer in 5-7 sentences.
"""

def get_condenser_documentation_prompt(
    folder_structure: str,
    folder_docs_text: str,
    module_docs_text: str,
) -> str:
    """
    Construct a comprehensive LLM prompt for condensing codebase documentation.

    This prompt instructs a large language model to synthesise a polished,
    professional README or DOCUMENTATION.md from the provided context.  It
    outlines the desired structure and style, encourages best practices from
    popular open source projects, and defines the sections and content to
    include.  By passing in the folder structure, folder‐level documentation
    and module‐level documentation, callers ensure the model has all the
    information it needs to generate a detailed, coherent summary of the
    codebase.

    Args:
        folder_structure: A high‑level visualisation of the project's folder
            hierarchy.  This might be a tree view or outline showing
            directories and their relative depths.
        folder_docs_text: The formatted folder‑level documentation generated
            earlier in the pipeline.  Each folder's purpose and metrics should
            be included here.
        module_docs_text: The formatted module‑level documentation generated
            earlier in the pipeline.  Function/class summaries and dependency
            information should be included.

    Returns:
        A formatted markdown prompt string.  When sent to a capable LLM, this
        prompt should yield a comprehensive README that covers everything from
        installation and quick start to architecture, project structure,
        components, troubleshooting, contributing guidelines, tests, security
        considerations and licensing.  The return value contains no extra
        commentary or analysis - only instructions for the model.
    """
    return f"""
You are a technical documentation expert tasked with producing a comprehensive,
professional README or DOCUMENTATION.md for a Python project.  The README
should feel like it belongs to a mature open source library (see examples like
React, Vue, TensorFlow, FastAPI) and should inspire confidence in users and
contributors.

CONTEXT
-------

PROJECT STRUCTURE:
{folder_structure}

FOLDER‑LEVEL DOCUMENTATION:
{folder_docs_text}

MODULE‑LEVEL DOCUMENTATION:
{module_docs_text}

GOAL
----

Use the provided context to draft a standalone README that covers all aspects
of the project.  Your README should be organised with clear headings,
subheadings, code blocks, bullet lists and concise paragraphs.  Use anchor
links for the table of contents and keep sentences crisp and engaging.
Sprinkle relevant emojis sparingly (e.g. 🚀, 📦, ⚡, 🔧, 📚, 🎯, ✨) to emphasise
important points.

**Sections to include (in order):**

1. **Title & tagline**  
   - Use the project name as the main heading (for example
     “DocAgent — AI‑assisted Codebase Documentation Generator”).  
   - Provide a one‑line summary of what the tool does and who it’s for.  
   - Include a short list of placeholder badges (version, license, build
     status).

2. **Table of Contents**  
   - Provide a clean, indented list of links pointing to all major sections
     described below.

3. **Quick Start**  
   - Describe how to clone the repository, set up the environment (e.g.
     conda or pip), set the LLM API key, and run the generator.  
   - Use shell commands in fenced code blocks and note that outputs are
     written to `./output` by default.  Mention asynchronous behaviour where
     relevant.

4. **Installation**  
   - Offer a minimal pip installation alternative and mention that
     `environment.yml` contains full dependencies.  
   - Mention the recommended Python version (e.g. 3.10+) and highlight
     optional extras.

5. **Configuration**  
   - Explain how to set the LLM provider (e.g. using a `DEEPSEEK_KEY`),
     adjust embedding models (default “BAAI/bge-small-en-v1.5”), control GPU
     usage and set concurrency (`MAX_CONCURRENT_TASKS`).  
   - Encourage users to adapt the provider code if they wish to use another
     API such as OpenAI.

6. **Usage**  
   - Provide CLI usage (running `main.py`) with a bullet list of what
     happens internally (analyse imports, chunk and retrieve source,
     generate module docs, run a review pass, write outputs).  
   - Provide a programmatic example using `AsyncDocGenerator` with
     `asyncio.run(...)` to illustrate integrating the generator into custom
     pipelines.

7. **Outputs & Where to Find Them**  
   - Describe the files created in the output directory:  
     * `scc_contexts.txt` - human‑readable architecture overviews for
       strongly connected components (mutual dependency cycles).  
     * `Module level docum.txt` - aggregated module‑level documentation.  
     * `Folder Level docum.txt` - folder‑level summaries generated by
       condensing module docs.  
     * `Final Condensed.md` - the final README‑style condensed documentation
       generated from folder and module docs.  
     * `dependency used.txt` - a log of dependency usage and whether docs for
       dependencies were available when a module was processed.  
   - Note that file names can be customised by editing the output writer.

8. **Architecture (Layers & Flow)**  
   - Summarise the layered pipeline:  
     * **Layer 1 - Ingestion & Vectorisation:** parse Python files using the
       AST, produce chunks (functions, classes or fallback whole files) and
       embed them using sentence transformers.  
     * **Layer 2 - Retrieval & LLM Interactions:** load code chunks for a
       given module via a retriever, prepare structured prompts via a
       central prompt router, call the LLM via a provider (sync/async), and
       verify outputs via a reviewer that enforces JSON structure.  
     * **Layer 3 - Orchestration & Output:** coordinate the process using
       an async doc generator, schedule modules in dependency‑resolved batches
       with concurrency control, handle strongly connected component
       contexts, and consolidate the results via an output writer.  
   - Explain concurrency and correctness: modules are processed in
     dependency‑ordered batches so that dependencies are documented before
     dependants, a semaphore controls concurrent LLM calls to avoid
     overloading resources, and a retry loop allows for re‑generation if
     review fails.

9. **Project Structure (Key Files)**  
   - Present a tree or outline of important files and directories with
     one‑line descriptions, for example:  
     * `main.py` - simple entrypoint for running the async pipeline.  
     * `environment.yml` - conda + pip environment definition.  
     * `import_graph.png` - visualisation of the import graph.  
     * `layer1/` - code analysis and processing (parser, chunker,
       embedder).  
     * `layer2/` - documentation orchestration (llm provider, retriever,
       prompt router, reviewer, schemas).  
     * `layer3/` - pipeline coordination (async generator, batch
       processor, scc manager, output writer, progress reporter).  
   - Include any other top‑level files or directories relevant to the
     project.

10. **Core Components — short descriptions & customisation points**  
   - For each key class or function (e.g. `ImportGraph`, `CodeChunker`,
     `CodeEmbedder`, `LLMProvider`, `PromptRouter`, `Reviewer`,
     `BatchProcessor`), describe its responsibility and list ways users can
     customise it (changing chunk granularity, switching embedding model,
     modifying prompts, adjusting retries or concurrency).  
   - Provide usage examples or signatures in fenced `python` code blocks
     where helpful.

11. **Troubleshooting & Tips**  
   - List common problems and their solutions, such as missing API keys,
     model downloads consuming too much disk, GPU detection issues,
     JSON parse errors from noisy LLM outputs, how to change output file
     names, and strategies for large codebases (e.g. reducing concurrency,
     caching embeddings).  
   - Use bullet points for clarity.

12. **Development & Contributing**  
   - Encourage users to edit `prompt_router.py` to refine output style,
     adjust concurrency/timeouts and batch sizes in the orchestrator or
     batch processor, add tests using provided artefacts, and extend the
     LLM provider to support other APIs or streaming.  
   - Include instructions for running tests and outline project
     conventions.

13. **Tests & Example Artifacts**  
   - Describe any test‑mode artefacts produced by the code, such as
     `chunks_test.json` (sample chunks from the AST chunker) and
     `embeddings_test.json` (example embedding vectors).  
   - Explain that these files are useful for verifying behaviour and
     developing unit tests.

14. **Security & Privacy**  
   - Caution users that the tool sends code to the configured LLM provider
     and that they should not run it on private or proprietary code without
     ensuring the provider’s policies meet their security requirements.  
   - Suggest options for restricted or air‑gapped deployments if needed.

15. **License**  
   - Include a placeholder license section and encourage adding a proper
     license file (e.g. MIT, Apache, BSD) to the repository.

16. **Acknowledgements & Inspirations**  
   - Briefly mention inspirations such as DocAgent patterns and
     retrieval‑augmented generation (RAG) workflows, and list major
     dependencies like sentence transformers and the OpenAI‑compatible API.

STYLE NOTES
-----------

- Keep paragraphs short (3-5 sentences) and break up text with lists and
  tables.  
- Use fenced code blocks with language identifiers (e.g. `python`, `bash`) for
  code samples.  
- Use tables only for compact data, not for long paragraphs.  
- Use collapsible `<details>` blocks for lengthy sections if needed.  
- The final output must be pure markdown ready to save as `README.md` and
  must not include this prompt text or any commentary.

Generate the full README using the context provided.  Ensure that it is
polished, engaging and comprehensive.  Return only the README content.
"""


def get_documentation_plan_prompt(
    folder_structure: str,
    folder_docs: dict,
    total_modules: int,
    total_folders: int,
    cycle_count: int,
    has_cli: bool,
    has_tests: bool,
    reviewer_feedback: str = None
) -> str:
    """Generate prompt for documentation planning agent"""

    folder_summary = "\n".join([
        f"- {folder}: {doc[:150]}..."
        for folder, doc in list(folder_docs.items())[:10]
    ])

    feedback_section = f"\n\nREVIEWER FEEDBACK (from previous attempt):\n{reviewer_feedback}\n\nPlease address the feedback above in your revised plan.\n" if reviewer_feedback else ""

    return f"""
You are a technical documentation architect. Your task is to analyze a Python codebase and design the optimal documentation structure.

CODEBASE ANALYSIS
-----------------
- Total modules: {total_modules}
- Total folders: {total_folders}
- Dependency cycles: {cycle_count}
- Has CLI entrypoint: {has_cli}
- Has tests: {has_tests}

FOLDER STRUCTURE:
{folder_structure}

FOLDER SUMMARIES (sample):
{folder_summary}
{feedback_section}
YOUR TASK
---------
Design a documentation plan that:
1. Identifies the project type (library, CLI tool, web service, etc.)
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
      "required_context": ["layer1", "layer2/writer.py", "all_folders"],
      "style": "tutorial | reference | architecture | guide | api-docs",
      "max_tokens": 500,
      "dependencies": ["other-section-id"]
    }}
  ],

  "glossary": [
    {{"term": "DocAgent", "definition": "AI-based documentation generator"}}
  ]
}}

GUIDELINES:
- Tailor sections to THIS codebase (don't use generic template)
- If it's a CLI tool, include Quick Start and Usage prominently
- If it's a library, emphasize API Reference and Integration Guide
- If there are cycles, include Architecture section early
- Only include sections that add value (skip generic boilerplate)
- Specify minimal required_context per section (not "all")
- Order: overview → setup → usage → architecture → contributing

Generate the plan now.
"""


def get_section_generation_prompt(
    section: dict,
    context_data: str,
    plan_context: str
) -> str:
    """Generate prompt for creating a single documentation section"""

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
{context_data}

YOUR TASK:
Write ONLY the "{section['title']}" section. Follow these rules:
1. Write in {section['style']} style
2. Focus ONLY on the purpose stated above
3. Use ONLY the context provided (do not invent details)
4. Keep it under {section['max_tokens']} tokens
5. Use markdown formatting (headers, code blocks, lists)
6. Do NOT include other sections or boilerplate

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