"""
Edge drawing and routing for flowchart generation.

This module handles all edge-related rendering operations including:
- Forward edge drawing for both TB (top-to-bottom) and LR (left-to-right) modes
- Back edge drawing for cyclic graphs in both modes
- Line drawing primitives (horizontal, vertical)
- Corner and junction handling with automatic upgrades to tees and crosses
- Safe routing calculations to avoid crossing through boxes

The EdgeDrawer class centralizes edge rendering logic and is used by the
FlowchartGenerator to draw connections between nodes.
"""

from typing import Dict, List, Tuple

from .layout import LayoutResult
from .models import ColumnBoundary, LayerBoundary
from .positioning import PositionCalculator
from .renderer import ARROW_CHARS, BOX_CHARS, LINE_CHARS, BoxDimensions, Canvas


class EdgeDrawer:
    """
    Draws edges between nodes on the flowchart canvas.

    Handles both forward edges (following the flow direction) and back edges
    (cycles that go against the flow). Supports both TB (top-to-bottom) and
    LR (left-to-right) layout directions.

    Attributes:
        position_calculator: Calculator for port positions.
        shadow: Whether boxes have shadows (affects routing).
    """

    def __init__(
        self,
        position_calculator: PositionCalculator,
        shadow: bool = True,
    ):
        """
        Initialize the edge drawer.

        Args:
            position_calculator: Calculator for port positions.
            shadow: Whether boxes have shadows.
        """
        self.position_calculator = position_calculator
        self.shadow = shadow
        # Track box regions to avoid drawing lines through them
        self._box_regions: List[Tuple[int, int, int, int]] = []  # (x, y, width, height)

    def _set_box_regions(
        self,
        box_positions: Dict[str, Tuple[int, int]],
        box_dimensions: Dict[str, BoxDimensions],
    ) -> None:
        """
        Set the box regions to avoid when drawing lines.

        Args:
            box_positions: Dictionary of box positions.
            box_dimensions: Dictionary of box dimensions.
        """
        self._box_regions = []
        self._box_full_regions: List[Tuple[int, int, int, int]] = []
        for name, (x, y) in box_positions.items():
            dims = box_dimensions[name]
            # Include the box content area (inside borders)
            self._box_regions.append((x + 1, y + 1, dims.width - 2, dims.height - 2))
            # Also track full box regions including borders
            # (for preventing border modification)
            self._box_full_regions.append((x, y, dims.width, dims.height))

    def _is_inside_box(self, x: int, y: int) -> bool:
        """
        Check if a position is inside any box content area.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            True if the position is inside a box content area.
        """
        for bx, by, bw, bh in self._box_regions:
            if bx <= x < bx + bw and by <= y < by + bh:
                return True
        return False

    def _is_on_box_border(self, x: int, y: int) -> bool:
        """
        Check if a position is on any box border (but not a corner).

        Box borders are the `│` and `─` characters that form the box outline.
        We want to avoid modifying these to crosses/tees when edges pass by.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            True if the position is on a box border (excluding corners).
        """
        for bx, by, bw, bh in self._box_full_regions:
            # Left border (excluding corners)
            if x == bx and by < y < by + bh - 1:
                return True
            # Right border (excluding corners)
            if x == bx + bw - 1 and by < y < by + bh - 1:
                return True
            # Top border (excluding corners)
            if y == by and bx < x < bx + bw - 1:
                return True
            # Bottom border (excluding corners)
            if y == by + bh - 1 and bx < x < bx + bw - 1:
                return True
        return False

    def _find_boxes_in_region(
        self,
        box_positions: Dict[str, Tuple[int, int]],
        box_dimensions: Dict[str, BoxDimensions],
        exclude_nodes: set,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
    ) -> List[Tuple[str, int, int, BoxDimensions]]:
        """
        Find all boxes that overlap with a rectangular region.

        Args:
            box_positions: Dictionary of box positions.
            box_dimensions: Dictionary of box dimensions.
            exclude_nodes: Nodes to exclude from the check.
            x_min: Minimum x of the region.
            x_max: Maximum x of the region.
            y_min: Minimum y of the region.
            y_max: Maximum y of the region.

        Returns:
            List of (name, x, y, dims) tuples for boxes that overlap.
        """
        result = []
        for name, (x, y) in box_positions.items():
            if name in exclude_nodes:
                continue
            dims = box_dimensions[name]
            box_right = x + dims.width + (1 if self.shadow else 0)
            box_bottom = y + dims.height + (1 if self.shadow else 0)

            # Check if this box overlaps with the region
            overlaps_x = x < x_max and box_right > x_min
            overlaps_y = y < y_max and box_bottom > y_min

            if overlaps_x and overlaps_y:
                result.append((name, x, y, dims))

        return result

    def draw_edges(
        self,
        canvas: Canvas,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
        layer_boundaries: List[LayerBoundary],
    ) -> None:
        """
        Draw all forward edges on the canvas in TB mode (skip back edges).

        Args:
            canvas: The canvas to draw on.
            layout_result: The layout result with edge information.
            box_dimensions: Dictionary of box dimensions.
            box_positions: Dictionary of box positions.
            layer_boundaries: List of layer boundary information.
        """
        # Set box regions to avoid when drawing lines
        self._set_box_regions(box_positions, box_dimensions)

        # Build lookup for node layers
        node_layer = {name: node.layer for name, node in layout_result.nodes.items()}

        # Group edges by source to allocate ports properly
        edges_from: Dict[str, List[str]] = {}
        edges_to: Dict[str, List[str]] = {}

        for source, target in layout_result.edges:
            # Skip back edges (edges going to earlier or same layer)
            if (source, target) in layout_result.back_edges:
                continue

            src_layer = node_layer.get(source, 0)
            tgt_layer = node_layer.get(target, 0)

            # Only draw forward edges (target layer > source layer)
            if tgt_layer <= src_layer:
                continue

            if source not in edges_from:
                edges_from[source] = []
            edges_from[source].append(target)

            if target not in edges_to:
                edges_to[target] = []
            edges_to[target].append(source)

        # Sort edges for consistent port allocation
        for source in edges_from:
            edges_from[source].sort(key=lambda t: layout_result.nodes[t].position)
        for target in edges_to:
            edges_to[target].sort(key=lambda s: layout_result.nodes[s].position)

        # Draw each forward edge
        for source, target in layout_result.edges:
            if (source, target) in layout_result.back_edges:
                continue

            src_layer = node_layer.get(source, 0)
            tgt_layer = node_layer.get(target, 0)

            if tgt_layer <= src_layer:
                continue

            self._draw_edge(
                canvas,
                source,
                target,
                box_dimensions,
                box_positions,
                edges_from.get(source, []),
                edges_to.get(target, []),
                layer_boundaries,
                src_layer,
                tgt_layer,
                layout_result,
            )

    def _draw_edge(
        self,
        canvas: Canvas,
        source: str,
        target: str,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
        source_targets: List[str],
        target_sources: List[str],
        layer_boundaries: List[LayerBoundary],
        src_layer: int,
        tgt_layer: int,
        layout_result: LayoutResult,
    ) -> None:
        """Draw a single edge from source to target with layer-aware routing."""
        src_dims = box_dimensions[source]
        tgt_dims = box_dimensions[target]
        src_x, src_y = box_positions[source]
        tgt_x, tgt_y = box_positions[target]

        # Check if target and source are at the same y-level (horizontally adjacent)
        # This happens when nodes are grouped together in TB mode
        # Use a tolerance based on the larger box height
        src_bottom = src_y + src_dims.height + (1 if self.shadow else 0)
        tgt_bottom = tgt_y + tgt_dims.height + (1 if self.shadow else 0)

        # Boxes are at "same level" if they overlap vertically
        # (one box's top is within the other's height range)
        boxes_overlap_vertically = (src_y <= tgt_y < src_bottom) or (
            tgt_y <= src_y < tgt_bottom
        )

        if boxes_overlap_vertically:
            # Target and source are at similar y positions (horizontally adjacent)
            # Route horizontally: exit right, go to target, enter from left
            self._draw_edge_tb_stacked(
                canvas,
                source,
                target,
                box_dimensions,
                box_positions,
                source_targets,
                target_sources,
                layout_result,
            )
            return

        # Check if target is above or below source in canvas coordinates
        target_is_below = tgt_y >= src_bottom

        if not target_is_below:
            # Target is above source - route upward with special handling
            # This can happen with grouped nodes that span multiple layers
            self._draw_edge_tb_upward(
                canvas,
                source,
                target,
                box_dimensions,
                box_positions,
                source_targets,
                target_sources,
                layout_result,
            )
            return

        # Check if boxes overlap horizontally (inside borders)
        src_left = src_x + 1
        src_right = src_x + src_dims.width - 2
        tgt_left = tgt_x + 1
        tgt_right = tgt_x + tgt_dims.width - 2

        overlap_left = max(src_left, tgt_left)
        overlap_right = min(src_right, tgt_right)
        has_overlap = overlap_left < overlap_right

        # Check if there are ANY boxes that would block a direct path
        # This includes boxes at the same y level (due to grouping)
        # or in intermediate layers
        boxes_in_path = False
        if has_overlap:
            # Calculate the path region
            path_x_min = min(overlap_left, overlap_right) - 1
            path_x_max = max(overlap_left, overlap_right) + 1
            path_y_min = src_y + src_dims.height  # Below source
            path_y_max = tgt_y  # Above target

            # Find all boxes in this path region
            blocking_boxes = self._find_boxes_in_region(
                box_positions,
                box_dimensions,
                exclude_nodes={source, target},
                x_min=path_x_min,
                x_max=path_x_max,
                y_min=path_y_min,
                y_max=path_y_max,
            )
            boxes_in_path = len(blocking_boxes) > 0

        # Check if other targets from this source require fan-out routing
        # If so, we should use fan-out routing for ALL edges to avoid crossing
        other_targets_need_fanout = False
        if len(source_targets) > 1:
            for t in source_targets:
                if t == target:
                    continue
                t_dims = box_dimensions[t]
                t_x, _ = box_positions[t]
                t_left = t_x + 1
                t_right = t_x + t_dims.width - 2
                t_overlap_left = max(src_left, t_left)
                t_overlap_right = min(src_right, t_right)
                if t_overlap_left >= t_overlap_right:
                    # This target has no overlap, will use fan-out routing
                    other_targets_need_fanout = True
                    break

        if has_overlap and not boxes_in_path and not other_targets_need_fanout:
            # Boxes overlap and no obstructions - find overlapping targets
            overlapping_targets = []
            for t in source_targets:
                t_dims = box_dimensions[t]
                t_x, _ = box_positions[t]
                t_left = t_x + 1
                t_right = t_x + t_dims.width - 2
                t_overlap_left = max(src_left, t_left)
                t_overlap_right = min(src_right, t_right)
                if t_overlap_left < t_overlap_right:
                    overlapping_targets.append(t)

            # Distribute ports within the overlap region for overlapping targets
            overlap_width = overlap_right - overlap_left
            overlap_count = len(overlapping_targets)
            overlap_idx = overlapping_targets.index(target)

            if overlap_count == 1:
                # Single overlapping target - use center of overlap
                port_x = (overlap_left + overlap_right) // 2
            else:
                # Multiple overlapping targets - distribute within overlap
                if overlap_width >= overlap_count * 2:
                    # Enough space to distribute
                    spacing = overlap_width // (overlap_count + 1)
                    port_x = overlap_left + spacing * (overlap_idx + 1)
                else:
                    # Tight space - just use center offset slightly
                    port_x = overlap_left + (overlap_width * (overlap_idx + 1)) // (
                        overlap_count + 1
                    )

            # Use same x for both source and target (straight line)
            src_port_x = port_x
            tgt_port_x = port_x
        else:
            # No horizontal overlap or boxes in path - use distributed ports
            # Source: exit from bottom
            src_port_count = len(source_targets)
            src_port_idx = source_targets.index(target)
            src_port_x = self.position_calculator.calculate_port_x(
                src_x, src_dims.width, src_port_idx, src_port_count
            )

            # Target: enter from top
            tgt_port_count = len(target_sources)
            tgt_port_idx = target_sources.index(source)
            tgt_port_x = self.position_calculator.calculate_port_x(
                tgt_x, tgt_dims.width, tgt_port_idx, tgt_port_count
            )

        src_port_y = src_y + src_dims.height - 1  # Bottom border
        tgt_port_y = tgt_y  # Top border

        # Modify source bottom border to show exit point (tee down)
        canvas.set(src_port_x, src_port_y, LINE_CHARS["tee_down"], "source_exit_port")

        # Calculate path
        # Start below source (through shadow - arrow lines overwrite shadows)
        start_y = src_port_y + 1
        # End at target top
        end_y = tgt_port_y

        # Check if we need to route around boxes (when there are obstructions)
        if boxes_in_path:
            # Route to the right side of all boxes to avoid crossing them
            max_right_x = src_x + src_dims.width
            for layer_idx in range(src_layer + 1, tgt_layer):
                for node_name in layout_result.layers[layer_idx]:
                    node_dims = box_dimensions[node_name]
                    node_x, _ = box_positions[node_name]
                    node_right = node_x + node_dims.width + (2 if self.shadow else 0)
                    max_right_x = max(max_right_x, node_right)

            # Route: down, right to bypass, down, left to target
            route_x = max_right_x + 2  # Go 2 chars to the right of all boxes

            # Use the mid_y from source layer for the first horizontal segment
            mid_y = self._get_safe_horizontal_y(layer_boundaries, src_layer, start_y)

            # Vertical from source to mid
            self._draw_vertical_line(canvas, src_port_x, start_y, mid_y - 1)

            # Corner turning right
            canvas.set(
                src_port_x, mid_y, LINE_CHARS["corner_bottom_left"], "route_turn_right"
            )

            # Horizontal segment to the route column
            self._draw_horizontal_line(canvas, src_port_x, route_x, mid_y)

            # Corner turning down
            canvas.set(
                route_x, mid_y, LINE_CHARS["corner_top_right"], "route_turn_down"
            )

            # Find the y position for the horizontal segment above the target
            tgt_mid_y = self._get_safe_horizontal_y(
                layer_boundaries, tgt_layer - 1, start_y
            )

            # Vertical segment down the right side
            self._draw_vertical_line(canvas, route_x, mid_y + 1, tgt_mid_y - 1)

            # Corner turning left (line comes from above, exits left)
            canvas.set(
                route_x, tgt_mid_y, LINE_CHARS["corner_bottom_right"], "route_turn_left"
            )

            # Horizontal segment back toward target
            self._draw_horizontal_line(canvas, tgt_port_x, route_x, tgt_mid_y)

            # Corner turning down to target (line comes from right, exits down)
            canvas.set(
                tgt_port_x, tgt_mid_y, LINE_CHARS["corner_top_left"], "route_to_target"
            )

            # Vertical to target (only if there's space between corner and arrow)
            if tgt_mid_y + 1 <= end_y - 2:
                self._draw_vertical_line(canvas, tgt_port_x, tgt_mid_y + 1, end_y - 2)

            # Arrow
            canvas.set(tgt_port_x, tgt_port_y - 1, ARROW_CHARS["down"], "arrow_down")

        elif src_port_x == tgt_port_x and not other_targets_need_fanout:
            # Direct vertical line (stop before arrow position)
            # Only use direct vertical when there's no fan-out from this source
            # But first check if there are boxes in the vertical path
            boxes_in_vertical_path = self._find_boxes_in_region(
                box_positions,
                box_dimensions,
                exclude_nodes={source, target},
                x_min=src_port_x - 1,
                x_max=src_port_x + 2,
                y_min=start_y,
                y_max=end_y,
            )
            if boxes_in_vertical_path:
                # Route around - can't go straight down
                # Find a safe x to route through
                safe_x = max(
                    x + dims.width + 2 for _, x, _, dims in boxes_in_vertical_path
                )
                mid_y = self._get_safe_horizontal_y(
                    layer_boundaries, src_layer, start_y
                )

                # Down from source to mid_y
                self._draw_vertical_line(canvas, src_port_x, start_y, mid_y - 1)
                self._set_corner(canvas, src_port_x, mid_y, "bottom_left")

                # Right to safe_x
                self._draw_horizontal_line(canvas, src_port_x, safe_x, mid_y)
                self._set_corner(canvas, safe_x, mid_y, "top_right")

                # Down past the blocking boxes
                tgt_mid_y = self._get_safe_horizontal_y(
                    layer_boundaries, tgt_layer - 1, start_y
                )
                self._draw_vertical_line(canvas, safe_x, mid_y + 1, tgt_mid_y - 1)
                self._set_corner(canvas, safe_x, tgt_mid_y, "bottom_right")

                # Left to target x
                self._draw_horizontal_line(canvas, tgt_port_x, safe_x, tgt_mid_y)
                self._set_corner(canvas, tgt_port_x, tgt_mid_y, "top_left")

                # Down to target
                if tgt_mid_y + 1 <= end_y - 2:
                    self._draw_vertical_line(
                        canvas, tgt_port_x, tgt_mid_y + 1, end_y - 2
                    )
                canvas.set(
                    tgt_port_x, tgt_port_y - 1, ARROW_CHARS["down"], "arrow_down"
                )
            else:
                self._draw_vertical_line(canvas, src_port_x, start_y, end_y - 2)
                # Draw arrow one row above target box (doesn't overwrite border)
                canvas.set(
                    tgt_port_x, tgt_port_y - 1, ARROW_CHARS["down"], "arrow_down"
                )
        else:
            # Need to route with horizontal segment
            # Use layer-aware routing: place horizontal segment in the gap zone
            # below the source layer where no boxes can exist
            mid_y = self._get_safe_horizontal_y(layer_boundaries, src_layer, start_y)

            # Check if there are boxes in the horizontal segment path at mid_y
            horiz_min_x = min(src_port_x, tgt_port_x)
            horiz_max_x = max(src_port_x, tgt_port_x)
            boxes_in_horiz_path = self._find_boxes_in_region(
                box_positions,
                box_dimensions,
                exclude_nodes={source, target},
                x_min=horiz_min_x,
                x_max=horiz_max_x,
                y_min=mid_y - 1,
                y_max=mid_y + 2,
            )

            if boxes_in_horiz_path:
                # Need to route around boxes in the horizontal path
                # Find max bottom of blocking boxes and route below them
                max_bottom = max(
                    y + dims.height + (2 if self.shadow else 0)
                    for _, _, y, dims in boxes_in_horiz_path
                )
                mid_y = max_bottom + 2

            # Vertical from source to mid
            self._draw_vertical_line(canvas, src_port_x, start_y, mid_y - 1)

            # Corner at source column (use smart corner setter for fan-out merging)
            if src_port_x == tgt_port_x:
                # Target is directly below source - use tee_down for fan-out junction
                # This avoids creating a cross when source and target corners combine
                canvas.set(src_port_x, mid_y, LINE_CHARS["tee_down"], "fanout_junction")
            elif tgt_port_x > src_port_x:
                self._set_corner(canvas, src_port_x, mid_y, "bottom_left")
            else:
                self._set_corner(canvas, src_port_x, mid_y, "bottom_right")

            # Horizontal segment
            self._draw_horizontal_line(canvas, src_port_x, tgt_port_x, mid_y)

            # Check for boxes in the vertical segment from mid_y to target
            boxes_in_final_vertical = self._find_boxes_in_region(
                box_positions,
                box_dimensions,
                exclude_nodes={source, target},
                x_min=tgt_port_x - 1,
                x_max=tgt_port_x + 2,
                y_min=mid_y,
                y_max=end_y,
            )

            if boxes_in_final_vertical:
                # Need to route around boxes in the final vertical segment
                # Find max right of blocking boxes and route to the right of them
                max_right = max(
                    x + dims.width + (2 if self.shadow else 0)
                    for _, x, _, dims in boxes_in_final_vertical
                )
                route_x = max_right + 2

                # From source column, go to route_x
                self._draw_horizontal_line(canvas, src_port_x, route_x, mid_y)
                if tgt_port_x > src_port_x:
                    self._set_corner(canvas, src_port_x, mid_y, "bottom_left")
                else:
                    self._set_corner(canvas, src_port_x, mid_y, "bottom_right")
                self._set_corner(canvas, route_x, mid_y, "top_right")

                # Down at route_x past blocking boxes
                tgt_mid_y = self._get_safe_horizontal_y(
                    layer_boundaries, tgt_layer - 1, start_y
                )
                tgt_mid_y = max(
                    tgt_mid_y,
                    max(
                        y + dims.height + (2 if self.shadow else 0)
                        for _, _, y, dims in boxes_in_final_vertical
                    )
                    + 2,
                )
                self._draw_vertical_line(canvas, route_x, mid_y + 1, tgt_mid_y - 1)
                self._set_corner(canvas, route_x, tgt_mid_y, "bottom_right")

                # Left to target x
                self._draw_horizontal_line(canvas, tgt_port_x, route_x, tgt_mid_y)
                self._set_corner(canvas, tgt_port_x, tgt_mid_y, "top_left")

                # Down to target
                if tgt_mid_y + 1 <= end_y - 2:
                    self._draw_vertical_line(
                        canvas, tgt_port_x, tgt_mid_y + 1, end_y - 2
                    )
            else:
                # Corner at target column (use smart corner setter for fan-in merging)
                # Skip if target is at same x as source (already handled above)
                if tgt_port_x != src_port_x:
                    if tgt_port_x > src_port_x:
                        self._set_corner(canvas, tgt_port_x, mid_y, "top_right")
                    else:
                        self._set_corner(canvas, tgt_port_x, mid_y, "top_left")

                # Vertical from mid to target (stop before arrow position)
                # Only draw if there's actually space between the corner and the arrow
                if mid_y + 1 <= end_y - 2:
                    self._draw_vertical_line(canvas, tgt_port_x, mid_y + 1, end_y - 2)

            # Draw arrow one row above target box (doesn't overwrite border)
            canvas.set(tgt_port_x, tgt_port_y - 1, ARROW_CHARS["down"], "arrow_down")

    def _draw_edge_tb_upward(
        self,
        canvas: Canvas,
        source: str,
        target: str,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
        source_targets: List[str],
        target_sources: List[str],
        layout_result: LayoutResult,
    ) -> None:
        """
        Draw an edge when target is above source in canvas coordinates.

        This happens when grouped nodes span multiple layers - a node in a lower
        layer might have an edge to a grouped node that's visually above it.
        Routes: exit top of source -> up -> horizontal to target column ->
        up -> enter target bottom
        """
        src_dims = box_dimensions[source]
        tgt_dims = box_dimensions[target]
        src_x, src_y = box_positions[source]
        tgt_x, tgt_y = box_positions[target]

        # Calculate port positions
        src_port_count = len(source_targets)
        src_port_idx = source_targets.index(target)
        tgt_port_count = len(target_sources)
        tgt_port_idx = target_sources.index(source)

        # Source: exit from TOP (since target is above)
        src_port_x = self.position_calculator.calculate_port_x(
            src_x, src_dims.width, src_port_idx, src_port_count
        )
        src_exit_y = src_y  # Top border of source

        # Target: enter from BOTTOM (since source is below)
        tgt_port_x = self.position_calculator.calculate_port_x(
            tgt_x, tgt_dims.width, tgt_port_idx, tgt_port_count
        )
        tgt_entry_y = tgt_y + tgt_dims.height - 1  # Bottom border of target

        # Check for boxes in the path between source top and target bottom
        path_y_top = tgt_entry_y + (2 if self.shadow else 1)  # Below target shadow
        path_y_bottom = src_exit_y - 1  # Above source

        boxes_in_path = self._find_boxes_in_region(
            box_positions,
            box_dimensions,
            exclude_nodes={source, target},
            x_min=min(src_port_x, tgt_port_x) - 1,
            x_max=max(src_port_x, tgt_port_x) + 2,
            y_min=path_y_top,
            y_max=path_y_bottom,
        )

        if src_port_x == tgt_port_x and not boxes_in_path:
            # Direct vertical line upward
            # Mark exit on source top border
            canvas.set(src_port_x, src_exit_y, LINE_CHARS["tee_up"], "source_top_exit")

            # Vertical line from source top up to just above target bottom
            self._draw_vertical_line(canvas, src_port_x, path_y_top + 1, src_exit_y - 1)

            # Arrow pointing up at target bottom
            canvas.set(tgt_port_x, tgt_entry_y + 1, ARROW_CHARS["up"], "arrow_up")
        else:
            # Route with horizontal segment
            # Find mid_y in the gap between target (above) and source (below)
            mid_y = (path_y_top + path_y_bottom) // 2

            if boxes_in_path:
                # Need to route around boxes - find max right of all boxes
                max_right = max(
                    x + dims.width + (2 if self.shadow else 0)
                    for _, x, _, dims in boxes_in_path
                )
                route_x = max_right + 2

                # Mark exit on source top
                canvas.set(
                    src_port_x, src_exit_y, LINE_CHARS["tee_up"], "source_top_exit"
                )

                # Up from source to mid_y
                self._draw_vertical_line(canvas, src_port_x, mid_y + 1, src_exit_y - 1)

                # Corner turning right
                if route_x > src_port_x:
                    self._set_corner(canvas, src_port_x, mid_y, "top_left")
                else:
                    self._set_corner(canvas, src_port_x, mid_y, "top_right")

                # Horizontal to route_x
                self._draw_horizontal_line(canvas, src_port_x, route_x, mid_y)

                # Corner at route_x turning up
                self._set_corner(canvas, route_x, mid_y, "bottom_right")

                # Up at route_x past blocking boxes
                upper_mid_y = path_y_top + 2
                self._draw_vertical_line(canvas, route_x, upper_mid_y + 1, mid_y - 1)

                # Corner turning left toward target
                self._set_corner(canvas, route_x, upper_mid_y, "top_right")

                # Horizontal to target x
                self._draw_horizontal_line(canvas, tgt_port_x, route_x, upper_mid_y)

                # Corner turning up to target
                self._set_corner(canvas, tgt_port_x, upper_mid_y, "top_left")

                # Up to target
                if upper_mid_y - 1 >= path_y_top + 2:
                    self._draw_vertical_line(
                        canvas, tgt_port_x, path_y_top + 2, upper_mid_y - 1
                    )

                # Arrow pointing up
                canvas.set(tgt_port_x, tgt_entry_y + 1, ARROW_CHARS["up"], "arrow_up")
            else:
                # No boxes in path - simple route
                # Mark exit on source top
                canvas.set(
                    src_port_x, src_exit_y, LINE_CHARS["tee_up"], "source_top_exit"
                )

                # Up from source to mid_y
                self._draw_vertical_line(canvas, src_port_x, mid_y + 1, src_exit_y - 1)

                # Corner at source column
                if tgt_port_x > src_port_x:
                    self._set_corner(canvas, src_port_x, mid_y, "top_left")
                else:
                    self._set_corner(canvas, src_port_x, mid_y, "top_right")

                # Horizontal to target column
                self._draw_horizontal_line(canvas, src_port_x, tgt_port_x, mid_y)

                # Corner at target column
                if tgt_port_x > src_port_x:
                    self._set_corner(canvas, tgt_port_x, mid_y, "bottom_right")
                else:
                    self._set_corner(canvas, tgt_port_x, mid_y, "bottom_left")

                # Up to target
                if mid_y - 1 >= path_y_top + 2:
                    self._draw_vertical_line(
                        canvas, tgt_port_x, path_y_top + 2, mid_y - 1
                    )

                # Arrow pointing up
                canvas.set(tgt_port_x, tgt_entry_y + 1, ARROW_CHARS["up"], "arrow_up")

    def _draw_edge_tb_stacked(
        self,
        canvas: Canvas,
        source: str,
        target: str,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
        source_targets: List[str],
        target_sources: List[str],
        layout_result: LayoutResult,
    ) -> None:
        """
        Draw an edge when source and target are horizontally adjacent (same y-position).

        This happens when nodes are grouped together in TB mode. The edge routes
        horizontally between the boxes - exiting from right and entering from left.
        If there are intermediate boxes in the path, routes around them below.
        """
        src_dims = box_dimensions[source]
        tgt_dims = box_dimensions[target]
        src_x, src_y = box_positions[source]
        tgt_x, tgt_y = box_positions[target]

        # Determine which box is on the left and which is on the right
        if src_x < tgt_x:
            goes_right = True
            src_exit_x = src_x + src_dims.width - 1 + (1 if self.shadow else 0)
            tgt_entry_x = tgt_x
            path_left_x = src_exit_x
            path_right_x = tgt_entry_x
        else:
            goes_right = False
            src_exit_x = src_x
            tgt_entry_x = tgt_x + tgt_dims.width - 1
            path_left_x = tgt_entry_x
            path_right_x = src_exit_x

        # Check for boxes in the horizontal path between source and target
        boxes_in_path = []
        for node_name, (node_x, node_y) in box_positions.items():
            if node_name == source or node_name == target:
                continue
            node_dims = box_dimensions[node_name]
            node_left = node_x
            node_right = node_x + node_dims.width + (1 if self.shadow else 0)

            # Check if this box overlaps with the horizontal path
            overlaps_x = node_left < path_right_x and node_right > path_left_x
            # Check y overlap - boxes at similar y positions
            src_top = src_y
            src_bottom = src_y + src_dims.height + (1 if self.shadow else 0)
            node_top = node_y
            node_bottom = node_y + node_dims.height + (1 if self.shadow else 0)
            overlaps_y = node_top < src_bottom and node_bottom > src_top

            if overlaps_x and overlaps_y:
                boxes_in_path.append((node_name, node_x, node_y, node_dims))

        # Calculate vertical port positions
        src_port_count = len(source_targets)
        src_port_idx = source_targets.index(target)
        tgt_port_count = len(target_sources)
        tgt_port_idx = target_sources.index(source)

        src_port_y = self.position_calculator.calculate_port_y(
            src_y, src_dims.height, src_port_idx, src_port_count
        )
        tgt_port_y = self.position_calculator.calculate_port_y(
            tgt_y, tgt_dims.height, tgt_port_idx, tgt_port_count
        )

        if boxes_in_path:
            # Route around intermediate boxes - go below all boxes
            max_bottom_y = src_y + src_dims.height + (1 if self.shadow else 0)
            max_bottom_y = max(
                max_bottom_y, tgt_y + tgt_dims.height + (1 if self.shadow else 0)
            )
            for _, _, node_y, node_dims in boxes_in_path:
                node_bottom = node_y + node_dims.height + (2 if self.shadow else 0)
                max_bottom_y = max(max_bottom_y, node_bottom)

            route_y = max_bottom_y + 2  # Route 2 rows below all boxes

            # Exit source from bottom
            src_port_x = self.position_calculator.calculate_port_x(
                src_x, src_dims.width, src_port_idx, src_port_count
            )
            src_bottom_y = src_y + src_dims.height - 1

            # Enter target from bottom
            tgt_port_x = self.position_calculator.calculate_port_x(
                tgt_x, tgt_dims.width, tgt_port_idx, tgt_port_count
            )
            tgt_bottom_y = tgt_y + tgt_dims.height - 1

            # Draw: vertical from source bottom to route_y
            self._draw_vertical_line(canvas, src_port_x, src_bottom_y + 1, route_y)

            # Corner at route_y turning right/left
            if goes_right:
                self._set_corner(canvas, src_port_x, route_y, "bottom_left")
            else:
                self._set_corner(canvas, src_port_x, route_y, "bottom_right")

            # Horizontal segment at route_y
            self._draw_horizontal_line(canvas, src_port_x, tgt_port_x, route_y)

            # Corner at target column turning up
            if goes_right:
                self._set_corner(canvas, tgt_port_x, route_y, "bottom_right")
            else:
                self._set_corner(canvas, tgt_port_x, route_y, "bottom_left")

            # Vertical from route_y up to target bottom
            self._draw_vertical_line(canvas, tgt_port_x, tgt_bottom_y + 2, route_y)

            # Arrow pointing up at target bottom border
            canvas.set(tgt_port_x, tgt_bottom_y + 1, ARROW_CHARS["up"])

        else:
            # No intermediate boxes - draw a clean horizontal connection
            # For horizontally adjacent boxes, adjust at the source exit
            # then go straight to target
            if goes_right:
                if src_port_y == tgt_port_y:
                    # Same height - direct horizontal line
                    self._draw_horizontal_line(
                        canvas, src_exit_x, tgt_entry_x - 1, src_port_y
                    )
                    canvas.set(tgt_entry_x - 1, tgt_port_y, ARROW_CHARS["right"])
                else:
                    # Different heights - adjust at source exit, then straight to target
                    # Short vertical segment right after source exit
                    adjust_x = src_exit_x + 1

                    # Draw horizontal from source exit
                    canvas.set(
                        src_exit_x,
                        src_port_y,
                        LINE_CHARS["horizontal"],
                        "horizontal_exit",
                    )

                    # Draw vertical adjustment segment
                    min_y = min(src_port_y, tgt_port_y)
                    max_y = max(src_port_y, tgt_port_y)
                    self._draw_vertical_line(canvas, adjust_x, min_y, max_y)

                    # Set corner at adjustment point on source side
                    if tgt_port_y > src_port_y:
                        self._set_corner(canvas, adjust_x, src_port_y, "top_right")
                        self._set_corner(canvas, adjust_x, tgt_port_y, "bottom_left")
                    else:
                        self._set_corner(canvas, adjust_x, src_port_y, "bottom_right")
                        self._set_corner(canvas, adjust_x, tgt_port_y, "top_left")

                    # Horizontal line from adjustment to target
                    self._draw_horizontal_line(
                        canvas, adjust_x, tgt_entry_x - 1, tgt_port_y
                    )
                    canvas.set(tgt_entry_x - 1, tgt_port_y, ARROW_CHARS["right"])
            else:
                if src_port_y == tgt_port_y:
                    # Same height - direct horizontal line
                    self._draw_horizontal_line(
                        canvas, tgt_entry_x + 1, src_exit_x, src_port_y
                    )
                    canvas.set(tgt_entry_x + 1, tgt_port_y, ARROW_CHARS["left"])
                else:
                    # Different heights - adjust at source exit, then straight to target
                    adjust_x = src_exit_x - 1

                    # Draw horizontal from source exit
                    canvas.set(
                        src_exit_x,
                        src_port_y,
                        LINE_CHARS["horizontal"],
                        "horizontal_exit",
                    )

                    # Draw vertical adjustment segment
                    min_y = min(src_port_y, tgt_port_y)
                    max_y = max(src_port_y, tgt_port_y)
                    self._draw_vertical_line(canvas, adjust_x, min_y, max_y)

                    # Set corner at adjustment point on source side
                    if tgt_port_y > src_port_y:
                        self._set_corner(canvas, adjust_x, src_port_y, "top_left")
                        self._set_corner(canvas, adjust_x, tgt_port_y, "bottom_right")
                    else:
                        self._set_corner(canvas, adjust_x, src_port_y, "bottom_left")
                        self._set_corner(canvas, adjust_x, tgt_port_y, "top_right")

                    # Horizontal line from adjustment to target
                    self._draw_horizontal_line(
                        canvas, tgt_entry_x + 1, adjust_x, tgt_port_y
                    )
                    canvas.set(tgt_entry_x + 1, tgt_port_y, ARROW_CHARS["left"])

    def _get_safe_horizontal_y(
        self,
        layer_boundaries: List[LayerBoundary],
        src_layer: int,
        start_y: int,
    ) -> int:
        """
        Get a safe y-coordinate for horizontal edge routing.

        Places the horizontal segment in the gap zone below the source layer,
        ensuring it doesn't pass through any boxes.

        Args:
            layer_boundaries: List of layer boundary information.
            src_layer: The layer index of the source node.
            start_y: The y-coordinate where the edge starts (below source box).

        Returns:
            A y-coordinate in the gap zone that's safe for horizontal routing.
        """
        if src_layer < len(layer_boundaries):
            boundary = layer_boundaries[src_layer]
            # Place horizontal line in the middle of the gap zone
            gap_middle = (boundary.gap_start_y + boundary.gap_end_y) // 2
            # Ensure we're at least at start_y (below the source shadow)
            return max(gap_middle, start_y + 1)
        else:
            # Fallback: just below the start
            return start_y + 2

    def _get_safe_vertical_x(
        self,
        column_boundaries: List[ColumnBoundary],
        src_layer: int,
        start_x: int,
    ) -> int:
        """
        Get a safe x-coordinate for vertical edge routing in LR mode.

        Places the vertical segment in the gap zone to the right of the source
        layer, ensuring it doesn't pass through any boxes.

        Args:
            column_boundaries: List of column boundary information.
            src_layer: The layer index of the source node.
            start_x: The x-coordinate where the edge starts (after source box).

        Returns:
            An x-coordinate in the gap zone that's safe for vertical routing.
        """
        if src_layer < len(column_boundaries):
            boundary = column_boundaries[src_layer]
            # Place vertical line in the middle of the gap zone
            gap_middle = (boundary.gap_start_x + boundary.gap_end_x) // 2
            # Ensure we're at least at start_x (after the source shadow)
            return max(gap_middle, start_x + 1)
        else:
            # Fallback: just after the start
            return start_x + 2

    def _draw_vertical_line(
        self, canvas: Canvas, x: int, y_start: int, y_end: int
    ) -> None:
        """
        Draw a vertical line from y_start to y_end.

        Handles intersection with existing lines by upgrading to appropriate
        junction characters (tees, crosses). Avoids drawing inside box content.

        Args:
            canvas: The canvas to draw on.
            x: X coordinate for the line.
            y_start: Starting Y coordinate.
            y_end: Ending Y coordinate.
        """
        if y_start > y_end:
            y_start, y_end = y_end, y_start

        for y in range(y_start, y_end + 1):
            # Skip if this position is inside a box or on a box border
            if self._is_inside_box(x, y) or self._is_on_box_border(x, y):
                continue

            current = canvas.get(x, y)
            if current == LINE_CHARS["horizontal"]:
                canvas.set(x, y, LINE_CHARS["cross"], "vertical_crosses_horizontal")
            elif current in (
                LINE_CHARS["corner_top_left"],
                LINE_CHARS["corner_bottom_left"],
            ):
                # Corners with "right" segment + vertical = tee_right
                # corner_top_left (┌) has: down, right -> + up, down = tee_right (├)
                # corner_bottom_left (└) has: up, right -> + up, down = tee_right (├)
                canvas.set(x, y, LINE_CHARS["tee_right"], "upgrade_corner_to_tee")
            elif current in (
                LINE_CHARS["corner_top_right"],
                LINE_CHARS["corner_bottom_right"],
            ):
                # Corners with "left" segment + vertical = tee_left
                # corner_top_right (┐) has: down, left -> + up, down = tee_left (┤)
                # corner_bottom_right (┘) has: up, left -> + up, down = tee_left (┤)
                canvas.set(x, y, LINE_CHARS["tee_left"], "upgrade_corner_to_tee")
            elif current in (LINE_CHARS["tee_up"], LINE_CHARS["tee_down"]):
                # Tees with horizontal segments + vertical = cross
                canvas.set(x, y, LINE_CHARS["cross"], "upgrade_tee_to_cross")
            elif current == " " or current == BOX_CHARS["shadow"]:
                canvas.set(x, y, LINE_CHARS["vertical"], "vertical_line")

    def _draw_horizontal_line(
        self, canvas: Canvas, x_start: int, x_end: int, y: int
    ) -> None:
        """
        Draw a horizontal line from x_start to x_end (exclusive of endpoints).

        Handles intersection with existing lines by upgrading to appropriate
        junction characters (tees, crosses). Avoids drawing inside box content.

        Args:
            canvas: The canvas to draw on.
            x_start: Starting X coordinate.
            x_end: Ending X coordinate.
            y: Y coordinate for the line.
        """
        if x_start > x_end:
            x_start, x_end = x_end, x_start

        for x in range(x_start + 1, x_end):
            # Skip if this position is inside a box or on a box border
            if self._is_inside_box(x, y) or self._is_on_box_border(x, y):
                continue

            current = canvas.get(x, y)
            if current == LINE_CHARS["vertical"]:
                canvas.set(x, y, LINE_CHARS["cross"], "horizontal_crosses_vertical")
            elif current in (
                LINE_CHARS["corner_top_left"],
                LINE_CHARS["corner_top_right"],
            ):
                # Corners with "down" segment + horizontal = tee_down
                # corner_top_left (┌) has: down, right -> + left, right = tee_down (┬)
                # corner_top_right (┐) has: down, left -> + left, right = tee_down (┬)
                canvas.set(x, y, LINE_CHARS["tee_down"], "upgrade_corner_to_tee")
            elif current in (
                LINE_CHARS["corner_bottom_left"],
                LINE_CHARS["corner_bottom_right"],
            ):
                # Corners with "up" segment + horizontal = tee_up
                # corner_bottom_left (└) has: up, right -> + left, right = tee_up (┴)
                # corner_bottom_right (┘) has: up, left -> + left, right = tee_up (┴)
                canvas.set(x, y, LINE_CHARS["tee_up"], "upgrade_corner_to_tee")
            elif current in (LINE_CHARS["tee_right"], LINE_CHARS["tee_left"]):
                # Tees with vertical segments + horizontal = cross
                canvas.set(x, y, LINE_CHARS["cross"], "upgrade_vertical_tee_to_cross")
            elif current in (LINE_CHARS["tee_up"], LINE_CHARS["tee_down"]):
                # These tees already have horizontal connectivity, no change needed
                pass
            elif current == LINE_CHARS["horizontal"]:
                # Already horizontal, no change needed
                pass
            elif current == " " or current == BOX_CHARS["shadow"]:
                canvas.set(x, y, LINE_CHARS["horizontal"], "horizontal_line")

    def _set_corner(self, canvas: Canvas, x: int, y: int, corner_type: str) -> None:
        """
        Set a corner character at position (x, y), handling existing content.

        If there's already a line at this position, the corner is upgraded to
        the appropriate junction character (tee or cross).

        Args:
            canvas: The canvas to draw on.
            x: X position.
            y: Y position.
            corner_type: One of 'top_left', 'top_right', 'bottom_left', 'bottom_right'.
        """
        # Skip if this position is inside a box or on a box border
        if self._is_inside_box(x, y) or self._is_on_box_border(x, y):
            return

        current = canvas.get(x, y)
        corner_char = LINE_CHARS[f"corner_{corner_type}"]

        if current in (" ", BOX_CHARS["shadow"]):
            canvas.set(x, y, corner_char, f"corner_{corner_type}")
        elif current == LINE_CHARS["horizontal"]:
            # Horizontal line + corner = tee pointing up or down
            if "top" in corner_type:
                canvas.set(x, y, LINE_CHARS["tee_down"], "upgrade_horiz_to_tee")
            else:
                canvas.set(x, y, LINE_CHARS["tee_up"], "upgrade_horiz_to_tee")
        elif current == LINE_CHARS["vertical"]:
            # Vertical line + corner = tee pointing left or right
            if "left" in corner_type:
                canvas.set(x, y, LINE_CHARS["tee_right"], "upgrade_vert_to_tee")
            else:
                canvas.set(x, y, LINE_CHARS["tee_left"], "upgrade_vert_to_tee")
        elif current in (
            LINE_CHARS["corner_top_left"],
            LINE_CHARS["corner_top_right"],
            LINE_CHARS["corner_bottom_left"],
            LINE_CHARS["corner_bottom_right"],
        ):
            # Corner + corner = appropriate tee based on combined segments
            # Each corner has specific segments; combine them to get the right tee
            # Segments: top_left (down,right), top_right (down,left),
            #           bottom_left (up,right), bottom_right (up,left)
            segments = set()

            # Add segments from existing corner
            if current == LINE_CHARS["corner_top_left"]:
                segments.update(["down", "right"])
            elif current == LINE_CHARS["corner_top_right"]:
                segments.update(["down", "left"])
            elif current == LINE_CHARS["corner_bottom_left"]:
                segments.update(["up", "right"])
            elif current == LINE_CHARS["corner_bottom_right"]:
                segments.update(["up", "left"])

            # Add segments from new corner
            if corner_type == "top_left":
                segments.update(["down", "right"])
            elif corner_type == "top_right":
                segments.update(["down", "left"])
            elif corner_type == "bottom_left":
                segments.update(["up", "right"])
            elif corner_type == "bottom_right":
                segments.update(["up", "left"])

            # Determine result based on combined segments
            if segments == {"up", "down", "left", "right"}:
                canvas.set(x, y, LINE_CHARS["cross"], "merge_corners_to_cross")
            elif segments == {"up", "down", "right"}:
                canvas.set(x, y, LINE_CHARS["tee_right"], "merge_corners_to_tee_right")
            elif segments == {"up", "down", "left"}:
                canvas.set(x, y, LINE_CHARS["tee_left"], "merge_corners_to_tee_left")
            elif segments == {"up", "left", "right"}:
                canvas.set(x, y, LINE_CHARS["tee_up"], "merge_corners_to_tee_up")
            elif segments == {"down", "left", "right"}:
                canvas.set(x, y, LINE_CHARS["tee_down"], "merge_corners_to_tee_down")
            else:
                # Same corner or incomplete, keep the corner
                canvas.set(x, y, corner_char, f"corner_{corner_type}_unchanged")
        elif current in (
            LINE_CHARS["tee_left"],
            LINE_CHARS["tee_right"],
            LINE_CHARS["tee_up"],
            LINE_CHARS["tee_down"],
        ):
            # Tee + corner: only becomes cross if corner adds a genuinely new segment
            # tee_left (├): up, down, right
            # tee_right (┤): up, down, left
            # tee_up (┴): up, left, right
            # tee_down (┬): down, left, right
            tee_segments = set()
            if current == LINE_CHARS["tee_left"]:
                tee_segments = {"up", "down", "right"}
            elif current == LINE_CHARS["tee_right"]:
                tee_segments = {"up", "down", "left"}
            elif current == LINE_CHARS["tee_up"]:
                tee_segments = {"up", "left", "right"}
            elif current == LINE_CHARS["tee_down"]:
                tee_segments = {"down", "left", "right"}

            # Add segments from new corner
            corner_segments = set()
            if corner_type == "top_left":
                corner_segments = {"down", "right"}
            elif corner_type == "top_right":
                corner_segments = {"down", "left"}
            elif corner_type == "bottom_left":
                corner_segments = {"up", "right"}
            elif corner_type == "bottom_right":
                corner_segments = {"up", "left"}

            # Check if corner adds any new segment
            combined = tee_segments | corner_segments
            if combined == {"up", "down", "left", "right"}:
                canvas.set(x, y, LINE_CHARS["cross"], "upgrade_tee_corner_to_cross")
            # else: tee already has all needed segments, no change

    def draw_back_edges(
        self,
        canvas: Canvas,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
    ) -> None:
        """
        Draw back edges (cycle edges) along the left margin of the diagram.

        Back edges exit from the bottom-left of the source box, route down
        then left to the margin, up along the margin, then right and up
        to enter the target from the left.

        If there are boxes between the margin and the target, the edge routes
        below those boxes to avoid crossing through them.

        Args:
            canvas: The canvas to draw on.
            layout_result: The layout result with back edge information.
            box_dimensions: Dictionary of box dimensions.
            box_positions: Dictionary of box positions.
        """
        if not layout_result.back_edges:
            return

        margin_x = 2  # Starting route column for back edges

        # Sort back edges by source layer (draw deeper ones first)
        node_layer = {name: node.layer for name, node in layout_result.nodes.items()}

        sorted_back_edges = sorted(
            layout_result.back_edges,
            key=lambda e: node_layer.get(e[0], 0),
            reverse=True,
        )

        # Track entries per target for offset
        target_entry_count: Dict[str, int] = {}

        # Track used margin positions to offset multiple back edges
        margin_offset = 0

        for source, target in sorted_back_edges:
            src_dims = box_dimensions[source]
            tgt_dims = box_dimensions[target]
            src_x, src_y = box_positions[source]
            tgt_x, tgt_y = box_positions[target]

            # Use offset margin for multiple back edges
            route_x = margin_x + margin_offset
            margin_offset += 3  # Space out multiple back edges (increased for clarity)

            # Track how many edges already entered this target
            entry_idx = target_entry_count.get(target, 0)
            target_entry_count[target] = entry_idx + 1

            # Exit point: bottom of source box, then route to left margin
            exit_border_y = src_y + src_dims.height - 1  # Bottom border
            exit_below_y = exit_border_y + (2 if self.shadow else 1)  # Below shadow

            # Entry point: left side of target box
            # Offset vertically for multiple entries to same target
            entry_x = tgt_x
            base_entry_y = tgt_y + 1  # Start from top of content
            entry_y = base_entry_y + entry_idx

            # Ensure entry_y is within the box
            max_entry_y = tgt_y + tgt_dims.height - 2
            if entry_y > max_entry_y:
                entry_y = max_entry_y

            # Check if there are boxes between margin and target that would block
            # the horizontal path at entry_y
            boxes_in_path = []
            for node_name, (node_x, node_y) in box_positions.items():
                if node_name == target:
                    continue
                node_dims = box_dimensions[node_name]
                node_right = node_x + node_dims.width + (1 if self.shadow else 0)
                node_bottom = node_y + node_dims.height + (2 if self.shadow else 0)

                # Check if this box is between margin and target horizontally
                # AND overlaps with entry_y vertically
                if node_x > route_x and node_right < entry_x:
                    if node_y <= entry_y < node_bottom:
                        boxes_in_path.append((node_name, node_x, node_y, node_dims))

            # Draw the back edge path:
            # 1. Mark exit on source bottom-left corner area
            exit_x = src_x + 1 + (margin_offset - 3)  # Offset exit point too
            if exit_x >= src_x + src_dims.width - 1:
                exit_x = src_x + 1

            canvas.set(exit_x, exit_border_y, LINE_CHARS["tee_down"])

            # 2. Short vertical line down from source (through shadow)
            for y in range(exit_border_y + 1, exit_below_y + 1):
                canvas.set(exit_x, y, LINE_CHARS["vertical"])

            # 3. Corner turning left
            canvas.set(exit_x, exit_below_y, LINE_CHARS["corner_bottom_right"])

            # 4. Horizontal line left to margin
            for x in range(route_x + 1, exit_x):
                current = canvas.get(x, exit_below_y)
                if current == LINE_CHARS["vertical"]:
                    canvas.set(x, exit_below_y, LINE_CHARS["cross"])
                elif current == " " or current == BOX_CHARS["shadow"]:
                    canvas.set(x, exit_below_y, LINE_CHARS["horizontal"])

            # 5. Corner at margin (turning up)
            canvas.set(route_x, exit_below_y, LINE_CHARS["corner_bottom_left"])

            if boxes_in_path:
                # Need to route around boxes
                # Strategy: go up to above the target layer (in the gap),
                # then route horizontally, then down into target from above
                # This avoids crossing boxes in the same layer as the target

                # Find the top of the target (where we want to enter from above)
                safe_y = tgt_y - 2  # Position in gap above target layer

                # Find a safe approach x (to the right of blocking boxes)
                max_blocking_right = max(
                    node_x + node_dims.width + (2 if self.shadow else 1)
                    for _, node_x, _, node_dims in boxes_in_path
                )
                # Approach from the right of blocking boxes, but left of target
                approach_x = min(max_blocking_right + 2, entry_x - 4)
                if approach_x < route_x + 4:
                    approach_x = route_x + 4

                # 6a. Vertical line up the margin to safe_y
                for y in range(safe_y + 1, exit_below_y):
                    current = canvas.get(route_x, y)
                    if current == LINE_CHARS["horizontal"]:
                        canvas.set(route_x, y, LINE_CHARS["cross"])
                    elif current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(route_x, y, LINE_CHARS["vertical"])

                # 7a. Corner at safe_y (turning right)
                canvas.set(route_x, safe_y, LINE_CHARS["corner_top_left"])

                # 8a. Horizontal line to approach position
                for x in range(route_x + 1, approach_x):
                    current = canvas.get(x, safe_y)
                    if current == LINE_CHARS["vertical"]:
                        canvas.set(x, safe_y, LINE_CHARS["cross"])
                    elif current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(x, safe_y, LINE_CHARS["horizontal"])

                # 9a. Corner turning down toward target
                canvas.set(approach_x, safe_y, LINE_CHARS["corner_top_right"])

                # 10a. Vertical line down to entry level
                for y in range(safe_y + 1, entry_y):
                    current = canvas.get(approach_x, y)
                    if current == LINE_CHARS["horizontal"]:
                        canvas.set(approach_x, y, LINE_CHARS["cross"])
                    elif current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(approach_x, y, LINE_CHARS["vertical"])

                # 11a. Corner at entry_y turning right to target
                canvas.set(approach_x, entry_y, LINE_CHARS["corner_bottom_left"])

                # 12a. Horizontal line to arrow position
                for x in range(approach_x + 1, entry_x - 1):
                    current = canvas.get(x, entry_y)
                    if current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(x, entry_y, LINE_CHARS["horizontal"])

                # 13a. Arrow
                canvas.set(entry_x - 1, entry_y, ARROW_CHARS["right"])
            else:
                # No boxes in path - draw directly
                # 6. Vertical line up the margin
                for y in range(entry_y + 1, exit_below_y):
                    current = canvas.get(route_x, y)
                    if current == LINE_CHARS["horizontal"]:
                        canvas.set(route_x, y, LINE_CHARS["cross"])
                    elif current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(route_x, y, LINE_CHARS["vertical"])

                # 7. Corner at target level (turning right)
                current = canvas.get(route_x, entry_y)
                if current == LINE_CHARS["vertical"]:
                    canvas.set(route_x, entry_y, LINE_CHARS["tee_right"])
                elif current == LINE_CHARS["horizontal"]:
                    canvas.set(route_x, entry_y, LINE_CHARS["tee_down"])
                elif current == " " or current == BOX_CHARS["shadow"]:
                    canvas.set(route_x, entry_y, LINE_CHARS["corner_top_left"])

                # 8. Horizontal line from margin to target
                for x in range(route_x + 1, entry_x - 1):
                    current = canvas.get(x, entry_y)
                    if current == LINE_CHARS["vertical"]:
                        canvas.set(x, entry_y, LINE_CHARS["cross"])
                    elif current == LINE_CHARS["corner_top_left"]:
                        canvas.set(x, entry_y, LINE_CHARS["tee_down"])
                    elif current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(x, entry_y, LINE_CHARS["horizontal"])

                # 9. Arrow one column before target box
                canvas.set(entry_x - 1, entry_y, ARROW_CHARS["right"])

    def draw_edges_horizontal(
        self,
        canvas: Canvas,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
        column_boundaries: List[ColumnBoundary],
        title_height: int = 0,
    ) -> None:
        """
        Draw all forward edges in horizontal (LR) mode.

        Args:
            canvas: The canvas to draw on.
            layout_result: The layout result with edge information.
            box_dimensions: Dictionary of box dimensions.
            box_positions: Dictionary of box positions.
            column_boundaries: List of column boundary information.
            title_height: Height of title area (for offset calculations).
        """
        # Set box regions to avoid when drawing lines
        self._set_box_regions(box_positions, box_dimensions)

        # Build lookup for node layers
        node_layer = {name: node.layer for name, node in layout_result.nodes.items()}

        # Group edges by source to allocate ports properly
        edges_from: Dict[str, List[str]] = {}
        edges_to: Dict[str, List[str]] = {}

        for source, target in layout_result.edges:
            # Skip back edges
            if (source, target) in layout_result.back_edges:
                continue

            src_layer = node_layer.get(source, 0)
            tgt_layer = node_layer.get(target, 0)

            # Only draw forward edges (target layer > source layer)
            if tgt_layer <= src_layer:
                continue

            if source not in edges_from:
                edges_from[source] = []
            edges_from[source].append(target)

            if target not in edges_to:
                edges_to[target] = []
            edges_to[target].append(source)

        # Sort edges for consistent port allocation (by vertical position)
        for source in edges_from:
            edges_from[source].sort(key=lambda t: box_positions[t][1])
        for target in edges_to:
            edges_to[target].sort(key=lambda s: box_positions[s][1])

        # Draw each forward edge
        for source, target in layout_result.edges:
            if (source, target) in layout_result.back_edges:
                continue

            src_layer = node_layer.get(source, 0)
            tgt_layer = node_layer.get(target, 0)

            if tgt_layer <= src_layer:
                continue

            self._draw_edge_horizontal(
                canvas,
                source,
                target,
                box_dimensions,
                box_positions,
                edges_from.get(source, []),
                edges_to.get(target, []),
                column_boundaries,
                src_layer,
                tgt_layer,
                layout_result,
            )

    def _draw_edge_horizontal(
        self,
        canvas: Canvas,
        source: str,
        target: str,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
        source_targets: List[str],
        target_sources: List[str],
        column_boundaries: List[ColumnBoundary],
        src_layer: int,
        tgt_layer: int,
        layout_result: LayoutResult,
    ) -> None:
        """Draw a single edge from source to target in horizontal (LR) mode."""
        src_dims = box_dimensions[source]
        tgt_dims = box_dimensions[target]
        src_x, src_y = box_positions[source]
        tgt_x, tgt_y = box_positions[target]

        # Check if target is actually to the right of source (accounting for box width)
        # This can fail when nodes are grouped and stacked vertically
        src_right = src_x + src_dims.width + (1 if self.shadow else 0)
        target_is_right_of_source = tgt_x > src_right

        if not target_is_right_of_source:
            # Target is at same x or to the left (due to grouping)
            # Route around: exit right, go to routing column,
            # go down/up, enter from left
            self._draw_edge_horizontal_stacked(
                canvas,
                source,
                target,
                box_dimensions,
                box_positions,
                source_targets,
                target_sources,
                layout_result,
            )
            return

        # Check if boxes overlap vertically (inside borders)
        # For compact boxes (height 3), there's only one content row at y+1
        src_top = src_y + 1
        src_bottom = src_y + src_dims.height - 2
        tgt_top = tgt_y + 1
        tgt_bottom = tgt_y + tgt_dims.height - 2

        # Ensure bottom >= top for single-row content
        if src_bottom < src_top:
            src_bottom = src_top
        if tgt_bottom < tgt_top:
            tgt_bottom = tgt_top

        overlap_top = max(src_top, tgt_top)
        overlap_bottom = min(src_bottom, tgt_bottom)
        # Use <= to include single-row overlap (compact boxes)
        has_overlap = overlap_top <= overlap_bottom

        # Check if there are ANY boxes that would block a direct path
        # This includes boxes at the same x level (due to grouping)
        # or in intermediate columns
        boxes_in_path = False
        if has_overlap:
            # Calculate the path region
            path_x_min = src_x + src_dims.width  # After source
            path_x_max = tgt_x  # Before target
            path_y_min = min(overlap_top, overlap_bottom) - 1
            path_y_max = max(overlap_top, overlap_bottom) + 1

            # Find all boxes in this path region
            blocking_boxes = self._find_boxes_in_region(
                box_positions,
                box_dimensions,
                exclude_nodes={source, target},
                x_min=path_x_min,
                x_max=path_x_max,
                y_min=path_y_min,
                y_max=path_y_max,
            )
            boxes_in_path = len(blocking_boxes) > 0

        # Check if other targets from this source require fan-out routing
        # If so, we should use fan-out routing for ALL edges to avoid crossing
        other_targets_need_fanout = False
        if len(source_targets) > 1:
            for t in source_targets:
                if t == target:
                    continue
                t_dims = box_dimensions[t]
                t_x, t_y = box_positions[t]
                t_top = t_y + 1
                t_bottom = t_y + t_dims.height - 2
                # Adjust for compact boxes with single content row
                if t_bottom < t_top:
                    t_bottom = t_top
                t_overlap_top = max(src_top, t_top)
                t_overlap_bottom = min(src_bottom, t_bottom)
                # Use > for NO overlap (opposite of <= check)
                if t_overlap_top > t_overlap_bottom:
                    # This target has no vertical overlap, will use fan-out routing
                    other_targets_need_fanout = True
                    break

        if has_overlap and not boxes_in_path and not other_targets_need_fanout:
            # Boxes overlap vertically and no obstructions
            overlapping_targets = []
            for t in source_targets:
                t_dims = box_dimensions[t]
                t_x, t_y = box_positions[t]
                t_top = t_y + 1
                t_bottom = t_y + t_dims.height - 2
                # Adjust for compact boxes with single content row
                if t_bottom < t_top:
                    t_bottom = t_top
                t_overlap_top = max(src_top, t_top)
                t_overlap_bottom = min(src_bottom, t_bottom)
                # Use <= for single-row overlap (compact boxes)
                if t_overlap_top <= t_overlap_bottom:
                    overlapping_targets.append(t)

            # Distribute ports within the overlap region
            # For compact boxes, overlap_height may be 0, so use at least 1
            overlap_height = max(1, overlap_bottom - overlap_top)
            overlap_count = len(overlapping_targets)
            overlap_idx = overlapping_targets.index(target)

            if overlap_count == 1:
                port_y = (overlap_top + overlap_bottom) // 2
            else:
                if overlap_height >= overlap_count * 2:
                    spacing = overlap_height // (overlap_count + 1)
                    port_y = overlap_top + spacing * (overlap_idx + 1)
                else:
                    port_y = overlap_top + (overlap_height * (overlap_idx + 1)) // (
                        overlap_count + 1
                    )

            src_port_y = port_y
            tgt_port_y = port_y
        else:
            # No vertical overlap or boxes in path - use distributed ports
            src_port_count = len(source_targets)
            src_port_idx = source_targets.index(target)
            src_port_y = self.position_calculator.calculate_port_y(
                src_y, src_dims.height, src_port_idx, src_port_count
            )

            tgt_port_count = len(target_sources)
            tgt_port_idx = target_sources.index(source)
            tgt_port_y = self.position_calculator.calculate_port_y(
                tgt_y, tgt_dims.height, tgt_port_idx, tgt_port_count
            )

        # Exit from right side of source box
        src_port_x = src_x + src_dims.width - 1
        # Enter left side of target box
        tgt_port_x = tgt_x

        # Note: We don't modify the box border in LR mode - the edge line
        # starts just outside the box border to avoid visual overlap

        # Calculate path
        start_x = src_port_x + 1  # After source (through shadow)
        end_x = tgt_port_x

        # Check if we need to route around boxes
        if boxes_in_path:
            # Route below all boxes to avoid crossing them
            max_bottom_y = src_y + src_dims.height
            for layer_idx in range(src_layer + 1, tgt_layer):
                for node_name in layout_result.layers[layer_idx]:
                    node_dims = box_dimensions[node_name]
                    node_x, node_y = box_positions[node_name]
                    node_bottom = node_y + node_dims.height + (2 if self.shadow else 0)
                    max_bottom_y = max(max_bottom_y, node_bottom)

            # Route: right, down to bypass, right, up to target
            route_y = max_bottom_y + 2  # Go 2 rows below all boxes

            # Use the mid_x from source layer for the first vertical segment
            mid_x = self._get_safe_vertical_x(column_boundaries, src_layer, start_x)

            # Horizontal from source to mid
            self._draw_horizontal_line(canvas, start_x - 1, mid_x, src_port_y)

            # Corner turning down (use smart corner setter)
            self._set_corner(canvas, mid_x, src_port_y, "top_right")

            # Vertical segment down to route_y
            self._draw_vertical_line(canvas, mid_x, src_port_y + 1, route_y - 1)

            # Corner turning right (use smart corner setter)
            self._set_corner(canvas, mid_x, route_y, "bottom_left")

            # Find the x position for the vertical segment before the target
            tgt_mid_x = self._get_safe_vertical_x(
                column_boundaries, tgt_layer - 1, start_x
            )

            # Horizontal segment below boxes
            self._draw_horizontal_line(canvas, mid_x, tgt_mid_x, route_y)

            # Corner turning up (use smart corner setter)
            self._set_corner(canvas, tgt_mid_x, route_y, "bottom_right")

            # Vertical segment up toward target
            self._draw_vertical_line(canvas, tgt_mid_x, tgt_port_y + 1, route_y - 1)

            # Corner turning right to target (use smart corner setter)
            self._set_corner(canvas, tgt_mid_x, tgt_port_y, "top_left")

            # Horizontal to target
            self._draw_horizontal_line(canvas, tgt_mid_x, end_x - 1, tgt_port_y)

            # Arrow
            canvas.set(tgt_port_x - 1, tgt_port_y, ARROW_CHARS["right"])

        elif src_port_y == tgt_port_y and not other_targets_need_fanout:
            # Direct horizontal line
            # Only use direct horizontal when there's no fan-out from this source
            # Note: _draw_horizontal_line is exclusive of endpoints, so we adjust
            # start_x - 1 so the line begins at start_x, and end_x - 1 so it ends
            # at end_x - 2 (one position before the arrow at end_x - 1)
            self._draw_horizontal_line(canvas, start_x - 1, end_x - 1, src_port_y)
            canvas.set(tgt_port_x - 1, tgt_port_y, ARROW_CHARS["right"])
        else:
            # Need to route with vertical segment
            # Use column-aware routing: place vertical segment in the gap zone
            # to the right of the source layer where no boxes can exist
            mid_x = self._get_safe_vertical_x(column_boundaries, src_layer, start_x)

            # Horizontal from source to mid
            # Adjust for exclusive endpoints: start_x - 1 so line begins at start_x,
            # mid_x so line ends at mid_x - 1 (just before the corner at mid_x)
            self._draw_horizontal_line(canvas, start_x - 1, mid_x, src_port_y)

            # Corner at source row (use smart corner setter for proper junctions)
            if src_port_y == tgt_port_y:
                # Target is directly to the right of source - draw horizontal at mid_x
                # to connect the two horizontal segments. Other edges going up/down
                # will convert this to appropriate tees via _set_corner.
                current = canvas.get(mid_x, src_port_y)
                if current in (" ", BOX_CHARS["shadow"]):
                    canvas.set(mid_x, src_port_y, LINE_CHARS["horizontal"])
                # If there's already something there, _set_corner from other edges
                # will have handled it correctly
            elif tgt_port_y > src_port_y:
                self._set_corner(canvas, mid_x, src_port_y, "top_right")
            else:
                self._set_corner(canvas, mid_x, src_port_y, "bottom_right")

            # Vertical segment (draw between corners, not including corner positions)
            # Only draw if there's actually space between the corners
            if tgt_port_y > src_port_y:
                if src_port_y + 1 <= tgt_port_y - 1:
                    self._draw_vertical_line(
                        canvas, mid_x, src_port_y + 1, tgt_port_y - 1
                    )
            elif tgt_port_y < src_port_y:
                if tgt_port_y + 1 <= src_port_y - 1:
                    self._draw_vertical_line(
                        canvas, mid_x, tgt_port_y + 1, src_port_y - 1
                    )
            # If src_port_y == tgt_port_y, no vertical segment needed

            # Corner at target row (use smart corner setter for proper junctions)
            # Skip if target is at same y as source (already handled above)
            if tgt_port_y != src_port_y:
                if tgt_port_y > src_port_y:
                    self._set_corner(canvas, mid_x, tgt_port_y, "bottom_left")
                else:
                    self._set_corner(canvas, mid_x, tgt_port_y, "top_left")

            # Horizontal from mid to target
            # Adjust for exclusive endpoints: mid_x so line begins at mid_x + 1,
            # end_x - 1 so line ends at end_x - 2 (just before the arrow at end_x - 1)
            self._draw_horizontal_line(canvas, mid_x, end_x - 1, tgt_port_y)

            # Arrow
            canvas.set(tgt_port_x - 1, tgt_port_y, ARROW_CHARS["right"])

    def _draw_edge_horizontal_stacked(
        self,
        canvas: Canvas,
        source: str,
        target: str,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
        source_targets: List[str],
        target_sources: List[str],
        layout_result: LayoutResult,
    ) -> None:
        """
        Draw an edge when source and target are vertically stacked (same x-position).

        This happens when nodes are grouped together in LR mode. The edge routes
        vertically between the boxes - exiting from bottom/top and entering from
        top/bottom. If there are intermediate boxes in the path, routes around
        them to the right.
        """
        src_dims = box_dimensions[source]
        tgt_dims = box_dimensions[target]
        src_x, src_y = box_positions[source]
        tgt_x, tgt_y = box_positions[target]

        # Determine which box is on top and which is on bottom
        if src_y < tgt_y:
            goes_down = True
            src_exit_y = src_y + src_dims.height - 1 + (1 if self.shadow else 0)
            tgt_entry_y = tgt_y
            path_top_y = src_exit_y
            path_bottom_y = tgt_entry_y
        else:
            goes_down = False
            src_exit_y = src_y
            tgt_entry_y = tgt_y + tgt_dims.height - 1
            path_top_y = tgt_entry_y
            path_bottom_y = src_exit_y

        # Check for boxes in the vertical path between source and target
        boxes_in_path = []
        for node_name, (node_x, node_y) in box_positions.items():
            if node_name == source or node_name == target:
                continue
            node_dims = box_dimensions[node_name]
            node_top = node_y
            node_bottom = node_y + node_dims.height + (1 if self.shadow else 0)

            # Check if this box overlaps with the vertical path
            # Box must be in the x range AND y range
            overlaps_y = node_top < path_bottom_y and node_bottom > path_top_y
            # Check x overlap - boxes at similar x positions
            src_left = src_x
            src_right = src_x + src_dims.width + (1 if self.shadow else 0)
            node_left = node_x
            node_right = node_x + node_dims.width + (1 if self.shadow else 0)
            overlaps_x = node_left < src_right and node_right > src_left

            if overlaps_y and overlaps_x:
                boxes_in_path.append((node_name, node_x, node_y, node_dims))

        # Calculate horizontal port positions
        src_port_count = len(source_targets)
        src_port_idx = source_targets.index(target)
        tgt_port_count = len(target_sources)
        tgt_port_idx = target_sources.index(source)

        def calculate_port_x(
            box_x: int, box_width: int, port_idx: int, port_count: int
        ) -> int:
            content_start = box_x + 1
            content_width = box_width - 2
            if port_count == 1:
                return content_start + content_width // 2
            else:
                spacing = content_width // (port_count + 1)
                return content_start + spacing * (port_idx + 1)

        src_port_x = calculate_port_x(
            src_x, src_dims.width, src_port_idx, src_port_count
        )
        tgt_port_x = calculate_port_x(
            tgt_x, tgt_dims.width, tgt_port_idx, tgt_port_count
        )

        if boxes_in_path:
            # Route around intermediate boxes - go to the right side
            max_right_x = src_x + src_dims.width + (1 if self.shadow else 0)
            max_right_x = max(
                max_right_x, tgt_x + tgt_dims.width + (1 if self.shadow else 0)
            )
            for _, node_x, _, node_dims in boxes_in_path:
                node_right = node_x + node_dims.width + (2 if self.shadow else 0)
                max_right_x = max(max_right_x, node_right)

            route_x = max_right_x + 2  # Route 2 chars to the right of all boxes

            # Exit source from right side
            src_port_y = self.position_calculator.calculate_port_y(
                src_y, src_dims.height, src_port_idx, src_port_count
            )
            src_right_x = src_x + src_dims.width - 1

            # Enter target from right side
            tgt_port_y = self.position_calculator.calculate_port_y(
                tgt_y, tgt_dims.height, tgt_port_idx, tgt_port_count
            )
            tgt_right_x = tgt_x + tgt_dims.width - 1

            # Draw: horizontal from source right to route_x
            self._draw_horizontal_line(canvas, src_right_x, route_x, src_port_y)

            # Corner at route_x turning down/up
            if goes_down:
                self._set_corner(canvas, route_x, src_port_y, "top_right")
            else:
                self._set_corner(canvas, route_x, src_port_y, "bottom_right")

            # Vertical segment
            if goes_down:
                self._draw_vertical_line(
                    canvas, route_x, src_port_y + 1, tgt_port_y - 1
                )
            else:
                self._draw_vertical_line(
                    canvas, route_x, tgt_port_y + 1, src_port_y - 1
                )

            # Corner at target row turning left
            if goes_down:
                self._set_corner(canvas, route_x, tgt_port_y, "bottom_left")
            else:
                self._set_corner(canvas, route_x, tgt_port_y, "top_left")

            # Horizontal from route_x back to target right
            self._draw_horizontal_line(canvas, tgt_right_x + 1, route_x, tgt_port_y)

            # Arrow pointing left at target right border
            canvas.set(tgt_right_x + 1, tgt_port_y, ARROW_CHARS["left"])

        elif src_port_x == tgt_port_x:
            # Direct vertical line (no intermediate boxes, same x port)
            if goes_down:
                self._draw_vertical_line(
                    canvas, src_port_x, src_exit_y, tgt_entry_y - 2
                )
                canvas.set(src_port_x, tgt_entry_y - 1, ARROW_CHARS["down"])
            else:
                self._draw_vertical_line(
                    canvas, src_port_x, tgt_entry_y + 2, src_exit_y
                )
                canvas.set(src_port_x, tgt_entry_y + 1, ARROW_CHARS["up"])
        else:
            # Route with horizontal segment (no intermediate boxes, different x ports)
            if goes_down:
                mid_y = (src_exit_y + tgt_entry_y) // 2
                self._draw_vertical_line(canvas, src_port_x, src_exit_y, mid_y)

                if tgt_port_x > src_port_x:
                    self._set_corner(canvas, src_port_x, mid_y, "bottom_left")
                    self._set_corner(canvas, tgt_port_x, mid_y, "top_right")
                else:
                    self._set_corner(canvas, src_port_x, mid_y, "bottom_right")
                    self._set_corner(canvas, tgt_port_x, mid_y, "top_left")

                self._draw_horizontal_line(canvas, src_port_x, tgt_port_x, mid_y)
                self._draw_vertical_line(canvas, tgt_port_x, mid_y, tgt_entry_y - 2)
                canvas.set(tgt_port_x, tgt_entry_y - 1, ARROW_CHARS["down"])
            else:
                mid_y = (tgt_entry_y + src_exit_y) // 2
                self._draw_vertical_line(canvas, src_port_x, mid_y, src_exit_y)

                if tgt_port_x > src_port_x:
                    self._set_corner(canvas, src_port_x, mid_y, "top_left")
                    self._set_corner(canvas, tgt_port_x, mid_y, "bottom_right")
                else:
                    self._set_corner(canvas, src_port_x, mid_y, "top_right")
                    self._set_corner(canvas, tgt_port_x, mid_y, "bottom_left")

                self._draw_horizontal_line(canvas, src_port_x, tgt_port_x, mid_y)
                self._draw_vertical_line(canvas, tgt_port_x, tgt_entry_y + 2, mid_y)
                canvas.set(tgt_port_x, tgt_entry_y + 1, ARROW_CHARS["up"])

    def draw_back_edges_horizontal(
        self,
        canvas: Canvas,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
        title_height: int = 0,
    ) -> None:
        """
        Draw back edges (cycle edges) along the top margin in horizontal mode.

        Back edges exit from the top-right of the source box, route up
        to the margin, left along the margin, then down to enter the
        target from the top.

        If there are boxes between the margin and the target, the edge routes
        to the right of those boxes to avoid crossing through them.

        Args:
            canvas: The canvas to draw on.
            layout_result: The layout result with back edge information.
            box_dimensions: Dictionary of box dimensions.
            box_positions: Dictionary of box positions.
            title_height: Height of title area (for margin positioning).
        """
        if not layout_result.back_edges:
            return

        margin_y = 2 + title_height  # Starting route row for back edges

        # Sort back edges by source layer (draw deeper ones first)
        node_layer = {name: node.layer for name, node in layout_result.nodes.items()}

        sorted_back_edges = sorted(
            layout_result.back_edges,
            key=lambda e: node_layer.get(e[0], 0),
            reverse=True,
        )

        # Track entries per target for offset
        target_entry_count: Dict[str, int] = {}

        # Track used margin positions to offset multiple back edges
        margin_offset = 0

        for source, target in sorted_back_edges:
            src_dims = box_dimensions[source]
            tgt_dims = box_dimensions[target]
            src_x, src_y = box_positions[source]
            tgt_x, tgt_y = box_positions[target]

            # Use offset margin for multiple back edges
            route_y = margin_y + margin_offset
            margin_offset += 3  # Space out multiple back edges (increased for clarity)

            # Track how many edges already entered this target
            entry_idx = target_entry_count.get(target, 0)
            target_entry_count[target] = entry_idx + 1

            # Exit point: right side of source box, near top
            exit_border_x = src_x + src_dims.width - 1
            exit_right_x = exit_border_x + (2 if self.shadow else 1)

            # Entry point: top side of target box
            entry_y = tgt_y
            base_entry_x = tgt_x + 1
            entry_x = base_entry_x + entry_idx

            # Ensure entry_x is within the box
            max_entry_x = tgt_x + tgt_dims.width - 2
            if entry_x > max_entry_x:
                entry_x = max_entry_x

            # Check if there are boxes between margin and target that would block
            # the vertical path at entry_x
            boxes_in_descent_path = []
            for node_name, (node_x, node_y) in box_positions.items():
                if node_name == target:
                    continue
                node_dims = box_dimensions[node_name]
                node_right = node_x + node_dims.width + (1 if self.shadow else 0)
                node_bottom = node_y + node_dims.height + (2 if self.shadow else 0)

                # Check if this box is between margin and target vertically
                # AND overlaps with entry_x horizontally
                if node_y > route_y and node_bottom < entry_y:
                    if node_x <= entry_x < node_right:
                        boxes_in_descent_path.append(
                            (node_name, node_x, node_y, node_dims)
                        )

            # Draw the back edge path:
            # 1. Mark exit on source right side near top
            exit_y = src_y + 1 + (margin_offset - 3)
            if exit_y >= src_y + src_dims.height - 1:
                exit_y = src_y + 1

            # Note: We don't modify the box border in LR mode - the edge line
            # starts just outside the box border to avoid visual overlap

            # Check if there are boxes between source and margin that would block
            # the upward vertical path at exit_right_x
            boxes_in_ascent_path = []
            for node_name, (node_x, node_y) in box_positions.items():
                if node_name == source:
                    continue
                node_dims = box_dimensions[node_name]
                node_right = node_x + node_dims.width + (1 if self.shadow else 0)
                node_bottom = node_y + node_dims.height + (2 if self.shadow else 0)

                # Check if this box is between margin and source vertically
                # AND overlaps with exit_right_x horizontally
                if node_y > route_y and node_bottom < exit_y:
                    if node_x <= exit_right_x < node_right:
                        boxes_in_ascent_path.append(
                            (node_name, node_x, node_y, node_dims)
                        )

            if boxes_in_ascent_path:
                # Need to route around boxes on the way up to the margin
                # Strategy: go further right past all blocking boxes, then go up

                # Find the rightmost edge of blocking boxes
                max_blocking_right = max(
                    node_x + node_dims.width + (2 if self.shadow else 1)
                    for _, node_x, _, node_dims in boxes_in_ascent_path
                )

                # Turn up position: to the right of all blocking boxes
                turn_up_x = max_blocking_right + 1

                # 2a. Horizontal line right from source to turn_up_x
                for x in range(exit_border_x + 1, turn_up_x):
                    current = canvas.get(x, exit_y)
                    if current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(x, exit_y, LINE_CHARS["horizontal"])

                # 3a. Corner turning up at turn_up_x
                canvas.set(turn_up_x, exit_y, LINE_CHARS["corner_bottom_right"])

                # 4a. Vertical line up to margin
                for y in range(route_y + 1, exit_y):
                    current = canvas.get(turn_up_x, y)
                    if current == LINE_CHARS["horizontal"]:
                        canvas.set(turn_up_x, y, LINE_CHARS["cross"])
                    elif current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(turn_up_x, y, LINE_CHARS["vertical"])

                # 5a. Corner at margin (turning left)
                canvas.set(turn_up_x, route_y, LINE_CHARS["corner_top_right"])

                # Update exit_right_x for the horizontal line along margin
                exit_right_x = turn_up_x
            else:
                # No boxes in ascent path - draw directly
                # 2. Short horizontal line right from source (through shadow)
                for x in range(exit_border_x + 1, exit_right_x + 1):
                    canvas.set(x, exit_y, LINE_CHARS["horizontal"])

                # 3. Corner turning up (line enters from left, exits upward)
                canvas.set(exit_right_x, exit_y, LINE_CHARS["corner_bottom_right"])

                # 4. Vertical line up to margin
                for y in range(route_y + 1, exit_y):
                    current = canvas.get(exit_right_x, y)
                    if current == LINE_CHARS["horizontal"]:
                        canvas.set(exit_right_x, y, LINE_CHARS["cross"])
                    elif current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(exit_right_x, y, LINE_CHARS["vertical"])

                # 5. Corner at margin (turning left)
                canvas.set(exit_right_x, route_y, LINE_CHARS["corner_top_right"])

            # 6. Horizontal line left along the margin
            for x in range(entry_x + 1, exit_right_x):
                current = canvas.get(x, route_y)
                if current == LINE_CHARS["vertical"]:
                    canvas.set(x, route_y, LINE_CHARS["cross"])
                elif current == " " or current == BOX_CHARS["shadow"]:
                    canvas.set(x, route_y, LINE_CHARS["horizontal"])

            if boxes_in_descent_path:
                # Need to route around boxes
                # Strategy: continue LEFT on the margin past all blocking boxes,
                # then turn down and enter the target from the left side.
                # This avoids crossing boxes in the same column as the target.

                # Find the leftmost x of all blocking boxes
                min_blocking_left = min(
                    node_x for _, node_x, _, _ in boxes_in_descent_path
                )

                # Turn down position: to the left of all blocking boxes
                turn_down_x = min_blocking_left - 2

                # Calculate entry y position inside the target box
                target_entry_y = tgt_y + 1 + entry_idx
                max_target_entry_y = tgt_y + tgt_dims.height - 2
                if target_entry_y > max_target_entry_y:
                    target_entry_y = max_target_entry_y

                # Continue horizontal line from entry_x to turn_down_x
                # (the original line was drawn from exit_right_x to entry_x+1)
                for x in range(turn_down_x + 1, entry_x + 1):
                    current = canvas.get(x, route_y)
                    if current == LINE_CHARS["vertical"]:
                        canvas.set(x, route_y, LINE_CHARS["cross"])
                    elif current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(x, route_y, LINE_CHARS["horizontal"])

                # 7a. Corner at turn_down_x, route_y (turning down)
                canvas.set(turn_down_x, route_y, LINE_CHARS["corner_top_left"])

                # 8a. Vertical line down to target_entry_y
                for y in range(route_y + 1, target_entry_y):
                    current = canvas.get(turn_down_x, y)
                    if current == LINE_CHARS["horizontal"]:
                        canvas.set(turn_down_x, y, LINE_CHARS["cross"])
                    elif current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(turn_down_x, y, LINE_CHARS["vertical"])

                # 9a. Corner at turn_down_x, target_entry_y (turning right)
                corner_char = LINE_CHARS["corner_bottom_left"]
                canvas.set(turn_down_x, target_entry_y, corner_char)

                # 10a. Horizontal line to arrow position
                for x in range(turn_down_x + 1, tgt_x - 1):
                    current = canvas.get(x, target_entry_y)
                    if current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(x, target_entry_y, LINE_CHARS["horizontal"])

                # 11a. Arrow (entering from left)
                canvas.set(tgt_x - 1, target_entry_y, ARROW_CHARS["right"])
            else:
                # No boxes in path - draw directly
                # 7. Corner at target column (turning down)
                current = canvas.get(entry_x, route_y)
                if current == LINE_CHARS["horizontal"]:
                    canvas.set(entry_x, route_y, LINE_CHARS["tee_down"])
                elif current == LINE_CHARS["vertical"]:
                    canvas.set(entry_x, route_y, LINE_CHARS["tee_down"])
                elif current == " " or current == BOX_CHARS["shadow"]:
                    canvas.set(entry_x, route_y, LINE_CHARS["corner_top_left"])

                # 8. Vertical line from margin to target (stop before arrow)
                for y in range(route_y + 1, entry_y - 1):
                    current = canvas.get(entry_x, y)
                    if current == LINE_CHARS["horizontal"]:
                        canvas.set(entry_x, y, LINE_CHARS["cross"])
                    elif current == " " or current == BOX_CHARS["shadow"]:
                        canvas.set(entry_x, y, LINE_CHARS["vertical"])

                # 9. Arrow one row above target box
                canvas.set(entry_x, entry_y - 1, ARROW_CHARS["down"])
