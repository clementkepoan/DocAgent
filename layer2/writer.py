from .schemas import AgentState
from .llmprovider import LLMProvider
from .prompt_router import get_module_documentation_prompt, get_condenser_documentation_prompt
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

    # Get prompt from centralized router
    prompt = get_module_documentation_prompt(
        file=file,
        deps=deps,
        dependency_context=dependency_context,
        code_context=code_context,
        reviewer_suggestions=reviewer_suggestions
    )

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
        json.dump(folder_docs, f, indent=2)
    
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
    
    # Get prompt from centralized router
    prompt = get_condenser_documentation_prompt(
        folder_structure=folder_structure,
        folder_docs_text=folder_docs_text,
        module_docs_text=module_docs_text
    )

    print("Generating comprehensive GitHub-style documentation...")
    condensed_doc = llm.generate(prompt)
    
    # Save to file
    with open(output_file, "w") as f:
        f.write(condensed_doc)
    
    print(f"✓ Comprehensive documentation saved to {output_file}")
    return condensed_doc

