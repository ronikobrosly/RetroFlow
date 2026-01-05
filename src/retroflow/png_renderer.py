"""
PNG Renderer module for flowchart generator.

Renders flowcharts as high-resolution PNG images with professional styling.
"""

import math
import os
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

from .edge_routing import create_router, EdgeRoute


class PNGRenderer:
    """Renders flowcharts as PNG images with professional styling."""

    def __init__(
        self,
        box_padding: int = 15,
        box_min_width: int = 100,
        box_height: int = 36,
        horizontal_spacing: int = 80,
        vertical_spacing: int = 40,
        shadow_offset: int = 5,
        font_size: int = 11,
        font_path: str | None = None,  # Custom font path
        scale: int = 2,  # For high-resolution output
        margin: int = 50,
        horizontal_flow: bool = True,  # Flow left-to-right instead of top-to-bottom
    ):
        self.box_padding = box_padding
        self.box_min_width = box_min_width
        self.box_height = box_height
        self.horizontal_spacing = horizontal_spacing
        self.vertical_spacing = vertical_spacing
        self.shadow_offset = shadow_offset
        self.font_size = font_size
        self.font_path = font_path
        self.scale = scale
        self.margin = margin
        self.horizontal_flow = horizontal_flow

        # Colors
        self.bg_color = (255, 255, 255)
        self.box_fill = (255, 255, 255)
        self.box_outline = (0, 0, 0)
        self.shadow_color = (160, 160, 160)
        self.text_color = (0, 0, 0)
        self.line_color = (0, 0, 0)

        self.node_positions = {}  # node -> (x, y, width, height)
        self.font = None

    def _get_font(self) -> ImageFont.FreeTypeFont:
        """Get a font for rendering text."""
        if self.font is not None:
            return self.font

        font_size = self.font_size * self.scale

        # Use custom font if provided
        if self.font_path:
            if os.path.exists(self.font_path):
                try:
                    self.font = ImageFont.truetype(self.font_path, font_size)
                    return self.font
                except Exception:
                    pass  # Fall through to default fonts

        # Try to load a monospace font from system
        font_options = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
            "/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf",
        ]

        for path in font_options:
            if os.path.exists(path):
                try:
                    self.font = ImageFont.truetype(path, font_size)
                    return self.font
                except Exception:
                    continue

        # Fallback to default font
        self.font = ImageFont.load_default()
        return self.font

    def _calculate_text_size(self, text: str, draw: ImageDraw.Draw) -> Tuple[int, int]:
        """Calculate the size of text."""
        font = self._get_font()
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def _calculate_box_dimensions(
        self, node: str, draw: ImageDraw.Draw
    ) -> Tuple[int, int]:
        """Calculate box dimensions based on text content."""
        # Handle multi-line labels
        lines = node.upper().split("\n")
        max_width = 0
        total_height = 0
        line_spacing = 4 * self.scale

        font = self._get_font()
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            max_width = max(max_width, line_width)
            total_height += line_height
            if i > 0:
                total_height += line_spacing

        # Add padding
        padding = self.box_padding * 2 * self.scale
        width = max(self.box_min_width * self.scale, max_width + padding)
        height = max(self.box_height * self.scale, total_height + padding)

        return width, height

    def _draw_hatched_shadow(
        self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int
    ):
        """Draw a shadow effect using a checkerboard pattern (like ▒ character)."""
        s = self.shadow_offset * self.scale

        # Size of each "pixel" in the checkerboard pattern
        pixel_size = max(2, self.scale)

        def draw_checkerboard(region_x, region_y, region_w, region_h):
            """Draw checkerboard pattern in a region."""
            row = 0
            for py in range(region_y, region_y + region_h, pixel_size):
                col = 0
                for px in range(region_x, region_x + region_w, pixel_size):
                    # Checkerboard: draw pixel if (row + col) is even
                    if (row + col) % 2 == 0:
                        draw.rectangle(
                            [px, py, px + pixel_size - 1, py + pixel_size - 1],
                            fill=self.shadow_color,
                        )
                    col += 1
                row += 1

        # Right shadow strip (includes corner at bottom)
        draw_checkerboard(x + w, y + s, s, h)

        # Bottom shadow strip (stops before corner to avoid overlap)
        draw_checkerboard(x + s, y + h, w - s, s)

    def render(self, graph, layout, output_path: str = "diagram.png") -> str:
        """
        Render the flowchart as a PNG image.

        Args:
            graph: Graph object
            layout: Layout object with node positions
            output_path: Path to save the PNG file

        Returns:
            Path to the saved PNG file
        """
        # Create a temporary image to measure text
        temp_img = Image.new("RGB", (100, 100), self.bg_color)
        temp_draw = ImageDraw.Draw(temp_img)

        # Calculate box dimensions for each node
        box_dimensions = {}
        for node in graph.nodes:
            box_dimensions[node] = self._calculate_box_dimensions(node, temp_draw)

        # Get layout dimensions
        layout_width, layout_height = layout.get_layout_dimensions()

        if layout_width == 0 or layout_height == 0:
            # Create a small placeholder image
            img = Image.new("RGB", (200, 100), self.bg_color)
            img.save(output_path)
            return output_path

        # For horizontal flow, swap layer coordinates
        # layer_x becomes row (vertical position)
        # layer_y becomes column (horizontal position)

        if self.horizontal_flow:
            # Organize nodes by columns (original layer_y = horizontal position)
            columns = {}  # layer_y -> list of nodes
            for node, (layer_x, layer_y) in layout.positions.items():
                if layer_y not in columns:
                    columns[layer_y] = []
                columns[layer_y].append((node, layer_x))

            # Calculate max width per column
            col_widths = {}
            for col_idx, nodes in columns.items():
                max_w = 0
                for node, _ in nodes:
                    w, h = box_dimensions[node]
                    max_w = max(max_w, w)
                col_widths[col_idx] = max_w

            # Calculate max height per row
            rows = {}  # layer_x -> list of nodes
            for node, (layer_x, layer_y) in layout.positions.items():
                if layer_x not in rows:
                    rows[layer_x] = []
                rows[layer_x].append((node, layer_y))

            row_heights = {}
            for row_idx, nodes in rows.items():
                max_h = 0
                for node, _ in nodes:
                    w, h = box_dimensions[node]
                    max_h = max(max_h, h)
                row_heights[row_idx] = max_h

            # Calculate pixel positions
            x_offset = self.margin * self.scale
            col_x_positions = {}
            for col_idx in sorted(col_widths.keys()):
                col_x_positions[col_idx] = x_offset
                x_offset += col_widths[col_idx] + self.horizontal_spacing * self.scale

            y_offset = self.margin * self.scale
            row_y_positions = {}
            for row_idx in sorted(row_heights.keys()):
                row_y_positions[row_idx] = y_offset
                y_offset += row_heights[row_idx] + self.vertical_spacing * self.scale

            # Store node positions
            for node, (layer_x, layer_y) in layout.positions.items():
                w, h = box_dimensions[node]
                col_w = col_widths[layer_y]
                row_h = row_heights[layer_x]

                # Center box within its cell
                x = col_x_positions[layer_y] + (col_w - w) // 2
                y = row_y_positions[layer_x] + (row_h - h) // 2

                self.node_positions[node] = (x, y, w, h)

            canvas_width = x_offset + self.margin * self.scale
            canvas_height = y_offset + self.margin * self.scale
        else:
            # Original vertical flow
            col_widths = {}
            for node, (layer_x, layer_y) in layout.positions.items():
                w, h = box_dimensions[node]
                col_widths[layer_x] = max(col_widths.get(layer_x, 0), w)

            row_heights = {}
            for node, (layer_x, layer_y) in layout.positions.items():
                w, h = box_dimensions[node]
                row_heights[layer_y] = max(row_heights.get(layer_y, 0), h)

            x_offset = self.margin * self.scale
            col_x_positions = {}
            for col_idx in sorted(col_widths.keys()):
                col_x_positions[col_idx] = x_offset
                x_offset += col_widths[col_idx] + self.horizontal_spacing * self.scale

            y_offset = self.margin * self.scale
            row_y_positions = {}
            for row_idx in sorted(row_heights.keys()):
                row_y_positions[row_idx] = y_offset
                y_offset += row_heights[row_idx] + self.vertical_spacing * self.scale

            for node, (layer_x, layer_y) in layout.positions.items():
                w, h = box_dimensions[node]
                col_w = col_widths[layer_x]
                row_h = row_heights[layer_y]

                x = col_x_positions[layer_x] + (col_w - w) // 2
                y = row_y_positions[layer_y] + (row_h - h) // 2

                self.node_positions[node] = (x, y, w, h)

            canvas_width = x_offset + self.margin * self.scale
            canvas_height = y_offset + self.margin * self.scale

        # Create the image
        img = Image.new("RGB", (canvas_width, canvas_height), self.bg_color)
        draw = ImageDraw.Draw(img)

        # Draw shadows first
        for node, (x, y, w, h) in self.node_positions.items():
            self._draw_hatched_shadow(draw, x, y, w, h)

        # Draw connections
        self._draw_connections(draw, graph, layout)

        # Draw boxes
        for node, (x, y, w, h) in self.node_positions.items():
            self._draw_box(draw, x, y, w, h, node)

        # Save the image
        img.save(output_path, "PNG", dpi=(300, 300))

        return output_path

    def _draw_box(
        self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, label: str
    ):
        """Draw a box with border."""
        line_width = max(1, self.scale)

        # Draw main box
        draw.rectangle(
            [x, y, x + w, y + h],
            fill=self.box_fill,
            outline=self.box_outline,
            width=line_width,
        )

        # Draw text (centered, uppercase)
        font = self._get_font()
        text = label.upper()
        lines = text.split("\n")
        line_spacing = 4 * self.scale

        # Calculate total text height
        total_height = 0
        line_dims = []
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]
            line_h = bbox[3] - bbox[1]
            line_dims.append((line_w, line_h))
            total_height += line_h
            if i > 0:
                total_height += line_spacing

        # Draw each line centered
        current_y = y + (h - total_height) // 2
        for i, line in enumerate(lines):
            line_w, line_h = line_dims[i]
            text_x = x + (w - line_w) // 2
            draw.text((text_x, current_y), line, fill=self.text_color, font=font)
            current_y += line_h + line_spacing

    def _draw_connections(self, draw: ImageDraw.Draw, graph, layout):
        """Draw arrows between connected nodes using orthogonal edge routing."""
        edges = layout.get_edges_for_rendering()
        line_width = max(1, self.scale)

        # Create the routing system
        grid, port_manager, router = create_router(self.node_positions)

        # Detect bidirectional edges
        edge_set = {(s, t) for s, t, _ in edges}
        bidirectional = set()
        for source, target, _ in edges:
            if (target, source) in edge_set:
                bidirectional.add((min(source, target), max(source, target)))

        # Route all edges
        processed = set()
        for source, target, is_feedback in edges:
            # Check if this is a bidirectional edge
            bidir_key = (min(source, target), max(source, target))
            is_bidir = bidir_key in bidirectional

            # Skip reverse direction of bidirectional edges
            if is_bidir and bidir_key in processed:
                continue
            if is_bidir:
                processed.add(bidir_key)

            # Route the edge
            route = router.route_edge(source, target, is_bidir)
            if route:
                self._draw_routed_edge(draw, route, line_width)

    def _draw_routed_edge(
        self, draw: ImageDraw.Draw, route: EdgeRoute, line_width: int
    ):
        """Draw a routed edge with waypoints."""
        waypoints = route.waypoints
        if len(waypoints) < 2:
            return

        # Draw the path segments
        for i in range(len(waypoints) - 1):
            p1 = waypoints[i]
            p2 = waypoints[i + 1]
            draw.line([p1, p2], fill=self.line_color, width=line_width)

        # Draw arrowhead at end (always)
        if len(waypoints) >= 2:
            from_pt = waypoints[-2]
            to_pt = waypoints[-1]
            self._draw_arrowhead(draw, from_pt, to_pt)

        # Draw arrowhead at start if bidirectional
        if route.is_bidirectional and len(waypoints) >= 2:
            from_pt = waypoints[1]
            to_pt = waypoints[0]
            self._draw_arrowhead(draw, from_pt, to_pt)

    def _draw_arrowhead(
        self,
        draw: ImageDraw.Draw,
        from_point: Tuple[int, int],
        to_point: Tuple[int, int],
    ):
        """Draw an arrowhead at the end of a line."""
        x1, y1 = from_point
        x2, y2 = to_point

        arrow_size = 8 * self.scale

        # Calculate angle
        angle = math.atan2(y2 - y1, x2 - x1)

        # Calculate arrowhead points
        angle1 = angle + math.pi * 0.8
        angle2 = angle - math.pi * 0.8

        ax1 = x2 + arrow_size * math.cos(angle1)
        ay1 = y2 + arrow_size * math.sin(angle1)
        ax2 = x2 + arrow_size * math.cos(angle2)
        ay2 = y2 + arrow_size * math.sin(angle2)

        # Draw filled arrowhead
        draw.polygon([(x2, y2), (ax1, ay1), (ax2, ay2)], fill=self.line_color)


def render_to_png(graph, layout, output_path: str = "diagram.png", **kwargs) -> str:
    """
    Convenience function to render a flowchart to PNG.

    Args:
        graph: Graph object
        layout: Layout object
        output_path: Path to save the PNG file
        **kwargs: Additional parameters for PNGRenderer

    Returns:
        Path to the saved PNG file
    """
    renderer = PNGRenderer(**kwargs)
    return renderer.render(graph, layout, output_path)
