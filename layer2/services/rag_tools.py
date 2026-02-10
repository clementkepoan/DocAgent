"""
RAG Tools for Agentic Documentation Generation
===============================================

Provides tool definitions and handlers for LLM tool calling.
The LLM can call search_codebase to get more context during section generation.

Key Fix for Infinite Loop Bug:
- Clear termination: text response = final answer
- Tool call = execute and continue
- Max iterations as safety net
"""

import json
from typing import List, Dict, Any, Callable, Optional
from layer1.parent_child_retriever import ParentChildRetriever, RAGResult
from config import get_config


# Tool definition for OpenAI-compatible API
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_codebase",
        "description": (
            "Search for relevant code and documentation in the codebase. "
            "Use when you need more context about a specific concept, function, module, or pattern. "
            "Returns module documentation and relevant code snippets."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural language query describing what to search for. "
                        "Examples: 'dependency analysis', 'how does parsing work', "
                        "'batch processing logic', 'LLM provider implementation'"
                    )
                }
            },
            "required": ["query"]
        }
    }
}


# Phase 1 exploration prompt for hybrid RAG + Reasoner mode
EXPLORATION_SYSTEM_PROMPT = """
## Phase 1: Context Gathering Mode

You are gathering context from a codebase to write documentation.
Your job is to search for relevant modules, code, and documentation using the search_codebase tool.

**Your task:**
1. Make 2-4 targeted searches based on the section's purpose and requirements
2. Focus on finding code examples, API details, and relevant module documentation
3. DO NOT write the final documentation - just gather context

**Search strategy:**
- Search for key concepts mentioned in the section purpose
- Look for related modules and their implementations
- Find code patterns and examples that support the section

After gathering enough context, stop making tool calls. Your search results will be passed to a synthesis phase.
"""


def get_exploration_system_prompt() -> str:
    """Get the Phase 1 exploration system prompt."""
    return EXPLORATION_SYSTEM_PROMPT


def get_exploration_prompt(section: dict, base_context: str, plan_context: str) -> str:
    """
    Generate Phase 1 exploration prompt for hybrid mode.

    Args:
        section: Section being generated (title, purpose, style, required_context)
        base_context: Static context already gathered
        plan_context: Overall plan context (project type, audience)

    Returns:
        User prompt for Phase 1 context gathering
    """
    return f"""## Section to Write
**Title:** {section.get('title', 'Untitled')}
**Purpose:** {section.get('purpose', 'No purpose specified')}
**Style:** {section.get('style', 'narrative')}
**Required Context:** {section.get('required_context', [])}

## Plan Context
{plan_context}

## Base Context Already Available
{base_context[:3000] if len(base_context) > 3000 else base_context}

---

Now use the search_codebase tool to gather additional context needed for this section.
Focus on finding:
1. Relevant source code and implementations
2. Module documentation
3. Code patterns and examples

Make 2-4 targeted searches, then stop."""


# System prompt addition for agentic section generation
AGENTIC_SYSTEM_PROMPT_ADDITION = """

## Using the search_codebase Tool

You have access to a `search_codebase` tool that can retrieve relevant code and documentation from the codebase.

**When to use it:**
- When the provided context is insufficient for the section you're writing
- When you need specific implementation details not in the initial context
- When referencing a concept, pattern, or module you want to verify

**Important guidelines:**
1. Use the tool sparingly - only when necessary
2. After receiving search results, you MUST produce your final documentation
3. Do NOT call search_codebase repeatedly unless the results were clearly insufficient
4. Your response after receiving tool results should be the documentation content, not another tool call

**Termination rule:** Once you have sufficient context (either from initial context or from search results), generate your final documentation output directly without further tool calls.
"""


class RAGToolHandler:
    """
    Handles RAG tool execution for agentic generation.

    Maintains retriever instance and provides async tool execution.
    """

    def __init__(self, retriever: Optional[ParentChildRetriever] = None):
        """
        Initialize tool handler.

        Args:
            retriever: ParentChildRetriever instance. Created if None.
        """
        self._retriever = retriever
        self._retriever_initialized = retriever is not None

    @property
    def retriever(self) -> ParentChildRetriever:
        """Lazy initialization of retriever."""
        if not self._retriever_initialized:
            self._retriever = ParentChildRetriever()
            self._retriever_initialized = True
        return self._retriever

    async def execute_search_tool(self, query: str) -> str:
        """
        Execute search_codebase tool and format results for LLM.

        Args:
            query: Search query from LLM tool call

        Returns:
            Formatted context string for LLM consumption
        """
        try:
            config = get_config()
            results = await self.retriever.retrieve(
                query=query,
                top_k_parents=config.rag.top_k_parents,
                top_k_children=config.rag.top_k_children
            )

            if not results:
                return f"No relevant modules or code found for query: '{query}'"

            # Format results for LLM
            formatted_parts = []
            for result in results:
                formatted_parts.append(result.to_context_string(
                    max_chunks=config.rag.top_k_children,
                    include_code=True
                ))

            return "\n\n---\n\n".join(formatted_parts)

        except Exception as e:
            return f"Search error: {str(e)}"

    async def handle_tool_call(self, tool_call) -> str:
        """
        Handle a tool call from LLM response.

        Args:
            tool_call: Tool call object from OpenAI response

        Returns:
            Tool execution result as string
        """
        function_name = tool_call.function.name

        if function_name == "search_codebase":
            try:
                args = json.loads(tool_call.function.arguments)
                query = args.get("query", "")
                if not query:
                    return "Error: search_codebase requires a 'query' parameter"
                return await self.execute_search_tool(query)
            except json.JSONDecodeError:
                return "Error: Invalid JSON in tool arguments"
        else:
            return f"Unknown tool: {function_name}"


def get_rag_tools() -> List[Dict[str, Any]]:
    """Get list of RAG tool definitions for LLM."""
    return [SEARCH_TOOL]


def get_agentic_system_prompt(base_prompt: str) -> str:
    """
    Combine base system prompt with agentic tool instructions.

    Args:
        base_prompt: Original system prompt for section generation

    Returns:
        Enhanced prompt with tool usage instructions
    """
    return base_prompt + AGENTIC_SYSTEM_PROMPT_ADDITION


async def execute_rag_search(query: str, retriever: Optional[ParentChildRetriever] = None) -> str:
    """
    Convenience function for direct RAG search.

    Args:
        query: Search query
        retriever: Optional retriever instance

    Returns:
        Formatted context string
    """
    handler = RAGToolHandler(retriever)
    return await handler.execute_search_tool(query)


def parse_rag_context_requests(required_context: List[str]) -> List[str]:
    """
    Extract RAG queries from required_context list.

    Looks for entries prefixed with "rag:" and returns the queries.

    Args:
        required_context: List of context requirements

    Returns:
        List of RAG queries to execute
    """
    rag_queries = []
    for ctx in required_context:
        if ctx.startswith("rag:"):
            query = ctx[4:].strip()
            if query:
                rag_queries.append(query)
    return rag_queries


async def prefetch_rag_context(
    required_context: List[str],
    retriever: Optional[ParentChildRetriever] = None
) -> Dict[str, str]:
    """
    Pre-fetch RAG context for all rag: prefixed requirements.

    Args:
        required_context: List of context requirements
        retriever: Optional retriever instance

    Returns:
        Dict mapping queries to their results
    """
    queries = parse_rag_context_requests(required_context)
    if not queries:
        return {}

    handler = RAGToolHandler(retriever)
    results = {}

    for query in queries:
        result = await handler.execute_search_tool(query)
        results[query] = result

    return results
