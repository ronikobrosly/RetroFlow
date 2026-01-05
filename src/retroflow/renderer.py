"""
Renderer module for flowchart generator.

Handles ASCII rendering of flowcharts with boxes and arrows.
"""


class ASCIICanvas:
    """Canvas for drawing ASCII art."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.canvas = [[" " for _ in range(width)] for _ in range(height)]

    def set_char(self, x: int, y: int, char: str):
        """Set a character at position (x, y)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.canvas[y][x] = char

    def get_char(self, x: int, y: int) -> str:
        """Get character at position (x, y)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.canvas[y][x]
        return " "

    def draw_box(self, x: int, y: int, width: int, height: int, label: str):
        """Draw a box with shadow at position (x, y)."""
        # Top border
        self.set_char(x, y, "┌")
        for i in range(1, width - 1):
            self.set_char(x + i, y, "─")
        self.set_char(x + width - 1, y, "┐")

        # Middle rows
        for row in range(1, height - 1):
            self.set_char(x, y + row, "│")
            # Add label in the middle row
            if row == (height - 1) // 2:
                label_padded = label.center(width - 2)
                for i, char in enumerate(label_padded):
                    self.set_char(x + 1 + i, y + row, char)
            self.set_char(x + width - 1, y + row, "│")
            self.set_char(x + width, y + row, "░")  # Shadow

        # Bottom border
        self.set_char(x, y + height - 1, "└")
        for i in range(1, width - 1):
            self.set_char(x + i, y + height - 1, "─")
        self.set_char(x + width - 1, y + height - 1, "┘")
        self.set_char(x + width, y + height - 1, "░")  # Shadow

        # Bottom shadow
        for i in range(1, width + 1):
            self.set_char(x + i, y + height, "░")

    def draw_line(self, x1: int, y1: int, x2: int, y2: int, char: str = "│"):
        """Draw a line from (x1, y1) to (x2, y2)."""
        if x1 == x2:  # Vertical line
            start_y, end_y = min(y1, y2), max(y1, y2)
            for y in range(start_y, end_y + 1):
                if self.get_char(x1, y) == " ":
                    self.set_char(x1, y, "│")
        elif y1 == y2:  # Horizontal line
            start_x, end_x = min(x1, x2), max(x1, x2)
            for x in range(start_x, end_x + 1):
                if self.get_char(x, y1) == " ":
                    self.set_char(x, y1, "─")

    def draw_arrow_down(self, x: int, y: int):
        """Draw a downward arrow at position."""
        self.set_char(x, y, "▼")

    def draw_arrow_up(self, x: int, y: int):
        """Draw an upward arrow at position."""
        self.set_char(x, y, "▲")

    def draw_corner(self, x: int, y: int, corner_type: str):
        """Draw a corner piece."""
        corners = {
            "top-left": "┌",
            "top-right": "┐",
            "bottom-left": "└",
            "bottom-right": "┘",
            "cross": "┼",
            "tee-down": "┬",
            "tee-up": "┴",
            "tee-right": "├",
            "tee-left": "┤",
        }
        if corner_type in corners:
            self.set_char(x, y, corners[corner_type])

    def to_string(self) -> str:
        """Convert canvas to string."""
        # Remove trailing whitespace from each line
        lines = ["".join(row).rstrip() for row in self.canvas]
        # Remove trailing empty lines
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)


class FlowchartRenderer:
    """Renders flowcharts using ASCII art."""

    def __init__(
        self, box_width=11, box_height=3, horizontal_spacing=4, vertical_spacing=3
    ):
        self.box_width = box_width
        self.box_height = box_height
        self.horizontal_spacing = horizontal_spacing
        self.vertical_spacing = vertical_spacing
        self.node_positions = {}  # pixel positions
        self.canvas = None

    def render(self, graph, layout) -> str:
        """
        Render the flowchart.

        Args:
            graph: Graph object
            layout: Layout object with node positions

        Returns:
            ASCII string representation
        """
        # Get layout dimensions
        layout_width, layout_height = layout.get_layout_dimensions()

        if layout_width == 0 or layout_height == 0:
            return "Empty graph"

        # Calculate canvas size
        total_box_width = self.box_width + 1  # +1 for shadow
        total_box_height = self.box_height + 1  # +1 for shadow

        canvas_width = (
            layout_width * (total_box_width + self.horizontal_spacing)
            + self.horizontal_spacing
        )
        canvas_height = (
            layout_height * (total_box_height + self.vertical_spacing)
            + self.vertical_spacing
        )

        self.canvas = ASCIICanvas(canvas_width, canvas_height)

        # Calculate pixel positions for each node
        for node, (layer_x, layer_y) in layout.positions.items():
            horiz = self.horizontal_spacing
            vert = self.vertical_spacing
            pixel_x = horiz + layer_x * (total_box_width + horiz)
            pixel_y = vert + layer_y * (total_box_height + vert)
            self.node_positions[node] = (pixel_x, pixel_y)

        # Draw connections first (so boxes appear on top)
        self._draw_connections(graph, layout)

        # Draw boxes
        for node, (x, y) in self.node_positions.items():
            self.canvas.draw_box(x, y, self.box_width, self.box_height, node)

        return self.canvas.to_string()

    def _draw_connections(self, graph, layout):
        """Draw arrows between connected nodes."""
        edges = layout.get_edges_for_rendering()

        for source, target, is_feedback in edges:
            if source not in self.node_positions or target not in self.node_positions:
                continue

            src_x, src_y = self.node_positions[source]
            tgt_x, tgt_y = self.node_positions[target]

            # Calculate center points of boxes
            src_center_x = src_x + self.box_width // 2
            src_bottom_y = src_y + self.box_height

            tgt_center_x = tgt_x + self.box_width // 2
            tgt_top_y = tgt_y

            if is_feedback:
                # Draw feedback edge (reversed direction)
                self._draw_feedback_arrow(
                    src_center_x, src_bottom_y, tgt_center_x, tgt_top_y
                )
            else:
                # Draw normal arrow
                self._draw_arrow(src_center_x, src_bottom_y, tgt_center_x, tgt_top_y)

    def _draw_arrow(self, x1: int, y1: int, x2: int, y2: int):
        """Draw an arrow from (x1, y1) to (x2, y2)."""
        # Simple routing: go down, then horizontal, then down

        if x1 == x2:
            # Straight vertical line
            for y in range(y1 + 1, y2):
                self.canvas.set_char(x1, y, "│")
            if y2 > y1 + 1:
                self.canvas.draw_arrow_down(x2, y2 - 1)
        else:
            # Go down a bit
            mid_y = (y1 + y2) // 2

            # Vertical line down
            for y in range(y1 + 1, mid_y):
                self.canvas.set_char(x1, y, "│")

            # Horizontal line
            if x1 < x2:
                # Going right
                self.canvas.draw_corner(x1, mid_y, "bottom-left")
                for x in range(x1 + 1, x2):
                    self.canvas.set_char(x, mid_y, "─")
                self.canvas.draw_corner(x2, mid_y, "bottom-right")
            else:
                # Going left
                self.canvas.draw_corner(x1, mid_y, "bottom-right")
                for x in range(x2 + 1, x1):
                    self.canvas.set_char(x, mid_y, "─")
                self.canvas.draw_corner(x2, mid_y, "bottom-left")

            # Vertical line down to target
            for y in range(mid_y + 1, y2):
                self.canvas.set_char(x2, y, "│")

            if y2 > mid_y + 1:
                self.canvas.draw_arrow_down(x2, y2 - 1)

    def _draw_feedback_arrow(self, x1: int, y1: int, x2: int, y2: int):
        """Draw a feedback arrow (dashed or different style)."""
        # For now, just draw it the same way
        # Could be enhanced with different styling
        self._draw_arrow(x1, y1, x2, y2)


def render_flowchart(graph, layout, **kwargs) -> str:
    """
    Convenience function to render a flowchart.

    Args:
        graph: Graph object
        layout: Layout object
        **kwargs: Additional parameters for renderer

    Returns:
        ASCII string representation
    """
    renderer = FlowchartRenderer(**kwargs)
    return renderer.render(graph, layout)
