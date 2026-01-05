# RetroFlow

```
 ___________________________________________________________
|                                                           |
|   _____      _             ______ _                       |
|  |  __ \    | |           |  ____| |                      |
|  | |__) |___| |_ _ __ ___ | |__  | | _____      __        |
|  |  _  // _ \ __| '__/ _ \|  __| | |/ _ \ \ /\ / /        |
|  | | \ \  __/ |_| | | (_) | |    | | (_) \ V  V /         |
|  |_|  \_\___|\__|_|  \___/|_|    |_|\___/ \_/\_/          |
|                                                           |
|            [ Beautiful ASCII Flowcharts ]                 |
|___________________________________________________________|
               ||                           ||
```

A Python library for generating beautiful ASCII and PNG flowcharts from simple text descriptions.

[![PyPI version](https://badge.fury.io/py/retroflow.svg)](https://badge.fury.io/py/retroflow)
[![Python Versions](https://img.shields.io/pypi/pyversions/retroflow.svg)](https://pypi.org/project/retroflow/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Installation

```bash
pip install retroflow
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add retroflow
```

## Quick Start

```python
from retroflow import FlowchartGenerator

# Create a generator
generator = FlowchartGenerator()

# Define your flowchart using simple arrow syntax
flowchart = generator.generate("""
    Start -> Process
    Process -> Decision
    Decision -> End
""")

print(flowchart)
```

Output:
```
    ┌─────────┐
    │  START  │░
    └─────────┘░
     ░░░░░░░░░░
         │
         ▼
    ┌─────────┐
    │ PROCESS │░
    └─────────┘░
     ░░░░░░░░░░
         │
         ▼
    ┌─────────┐
    │DECISION │░
    └─────────┘░
     ░░░░░░░░░░
         │
         ▼
    ┌─────────┐
    │   END   │░
    └─────────┘░
     ░░░░░░░░░░
```

## Features

- **Simple syntax**: Define flowcharts using intuitive `A -> B` arrow notation
- **ASCII output**: Generate text-based flowcharts for terminals and documentation
- **PNG export**: Create high-resolution images for presentations and reports
- **Intelligent layout**: Automatic node positioning with the Sugiyama algorithm
- **Cycle detection**: Handles cyclic graphs gracefully
- **Customizable**: Adjust box sizes, spacing, and layout algorithms

## Usage

### Basic Generation

```python
from retroflow import FlowchartGenerator

generator = FlowchartGenerator()

# Simple linear flow
result = generator.generate("""
    A -> B
    B -> C
    C -> D
""")
print(result)
```

### Branching Flows

```python
# Branching and merging
result = generator.generate("""
    Start -> Validate
    Validate -> Process
    Validate -> Error
    Process -> End
    Error -> End
""")
print(result)
```

### Cyclic Flows

```python
# Loops and cycles are supported
result = generator.generate("""
    Init -> Check
    Check -> Process
    Process -> Check
    Check -> Done
""")
print(result)
```

### Export to PNG

```python
generator = FlowchartGenerator()

# Save as high-resolution PNG
generator.save_png("""
    Login -> Authenticate
    Authenticate -> Success
    Authenticate -> Failure
    Success -> Dashboard
    Failure -> Login
""", "auth_flow.png", scale=2)
```

### Export to Text File

```python
generator = FlowchartGenerator()

generator.save_txt("""
    A -> B
    B -> C
""", "flowchart.txt")
```

### Get Statistics

```python
generator = FlowchartGenerator()

flowchart, stats = generator.generate_with_stats("""
    A -> B
    B -> C
    C -> A
""")

print(f"Nodes: {stats['nodes']}")
print(f"Edges: {stats['edges']}")
print(f"Has cycle: {stats['has_cycle']}")
print(f"Longest path: {stats['longest_path']}")
```

## Configuration

### FlowchartGenerator Options

```python
generator = FlowchartGenerator(
    box_width=11,           # Width of each box (default: 11)
    box_height=3,           # Height of each box (default: 3)
    horizontal_spacing=4,   # Space between boxes horizontally (default: 4)
    vertical_spacing=3,     # Space between boxes vertically (default: 3)
    layout_algorithm='layered'  # 'layered' or 'simple' (default: 'layered')
)
```

### PNG Export Options

```python
generator.save_png(
    input_text,
    output_path="diagram.png",
    scale=2,              # Resolution multiplier (default: 2)
    horizontal_flow=True, # Left-to-right flow (default: True)
    margin=50,            # Image margin in pixels (default: 50)
    font_path="/path/to/font.ttf",  # Custom font (default: system monospace)
    font_size=11,         # Font size in points (default: 11)
)
```

## Input Format

The input format uses a simple arrow syntax:

```
# Comments start with #
NodeA -> NodeB
NodeB -> NodeC

# Node names can contain spaces
User Login -> Validate Credentials
Validate Credentials -> Access Granted
```

### Rules

- Each line defines one connection: `Source -> Target`
- Node names are trimmed of whitespace
- Empty lines are ignored
- Lines starting with `#` are comments
- Node names can contain spaces

## API Reference

### FlowchartGenerator

The main class for generating flowcharts.

#### Methods

| Method | Description |
|--------|-------------|
| `generate(input_text)` | Generate ASCII flowchart string |
| `generate_with_stats(input_text)` | Generate flowchart and return statistics |
| `save_png(input_text, output_path, **kwargs)` | Save as PNG image |
| `save_txt(input_text, output_path)` | Save as text file |

### Convenience Functions

```python
from retroflow import generate_flowchart, parse_flowchart

# Quick generation
flowchart = generate_flowchart("A -> B\nB -> C")

# Parse without rendering
connections = parse_flowchart("A -> B\nB -> C")
# Returns: [('A', 'B'), ('B', 'C')]
```

### Lower-Level API

For advanced use cases, you can access the individual components:

```python
from retroflow import (
    parse_flowchart,
    create_graph,
    compute_layout,
    render_flowchart,
    render_to_png,
)

# Parse input
connections = parse_flowchart("A -> B\nB -> C")

# Create graph structure
graph = create_graph(connections)

# Compute layout
layout = compute_layout(graph, algorithm='layered')

# Render to ASCII
ascii_output = render_flowchart(graph, layout)

# Or render to PNG
render_to_png(graph, layout, "output.png")
```

## Development

### Setup

```bash
git clone https://github.com/ronikobrosly/retroflow.git
cd retroflow
uv sync --dev
```

### Run Tests

```bash
uv run pytest
```

### Run Linting

```bash
uvx ruff check .
uvx ruff format --check .
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
