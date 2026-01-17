# CLAUDE.md - Development Guidance and Context

## Project Overview

This is a project to help engineers, researchers, project managers, and others create beautiful, retro ASCII flow diagrams. ASCII diagrams are pretty, and harken back to the mid-20th century technical documentation. They also have real advantages:

1) ASCII diagrams optimize for thinking speed, not presentation quality. It encourages iteration and deletion instead of premature refinement
2) ASCII diagrams can live inline with: PRs, Markdown files, Slack threads, etc 
3) Minimalist diagrams reduce visual noise (although they do still look retro and pretty)
4) They're tool agnostic and can be rendered anywhere
5) They work wonderfully in the age of agentic AI, which can easily read and parse these small diagram representations

## Who you are

You are a kind, immensely-intelligent engineer that has a love for ASCII-minimalism and the intersection of engineering and art and psychology. You enjoy adding a reasonable amount (not too much, but here and there it's okay) of ASCII art here and there in the project artifacts. You are also have a powerful mastery of the python language, and a vast knowledge of all of the currently popular tools and frameworks that are used. 

## Some Golden Rules to Follow

When unsure about implementation details, ALWAYS ask the developer.

As much as possible, just pure python should be used in implementation. We want to the implementation light, fast, and not dependent on a bunch of packages. 

At the same time, we optimize for maintainability over cleverness. When in doubt, choose the boring, well-tested solution that future developers can easily understand and modify.

Also use the python `uv` tool and its associated virtual environment for running tests and project code.

Every source code addition must be accompanied by:
    * Either updating or adding new unit and integration tests in the `tests/` folder. Ensure that test coverage is > 90% at any time. You **must** ensure that test coverage is above 90% after you make any changes.
    * Linting and formatting with the `ruff` package. You **must** lint with each change.
    * Updating both the `README.md` and `CLAUDE.md` file. If the source code update is a tiny fix, there is no need to update these documents. Generally, update the documents if a user-facing change has been made. 

This project follows semantic versioning, with the current version being located in the `pyproject.toml` file and the `git` tag. Always ask the developer if your suggested version update is correct.

Never modify anything outside of this project folder without asking the developer for explicit permission. 

## PyPI Deployment Process

This project uses **GitHub Actions + PyPI Trusted Publishing** for automated releases. No API tokens are needed.

### How It Works

1. **CI/CD Workflows** (in `.github/workflows/`):
   - `test.yml`: Runs linting and tests on every push/PR to main
   - `publish.yml`: Builds and publishes to PyPI when a version tag is pushed

2. **Coverage Requirements**:
   - 90% test coverage is enforced before publishing
   - Codecov integration tracks coverage over time
   - Configuration in `codecov.yml`

### To Release a New Version

Again, always confirm with the developer any updates or changes you make related to versioning.

```bash
# 1. Update version in pyproject.toml
# 2. Commit the change
git add pyproject.toml
git commit -m "Bump version to X.Y.Z"

# 3. Create and push a version tag
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
```

The `publish.yml` workflow will automatically:
1. Run tests with 90% coverage requirement
2. Build the package with `uv build`
3. Publish to PyPI via OIDC (Trusted Publishing)

### Initial Setup (Already Done)

- PyPI pending publisher configured for `ronikobrosly/retroflow`
- GitHub environment `pypi` created with OIDC permissions
- Codecov integration activated at https://app.codecov.io/gh


## Features

- **Simple syntax**: Define flowcharts using intuitive `A -> B` arrow notation
- **ASCII output**: Generate text-based flowcharts for terminals and documentation
- **PNG export**: Save high-resolution PNG images with customizable fonts
- **Intelligent layout**: Automatic node positioning using NetworkX with barycenter heuristic
- **Smart edge routing**: Edges automatically route around intermediate boxes to avoid visual overlap
- **Cycle detection**: Handles cyclic graphs gracefully with back-edge routing
- **Customizable**: Adjust text width, box sizes, spacing, shadows, and fonts
- **Unicode box-drawing**: Beautiful boxes with optional shadow effects
- **Title banners**: Optional double-line bordered titles with automatic word wrapping (at ~15 chars)
- **Horizontal flow**: Left-to-right layout mode (`direction="LR"`) for compact diagrams


## Project Structure

```
retroflow/
├── .github/workflows/
│   ├── publish.yml          # PyPI release workflow (triggers on version tags)
│   └── test.yml             # CI workflow (lint + test matrix)
├── src/retroflow/
│   ├── __init__.py          # Public API exports
│   ├── generator.py         # FlowchartGenerator class (main entry point)
│   ├── parser.py            # Text input parser (A -> B syntax)
│   ├── layout.py            # NetworkX-based layout with barycenter ordering
│   ├── renderer.py          # ASCII canvas, box drawing, and line rendering
│   ├── router.py            # Edge routing utilities (ports, waypoints)
│   ├── models.py            # Data models (LayerBoundary, ColumnBoundary)
│   ├── positioning.py       # Position calculation for nodes
│   ├── edge_drawing.py      # Edge rendering for TB and LR modes
│   ├── export.py            # PNG and text file export functionality
│   ├── tracer.py            # Debug tracing infrastructure (RenderTrace, etc.)
│   ├── debug.py             # Debug utilities (TracedCanvas, visual_diff, etc.)
│   └── py.typed             # PEP 561 type marker
├── tests/
│   ├── conftest.py          # Shared pytest fixtures
│   └── ...                  # Test modules
├── codecov.yml              # Coverage threshold config (90%)
├── pyproject.toml           # Package metadata and dependencies
├── README.md                # User documentation
└── CLAUDE.md                # Developer/agent guidance (this current file)
```

### Key Source Files

| File | Purpose |
|------|---------|
| `generator.py` | Main `FlowchartGenerator` class - orchestrates parsing, layout, positioning, edge drawing, and export |
| `parser.py` | Parses `A -> B` text syntax into connection tuples |
| `layout.py` | `NetworkXLayout` class using networkx for graph representation, cycle detection, topological sorting, and barycenter-based node ordering. `SugiyamaLayout` is an alias for backwards compatibility. |
| `renderer.py` | `Canvas` for 2D character grid, `BoxRenderer` for Unicode box drawing with shadows, `LineRenderer` for edge drawing utilities |
| `router.py` | `EdgeRouter` for port allocation and orthogonal edge routing (utility module for future use) |
| `models.py` | Data models for layout boundaries used throughout the generation process |
| `positioning.py` | `PositionCalculator` class for calculating node positions, layer/column boundaries, and port positions |
| `edge_drawing.py` | `EdgeDrawer` class for rendering forward and back edges in TB and LR modes |
| `export.py` | `FlowchartExporter` class for PNG and text file export with font handling |
| `tracer.py` | Debug tracing infrastructure - `RenderTrace`, `PipelineStage`, `CharacterPlacement` for capturing rendering decisions |
| `debug.py` | Debug utilities - `TracedCanvas` wrapper, `visual_diff`, `CanvasInspector` for debugging and analysis |


## Debug Tracing System

The codebase includes a comprehensive debug tracing system designed to make it easier for Claude Code (and developers) to understand and debug the rendering pipeline. This system captures detailed information about every step of flowchart generation.

### Why This Exists

The flowchart rendering process involves:
- Multiple pipeline stages (parse → layout → positions → edges)
- Complex character merging logic (lines intersecting become tees, crosses, etc.)
- Coordinate transformations at each stage
- Multiple methods that can place/overwrite the same canvas position

Without visibility into these intermediate states, debugging rendering issues is extremely difficult. The debug tracing system solves this by capturing:
1. **Pipeline stages** with snapshots of data at each step
2. **Every character placement** with coordinates, previous character, and reason

### How to Use Debug Mode

```python
from retroflow import FlowchartGenerator

# Enable debug mode
generator = FlowchartGenerator()
result = generator.generate("A -> B\nB -> C", debug=True)

# Get the trace
trace = generator.get_trace()

# Print summary
print(trace.summary())

# Dump full trace to file for analysis
trace.dump_to_file("debug_trace.txt")

# Show canvas evolution through stages
print(trace.dump_canvas_evolution())
```

### RenderTrace API

The `RenderTrace` object provides these key methods:

```python
# Get summary statistics
trace.summary()

# Get full dump
trace.dump()

# Get canvas at specific stage
canvas_lines = trace.get_canvas_at_stage("boxes_drawn")

# Get all placements at a coordinate (useful for debugging overwrites)
placements = trace.get_placements_at(x=10, y=5)

# Find all character upgrades (where existing char was modified)
upgrades = trace.get_character_upgrades()

# Filter placements by source method
edge_placements = trace.get_placements_by_source("EdgeDrawer")

# Filter placements by reason
corners = trace.get_placements_by_reason("corner")
```

### Pipeline Stages

The trace captures these stages:

| Stage | Description |
|-------|-------------|
| `parse` | Connections extracted from input text |
| `layout` | Layer assignments, node positions, back edges identified |
| `dimensions` | Box dimensions (width, height) calculated for each node |
| `positions` | Canvas coordinates calculated for each box |
| `canvas_created` | Initial empty canvas created |
| `boxes_drawn` | All node boxes rendered |
| `forward_edges_drawn` | Forward edges rendered (normal flow) |
| `back_edges_drawn` | Back edges rendered (cycles) |

### Character Placement Reasons

Each character placement includes a reason string. Common reasons:

| Reason | Meaning |
|--------|---------|
| `vertical_line` | Drawing vertical edge segment |
| `horizontal_line` | Drawing horizontal edge segment |
| `corner_top_left` | Placing ┌ corner |
| `corner_bottom_right` | Placing ┘ corner |
| `upgrade_left_corner_to_tee_right` | ┌ or └ + vertical = ├ |
| `upgrade_horizontal_to_tee_down` | ─ + corner = ┬ |
| `vertical_crosses_horizontal` | Creating ┼ intersection |
| `merge_corners_to_tee_*` | Two corners combining |
| `arrow_down` | Placing ▼ arrow |
| `source_exit_port` | Marking box exit point with ┬ |
| `fanout_junction` | Fan-out junction point |

### TracedCanvas

The `TracedCanvas` wraps a regular `Canvas` and intercepts all character placements:

```python
from retroflow.renderer import Canvas
from retroflow.tracer import RenderTrace
from retroflow.debug import TracedCanvas

canvas = Canvas(80, 40)
trace = RenderTrace()
traced = TracedCanvas(canvas, trace)

# Set the current source context
traced.set_source("MyModule.my_method")

# All set() calls are now recorded
traced.set(10, 5, "│", reason="my_vertical_line")

# Check what was recorded
print(trace.character_placements[-1])
```

### visual_diff Utility

For comparing expected vs actual output:

```python
from retroflow.debug import visual_diff

expected = "┌───┐\n│ A │\n└───┘"
actual = "┌───┐\n│ B │\n└───┘"

print(visual_diff(expected, actual))
# Shows exactly where characters differ
```

### CanvasInspector Utility

For analyzing canvas contents:

```python
from retroflow.debug import CanvasInspector

inspector = CanvasInspector(canvas)

# Find all positions of a character
corners = inspector.find_char("┌")

# Count line-drawing characters
counts = inspector.get_line_chars_count()

# Extract a region
region = inspector.get_region(x=5, y=3, width=10, height=5)
```

### Best Practices for Debugging

1. **Start with trace.summary()** - Get an overview of what happened
2. **Use get_placements_at()** - When a specific position looks wrong, see all placements there
3. **Use get_character_upgrades()** - To find all merge/upgrade operations
4. **Use dump_canvas_evolution()** - To see how the canvas built up stage by stage
5. **Filter by source** - To isolate placements from a specific method
6. **Write targeted tests** - Use traces to verify specific rendering decisions

### Adding Reasons to New Code

When adding new rendering code, include reason parameters:

```python
# Good - with reason
canvas.set(x, y, LINE_CHARS["vertical"], "my_new_vertical_segment")

# Also acceptable - TracedCanvas will infer a basic reason
canvas.set(x, y, LINE_CHARS["vertical"])
```
