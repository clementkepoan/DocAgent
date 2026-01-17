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


def get_condenser_documentation_prompt(folder_structure: str,
                                        folder_docs_text: str,
                                        module_docs_text: str) -> str:
    """
    Generate LLM prompt for comprehensive documentation condensing.
    
    Args:
        folder_structure: High-level folder structure visualization
        folder_docs_text: Formatted folder-level documentation
        module_docs_text: Formatted module-level documentation
    
    Returns:
        Formatted LLM prompt for comprehensive documentation generation
    """
    return f"""
You are a technical documentation expert tasked with creating comprehensive, professional README-style documentation similar to popular GitHub repositories (like React, Vue, TensorFlow, FastAPI, etc.).

CONTEXT & SOURCE MATERIAL
=========================

PROJECT STRUCTURE:
{folder_structure}

FOLDER-LEVEL DOCUMENTATION:
{folder_docs_text}

MODULE-LEVEL DOCUMENTATION:
{module_docs_text}

TASK
====

Create a professional, engaging markdown documentation file following modern GitHub README best practices:

**STRUCTURE TO FOLLOW:**

1. **Title & Badges Section**
   - Project name as main heading
   - Brief one-line description
   - Add placeholder badges (version, license, build status, etc.)

2. **Table of Contents**
   - Clickable links to all major sections
   - Clean, organized structure

3. **Overview** (2-3 paragraphs)
   - What the project does
   - Why it exists / problem it solves
   - Key features (3-5 bullet points with emojis)

4. **Quick Start** / **Installation**
   - Clear, copy-paste ready commands
   - Prerequisites if any
   - Basic usage example

5. **Architecture** 
   - High-level architecture diagram description
   - Core design patterns and principles
   - Technology stack

6. **Project Structure**
   - Tree-like folder visualization with explanations
   - Purpose of each major directory
   - How components interact

7. **Core Components** / **API Reference**
   - Organized by folders/modules
   - For each component:
     * Purpose and responsibility
     * Key classes/functions with signatures
     * Usage examples with code blocks
     * Important parameters/returns

8. **Key Features & Capabilities**
   - Detailed feature descriptions
   - Use cases and examples
   - Performance characteristics if relevant

9. **Dependencies & Relationships**
   - Import graph or dependency tree
   - Module interaction patterns
   - External dependencies

10. **Development**
    - How to contribute
    - Running tests
    - Project conventions

11. **License** (placeholder)
    - Standard license section

**STYLE GUIDELINES:**

✅ DO:
- Use emojis sparingly but effectively (🚀 📦 ⚡ 🔧 📚 🎯 ✨)
- Write in active, engaging voice
- Include code examples in ```python blocks
- Use tables for structured information
- Add collapsible sections for lengthy content using <details>
- Use badges and shields at the top
- Keep sentences concise and scannable
- Use consistent formatting throughout

❌ DON'T:
- Write long paragraphs without breaks
- Use excessive technical jargon without explanation
- Forget code syntax highlighting
- Make walls of text - break it up visually
- Skip practical examples

**FORMATTING EXAMPLES:**

For features:
```markdown
### ⚡ Key Features

- 🔥 **Fast Processing** - Optimized algorithms for high-speed execution
- 📊 **Smart Analysis** - Intelligent code pattern recognition
- 🎯 **Precise Results** - Accurate dependency tracking
```

For API documentation:
```markdown
#### `function_name(param1, param2)`

**Description:** Brief explanation of what it does

**Parameters:**
- `param1` (type): Description
- `param2` (type): Description

**Returns:** What it returns

**Example:**
\```python
result = function_name("value", 42)
print(result)
\```
```

For collapsible sections:
```markdown
<details>
<summary>Click to expand detailed information</summary>

Detailed content here...

</details>
```

**OUTPUT REQUIREMENTS:**
- Return ONLY the markdown content
- No preamble or meta-commentary
- Ready to save as README.md or DOCUMENTATION.md
- Professional, polished, and visually appealing
- Should inspire confidence in the project
- Include realistic placeholder values where specific details are missing

Generate documentation that would make developers excited to use and contribute to this project!
"""
