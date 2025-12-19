from .schemas import AgentState
from .llmprovider import LLMProvider

llm = LLMProvider()

def write(state: AgentState) -> AgentState:
    print("✍️ Writer running")

    file = state["file"]
    code = state["code_chunks"]
    deps = state["dependencies"]
    deps_docs = state["dependency_docs"]

    #print(f"Check code if loaded properly:\n{code}\n")
    #print(f"Check dependencies if loaded properly:\n{deps}\n")
    #print(f"Check dependencies docs if loaded properly:\n")
    #for d in deps_docs:
    #    print(d)

    


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
You are an automated documentation agent.

Your task is to write a **concise, accurate, module-level documentation**
for the file **{file}**.

Rules:
- Do NOT re-document functionality already covered by dependencies.
- Assume dependency documentation is correct and authoritative.
- Focus on this module's responsibility and how it interacts with dependencies.
- Do NOT invent behavior not present in the code.

Dependencies (imported modules):
{deps if deps else "None"}

Dependency Documentation (for context only):
{dependency_context}

Source Code:
python
{code_context}

Write a clear module-level description in 3–6 sentences.
"""

    print(f"📝 Writer prompt:\n{prompt}\n")

    response = llm.generate(prompt)

    print(f"📝 Writer response:\n{response}\n")

    state["draft_doc"] = f"""

Module Documentation for {file}:
{response}

"""







    return state
