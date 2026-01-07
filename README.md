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
[![codecov](https://codecov.io/gh/ronikobrosly/retroflow/branch/main/graph/badge.svg)](https://codecov.io/gh/ronikobrosly/retroflow)


## Overview 

This is a project to help engineers, researchers, project managers, and others create beautiful, retro-looking ASCII flow diagrams. ASCII diagrams are pretty, and harken back to the mid-20th century technical documentation. They also have real advantages:

1) They work wonderfully in the age of agentic AI, which can easily read and parse these small representations.
2) ASCII diagrams can live inline with: PRs, Markdown files, Slack threads, etc.
3) ASCII diagrams optimize for thinking speed, not presentation quality. It encourages iteration and deletion instead of premature refinement.
4) Minimalist diagrams reduce visual noise (although they do still look retro and pretty)
5) They're tool agnostic and can be rendered anywhere



```
    ┌─────────┐
    │  START  │░
    └─────────┘░
     ░░░░░░░░░░░
         │
         ▼
    ┌─────────┐
    │ PROCESS │░
    └─────────┘░
     ░░░░░░░░░░░
         │
         ▼
    ┌─────────┐
    │DECISION │░
    └─────────┘░
     ░░░░░░░░░░░
         │
         ▼
    ┌─────────┐
    │   END   │░
    └─────────┘░
     ░░░░░░░░░░░
```

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

## Features

- **Simple syntax**: Define flowcharts using intuitive `A -> B` arrow notation
- **ASCII output**: Generate text-based flowcharts for terminals and documentation
- **Intelligent layout**: Automatic node positioning using NetworkX with barycenter heuristic
- **Cycle detection**: Handles cyclic graphs gracefully with back-edge routing
- **Customizable**: Adjust text width, box sizes, spacing, and shadows
- **Unicode box-drawing**: Beautiful boxes with optional shadow effects

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

### Export to Text File

```python
generator = FlowchartGenerator()

generator.save_txt("""
    A -> B
    B -> C
""", "flowchart.txt")
```

## Configuration

### FlowchartGenerator Options

```python
generator = FlowchartGenerator(
    max_text_width=22,      # Max width for text inside boxes before wrapping (default: 22)
    min_box_width=10,       # Minimum box width (default: 10)
    horizontal_spacing=12,  # Space between boxes horizontally (default: 12)
    vertical_spacing=6,     # Space between boxes vertically (default: 6)
    shadow=True             # Whether to draw box shadows (default: True)
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
| `save_txt(input_text, filename)` | Save flowchart to a text file |

### Convenience Functions

```python
from retroflow import parse_flowchart

# Parse without rendering
connections = parse_flowchart("A -> B\nB -> C")
# Returns: [('A', 'B'), ('B', 'C')]
```

### Lower-Level API

For advanced use cases, you can access the individual components:

```python
from retroflow import (
    Parser,
    SugiyamaLayout,  # Alias for NetworkXLayout
    Canvas,
    BoxRenderer,
)

# Parse input
parser = Parser()
connections = parser.parse("A -> B\nB -> C")

# Compute layout
layout_engine = SugiyamaLayout()
layout_result = layout_engine.layout(connections)

# Access layout information
for node_name, node_layout in layout_result.nodes.items():
    print(f"{node_name}: layer={node_layout.layer}, position={node_layout.position}")
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

Contributions are 100% welcome! Please feel free to submit a PR.
