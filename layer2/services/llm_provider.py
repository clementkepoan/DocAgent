import os
import asyncio
from openai import AsyncOpenAI, OpenAI
from dotenv import load_dotenv
from typing import Dict, List, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from config import LLMConfig

load_dotenv()


class LLMProvider:
    def __init__(self, config: "LLMConfig" = None):
        if config is None:
            # Backward compatible: use defaults if no config provided
            from config import LLMConfig
            config = LLMConfig()

        self.api_key = config.api_key
        self.base_url = config.base_url
        self.chat_model = config.chat_model
        self.reasoner_model = config.reasoner_model
        self.temperature = config.temperature
        self.async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        self.sync_client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate(self, prompt: str) -> str:
        """Synchronous LLM call"""
        response = self.sync_client.chat.completions.create(
            model=self.chat_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )

        return response.choices[0].message.content

    async def generate_async(self, prompt: str) -> str:
        """Asynchronous LLM call for parallel processing"""
        response = await self.async_client.chat.completions.create(
            model=self.chat_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )

        return response.choices[0].message.content

    async def generate_with_reasoner_async(self, prompt: str) -> str:
        """
        Asynchronous LLM call using DeepSeek Reasoner model.
        Use this for complex tasks that benefit from chain-of-thought reasoning.

        Note: Reasoner model returns both reasoning_content and content.
        We return only the final content (answer), not the reasoning trace.
        """
        response = await self.async_client.chat.completions.create(
            model=self.reasoner_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )

        # DeepSeek Reasoner returns reasoning in reasoning_content and final answer in content
        return response.choices[0].message.content

    def generate_with_reasoner(self, prompt: str) -> str:
        """
        Synchronous LLM call using DeepSeek Reasoner model.
        Use this for complex tasks that benefit from chain-of-thought reasoning.
        """
        response = self.sync_client.chat.completions.create(
            model=self.reasoner_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
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
