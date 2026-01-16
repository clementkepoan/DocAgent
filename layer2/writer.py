from .schemas import AgentState
from .llmprovider import LLMProvider
from layer1.grouper import generate_llm_prompts
import json
import re

llm = LLMProvider()

def parse_doc_json(text: str) -> dict:
    """Extracts JSON from LLM response"""
    cleaned = re.sub(r"```json|```", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse documentation JSON: {e}\nRaw text:\n{text}")
    

def format_structured_doc(file: str, doc_data: dict) -> str:
    """Convert structured doc data to readable markdown"""
    
    key_funcs = "\n".join([
        f"  - `{func['name']}`: {func['purpose']}"
        for func in doc_data.get("key_functions", [])
    ])
    
    exports = ", ".join([f"`{e}`" for e in doc_data.get("exports", [])])
    
    return f"""
## Module: `{file}`

**Summary:** {doc_data.get('summary', 'N/A')}

**Responsibility:** {doc_data.get('responsibility', 'N/A')}

**Key Functions:**
{key_funcs if key_funcs else "  - None"}

**Dependency Usage:** {doc_data.get('dependency_usage', 'No dependencies')}

**Exports:** {exports if exports else "None"}

---
"""

def module_write(state: AgentState) -> AgentState:
    """Generate documentation for a single module"""
    # print("✍️ Writer running")

    file = state["file"]
    code = state["code_chunks"]
    deps = state["dependencies"]
    deps_docs = state["dependency_docs"]
    reviewer_suggestions = state["reviewer_suggestions"]

    #print(f"deps for {file}: {deps}")

    dependency_context = (
        "\n\n".join(
            f"[Dependency Documentation]\n{doc}"
            for doc in deps_docs
        )
        if deps_docs
        else "None"
    )

    code_context = "\n".join(code)

    # KEY IMPROVEMENT: Structured output preserves more information
    prompt = f"""
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

    response = llm.generate(prompt)
    
    # Parse structured response
    try:
        doc_data = parse_doc_json(response)
        
        # Store both structured and formatted versions
        state["draft_doc"] = format_structured_doc(file, doc_data)
    except ValueError as e:
        # Fallback: store raw response if JSON parsing fails
        print(f"⚠️ Failed to parse structured doc: {e}")
        state["draft_doc"] = f"Module Documentation for {file}:\n{response}\n"

    return state


def folder_write(analyzer, final_docs, output_file: str = "output.txt"):
    """Generate folder-level documentation from module docs"""
    print("\nGenerating folder-level LLM prompts...\n")
    folder_prompts = generate_llm_prompts(analyzer, final_docs)
    
    folder_docs = {}
    
    for prompt_data in folder_prompts:
        folder_path = prompt_data['folder']
        prompt = prompt_data['prompt']
        
        print(f"Generating description for folder: {folder_path}")
        description = llm.generate(prompt)
        folder_docs[folder_path] = description
        print(f"✓ {folder_path}\n")

    with open(output_file, "w") as f:
        f.write(folder_docs)
    
    return folder_docs


def condenser_write(analyzer, final_docs, folder_docs, output_file: str = "DOCUMENTATION.md"):
    """Condense all documentation into a comprehensive markdown file"""
    print(f"\n🔄 Condensing all documentation into {output_file}...\n")
    
    # Get folder structure for context
    from layer1.grouper import FolderProcessor
    processor = FolderProcessor(analyzer)
    folder_structure = processor.get_folder_structure_str(include_modules=True)
    
    # Format all module documentation
    module_docs_text = "\n".join(final_docs.values())
    
    # Format all folder documentation
    folder_docs_text = "\n".join([
        f"### {folder_path}\n{description}"
        for folder_path, description in folder_docs.items()
    ])
    
    # Design comprehensive prompt for final condensing
    prompt = f"""
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

    print("Generating comprehensive GitHub-style documentation...")
    condensed_doc = llm.generate(prompt)
    
    # Save to file
    with open(output_file, "w") as f:
        f.write(condensed_doc)
    
    print(f"✓ Comprehensive documentation saved to {output_file}")
    return condensed_doc

