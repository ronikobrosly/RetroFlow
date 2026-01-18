# Group Box Implementation Plan

## Overview

This document describes the implementation plan for adding **group boxes** to RetroFlow. Group boxes allow users to visually cluster related nodes together within a labeled container, making diagrams easier to read and understand.

A good example of an isolated group box:

```
     GROUP TITLE
┌┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┐
┆                   ┆░
┆  ┌───────────┐    ┆░
┆  │  NODE A   │░   ┆░
┆  └───────────┘░   ┆░
┆    ░░░░░░░░░░░░   ┆░
┆        │          ┆░
┆        ▼          ┆░
┆  ┌───────────┐    ┆░
┆  │  NODE B   │░   ┆░
┆  └───────────┘░   ┆░
┆    ░░░░░░░░░░░░   ┆░
└┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘░
 ░░░░░░░░░░░░░░░░░░░░░
```

---

## Requirements Summary

### Syntax

Groups are defined at the top of input text, before edge definitions:

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

### Visual Requirements

| Requirement | Description |
|-------------|-------------|
| Border style | Dashed lines using `┄` or `╌` characters (horizontal) and `┆` or `╎` (vertical) |
| Shadows | Group boxes have shadows on right and bottom edges (same as text boxes) |
| Title | Centered text positioned on the top edge of the group box |
| Padding | Internal padding between group border and contained nodes |
| Node styling | Nodes inside groups retain their normal styling (solid border, shadow) |

### Layout Requirements

See the `grouped_boxes.png` image for an example of a clean layout with group boxes. 

1. **Group hierarchy takes priority**: Nodes within a group are positioned together, even if the global graph structure would place them in different layers
2. **Single membership**: A node can belong to at most one group (enforced during parsing)
3. **Ungrouped node margins**: When groups exist, ungrouped nodes receive extra margin to prevent visual crowding
4. **Both directions**: Works in TB (top-to-bottom) and LR (left-to-right) modes
5. **No overlapping**: VERY IMPORTANT: Under no circumstances should text boxes overlap or sit too closely with each other, no group boxes should overlap or sit too closely with each other, and no group box boundaries should overlap or sit too closely with text boxes. 

---

## Architecture Changes

### New Files

| File | Purpose |
|------|---------|
| `src/retroflow/groups.py` | Group data models and group-aware layout utilities |

### Modified Files

| File | Changes |
|------|---------|
| `parser.py` | Parse group definitions from input text |
| `layout.py` | Group-aware layer assignment |
| `positioning.py` | Calculate group bounding boxes and add group padding |
| `renderer.py` | Add `GroupBoxRenderer` class for dashed boxes |
| `generator.py` | Orchestrate group parsing, layout, and rendering |
| `models.py` | Add `GroupDefinition` and `GroupBoundary` models |

---

## Data Models

### GroupDefinition (in `models.py`)

```python
@dataclass
class GroupDefinition:
    """Definition of a node group from parsed input."""

    name: str                    # Group title/label
    members: List[str]           # List of node names in this group
    order: int                   # Order in which group was defined (for z-ordering)
```

### GroupBoundary (in `models.py`)

```python
@dataclass
class GroupBoundary:
    """Calculated boundaries for a rendered group box."""

    name: str                    # Group title
    members: List[str]           # Node names in this group

    # Canvas coordinates (calculated during positioning)
    x: int                       # Left edge (content area, not including title)
    y: int                       # Top edge (below title)
    width: int                   # Width of group box
    height: int                  # Height of group box (not including title)

    # Title positioning
    title_x: int                 # X position for centered title
    title_y: int                 # Y position for title (above box)
    title_width: int             # Width of title text
```

### ParseResult (new, in `parser.py`)

```python
@dataclass
class ParseResult:
    """Result of parsing input text."""

    connections: List[Tuple[str, str]]  # Edge connections
    groups: List[GroupDefinition]        # Group definitions
```

---

## Implementation Phases

### Phase 1: Parsing (parser.py)

#### 1.1 Extend Parser to Recognize Group Syntax

**Input format:**
```
[GROUP NAME: node1 node2 node3]
```

**Parsing logic:**
1. Scan lines at the beginning of input for group definitions
2. Group definition regex: `^\s*\[([^:]+):\s*(.+)\]\s*$`
3. Extract group name (before colon) and member list (after colon)
4. Member list is space-separated, but must handle multi-word node names

**Challenge: Multi-word node names**

The syntax `[MY GROUP: Node One Node Two Node Three]` is ambiguous. We need a strategy:

**Strategy A (Recommended):** Two-pass parsing
1. First, parse all edges to discover all valid node names
2. Then, parse group member lists by matching against known node names
3. Use greedy matching (longest match first) for multi-word names

**Strategy B:** Require quoted node names in groups
```
[MY GROUP: "Node One" "Node Two"]
```

**Recommendation:** Use Strategy A to maintain syntax simplicity.

#### 1.2 Validation

- Error if a node appears in multiple groups
- Warning if a group references a node that doesn't exist in any edge
- Error if group definition appears after edge definitions (enforce order)

#### 1.3 New Parser API

```python
class Parser:
    def parse(self, input_text: str) -> ParseResult:
        """Parse input text into connections and groups."""
        ...

    def _parse_groups(self, lines: List[str], all_nodes: Set[str]) -> List[GroupDefinition]:
        """Parse group definitions, matching against known nodes."""
        ...

    def _match_node_names(self, member_text: str, known_nodes: Set[str]) -> List[str]:
        """Match member text against known node names (greedy longest-first)."""
        ...
```

---

### Phase 2: Layout (layout.py)

#### 2.1 Group-Aware Layer Assignment

The current layout uses topological sorting to assign layers. With groups, we need to modify this:

**Current behavior:**
- Each node gets assigned to a layer based on its predecessors
- Layer = max(predecessor layers) + 1

**New behavior with groups:**
1. Calculate "natural" layers for all nodes (as currently done)
2. For each group, determine the group's layer span:
   - `group_min_layer = min(node.layer for node in group.members)`
   - `group_max_layer = max(node.layer for node in group.members)`
3. **Compress group members to top of span**: Move all group members to start at `group_min_layer`
4. Re-calculate internal ordering within the group
5. Adjust downstream nodes if needed

**Example:**

Before group adjustment:
```
Layer 0: [A]           (A is in GROUP1)
Layer 1: [B, X]        (B is in GROUP1, X is ungrouped)
Layer 2: [C]           (C is in GROUP1)
```

After group adjustment (GROUP1 members compressed):
```
Layer 0: [A, B, C]     (all GROUP1 members)
Layer 1: [X]           (ungrouped, shifted down if needed)
```

#### 2.2 Intra-Group Ordering

Within a group, nodes should be ordered to minimize edge crossings (using existing barycenter heuristic), but constrained to stay within the group's layer span.

#### 2.3 Modified LayoutResult

```python
@dataclass
class LayoutResult:
    nodes: Dict[str, NodeLayout]
    layers: List[List[str]]
    edges: List[Tuple[str, str]]
    back_edges: Set[Tuple[str, str]]
    has_cycles: bool
    groups: List[GroupDefinition]      # NEW: pass through for positioning
    node_to_group: Dict[str, str]      # NEW: node_name -> group_name mapping
```

---

### Phase 3: Positioning (positioning.py)

#### 3.1 Calculate Group Bounding Boxes

After calculating individual node positions, compute group boundaries:

```python
def calculate_group_boundaries(
    self,
    groups: List[GroupDefinition],
    box_positions: Dict[str, Tuple[int, int]],
    box_dimensions: Dict[str, BoxDimensions],
    padding: int = 2,
    title_height: int = 1,
) -> List[GroupBoundary]:
    """
    Calculate bounding boxes for each group.

    For each group:
    1. Find min/max x and y of all member nodes (including their shadows)
    2. Add internal padding
    3. Calculate title position (centered above)
    """
```

#### 3.2 Add Group Padding to Spacing

When groups exist, modify spacing calculations:

```python
# Constants for group spacing
GROUP_INTERNAL_PADDING = 2      # Space between group border and nodes
GROUP_EXTERNAL_MARGIN = 3       # Space between group box and adjacent elements
GROUP_TITLE_HEIGHT = 1          # Height reserved for group title
```

#### 3.3 Adjust Canvas Size

Canvas size calculation must account for:
- Group box borders and shadows
- Group titles above boxes
- Extra margins around groups

---

### Phase 4: Rendering (renderer.py)

#### 4.1 Dashed Box Characters

Add new character sets for dashed lines:

```python
# Dashed box-drawing characters
DASHED_BOX_CHARS = {
    "horizontal": "┄",           # or "╌" for lighter dashes
    "vertical": "┆",             # or "╎" for lighter dashes
    "top_left": "┌",             # Corners remain solid for clarity
    "top_right": "┐",
    "bottom_left": "└",
    "bottom_right": "┘",
    "shadow": "░",
}
```

#### 4.2 GroupBoxRenderer Class

```python
class GroupBoxRenderer:
    """Renders group boxes with dashed borders and shadows."""

    def __init__(self, shadow: bool = True):
        self.shadow = shadow
        self.chars = DASHED_BOX_CHARS

    def draw_group_box(
        self,
        canvas: Canvas,
        boundary: GroupBoundary,
    ) -> None:
        """
        Draw a group box with:
        - Dashed border
        - Shadow on right and bottom
        - Centered title on top edge
        """
        ...

    def _draw_title_on_border(
        self,
        canvas: Canvas,
        x: int,
        y: int,
        title: str,
        box_width: int,
    ) -> None:
        """Draw title text centered on the top border line."""
        # Title sits on the top border, breaking the dashed line
        # Example: ┌─ MY GROUP ─┐
        ...
```

#### 4.3 Drawing Order

Groups must be drawn **before** node boxes so nodes appear "on top":

```
1. Draw group boxes (dashed borders, shadows, titles)
2. Draw node boxes (solid borders, shadows, text)
3. Draw edges (lines, arrows)
```

---

### Phase 5: Generator Integration (generator.py)

#### 5.1 Updated Generate Pipeline

```python
def generate(self, input_text: str, title: Optional[str] = None, debug: bool = False) -> str:
    # 1. Parse input (now returns ParseResult with groups)
    parse_result = self.parser.parse(input_text)
    connections = parse_result.connections
    groups = parse_result.groups

    # 2. Run layout (now group-aware)
    layout_result = self.layout_engine.layout(connections, groups)

    # 3. Calculate box dimensions
    box_dimensions = self.position_calculator.calculate_all_box_dimensions(layout_result)

    # 4. Calculate positions (with group padding)
    box_positions = self.position_calculator.calculate_positions(
        layout_result, box_dimensions, groups=groups
    )

    # 5. Calculate group boundaries
    group_boundaries = self.position_calculator.calculate_group_boundaries(
        groups, box_positions, box_dimensions
    )

    # 6. Create canvas
    canvas = Canvas(width, height)

    # 7. Draw groups FIRST (so nodes draw on top)
    self._draw_groups(canvas, group_boundaries)

    # 8. Draw node boxes
    self._draw_boxes(canvas, box_dimensions, box_positions, layout_result)

    # 9. Draw edges
    self._draw_edges(canvas, ...)

    return canvas.render()
```

---

### Phase 6: Edge Routing Considerations

#### 6.1 Edges Crossing Group Boundaries

Edges that connect nodes in different groups (or grouped to ungrouped) must cross group boundaries. The current edge routing should handle this naturally since it routes around boxes, not groups.

**No special handling needed** - edges will route through the group's internal padding space.

#### 6.2 Intra-Group Edges

Edges between nodes within the same group should route normally. The group box is drawn first, so edge lines will appear on top of the dashed border (which is fine visually).

#### 6.3 Back Edges

Back edges (cycle edges) currently route along the left margin (TB) or top margin (LR). This should continue to work with groups, but may need adjustment if a back edge's source/target is inside a group.

**Potential issue:** Back edge margin calculation will absolutely need to account for group box width.

---

## Testing Strategy

### Unit Tests

| Test Area | Test Cases |
|-----------|------------|
| Parser | Group syntax parsing, multi-word node matching, validation errors |
| Layout | Group compression, intra-group ordering, ungrouped node handling |
| Positioning | Group boundary calculation, padding, canvas sizing |
| Rendering | Dashed box drawing, title centering, shadow rendering |

### Integration Tests

1. **Basic group** - Single group with 2-3 nodes
2. **Multiple groups** - Two or more non-overlapping groups
3. **Mixed** - Some nodes grouped, some ungrouped
4. **Groups spanning layers** - Group members at different natural layers
5. **Edges crossing groups** - Connections between groups
6. **Large groups** - Groups with 5+ nodes
7. **LR mode** - All above tests in horizontal orientation
8. **With cycles** - Groups containing nodes involved in back edges
9. **Long titles** - Group titles that need wrapping or truncation

### Visual Regression Tests

Use the existing `extensive_retroflow_testing.py` tests 41-81 as the baseline. These should produce valid output once the feature is implemented. Ensure that the output files of these tests don't contain broken arrow lines (AKA edges), that there aren't free floating arrows or missing arrows, and that no boxes (whether group or text boxes) overlap.

---

## Potential Problems and Mitigations

### Problem 1: Multi-Word Node Name Ambiguity

**Issue:** `[GROUP: Node One Node Two]` - is this two nodes "Node One" and "Node Two", or three nodes "Node", "One Node", "Two"?

**Mitigation:** Two-pass parsing with greedy longest-match against known node names from edges.

### Problem 2: Group Member Not in Any Edge

**Issue:** User defines `[GROUP: A B C]` but node `C` never appears in any edge.

**Mitigation:**
- Warn but don't error (node might be intentionally orphaned)
- Still include the node in the group's bounding box
- Node won't be drawn (no box) but title still shows

**Alternative:** Error and require all group members to exist in edges.

### Problem 3: Group Layout Conflicts with Edge Minimization

**Issue:** Compressing group members to the same layer region may increase edge crossings.

**Mitigation:** Accept this trade-off. Group visual clustering takes priority over global edge crossing minimization. Document this behavior.

### Problem 4: Very Long Group Titles

**Issue:** Title like "FASTAPI ML MICROSERVICE WITH AUTHENTICATION" may be wider than the group contents.

**Mitigation:**
- Expand group box width to fit title
- Or truncate/wrap title (with "..." if truncated)

**Recommendation:** Expand box to fit title (more readable).

### Problem 5: Empty Groups

**Issue:** Group defined but all members removed from edges.

**Mitigation:** Skip rendering empty groups. Warn during parsing.

### Problem 6: Overlapping Groups (Visually)

**Issue:** Two groups whose members are interspersed in the layout may produce overlapping boxes.

**Mitigation:** The group-aware layout (Phase 2) should prevent this by clustering group members. If it still happens, this is an edge case we accept for v1.

### Problem 7: Performance with Many Groups

**Issue:** Many groups with many members could slow down positioning.

**Mitigation:** The algorithm is O(n) per group for boundary calculation, which should be fine for reasonable diagram sizes. Not a concern for v1.

---

## Implementation Order

Recommended order for implementing phases:

1. **Phase 1 (Parser)** - Can be tested independently
2. **Phase 4 (Renderer)** - Implement `GroupBoxRenderer`, test with hardcoded boundaries
3. **Phase 3 (Positioning)** - Calculate boundaries from real positions
4. **Phase 5 (Generator)** - Wire everything together (basic version)
5. **Phase 2 (Layout)** - Group-aware layer assignment (most complex)
6. **Phase 6 (Edges)** - Verify/fix edge routing with groups
7. **Polish** - Debug tracing, error messages, documentation

---

## Success Criteria

The feature is complete when:

1. All 40 grouped tests (41-81) in `extensive_retroflow_testing.py` produce valid, readable output
2. Grouped diagrams render correctly in both TB and LR modes
3. Edges route cleanly across group boundaries
4. Test coverage remains above 90%
5. No regressions in non-grouped diagrams (tests 0-40)
6. `grouped_boxes.png` can be reproduced from equivalent input text

---

## ASCII Art Reference

### Dashed Box with Shadow

```
     GROUP TITLE
┌┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┐
┆                   ┆░
┆  ┌───────────┐    ┆░
┆  │  NODE A   │░   ┆░
┆  └───────────┘░   ┆░
┆    ░░░░░░░░░░░░   ┆░
┆        │          ┆░
┆        ▼          ┆░
┆  ┌───────────┐    ┆░
┆  │  NODE B   │░   ┆░
┆  └───────────┘░   ┆░
┆    ░░░░░░░░░░░░   ┆░
└┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘░
 ░░░░░░░░░░░░░░░░░░░░░
```

---

## Appendix: Character Reference

### Dashed Line Characters

| Character | Unicode | Name |
|-----------|---------|------|
| ┄ | U+2504 | Box Drawings Light Triple Dash Horizontal |
| ┆ | U+2506 | Box Drawings Light Triple Dash Vertical |
| ╌ | U+254C | Box Drawings Light Double Dash Horizontal |
| ╎ | U+254E | Box Drawings Light Double Dash Vertical |

### Corner Characters (Solid, for Clarity)

| Character | Unicode | Name |
|-----------|---------|------|
| ┌ | U+250C | Box Drawings Light Down and Right |
| ┐ | U+2510 | Box Drawings Light Down and Left |
| └ | U+2514 | Box Drawings Light Up and Right |
| ┘ | U+2518 | Box Drawings Light Up and Left |

---

*Plan version: 1.0*
*Created: January 2026*
*Author: Claude Code + Human collaboration*
