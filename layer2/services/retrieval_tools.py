"""Tool definitions and executor for adaptive RAG retrieval."""

from typing import List, Dict, Any, Optional
import json


# Tool definitions for DeepSeek function calling
RETRIEVAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_function_details",
            "description": "Get full source code and documentation for a specific function from a module",
            "parameters": {
                "type": "object",
                "properties": {
                    "module": {
                        "type": "string",
                        "description": "Module name (e.g., 'layer1.parser' or 'layer2.services.llm_provider')"
                    },
                    "function_name": {
                        "type": "string",
                        "description": "Function name to retrieve (e.g., 'parse_file' or 'generate_async')"
                    }
                },
                "required": ["module", "function_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_class_details",
            "description": "Get full source code, methods, and documentation for a specific class from a module",
            "parameters": {
                "type": "object",
                "properties": {
                    "module": {
                        "type": "string",
                        "description": "Module name (e.g., 'layer1.parser' or 'layer2.services.llm_provider')"
                    },
                    "class_name": {
                        "type": "string",
                        "description": "Class name to retrieve (e.g., 'ImportGraph' or 'LLMProvider')"
                    }
                },
                "required": ["module", "class_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_module_overview",
            "description": "Get overview of a module including key functions and classes",
            "parameters": {
                "type": "object",
                "properties": {
                    "module": {
                        "type": "string",
                        "description": "Module name to get overview for (e.g., 'layer1.parser')"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of top chunks to retrieve (default: 5)",
                        "default": 5
                    }
                },
                "required": ["module"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_usage_patterns",
            "description": "Find where a function or class is used in other parts of the codebase",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Function or class name to search for (e.g., 'parse_file' or 'ImportGraph')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of usage examples to return (default: 3)",
                        "default": 3
                    }
                },
                "required": ["entity_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_dependency_exports",
            "description": "Get main exports and public API from a dependency module",
            "parameters": {
                "type": "object",
                "properties": {
                    "dependency_module": {
                        "type": "string",
                        "description": "Dependency module name (e.g., 'layer2.services.llm_provider')"
                    }
                },
                "required": ["dependency_module"]
            }
        }
    }
]


class RetrievalToolExecutor:
    """Execute tool calls by delegating to RAG service."""

    def __init__(self, rag_service):
        """
        Initialize tool executor.

        Args:
            rag_service: RAGService instance for executing retrievals
        """
        self.rag = rag_service

    async def execute_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> str:
        """
        Execute a tool call and return formatted results.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments from LLM function call

        Returns:
            Formatted string with retrieval results
        """
        try:
            if tool_name == "get_function_details":
                return await self._get_function_details(
                    arguments["module"],
                    arguments["function_name"]
                )

            elif tool_name == "get_class_details":
                return await self._get_class_details(
                    arguments["module"],
                    arguments["class_name"]
                )

            elif tool_name == "get_module_overview":
                return await self._get_module_overview(
                    arguments["module"],
                    arguments.get("top_k", 5)
                )

            elif tool_name == "find_usage_patterns":
                return await self._find_usage_patterns(
                    arguments["entity_name"],
                    arguments.get("limit", 3)
                )

            elif tool_name == "get_dependency_exports":
                return await self._get_dependency_exports(
                    arguments["dependency_module"]
                )

            else:
                return f"Error: Unknown tool '{tool_name}'"

        except Exception as e:
            # Return error in a format the LLM can understand
            return f"Error executing {tool_name}: {str(e)}"

    async def _get_function_details(
        self,
        module: str,
        function_name: str
    ) -> str:
        """Retrieve and format function details."""
        results = self.rag.retrieve_by_entity_name(
            module=module,
            entity_name=function_name,
            entity_type="function"
        )

        if not results:
            return f"No function named '{function_name}' found in module '{module}'"

        # Format results
        return self._format_function_results(results, module, function_name)

    async def _get_class_details(
        self,
        module: str,
        class_name: str
    ) -> str:
        """Retrieve and format class details."""
        results = self.rag.retrieve_by_entity_name(
            module=module,
            entity_name=class_name,
            entity_type="class"
        )

        if not results:
            return f"No class named '{class_name}' found in module '{module}'"

        # Format results
        return self._format_class_results(results, module, class_name)

    async def _get_module_overview(
        self,
        module: str,
        top_k: int
    ) -> str:
        """Retrieve and format module overview."""
        results = self.rag.retrieve_module_top_k(module=module, top_k=top_k)

        if not results:
            return f"No chunks found for module '{module}'"

        # Format results
        return self._format_overview_results(results, module)

    async def _find_usage_patterns(
        self,
        entity_name: str,
        limit: int
    ) -> str:
        """Retrieve and format usage patterns."""
        results = self.rag.retrieve_usage_patterns(
            entity_name=entity_name,
            limit=limit
        )

        if not results:
            return f"No usage patterns found for '{entity_name}'"

        # Format results
        return self._format_usage_results(results, entity_name)

    async def _get_dependency_exports(
        self,
        dependency_module: str
    ) -> str:
        """Retrieve and format dependency exports."""
        results = self.rag.retrieve_dependency_context(
            dependency_name=dependency_module
        )

        if not results:
            return f"No exports found for dependency '{dependency_module}'"

        # Format results
        return self._format_exports_results(results, dependency_module)

    def _format_function_results(
        self,
        results: List[Dict[str, Any]],
        module: str,
        function_name: str
    ) -> str:
        """Format function retrieval results for LLM consumption."""
        output = [f"Function: `{function_name}` in module `{module}`\n"]

        for i, result in enumerate(results, 1):
            output.append(f"## Definition {i}")
            output.append(f"File: {result['file_path']}:{result['start_line']}-{result['end_line']}")

            if result.get("enriched_text"):
                output.append(f"Purpose: {result['enriched_text']}")

            output.append("```python")
            output.append(result["code"])
            output.append("```")
            output.append("")

        return "\n".join(output)

    def _format_class_results(
        self,
        results: List[Dict[str, Any]],
        module: str,
        class_name: str
    ) -> str:
        """Format class retrieval results for LLM consumption."""
        output = [f"Class: `{class_name}` in module `{module}`\n"]

        for i, result in enumerate(results, 1):
            output.append(f"## Definition {i}")
            output.append(f"File: {result['file_path']}:{result['start_line']}-{result['end_line']}")

            if result.get("enriched_text"):
                output.append(f"Purpose: {result['enriched_text']}")

            output.append("```python")
            output.append(result["code"])
            output.append("```")
            output.append("")

        return "\n".join(output)

    def _format_overview_results(
        self,
        results: List[Dict[str, Any]],
        module: str
    ) -> str:
        """Format module overview results for LLM consumption."""
        output = [f"Module Overview: `{module}`\n"]
        output.append(f"Found {len(results)} key entities:\n")

        for i, result in enumerate(results, 1):
            output.append(f"### {i}. `{result['name']}` ({result['entity_type']})")
            output.append(f"   Location: {result['file_path']}:{result['start_line']}-{result['end_line']}")

            if result.get("enriched_text"):
                # Truncate long enriched text
                enriched = result['enriched_text'][:200]
                if len(result['enriched_text']) > 200:
                    enriched += "..."
                output.append(f"   Purpose: {enriched}")

            # Show code preview (first 300 chars)
            code_preview = result["code"][:300]
            if len(result["code"]) > 300:
                code_preview += "\n# ... (truncated)"
            output.append(f"```python")
            output.append(code_preview)
            output.append(f"```")
            output.append("")

        return "\n".join(output)

    def _format_usage_results(
        self,
        results: List[Dict[str, Any]],
        entity_name: str
    ) -> str:
        """Format usage pattern results for LLM consumption."""
        output = [f"Usage Patterns for `{entity_name}`\n"]
        output.append(f"Found {len(results)} usage examples:\n")

        for i, result in enumerate(results, 1):
            output.append(f"### Usage {i}")
            output.append(f"   Location: {result['file_path']}:{result['start_line']}-{result['end_line']}")
            output.append(f"   In: `{result['name']}` ({result['entity_type']})")

            # Show code snippet
            code_snippet = result["code"][:400]
            if len(result["code"]) > 400:
                code_snippet += "\n# ... (truncated)"
            output.append(f"```python")
            output.append(code_snippet)
            output.append(f"```")
            output.append("")

        return "\n".join(output)

    def _format_exports_results(
        self,
        results: List[Dict[str, Any]],
        dependency_module: str
    ) -> str:
        """Format dependency exports for LLM consumption."""
        output = [f"Public API of `{dependency_module}`\n"]
        output.append(f"Found {len(results)} main exports:\n")

        for i, result in enumerate(results, 1):
            output.append(f"### Export {i}: `{result['name']}` ({result['entity_type']})")
            output.append(f"   Location: {result['file_path']}:{result['start_line']}-{result['end_line']}")

            if result.get("enriched_text"):
                enriched = result['enriched_text'][:200]
                if len(result['enriched_text']) > 200:
                    enriched += "..."
                output.append(f"   Purpose: {enriched}")

            # Show code preview
            code_preview = result["code"][:300]
            if len(result["code"]) > 300:
                code_preview += "\n# ... (truncated)"
            output.append(f"```python")
            output.append(code_preview)
            output.append(f"```")
            output.append("")

        return "\n".join(output)
