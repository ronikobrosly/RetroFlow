"""
Main flowchart generator module.

Combines parsing, layout, and rendering to produce
beautiful ASCII flowcharts.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .layout import LayoutResult, NetworkXLayout
from .parser import Parser
from .renderer import (
    ARROW_CHARS,
    BOX_CHARS,
    LINE_CHARS,
    BoxDimensions,
    BoxRenderer,
    Canvas,
    TitleRenderer,
)


@dataclass
class LayerBoundary:
    """Boundary information for a layer."""

    layer_idx: int
    top_y: int  # Top of layer (where boxes start)
    bottom_y: int  # Bottom of layer (including shadow)
    gap_start_y: int  # Start of gap below this layer
    gap_end_y: int  # End of gap (start of next layer)


@dataclass
class ColumnBoundary:
    """Boundary information for a column (layer in LR mode)."""

    layer_idx: int
    left_x: int  # Left edge of column (where boxes start)
    right_x: int  # Right edge of column (including shadow)
    gap_start_x: int  # Start of gap to the right of this column
    gap_end_x: int  # End of gap (start of next column)


class FlowchartGenerator:
    """
    Generate ASCII flowcharts from simple text descriptions.

    Example:
        >>> generator = FlowchartGenerator()
        >>> flowchart = generator.generate('''
        ...     A -> B
        ...     B -> C
        ... ''')
        >>> print(flowchart)
    """

    def __init__(
        self,
        max_text_width: int = 22,
        min_box_width: int = 10,
        horizontal_spacing: int = 12,
        vertical_spacing: int = 3,
        shadow: bool = True,
        rounded: bool = False,
        compact: bool = False,
        font: Optional[str] = None,
        title: Optional[str] = None,
        direction: str = "TB",
    ):
        """
        Initialize the flowchart generator.

        Args:
            max_text_width: Maximum width for text inside boxes before wrapping
            min_box_width: Minimum box width
            horizontal_spacing: Space between boxes horizontally
            vertical_spacing: Space between boxes vertically
            shadow: Whether to draw box shadows
            rounded: Whether to use rounded corners (╭╮╯╰) instead of square
            compact: Whether to use compact boxes (no vertical padding)
            font: Font name for PNG output (e.g., "Cascadia Code", "Monaco")
            title: Optional title to display above the flowchart
            direction: Flow direction - "TB" (top-to-bottom) or "LR" (left-to-right)
        """
        self.max_text_width = max_text_width
        self.min_box_width = min_box_width
        self.horizontal_spacing = horizontal_spacing
        self.vertical_spacing = vertical_spacing
        self.shadow = shadow
        self.rounded = rounded
        self.compact = compact
        self.font = font
        self.title = title
        self.direction = direction.upper()

        if self.direction not in ("TB", "LR"):
            raise ValueError(
                "direction must be 'TB' (top-to-bottom) or 'LR' (left-to-right)"
            )

        self.parser = Parser()
        self.layout_engine = NetworkXLayout()
        self.box_renderer = BoxRenderer(
            max_text_width=max_text_width,
            shadow=shadow,
            rounded=rounded,
            compact=compact,
        )
        self.title_renderer = TitleRenderer()

    def generate(self, input_text: str, title: Optional[str] = None) -> str:
        """
        Generate an ASCII flowchart from input text.

        Args:
            input_text: Multi-line string with connections like "A -> B"
            title: Optional title to display (overrides instance title)

        Returns:
            ASCII art flowchart as a string
        """
        # Use provided title or fall back to instance title
        effective_title = title if title is not None else self.title

        # Parse input
        connections = self.parser.parse(input_text)

        # Run layout
        layout_result = self.layout_engine.layout(connections)

        # Calculate box dimensions for each node
        box_dimensions = self._calculate_all_box_dimensions(layout_result)

        # Calculate actual pixel positions - leave margin for back edges
        # Each back edge needs 3 chars of space, plus 4 for min line before arrow
        num_back_edges = len(layout_result.back_edges)
        back_edge_margin = (4 + num_back_edges * 3) if num_back_edges > 0 else 0

        if self.direction == "LR":
            box_positions = self._calculate_positions_horizontal(
                layout_result, box_dimensions, top_margin=back_edge_margin
            )
        else:
            box_positions = self._calculate_positions(
                layout_result, box_dimensions, left_margin=back_edge_margin
            )

        # Calculate layer boundaries for safe edge routing
        layer_boundaries = self._calculate_layer_boundaries(
            layout_result, box_dimensions
        )

        # Calculate column boundaries for LR mode
        column_boundaries: List[ColumnBoundary] = []
        if self.direction == "LR":
            column_boundaries = self._calculate_column_boundaries(
                layout_result, box_dimensions
            )

        # Calculate canvas size
        canvas_width, canvas_height = self._calculate_canvas_size(
            box_dimensions, box_positions
        )

        # Calculate title dimensions and offset
        title_height = 0
        title_width = 0
        diagram_x_offset = 0
        title_x_offset = 0

        if effective_title:
            title_width, title_height = self.title_renderer.calculate_title_dimensions(
                effective_title
            )
            title_height += 2  # Add spacing below title

            # Determine centering: center title above diagram or diagram under title
            if title_width > canvas_width:
                # Title is wider - center diagram under title
                diagram_x_offset = (title_width - canvas_width) // 2
                canvas_width = title_width
            else:
                # Diagram is wider - center title above diagram
                title_x_offset = (canvas_width - title_width) // 2

        # Create canvas with padding and title space
        canvas = Canvas(canvas_width + 5, canvas_height + title_height + 5)

        # Draw title if present, centered above the diagram
        if effective_title:
            self.title_renderer.draw_title(
                canvas, title_x_offset, 0, effective_title, title_width
            )

        # Offset box positions for title and centering
        if title_height > 0 or diagram_x_offset > 0:
            box_positions = {
                name: (x + diagram_x_offset, y + title_height)
                for name, (x, y) in box_positions.items()
            }
            # Also offset layer boundaries by title height
            if title_height > 0:
                layer_boundaries = [
                    LayerBoundary(
                        layer_idx=lb.layer_idx,
                        top_y=lb.top_y + title_height,
                        bottom_y=lb.bottom_y + title_height,
                        gap_start_y=lb.gap_start_y + title_height,
                        gap_end_y=lb.gap_end_y + title_height,
                    )
                    for lb in layer_boundaries
                ]
                # And column boundaries for LR mode
                if self.direction == "LR" and diagram_x_offset > 0:
                    column_boundaries = [
                        ColumnBoundary(
                            layer_idx=cb.layer_idx,
                            left_x=cb.left_x + diagram_x_offset,
                            right_x=cb.right_x + diagram_x_offset,
                            gap_start_x=cb.gap_start_x + diagram_x_offset,
                            gap_end_x=cb.gap_end_x + diagram_x_offset,
                        )
                        for cb in column_boundaries
                    ]

        # Draw boxes first
        self._draw_boxes(canvas, box_dimensions, box_positions, layout_result)

        # Draw forward edges with layer-aware routing
        if self.direction == "LR":
            self._draw_edges_horizontal(
                canvas,
                layout_result,
                box_dimensions,
                box_positions,
                column_boundaries,
                title_height,
            )
        else:
            self._draw_edges(
                canvas, layout_result, box_dimensions, box_positions, layer_boundaries
            )

        # Draw back edges along the margin
        if layout_result.back_edges:
            if self.direction == "LR":
                self._draw_back_edges_horizontal(
                    canvas, layout_result, box_dimensions, box_positions, title_height
                )
            else:
                self._draw_back_edges(
                    canvas, layout_result, box_dimensions, box_positions
                )

        return canvas.render()

    def save_txt(
        self, input_text: str, filename: str, boxes_only: bool = False
    ) -> None:
        """
        Generate flowchart and save to a text file.

        Args:
            input_text: Multi-line string with connections
            filename: Output filename (should end in .txt)
            boxes_only: If True, only draw boxes without edges (ignored)
        """
        flowchart = self.generate(input_text)
        output_path = Path(filename)
        output_path.write_text(flowchart, encoding="utf-8")

    def save_png(
        self,
        input_text: str,
        filename: str,
        font_size: int = 16,
        bg_color: str = "#FFFFFF",
        fg_color: str = "#000000",
        padding: int = 20,
        font: Optional[str] = None,
        scale: int = 2,
    ) -> None:
        """
        Generate flowchart and save as a high-resolution PNG image.

        The PNG rendering is faithful to the ASCII version, using a monospace
        font to preserve the exact character layout and box-drawing characters.

        Args:
            input_text: Multi-line string with connections like "A -> B"
            filename: Output filename (should end in .png)
            font_size: Font size in points (higher = higher resolution)
            bg_color: Background color as hex string (e.g., "#FFFFFF")
            fg_color: Foreground/text color as hex string (e.g., "#000000")
            padding: Padding around the diagram in pixels
            font: Font name to use (overrides instance font if provided)
            scale: Resolution multiplier for crisp output (default 2 for retina)

        Example:
            >>> generator = FlowchartGenerator(font="Cascadia Code")
            >>> generator.save_png("A -> B -> C", "flowchart.png", font_size=24)
        """
        ascii_art = self.generate(input_text)
        lines = ascii_art.split("\n")

        # Use provided font, fall back to instance font, then system defaults
        font_name = font or self.font
        # Apply scale multiplier to font size for higher resolution output
        scaled_font_size = font_size * scale
        loaded_font = self._load_monospace_font(scaled_font_size, font_name)

        # Calculate character dimensions using a reference character
        bbox = loaded_font.getbbox("M")
        char_width = bbox[2] - bbox[0]
        char_height = bbox[3] - bbox[1]
        line_height = int(char_height * 1.2)  # Add some line spacing

        # Scale padding to match resolution
        scaled_padding = padding * scale

        # Calculate image dimensions
        max_line_len = max(len(line) for line in lines) if lines else 0
        img_width = char_width * max_line_len + scaled_padding * 2
        img_height = line_height * len(lines) + scaled_padding * 2

        # Ensure minimum dimensions (scaled)
        img_width = max(img_width, 100 * scale)
        img_height = max(img_height, 100 * scale)

        # Create image and draw text
        img = Image.new("RGB", (img_width, img_height), bg_color)
        draw = ImageDraw.Draw(img)

        y = scaled_padding
        for line in lines:
            draw.text((scaled_padding, y), line, font=loaded_font, fill=fg_color)
            y += line_height

        # Save the image
        output_path = Path(filename)
        img.save(output_path, "PNG")

    def _load_monospace_font(
        self, font_size: int, font_name: Optional[str] = None
    ) -> ImageFont.FreeTypeFont:
        """
        Load a monospace font for PNG rendering.

        Tries the following in order:
        1. User-specified font name if provided
        2. Common system monospace fonts
        3. Pillow's default font

        Args:
            font_size: Font size in points
            font_name: Optional font name (e.g., "Cascadia Code", "Monaco")

        Returns:
            A PIL ImageFont object
        """
        # Build list of fonts to try
        fonts_to_try = []

        # Add user-specified font first
        if font_name:
            fonts_to_try.append(font_name)

        # Common monospace fonts across different systems
        fonts_to_try.extend(
            [
                # Linux
                "DejaVuSansMono",
                "DejaVu Sans Mono",
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                # macOS
                "Monaco",
                "Menlo",
                "/System/Library/Fonts/Monaco.ttf",
                "/System/Library/Fonts/Menlo.ttc",
                # Windows
                "Consolas",
                "Cascadia Code",
                "Courier New",
                "C:/Windows/Fonts/consola.ttf",
            ]
        )

        for font in fonts_to_try:
            try:
                return ImageFont.truetype(font, font_size)
            except OSError:
                continue

        # Fall back to Pillow's default font
        try:
            return ImageFont.load_default(size=font_size)
        except TypeError:
            # Older Pillow versions don't support size parameter
            return ImageFont.load_default()

    def _calculate_all_box_dimensions(
        self, layout_result: LayoutResult
    ) -> Dict[str, BoxDimensions]:
        """Calculate dimensions for all boxes, ensuring minimum size."""
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

    def _calculate_positions(
        self,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        left_margin: int = 0,
    ) -> Dict[str, Tuple[int, int]]:
        """
        Calculate actual x,y positions for each box.
        Centers nodes within each layer.

        Args:
            layout_result: The layout result from the layout engine
            box_dimensions: Dictionary of box dimensions
            left_margin: Extra space on left for back edge routing
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

    def _calculate_positions_horizontal(
        self,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        top_margin: int = 0,
    ) -> Dict[str, Tuple[int, int]]:
        """
        Calculate actual x,y positions for each box in horizontal (LR) mode.
        Layers become columns, nodes within a layer stack vertically.

        Args:
            layout_result: The layout result from the layout engine
            box_dimensions: Dictionary of box dimensions
            top_margin: Extra space on top for back edge routing
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

    def _calculate_layer_boundaries(
        self,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
    ) -> List[LayerBoundary]:
        """
        Calculate the y-boundaries for each layer.

        This information is used for safe edge routing - horizontal segments
        should be placed in the gaps between layers where no boxes exist.

        Returns:
            List of LayerBoundary objects, one per layer
        """
        boundaries: List[LayerBoundary] = []

        # Calculate layer heights (same logic as _calculate_positions)
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

    def _calculate_column_boundaries(
        self,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
    ) -> List[ColumnBoundary]:
        """
        Calculate the x-boundaries for each column (layer in LR mode).

        This information is used for safe edge routing - vertical segments
        should be placed in the gaps between columns where no boxes exist.

        Returns:
            List of ColumnBoundary objects, one per layer/column
        """
        boundaries: List[ColumnBoundary] = []

        # Calculate layer widths (same logic as _calculate_positions_horizontal)
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

    def _calculate_canvas_size(
        self,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
    ) -> Tuple[int, int]:
        """Calculate required canvas dimensions."""
        max_x = 0
        max_y = 0

        for node_name, (x, y) in box_positions.items():
            dims = box_dimensions[node_name]
            right = x + dims.width + (2 if self.shadow else 0)
            bottom = y + dims.height + (2 if self.shadow else 0)
            max_x = max(max_x, right)
            max_y = max(max_y, bottom)

        return max_x, max_y

    def _draw_boxes(
        self,
        canvas: Canvas,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
        layout_result: LayoutResult,
    ) -> None:
        """Draw all boxes on the canvas."""
        for node_name in layout_result.nodes:
            dims = box_dimensions[node_name]
            x, y = box_positions[node_name]
            self.box_renderer.draw_box(canvas, x, y, dims)

    def _draw_edges(
        self,
        canvas: Canvas,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
        layer_boundaries: List[LayerBoundary],
    ) -> None:
        """Draw all forward edges on the canvas (skip back edges)."""

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

        # Check if boxes overlap horizontally (inside borders)
        src_left = src_x + 1
        src_right = src_x + src_dims.width - 2
        tgt_left = tgt_x + 1
        tgt_right = tgt_x + tgt_dims.width - 2

        overlap_left = max(src_left, tgt_left)
        overlap_right = min(src_right, tgt_right)
        has_overlap = overlap_left < overlap_right

        # Check if there are boxes in intermediate layers that would block a direct path
        boxes_in_path = False
        if has_overlap and tgt_layer - src_layer > 1:
            # Check intermediate layers for boxes that would be crossed
            for layer_idx in range(src_layer + 1, tgt_layer):
                for node_name in layout_result.layers[layer_idx]:
                    node_dims = box_dimensions[node_name]
                    node_x, node_y = box_positions[node_name]
                    node_left = node_x
                    node_right = node_x + node_dims.width

                    # Check if this box's x range overlaps with the edge's x range
                    if node_left < overlap_right and node_right > overlap_left:
                        boxes_in_path = True
                        break
                if boxes_in_path:
                    break

        if has_overlap and not boxes_in_path:
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
            src_port_x = self._calculate_port_x(
                src_x, src_dims.width, src_port_idx, src_port_count
            )

            # Target: enter from top
            tgt_port_count = len(target_sources)
            tgt_port_idx = target_sources.index(source)
            tgt_port_x = self._calculate_port_x(
                tgt_x, tgt_dims.width, tgt_port_idx, tgt_port_count
            )

        src_port_y = src_y + src_dims.height - 1  # Bottom border
        tgt_port_y = tgt_y  # Top border

        # Modify source bottom border to show exit point (tee down)
        canvas.set(src_port_x, src_port_y, LINE_CHARS["tee_down"])

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
            canvas.set(src_port_x, mid_y, LINE_CHARS["corner_bottom_left"])

            # Horizontal segment to the route column
            self._draw_horizontal_line(canvas, src_port_x, route_x, mid_y)

            # Corner turning down
            canvas.set(route_x, mid_y, LINE_CHARS["corner_top_right"])

            # Find the y position for the horizontal segment above the target
            tgt_mid_y = self._get_safe_horizontal_y(
                layer_boundaries, tgt_layer - 1, start_y
            )

            # Vertical segment down the right side
            self._draw_vertical_line(canvas, route_x, mid_y + 1, tgt_mid_y - 1)

            # Corner turning left (line comes from above, exits left)
            canvas.set(route_x, tgt_mid_y, LINE_CHARS["corner_bottom_right"])

            # Horizontal segment back toward target
            self._draw_horizontal_line(canvas, tgt_port_x, route_x, tgt_mid_y)

            # Corner turning down to target (line comes from right, exits down)
            canvas.set(tgt_port_x, tgt_mid_y, LINE_CHARS["corner_top_left"])

            # Vertical to target
            self._draw_vertical_line(canvas, tgt_port_x, tgt_mid_y + 1, end_y - 2)

            # Arrow
            canvas.set(tgt_port_x, tgt_port_y - 1, ARROW_CHARS["down"])

        elif src_port_x == tgt_port_x:
            # Direct vertical line (stop before arrow position)
            self._draw_vertical_line(canvas, src_port_x, start_y, end_y - 2)
            # Draw arrow one row above target box (doesn't overwrite border)
            canvas.set(tgt_port_x, tgt_port_y - 1, ARROW_CHARS["down"])
        else:
            # Need to route with horizontal segment
            # Use layer-aware routing: place horizontal segment in the gap zone
            # below the source layer where no boxes can exist
            mid_y = self._get_safe_horizontal_y(layer_boundaries, src_layer, start_y)

            # Vertical from source to mid
            self._draw_vertical_line(canvas, src_port_x, start_y, mid_y - 1)

            # Corner at source column
            if tgt_port_x > src_port_x:
                canvas.set(src_port_x, mid_y, LINE_CHARS["corner_bottom_left"])
            else:
                canvas.set(src_port_x, mid_y, LINE_CHARS["corner_bottom_right"])

            # Horizontal segment
            self._draw_horizontal_line(canvas, src_port_x, tgt_port_x, mid_y)

            # Corner at target column
            if tgt_port_x > src_port_x:
                canvas.set(tgt_port_x, mid_y, LINE_CHARS["corner_top_right"])
            else:
                canvas.set(tgt_port_x, mid_y, LINE_CHARS["corner_top_left"])

            # Vertical from mid to target (stop before arrow position)
            self._draw_vertical_line(canvas, tgt_port_x, mid_y + 1, end_y - 2)

            # Draw arrow one row above target box (doesn't overwrite border)
            canvas.set(tgt_port_x, tgt_port_y - 1, ARROW_CHARS["down"])

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
            layer_boundaries: List of layer boundary information
            src_layer: The layer index of the source node
            start_y: The y-coordinate where the edge starts (below source box)

        Returns:
            A y-coordinate in the gap zone that's safe for horizontal routing
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
            column_boundaries: List of column boundary information
            src_layer: The layer index of the source node
            start_x: The x-coordinate where the edge starts (after source box)

        Returns:
            An x-coordinate in the gap zone that's safe for vertical routing
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

    def _calculate_port_x(
        self, box_x: int, box_width: int, port_idx: int, port_count: int
    ) -> int:
        """Calculate x position for a port on a box."""
        if port_count == 1:
            # Single port: center of box
            return box_x + box_width // 2
        else:
            # Multiple ports: distribute evenly
            usable_width = box_width - 4  # Leave margins
            spacing = usable_width // (port_count + 1)
            return box_x + 2 + spacing * (port_idx + 1)

    def _draw_vertical_line(
        self, canvas: Canvas, x: int, y_start: int, y_end: int
    ) -> None:
        """Draw a vertical line from y_start to y_end."""
        if y_start > y_end:
            y_start, y_end = y_end, y_start

        for y in range(y_start, y_end + 1):
            current = canvas.get(x, y)
            if current == LINE_CHARS["horizontal"]:
                canvas.set(x, y, LINE_CHARS["cross"])
            elif current == " " or current == BOX_CHARS["shadow"]:
                canvas.set(x, y, LINE_CHARS["vertical"])

    def _draw_horizontal_line(
        self, canvas: Canvas, x_start: int, x_end: int, y: int
    ) -> None:
        """Draw a horizontal line from x_start to x_end (exclusive of endpoints)."""
        if x_start > x_end:
            x_start, x_end = x_end, x_start

        for x in range(x_start + 1, x_end):
            current = canvas.get(x, y)
            if current == LINE_CHARS["vertical"]:
                canvas.set(x, y, LINE_CHARS["cross"])
            elif current == " " or current == BOX_CHARS["shadow"]:
                canvas.set(x, y, LINE_CHARS["horizontal"])

    def _draw_back_edges(
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

    def _draw_edges_horizontal(
        self,
        canvas: Canvas,
        layout_result: LayoutResult,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
        column_boundaries: List[ColumnBoundary],
        title_height: int = 0,
    ) -> None:
        """Draw all forward edges in horizontal (LR) mode."""

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

        # Check if boxes overlap vertically (inside borders)
        src_top = src_y + 1
        src_bottom = src_y + src_dims.height - 2
        tgt_top = tgt_y + 1
        tgt_bottom = tgt_y + tgt_dims.height - 2

        overlap_top = max(src_top, tgt_top)
        overlap_bottom = min(src_bottom, tgt_bottom)
        has_overlap = overlap_top < overlap_bottom

        # Check if there are boxes in intermediate columns that would block the path
        boxes_in_path = False
        if has_overlap and tgt_layer - src_layer > 1:
            for layer_idx in range(src_layer + 1, tgt_layer):
                for node_name in layout_result.layers[layer_idx]:
                    node_dims = box_dimensions[node_name]
                    node_x, node_y = box_positions[node_name]
                    node_top = node_y
                    node_bottom = node_y + node_dims.height

                    # Check if this box's y range overlaps with the edge's y range
                    if node_top < overlap_bottom and node_bottom > overlap_top:
                        boxes_in_path = True
                        break
                if boxes_in_path:
                    break

        if has_overlap and not boxes_in_path:
            # Boxes overlap vertically and no obstructions
            overlapping_targets = []
            for t in source_targets:
                t_dims = box_dimensions[t]
                t_x, t_y = box_positions[t]
                t_top = t_y + 1
                t_bottom = t_y + t_dims.height - 2
                t_overlap_top = max(src_top, t_top)
                t_overlap_bottom = min(src_bottom, t_bottom)
                if t_overlap_top < t_overlap_bottom:
                    overlapping_targets.append(t)

            # Distribute ports within the overlap region
            overlap_height = overlap_bottom - overlap_top
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
            src_port_y = self._calculate_port_y(
                src_y, src_dims.height, src_port_idx, src_port_count
            )

            tgt_port_count = len(target_sources)
            tgt_port_idx = target_sources.index(source)
            tgt_port_y = self._calculate_port_y(
                tgt_y, tgt_dims.height, tgt_port_idx, tgt_port_count
            )

        # Exit from right side of source box
        src_port_x = src_x + src_dims.width - 1
        # Enter left side of target box
        tgt_port_x = tgt_x

        # Modify source right border to show exit point (tee right)
        canvas.set(src_port_x, src_port_y, LINE_CHARS["tee_left"])

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

            # Corner turning down
            canvas.set(mid_x, src_port_y, LINE_CHARS["corner_top_right"])

            # Vertical segment down to route_y
            self._draw_vertical_line(canvas, mid_x, src_port_y + 1, route_y - 1)

            # Corner turning right
            canvas.set(mid_x, route_y, LINE_CHARS["corner_bottom_left"])

            # Find the x position for the vertical segment before the target
            tgt_mid_x = self._get_safe_vertical_x(
                column_boundaries, tgt_layer - 1, start_x
            )

            # Horizontal segment below boxes
            self._draw_horizontal_line(canvas, mid_x, tgt_mid_x, route_y)

            # Corner turning up
            canvas.set(tgt_mid_x, route_y, LINE_CHARS["corner_bottom_right"])

            # Vertical segment up toward target
            self._draw_vertical_line(canvas, tgt_mid_x, tgt_port_y + 1, route_y - 1)

            # Corner turning right to target
            canvas.set(tgt_mid_x, tgt_port_y, LINE_CHARS["corner_top_left"])

            # Horizontal to target
            self._draw_horizontal_line(canvas, tgt_mid_x, end_x - 1, tgt_port_y)

            # Arrow
            canvas.set(tgt_port_x - 1, tgt_port_y, ARROW_CHARS["right"])

        elif src_port_y == tgt_port_y:
            # Direct horizontal line
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

            # Corner at source row
            if tgt_port_y > src_port_y:
                canvas.set(mid_x, src_port_y, LINE_CHARS["corner_top_right"])
            else:
                canvas.set(mid_x, src_port_y, LINE_CHARS["corner_bottom_right"])

            # Vertical segment
            self._draw_vertical_line(canvas, mid_x, src_port_y, tgt_port_y)

            # Corner at target row
            if tgt_port_y > src_port_y:
                canvas.set(mid_x, tgt_port_y, LINE_CHARS["corner_bottom_left"])
            else:
                canvas.set(mid_x, tgt_port_y, LINE_CHARS["corner_top_left"])

            # Horizontal from mid to target
            # Adjust for exclusive endpoints: mid_x so line begins at mid_x + 1,
            # end_x - 1 so line ends at end_x - 2 (just before the arrow at end_x - 1)
            self._draw_horizontal_line(canvas, mid_x, end_x - 1, tgt_port_y)

            # Arrow
            canvas.set(tgt_port_x - 1, tgt_port_y, ARROW_CHARS["right"])

    def _calculate_port_y(
        self, box_y: int, box_height: int, port_idx: int, port_count: int
    ) -> int:
        """Calculate y position for a port on a box (horizontal mode)."""
        if port_count == 1:
            return box_y + box_height // 2
        else:
            usable_height = box_height - 4
            spacing = usable_height // (port_count + 1)
            return box_y + 2 + spacing * (port_idx + 1)

    def _draw_back_edges_horizontal(
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

            canvas.set(exit_border_x, exit_y, LINE_CHARS["tee_left"])

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
