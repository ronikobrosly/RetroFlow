"""
Main flowchart generator module.

Combines parsing, layout, and rendering to produce
beautiful ASCII flowcharts.
"""

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
)


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
        vertical_spacing: int = 6,
        shadow: bool = True,
        font: Optional[str] = None,
    ):
        """
        Initialize the flowchart generator.

        Args:
            max_text_width: Maximum width for text inside boxes before wrapping
            min_box_width: Minimum box width
            horizontal_spacing: Space between boxes horizontally
            vertical_spacing: Space between boxes vertically
            shadow: Whether to draw box shadows
            font: Font name for PNG output (e.g., "Cascadia Code", "Monaco")
        """
        self.max_text_width = max_text_width
        self.min_box_width = min_box_width
        self.horizontal_spacing = horizontal_spacing
        self.vertical_spacing = vertical_spacing
        self.shadow = shadow
        self.font = font

        self.parser = Parser()
        self.layout_engine = NetworkXLayout()
        self.box_renderer = BoxRenderer(max_text_width=max_text_width, shadow=shadow)

    def generate(self, input_text: str) -> str:
        """
        Generate an ASCII flowchart from input text.

        Args:
            input_text: Multi-line string with connections like "A -> B"

        Returns:
            ASCII art flowchart as a string
        """
        # Parse input
        connections = self.parser.parse(input_text)

        # Run layout
        layout_result = self.layout_engine.layout(connections)

        # Calculate box dimensions for each node
        box_dimensions = self._calculate_all_box_dimensions(layout_result)

        # Calculate actual pixel positions - leave margin for back edges
        back_edge_margin = 6 if layout_result.back_edges else 0
        box_positions = self._calculate_positions(
            layout_result, box_dimensions, left_margin=back_edge_margin
        )

        # Calculate canvas size
        canvas_width, canvas_height = self._calculate_canvas_size(
            box_dimensions, box_positions
        )

        # Create canvas with padding
        canvas = Canvas(canvas_width + 5, canvas_height + 5)

        # Draw boxes first
        self._draw_boxes(canvas, box_dimensions, box_positions, layout_result)

        # Draw forward edges
        self._draw_edges(canvas, layout_result, box_dimensions, box_positions)

        # Draw back edges along the left margin
        if layout_result.back_edges:
            self._draw_back_edges(canvas, layout_result, box_dimensions, box_positions)

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

        Example:
            >>> generator = FlowchartGenerator(font="Cascadia Code")
            >>> generator.save_png("A -> B -> C", "flowchart.png", font_size=24)
        """
        ascii_art = self.generate(input_text)
        lines = ascii_art.split("\n")

        # Use provided font, fall back to instance font, then system defaults
        font_name = font or self.font
        loaded_font = self._load_monospace_font(font_size, font_name)

        # Calculate character dimensions using a reference character
        bbox = loaded_font.getbbox("M")
        char_width = bbox[2] - bbox[0]
        char_height = bbox[3] - bbox[1]
        line_height = int(char_height * 1.2)  # Add some line spacing

        # Calculate image dimensions
        max_line_len = max(len(line) for line in lines) if lines else 0
        img_width = char_width * max_line_len + padding * 2
        img_height = line_height * len(lines) + padding * 2

        # Ensure minimum dimensions
        img_width = max(img_width, 100)
        img_height = max(img_height, 100)

        # Create image and draw text
        img = Image.new("RGB", (img_width, img_height), bg_color)
        draw = ImageDraw.Draw(img)

        y = padding
        for line in lines:
            draw.text((padding, y), line, font=loaded_font, fill=fg_color)
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
    ) -> None:
        """Draw a single edge from source to target."""
        src_dims = box_dimensions[source]
        tgt_dims = box_dimensions[target]
        src_x, src_y = box_positions[source]
        tgt_x, tgt_y = box_positions[target]

        # Calculate port positions (where edge exits/enters box)
        # Source: exit from bottom
        src_port_count = len(source_targets)
        src_port_idx = source_targets.index(target)
        src_port_x = self._calculate_port_x(
            src_x, src_dims.width, src_port_idx, src_port_count
        )
        src_port_y = src_y + src_dims.height - 1  # Bottom border

        # Target: enter from top
        tgt_port_count = len(target_sources)
        tgt_port_idx = target_sources.index(source)
        tgt_port_x = self._calculate_port_x(
            tgt_x, tgt_dims.width, tgt_port_idx, tgt_port_count
        )
        tgt_port_y = tgt_y  # Top border

        # Modify source bottom border to show exit point (tee down)
        canvas.set(src_port_x, src_port_y, LINE_CHARS["tee_down"])

        # Calculate path
        # Start below source (after shadow)
        start_y = src_port_y + (2 if self.shadow else 1)
        # End at target top
        end_y = tgt_port_y

        if src_port_x == tgt_port_x:
            # Direct vertical line
            self._draw_vertical_line(canvas, src_port_x, start_y, end_y - 1)
            # Draw arrow at target
            canvas.set(tgt_port_x, tgt_port_y, ARROW_CHARS["down"])
        else:
            # Need to route with horizontal segment
            mid_y = start_y + (end_y - start_y) // 2

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

            # Vertical from mid to target
            self._draw_vertical_line(canvas, tgt_port_x, mid_y + 1, end_y - 1)

            # Draw arrow at target
            canvas.set(tgt_port_x, tgt_port_y, ARROW_CHARS["down"])

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
            margin_offset += 2  # Space out multiple back edges

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

            # Draw the back edge path:
            # 1. Mark exit on source bottom-left corner area
            exit_x = src_x + 1 + (margin_offset - 2)  # Offset exit point too
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

            # 6. Vertical line up the margin
            for y in range(entry_y + 1, exit_below_y):
                current = canvas.get(route_x, y)
                if current == LINE_CHARS["horizontal"]:
                    canvas.set(route_x, y, LINE_CHARS["cross"])
                elif current == " " or current == BOX_CHARS["shadow"]:
                    canvas.set(route_x, y, LINE_CHARS["vertical"])

            # 7. Corner at target level (turning right)
            # Check if there's already something there (from another back edge)
            # Use corner_top_left (┌) for line going down to vertical below
            current = canvas.get(route_x, entry_y)
            if current == LINE_CHARS["vertical"]:
                canvas.set(route_x, entry_y, LINE_CHARS["tee_right"])
            elif current == LINE_CHARS["horizontal"]:
                canvas.set(route_x, entry_y, LINE_CHARS["tee_down"])
            elif current == " " or current == BOX_CHARS["shadow"]:
                canvas.set(route_x, entry_y, LINE_CHARS["corner_top_left"])
            # else leave existing corner/tee

            # 8. Horizontal line from margin to target
            for x in range(route_x + 1, entry_x):
                current = canvas.get(x, entry_y)
                if current == LINE_CHARS["vertical"]:
                    canvas.set(x, entry_y, LINE_CHARS["cross"])
                elif current == LINE_CHARS["corner_top_left"]:
                    canvas.set(x, entry_y, LINE_CHARS["tee_down"])
                elif current == " " or current == BOX_CHARS["shadow"]:
                    canvas.set(x, entry_y, LINE_CHARS["horizontal"])
                # else leave horizontal lines alone

            # 9. Arrow at target entry point (on left border)
            canvas.set(entry_x, entry_y, ARROW_CHARS["right"])
