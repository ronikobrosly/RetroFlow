"""
ASCII renderer module for flowchart generation.

Handles drawing boxes with shadows, text wrapping, and line art
using Unicode box-drawing characters.
"""

from dataclasses import dataclass
from typing import List

# Unicode box-drawing characters
BOX_CHARS = {
    "top_left": "┌",
    "top_right": "┐",
    "bottom_left": "└",
    "bottom_right": "┘",
    "horizontal": "─",
    "vertical": "│",
    "shadow": "░",
}

# Arrow characters
ARROW_CHARS = {
    "down": "▼",
    "up": "▲",
    "right": "►",
    "left": "◄",
}

# Line drawing characters for routing
LINE_CHARS = {
    "horizontal": "─",
    "vertical": "│",
    "corner_top_left": "┌",
    "corner_top_right": "┐",
    "corner_bottom_left": "└",
    "corner_bottom_right": "┘",
    "tee_right": "├",
    "tee_left": "┤",
    "tee_down": "┬",
    "tee_up": "┴",
    "cross": "┼",
}


@dataclass
class BoxDimensions:
    """Dimensions of a rendered box."""

    width: int  # Total width including border
    height: int  # Total height including border
    text_lines: List[str]  # Wrapped text lines
    padding: int = 1  # Internal padding


class Canvas:
    """
    A 2D character canvas for drawing ASCII art.
    """

    def __init__(self, width: int, height: int, fill_char: str = " "):
        self.width = width
        self.height = height
        self.grid: List[List[str]] = [
            [fill_char for _ in range(width)] for _ in range(height)
        ]

    def set(self, x: int, y: int, char: str) -> None:
        """Set a character at position (x, y)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = char

    def get(self, x: int, y: int) -> str:
        """Get character at position (x, y)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x]
        return " "

    def draw_text(self, x: int, y: int, text: str) -> None:
        """Draw text starting at position (x, y)."""
        for i, char in enumerate(text):
            self.set(x + i, y, char)

    def render(self) -> str:
        """Render the canvas to a string."""
        lines = []
        for row in self.grid:
            line = "".join(row).rstrip()
            lines.append(line)

        # Remove trailing empty lines
        while lines and not lines[-1]:
            lines.pop()

        return "\n".join(lines)


class BoxRenderer:
    """
    Renders boxes with shadows and wrapped text.
    """

    def __init__(self, max_text_width: int = 20, padding: int = 1, shadow: bool = True):
        self.max_text_width = max_text_width
        self.padding = padding
        self.shadow = shadow

    def calculate_box_dimensions(self, text: str) -> BoxDimensions:
        """
        Calculate box dimensions based on text content.
        Text is wrapped to fit within max_text_width.
        """
        words = text.split()
        lines: List[str] = []
        current_line: List[str] = []
        current_length = 0

        for word in words:
            word_len = len(word)
            space_needed = 1 if current_line else 0

            if current_length + word_len + space_needed <= self.max_text_width:
                current_line.append(word)
                current_length += word_len + (1 if len(current_line) > 1 else 0)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_len

        if current_line:
            lines.append(" ".join(current_line))

        if not lines:
            lines = [""]

        # Calculate dimensions
        max_line_width = max(len(line) for line in lines)
        text_width = max(max_line_width, 1)

        # Box width = text_width + 2*padding + 2 (for borders)
        box_width = text_width + 2 * self.padding + 2

        # Box height = num_lines + 2*padding + 2 (for borders)
        # But padding is typically 0 for vertical, let's use 0 vertical padding
        box_height = len(lines) + 2  # Just borders, no vertical padding

        return BoxDimensions(
            width=box_width, height=box_height, text_lines=lines, padding=self.padding
        )

    def draw_box(
        self, canvas: Canvas, x: int, y: int, dimensions: BoxDimensions
    ) -> None:
        """
        Draw a box with shadow at position (x, y).

        Box structure (shadow on right side of content and bottom):
        ┌───────────┐
        │   TEXT    │░
        └───────────┘░
          ░░░░░░░░░░░░
        """
        w = dimensions.width
        h = dimensions.height

        # Draw top border (no shadow on top row)
        canvas.set(x, y, BOX_CHARS["top_left"])
        for i in range(1, w - 1):
            canvas.set(x + i, y, BOX_CHARS["horizontal"])
        canvas.set(x + w - 1, y, BOX_CHARS["top_right"])

        # Draw sides and content
        for row in range(1, h - 1):
            canvas.set(x, y + row, BOX_CHARS["vertical"])
            canvas.set(x + w - 1, y + row, BOX_CHARS["vertical"])

            # Draw shadow on right side (content rows only)
            if self.shadow:
                canvas.set(x + w, y + row, BOX_CHARS["shadow"])

        # Draw bottom border
        canvas.set(x, y + h - 1, BOX_CHARS["bottom_left"])
        for i in range(1, w - 1):
            canvas.set(x + i, y + h - 1, BOX_CHARS["horizontal"])
        canvas.set(x + w - 1, y + h - 1, BOX_CHARS["bottom_right"])

        # Draw shadow on right side of bottom border
        if self.shadow:
            canvas.set(x + w, y + h - 1, BOX_CHARS["shadow"])

        # Draw bottom shadow (offset by 1 to align under content, not under left border)
        if self.shadow:
            for i in range(1, w + 1):
                canvas.set(x + i, y + h, BOX_CHARS["shadow"])

        # Draw text (centered)
        for line_idx, line in enumerate(dimensions.text_lines):
            text_y = y + 1 + line_idx
            # Center the text within the box
            available_width = w - 2  # Minus borders
            text_x = x + 1 + (available_width - len(line)) // 2
            canvas.draw_text(text_x, text_y, line)


class LineRenderer:
    """
    Renders lines and arrows between boxes.
    """

    def draw_vertical_line(
        self,
        canvas: Canvas,
        x: int,
        y_start: int,
        y_end: int,
        arrow_at_end: bool = True,
    ) -> None:
        """Draw a vertical line from y_start to y_end."""
        if y_start > y_end:
            y_start, y_end = y_end, y_start
            direction = "up"
        else:
            direction = "down"

        for y in range(y_start, y_end):
            current = canvas.get(x, y)
            if current == LINE_CHARS["horizontal"]:
                canvas.set(x, y, LINE_CHARS["cross"])
            elif current == LINE_CHARS["corner_top_left"]:
                canvas.set(x, y, LINE_CHARS["tee_right"])
            elif current == LINE_CHARS["corner_top_right"]:
                canvas.set(x, y, LINE_CHARS["tee_left"])
            elif current == LINE_CHARS["corner_bottom_left"]:
                canvas.set(x, y, LINE_CHARS["tee_right"])
            elif current == LINE_CHARS["corner_bottom_right"]:
                canvas.set(x, y, LINE_CHARS["tee_left"])
            elif current in (ARROW_CHARS["down"], ARROW_CHARS["up"]):
                pass  # Don't overwrite arrows
            elif current == " " or current == LINE_CHARS["vertical"]:
                canvas.set(x, y, LINE_CHARS["vertical"])

        # Draw arrow at end
        if arrow_at_end:
            arrow_y = y_end if direction == "down" else y_start
            canvas.set(x, arrow_y, ARROW_CHARS[direction])

    def draw_horizontal_line(
        self,
        canvas: Canvas,
        x_start: int,
        x_end: int,
        y: int,
        arrow_at_end: bool = True,
    ) -> None:
        """Draw a horizontal line from x_start to x_end."""
        if x_start > x_end:
            x_start, x_end = x_end, x_start
            direction = "left"
        else:
            direction = "right"

        for x in range(x_start, x_end):
            current = canvas.get(x, y)
            if current == LINE_CHARS["vertical"]:
                canvas.set(x, y, LINE_CHARS["cross"])
            elif current == LINE_CHARS["corner_top_left"]:
                canvas.set(x, y, LINE_CHARS["tee_down"])
            elif current == LINE_CHARS["corner_top_right"]:
                canvas.set(x, y, LINE_CHARS["tee_down"])
            elif current == LINE_CHARS["corner_bottom_left"]:
                canvas.set(x, y, LINE_CHARS["tee_up"])
            elif current == LINE_CHARS["corner_bottom_right"]:
                canvas.set(x, y, LINE_CHARS["tee_up"])
            elif current in (ARROW_CHARS["left"], ARROW_CHARS["right"]):
                pass  # Don't overwrite arrows
            elif current == " " or current == LINE_CHARS["horizontal"]:
                canvas.set(x, y, LINE_CHARS["horizontal"])

        # Draw arrow at end
        if arrow_at_end:
            arrow_x = x_end if direction == "right" else x_start
            canvas.set(arrow_x, y, ARROW_CHARS[direction])

    def draw_corner(self, canvas: Canvas, x: int, y: int, corner_type: str) -> None:
        """
        Draw a corner character.
        corner_type: 'top_left', 'top_right', 'bottom_left', 'bottom_right'
        """
        current = canvas.get(x, y)

        if current == " ":
            canvas.set(x, y, LINE_CHARS[f"corner_{corner_type}"])
        elif current == LINE_CHARS["horizontal"]:
            if "top" in corner_type:
                canvas.set(x, y, LINE_CHARS["tee_down"])
            else:
                canvas.set(x, y, LINE_CHARS["tee_up"])
        elif current == LINE_CHARS["vertical"]:
            if "left" in corner_type:
                canvas.set(x, y, LINE_CHARS["tee_right"])
            else:
                canvas.set(x, y, LINE_CHARS["tee_left"])
        elif current.startswith("corner_") or current in LINE_CHARS.values():
            canvas.set(x, y, LINE_CHARS["cross"])
