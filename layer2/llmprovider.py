import os
import asyncio
from openai import AsyncOpenAI, OpenAI
from dotenv import load_dotenv
from typing import Dict, List
import json



load_dotenv()


class LLMProvider:
    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_KEY")
        self.base_url = "https://api.deepseek.com"
        self.async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)  # Reuse!
        self.sync_client = OpenAI(api_key=self.api_key, base_url=self.base_url)        # Reuse!
    
    def generate(self, prompt: str) -> str:
        """Synchronous LLM call"""
        response = self.sync_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content
    
    async def generate_async(self, prompt: str) -> str:
        """Asynchronous LLM call for parallel processing"""
        response = await self.async_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content

    def generate_scc_overview(self, scc_modules: List[str], code_chunks_dict: Dict[str, str]) -> str:
        """
        Generate a high-level coherence overview for a strongly connected component (cycle).
        
        Args:
            scc_modules: List of module names in the cycle
            code_chunks_dict: Dict mapping module names to their source code
            
        Returns:
            High-level overview doc explaining the cycle's collective responsibility and patterns
        """
        # Build code context
        code_context = "\n\n".join([
            f"=== Module: {mod} ===\n{code_chunks_dict.get(mod, '(source not available)')}"
            for mod in scc_modules
        ])

        prompt = f"""
You are analyzing a circular dependency group in a Python codebase.

MODULES IN CYCLE: {', '.join(scc_modules)}

SOURCE CODE:
{code_context}

TASK
====
Analyze these mutually-dependent modules and generate a high-level ARCHITECTURE OVERVIEW document.

Your overview should:
1. Identify the collective responsibility of this module group
2. Explain the interdependency pattern (why they depend on each other)
3. Describe key abstractions or patterns that emerge from the cycle
4. Note which modules are "entry points" vs "utilities"
5. Flag any architectural concerns (tight coupling, unclear boundaries)

OUTPUT FORMAT
=============
Return a JSON object with EXACTLY this schema:

{{
  "cycle_pattern": "Brief name of the dependency pattern (e.g., 'Mutual Registry Pattern')",
  "collective_responsibility": "What this group does as a whole",
  "interdependency_explanation": "Why these modules depend on each other",
  "key_abstractions": ["abstraction1", "abstraction2"],
  "entry_points": ["module1", "module2"],
  "utilities": ["module3"],
  "architectural_concerns": ["concern1", "concern2"] or [],
  "summary": "2-3 sentence overview that other modules can use for context"
}}

Guidelines:
- Be concise but informative
- Focus on architectural patterns, not implementation details
- Explain the "why" behind the circular dependency
- The summary should be usable as context for documenting individual modules

Ensure the JSON is well-formed and parsable.
"""
        return self.generate(prompt)
    
    async def generate_scc_overview_async(self, scc_modules: List[str], code_chunks_dict: Dict[str, str]) -> str:
        """
        Async version of generate_scc_overview for parallel processing.
        
        Args:
            scc_modules: List of module names in the cycle
            code_chunks_dict: Dict mapping module names to their source code
            
        Returns:
            High-level overview doc explaining the cycle's collective responsibility and patterns
        """
        # Build code context
        code_context = "\n\n".join([
            f"=== Module: {mod} ===\n{code_chunks_dict.get(mod, '(source not available)')}"
            for mod in scc_modules
        ])

        prompt = f"""
You are analyzing a circular dependency group in a Python codebase.

MODULES IN CYCLE: {', '.join(scc_modules)}

SOURCE CODE:
{code_context}

TASK
====
Analyze these mutually-dependent modules and generate a high-level ARCHITECTURE OVERVIEW document.

Your overview should:
1. Identify the collective responsibility of this module group
2. Explain the interdependency pattern (why they depend on each other)
3. Describe key abstractions or patterns that emerge from the cycle
4. Note which modules are "entry points" vs "utilities"
5. Flag any architectural concerns (tight coupling, unclear boundaries)

OUTPUT FORMAT
=============
Return a JSON object with EXACTLY this schema:

{{
  "cycle_pattern": "Brief name of the dependency pattern (e.g., 'Mutual Registry Pattern')",
  "collective_responsibility": "What this group does as a whole",
  "interdependency_explanation": "Why these modules depend on each other",
  "key_abstractions": ["abstraction1", "abstraction2"],
  "entry_points": ["module1", "module2"],
  "utilities": ["module3"],
  "architectural_concerns": ["concern1", "concern2"] or [],
  "summary": "2-3 sentence overview that other modules can use for context"
}}

Guidelines:
- Be concise but informative
- Focus on architectural patterns, not implementation details
- Explain the "why" behind the circular dependency
- The summary should be usable as context for documenting individual modules

Ensure the JSON is well-formed and parsable.
"""
        return await self.generate_async(prompt)







