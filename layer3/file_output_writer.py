"""Handles all file writing operations for documentation output."""

import os
import asyncio
from typing import Dict, TYPE_CHECKING
from layer2.services.folder_generator import generate_folder_docs_async

if TYPE_CHECKING:
    from config import DocGenConfig


class OutputWriter:
    """Centralizes all file writing operations."""

    def __init__(self, config: "DocGenConfig" = None):
        # Load config if not provided
        if config is None:
            from config import DocGenConfig
            config = DocGenConfig()

        self.config = config
        self.output_dir = os.path.abspath(config.output.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
    
    def write_scc_contexts(self, scc_contexts_dict: Dict[str, str]) -> None:
        """Export SCC contexts to a text file."""
        if not scc_contexts_dict:
            return
        
        output_file = os.path.join(self.output_dir, "scc_contexts.txt")
        try:
            with open(output_file, "w") as f:
                f.write("="*80 + "\n")
                f.write("STRONGLY CONNECTED COMPONENTS (CYCLE) ARCHITECTURE OVERVIEWS\n")
                f.write("="*80 + "\n\n")
                
                for idx, (key, context) in enumerate(scc_contexts_dict.items(), 1):
                    f.write(f"\n{'─'*80}\n")
                    f.write(f"Cycle {idx}\n")
                    f.write(f"{'─'*80}\n\n")
                    f.write(context)
                    f.write("\n")
                
                f.write("\n" + "="*80 + "\n")
                f.write(f"Total cycles documented: {len(scc_contexts_dict)}\n")
                f.write("="*80 + "\n")
            
            print(f"✓ SCC contexts exported to {output_file}")
        except Exception as e:
            print(f"⚠️  Failed to export SCC contexts: {e}")
    
    def write_module_docs(self, final_docs: Dict[str, str]) -> None:
        """Aggregate module-level docs into a single file."""
        module_agg_path = os.path.join(self.output_dir, "Module level docum.txt")
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
    
    async def write_folder_docs(
        self,
        analyzer,
        final_docs: Dict[str, str],
        semaphore: asyncio.Semaphore
    ) -> tuple:
        """
        Generate and write folder-level documentation (async version).

        Args:
            analyzer: ImportGraph analyzer
            final_docs: Module documentation dict
            semaphore: Semaphore for rate limiting

        Returns:
            (folder_docs, folder_tree) for use by condenser
        """
        print("📁 Generating folder-level documentation...")
        try:
            # Call async version with semaphore and llm_config
            folder_docs, folder_tree = await generate_folder_docs_async(
                analyzer, final_docs, semaphore, llm_config=self.config.llm
            )

            # Write to file (sync I/O is fine here)
            folder_txt_path = os.path.join(self.output_dir, "Folder Level docum.txt")
            try:
                with open(folder_txt_path, "w") as ff:
                    ff.write("FOLDER LEVEL DOCUMENTATION\n")
                    ff.write("="*80 + "\n\n")
                    for folder_path, description in folder_docs.items():
                        ff.write(f"## {folder_path}\n\n{description}\n\n")
                print(f"✓ Folder documentation written to {folder_txt_path}\n")
            except Exception as e:
                print(f"⚠️ Failed to write folder-level text file: {e}\n")

            return folder_docs, folder_tree
        except Exception as e:
            print(f"⚠️  Folder documentation failed: {e}\n")
            import traceback
            traceback.print_exc()
            return {}, {}
    
    # Legacy write_condensed_doc REMOVED


    async def write_condensed_doc_with_planner(
        self,
        analyzer,
        final_docs: Dict[str, str],
        folder_docs: Dict[str, str],
        folder_tree: dict,
        semaphore: asyncio.Semaphore
    ) -> None:
        """
        Generate condensed doc using planner agent (replaces old condenser).

        Args:
            analyzer: ImportGraph analyzer
            final_docs: Module documentation dict
            folder_docs: Folder documentation dict
            folder_tree: Hierarchical folder structure from folder_write_async
            semaphore: For rate limiting LLM calls
        """
        print("📄 Generating documentation with planner agent...")

        try:
            from layer2.plan_pipeline.planner import generate_documentation_plan
            from layer2.plan_pipeline.reviewer import review_documentation_plan
            from layer2.plan_pipeline.executor import execute_documentation_plan

            # Step 1: Generate plan
            plan = await generate_documentation_plan(
                analyzer,
                folder_docs,
                folder_tree,
                final_docs,
                semaphore
            )

            # Step 2: Review plan with retry loop
            max_plan_retries = self.config.processing.max_plan_retries
            plan_valid = False

            for attempt in range(max_plan_retries):
                valid, feedback = await review_documentation_plan(
                    plan,
                    analyzer,
                    folder_docs,
                    semaphore
                )

                if valid:
                    plan_valid = True
                    break

                if attempt < max_plan_retries - 1:
                    print(f"⚠️  Plan revision needed (attempt {attempt + 1}/{max_plan_retries}): {feedback[:100]}...")
                    # Regenerate plan with feedback
                    plan = await generate_documentation_plan(
                        analyzer,
                        folder_docs,
                        folder_tree,
                        final_docs,
                        semaphore,
                        reviewer_feedback=feedback
                    )
                else:
                    print(f"⚠️  Plan not perfect but proceeding: {feedback[:100]}...")

            # Step 3: Execute plan (generate sections)
            condensed_doc = await execute_documentation_plan(
                plan,
                analyzer,
                folder_docs,
                folder_tree,
                final_docs,
                semaphore,
                use_reasoner=self.config.generation.use_reasoner,
                config=self.config
            )

            # Write to file
            condensed_path = os.path.join(self.output_dir, "Final Condensed.md")
            with open(condensed_path, "w") as f:
                f.write(condensed_doc)

            print(f"✓ Planned documentation saved to {condensed_path}\n")

        except Exception as e:
            print(f"⚠️  Planner-based documentation failed: {e}\n")
            import traceback
            traceback.print_exc()
            raise  # Re-raise since we're replacing the old approach
    
    def write_dependency_usage(self, dependency_usage_log: Dict) -> None:
        """Aggregate dependency usage into one file."""
        dep_used_path = os.path.join(self.output_dir, "dependency used.txt")
        try:
            with open(dep_used_path, "w") as outf:
                outf.write("Dependency usage report\n")
                outf.write("="*80 + "\n\n")

                if dependency_usage_log:
                    for module in sorted(dependency_usage_log.keys()):
                        data = dependency_usage_log[module]
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

    def write_rag_usage(self, rag_tracker) -> None:
        """
        Write RAG usage report.

        Note: This is called by async_doc_generator, not directly used here.
        The actual writing is done by RAGUsageTracker.write_report().
        This method is kept for API consistency with other write_* methods.

        Args:
            rag_tracker: RAGUsageTracker instance
        """
        if rag_tracker:
            rag_tracker.write_report()