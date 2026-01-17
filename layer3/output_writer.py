"""Handles all file writing operations for documentation output."""

import os
from typing import Dict
from layer2.writer import folder_write, condenser_write


class OutputWriter:
    """Centralizes all file writing operations."""
    
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = os.path.abspath(output_dir)
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
    
    def write_folder_docs(self, analyzer, final_docs: Dict[str, str]) -> Dict[str, str]:
        """Generate and write folder-level documentation."""
        print("📁 Generating folder-level documentation...")
        try:
            # Generate the docs without writing to a JSON file
            folder_docs = folder_write(analyzer, final_docs)
            
            # Write only the human-readable text file
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
            
            return folder_docs
        except Exception as e:
            print(f"⚠️  Folder documentation failed: {e}\n")
            return {}
    
    def write_condensed_doc(self, analyzer, final_docs: Dict[str, str], folder_docs: Dict[str, str]) -> None:
        """Generate and write consolidated condensed documentation."""
        print("📄 Generating consolidated Final Condensed.md ...")
        try:
            condensed_path = os.path.join(self.output_dir, "Final Condensed.md")
            condenser_write(analyzer, final_docs, folder_docs, output_file=condensed_path)
            print(f"✓ Condensed documentation saved to {condensed_path}\n")
        except Exception as e:
            print(f"⚠️  Condensing documentation failed: {e}\n")
    
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