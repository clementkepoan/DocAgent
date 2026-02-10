"""Simplified async documentation generator - main orchestration only."""

import asyncio
from typing import Dict, TYPE_CHECKING
from layer1.parser import ImportGraph
from layer1.parent_child_indexer import ParentChildIndexer
from layer3.scc_manager import SCCManager
from layer3.batch_processor import BatchProcessor
from layer3.file_output_writer import OutputWriter
from layer3.progress_reporter import ProgressReporter

if TYPE_CHECKING:
    from config import DocGenConfig


class AsyncDocGenerator:
    """Orchestrates async documentation generation - simplified coordinator."""

    def __init__(self, root_path: str = "./", output_dir: str = "./output", config: "DocGenConfig" = None):
        # Load config if not provided
        if config is None:
            from config import DocGenConfig
            config = DocGenConfig.from_env()

        # Override output_dir if explicitly passed (not default)
        if output_dir != "./output":
            from config import OutputConfig
            config = DocGenConfig(
                llm=config.llm,
                processing=config.processing,
                generation=config.generation,
                output=OutputConfig(
                    output_dir=output_dir,
                    module_docs_file=config.output.module_docs_file,
                    folder_docs_file=config.output.folder_docs_file,
                    scc_contexts_file=config.output.scc_contexts_file,
                    condensed_file=config.output.condensed_file,
                )
            )

        self.config = config
        self.root_path = root_path
        self.analyzer = None
        self.semaphore = asyncio.Semaphore(config.processing.max_concurrent_tasks)

        # Initialize Parent-Child RAG indexer
        self.parent_child_indexer = ParentChildIndexer(root_path)

        # Delegate responsibilities to specialized components (with config)
        self.scc_manager = SCCManager(root_path, self.semaphore, config)
        self.batch_processor = BatchProcessor(
            root_path, None, self.semaphore, config,
            parent_indexer=self.parent_child_indexer  # Pass indexer for RAG
        )
        self.output_writer = OutputWriter(config)
        self.reporter = ProgressReporter()

    async def analyze_codebase(self) -> None:
        """Analyze codebase structure, detect cycles, and index code chunks for RAG."""
        print("📊 Analyzing codebase structure...")
        self.analyzer = ImportGraph(self.root_path)
        self.analyzer.analyze()

        # Update batch processor with analyzer
        self.batch_processor.analyzer = self.analyzer

        # Filter to only actual modules, exclude packages
        self.modules_only = [m for m in self.analyzer.module_index if m not in self.analyzer.packages]

        cycles = [scc for scc in self.analyzer.get_sccs() if len(scc) > 1]
        self.reporter.print_analysis_summary(len(self.modules_only), len(self.analyzer.packages), len(cycles))

        # Index code chunks for Parent-Child RAG (children)
        print("📚 Indexing code chunks for RAG...")
        try:
            chunks_indexed = await self.parent_child_indexer.index_all_code_chunks(
                self.analyzer.module_index
            )
            print(f"   Indexed {chunks_indexed} code chunks")
        except Exception as e:
            print(f"   Warning: Code chunk indexing failed: {e}")
    
    async def run(self) -> Dict[str, str]:
        """Main orchestration: batch processing by dependency layers."""
        
        self.reporter.start()
        self.reporter.print_header()
        
        # Analyze codebase
        await self.analyze_codebase()
        
        # Get modules sorted by dependencies
        sorted_modules = [m for m in self.analyzer.get_sorted_by_dependency(reverse=False) 
                         if m not in self.analyzer.packages]
        total_modules = len(sorted_modules)
        print(f"📋 Processing {total_modules} modules\n")
        
        # Pre-generate all SCC contexts
        sccs = self.analyzer.get_sccs()
        scc_contexts = await self.scc_manager.generate_all_scc_contexts(sccs)
        
        # Export SCC contexts
        scc_contexts_dict = self.scc_manager.get_all_contexts()
        if scc_contexts_dict:
            self.output_writer.write_scc_contexts(scc_contexts_dict)
        
        # Organize modules into dependency batches
        batches = self.batch_processor.organize_batches(sorted_modules)
        print(f"📋 Organized into {len(batches)} dependency batches\n")
        
        # Process all batches
        for batch_idx, batch in enumerate(batches, 1):
            await self.batch_processor.process_batch(batch, batch_idx, len(batches), scc_contexts, self.reporter)
        
        # Print summary
        final_docs = self.batch_processor.final_docs
        failed_modules = self.batch_processor.failed_modules
        self.reporter.print_final_summary(len(final_docs), total_modules, failed_modules)
        
        return final_docs
    
    async def write_all_outputs(self, final_docs: Dict[str, str]) -> None:
        """Write all output files (async version)."""
        if not final_docs or not self.analyzer:
            return

        # Module-level docs (sync is fine)
        self.output_writer.write_module_docs(final_docs)

        # Folder-level docs (now async, parallel per level, bottom-up)
        folder_docs, folder_tree = await self.output_writer.write_folder_docs(
            self.analyzer,
            final_docs,
            self.semaphore  # Pass existing semaphore
        )

        # Condensed documentation (now with planner agent)
        await self.output_writer.write_condensed_doc_with_planner(
            self.analyzer,
            final_docs,
            folder_docs,
            folder_tree,  # Pass hierarchical structure
            self.semaphore
        )

        # Dependency usage log (sync is fine)
        self.output_writer.write_dependency_usage(self.batch_processor.dependency_usage_log)