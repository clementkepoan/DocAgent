"""SCC (Strongly Connected Component) context generation and management."""

import asyncio
import ast
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from layer2.schemas.agent_state import AgentState
from layer2.services.code_retriever import retrieve
from layer2.module_pipeline.writer import scc_context_write

if TYPE_CHECKING:
    from config import DocGenConfig


def _extract_api_signatures(code: str, max_chars: int = 2000) -> str:
    """Extract only class and function signatures from code (no bodies)."""
    try:
        tree = ast.parse(code)
        signatures = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                # Get class with method signatures only
                class_sig = f"class {node.name}:"
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        args = [a.arg for a in item.args.args][:5]
                        args_str = ', '.join(args)
                        if len(item.args.args) > 5:
                            args_str += ', ...'
                        methods.append(f"    def {item.name}({args_str}): ...")
                if methods:
                    class_sig += "\n" + "\n".join(methods[:15])  # Max 15 methods
                signatures.append(class_sig)

            elif isinstance(node, ast.FunctionDef):
                args = [a.arg for a in node.args.args][:6]
                args_str = ', '.join(args)
                if len(node.args.args) > 6:
                    args_str += ', ...'
                signatures.append(f"def {node.name}({args_str}): ...")

        result = "\n\n".join(signatures)
        if len(result) > max_chars:
            result = result[:max_chars] + "\n... [signatures truncated]"
        return result if result else code[:max_chars]
    except:
        # If AST parsing fails, return truncated code
        return code[:max_chars]


class SCCManager:
    """Manages SCC context generation for cyclic dependencies."""

    def __init__(self, root_path: str, semaphore: asyncio.Semaphore, config: "DocGenConfig" = None):
        # Load config if not provided
        if config is None:
            from config import DocGenConfig
            config = DocGenConfig()

        self.config = config
        self.root_path = root_path
        self.semaphore = semaphore
        self.scc_contexts_dict: Dict[str, str] = {}
    
    async def generate_scc_context(self, scc: Set[str]) -> Optional[str]:
        """Generate SCC context doc for cycles."""
        if len(scc) == 1:
            return None  # No context needed for independent modules

        scc_list = sorted(scc)
        scc_size = len(scc)
        print(f"\n  📖 Generating SCC overview for {scc_size} modules...")

        # Calculate per-module character limit based on SCC size
        # Target ~60K total chars to stay within context window
        MAX_TOTAL_CHARS = 60000
        chars_per_module = MAX_TOTAL_CHARS // scc_size

        # For very large SCCs, use API signatures only (not full code)
        use_signatures_only = scc_size > 15
        if use_signatures_only:
            chars_per_module = min(chars_per_module, 2000)  # Signatures are compact
            print(f"    (Very large SCC: using API signatures only, {chars_per_module} chars/module)")
        elif scc_size > 10:
            chars_per_module = min(chars_per_module, 3000)  # Max 3KB per module for medium SCCs
            print(f"    (Medium SCC: limiting to {chars_per_module} chars/module)")

        # Retrieve code chunks for all modules in SCC
        code_chunks_dict = {}
        for module in scc_list:
            state: AgentState = {
                "file": module,
                "dependencies": [],
                "code_chunks": [],
                "dependency_docs": [],
                "draft_doc": None,
                "review_passed": False,
                "reviewer_suggestions": "",
                "retry_count": 0,
                "ROOT_PATH": self.root_path,
                "scc_context": None,
                "is_cyclic": True,
            }
            state = retrieve(state)
            code_content = "\n".join(state["code_chunks"])

            # For very large SCCs, extract only API signatures
            if use_signatures_only:
                code_content = _extract_api_signatures(code_content, chars_per_module)
            elif len(code_content) > chars_per_module:
                # Truncate if necessary
                code_content = code_content[:chars_per_module] + f"\n\n... [truncated, {len(code_content) - chars_per_module} chars omitted]"

            code_chunks_dict[module] = code_content

        # Generate SCC overview with retry logic
        max_retries = self.config.processing.scc_max_retries
        llm_config = self.config.llm
        current_code_chunks = code_chunks_dict.copy()

        for attempt in range(max_retries):
            try:
                async with self.semaphore:
                    context = await scc_context_write(scc_list, current_code_chunks, llm_config=llm_config)
                print(f"  ✓ SCC overview generated")
                return context
            except Exception as e:
                error_msg = str(e)
                is_context_error = "context length" in error_msg.lower() or "maximum" in error_msg.lower()

                if attempt < max_retries - 1:
                    print(f"  ⚠️  SCC overview generation failed (attempt {attempt + 1}/{max_retries}): {error_msg[:80]}")

                    # If context length error, aggressively truncate for retry
                    if is_context_error:
                        print(f"    → Reducing context size for retry...")
                        truncate_factor = 0.5 ** (attempt + 1)  # 50%, 25%, 12.5%...
                        for module in current_code_chunks:
                            content = current_code_chunks[module]
                            max_len = int(len(content) * truncate_factor)
                            if max_len < 500:
                                max_len = 500  # Minimum 500 chars
                            current_code_chunks[module] = _extract_api_signatures(content, max_len)

                    await asyncio.sleep(2 ** attempt)
                else:
                    print(f"  ❌ SCC overview generation failed after {max_retries} attempts")
                    return None
    
    async def generate_all_scc_contexts(self, sccs: List[Set[str]]) -> Dict[str, str]:
        """Pre-generate all SCC contexts and return module -> context mapping."""
        print("📖 Pre-generating cycle architecture docs...")
        scc_contexts: Dict[str, str] = {}
        cycles = [scc for scc in sccs if len(scc) > 1]
        
        for cycle in cycles:
            context = await self.generate_scc_context(cycle)
            if context:
                for module in cycle:
                    scc_contexts[module] = context
                self.scc_contexts_dict[f"cycle_{len(self.scc_contexts_dict)+1}"] = context
        
        print(f"✓ Generated {len(cycles)} cycle contexts\n")
        return scc_contexts
    
    def get_all_contexts(self) -> Dict[str, str]:
        """Get all generated SCC contexts."""
        return self.scc_contexts_dict