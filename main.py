"""Main entry point for async documentation generation."""

import asyncio
from layer3.async_doc_generator import AsyncDocGenerator


async def main():
    """Entry point for documentation generation."""
    
    generator = AsyncDocGenerator(root_path="./")
    final_docs = await generator.run()
    
    # Write all output files
    generator.write_all_outputs(final_docs)
    
    # Print completion
    generator.reporter.print_completion()


if __name__ == "__main__":
    asyncio.run(main())