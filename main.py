"""Main entry point for async documentation generation."""

import asyncio
from layer3.async_doc_generator import AsyncDocGenerator
from config import DocGenConfig


async def main():
    """Entry point for documentation generation."""

    # Load config from environment variables (with defaults)
    config = DocGenConfig.from_env()

    # Alternative: Override specific values programmatically
    # from config import ProcessingConfig, GenerationConfig
    # config = DocGenConfig(
    #     processing=ProcessingConfig(max_concurrent_tasks=10, max_retries=2),
    #     generation=GenerationConfig(use_reasoner=False),
    # )

    generator = AsyncDocGenerator(root_path="./", config=config)
    final_docs = await generator.run()

    # Write all output files
    await generator.write_all_outputs(final_docs)

    # Print completion
    generator.reporter.print_completion()


if __name__ == "__main__":
    asyncio.run(main())