# ToolAnything

One Function to MCP and Tool calling

## Overview

ToolAnything is a Python framework that simplifies the creation and management of tool-based applications with support for Model Context Protocol (MCP) and tool calling interfaces.

## Features

- **Unified Interface**: Single function interface for MCP and tool calling
- **Modular Architecture**: Clean separation of concerns with dedicated modules
- **Extensible**: Easy to extend with custom tools and adapters
- **Type-Safe**: Built with type hints for better IDE support and fewer runtime errors

## Installation

```bash
pip install toolanything
```

For development:

```bash
pip install -e ".[dev]"
```

## Project Structure

```
toolanything/
├── pyproject.toml          # Project configuration and dependencies
├── README.md               # This file
├── LICENSE                 # MIT License
├── CHANGELOG.md            # Version history and changes
├── setup.cfg / setup.py    # Build configuration
├── requirements.txt        # Core dependencies
├── docs/                   # Documentation
├── examples/               # Example implementations
│   ├── weather_tool/       # Weather tool example
│   ├── finance_tools/      # Finance tools example
│   └── mcp_server_demo/    # MCP server demonstration
├── scripts/                # Utility scripts
├── tests/                  # Test suite
│   └── fixtures/           # Test fixtures and data
└── src/
    └── toolanything/       # Main package
        ├── core/           # Core functionality
        ├── decorators/     # Decorators for tool definition
        ├── pipeline/       # Pipeline processing
        ├── adapters/       # Adapters for different protocols
        ├── state/          # State management
        ├── cli/            # Command-line interface
        │   └── commands/   # CLI commands
        ├── server/         # Server implementations
        └── utils/          # Utility functions
```

## Quick Start

```python
from toolanything import tool

@tool
def my_function(param: str) -> str:
    """A simple tool example."""
    return f"Processed: {param}"
```

## Examples

Check the `examples/` directory for complete working examples:

- **weather_tool**: Demonstrates weather data retrieval
- **finance_tools**: Shows financial data processing
- **mcp_server_demo**: MCP server implementation example

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

AllanYiin

## Links

- GitHub: [https://github.com/AllanYiin/ToolAnything](https://github.com/AllanYiin/ToolAnything)
- Issues: [https://github.com/AllanYiin/ToolAnything/issues](https://github.com/AllanYiin/ToolAnything/issues)
