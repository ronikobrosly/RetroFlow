"""
Data models for flowchart generation.

This module contains dataclasses that represent layout boundaries and group
definitions used throughout the flowchart generation process. These models
encapsulate the geometric information needed for positioning nodes and routing
edges, as well as group box specifications.

Classes:
    LayerBoundary: Boundary information for a horizontal layer (TB mode).
    ColumnBoundary: Boundary information for a vertical column (LR mode).
    GroupDefinition: Definition of a node group from parsed input.
    GroupBoundary: Calculated boundaries for a rendered group box.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class LayerBoundary:
    """
    Boundary information for a horizontal layer in top-to-bottom (TB) mode.

    Used for safe edge routing - horizontal edge segments should be placed
    in the gaps between layers where no boxes exist.

    Attributes:
        layer_idx: Index of this layer (0-based from top).
        top_y: Y coordinate where boxes in this layer start.
        bottom_y: Y coordinate of the bottom of boxes (including shadow).
        gap_start_y: Y coordinate where the gap below this layer begins.
        gap_end_y: Y coordinate where the gap ends (start of next layer).
    """

    layer_idx: int
    top_y: int
    bottom_y: int
    gap_start_y: int
    gap_end_y: int


@dataclass
class ColumnBoundary:
    """
    Boundary information for a vertical column in left-to-right (LR) mode.

    Used for safe edge routing - vertical edge segments should be placed
    in the gaps between columns where no boxes exist.

    Attributes:
        layer_idx: Index of this column/layer (0-based from left).
        left_x: X coordinate where boxes in this column start.
        right_x: X coordinate of the right edge of boxes (including shadow).
        gap_start_x: X coordinate where the gap to the right begins.
        gap_end_x: X coordinate where the gap ends (start of next column).
    """

    layer_idx: int
    left_x: int
    right_x: int
    gap_start_x: int
    gap_end_x: int


@dataclass
class GroupDefinition:
    """
    Definition of a node group from parsed input.

    Groups are specified in the input text using syntax like:
    [GROUP NAME: node1 node2 node3]

    Attributes:
        name: Group title/label to display above the group box.
        members: List of node names that belong to this group.
        order: Order in which group was defined (for z-ordering when rendering).
    """

    name: str
    members: List[str] = field(default_factory=list)
    order: int = 0


@dataclass
class GroupBoundary:
    """
    Calculated boundaries for a rendered group box.

    This is computed after node positions are determined, based on the
    bounding box of all member nodes plus padding.

    Attributes:
        name: Group title.
        members: Node names in this group.
        x: Left edge x-coordinate of the group box (content area).
        y: Top edge y-coordinate (below title).
        width: Width of group box.
        height: Height of group box (not including title).
        title_x: X position for centered title.
        title_y: Y position for title (above box).
        title_width: Width of title text.
    """

    name: str
    members: List[str] = field(default_factory=list)

    # Canvas coordinates (calculated during positioning)
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    # Title positioning
    title_x: int = 0
    title_y: int = 0
    title_width: int = 0
