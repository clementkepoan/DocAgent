import asyncio
from layer2.schemas import AgentState
from layer2.retriever import retrieve
from layer2.writer import module_write, folder_write, condenser_write, scc_context_write
from layer2.reviewer import review
from layer1.parser import ImportGraph
from typing import List, Set, Dict, Optional
from tqdm import tqdm
import os
import time


MAX_RETRIES = 1
MAX_CONCURRENT_TASKS = 20  # Limit concurrent LLM calls
RETRIEVE_TIMEOUT = 10  # seconds for file/AST retrieval



class AsyncDocGenerator:
    """Orchestrates async documentation generation with cycle-aware batch processing."""
    
    def __init__(self, root_path: str = "./", output_dir: str = "./output"):
        self.root_path = root_path
        self.analyzer = None
        self.final_docs: Dict[str, str] = {}
        self.failed_modules: List[tuple] = []
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
        self.final_docs_lock = asyncio.Lock()
        self.start_time = None
        self.scc_contexts_dict: Dict[str, str] = {}  # Store for export
        # Output directories
        self.output_dir = os.path.abspath(output_dir)

        
    async def analyze_codebase(self) -> None:
        """Analyze codebase structure and detect cycles."""
        print("📊 Analyzing codebase structure...")
        self.analyzer = ImportGraph(self.root_path)
        self.analyzer.analyze()
        
        # Filter to only actual modules, exclude packages
        self.modules_only = [m for m in self.analyzer.module_index if m not in self.analyzer.packages]
        
        print(f"✓ Found {len(self.modules_only)} modules ({len(self.analyzer.packages)} packages)")
        print(f"✓ Detected {len([scc for scc in self.analyzer.get_sccs() if len(scc) > 1])} cycles\n")
    
    def _format_elapsed_time(self) -> str:
        """Format elapsed time from start."""
        if not self.start_time:
            return "0s"
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        mins = int((elapsed % 3600) // 60)
        secs = int(elapsed % 60)
        if hours > 0:
            return f"{hours}h {mins}m {secs}s"
        elif mins > 0:
            return f"{mins}m {secs}s"
        else:
            return f"{secs}s"
    
    async def get_sccs_with_order(self) -> List[Set[str]]:
        """Get SCCs in dependency order."""
        sccs = self.analyzer.get_sccs()
        
        # Map each SCC to its topological order
        sorted_modules = self.analyzer.get_sorted_by_dependency(reverse=False)
        scc_order = {}
        
        for scc in sccs:
            # Get the minimum index from sorted_modules to determine SCC order
            min_index = min(
                (sorted_modules.index(m) for m in scc if m in sorted_modules),
                default=float('inf')
            )
            scc_order[frozenset(scc)] = min_index
        
        # Sort SCCs by their first module appearance
        sorted_sccs = sorted(sccs, key=lambda scc: scc_order.get(frozenset(scc), float('inf')))
        return sorted_sccs
    
    def _get_scc_description(self, scc: Set[str]) -> str:
        """Get human-readable description of SCC."""
        if len(scc) == 1:
            return f"Independent"
        return f"Cycle ({len(scc)} modules)"
    
    async def validate_scc_dependencies(self, scc: Set[str]) -> bool:
        """Validate that all external dependencies of SCC are in final_docs."""
        for module in scc:
            deps = self.analyzer.get_dependencies(module)
            external_deps = [d for d in deps if d not in scc]
            
            for dep in external_deps:
                if dep not in self.final_docs:
                    print(f"  ⚠️  Warning: External dependency {dep} not yet documented for {module}")
                    return False
        return True
    
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
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with self.semaphore:
                    context = await scc_context_write(scc_list, code_chunks_dict)
                print(f"  ✓ SCC overview generated")
                return context
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  ⚠️  SCC overview generation failed (attempt {attempt + 1}/{max_retries}): {str(e)[:80]}")
                    await asyncio.sleep(2 ** attempt)
                else:
                    print(f"  ❌ SCC overview generation failed after {max_retries} attempts")
                    return None
    
    async def process_module(self, module: str, dependencies: List[str], 
                            dependency_docs: List[str], scc_context: Optional[str],
                            is_cyclic: bool, dependency_doc_sources: Dict[str, bool] = None) -> tuple:
        """Process a single module: retrieve -> write -> review.

        dependency_doc_sources: mapping of dependency module -> bool (True if doc present when scheduled)
        """
        
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

            # Store dependency usage for later aggregation into single file
            if not hasattr(self, 'dependency_usage_log'):
                self.dependency_usage_log = {}
            self.dependency_usage_log[module] = {
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                "dependencies": dependency_doc_sources if dependency_doc_sources else {dep: dep in self.final_docs for dep in dependencies}
            }
            
            # Retrieve code chunks (run in a thread to avoid blocking event loop)
            retrieve_start = time.time()
            try:
                state = await asyncio.wait_for(asyncio.to_thread(retrieve, state), timeout=RETRIEVE_TIMEOUT)
                state["last_retrieve_time"] = time.time() - retrieve_start
            except asyncio.TimeoutError:
                return (module, None, False, f"Retrieve timed out after {RETRIEVE_TIMEOUT}s", {"retrieve": None, "write": None, "review": None})
            except Exception as e:
                return (module, None, False, f"Retrieve failed: {e}", {"retrieve": None, "write": None, "review": None})

            # Write documentation (async)
            write_start = time.time()
            try:
                async with self.semaphore:
                    state = await module_write(state)
                state["last_write_time"] = time.time() - write_start
            except Exception as e:
                return (module, None, False, f"Write failed: {e}", {"retrieve": state.get("last_retrieve_time"), "write": None, "review": None})

            # Review documentation (async)
            try:
                state = await review(state)
            except Exception as e:
                return (module, None, False, f"Review failed: {e}", {"retrieve": state.get("last_retrieve_time"), "write": state.get("last_write_time"), "review": None})

            # Retry if needed
            retry_count = 0
            while not state["review_passed"] and retry_count < MAX_RETRIES:
                retry_count += 1
                state["retry_count"] = retry_count
                write_start = time.time()
                try:
                    async with self.semaphore:
                        state = await module_write(state)
                    state["last_write_time"] = time.time() - write_start
                except Exception as e:
                    return (module, None, False, f"Write retry failed: {e}", {"retrieve": state.get("last_retrieve_time"), "write": None, "review": None})
                try:
                    state = await review(state)
                except Exception as e:
                    return (module, None, False, f"Review retry failed: {e}", {"retrieve": state.get("last_retrieve_time"), "write": state.get("last_write_time"), "review": None})

            return (module, state["draft_doc"], True, None, {"retrieve": state.get("last_retrieve_time"), "write": state.get("last_write_time"), "review": state.get("last_review_time")})
        
        except Exception as e:
            return (module, None, False, str(e), {"retrieve": state.get("last_retrieve_time") if 'state' in locals() else None, "write": state.get("last_write_time") if 'state' in locals() else None, "review": state.get("last_review_time") if 'state' in locals() else None})
    
    async def process_batch(self, modules_to_process: List[str], batch_num: int, total_batches: int,
                           scc_contexts: Dict[str, str]) -> None:
        """Process a batch of modules in parallel with progress bar."""
        
        elapsed = self._format_elapsed_time()
        print(f"\n[Batch {batch_num}/{total_batches}] Processing {len(modules_to_process)} modules in parallel... [{elapsed}]")
        
        # Create progress bar for this batch
        pbar = tqdm(total=len(modules_to_process), desc=f"  Batch {batch_num}", 
                   unit="module", ncols=80, leave=False, colour="blue")
        
        # Prepare all tasks with module name mapping
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
            
            # Compute which dependency docs are present at scheduling time
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
                timing_str = ""
                if timings:
                    parts = []
                    if timings.get("retrieve") is not None:
                        parts.append(f"r:{timings['retrieve']:.1f}s")
                    if timings.get("write") is not None:
                        parts.append(f"w:{timings['write']:.1f}s")
                    if timings.get("review") is not None:
                        parts.append(f"rv:{timings['review']:.1f}s")
                    timing_str = " [" + ", ".join(parts) + "]" if parts else ""

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
        print(f"  ✓ Batch complete: {success_count}/{actual_processed} modules documented" + 
              (f" ({skipped_packages} packages skipped)" if skipped_packages > 0 else ""))
    
    async def run(self) -> Dict[str, str]:
        """Main orchestration: batch processing by dependency layers."""
        
        self.start_time = time.time()
        
        print("\n" + "="*80)
        print("🚀 AsyncDocAgent - Parallel Documentation Generation")
        print("="*80 + "\n")
        
        # Analyze
        await self.analyze_codebase()
        
        # Use modules_only (excludes packages)
        sorted_modules = [m for m in self.analyzer.get_sorted_by_dependency(reverse=False) 
                         if m not in self.analyzer.packages]
        total_modules = len(sorted_modules)
        
        print(f"📋 Processing {total_modules} modules\n")
        
        # Pre-generate all SCC contexts
        print("📖 Pre-generating cycle architecture docs...")
        scc_contexts: Dict[str, str] = {}
        cycles = [scc for scc in self.analyzer.get_sccs() if len(scc) > 1]
        for cycle in cycles:
            context = await self.generate_scc_context(cycle)
            if context:
                for module in cycle:
                    scc_contexts[module] = context
                self.scc_contexts_dict[f"cycle_{len(self.scc_contexts_dict)+1}"] = context
        print(f"✓ Generated {len(cycles)} cycle contexts\n")
        
        # Export SCC contexts to file
        if self.scc_contexts_dict:
            self._export_scc_contexts()
        
        # Group modules into batches by dependency depth
        # All independent modules → all modules 1-deep → etc
        batches = []
        processed = set()
        batch_num = 1
        max_iterations = total_modules  # Safety check
        
        while len(processed) < total_modules and max_iterations > 0:
            max_iterations -= 1
            # Find all modules whose LOCAL dependencies (within the codebase) are satisfied
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
                # This can happen if there are external dependencies or other edge cases
                available = [m for m in sorted_modules if m not in processed]
                if available:
                    print(f"  ℹ️  Note: Processing {len(available)} remaining modules with potential external deps")
            
            if available:
                batches.append(available)
                processed.update(available)
                batch_num += 1
        
        # Process all batches sequentially (but each batch processes modules in parallel)
        print(f"📋 Organized into {len(batches)} dependency batches\n")
        
        for batch_idx, batch in enumerate(batches, 1):
            await self.process_batch(batch, batch_idx, len(batches), scc_contexts)
        
        # Summary
        print("\n" + "="*80)
        print("📊 Documentation Generation Summary")
        print("="*80)
        print(f"✓ Successfully documented: {len(self.final_docs)}/{total_modules} modules")
        print(f"⏱️  Total time elapsed: {self._format_elapsed_time()}")
        
        if self.failed_modules:
            print(f"\n❌ Failed modules ({len(self.failed_modules)}):")
            for module, error, attempt in self.failed_modules[:10]:
                print(f"  - {module}: {error[:60]}")
            if len(self.failed_modules) > 10:
                print(f"  ... and {len(self.failed_modules) - 10} more")
        
        return self.final_docs
    
    def _export_scc_contexts(self) -> None:
        """Export SCC contexts to a text file."""
        output_file = "scc_contexts.txt"
        try:
            with open(output_file, "w") as f:
                f.write("="*80 + "\n")
                f.write("STRONGLY CONNECTED COMPONENTS (CYCLE) ARCHITECTURE OVERVIEWS\n")
                f.write("="*80 + "\n\n")
                
                for idx, (key, context) in enumerate(self.scc_contexts_dict.items(), 1):
                    f.write(f"\n{'─'*80}\n")
                    f.write(f"Cycle {idx}\n")
                    f.write(f"{'─'*80}\n\n")
                    f.write(context)
                    f.write("\n")
                
                f.write("\n" + "="*80 + "\n")
                f.write(f"Total cycles documented: {len(self.scc_contexts_dict)}\n")
                f.write("="*80 + "\n")
            
            print(f"✓ SCC contexts exported to {output_file}")
        except Exception as e:
            print(f"⚠️  Failed to export SCC contexts: {e}")


async def main():
    """Entry point."""
    
    generator = AsyncDocGenerator(root_path="./")
    final_docs = await generator.run()
    
    # Generate folder-level documentation
    if final_docs and generator.analyzer:
        # Ensure output directory exists
        output_dir = os.path.join(".", "output")
        os.makedirs(output_dir, exist_ok=True)

        # Aggregate module-level docs into a single file
        module_agg_path = os.path.join(output_dir, "Module level docum.txt")
        print("\n📁 Writing aggregated module-level documentation...")
        try:
            with open(module_agg_path, "w") as mf:
                mf.write("MODULE LEVEL DOCUMENTATION\n")
                mf.write("="*80 + "\n\n")
                for module, doc in final_docs.items():
                    mf.write(f"\n\n## Module: {module}\n\n")
                    mf.write(doc)
            print(f"✓ Module documentation aggregated to {module_agg_path}\n")
        except Exception as e:
            print(f"⚠️ Failed to write aggregated module docs: {e}\n")

        # Folder-level documentation (JSON + plain text)
        print("📁 Generating folder-level documentation...")
        try:
            folder_json_path = os.path.join(output_dir, "folder_docs.json")
            folder_docs = folder_write(generator.analyzer, final_docs, output_file=folder_json_path)
            # Also write a human-readable text file
            folder_txt_path = os.path.join(output_dir, "Folder Level docum.txt")
            try:
                with open(folder_txt_path, "w") as ff:
                    ff.write("FOLDER LEVEL DOCUMENTATION\n")
                    ff.write("="*80 + "\n\n")
                    for folder_path, description in folder_docs.items():
                        ff.write(f"## {folder_path}\n\n{description}\n\n")
                print(f"✓ Folder documentation written to {folder_txt_path}\n")
            except Exception as e:
                print(f"⚠️ Failed to write folder-level text file: {e}\n")
        except Exception as e:
            print(f"⚠️  Folder documentation failed: {e}\n")
            folder_docs = {}

        # Final condensed documentation into Final Condensed.md
        print("📄 Generating consolidated Final Condensed.md ...")
        try:
            condensed_path = os.path.join(output_dir, "Final Condensed.md")
            condensed_doc = condenser_write(generator.analyzer, final_docs, folder_docs, output_file=condensed_path)
            print(f"✓ Condensed documentation saved to {condensed_path}\n")
        except Exception as e:
            print(f"⚠️  Condensing documentation failed: {e}\n")

        # Aggregate dependency usage into one file from the log
        dep_used_path = os.path.join(output_dir, "dependency used.txt")
        try:
            with open(dep_used_path, "w") as outf:
                outf.write("Dependency usage report\n")
                outf.write("="*80 + "\n\n")
                dep_log = getattr(generator, 'dependency_usage_log', {})
                if dep_log:
                    for module in sorted(dep_log.keys()):
                        data = dep_log[module]
                        outf.write(f"Module: {module}\n")
                        outf.write(f"Scheduled at: {data['timestamp']}\n")
                        outf.write("Dependencies:\n")
                        for dep, present in sorted(data['dependencies'].items()):
                            outf.write(f"  {dep}, {present}\n")
                        outf.write("\n")
                    print(f"✓ Aggregated dependency usages to {dep_used_path}\n")
                else:
                    outf.write("No dependency usage data found.\n")
                    print(f"⚠️ No dependency usage data found to aggregate\n")
        except Exception as e:
            print(f"⚠️ Failed to write dependency used file: {e}\n")

    
    print("="*80)
    print("✨ ASYNC DOCUMENTATION GENERATION COMPLETE!")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())