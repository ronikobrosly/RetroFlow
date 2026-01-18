"""
Position calculation for flowchart layout.

This module handles all geometric calculations for positioning nodes on the canvas,
including:
- Box dimension calculations
- Node position calculations for both TB (top-to-bottom) and LR (left-to-right) modes
- Layer and column boundary calculations for edge routing
- Port position calculations for edge connections

The PositionCalculator class centralizes these calculations and is used by the
FlowchartGenerator to determine where each element should be placed.
"""

from typing import Dict, List, Set, Tuple

from .layout import LayoutResult
from .models import ColumnBoundary, GroupBoundary, GroupDefinition, LayerBoundary
from .renderer import BoxDimensions, BoxRenderer

# Constants for group spacing
GROUP_INTERNAL_PADDING = 3  # Space between group border and nodes
GROUP_EXTERNAL_MARGIN = 4  # Space between group box and adjacent elements
GROUP_TITLE_HEIGHT = 1  # Height reserved for group title
GROUP_EDGE_MARGIN = 3  # Minimum space between edges and group borders


class PositionCalculator:
    """
    Calculates positions for all flowchart elements.

    This class handles the geometric layout of nodes and boundaries
    for both vertical (TB) and horizontal (LR) flow directions.

    Attributes:
        box_renderer: Renderer for calculating box dimensions.
        min_box_width: Minimum width for node boxes.
        horizontal_spacing: Space between boxes horizontally.
        vertical_spacing: Space between boxes vertically.
        shadow: Whether boxes have shadows.
    """

    def __init__(
        self,
        box_renderer: BoxRenderer,
        min_box_width: int = 10,
        horizontal_spacing: int = 12,
        vertical_spacing: int = 3,
        shadow: bool = True,
    ):
        """
        Initialize the position calculator.

        Args:
            box_renderer: Renderer for calculating box dimensions.
            min_box_width: Minimum width for node boxes.
            horizontal_spacing: Space between boxes horizontally.
            vertical_spacing: Space between boxes vertically.
            shadow: Whether boxes have shadows.
        """
        self.box_renderer = box_renderer
        self.min_box_width = min_box_width
        self.horizontal_spacing = horizontal_spacing
        self.vertical_spacing = vertical_spacing
        self.shadow = shadow

    def calculate_all_box_dimensions(
        self, layout_result: LayoutResult
    ) -> Dict[str, BoxDimensions]:
        """
        Calculate dimensions for all boxes, ensuring minimum size.

        Args:
            layout_result: The layout result containing node information.

        Returns:
            Dictionary mapping node names to their BoxDimensions.
        """
        dimensions = {}

        for node_name in layout_result.nodes:
            dims = self.box_renderer.calculate_box_dimensions(node_name)

            # Ensure minimum width
            if dims.width < self.min_box_width:
                dims = BoxDimensions(
                    width=self.min_box_width,
                    height=dims.height,
                    text_lines=dims.text_lines,
                    padding=dims.padding,
                )

            dimensions[node_name] = dims

        return dimensions

    def calculate_positions(
        self,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        left_margin: int = 0,
    ) -> Dict[str, Tuple[int, int]]:
        """
        Calculate actual x,y positions for each box in TB (top-to-bottom) mode.

        Centers nodes within each layer.

        Args:
            layout_result: The layout result from the layout engine.
            box_dimensions: Dictionary of box dimensions.
            left_margin: Extra space on left for back edge routing.

        Returns:
            Dictionary mapping node names to (x, y) positions.
        """
        positions: Dict[str, Tuple[int, int]] = {}

        # Calculate dimensions for each layer
        layer_heights: List[int] = []
        layer_widths: List[List[int]] = []

        for layer in layout_result.layers:
            max_height = 0
            widths = []

            for node_name in layer:
                dims = box_dimensions[node_name]
                # Include shadow in height calculation
                box_height = dims.height + (2 if self.shadow else 0)
                max_height = max(max_height, box_height)
                # Include shadow in width calculation
                box_width = dims.width + (1 if self.shadow else 0)
                widths.append(box_width)

            layer_heights.append(max_height)
            layer_widths.append(widths)

        # Calculate cumulative y positions (top of each layer)
        y_positions: List[int] = [0]
        for height in layer_heights[:-1]:
            y_positions.append(y_positions[-1] + height + self.vertical_spacing)

        # Calculate total width of each layer
        layer_total_widths = []
        for widths in layer_widths:
            if widths:
                total = sum(widths) + self.horizontal_spacing * (len(widths) - 1)
            else:
                total = 0
            layer_total_widths.append(total)

        # Find maximum layer width for centering
        max_layer_width = max(layer_total_widths) if layer_total_widths else 0

        # Assign x,y positions
        for layer_idx, layer in enumerate(layout_result.layers):
            widths = layer_widths[layer_idx]
            total_width = layer_total_widths[layer_idx]

            # Center this layer, plus left margin for back edges
            start_x = left_margin + (max_layer_width - total_width) // 2

            current_x = start_x
            for pos_idx, node_name in enumerate(layer):
                positions[node_name] = (current_x, y_positions[layer_idx])
                current_x += widths[pos_idx] + self.horizontal_spacing

        return positions

    def calculate_positions_horizontal(
        self,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        top_margin: int = 0,
    ) -> Dict[str, Tuple[int, int]]:
        """
        Calculate actual x,y positions for each box in LR (left-to-right) mode.

        Layers become columns, nodes within a layer stack vertically.

        Args:
            layout_result: The layout result from the layout engine.
            box_dimensions: Dictionary of box dimensions.
            top_margin: Extra space on top for back edge routing.

        Returns:
            Dictionary mapping node names to (x, y) positions.
        """
        positions: Dict[str, Tuple[int, int]] = {}

        # Calculate dimensions for each layer (now columns)
        layer_widths: List[int] = []  # Max width per layer (column)
        layer_heights: List[List[int]] = []  # Heights of nodes in each layer

        for layer in layout_result.layers:
            max_width = 0
            heights = []

            for node_name in layer:
                dims = box_dimensions[node_name]
                # Include shadow in width calculation
                box_width = dims.width + (1 if self.shadow else 0)
                max_width = max(max_width, box_width)
                # Include shadow in height calculation
                box_height = dims.height + (2 if self.shadow else 0)
                heights.append(box_height)

            layer_widths.append(max_width)
            layer_heights.append(heights)

        # Calculate cumulative x positions (left edge of each layer/column)
        x_positions: List[int] = [0]
        for width in layer_widths[:-1]:
            x_positions.append(x_positions[-1] + width + self.horizontal_spacing)

        # Calculate total height of each layer (column)
        layer_total_heights = []
        for heights in layer_heights:
            if heights:
                total = sum(heights) + self.vertical_spacing * (len(heights) - 1)
            else:
                total = 0
            layer_total_heights.append(total)

        # Find maximum layer height for centering
        max_layer_height = max(layer_total_heights) if layer_total_heights else 0

        # Assign x,y positions
        for layer_idx, layer in enumerate(layout_result.layers):
            heights = layer_heights[layer_idx]
            total_height = layer_total_heights[layer_idx]

            # Center this layer vertically, plus top margin for back edges
            start_y = top_margin + (max_layer_height - total_height) // 2

            current_y = start_y
            for pos_idx, node_name in enumerate(layer):
                positions[node_name] = (x_positions[layer_idx], current_y)
                current_y += heights[pos_idx] + self.vertical_spacing

        return positions

    def calculate_layer_boundaries(
        self,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
    ) -> List[LayerBoundary]:
        """
        Calculate the y-boundaries for each layer.

        This information is used for safe edge routing - horizontal segments
        should be placed in the gaps between layers where no boxes exist.

        Args:
            layout_result: The layout result from the layout engine.
            box_dimensions: Dictionary of box dimensions.

        Returns:
            List of LayerBoundary objects, one per layer.
        """
        boundaries: List[LayerBoundary] = []

        # Calculate layer heights (same logic as calculate_positions)
        layer_heights: List[int] = []
        for layer in layout_result.layers:
            max_height = 0
            for node_name in layer:
                dims = box_dimensions[node_name]
                box_height = dims.height + (2 if self.shadow else 0)
                max_height = max(max_height, box_height)
            layer_heights.append(max_height)

        # Calculate y positions for each layer
        y_positions: List[int] = [0]
        for height in layer_heights[:-1]:
            y_positions.append(y_positions[-1] + height + self.vertical_spacing)

        # Build boundary objects
        num_layers = len(layout_result.layers)
        for i in range(num_layers):
            top_y = y_positions[i]
            bottom_y = top_y + layer_heights[i] - 1  # -1 because it's inclusive

            # Gap starts after the shadow (bottom_y is already inclusive of shadow)
            gap_start_y = top_y + layer_heights[i]

            # Gap ends at the start of the next layer (or canvas edge)
            if i < num_layers - 1:
                gap_end_y = y_positions[i + 1] - 1
            else:
                gap_end_y = gap_start_y + self.vertical_spacing  # Last layer

            boundaries.append(
                LayerBoundary(
                    layer_idx=i,
                    top_y=top_y,
                    bottom_y=bottom_y,
                    gap_start_y=gap_start_y,
                    gap_end_y=gap_end_y,
                )
            )

        return boundaries

    def calculate_column_boundaries(
        self,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
    ) -> List[ColumnBoundary]:
        """
        Calculate the x-boundaries for each column (layer in LR mode).

        This information is used for safe edge routing - vertical segments
        should be placed in the gaps between columns where no boxes exist.

        Args:
            layout_result: The layout result from the layout engine.
            box_dimensions: Dictionary of box dimensions.

        Returns:
            List of ColumnBoundary objects, one per layer/column.
        """
        boundaries: List[ColumnBoundary] = []

        # Calculate layer widths (same logic as calculate_positions_horizontal)
        layer_widths: List[int] = []
        for layer in layout_result.layers:
            max_width = 0
            for node_name in layer:
                dims = box_dimensions[node_name]
                box_width = dims.width + (1 if self.shadow else 0)
                max_width = max(max_width, box_width)
            layer_widths.append(max_width)

        # Calculate x positions for each layer
        x_positions: List[int] = [0]
        for width in layer_widths[:-1]:
            x_positions.append(x_positions[-1] + width + self.horizontal_spacing)

        # Build boundary objects
        num_layers = len(layout_result.layers)
        for i in range(num_layers):
            left_x = x_positions[i]
            right_x = left_x + layer_widths[i] - 1  # -1 because it's inclusive

            # Gap starts after the shadow (right_x is already inclusive of shadow)
            gap_start_x = left_x + layer_widths[i]

            # Gap ends at the start of the next layer (or canvas edge)
            if i < num_layers - 1:
                gap_end_x = x_positions[i + 1] - 1
            else:
                gap_end_x = gap_start_x + self.horizontal_spacing  # Last layer

            boundaries.append(
                ColumnBoundary(
                    layer_idx=i,
                    left_x=left_x,
                    right_x=right_x,
                    gap_start_x=gap_start_x,
                    gap_end_x=gap_end_x,
                )
            )

        return boundaries

    def calculate_canvas_size(
        self,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
    ) -> Tuple[int, int]:
        """
        Calculate required canvas dimensions.

        Args:
            box_dimensions: Dictionary of box dimensions.
            box_positions: Dictionary of box positions.

        Returns:
            Tuple of (width, height) for the canvas.
        """
        max_x = 0
        max_y = 0

        for node_name, (x, y) in box_positions.items():
            dims = box_dimensions[node_name]
            right = x + dims.width + (2 if self.shadow else 0)
            bottom = y + dims.height + (2 if self.shadow else 0)
            max_x = max(max_x, right)
            max_y = max(max_y, bottom)

        return max_x, max_y

    def calculate_port_x(
        self, box_x: int, box_width: int, port_idx: int, port_count: int
    ) -> int:
        """
        Calculate x position for a port on a box (vertical mode).

        Args:
            box_x: X position of the box.
            box_width: Width of the box.
            port_idx: Index of this port (0-based).
            port_count: Total number of ports.

        Returns:
            X coordinate for the port.
        """
        if port_count == 1:
            # Single port: center of box
            return box_x + box_width // 2
        else:
            # Multiple ports: distribute evenly
            usable_width = box_width - 4  # Leave margins
            spacing = usable_width // (port_count + 1)
            return box_x + 2 + spacing * (port_idx + 1)

    def calculate_port_y(
        self, box_y: int, box_height: int, port_idx: int, port_count: int
    ) -> int:
        """
        Calculate y position for a port on a box (horizontal mode).

        Args:
            box_y: Y position of the box.
            box_height: Height of the box.
            port_idx: Index of this port (0-based).
            port_count: Total number of ports.

        Returns:
            Y coordinate for the port.
        """
        # Content rows are between top and bottom borders
        # For compact box (height 3): only row box_y + 1 is content
        # For non-compact box (height 5+): rows box_y + 2 to box_y + height - 3
        content_top = box_y + 1
        content_bottom = box_y + box_height - 2

        # Ensure we have at least one valid row
        if content_bottom < content_top:
            content_bottom = content_top

        content_height = content_bottom - content_top + 1

        if port_count == 1 or content_height == 1:
            # Single port or single content row: use middle of content area
            return content_top + content_height // 2
        else:
            # Multiple ports: distribute across content rows
            # Ensure spacing is at least 1 to avoid overlapping ports
            spacing = max(1, content_height // (port_count + 1))
            port_y = content_top + spacing * (port_idx + 1)
            # Clamp to valid content range
            return min(max(port_y, content_top), content_bottom)

    def calculate_group_boundaries(
        self,
        groups: List[GroupDefinition],
        box_positions: Dict[str, Tuple[int, int]],
        box_dimensions: Dict[str, BoxDimensions],
        padding: int = GROUP_INTERNAL_PADDING,
        title_height: int = GROUP_TITLE_HEIGHT,
    ) -> List[GroupBoundary]:
        """
        Calculate bounding boxes for each group.

        For each group:
        1. Find min/max x and y of all member nodes (including their shadows)
        2. Add internal padding
        3. Calculate title position (centered above)

        Args:
            groups: List of group definitions.
            box_positions: Dictionary of node (x, y) positions.
            box_dimensions: Dictionary of node dimensions.
            padding: Internal padding between group border and nodes.
            title_height: Height reserved for group title.

        Returns:
            List of GroupBoundary objects with calculated positions.
        """
        boundaries: List[GroupBoundary] = []

        for group in groups:
            # Find members that actually have positions (some may not be in graph)
            valid_members = [m for m in group.members if m in box_positions]

            if not valid_members:
                continue

            # Calculate bounding box of all member nodes
            min_x = float("inf")
            min_y = float("inf")
            max_x = float("-inf")
            max_y = float("-inf")

            for member in valid_members:
                x, y = box_positions[member]
                dims = box_dimensions[member]

                # Include shadow in the calculations
                shadow_offset_x = 1 if self.shadow else 0
                shadow_offset_y = 2 if self.shadow else 0

                node_right = x + dims.width + shadow_offset_x
                node_bottom = y + dims.height + shadow_offset_y

                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, node_right)
                max_y = max(max_y, node_bottom)

            # Add padding around the bounding box
            group_x = int(min_x) - padding
            group_y = int(min_y) - padding - title_height  # Leave room for title
            group_width = int(max_x - min_x) + 2 * padding
            group_height = int(max_y - min_y) + 2 * padding + title_height

            # Ensure title fits
            title_text_width = len(group.name)
            if title_text_width + 2 > group_width:
                # Expand group to fit title
                extra = title_text_width + 2 - group_width
                group_x -= extra // 2
                group_width = title_text_width + 2

            # Calculate title position (centered above the box)
            title_x = group_x + (group_width - title_text_width) // 2

            boundaries.append(
                GroupBoundary(
                    name=group.name,
                    members=valid_members,
                    x=group_x,
                    y=group_y,
                    width=group_width,
                    height=group_height,
                    title_x=title_x,
                    title_y=group_y,
                    title_width=title_text_width,
                )
            )

        return boundaries

    def resolve_group_overlaps(
        self,
        group_boundaries: List[GroupBoundary],
        box_positions: Dict[str, Tuple[int, int]],
        box_dimensions: Dict[str, BoxDimensions],
        direction: str = "TB",
    ) -> Tuple[Dict[str, Tuple[int, int]], List[GroupBoundary]]:
        """
        Detect and resolve overlapping group boundaries.

        When groups overlap, shift node positions to create proper spacing
        between group boxes.

        Args:
            group_boundaries: List of calculated group boundaries.
            box_positions: Dictionary of node (x, y) positions.
            box_dimensions: Dictionary of node dimensions.
            direction: Flow direction ("TB" or "LR").

        Returns:
            Tuple of (adjusted box_positions, recalculated group_boundaries).
        """
        if len(group_boundaries) < 2:
            return box_positions, group_boundaries

        # Create a mutable copy of positions
        new_positions = dict(box_positions)
        margin = GROUP_EXTERNAL_MARGIN

        # Sort groups by their primary axis position
        if direction == "TB":
            # Sort by y (top to bottom)
            sorted_groups = sorted(group_boundaries, key=lambda g: g.y)

            # Check each pair of groups for vertical overlap
            for i in range(len(sorted_groups)):
                for j in range(i + 1, len(sorted_groups)):
                    g1, g2 = sorted_groups[i], sorted_groups[j]

                    # Check horizontal overlap (must overlap to need adjustment)
                    h_overlap = not (
                        g1.x + g1.width + margin < g2.x
                        or g2.x + g2.width + margin < g1.x
                    )

                    if not h_overlap:
                        continue

                    # Check vertical overlap
                    g1_bottom = g1.y + g1.height + (2 if self.shadow else 0)
                    g2_top = g2.y

                    if g1_bottom + margin > g2_top:
                        # Groups overlap vertically - shift g2 and its members down
                        shift = g1_bottom + margin - g2_top + 1

                        for member in g2.members:
                            if member in new_positions:
                                x, y = new_positions[member]
                                new_positions[member] = (x, y + shift)
        else:
            # LR mode: Sort by x (left to right)
            sorted_groups = sorted(group_boundaries, key=lambda g: g.x)

            # Check each pair of groups for horizontal overlap
            for i in range(len(sorted_groups)):
                for j in range(i + 1, len(sorted_groups)):
                    g1, g2 = sorted_groups[i], sorted_groups[j]

                    # Check vertical overlap (must overlap to need adjustment)
                    v_overlap = not (
                        g1.y + g1.height + margin < g2.y
                        or g2.y + g2.height + margin < g1.y
                    )

                    if not v_overlap:
                        continue

                    # Check horizontal overlap
                    g1_right = g1.x + g1.width + (2 if self.shadow else 0)
                    g2_left = g2.x

                    if g1_right + margin > g2_left:
                        # Groups overlap horizontally - shift g2 and its members right
                        shift = g1_right + margin - g2_left + 1

                        for member in g2.members:
                            if member in new_positions:
                                x, y = new_positions[member]
                                new_positions[member] = (x + shift, y)

        # Recalculate group boundaries with new positions
        groups = [
            GroupDefinition(name=g.name, members=g.members, order=i)
            for i, g in enumerate(group_boundaries)
        ]
        new_boundaries = self.calculate_group_boundaries(
            groups, new_positions, box_dimensions
        )

        return new_positions, new_boundaries

    def calculate_group_aware_positions(
        self,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        groups: List[GroupDefinition],
        direction: str = "TB",
        margin: int = 0,
    ) -> Dict[str, Tuple[int, int]]:
        """
        Calculate positions with group-aware spacing.

        In TB mode, all nodes within the same group are arranged horizontally
        (side-by-side) at the same y-level, regardless of their layer.
        In LR mode, all nodes within the same group are stacked vertically
        at the same x-position, regardless of their layer.

        Args:
            layout_result: The layout result from the layout engine.
            box_dimensions: Dictionary of box dimensions.
            groups: List of group definitions.
            direction: Flow direction ("TB" or "LR").
            margin: Extra margin for back edge routing.

        Returns:
            Dictionary mapping node names to (x, y) positions.
        """
        # Build a map of node -> group
        node_to_group: Dict[str, str] = {}
        group_name_to_def: Dict[str, GroupDefinition] = {}
        for group in groups:
            group_name_to_def[group.name] = group
            for member in group.members:
                node_to_group[member] = group.name

        # Build layer lookup
        node_to_layer: Dict[str, int] = {}
        for layer_idx, layer in enumerate(layout_result.layers):
            for node in layer:
                node_to_layer[node] = layer_idx

        # Group members by their group, keeping track of layer info
        group_members: Dict[str, List[str]] = {}
        for group in groups:
            valid_members = [m for m in group.members if m in node_to_layer]
            if valid_members:
                group_members[group.name] = valid_members

        if direction == "LR":
            return self._calculate_positions_lr_grouped(
                layout_result,
                box_dimensions,
                node_to_group,
                group_members,
                node_to_layer,
                margin,
            )
        else:
            return self._calculate_positions_tb_grouped(
                layout_result,
                box_dimensions,
                node_to_group,
                group_members,
                node_to_layer,
                margin,
            )

    def _calculate_positions_tb_grouped(
        self,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        node_to_group: Dict[str, str],
        group_members: Dict[str, List[str]],
        node_to_layer: Dict[str, int],
        left_margin: int = 0,
    ) -> Dict[str, Tuple[int, int]]:
        """
        Calculate positions in TB mode with group-aware layout.

        All nodes in a group are arranged HORIZONTALLY at the same y-level
        (at the y-level of the group's topmost layer).
        """
        positions: Dict[str, Tuple[int, int]] = {}

        # Calculate what the y-position would be for each layer (standard)
        layer_heights: List[int] = []
        for layer in layout_result.layers:
            max_height = 0
            for node_name in layer:
                dims = box_dimensions[node_name]
                box_height = dims.height + (2 if self.shadow else 0)
                max_height = max(max_height, box_height)
            layer_heights.append(max_height)

        # For each group, find the topmost layer (minimum layer index)
        group_top_layer: Dict[str, int] = {}
        for group_name, members in group_members.items():
            min_layer = min(node_to_layer[m] for m in members)
            group_top_layer[group_name] = min_layer

        # Calculate y positions with extra space for groups that span layers
        # Add extra space after layers where groups need room
        group_extra_height: Dict[str, int] = {}
        for group_name, members in group_members.items():
            if len(members) > 1:
                # Calculate total height needed for all group members
                total_height = (
                    sum(
                        box_dimensions[m].height + (2 if self.shadow else 0)
                        for m in members
                    )
                    + (len(members) - 1) * self.vertical_spacing
                )
                # Find max height in the group's top layer
                top_layer = group_top_layer[group_name]
                layer_max_height = layer_heights[top_layer]
                if total_height > layer_max_height:
                    group_extra_height[group_name] = total_height - layer_max_height

        # Build y positions accounting for group heights
        y_positions: List[int] = [0]
        for i in range(len(layer_heights) - 1):
            # Check if any group starts at this layer and needs extra space
            extra = 0
            for group_name, top_layer in group_top_layer.items():
                if top_layer == i and group_name in group_extra_height:
                    extra = max(extra, group_extra_height[group_name])

            effective_height = layer_heights[i] + extra
            next_y = y_positions[-1] + effective_height + self.vertical_spacing
            y_positions.append(next_y)

        # Calculate x positions: grouped nodes side by side, ungrouped standard
        # First, separate nodes into grouped and ungrouped per layer
        layer_ungrouped: List[List[str]] = [[] for _ in layout_result.layers]
        grouped_nodes: Set[str] = set()
        for members in group_members.values():
            grouped_nodes.update(members)

        for layer_idx, layer in enumerate(layout_result.layers):
            for node in layer:
                if node not in grouped_nodes:
                    layer_ungrouped[layer_idx].append(node)

        # Calculate width contributions per layer
        # Each layer's x content: ungrouped nodes + groups starting here
        # List of (name, width, is_group) tuples
        layer_contents: List[List[Tuple[str, int, bool]]] = []
        for layer_idx in range(len(layout_result.layers)):
            contents = []
            # Add ungrouped nodes
            for node in layer_ungrouped[layer_idx]:
                dims = box_dimensions[node]
                width = dims.width + (1 if self.shadow else 0)
                contents.append((node, width, False))
            # Add groups that start at this layer
            for group_name, top_layer in group_top_layer.items():
                if top_layer == layer_idx:
                    # Group width = sum of member widths + spacing
                    members = group_members[group_name]
                    group_width = (
                        sum(
                            box_dimensions[m].width + (1 if self.shadow else 0)
                            for m in members
                        )
                        + (len(members) - 1) * self.horizontal_spacing
                    )
                    contents.append((group_name, group_width, True))
            layer_contents.append(contents)

        # Calculate total width per layer and max width
        layer_widths = []
        for contents in layer_contents:
            if contents:
                total = sum(w for _, w, _ in contents)
                total += (len(contents) - 1) * self.horizontal_spacing
            else:
                total = 0
            layer_widths.append(total)
        max_width = max(layer_widths) if layer_widths else 0

        # Position nodes
        for layer_idx, contents in enumerate(layer_contents):
            total_width = layer_widths[layer_idx]
            start_x = left_margin + (max_width - total_width) // 2

            current_x = start_x
            for name, width, is_group in contents:
                if is_group:
                    # Position all group members horizontally
                    members = group_members[name]
                    member_x = current_x
                    for member in members:
                        dims = box_dimensions[member]
                        positions[member] = (member_x, y_positions[layer_idx])
                        member_x += dims.width + (1 if self.shadow else 0)
                        member_x += self.horizontal_spacing
                else:
                    positions[name] = (current_x, y_positions[layer_idx])
                current_x += width + self.horizontal_spacing

        return positions

    def _calculate_positions_lr_grouped(
        self,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        node_to_group: Dict[str, str],
        group_members: Dict[str, List[str]],
        node_to_layer: Dict[str, int],
        top_margin: int = 0,
    ) -> Dict[str, Tuple[int, int]]:
        """
        Calculate positions in LR mode with group-aware layout.

        All nodes in a group are stacked VERTICALLY at the same x-position
        (at the x-position of the group's leftmost layer).
        """
        positions: Dict[str, Tuple[int, int]] = {}

        # Calculate what the x-position (width) would be for each layer
        layer_widths: List[int] = []
        for layer in layout_result.layers:
            max_width = 0
            for node_name in layer:
                dims = box_dimensions[node_name]
                box_width = dims.width + (1 if self.shadow else 0)
                max_width = max(max_width, box_width)
            layer_widths.append(max_width)

        # For each group, find the leftmost layer (minimum layer index)
        group_left_layer: Dict[str, int] = {}
        for group_name, members in group_members.items():
            min_layer = min(node_to_layer[m] for m in members)
            group_left_layer[group_name] = min_layer

        # Calculate extra width needed for groups that span multiple layers
        group_extra_width: Dict[str, int] = {}
        for group_name, members in group_members.items():
            if len(members) > 1:
                # Find the widest member
                max_member_width = max(
                    box_dimensions[m].width + (1 if self.shadow else 0) for m in members
                )
                # Compare to the left layer's width
                left_layer = group_left_layer[group_name]
                if max_member_width > layer_widths[left_layer]:
                    group_extra_width[group_name] = (
                        max_member_width - layer_widths[left_layer]
                    )

        # Build x positions accounting for group widths
        x_positions: List[int] = [0]
        for i in range(len(layer_widths) - 1):
            # Check if any group starts at this layer and needs extra space
            extra = 0
            for group_name, left_layer in group_left_layer.items():
                if left_layer == i and group_name in group_extra_width:
                    extra = max(extra, group_extra_width[group_name])

            effective_width = layer_widths[i] + extra
            x_positions.append(
                x_positions[-1] + effective_width + self.horizontal_spacing
            )

        # Separate nodes into grouped and ungrouped per layer
        layer_ungrouped: List[List[str]] = [[] for _ in layout_result.layers]
        grouped_nodes: Set[str] = set()
        for members in group_members.values():
            grouped_nodes.update(members)

        for layer_idx, layer in enumerate(layout_result.layers):
            for node in layer:
                if node not in grouped_nodes:
                    layer_ungrouped[layer_idx].append(node)

        # Calculate height contributions for each layer
        # Each layer's y content: ungrouped nodes + groups starting here
        # List of (name, height, is_group) tuples
        layer_contents: List[List[Tuple[str, int, bool]]] = []
        for layer_idx in range(len(layout_result.layers)):
            contents = []
            # Add ungrouped nodes
            for node in layer_ungrouped[layer_idx]:
                dims = box_dimensions[node]
                height = dims.height + (2 if self.shadow else 0)
                contents.append((node, height, False))
            # Add groups that start at this layer
            for group_name, left_layer in group_left_layer.items():
                if left_layer == layer_idx:
                    # Group height = sum of member heights + spacing
                    members = group_members[group_name]
                    group_height = (
                        sum(
                            box_dimensions[m].height + (2 if self.shadow else 0)
                            for m in members
                        )
                        + (len(members) - 1) * self.vertical_spacing
                    )
                    contents.append((group_name, group_height, True))
            layer_contents.append(contents)

        # Calculate total height per layer and max height
        layer_heights = []
        for contents in layer_contents:
            if contents:
                total = sum(h for _, h, _ in contents)
                total += (len(contents) - 1) * self.vertical_spacing
            else:
                total = 0
            layer_heights.append(total)
        max_height = max(layer_heights) if layer_heights else 0

        # Position nodes
        for layer_idx, contents in enumerate(layer_contents):
            total_height = layer_heights[layer_idx]
            start_y = top_margin + (max_height - total_height) // 2

            current_y = start_y
            for name, height, is_group in contents:
                if is_group:
                    # Position all group members vertically (stacked)
                    members = group_members[name]
                    member_y = current_y
                    for member in members:
                        dims = box_dimensions[member]
                        positions[member] = (x_positions[layer_idx], member_y)
                        member_y += dims.height + (2 if self.shadow else 0)
                        member_y += self.vertical_spacing
                else:
                    positions[name] = (x_positions[layer_idx], current_y)
                current_y += height + self.vertical_spacing

        return positions

    def calculate_group_edge_margin(
        self,
        group_boundaries: List[GroupBoundary],
        direction: str = "TB",
    ) -> int:
        """
        Calculate extra margin needed for edges to avoid group boundaries.

        Args:
            group_boundaries: List of calculated group boundaries.
            direction: Flow direction ("TB" or "LR").

        Returns:
            Extra margin needed for edges.
        """
        if not group_boundaries:
            return 0

        margin = GROUP_EDGE_MARGIN

        if direction == "TB":
            # Find the leftmost group boundary
            min_x = min(gb.x for gb in group_boundaries)
            if min_x < margin:
                margin = margin - min_x + GROUP_EDGE_MARGIN
        else:
            # Find the topmost group boundary
            min_y = min(gb.y for gb in group_boundaries)
            if min_y < margin:
                margin = margin - min_y + GROUP_EDGE_MARGIN

        return margin
