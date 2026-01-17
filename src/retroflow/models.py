"""
Data models for flowchart generation.

This module contains dataclasses that represent layout boundaries
used throughout the flowchart generation process. These models encapsulate the
geometric information needed for positioning nodes and routing edges.

Classes:
    LayerBoundary: Boundary information for a horizontal layer (TB mode).
    ColumnBoundary: Boundary information for a vertical column (LR mode).
"""

from dataclasses import dataclass


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
