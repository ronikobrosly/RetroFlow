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

from typing import Dict, List, Tuple

from .layout import LayoutResult
from .models import ColumnBoundary, LayerBoundary
from .renderer import BoxDimensions, BoxRenderer


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
