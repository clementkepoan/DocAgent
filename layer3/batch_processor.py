"""Batch processing logic for parallel module documentation."""

import asyncio
import time
from typing import List, Dict, Optional, Set, TYPE_CHECKING
from tqdm import tqdm
from layer2.schemas.agent_state import AgentState
from layer2.services.code_retriever import retrieve
from layer2.module_pipeline.writer import module_write, module_write_adaptive
from layer2.module_pipeline.reviewer import review, review_adaptive
from layer3.progress_reporter import ProgressReporter
from layer3.rag_usage_tracker import RAGUsageTracker

if TYPE_CHECKING:
    from config import DocGenConfig
    from layer2.services.rag_retriever import RAGService
    from layer2.services.retrieval_tools import RetrievalToolExecutor


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
        self.rag_service: Optional["RAGService"] = None  # Set by AsyncDocGenerator if RAG enabled
        self.rag_tracker: Optional[RAGUsageTracker] = None  # Set by AsyncDocGenerator if RAG enabled
    
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
                "rag_context": None,  # Will be populated if RAG enabled
                "expanded_context": None,  # From adaptive retries
                "tool_calls_made": 0,  # Track adaptive iterations
                "initial_entities": None,  # Entity names for adaptive querying
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

            # Check if adaptive RAG is enabled
            adaptive_rag_enabled = self.config.generation.enable_adaptive_rag
            use_adaptive = adaptive_rag_enabled and self.rag_service is not None

            # RAG retrieval (primary or supplementary depending on mode)
            if self.rag_service is not None:
                try:
                    from layer2.services.rag_retriever import rag_retrieve

                    # For adaptive mode, we still need code_chunks for entity extraction
                    # But we'll do a lighter retrieval
                    if use_adaptive:
                        # In adaptive mode, do a minimal AST retrieval for entity list only
                        # This is temporary - will be removed in future pure-RAG version
                        try:
                            state = await asyncio.wait_for(
                                asyncio.to_thread(retrieve, state),
                                timeout=retrieve_timeout
                            )
                        except Exception:
                            # If AST fails, continue without it (RAG will handle it)
                            pass

                        # Extract entity names for adaptive querying
                        if state["code_chunks"]:
                            state["initial_entities"] = self._extract_entity_names(state["code_chunks"])

                    # RAG query (used in both modes)
                    state = await asyncio.to_thread(
                        rag_retrieve,
                        state,
                        self.rag_service,
                        self.config.generation.rag_top_k,
                        self.config.generation.rag_query_strategy
                    )

                    # Log initial RAG query
                    if self.rag_tracker and state.get("rag_context"):
                        await self.rag_tracker.log_initial_query(
                            module=module,
                            strategy=self.config.generation.rag_query_strategy,
                            top_k=self.config.generation.rag_top_k,
                            chunks_retrieved=len(state["rag_context"]),
                            chunks=state["rag_context"]
                        )

                except Exception as e:
                    # Non-fatal: continue without RAG context
                    if use_adaptive:
                        # In adaptive mode, RAG is required - fail if unavailable
                        return (module, None, False, f"RAG required but unavailable: {e}",
                                {"retrieve": None, "write": None, "review": None})
            elif not use_adaptive:
                # Traditional AST-based retrieval (non-adaptive mode)
                retrieve_start = time.time()
                try:
                    state = await asyncio.wait_for(asyncio.to_thread(retrieve, state), timeout=retrieve_timeout)
                    state["last_retrieve_time"] = time.time() - retrieve_start
                except asyncio.TimeoutError:
                    return (module, None, False, f"Retrieve timed out after {retrieve_timeout}s",
                            {"retrieve": None, "write": None, "review": None})
                except Exception as e:
                    return (module, None, False, f"Retrieve failed: {e}",
                            {"retrieve": None, "write": None, "review": None})

            # Create tool executor for adaptive mode
            tool_executor = None
            if use_adaptive and self.rag_service:
                from layer2.services.retrieval_tools import RetrievalToolExecutor
                base_executor = RetrievalToolExecutor(self.rag_service)

                # Wrap executor to log tool calls
                if self.rag_tracker:
                    tool_executor = LoggingRetrievalToolExecutor(base_executor, self.rag_tracker, module)
                else:
                    tool_executor = base_executor

            # Write documentation
            write_start = time.time()
            try:
                async with self.semaphore:
                    if use_adaptive:
                        state = await module_write_adaptive(
                            state,
                            llm_config=llm_config,
                            tool_executor=tool_executor,
                            max_turns=self.config.generation.adaptive_rag_max_rounds
                        )
                    else:
                        state = await module_write(state, llm_config=llm_config)
                state["last_write_time"] = time.time() - write_start
            except Exception as e:
                return (module, None, False, f"Write failed: {e}",
                        {"retrieve": state.get("last_retrieve_time"), "write": None, "review": None})

            # Review documentation (skip if max_retries is 0)
            if max_retries > 0:
                try:
                    if use_adaptive and self.config.generation.adaptive_rag_auto_expand:
                        pre_review_expanded = bool(state.get("expanded_context"))
                        state = await review_adaptive(
                            state,
                            llm_config=llm_config,
                            tool_executor=tool_executor,
                            timeout=review_timeout
                        )

                        # Log review expansion if it happened
                        if self.rag_tracker and state.get("expanded_context") and not pre_review_expanded:
                            # Extract missing entities from reviewer suggestions
                            from layer2.module_pipeline.reviewer import extract_missing_entities
                            missing_entities = extract_missing_entities(
                                state["reviewer_suggestions"],
                                module
                            )
                            await self.rag_tracker.log_review_expansion(
                                module=module,
                                missing_entities=missing_entities,
                                chunks_retrieved=len(state["expanded_context"])
                            )
                    else:
                        state = await review(state, llm_config=llm_config, timeout=review_timeout)
                except Exception as e:
                    return (module, None, False, f"Review failed: {e}",
                            {"retrieve": state.get("last_retrieve_time"),
                             "write": state.get("last_write_time"), "review": None})

            # Retry if needed
            retry_count = 0
            while max_retries > 0 and not state["review_passed"] and retry_count < max_retries:
                retry_count += 1
                state["retry_count"] = retry_count

                # For adaptive mode, expanded_context may be available
                if use_adaptive and state.get("expanded_context"):
                    print(f"    🔄 Retry {retry_count} for {module} with expanded context")

                write_start = time.time()
                try:
                    async with self.semaphore:
                        if use_adaptive:
                            state = await module_write_adaptive(
                                state,
                                llm_config=llm_config,
                                tool_executor=tool_executor,
                                max_turns=self.config.generation.adaptive_rag_max_rounds
                            )
                        else:
                            state = await module_write(state, llm_config=llm_config)
                    state["last_write_time"] = time.time() - write_start
                except Exception as e:
                    return (module, None, False, f"Write retry failed: {e}",
                            {"retrieve": state.get("last_retrieve_time"),
                             "write": None, "review": None})
                try:
                    if use_adaptive and self.config.generation.adaptive_rag_auto_expand:
                        state = await review_adaptive(
                            state,
                            llm_config=llm_config,
                            tool_executor=tool_executor,
                            timeout=review_timeout
                        )
                    else:
                        state = await review(state, llm_config=llm_config, timeout=review_timeout)
                except Exception as e:
                    return (module, None, False, f"Review retry failed: {e}",
                            {"retrieve": state.get("last_retrieve_time"),
                             "write": state.get("last_write_time"), "review": None})

            # Log module completion with RAG stats
            if self.rag_tracker and (self.config.generation.enable_rag or use_adaptive):
                total_chunks = len(state.get("rag_context", []))
                total_tool_calls = state.get("tool_calls_made", 0)
                mode = "adaptive" if use_adaptive else "supplementary"

                await self.rag_tracker.log_module_complete(
                    module=module,
                    total_queries=1 if self.config.generation.enable_rag or use_adaptive else 0,
                    total_tool_calls=total_tool_calls,
                    total_chunks=total_chunks,
                    mode=mode
                )

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

    def _extract_entity_names(self, code_chunks: List[str]) -> List[str]:
        """
        Extract function and class names from code chunks for adaptive querying.

        Args:
            code_chunks: List of code chunk strings

        Returns:
            List of entity names (functions and classes)
        """
        import re

        entities = []

        for chunk in code_chunks:
            # Extract function definitions
            function_matches = re.findall(r'def\s+(\w+)\s*\(', chunk)
            entities.extend(function_matches)

            # Extract class definitions
            class_matches = re.findall(r'class\s+(\w+)\s*[\(:]', chunk)
            entities.extend(class_matches)

        # Deduplicate while preserving order
        seen = set()
        unique_entities = []
        for entity in entities:
            if entity not in seen and not entity.startswith('_'):  # Skip private entities
                seen.add(entity)
                unique_entities.append(entity)

        return unique_entities[:50]  # Limit to 50 entities to avoid overwhelming prompts


class LoggingRetrievalToolExecutor:
    """Wrapper around RetrievalToolExecutor that logs tool calls to RAGUsageTracker."""

    def __init__(self, base_executor, tracker: RAGUsageTracker, module: str):
        """
        Initialize logging wrapper.

        Args:
            base_executor: Underlying RetrievalToolExecutor
            tracker: RAGUsageTracker instance
            module: Current module name for logging
        """
        self.base_executor = base_executor
        self.tracker = tracker
        self.module = module

    async def execute_tool_call(self, tool_name: str, arguments: Dict[str, any]) -> str:
        """
        Execute tool call and log the operation.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments from LLM function call

        Returns:
            Formatted string with retrieval results
        """
        # Execute the actual tool call
        result = await self.base_executor.execute_tool_call(tool_name, arguments)

        # Log the tool call
        await self.tracker.log_tool_call(
            module=self.module,
            tool_name=tool_name,
            arguments=arguments,
            result_summary=self._summarize_result(result)
        )

        return result

    def _summarize_result(self, result: str) -> str:
        """Create a brief summary of the tool result for logging."""
        lines = result.strip().split('\n')

        # Extract key information
        if len(lines) <= 3:
            return result.strip()[:100]

        # Get first meaningful line
        first_line = lines[0] if lines else ""

        # Count entities found
        entities_found = result.count("### ") + result.count("## ")
        chunks_found = result.count("```python")

        return f"{first_line} | Found: {entities_found} entities, {chunks_found} code blocks"