from .schemas import AgentState
from .llmprovider import LLMProvider

llm = LLMProvider()

def write(state: AgentState) -> AgentState:
    print("✍️ Writer running")

    file = state["file"]
    code = state["code_chunks"]
    deps = state["dependencies"]
    deps_docs = state["dependency_docs"]
    reviewer_suggestions = state["reviewer_suggestions"]

    #print(f"Check code if loaded properly:\n{code}\n")
    print(f"Check dependencies if loaded properly:\n{deps}\n")
    print(f"Check dependencies docs if loaded properly:\n")
    for d in deps_docs:
        print(d)

    


    dependency_context = (
        "\n\n".join(
            f"[Dependency Documentation]\n{doc}"
            for doc in deps_docs
    )
        if deps_docs
        else "None"
    )

    code_context = "\n".join(code)

    prompt = f"""
You are an automated documentation agent for a module or a function.

Your task is to write a **concise, accurate, module-level documentation**
for the file **{file}**.

Rules:
- Do NOT re-document functionality already covered by dependencies.
- Assume dependency documentation is always correct and authoritative.
- Focus on this module's responsibility and how it interacts with dependencies.
- Do NOT invent behavior not present in the code.
- If reviewer suggestion is present, use it to improve the documentation.

Dependencies (imported modules):
{deps if deps else "None"}

Dependency Documentation (for context only):
{dependency_context}

Source Code:
Language: python
{code_context}

Reviewer Suggestion:
{reviewer_suggestions}

Write a clear module-level description in 4-5 sentences.
"""

    #print(f"📝 Writer prompt:\n{prompt}\n")
    print(f"Reviewer Suggestions in writer: \n {reviewer_suggestions}")

    response = llm.generate(prompt)

    print(f"📝 Writer response:\n{response}\n")

    state["draft_doc"] = f"""
Module Documentation for {file}:
{response}

"""

    return state
