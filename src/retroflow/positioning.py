"""
Position calculation for flowchart layout.

This module handles all geometric calculations for positioning nodes on the canvas,
including:
- Box dimension calculations
- Node position calculations for both TB (top-to-bottom) and LR (left-to-right) modes
- Layer and column boundary calculations for edge routing
- Group bounding box calculations
- Port position calculations for edge connections

The PositionCalculator class centralizes these calculations and is used by the
FlowchartGenerator to determine where each element should be placed.
"""

from typing import Dict, List, Tuple

from .layout import LayoutResult
from .models import ColumnBoundary, GroupBoundingBox, LayerBoundary
from .renderer import BoxDimensions, BoxRenderer, GroupBoxRenderer


class PositionCalculator:
    """
    Calculates positions for all flowchart elements.

    This class handles the geometric layout of nodes, groups, and boundaries
    for both vertical (TB) and horizontal (LR) flow directions.

    Attributes:
        box_renderer: Renderer for calculating box dimensions.
        group_box_renderer: Renderer for group boxes.
        min_box_width: Minimum width for node boxes.
        horizontal_spacing: Space between boxes horizontally.
        vertical_spacing: Space between boxes vertically.
        shadow: Whether boxes have shadows.
        group_padding: Padding around grouped nodes inside group box.
        group_box_spacing: Minimum spacing between group boxes.
    """

    def __init__(
        self,
        box_renderer: BoxRenderer,
        group_box_renderer: GroupBoxRenderer,
        min_box_width: int = 10,
        horizontal_spacing: int = 12,
        vertical_spacing: int = 3,
        shadow: bool = True,
        group_padding: int = 2,
        group_box_spacing: int = 2,
    ):
        """
        Initialize the position calculator.

        Args:
            box_renderer: Renderer for calculating box dimensions.
            group_box_renderer: Renderer for group boxes.
            min_box_width: Minimum width for node boxes.
            horizontal_spacing: Space between boxes horizontally.
            vertical_spacing: Space between boxes vertically.
            shadow: Whether boxes have shadows.
            group_padding: Padding around grouped nodes inside group box.
            group_box_spacing: Minimum spacing between group boxes.
        """
        self.box_renderer = box_renderer
        self.group_box_renderer = group_box_renderer
        self.min_box_width = min_box_width
        self.horizontal_spacing = horizontal_spacing
        self.vertical_spacing = vertical_spacing
        self.shadow = shadow
        self.group_padding = group_padding
        self.group_box_spacing = group_box_spacing

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

    def calculate_group_bounding_boxes(
        self,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
    ) -> List[GroupBoundingBox]:
        """
        Calculate bounding boxes for all groups.

        For each group, finds the minimum bounding box that contains all
        member nodes with padding for the group border and label.

        Args:
            layout_result: The layout result containing groups.
            box_dimensions: Dictionary of box dimensions.
            box_positions: Dictionary of box positions.

        Returns:
            List of GroupBoundingBox objects.
        """
        group_boxes: List[GroupBoundingBox] = []

        for group in layout_result.groups:
            # Find bounds of all nodes in this group
            min_x = float("inf")
            min_y = float("inf")
            max_x = float("-inf")
            max_y = float("-inf")

            valid_nodes = []
            for node_name in group.nodes:
                if node_name in box_positions and node_name in box_dimensions:
                    valid_nodes.append(node_name)
                    x, y = box_positions[node_name]
                    dims = box_dimensions[node_name]

                    # Include shadow in calculations
                    node_right = x + dims.width + (1 if self.shadow else 0)
                    node_bottom = y + dims.height + (2 if self.shadow else 0)

                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, node_right)
                    max_y = max(max_y, node_bottom)

            if not valid_nodes:
                continue

            # Calculate label height (wrapped text)
            label_lines = self.group_box_renderer._wrap_label_text(group.name)
            label_height = len(label_lines) + 1  # +1 for spacing below label

            # Add padding around the group
            group_x = int(min_x) - self.group_padding
            group_y = int(min_y) - self.group_padding - label_height
            group_width = int(max_x - min_x) + 2 * self.group_padding + 1
            group_height = (
                int(max_y - min_y) + 2 * self.group_padding + label_height + 1
            )

            group_boxes.append(
                GroupBoundingBox(
                    group=group,
                    x=group_x,
                    y=group_y,
                    width=group_width,
                    height=group_height,
                    label_height=label_height,
                )
            )

        return group_boxes

    def separate_group_boxes(
        self,
        group_boxes: List[GroupBoundingBox],
    ) -> List[GroupBoundingBox]:
        """
        Adjust group boxes to ensure they don't touch or overlap.

        This method adds spacing between group boxes that would otherwise
        touch or overlap. It modifies the padding/position to ensure
        at least `group_box_spacing` characters between adjacent groups.

        Args:
            group_boxes: List of GroupBoundingBox objects.

        Returns:
            Adjusted list of GroupBoundingBox objects with proper spacing.
        """
        if len(group_boxes) <= 1:
            return group_boxes

        # Check each pair of group boxes and calculate needed adjustments
        adjusted_boxes = []

        for i, box in enumerate(group_boxes):
            # Start with the current box dimensions
            new_x = box.x
            new_y = box.y
            new_width = box.width
            new_height = box.height

            # Check against all other boxes for overlap/touching
            for j, other_box in enumerate(group_boxes):
                if i == j:
                    continue

                # Calculate the current separation (or overlap)
                # Horizontal overlap check
                box_right = new_x + new_width
                other_right = other_box.x + other_box.width

                # Vertical overlap check
                box_bottom = new_y + new_height
                other_bottom = other_box.y + other_box.height

                # Check if boxes overlap or touch horizontally AND vertically
                h_overlap = (
                    new_x < other_right + self.group_box_spacing
                    and box_right > other_box.x - self.group_box_spacing
                )
                v_overlap = (
                    new_y < other_bottom + self.group_box_spacing
                    and box_bottom > other_box.y - self.group_box_spacing
                )

                if h_overlap and v_overlap:
                    # Boxes are touching or overlapping - we need to shrink this box
                    # Determine the best way to separate them

                    # Calculate overlap amounts
                    # Positive = gap, negative = overlap
                    h_sep_left = other_box.x - box_right
                    h_sep_right = new_x - other_right
                    v_sep_top = other_box.y - box_bottom
                    v_sep_bottom = new_y - other_bottom

                    # If this box's right edge is near/past other's left edge
                    if (
                        h_sep_left < self.group_box_spacing
                        and new_x < other_box.x
                        and box_right >= other_box.x - self.group_box_spacing
                    ):
                        # Shrink width so right edge is spacing away from other's left
                        needed_shrink = box_right - (
                            other_box.x - self.group_box_spacing
                        )
                        if needed_shrink > 0:
                            new_width = max(new_width - needed_shrink, 10)

                    # If this box's bottom edge is near/past other's top edge
                    if (
                        v_sep_top < self.group_box_spacing
                        and new_y < other_box.y
                        and box_bottom >= other_box.y - self.group_box_spacing
                    ):
                        # Shrink height so bottom edge is spacing away from other's top
                        needed_shrink = box_bottom - (
                            other_box.y - self.group_box_spacing
                        )
                        if needed_shrink > 0:
                            new_height = max(new_height - needed_shrink, 5)

                    # If this box's left edge is near/past other's right edge
                    if (
                        h_sep_right < self.group_box_spacing
                        and new_x > other_box.x
                        and new_x <= other_right + self.group_box_spacing
                    ):
                        # Move left edge and shrink width
                        needed_move = (other_right + self.group_box_spacing) - new_x
                        if needed_move > 0:
                            new_x += needed_move
                            new_width = max(new_width - needed_move, 10)

                    # If this box's top edge is near/past other's bottom edge
                    if (
                        v_sep_bottom < self.group_box_spacing
                        and new_y > other_box.y
                        and new_y <= other_bottom + self.group_box_spacing
                    ):
                        # Move top edge and shrink height
                        needed_move = (other_bottom + self.group_box_spacing) - new_y
                        if needed_move > 0:
                            new_y += needed_move
                            new_height = max(new_height - needed_move, 5)

            adjusted_boxes.append(
                GroupBoundingBox(
                    group=box.group,
                    x=new_x,
                    y=new_y,
                    width=new_width,
                    height=new_height,
                    label_height=box.label_height,
                )
            )

        return adjusted_boxes

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
