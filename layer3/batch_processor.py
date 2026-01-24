"""Batch processing logic for parallel module documentation."""

import asyncio
import time
from typing import List, Dict, Optional, Set, TYPE_CHECKING
from tqdm import tqdm
from layer2.schemas.agent_state import AgentState
from layer2.services.code_retriever import retrieve
from layer2.module_pipeline.writer import module_write
from layer2.module_pipeline.reviewer import review
from layer3.progress_reporter import ProgressReporter

if TYPE_CHECKING:
    from config import DocGenConfig


class BatchProcessor:
    """Handles batch processing of modules with parallel execution."""

    def __init__(self, root_path: str, analyzer, semaphore: asyncio.Semaphore, config: "DocGenConfig" = None):
        # Load config if not provided
        if config is None:
            from config import DocGenConfig
            config = DocGenConfig()

        self.config = config
        self.root_path = root_path
        self.analyzer = analyzer
        self.semaphore = semaphore
        self.final_docs: Dict[str, str] = {}
        self.final_docs_lock = asyncio.Lock()
        self.failed_modules: List[tuple] = []
        self.dependency_usage_log: Dict = {}
    
    async def process_module(self, module: str, dependencies: List[str], 
                            dependency_docs: List[str], scc_context: Optional[str],
                            is_cyclic: bool, dependency_doc_sources: Dict[str, bool] = None) -> tuple:
        """Process a single module: retrieve -> write -> review."""
        
        try:
            # Initial state
            state: AgentState = {
                "file": module,
                "dependencies": dependencies,
                "code_chunks": [],
                "dependency_docs": dependency_docs,
                "draft_doc": None,
                "review_passed": False,
                "reviewer_suggestions": "",
                "retry_count": 0,
                "ROOT_PATH": self.root_path,
                "scc_context": scc_context,
                "is_cyclic": is_cyclic,
            }

            # Log dependency usage
            self.dependency_usage_log[module] = {
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                "dependencies": dependency_doc_sources if dependency_doc_sources else {dep: dep in self.final_docs for dep in dependencies}
            }
            
            # Get config values
            retrieve_timeout = self.config.processing.retrieve_timeout
            max_retries = self.config.processing.max_retries
            review_timeout = self.config.processing.review_timeout
            llm_config = self.config.llm

            # Retrieve code chunks
            retrieve_start = time.time()
            try:
                state = await asyncio.wait_for(asyncio.to_thread(retrieve, state), timeout=retrieve_timeout)
                state["last_retrieve_time"] = time.time() - retrieve_start
            except asyncio.TimeoutError:
                return (module, None, False, f"Retrieve timed out after {retrieve_timeout}s", {"retrieve": None, "write": None, "review": None})
            except Exception as e:
                return (module, None, False, f"Retrieve failed: {e}", {"retrieve": None, "write": None, "review": None})

            # Write documentation
            write_start = time.time()
            try:
                async with self.semaphore:
                    state = await module_write(state, llm_config=llm_config)
                state["last_write_time"] = time.time() - write_start
            except Exception as e:
                return (module, None, False, f"Write failed: {e}", {"retrieve": state.get("last_retrieve_time"), "write": None, "review": None})

            # Review documentation (skip if max_retries is 0)
            if max_retries > 0:
                try:
                    state = await review(state, llm_config=llm_config, timeout=review_timeout)
                except Exception as e:
                    return (module, None, False, f"Review failed: {e}", {"retrieve": state.get("last_retrieve_time"), "write": state.get("last_write_time"), "review": None})

            # Retry if needed
            retry_count = 0
            while max_retries > 0 and not state["review_passed"] and retry_count < max_retries:
                retry_count += 1
                state["retry_count"] = retry_count
                write_start = time.time()
                try:
                    async with self.semaphore:
                        state = await module_write(state, llm_config=llm_config)
                    state["last_write_time"] = time.time() - write_start
                except Exception as e:
                    return (module, None, False, f"Write retry failed: {e}", {"retrieve": state.get("last_retrieve_time"), "write": None, "review": None})
                try:
                    state = await review(state, llm_config=llm_config, timeout=review_timeout)
                except Exception as e:
                    return (module, None, False, f"Review retry failed: {e}", {"retrieve": state.get("last_retrieve_time"), "write": state.get("last_write_time"), "review": None})

            return (module, state["draft_doc"], True, None, {"retrieve": state.get("last_retrieve_time"), "write": state.get("last_write_time"), "review": state.get("last_review_time")})
        
        except Exception as e:
            return (module, None, False, str(e), {"retrieve": state.get("last_retrieve_time") if 'state' in locals() else None, "write": state.get("last_write_time") if 'state' in locals() else None, "review": state.get("last_review_time") if 'state' in locals() else None})
    
    async def process_batch(self, modules_to_process: List[str], batch_num: int, total_batches: int,
                           scc_contexts: Dict[str, str], reporter: ProgressReporter) -> None:
        """Process a batch of modules in parallel with progress bar."""
        
        reporter.print_batch_header(batch_num, total_batches, len(modules_to_process))
        
        # Create progress bar for this batch
        pbar = tqdm(total=len(modules_to_process), desc=f"  Batch {batch_num}", 
                   unit="module", ncols=80, leave=False, colour="blue")
        
        # Prepare all tasks
        tasks = {}
        skipped_packages = 0
        for module in modules_to_process:
            # Skip packages - they don't have corresponding .py files
            if module in self.analyzer.packages:
                skipped_packages += 1
                continue
            
            is_cyclic = self.analyzer.is_in_cycle(module)
            dependencies = self.analyzer.get_dependencies(module)
            
            # Gather dependency docs (should all be ready)
            dependency_docs = [
                self.final_docs[d] for d in dependencies 
                if d in self.final_docs
            ]
            
            scc_context = scc_contexts.get(module, None)
            dependency_doc_sources = {d: (d in self.final_docs) for d in dependencies}

            task = self.process_module(
                module=module,
                dependencies=dependencies,
                dependency_docs=dependency_docs,
                scc_context=scc_context,
                is_cyclic=is_cyclic,
                dependency_doc_sources=dependency_doc_sources
            )
            tasks[task] = module
        
        # Run all tasks concurrently with progress tracking
        success_count = 0
        for task in asyncio.as_completed(tasks.keys()):
            try:
                module, doc, success, error, timings = await task
                timing_str = reporter.format_timings(timings)

                if success and doc:
                    async with self.final_docs_lock:
                        self.final_docs[module] = doc
                    success_count += 1
                    pbar.update(1)
                    pbar.write(f"    ✓ {module}{timing_str}")
                else:
                    self.failed_modules.append((module, error or "Unknown error", 0, timings))
                    pbar.update(1)
                    pbar.write(f"    ✗ {module}: {error[:50] if error else 'Unknown error'}{timing_str}")
            except Exception as e:
                pbar.update(1)
                pbar.write(f"    ✗ Task error: {str(e)[:50]}")
        
        pbar.close()
        actual_processed = len(modules_to_process) - skipped_packages
        reporter.print_batch_complete(success_count, actual_processed, skipped_packages)
    
    def organize_batches(self, sorted_modules: List[str]) -> List[List[str]]:
        """Organize modules into batches by dependency depth."""
        batches = []
        processed = set()
        total_modules = len(sorted_modules)
        max_iterations = total_modules  # Safety check
        
        while len(processed) < total_modules and max_iterations > 0:
            max_iterations -= 1
            # Find all modules whose LOCAL dependencies are satisfied
            available = []
            for module in sorted_modules:
                if module in processed:
                    continue
                deps = self.analyzer.get_dependencies(module)
                # Check if all dependencies that are in this codebase are already processed
                local_deps = [d for d in deps if d in self.analyzer.module_index and d not in self.analyzer.packages]
                if all(d in processed for d in local_deps):
                    available.append(module)
            
            if not available:
                # Fallback: add all remaining unprocessed modules
                available = [m for m in sorted_modules if m not in processed]
                if available:
                    print(f"  ℹ️  Note: Processing {len(available)} remaining modules with potential external deps")
            
            if available:
                batches.append(available)
                processed.update(available)
        
        return batches