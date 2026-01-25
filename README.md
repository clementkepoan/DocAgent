# An AI-powered documentation generation tool that analyzes Python codebases and produces structured documentation using a multi-layer pipeline architecture.

## Overview

DocAgent is a structured documentation generation tool designed to automatically analyze Python codebases and produce comprehensive, well-organized documentation. Its primary purpose is to transform raw source code and configuration files into human-readable documentation through a multi-stage pipeline that leverages LLM-based analysis.

### Architecture Overview

The system follows a layered architecture that separates concerns across distinct processing stages:

**Layer 1: Data Processing & Embedding** (`layer1/`)
- Responsible for parsing, chunking, and vectorizing Python source code and configuration files
- Transforms raw source files into structured, embeddable chunks for downstream analysis
- Contains specialized modules for discrete steps: `parser` for import analysis, `chunker` for code extraction, and `embedder` for vector generation
- Acts as the foundational data processing layer for the entire system

**Layer 2: Core Business Logic** (`layer2/`)
- Houses the primary documentation generation workflows and supporting components
- Orchestrates the transformation of codebase analysis into structured documentation
- Organized into specialized subfolders:
  - `plan_pipeline/`: Orchestrates the core documentation workflow (planning, execution, review phases)
  - `module_pipeline/`: Handles module-specific documentation processing (review and writing stages)
  - `prompts/`: Generates structured prompts for LLM-based documentation across different phases
  - `schemas/`: Defines core data structures and type definitions using typed dictionaries
  - `services/`: Provides reusable business logic services for code analysis and LLM interaction

**Layer 3: Orchestration & Output** (`layer3/`)
- Executes the documentation generation pipeline and manages results
- Coordinates batch processing, asynchronous operations, and final file writing
- Contains modules for batch processing, asynchronous orchestration, file output, and progress reporting
- Sits above the core logic layer and below the CLI interface

**Root Level** (`./`)
- Contains the core orchestration and configuration logic
- `main` acts as the asynchronous entry point that initializes the system and manages the documentation workflow
- `config` centralizes all runtime settings, including LLM provider details
- Bootstraps the application and launches the primary process

### Key Characteristics

- **Modular Design**: Each layer and subfolder has well-defined responsibilities with clear separation of concerns
- **LLM Integration**: Leverages language models for intelligent code analysis and content generation
- **Batch Processing**: Supports parallel and asynchronous operations for efficient documentation generation
- **Configuration-Driven**: Runtime settings are centralized for easy customization
- **Typed Data Contracts**: Uses strongly-typed schemas to ensure data consistency across the application

The system's architecture enables it to scale from individual modules to entire project documentation while maintaining consistency and quality across generated content. See the source code for implementation details of specific components.

## Installation & Setup

This guide walks you through setting up the environment and configuration required to run the DocAgent tool.

### Prerequisites
- **Conda**: Anaconda or Miniconda must be installed on your system to manage the project environment.

### 1. Create the Conda Environment
Create and activate the Conda environment using the provided `environment.yml` file. This file specifies all Python and system dependencies.
```bash
conda env create -f environment.yml
conda activate doc-agent
```

### 2. Configure Environment Variables
The tool requires an API key for the DeepSeek LLM. Copy the provided example file and fill in your key.
```bash
cp .env.example .env
```
Edit the `.env` file and set your `DEEPSEEK_KEY`. You can also adjust other operational parameters like timeouts and retry limits as needed, following the examples in the file.

### 3. Prepare for First Use
With the environment active and the `.env` file configured, the tool's dependencies are installed and it is ready to execute. See the source code for implementation details on how to run the main pipelines.

## Quick Start

This tutorial shows you how to run the documentation generator on your codebase with minimal setup.

### Prerequisites

Complete the [Installation & Setup](installation) steps first:
1. Create and activate the Conda environment
2. Configure your `.env` file with a DeepSeek API key

### Step 1: Navigate to Your Codebase

Open your terminal and navigate to the root directory of the Python project you want to document:

```bash
cd /path/to/your/python/project
```

### Step 2: Run the Documentation Generator

From your project directory, execute the main script:

```bash
python /path/to/doc-agent/main.py
```

The tool will:
- Scan your current directory (`.`) for Python files
- Generate documentation using your configured DeepSeek API
- Save output files to the `./output` directory by default

### Step 3: View the Results

Check the output directory for generated documentation:

```bash
ls ./output/
```

You should find several files including:
- `Module level docum.txt` - Documentation for individual modules
- `Folder Level docum.txt` - Documentation organized by folder structure
- `Final Condensed.md` - A consolidated summary document

### Configuration Options

The tool uses sensible defaults, but you can customize behavior by editing your `.env` file:

- Change `OUTPUT_DIR` to specify a different output location
- Adjust `MAX_CONCURRENT_TASKS` to control parallel processing
- Set `USE_REASONER=false` to use the standard chat model instead

### Next Steps

Examine the generated documentation to verify quality. For more advanced usage, you can modify the configuration programmatically as shown in the `main.py` example, or explore the source code for implementation details.

## Configuration Guide

The documentation generator is configured through environment variables, which can be set directly in your shell or via a `.env` file in your project root. All settings have sensible defaults.

### Environment Variables

Create a `.env` file in your project root (use `.env.example` as a template) with the following variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_KEY` | (required) | API key for DeepSeek LLM provider |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | Base URL for DeepSeek API |
| `DEEPSEEK_CHAT_MODEL` | `deepseek-chat` | Model name for standard chat completions |
| `DEEPSEEK_REASONER_MODEL` | `deepseek-reasoner` | Model name for reasoning tasks |
| `LLM_TEMPERATURE` | `0.7` | Temperature for LLM responses (0.0-1.0, lower = more deterministic) |
| `MAX_CONCURRENT_TASKS` | `20` | Maximum number of concurrent processing tasks |
| `MAX_RETRIES` | `1` | Maximum retries for module documentation generation |
| `RETRIEVE_TIMEOUT` | `10` | Timeout in seconds for code retrieval operations |
| `REVIEW_TIMEOUT` | `60` | Timeout in seconds for LLM review operations |
| `MAX_PLAN_RETRIES` | `2` | Maximum retries for documentation plan generation |
| `SCC_MAX_RETRIES` | `3` | Maximum retries for strongly connected component context generation |
| `USE_REASONER` | `true` | Whether to use the reasoning model (`true`/`false`) |
| `ENABLE_LOGGING` | `true` | Whether to enable logging (`true`/`false`) |
| `PARALLEL_EXECUTION` | `true` | Whether to enable parallel execution (`true`/`false`) |
| `OUTPUT_DIR` | `./output` | Directory for generated documentation files |

### Configuration Structure

The configuration is organized into four main categories, each represented as a dataclass in the `config` module:

#### LLM Configuration (`LLMConfig`)
Controls LLM provider settings:
- `api_key`: Your DeepSeek API key (automatically loaded from `DEEPSEEK_KEY` environment variable)
- `base_url`, `chat_model`, `reasoner_model`: API endpoint and model selection
- `temperature`: Controls response randomness (0.0-1.0)

#### Processing Configuration (`ProcessingConfig`)
Controls batch processing and concurrency:
- `max_concurrent_tasks`: Limits parallel task execution
- `max_retries`, `max_plan_retries`, `scc_max_retries`: Retry limits for different operations
- `retrieve_timeout`, `review_timeout`: Timeout settings for network operations

#### Generation Configuration (`GenerationConfig`)
Controls documentation generation behavior:
- `use_reasoner`: Toggle between standard and reasoning models
- `enable_logging`: Enable/disable logging output
- `parallel_execution`: Enable/disable parallel processing

#### Output Configuration (`OutputConfig`)
Controls output paths and filenames:
- `output_dir`: Base output directory
- `module_docs_file`, `folder_docs_file`, `scc_contexts_file`, `condensed_file`: Output filenames

### Configuration File Detection

The `ConfigFileReader` class automatically scans for and reads configuration files to provide additional context to the documentation generator. It supports:

**Priority files** (always indexed if present):
- Dependency files: `environment.yml`, `requirements.txt`, `pyproject.toml`, `setup.py`
- Documentation: `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`
- Project config: `package.json`, `Makefile`, `.env.example`, `Dockerfile`

**Supported extensions**: `.yml`, `.yaml`, `.md`, `.json`, `.txt`, `.toml`, `.ini`, `.cfg`, `.rst`

**Ignored directories**: `__pycache__`, `.git`, `node_modules`, `.venv`, `venv`, `output`, and other common exclusion patterns.

Files larger than 50KB are truncated in the output with a truncation notice.

### Default Configuration

If no environment variables are set, the system uses these defaults:
- LLM: DeepSeek API with standard chat model
- Processing: 20 concurrent tasks with minimal retries
- Generation: Uses reasoning model with parallel execution enabled
- Output: Saves to `./output` directory with preset filenames

The configuration is loaded via `DocGenConfig.from_env()` which reads all environment variables and applies them to the appropriate configuration classes.

## Architecture: Three-Layer Design

DocAgent implements a structured, layered architecture to separate concerns across its data processing, business logic, and orchestration stages. This design enables modular development, clear data flow, and maintainability by isolating specific responsibilities within each layer.

### Layer 1: Foundational Data Processing
**Location:** `layer1/`
**Primary Responsibility:** To transform raw source code and configuration files into structured, embeddable data for the system.

This foundational layer acts as the data preparation pipeline. It parses Python source code (using `ast`), extracts meaningful chunks, and converts them into vector embeddings. Key modules follow a separation of concerns for discrete processing steps: the `parser` for import analysis, the `chunker` and `hierarchical_chunker` for code extraction, and the `embedder` for vector generation. The `grouper`, `config_reader`, and `vector_storing` modules handle additional data organization and persistence tasks.

**Key Characteristic:** This layer has low coupling, with modules that operate independently. Its role is purely data transformation; it does not contain business logic for documentation generation.

### Layer 2: Core Business Logic
**Location:** `layer2/`
**Primary Responsibility:** To orchestrate the transformation of processed code analysis into structured documentation plans and content.

Sitting above the data layer, `layer2` houses the application's core intelligence and workflows. It is organized into specialized sub-packages that manage distinct aspects of the documentation lifecycle:
*   `plan_pipeline/`: Orchestrates the high-level documentation workflow, including planning, execution, and review phases using LLM agents.
*   `module_pipeline/`: Handles the detailed review and writing stages for individual module documentation.
*   `prompts/`: Serves as a central factory for generating structured LLM instructions.
*   `schemas/`: Defines the strongly-typed data contracts (e.g., `agent_state`, `documentation` plans) that govern data flow between components.
*   `services/`: Provides reusable business logic services, such as LLM provider management and code retrieval.

**Key Characteristic:** This layer defines the system's data models and business processes. It is a top-level package upon which other layers depend, acting as the intermediary between foundational data and high-level orchestration.

### Layer 3: Orchestration and Output
**Location:** `layer3/`
**Primary Responsibility:** To execute the documentation generation pipeline at scale and manage the final output.

This is the action layer. It coordinates batch processing, asynchronous operations, and the physical writing of documentation files. Key modules include the `async_doc_generator` for main orchestration, `batch_processor` for parallelization, `file_output_writer` for file operations, and `scc_manager` for generating context based on strongly connected components. The `progress_reporter` handles tracking and user feedback.

**Key Characteristic:** This layer has high external dependencies and is imported by upper layers (like the CLI). It implements patterns for efficiency (async, batch processing) and sits between the core logic (`layer2`) and the user interface.

### Data Flow Between Layers
The system follows a primarily unidirectional flow from data to output:

1.  **Data Ingestion & Preparation (Layer 1):** The process begins in `layer1`, where raw source code is parsed, chunked, and embedded. The resulting structured data and vectors are made available for retrieval.
2.  **Logic Execution (Layer 2):** The orchestration in `layer3` invokes services and pipelines within `layer2`. `layer2` components use the `schemas` for type-safe data, employ the `services` (e.g., `code_retriever`) to fetch processed data from `layer1`, and use the `prompts` to guide LLMs through the `plan_pipeline` and `module_pipeline`.
3.  **Orchestration & Rendering (Layer 3):** The `layer3` modules take the documentation plans and content produced by `layer2` and manage their execution. This includes running generation in parallel batches, assembling the final documentation, and using the `file_output_writer` to produce the final Markdown files.

In essence, **`layer1` provides the data, `layer2` provides the rules and intelligence, and `layer3` provides the execution engine and output mechanism.** This separation ensures that changes to data processing (e.g., a new chunking strategy) or business logic (e.g., a new documentation template) can be made with minimal impact on the other layers.

## Core Components (Layer 2)

This layer contains the main business logic components that orchestrate the transformation of processed code analysis into structured documentation. The modules are organized into focused subfolders based on functional responsibility.

### `layer2/prompts`
**Purpose:** Central factory for generating structured LLM prompts used across all documentation phases.

This folder provides the specific instructions and context needed for the LLM to perform tasks. It exhibits high cohesion and is a critical dependency for many other components.

*   **`plan_prompts`**: Generates prompts for creating the overall documentation plan and executing section generation.
*   **`module_prompts`**: Provides prompts for generating module-level documentation and for reviewing the resulting content.
*   **`folder_prompts`**: Supplies prompts for generating folder-level documentation summaries and overviews.

### `layer2/schemas`
**Purpose:** Defines the core, strongly-typed data structures that govern the system's state and plans.

This folder acts as a foundational schema layer, providing data models that other components must adhere to. It uses typed dictionaries (e.g., `TypedDict`) to create explicit, validated schemas for complex nested data.

*   **`agent_state`**: Defines the data structure (importing `TypedDict`, `List`, `Optional`) for tracking the agent's runtime state.
*   **`documentation`**: Specifies the schemas for documentation generation plans and their constituent parts.

### `layer2/services`
**Purpose:** Provides reusable business logic services that orchestrate core documentation tasks.

This service layer encapsulates complex operations like code analysis and LLM interaction, sitting between higher-level orchestration and lower-level utilities.

*   **`llm_provider`**: A unified service for managing AI calls and interactions.
*   **`code_retriever`**: Handles structured code extraction from the codebase (imports `Path` from `pathlib`).
*   **`folder_generator`**: Coordinates the `code_retriever` and `llm_provider` to produce folder-level documentation.

### `layer2/plan_pipeline`
**Purpose:** Orchestrates the primary documentation generation workflow: planning, parallel execution, and review.

This pipeline implements a clear separation of concerns, using LLMs as agents within each distinct phase to transform codebase analysis into a structured documentation plan.

*   **`planner`**: Creates the initial, high-level documentation outline.
*   **`executor`**: Manages the parallel generation of individual plan sections.
*   **`reviewer`**: Validates the coherence and completeness of the resulting documentation plan.

### `layer2/module_pipeline`
**Purpose:** Manages the core processing phases for individual module documentation, specifically the review and writing stages.

This component orchestrates the transformation of raw LLM outputs into polished, structured documentation for a single module.

*   **`reviewer`**: Handles LLM provider management and validates LLM responses against the expected structure (imports `AgentState`).
*   **`writer`**: Focuses on text processing, formatting, and final content assembly (imports `AgentState`).

## API Reference

### Configuration Classes

The configuration system provides typed configuration classes for managing all aspects of the documentation generation process. Configuration is primarily loaded from environment variables.

#### `LLMConfig`
Configuration for Large Language Model interactions.

**See the source code for implementation details.**

#### `ProcessingConfig`
Configuration for document processing parameters.

**See the source code for implementation details.**

#### `GenerationConfig`
Configuration for documentation generation behavior.

**See the source code for implementation details.**

#### `OutputConfig`
Configuration for output formatting and storage.

**See the source code for implementation details.**

#### `DocGenConfig`
Main configuration container class.

**Methods:**
- `from_env(cls)`: Class method that loads configuration from environment variables. This is the primary way to initialize configuration.

**Usage:**
```python
from config import DocGenConfig

config = DocGenConfig.from_env()
```

### Layer 1: Core Processing Components

The `layer1` package contains foundational components for code analysis, processing, and embedding.

#### `ConfigFileReader`
Exported in `layer1.__all__` for reading and parsing configuration files.

**See the source code for implementation details.**

**Submodules:**
- `chunker`: Text chunking functionality
- `config_reader`: Configuration file parsing
- `embedder`: Embedding generation utilities
- `grouper`: Component grouping logic
- `hierarchical_chunker`: Multi-level text chunking
- `parser`: Code parsing and analysis
- `query`: Query interface for processed data
- `vector_storing`: Vector storage operations

### Layer 2: Business Logic Components

The `layer2` package contains orchestration logic that transforms processed code analysis into structured documentation.

**Subpackages:**
- `module_pipeline/`: Module-level documentation generation pipeline
- `plan_pipeline/`: Documentation plan generation pipeline
- `prompts/`: LLM prompt generation factory
- `schemas/`: Core data structures and type definitions
- `services/`: Service layer components

### Layer 3: Orchestration

#### `BatchProcessor`
High-level batch processing orchestrator.

**Methods:**
- `organize_batches(sorted_modules)`: Organizes modules into processing batches based on dependencies.

**See the source code for implementation details.**

## Testing Strategy

The current testing approach is focused on manual verification and integration testing of core components, particularly the embedding pipeline. Formal automated testing frameworks are not yet established in the provided context.

### Running Tests
A primary verification script, `test_local_embedder.py`, is provided to validate the end-to-end embedding generation process. You can run this test after setting up the environment to confirm the pipeline is functional.

```bash
python test_local_embedder.py
```

This script executes a complete workflow:
1. Parsing a sample codebase (`./backend`)
2. Chunking the parsed code into logical units
3. Generating vector embeddings for all chunks
4. Saving the results to a JSON file (`embeddings_test.json`)

### Test Coverage Expectations
The provided test validates the integration of the `ImportGraph`, `CodeChunker`, and `CodeEmbedder` classes. It serves as a functional check for the embedding generation pipeline, including GPU/CPU compatibility and correct output formatting for ChromaDB.

There is no evidence of unit tests, a dedicated test suite, or coverage metrics in the provided context. Testing beyond the provided script would require implementing a formal testing strategy. See the source code for implementation details of the current verification approach.

## Contributing Guide

Formal contribution guidelines are not fully documented in the available context. However, the project's structure and architectural patterns provide a foundation for development practices.

### Development Workflow
The primary entry point for the application is `main.py`. The core orchestration logic resides in `async_doc_generator.py`. To set up the development environment:
1.  Create the Conda environment using `environment.yml`.
2.  Activate the environment: `conda activate doc-agent`.
3.  Set the required `DEEPSEEK_KEY` in a `.env` file.

### Code Standards & Architecture
When modifying the codebase, adhere to the established three-layer architecture and its key patterns:
-   **Layer Separation**: Keep foundational data processing (`layer1/`), core business logic (`layer2/`), and orchestration logic distinct.
-   **State Management**: Use the `AgentState` TypedDict (`layer2/schemas/agent_state.py`) for type-safe state transitions within pipelines.
-   **Async Patterns**: Respect the `MAX_CONCURRENT_TASKS` semaphore for all LLM calls to manage API rate limits.
-   **Dependency Order**: Process modules in topological order (independent → dependent) to allow downstream references.

### Testing
A formal testing strategy is not yet established. Current verification relies on the manual integration test script `test_local_embedder.py`. See the source code for implementation details of the current verification approach.

### General Guidance
Prospective contributors should examine the existing source code to understand the current patterns and conventions. Significant architectural changes should maintain the documented separation of concerns and async processing model.

## Troubleshooting & FAQ

This guide addresses common problems users encounter when running the documentation generator.

### Missing API Key Error
**Symptom**: The tool fails to run or returns an authentication error.
**Solution**: Ensure you have created a `.env` file in your project root with a valid `DEEPSEEK_KEY`. Copy the `.env.example` template and fill in your API key. The key is required and has no default value.

### No Output Files Generated
**Symptom**: The tool runs but the `./output` directory remains empty.
**Checklist**:
1. Verify you are running the script from your project's root directory: `cd /path/to/your/python/project`
2. Confirm the script path is correct: `python /path/to/doc-agent/main.py`
3. Check that your project contains Python files in the scanned directory.

### Timeout Errors During Processing
**Symptom**: The process hangs or fails with timeout messages.
**Adjustments**: Increase timeout limits in your `.env` file:
- `RETRIEVE_TIMEOUT` (default: 10 seconds) for code reading.
- `REVIEW_TIMEOUT` (default: 60 seconds) for LLM operations.
For very large projects, consider increasing these values.

### Model-Related Issues
**Symptom**: Slow performance or unexpected model errors.
**Solution**: Try switching the model type. In your `.env` file, set `USE_REASONER=false` to use the standard `deepseek-chat` model instead of the reasoning model. This can sometimes resolve compatibility or performance issues.

### Concurrent Task Limits
**Symptom**: The tool uses excessive system resources or fails with resource errors.
**Adjustment**: Reduce the `MAX_CONCURRENT_TASKS` value in your `.env` file from the default of 20. A lower value (e.g., 5 or 10) reduces memory and CPU load, which is helpful on systems with limited resources.

