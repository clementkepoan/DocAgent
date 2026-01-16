# HTTPie 🚀

**A modern, user-friendly command-line HTTP client for the API era**

[![PyPI version](https://img.shields.io/pypi/v/httpie.svg)](https://pypi.org/project/httpie/)
[![Python versions](https://img.shields.io/pypi/pyversions/httpie.svg)](https://pypi.org/project/httpie/)
[![License](https://img.shields.io/badge/license-BSD--2--Clause-blue.svg)](LICENSE)
[![Build Status](https://img.shields.io/github/actions/workflow/status/httpie/cli/tests.yml)](https://github.com/httpie/cli/actions)
[![Downloads](https://img.shields.io/pypi/dm/httpie.svg)](https://pypi.org/project/httpie/)

## 📖 Table of Contents

- [Overview](#-overview)
- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Core Components](#-core-components)
- [Key Features](#-key-features)
- [Dependencies & Relationships](#-dependencies--relationships)
- [Development](#-development)
- [License](#-license)

## 🎯 Overview

HTTPie is a command-line HTTP client designed for the modern web. It provides an intuitive interface for interacting with HTTP APIs, featuring syntax highlighting, JSON support, persistent sessions, and a plugin system that makes API testing and debugging a pleasure.

Built on top of the popular `requests` library, HTTPie combines the power of Python's HTTP capabilities with a beautifully designed CLI experience. Whether you're debugging APIs, testing web services, or automating HTTP requests, HTTPie offers the perfect blend of simplicity and power.

### ✨ Key Features

- 🎨 **Beautiful Output** - Syntax highlighting for JSON, headers, and HTTP syntax
- 🔌 **Extensible Plugin System** - Add custom authentication, formatting, and transport handlers
- 💾 **Session Management** - Persistent cookies, headers, and authentication across requests
- 📦 **Smart Request Building** - Intuitive syntax for headers, JSON, forms, and file uploads
- ⚡ **Streaming Support** - Real-time response processing for APIs and long-running requests
- 🔒 **Security First** - SSL/TLS support, client certificates, and secure cookie handling

## 🚀 Quick Start

### Installation

```bash
# Install via pip (recommended)
pip install httpie

# Or using your system package manager
# macOS with Homebrew
brew install httpie

# Ubuntu/Debian
sudo apt install httpie

# Windows with Chocolatey
choco install httpie
```

### Basic Usage

```bash
# Simple GET request
http GET https://api.github.com/users/httpie

# POST with JSON data
http POST https://api.example.com/users name="John Doe" email="john@example.com"

# Custom headers and authentication
http GET https://api.example.com/protected \
  Authorization:"Bearer YOUR_TOKEN" \
  X-Custom-Header:"value"

# Download a file
http --download https://example.com/file.zip

# Use a session for persistent cookies/auth
http --session=logged-in POST https://api.example.com/login username=admin password=secret
http --session=logged-in GET https://api.example.com/dashboard
```

## 🏗️ Architecture

HTTPie follows a modular, plugin-based architecture that separates concerns while maintaining a cohesive user experience:

```
┌─────────────────────────────────────────────────────────────┐
│                    Command Line Interface                    │
├─────────────────────────────────────────────────────────────┤
│  Argument Parser  │  Plugin Manager  │  Session Manager     │
├─────────────────────────────────────────────────────────────┤
│                    HTTP Client Layer                         │
│  Request Builder  │  Adapter System  │  Response Processor  │
├─────────────────────────────────────────────────────────────┤
│                    Output Formatter                          │
│  Stream Manager   │  Syntax Highlighter │  Progress Display │
└─────────────────────────────────────────────────────────────┘
```

### Core Design Principles

1. **Modularity** - Each component is isolated and replaceable
2. **Extensibility** - Plugin system allows for custom functionality
3. **User Experience** - Intuitive CLI with helpful defaults
4. **Performance** - Streaming responses and efficient memory usage
5. **Compatibility** - Works across Python versions and platforms

### Technology Stack

- **Core HTTP**: `requests` library with custom adapters
- **CLI Framework**: Custom `argparse` extensions with Rich formatting
- **Plugin System**: Python entry points with dynamic discovery
- **Output Formatting**: Pygments for syntax highlighting, Rich for UI
- **Packaging**: PyInstaller for standalone executables

## 📁 Project Structure

```
httpie/
├── 📦 httpie/                    # Core application
│   ├── cli/                     # Command-line interface
│   │   ├── argparser.py         # Custom argument parsing
│   │   ├── argtypes.py          # Argument type definitions
│   │   ├── nested_json/         # Nested JSON accessor parsing
│   │   └── requestitems.py      # Request component processing
│   ├── client.py               # HTTP request/response orchestration
│   ├── output/                 # Output formatting system
│   │   ├── formatters/         # Content formatters (JSON, XML, etc.)
│   │   ├── lexers/            # Syntax highlighting lexers
│   │   ├── streams.py         # Output stream management
│   │   └── ui/                # User interface components
│   ├── plugins/               # Plugin system
│   │   ├── base.py           # Plugin base classes
│   │   ├── builtin.py        # Built-in authentication plugins
│   │   └── manager.py        # Plugin discovery and management
│   ├── sessions.py           # Session persistence
│   └── uploads.py           # File upload handling
├── 📦 tests/                  # Comprehensive test suite
│   ├── fixtures/             # Test fixtures and helpers
│   ├── utils/               # Testing utilities
│   └── test_*.py            # Individual test modules
├── 📁 extras/                # Additional tools and scripts
│   ├── packaging/           # Distribution packaging
│   ├── profiling/           # Performance benchmarking
│   └── scripts/            # Utility scripts
└── 📁 docs/                 # Documentation generation
```

### Directory Purposes

<details>
<summary>📦 Core Application Modules</summary>

- **`httpie/cli/`** - Command-line argument parsing and validation
- **`httpie/client/`** - HTTP request execution and response handling
- **`httpie/output/`** - Terminal output formatting and display
- **`httpie/plugins/`** - Extensible plugin architecture
- **`httpie/sessions/`** - Persistent session management
- **`httpie/uploads/`** - File upload and multipart handling
</details>

<details>
<summary>🧪 Testing Infrastructure</summary>

- **`tests/fixtures/`** - Shared test resources and mock objects
- **`tests/utils/`** - Reusable test helpers and utilities
- **`tests/test_*.py`** - Comprehensive test coverage
</details>

<details>
<summary>🔧 Development Tools</summary>

- **`extras/packaging/`** - Distribution and packaging scripts
- **`extras/profiling/`** - Performance benchmarking tools
- **`extras/scripts/`** - Utility scripts for development
- **`docs/`** - Automated documentation generation
</details>

## 🔧 Core Components

### CLI Argument System (`httpie/cli/`)

HTTPie's CLI system provides a sophisticated argument parsing framework with support for complex HTTP request specifications.

#### `HTTPieArgumentParser`

**Purpose:** Custom argument parser that extends Python's `argparse` with HTTPie-specific features.

```python
from httpie.cli.argparser import HTTPieArgumentParser

# Create a parser with HTTPie defaults
parser = HTTPieArgumentParser()
args = parser.parse_args(['GET', 'https://api.example.com'])
```

**Key Features:**
- URL shorthand notation (`:3000` → `http://localhost:3000`)
- Automatic HTTP method detection
- Support for nested JSON syntax
- Plugin-aware argument validation

#### Nested JSON Accessor (`httpie/cli/nested_json/`)

Parse and interpret nested JSON accessor expressions like `users[0].profile.name`.

```python
from httpie.cli.nested_json import parse_nested_json

# Parse nested JSON accessors
result = parse_nested_json(['users[0].name:=John', 'users[0].age:=30'])
# Returns: {'users': [{'name': 'John', 'age': 30}]}
```

### HTTP Client Layer (`httpie/client.py`)

Orchestrates HTTP request execution with session management and plugin integration.

#### `collect_messages()`

**Purpose:** Main orchestration function for HTTP request/response lifecycle.

```python
from httpie.client import collect_messages
from httpie.context import Environment

env = Environment()
messages = collect_messages(
    args=parsed_args,
    env=env,
    request=None
)

for message in messages:
    # Process each request/response in the chain
    print(message.headers)
```

**Key Responsibilities:**
- Session management and cookie handling
- Plugin transport adapter integration
- Redirect following with configurable limits
- Request/response streaming

### Output System (`httpie/output/`)

Manages terminal output with syntax highlighting and streaming capabilities.

#### Output Streams

```python
from httpie.output.streams import (
    RawStream,      # Unprocessed binary output
    EncodedStream,  # Text output with encoding conversion
    PrettyStream,   # Formatted output with syntax highlighting
    BufferedPrettyStream  # Fully buffered pretty output
)

# Select stream based on output options
stream_class, stream_kwargs = get_stream_type_and_kwargs(
    env=env,
    output_options=output_options,
    pretty=pretty
)
```

#### Formatter Plugins

```python
from httpie.output.formatters.json import JSONFormatter
from httpie.output.formatters.colors import ColorFormatter

# Register formatters for specific content types
formatter = JSONFormatter(**format_options)
formatted_body = formatter.format_body(
    body='{"message": "Hello"}',
    mime='application/json'
)
```

### Plugin System (`httpie/plugins/`)

Extensible architecture for adding custom functionality.

#### Creating a Custom Plugin

```python
from httpie.plugins.base import AuthPlugin

class CustomAuthPlugin(AuthPlugin):
    """Custom authentication plugin example."""
    
    name = 'custom-auth'
    auth_type = 'custom'
    description = 'Custom authentication scheme'
    
    def get_auth(self, username=None, password=None):
        return CustomAuth(username, password)

# Plugin automatically discovered via entry points
```

#### Plugin Manager

```python
from httpie.plugins.manager import plugin_manager

# Discover all installed plugins
plugins = plugin_manager.get_auth_plugins()
# Returns: {'basic': BasicAuthPlugin, 'digest': DigestAuthPlugin, ...}
```

### Session Management (`httpie/sessions.py`)

Persistent storage for cookies, headers, and authentication.

#### `Session` Class

```python
from httpie.sessions import get_httpie_session

# Create or load a session
session = get_httpie_session(
    session_name='my-session',
    host='api.example.com',
    config_dir='~/.config/httpie'
)

# Update session with new cookies/headers
session.update_headers(request_headers)
session.cookies.update(response_cookies)

# Save session to disk
session.save()
```

## ⚡ Key Features & Capabilities

### Smart Request Building

HTTPie provides intuitive syntax for constructing complex HTTP requests:

```bash
# JSON request with nested data
http POST api.example.com/users \
  name="John Doe" \
  profile.email="john@example.com" \
  profile.settings.notifications:=true

# Form data with file upload
http --form POST api.example.com/upload \
  name="Document" \
  file@/path/to/document.pdf

# Custom headers and query parameters
http GET api.example.com/search \
  q=="http client" \
  limit==10 \
  Authorization:"Bearer token"
```

### Streaming Responses

Handle real-time API responses efficiently:

```bash
# Stream JSON API responses
http --stream GET https://stream.example.com/events

# Follow progress with visual indicators
http --download --continue https://example.com/large-file.zip
```

### Plugin Ecosystem

Extend HTTPie with custom functionality:

```bash
# List installed plugins
httpie plugins list

# Install a plugin
httpie plugins install httpie-oauth

# Use plugin-specific features
http --auth-type=oauth https://api.example.com/protected
```

### Advanced Output Control

Fine-tune output formatting:

```bash
# Pretty print with specific colors
http --pretty=all --style=solarized https://api.example.com

# Output only specific parts
http --print=Hh https://api.example.com  # Headers only
http --print=b https://api.example.com   # Body only

# Format JSON with custom options
http --format-options=json.indent:4,json.sort_keys:true https://api.example.com
```

## 🔗 Dependencies & Relationships

### Internal Module Dependencies

```
httpie.core
├── httpie.cli.definition      # CLI argument definitions
├── httpie.client              # HTTP request execution
├── httpie.output.writer       # Output formatting
├── httpie.downloads           # File download handling
└── httpie.plugins.registry    # Plugin management

httpie.client
├── httpie.adapters           # HTTP adapter customization
├── httpie.ssl_               # SSL/TLS configuration
├── httpie.sessions           # Session persistence
└── httpie.uploads            # File upload handling

httpie.output.writer
├── httpie.output.streams     # Output stream management
├── httpie.output.processing  # Content processing
└── httpie.output.models      # Output data models
```

### External Dependencies

| Dependency | Purpose | Version |
|------------|---------|---------|
| `requests` | HTTP client foundation | >=2.22.0 |
| `Pygments` | Syntax highlighting | >=2.5.2 |
| `Rich` | Terminal formatting | >=10.0.0 |
| `requests-toolbelt` | Multipart uploads | >=0.9.1 |
| `importlib-metadata` | Plugin discovery | >=3.3.0 |

### Plugin Interface Dependencies

Plugins interact with HTTPie through well-defined interfaces:

1. **Authentication Plugins** - Extend `AuthPlugin` base class
2. **Formatter Plugins** - Extend `FormatterPlugin` base class  
3. **Transport Plugins** - Extend `TransportPlugin` base class
4. **Converter Plugins** - Extend `ConverterPlugin` base class

## 🛠️ Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/httpie/cli.git
cd cli

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test module
pytest tests/test_cli.py -v

# Run with coverage report
pytest --cov=httpie --cov-report=html

# Run integration tests
pytest tests/test_httpie.py
```

### Code Style & Conventions

HTTPie follows PEP 8 with additional project-specific conventions:

```bash
# Format code with black
black httpie/ tests/

# Sort imports with isort
isort httpie/ tests/

# Check code quality
flake8 httpie/ tests/
mypy httpie/ tests/
```

### Building Documentation

```bash
# Generate man pages
python extras/scripts/generate_man_pages.py

# Build distribution packages
python extras/packaging/linux/build.py
```

### Release Process

1. Update version in `httpie/__init__.py`
2. Update changelog
3. Run full test suite
4. Build distribution packages
5. Tag release and publish to PyPI

```bash
# Build and upload to PyPI
python setup.py sdist bdist_wheel
twine upload dist/*
```

## 📄 License

HTTPie is released under the [BSD 2-Clause License](LICENSE).

```
Copyright (c) 2012-present, Jakub Roztocil and contributors
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

---

<div align="center">
<sub>Built with ❤️ by <a href="https://github.com/httpie">HTTPie contributors</a></sub><br>
<sub>Documentation generated from source code analysis</sub>
</div>