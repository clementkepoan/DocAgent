"""SCC (Strongly Connected Component) context generation and management."""

import asyncio
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from layer2.schemas.agent_state import AgentState
from layer2.services.code_retriever import retrieve
from layer2.module_pipeline.writer import scc_context_write

if TYPE_CHECKING:
    from config import DocGenConfig


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
        print(f"\n  📖 Generating SCC overview for {len(scc)} modules...")

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
            code_chunks_dict[module] = "\n".join(state["code_chunks"])

        # Generate SCC overview with retry logic
        max_retries = self.config.processing.scc_max_retries
        llm_config = self.config.llm
        for attempt in range(max_retries):
            try:
                async with self.semaphore:
                    context = await scc_context_write(scc_list, code_chunks_dict, llm_config=llm_config)
                print(f"  ✓ SCC overview generated")
                return context
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  ⚠️  SCC overview generation failed (attempt {attempt + 1}/{max_retries}): {str(e)[:80]}")
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