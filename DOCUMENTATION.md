# 📚 Python Documentation Agent

> AI-powered documentation generator that analyzes Python codebases and creates comprehensive, structured documentation

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-black)](https://github.com/psf/black)
[![Architecture](https://img.shields.io/badge/architecture-layered-orange)](docs/architecture.md)

## 📖 Table of Contents

- [Overview](#-overview)
- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Core Components](#-core-components)
- [Key Features](#-key-features)
- [Dependencies](#-dependencies)
- [Development](#-development)
- [License](#-license)

## 🚀 Overview

The **Python Documentation Agent** is an intelligent tool that automatically generates comprehensive, professional-grade documentation for Python projects. By analyzing your codebase's structure, import dependencies, and module relationships, it creates detailed documentation that evolves with your code.

### The Problem It Solves

Documentation is often the first casualty in fast-paced development. Manual documentation becomes outdated quickly, and understanding complex dependency graphs is time-consuming. This tool bridges that gap by providing:

- **Automatic dependency analysis** - Understand how your modules interact
- **AI-powered documentation** - Generate human-readable explanations of your code
- **Structured output** - Professional README-style documentation ready for GitHub
- **Iterative improvement** - Review cycles ensure documentation quality

### ✨ Key Features

- 🔍 **Smart Dependency Analysis** - Automatically maps import relationships and detects circular dependencies
- 🤖 **AI-Powered Documentation** - Uses LLMs to generate context-aware, accurate documentation
- 📊 **Multi-Level Documentation** - Creates module, folder, and project-level documentation
- 🔄 **Review & Refine Cycles** - Iterative improvement ensures documentation quality
- 🏗️ **Layered Architecture** - Clean separation of concerns for maintainability
- ⚡ **Fast Processing** - Efficient algorithms handle large codebases

## ⚡ Quick Start

### Prerequisites

- Python 3.8 or higher
- DeepSeek API key (or compatible OpenAI API key)
- NetworkX library for graph operations

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/python-doc-agent.git
cd python-doc-agent

# Install dependencies
pip install networkx openai

# Set up your API key
export DEEPSEEK_API_KEY="your-api-key-here"
```

### Basic Usage

```python
from main import build_graph
from layer2.schemas import AgentState

# Initialize the agent state
state = AgentState(
    target_file="your_module.py",
    project_root=".",
    max_review_cycles=3
)

# Build and run the documentation pipeline
graph = build_graph()
result = graph.compile().invoke(state)

# Save the generated documentation
with open("DOCUMENTATION.md", "w") as f:
    f.write(result["final_documentation"])
```

### Example Workflow

```python
# Generate documentation for an entire project
from layer1.parser import ImportGraph
from layer1.grouper import FolderProcessor

# Analyze dependencies
graph = ImportGraph()
graph.analyze("your_project/")

# Generate folder-level documentation
processor = FolderProcessor(graph)
folders = processor.get_folders_bottom_up()

# Process each folder for documentation
for folder in folders:
    print(f"Processing: {folder.path}")
    # Documentation generation happens here...
```

## 🏗️ Architecture

### Layered Design Pattern

The system follows a clean, layered architecture where each layer has distinct responsibilities:

```
┌─────────────────────────────────────┐
│         Main Orchestrator           │  ← Top-level workflow control
├─────────────────────────────────────┤
│   Layer 2: Documentation Core       │  ← State management, LLM integration
│   • Schemas (Data structures)       │
│   • Writer (Documentation gen)      │
│   • Reviewer (Quality control)      │
│   • Retriever (Code extraction)     │
├─────────────────────────────────────┤
│   Layer 1: Dependency Analysis      │  ← Import parsing, graph operations
│   • Parser (Import analysis)        │
│   • Grouper (Folder organization)   │
└─────────────────────────────────────┘
```

### Core Design Principles

1. **Separation of Concerns** - Each layer focuses on a specific responsibility
2. **Data Flow Architecture** - State flows through a well-defined pipeline
3. **Provider Abstraction** - LLM interactions abstracted for flexibility
4. **Bottom-Up Processing** - Documentation generated from deepest dependencies upward

### Technology Stack

- **Core Language**: Python 3.8+
- **Dependency Analysis**: NetworkX for graph operations
- **AI Integration**: DeepSeek API (OpenAI-compatible)
- **Code Parsing**: Python AST module
- **State Management**: TypedDict for type safety

## 📁 Project Structure

```
python-doc-agent/
├── 📦 layer1/                    # Dependency analysis layer
│   ├── parser.py                # Import graph construction
│   └── grouper.py               # Folder organization
├── 📦 layer2/                    # Documentation core layer
│   ├── schemas.py               # Data structures & state
│   ├── retriever.py             # Code extraction
│   ├── llmprovider.py           # AI integration
│   ├── writer.py                # Documentation generation
│   └── reviewer.py              # Quality assurance
├── 📦 main.py                    # Workflow orchestration
├── 📂 examples/                  # Usage examples
├── 📂 tests/                     # Test suite
└── 📜 requirements.txt           # Dependencies
```

### Directory Purposes

<details>
<summary><strong>📦 layer1/ - Foundation Layer</strong></summary>

The foundational layer responsible for analyzing Python import dependencies and organizing modules into logical groups. This layer has zero external dependencies beyond Python's standard library and NetworkX, making it stable and self-contained.

- **parser.py**: Builds dependency graphs by scanning Python files and resolving imports
- **grouper.py**: Organizes modules into folder structures for documentation

</details>

<details>
<summary><strong>📦 layer2/ - Core Layer</strong></summary>

The core orchestration layer that coordinates between code analysis and AI-driven documentation generation. Implements key patterns like state management and provider abstraction.

- **schemas.py**: Defines the structured state container for the documentation pipeline
- **retriever.py**: Extracts and segments code from Python files
- **llmprovider.py**: Abstracts LLM interactions for flexibility
- **writer.py**: Orchestrates documentation generation at multiple levels
- **reviewer.py**: Validates and improves generated documentation

</details>

<details>
<summary><strong>📦 main.py - Orchestration Layer</strong></summary>

The entry point and workflow orchestrator that sequences the entire documentation generation process. Acts as the conductor that wires all components together into a cohesive pipeline.

</details>

## 🔧 Core Components

### Layer 1: Dependency Analysis

#### `ImportGraph` (layer1/parser.py)

**Purpose:** Analyzes Python import dependencies and builds a comprehensive dependency graph.

```python
class ImportGraph:
    def analyze(self, root_dir: str) -> None:
        """Main entry point: scans directory and builds dependency graph"""
    
    def topo_order_independent_first(self) -> List[str]:
        """Returns modules in topological order, independent modules first"""
    
    def _parse_imports(self, file_path: Path) -> List[str]:
        """Extracts and resolves imports from a Python file"""
```

**Example Usage:**
```python
from layer1.parser import ImportGraph

# Analyze a project
graph = ImportGraph()
graph.analyze("my_project/")

# Get dependency information
print(f"Total modules: {len(graph.module_index)}")
print(f"Circular dependencies: {graph.has_cycles()}")

# Process in optimal order
for module in graph.topo_order_independent_first():
    print(f"Processing: {module}")
```

#### `FolderProcessor` (layer1/grouper.py)

**Purpose:** Organizes modules into folder structures and computes import metrics.

```python
class FolderProcessor:
    def __init__(self, import_graph: ImportGraph):
        """Initialize with an existing import graph"""
    
    def get_folders_bottom_up(self) -> List[FolderInfo]:
        """Returns folders sorted by depth (deepest first)"""
    
    def _compute_all_metrics(self) -> None:
        """Calculates import metrics for each folder"""
```

### Layer 2: Documentation Core

#### `AgentState` (layer2/schemas.py)

**Purpose:** Defines the structured state container for the documentation pipeline.

```python
class AgentState(TypedDict):
    """Complete state structure for documentation generation"""
    target_file: str
    project_root: str
    module_docs: Dict[str, str]
    folder_docs: Dict[str, str]
    review_status: Dict[str, bool]
    current_review_cycle: int
    max_review_cycles: int
    final_documentation: Optional[str]
```

#### `LLMProvider` (layer2/llmprovider.py)

**Purpose:** Abstracts LLM interactions for flexible AI integration.

```python
class LLMProvider:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with API key (uses environment variable if None)"""
    
    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        """Send prompt to LLM and return completion"""
```

**Example Usage:**
```python
from layer2.llmprovider import LLMProvider

provider = LLMProvider()
documentation = provider.generate(
    prompt="Document this Python function...",
    temperature=0.5
)
```

#### Documentation Writer (layer2/writer.py)

**Purpose:** Orchestrates documentation generation at multiple levels.

<details>
<summary><strong>Key Functions</strong></summary>

```python
def module_write(state: AgentState) -> AgentState:
    """Generate documentation for a single module"""

def folder_write(state: AgentState) -> AgentState:
    """Generate folder-level documentation"""

def condenser_write(state: AgentState) -> AgentState:
    """Create comprehensive project documentation"""

def format_structured_doc(doc_data: Dict) -> str:
    """Convert structured data to readable markdown"""
```

</details>

#### Documentation Reviewer (layer2/reviewer.py)

**Purpose:** Validates and improves generated documentation through AI review.

```python
def review(state: AgentState) -> AgentState:
    """Review documentation and provide improvement suggestions"""

def parse_review_json(response: str) -> Dict:
    """Extract structured review data from LLM response"""
```

### Main Orchestrator (main.py)

**Purpose:** Sequences the entire documentation workflow.

```python
def build_graph() -> StateGraph:
    """Construct the documentation generation state machine"""

def review_router(state: AgentState) -> str:
    """Route to next step based on review status"""
```

## ⚡ Key Features & Capabilities

### Smart Dependency Analysis

The agent goes beyond simple import parsing to provide deep insights into your codebase:

```python
# Detect circular dependencies
graph = ImportGraph()
graph.analyze("project/")
if graph.has_cycles():
    print("Warning: Circular dependencies detected!")
    for cycle in graph.get_cycles():
        print(f"  Cycle: {' -> '.join(cycle)}")

# Get coupling metrics
processor = FolderProcessor(graph)
for folder in processor.get_folders_bottom_up():
    print(f"{folder.path}:")
    print(f"  External imports: {folder.external_imports}")
    print(f"  Internal imports: {folder.internal_imports}")
    print(f"  Sibling coupling: {folder.sibling_coupling}")
```

### Multi-Level Documentation

Generate documentation at different abstraction levels:

1. **Module Level** - Detailed documentation of individual Python files
2. **Folder Level** - Architectural documentation of directory structures
3. **Project Level** - Comprehensive README-style overview

### Iterative Improvement Cycle

The review system ensures documentation quality through multiple refinement passes:

```
Initial Draft → AI Review → Apply Suggestions → Final Documentation
       ↑                                      ↓
       └────────── Retry (if needed) ─────────┘
```

### Customizable Prompts

The system uses structured prompts that can be customized for different documentation styles:

```python
# Example prompt structure for module documentation
MODULE_PROMPT = """
You are a technical documentation expert. Document the following Python module:

Module: {module_name}
Dependencies: {dependencies}
Code: {code_chunks}

Generate documentation with:
1. Summary (one paragraph)
2. Responsibility (clear statement)
3. Key Functions (bulleted list)
4. Dependency Usage (what it imports and why)
5. Exports (what it provides)
"""
```

## 🔗 Dependencies & Relationships

### Internal Dependency Graph

```
main.py
    ├── layer2.retriever
    ├── layer2.writer
    ├── layer2.reviewer
    └── layer2.schemas

layer2.writer
    ├── layer1.grouper
    ├── layer2.llmprovider
    └── layer2.schemas

layer1.grouper
    └── layer1.parser

layer1.parser
    └── networkx (external)
```

### External Dependencies

| Package | Purpose | Version |
|---------|---------|---------|
| `networkx` | Graph operations and cycle detection | ^3.0 |
| `openai` | LLM API client (DeepSeek compatible) | ^1.0 |

### Module Interaction Patterns

1. **Data Flow Pattern**: State flows through `AgentState` across all components
2. **Provider Pattern**: `LLMProvider` abstracts AI model interactions
3. **Processor Pattern**: Each layer processes data and passes it upward
4. **Review Pattern**: Iterative improvement through feedback loops

## 🛠️ Development

### Setting Up Development Environment

```bash
# Clone and setup
git clone https://github.com/yourusername/python-doc-agent.git
cd python-doc-agent
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage report
pytest --cov=layer1 --cov=layer2 tests/

# Run specific test module
pytest tests/test_parser.py -v
```

### Code Conventions

- **Type Hints**: All functions must include type annotations
- **Docstrings**: Google-style docstrings for all public functions
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Imports**: Grouped as standard library → third-party → local
- **Formatting**: Black for code formatting, isort for import sorting

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

<details>
<summary><strong>Development Workflow</strong></summary>

```bash
# 1. Set up pre-commit hooks
pre-commit install

# 2. Make changes with automatic formatting
# (Black and isort will run on commit)

# 3. Run tests before committing
pytest tests/

# 4. Update documentation if needed
python -m examples.generate_docs

# 5. Create pull request with:
#    - Clear description of changes
#    - Updated tests if applicable
#    - Documentation updates if needed
```

</details>

### Project Roadmap

- [ ] Add support for additional LLM providers (Claude, Gemini)
- [ ] Implement documentation templates for different project types
- [ ] Add web interface for interactive documentation generation
- [ ] Support for other programming languages (JavaScript, TypeScript)
- [ ] Integration with CI/CD pipelines

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  
**Built with ❤️ by the Python Documentation Agent Team**

[Report Bug](https://github.com/yourusername/python-doc-agent/issues) · 
[Request Feature](https://github.com/yourusername/python-doc-agent/issues) · 
[Contribute](CONTRIBUTING.md)

</div>