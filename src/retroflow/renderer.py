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

# Double-line box characters (for titles/headers)
BOX_CHARS_DOUBLE = {
    "top_left": "╔",
    "top_right": "╗",
    "bottom_left": "╚",
    "bottom_right": "╝",
    "horizontal": "═",
    "vertical": "║",
}

# Rounded corner variants
BOX_CHARS_ROUNDED = {
    "top_left": "╭",
    "top_right": "╮",
    "bottom_left": "╰",
    "bottom_right": "╯",
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

# Dashed box-drawing characters for group boxes
DASHED_BOX_CHARS = {
    "horizontal": "┄",  # Light triple dash horizontal
    "vertical": "┆",  # Light triple dash vertical
    "top_left": "┌",  # Corners remain solid for clarity
    "top_right": "┐",
    "bottom_left": "└",
    "bottom_right": "┘",
    "shadow": "░",
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

    def set(self, x: int, y: int, char: str, reason: str = "") -> None:
        """
        Set a character at position (x, y).

        Args:
            x: X coordinate
            y: Y coordinate
            char: Character to place
            reason: Optional reason for placement (used by TracedCanvas for debugging,
                    ignored by regular Canvas)
        """
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

    def __init__(
        self,
        max_text_width: int = 20,
        padding: int = 1,
        shadow: bool = True,
        rounded: bool = False,
        compact: bool = True,
    ):
        self.max_text_width = max_text_width
        self.padding = padding
        self.shadow = shadow
        self.rounded = rounded
        self.compact = compact
        self.box_chars = BOX_CHARS_ROUNDED if rounded else BOX_CHARS

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

        # Box height = num_lines + 2 (for borders) + vertical padding
        # Compact mode: no vertical padding (height = lines + 2)
        # Normal mode: 1 line padding top and bottom (height = lines + 4)
        if self.compact:
            box_height = len(lines) + 2
        else:
            box_height = len(lines) + 4

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
        chars = self.box_chars

        # Draw top border (no shadow on top row)
        canvas.set(x, y, chars["top_left"])
        for i in range(1, w - 1):
            canvas.set(x + i, y, chars["horizontal"])
        canvas.set(x + w - 1, y, chars["top_right"])

        # Draw sides and content
        for row in range(1, h - 1):
            canvas.set(x, y + row, chars["vertical"])
            canvas.set(x + w - 1, y + row, chars["vertical"])

            # Draw shadow on right side (content rows only)
            if self.shadow:
                canvas.set(x + w, y + row, chars["shadow"])

        # Draw bottom border
        canvas.set(x, y + h - 1, chars["bottom_left"])
        for i in range(1, w - 1):
            canvas.set(x + i, y + h - 1, chars["horizontal"])
        canvas.set(x + w - 1, y + h - 1, chars["bottom_right"])

        # Draw shadow on right side of bottom border
        if self.shadow:
            canvas.set(x + w, y + h - 1, chars["shadow"])

        # Draw bottom shadow (offset by 1 to align under content, not under left border)
        if self.shadow:
            for i in range(1, w + 1):
                canvas.set(x + i, y + h, chars["shadow"])

        # Draw text (centered)
        # Compact mode: text starts at row 1 (right after top border)
        # Normal mode: text starts at row 2 (1 line vertical padding)
        text_start_y = y + 1 if self.compact else y + 2
        for line_idx, line in enumerate(dimensions.text_lines):
            text_y = text_start_y + line_idx
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
            elif current in (" ", LINE_CHARS["vertical"], BOX_CHARS["shadow"]):
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
            elif current in (" ", LINE_CHARS["horizontal"], BOX_CHARS["shadow"]):
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

        if current in (" ", BOX_CHARS["shadow"]):
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


class TitleRenderer:
    """
    Renders title banners with double-line borders.
    """

    def __init__(self, padding: int = 2, max_line_width: int = 15):
        """
        Initialize the title renderer.

        Args:
            padding: Horizontal padding inside the title box
            max_line_width: Maximum width for text before wrapping (default 15)
        """
        self.padding = padding
        self.max_line_width = max_line_width
        self.box_chars = BOX_CHARS_DOUBLE

    def _wrap_title_text(self, title: str) -> List[str]:
        """
        Wrap title text at word boundaries, respecting max_line_width.

        Words are wrapped so that each line doesn't exceed max_line_width
        characters (wrapping at the word boundary after reaching the limit).

        Args:
            title: The title text to wrap

        Returns:
            List of wrapped lines
        """
        words = title.split()
        if not words:
            return [""]

        lines: List[str] = []
        current_line: List[str] = []
        current_length = 0

        for word in words:
            word_len = len(word)
            space_needed = 1 if current_line else 0

            # Check if adding this word exceeds the limit
            if current_length + space_needed + word_len > self.max_line_width:
                # If we have content on the current line, save it and start new line
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                    current_length = word_len
                else:
                    # Single word exceeds limit - just add it anyway
                    lines.append(word)
                    current_line = []
                    current_length = 0
            else:
                current_line.append(word)
                current_length += space_needed + word_len

        # Add remaining content
        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [""]

    def calculate_title_dimensions(self, title: str, min_width: int = 0) -> tuple:
        """
        Calculate the dimensions needed for a title banner.

        The title is wrapped at word boundaries respecting max_line_width,
        and the box is sized to fit the wrapped text (not the diagram width).

        Args:
            title: The title text
            min_width: Minimum width for the title box (ignored for sizing,
                       but returned for compatibility)

        Returns:
            Tuple of (width, height) for the title box
        """
        # Wrap the title text
        lines = self._wrap_title_text(title)

        # Calculate width based on longest wrapped line
        max_line_len = max(len(line) for line in lines)

        # Title box: border + padding + text + padding + border
        box_width = max_line_len + 2 * self.padding + 2
        # Height: top border + text lines + bottom border
        box_height = len(lines) + 2

        return box_width, box_height

    def draw_title(self, canvas: Canvas, x: int, y: int, title: str, width: int) -> int:
        """
        Draw a title banner with double-line border.

        The title is wrapped at word boundaries and centered within the box.

        Args:
            canvas: The canvas to draw on
            x: X position (left edge)
            y: Y position (top edge)
            title: The title text
            width: Total width of the title box (used for centering text)

        Returns:
            The height of the title box (for positioning content below)
        """
        chars = self.box_chars
        lines = self._wrap_title_text(title)

        # Recalculate actual width based on content
        max_line_len = max(len(line) for line in lines)
        actual_width = max_line_len + 2 * self.padding + 2
        height = len(lines) + 2

        # Draw top border
        canvas.set(x, y, chars["top_left"])
        for i in range(1, actual_width - 1):
            canvas.set(x + i, y, chars["horizontal"])
        canvas.set(x + actual_width - 1, y, chars["top_right"])

        # Draw middle rows with title text (centered)
        for line_idx, line in enumerate(lines):
            row_y = y + 1 + line_idx
            canvas.set(x, row_y, chars["vertical"])
            canvas.set(x + actual_width - 1, row_y, chars["vertical"])

            # Center the text line within the box
            available_width = actual_width - 2  # Minus borders
            text_start = x + 1 + (available_width - len(line)) // 2
            canvas.draw_text(text_start, row_y, line)

        # Draw bottom border
        canvas.set(x, y + height - 1, chars["bottom_left"])
        for i in range(1, actual_width - 1):
            canvas.set(x + i, y + height - 1, chars["horizontal"])
        canvas.set(x + actual_width - 1, y + height - 1, chars["bottom_right"])

        return height  # Height of the title box


class GroupBoxRenderer:
    """
    Renders group boxes with dashed borders and shadows.

    Group boxes visually cluster related nodes together. They use dashed
    line characters for borders (to distinguish from solid node boxes)
    and have shadows on the right and bottom edges.
    """

    def __init__(self, shadow: bool = True):
        """
        Initialize the group box renderer.

        Args:
            shadow: Whether to draw shadows on group boxes.
        """
        self.shadow = shadow
        self.chars = DASHED_BOX_CHARS

    def draw_group_box(
        self,
        canvas: Canvas,
        x: int,
        y: int,
        width: int,
        height: int,
        title: str = "",
    ) -> None:
        """
        Draw a group box with dashed border.

        The title is drawn centered above the top border of the box.

        Args:
            canvas: The canvas to draw on.
            x: X position of the left edge.
            y: Y position of the top edge (where title goes).
            width: Width of the group box.
            height: Height of the group box (including title row if present).
            title: Title text to display above the box.
        """
        chars = self.chars

        # Calculate title row position and box start
        title_row = y
        box_top = y + 1 if title else y

        # Adjust height to account for title
        box_height = height - 1 if title else height

        # Draw title text (centered above the box)
        if title:
            # Center the title over the box
            title_start = x + (width - len(title)) // 2
            canvas.draw_text(title_start, title_row, title)

        # Draw top border (solid corners, dashed line)
        canvas.set(x, box_top, chars["top_left"])
        for i in range(1, width - 1):
            canvas.set(x + i, box_top, chars["horizontal"])
        canvas.set(x + width - 1, box_top, chars["top_right"])

        # Draw sides (dashed vertical lines)
        for row in range(1, box_height - 1):
            canvas.set(x, box_top + row, chars["vertical"])
            canvas.set(x + width - 1, box_top + row, chars["vertical"])

            # Draw shadow on right side
            if self.shadow:
                canvas.set(x + width, box_top + row, chars["shadow"])

        # Draw bottom border (solid corners, dashed line)
        canvas.set(x, box_top + box_height - 1, chars["bottom_left"])
        for i in range(1, width - 1):
            canvas.set(x + i, box_top + box_height - 1, chars["horizontal"])
        canvas.set(x + width - 1, box_top + box_height - 1, chars["bottom_right"])

        # Draw shadow on right side of bottom border
        if self.shadow:
            canvas.set(x + width, box_top + box_height - 1, chars["shadow"])

        # Draw bottom shadow
        if self.shadow:
            for i in range(1, width + 1):
                canvas.set(x + i, box_top + box_height, chars["shadow"])
