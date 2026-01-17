"""Progress tracking, timing, and summary reporting for documentation generation."""

import time
from typing import List


class ProgressReporter:
    """Handles all progress tracking, timing, and summary output."""
    
    def __init__(self):
        self.start_time = None
    
    def start(self):
        """Mark the start of generation."""
        self.start_time = time.time()
    
    def format_elapsed_time(self) -> str:
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
    
    def print_header(self):
        """Print the generation header."""
        print("\n" + "="*80)
        print("🚀 AsyncDocAgent - Parallel Documentation Generation")
        print("="*80 + "\n")
    
    def print_analysis_summary(self, total_modules: int, total_packages: int, cycle_count: int):
        """Print codebase analysis summary."""
        print(f"✓ Found {total_modules} modules ({total_packages} packages)")
        print(f"✓ Detected {cycle_count} cycles\n")
    
    def print_batch_header(self, batch_num: int, total_batches: int, module_count: int):
        """Print batch processing header."""
        elapsed = self.format_elapsed_time()
        print(f"\n[Batch {batch_num}/{total_batches}] Processing {module_count} modules in parallel... [{elapsed}]")
    
    def print_batch_complete(self, success_count: int, actual_processed: int, skipped_packages: int):
        """Print batch completion summary."""
        print(f"  ✓ Batch complete: {success_count}/{actual_processed} modules documented" + 
              (f" ({skipped_packages} packages skipped)" if skipped_packages > 0 else ""))
    
    def print_final_summary(self, success_count: int, total_modules: int, failed_modules: List[tuple]):
        """Print final generation summary."""
        print("\n" + "="*80)
        print("📊 Documentation Generation Summary")
        print("="*80)
        print(f"✓ Successfully documented: {success_count}/{total_modules} modules")
        print(f"⏱️  Total time elapsed: {self.format_elapsed_time()}")
        
        if failed_modules:
            print(f"\n❌ Failed modules ({len(failed_modules)}):")
            for module, error, attempt, _ in failed_modules[:10]:
                print(f"  - {module}: {error[:60]}")
            if len(failed_modules) > 10:
                print(f"  ... and {len(failed_modules) - 10} more")
    
    def print_completion(self):
        """Print final completion message."""
        print("\n" + "="*80)
        print("✨ ASYNC DOCUMENTATION GENERATION COMPLETE!")
        print("="*80 + "\n")
    
    @staticmethod
    def format_timings(timings: dict) -> str:
        """Format timing information for display."""
        if not timings:
            return ""
        parts = []
        if timings.get("retrieve") is not None:
            parts.append(f"r:{timings['retrieve']:.1f}s")
        if timings.get("write") is not None:
            parts.append(f"w:{timings['write']:.1f}s")
        if timings.get("review") is not None:
            parts.append(f"rv:{timings['review']:.1f}s")
        return " [" + ", ".join(parts) + "]" if parts else ""