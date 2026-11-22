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
- **Planned routing for complex diagrams**: Busy diagrams are routed as a whole (ports, lanes, tracks) so unrelated edges never share a cell
- **Self-checking output**: A checker reads every rendering back and decides which renderer's picture is returned
- **Cycle detection**: Handles cyclic graphs gracefully with back-edge routing
- **Customizable**: Adjust text width, box sizes, spacing, shadows, and fonts
- **Unicode box-drawing**: Beautiful boxes with optional shadow effects
- **Title banners**: Optional double-line bordered titles with automatic word wrapping (at ~15 chars)
- **Horizontal flow**: Left-to-right layout mode (`direction="LR"`) for compact diagrams
- **Group boxes**: Visually cluster related nodes within dashed-border containers with titles


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
│   ├── edge_drawing.py      # Classic edge rendering for TB and LR modes
│   ├── route_planner.py     # Planned renderer: ranks, lanes, ports, positions
│   ├── channel_router.py    # Track assignment for the gap between two layers
│   ├── wire_grid.py         # Glyphs computed from the lines in each cell
│   ├── checker.py           # Reads a rendering back; gate between renderers
│   ├── export.py            # PNG and text file export functionality
│   ├── tracer.py            # Debug tracing infrastructure (RenderTrace, etc.)
│   ├── debug.py             # Debug utilities (TracedCanvas, visual_diff, etc.)
│   └── py.typed             # PEP 561 type marker
├── tests/
│   ├── conftest.py          # Shared pytest fixtures
│   ├── unit/                # One module per source module
│   └── integration/
│       ├── diagram_corpus.py            # Simple, complex and random diagrams
│       ├── diagram_checker.py           # check_diagram / check_planned_diagram
│       ├── diagram_scorecard.py         # Clean/defect summary for the corpus
│       ├── golden/                      # Pinned output of the simple diagrams
│       ├── test_simple_diagram_goldens.py
│       ├── test_complex_diagrams.py     # Complex diagrams via generate()
│       ├── test_planned_renderer.py     # Planned renderer on its own + fuzzing
│       └── test_diagram_checker.py      # The checker, on hand-drawn pictures
├── manual_tests/
│   ├── render_corpus.py     # Writes every simple + complex diagram to .txt
│   └── output/              # Generated files (gitignored)
├── codecov.yml              # Coverage threshold config (90%)
├── pyproject.toml           # Package metadata and dependencies
├── README.md                # User documentation
└── CLAUDE.md                # Developer/agent guidance (this current file)
```

### Key Source Files

| File | Purpose |
|------|---------|
| `generator.py` | Main `FlowchartGenerator` class - runs the classic renderer, checks the result, falls back on the planned renderer; also export |
| `parser.py` | Parses `A -> B` text syntax into connection tuples; also parses group definitions (`[GROUP: nodes]`) |
| `layout.py` | `NetworkXLayout` class using networkx for graph representation, cycle detection, topological sorting, and barycenter-based node ordering. `SugiyamaLayout` is an alias for backwards compatibility. |
| `renderer.py` | `Canvas` for 2D character grid, `BoxRenderer` for Unicode box drawing with shadows, `GroupBoxRenderer` for dashed group boxes, `LineRenderer` for edge drawing utilities |
| `router.py` | `EdgeRouter` for port allocation and orthogonal edge routing (utility module for future use) |
| `models.py` | Data models for layout boundaries (`LayerBoundary`, `ColumnBoundary`) and group definitions (`GroupDefinition`, `GroupBoundary`) |
| `positioning.py` | `PositionCalculator` class for calculating node positions, layer/column boundaries, port positions, and group-aware positioning |
| `edge_drawing.py` | `EdgeDrawer` class for rendering forward and back edges in TB and LR modes (classic renderer) |
| `route_planner.py` | `RoutePlanner` plans a whole diagram as data (`RoutePlan`): layers, lanes, order, ports, hooks, positions, tracks, wires. Also `assign_ranks`, `spread_offsets`, `settle` |
| `channel_router.py` | `route_channel` gives every connection in one gap its own track; splits pieces with a jog when ordering rules contradict |
| `wire_grid.py` | `WireGrid` stores arms per cell per net and looks glyphs up from them; reports conflicts instead of drawing misleading junctions |
| `checker.py` | `analyze_rendering` reads a finished picture back into edges and reports `Issue`s (`DiagramReport`) |
| `export.py` | `FlowchartExporter` class for PNG and text file export with font handling |
| `tracer.py` | Debug tracing infrastructure - `RenderTrace`, `PipelineStage`, `CharacterPlacement` for capturing rendering decisions |
| `debug.py` | Debug utilities - `TracedCanvas` wrapper, `visual_diff`, `CanvasInspector` for debugging and analysis |


## Two Renderers and a Gate

```
input ──► classic renderer ──► checker: clean? ── yes ──► returned unchanged
                                      │ no
                                      ▼
          planned renderer ──► checker: better than classic? ──► returned
```

`FlowchartGenerator.generate()` always runs the **classic** renderer first
(`_render_classic`: `PositionCalculator` + `EdgeDrawer`). It draws one edge at
a time with the canvas as its only memory, which gives small diagrams their
familiar look and is why busy diagrams used to come out with fused lines.

The result is read back by `checker.analyze_rendering`. If it has no errors
and no warnings it is returned as is, so **anything the classic renderer draws
cleanly is byte-identical to before** (32 golden files in
`tests/integration/golden/` pin this). Otherwise the **planned** renderer
(`_render_planned`: `RoutePlanner` + `WireGrid`) draws the diagram, and its
picture is used when it checks out better: fewer errors, then fewer warnings.
A crash inside the planner also falls back to the classic picture.
`generator.last_renderer` is `"classic"` or `"planned"` after each call.

### The checker (`checker.py`)

The checker compares the canvas after boxes were drawn with the finished
canvas, so everything that differs is edge drawing. It follows line glyphs by
their arms and reads off which boxes each line connects. It never looks at
renderer internals.

| Code | Meaning |
|------|---------|
| `phantom_edge` / `missing_edge` | The picture shows an edge that is not in the input / an input edge cannot be traced |
| `stray_line`, `dangling_line`, `dangling_port` | A line without a source or arrowhead, or an arm reaching toward nothing |
| `floating_arrow`, `arrow_no_tail`, `arrow_hit_sideways` | Arrowhead defects |
| `box_missing`, `box_damaged`, `group_border_damaged` | Boxes, titles or group borders overwritten |
| `adjacent_lines` (warning) | Unrelated vertical strokes in touching columns |

### The planned renderer (`route_planner.py`)

```
ranks ──► lanes ──► order ──► ports ──► positions ──► tracks ──► wire grid
└──────────────────── pure data, no canvas ───────────────────┘
```

Five rules, each of which the tests check directly:

1. A glyph is computed from the arms in its cell; arms only come from route segments (`WireGrid`).
2. Edges share a line only as a *star* (one source fanning out, or several sources into one target), so a shared line never implies an edge that was not asked for.
3. One allocator per box side hands out ports for all edges on that side; boxes grow when a side is too short.
4. Every segment lies in space reserved for it: a lane beside the boxes it passes, a track in the channel between two layers. The canvas is sized from the routes.
5. Every ordering is total and derived from input order (no iteration over sets of names).

Everything is planned in **flow coordinates** (`flow` along the diagram,
`cross` across it), so LR is the same code as TB with the axes swapped. Only
`_Metrics` (pitches and gaps) and the final `_cell()` conversion differ.

How an edge attaches to a box (`_Edge.src_mode` / `dst_mode`):

| Mode | Meaning | Used for |
|------|---------|----------|
| `F` | Port on the side facing the flow, ending in a channel | All forward edges in TB; edges between neighbouring columns in LR |
| `X` | Hook from a lane right beside the box into a side that runs along the flow | Back-edge and self-loop targets in TB (`┌───►│ box │`); skip and back edges in LR (top and bottom borders) |
| `A` | Arc: re-enters on the side it left from, arrowhead pointing against the flow | Edges between non-neighbouring boxes of one group; self loops inside groups |
| `D` | Direct line between two neighbouring boxes of one layer | Neighbouring group members |

Other things worth knowing before changing the planner:

- **TB gives every edge its own port and arrowhead; LR shares lines.** A compact LR box has one row per facing side, so adjacent-column edges are bundled into stars and everything else goes to the top and bottom borders. A box never grows taller unless it is inside a group (where its top and bottom face other members).
- **Lanes** (`_Lane`) are one layer's worth of an edge travelling past boxes. Hooked lanes must stay adjacent to their box (`_place_anchored_lanes`); free lanes follow barycenter sweeps.
- **LR arcs pick a side** (`_choose_lane_sides`): forward skips default to below the row, back edges to above, and an arc flips sides when that avoids interleaving with arcs already placed.
- **Cross positions** (`_assign_cross_positions`) use `settle()` (pool-adjacent-violators): boxes line up middle-to-middle with the boxes they connect to, lanes follow lanes, and the last pass works outward from the widest layer so symmetric diagrams stay symmetric. `_straighten_ports` then slides lone ports to make lines straight.
- **Channels** (`channel_router.route_channel`): pieces whose spans overlap get different tracks; a stub above another piece's stub forces their order; contradictory orders are broken by splitting a piece with a jog; remaining freedom goes to the order with fewer crossings. A same-net four-way meeting is split into two tees, because `┼` must always mean "crossing".
- **Gaps keep their classic size** when their tracks fit and grow only for extra tracks (`_assign_flow_positions`), so planned diagrams look like classic ones where nothing is contested.
- **Groups**: all members of a group share a layer (`assign_ranks` collapses groups first) and stay contiguous. Grouped boxes only use `F`, `A` and `D`. In TB the title is placed beside the lines entering the group from above (`_group_title_start`), and the group is widened if no gap is long enough.

### Debugging a diagram

```bash
uv run python tests/integration/diagram_scorecard.py -v      # every corpus diagram
uv run python tests/integration/diagram_scorecard.py cicd-TB # one diagram + issues
```

To look at the pictures themselves, render the corpus to text files:

```bash
uv run python manual_tests/render_corpus.py              # all simple + complex
uv run python manual_tests/render_corpus.py cicd groups  # names containing either
```

Files land in `manual_tests/output/simple/` and `manual_tests/output/complex/`,
one per diagram and direction (`<case>-<direction>.txt`). Each one starts with a
header (case, direction, options, which renderer won, the input text) followed
by the diagram exactly as `generate()` returns it. An unfiltered run deletes the
old files first. The output folder is gitignored; the script has a smoke test
in `tests/integration/test_manual_render_script.py`.

```python
generator = FlowchartGenerator(direction="LR")
generator.generate(text, debug=True)
generator.last_renderer                      # which renderer won
trace = generator.get_trace()
trace.get_stage("renderer_selected").data    # issues of both renderers
trace.get_stage("routes_planned").data       # layers, tracks per channel, conflicts

# Force the planned renderer, bypassing the gate (tests do this):
parsed = generator.parser.parse_with_groups(text)
output, boxes_only = generator._render_planned(parsed, None, None)
```

`tests/integration/diagram_checker.py` has `check_diagram` (through the gate)
and `check_planned_diagram` (planned renderer only); both return a
`DiagramReport` whose `explain()` prints the issues above the picture.

### Tests for diagrams

- `diagram_corpus.py` holds every diagram: `SIMPLE_CASES` (pinned by goldens), `COMPLEX_CASES` (graph families, cycles, real-world diagrams, an options matrix, groups) and `RANDOM_CASES` (seeded, some with random options and groups). Every case runs in TB and LR. **Add new shapes here**; all test modules pick them up.
- A new diagram that must stay byte-identical goes in `SIMPLE_CASES`; regenerate with `RETROFLOW_UPDATE_GOLDENS=1 uv run pytest -k goldens` and review the diff.
- `test_planned_renderer.py` also fuzzes the planner with 300 seeded random graphs, groups and option sets. Use only `Random.random()` in generators so a seed means the same diagram on every Python version.


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
| `forward_edges_drawn` | Forward edges rendered (normal flow; classic renderer) |
| `back_edges_drawn` | Back edges rendered (cycles; classic renderer) |
| `routes_planned` | Layers, tracks per channel, crossings and wire conflicts (planned renderer) |
| `edges_drawn` | All wires painted (planned renderer) |
| `renderer_selected` | Which renderer's picture was returned, and the checker's issue counts for both |

The trace returned by `get_trace()` always belongs to the renderer whose
picture was returned.

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
| `wire_horizontal`, `wire_vertical`, `wire_corner`, `wire_junction`, `wire_crossing` | Glyphs painted from the wire grid (planned renderer) |
| `exit_port` | Port mark where a planned line leaves a box |

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


## Group Box Feature

Group boxes allow users to visually cluster related nodes together within a labeled container. This makes diagrams easier to read and understand, especially when depicting systems with distinct subsystems or logical groupings.

### Syntax

Groups are defined at the top of input text, **before** edge definitions:

```
[GROUP TITLE: node1 node2 node3]
[ANOTHER GROUP: nodeA nodeB]

node1 -> node2
node2 -> node3
nodeA -> nodeB
node3 -> nodeA
```

- Text before the colon is the **group title** (centered above the group box)
- Text after the colon is a **space-separated list of node names**
- Multi-word node names are supported (matched against nodes found in edges)
- Group definitions must appear before any edge definitions

### Example Usage

```python
from retroflow import FlowchartGenerator

generator = FlowchartGenerator()

result = generator.generate("""
[API Layer: Gateway Auth]
[Data Layer: Database Cache]

Gateway -> Auth
Auth -> Database
Database -> Cache
Gateway -> Cache
""")

print(result)
```

### Visual Appearance

Group boxes have:
- **Dashed borders**: Using `┄` (horizontal) and `┆` (vertical) characters
- **Solid corners**: Standard box-drawing corners (┌ ┐ └ ┘) for clarity
- **Shadows**: On right and bottom edges (same as node boxes, can be disabled)
- **Centered title**: Displayed above the group box

Example output:
```
     API LAYER
┌┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┐
┆                   ┆░
┆  ┌───────────┐    ┆░
┆  │  Gateway  │░   ┆░
┆  └───────────┘░   ┆░
┆    ░░░░░░░░░░░░   ┆░
┆        │          ┆░
┆        ▼          ┆░
┆  ┌───────────┐    ┆░
┆  │   Auth    │░   ┆░
┆  └───────────┘░   ┆░
┆    ░░░░░░░░░░░░   ┆░
└┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘░
 ░░░░░░░░░░░░░░░░░░░░░
```

### Layout Behavior

| Flow Direction | Node Arrangement Within Groups |
|---------------|-------------------------------|
| **TB (Top-to-Bottom)** | Nodes arranged **horizontally** (side-by-side) |
| **LR (Left-to-Right)** | Nodes arranged **vertically** (stacked) |

Nodes are arranged **perpendicular to the flow direction** within groups, making groups visually compact.

### Validation Rules

- A node can belong to **at most one group** (enforced during parsing)
- All group members must exist in at least one edge definition
- Group definitions must appear before edge definitions in the input

### Data Models

| Class | Location | Purpose |
|-------|----------|---------|
| `GroupDefinition` | `models.py` | Parsed group from input (name, members, order) |
| `GroupBoundary` | `models.py` | Calculated boundaries for rendering (x, y, width, height, title position) |
| `ParseResult` | `parser.py` | Combined result of parsing (connections + groups) |

### Implementation Files

| File | Group-Related Changes |
|------|----------------------|
| `parser.py` | `parse_with_groups()` method, group syntax parsing, multi-word node matching |
| `positioning.py` | `calculate_group_aware_positions()`, `calculate_group_boundaries()`, `resolve_group_overlaps()` |
| `renderer.py` | `GroupBoxRenderer` class, `DASHED_BOX_CHARS` constants |
| `generator.py` | Group orchestration in `_render_classic()` / `_render_planned()`, `_draw_groups()` method |
| `route_planner.py` | Planned renderer: `assign_ranks()` (groups share a layer), group extents, title placement, direct lines and arcs inside groups |
| `models.py` | `GroupDefinition`, `GroupBoundary` dataclasses |
