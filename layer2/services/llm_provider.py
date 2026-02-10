import os
import asyncio
from openai import AsyncOpenAI, OpenAI
from dotenv import load_dotenv
from typing import Dict, List, Callable, Optional, Any, TYPE_CHECKING
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

        # Load RAG config for max iterations
        from config import get_config
        self._rag_config = get_config().rag

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

    async def generate_with_tools_async(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        tool_handler: Callable,
        max_iterations: int = None
    ) -> str:
        """
        Agentic generation with tool calling support.

        KEY FIX for infinite loop bug:
        - If LLM returns text (no tool_call) → DONE (return content)
        - If LLM returns tool_call → execute, add result, continue loop
        - Max iterations as safety net

        Args:
            messages: Conversation messages (system + user)
            tools: List of tool definitions (OpenAI format)
            tool_handler: Async callable that takes tool_call and returns result string
            max_iterations: Maximum agentic turns. Defaults to settings.

        Returns:
            Final text response from LLM
        """
        if max_iterations is None:
            max_iterations = self._rag_config.max_tool_iterations

        # Work with a copy to avoid mutating original
        working_messages = list(messages)

        for iteration in range(max_iterations):
            try:
                response = await self.async_client.chat.completions.create(
                    model=self.chat_model,
                    messages=working_messages,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None,
                    temperature=self.temperature
                )

                message = response.choices[0].message

                # Check for tool calls
                if message.tool_calls:
                    # LLM wants to call tools - execute them
                    working_messages.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })

                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        try:
                            result = await tool_handler(tool_call)
                        except Exception as e:
                            result = f"Tool execution error: {str(e)}"

                        working_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result
                        })

                    # Continue loop - LLM will process tool results
                    continue

                else:
                    # No tool call = final answer
                    # This is the KEY fix: text response means we're done
                    return message.content or ""

            except Exception as e:
                # On error, try to return last assistant message or error
                for msg in reversed(working_messages):
                    if msg.get("role") == "assistant" and msg.get("content"):
                        return msg["content"]
                return f"Generation error: {str(e)}"

        # Safety: max iterations reached
        # Try to get last meaningful content
        for msg in reversed(working_messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                return msg["content"]
            if msg.get("role") == "tool" and msg.get("content"):
                # Last resort: return tool results as context indication
                return f"[Max iterations reached. Last tool result:]\n{msg['content'][:1000]}"

        return "[Max tool iterations reached without final response]"

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
