"""
Debug utilities for retroflow.

This module provides debugging tools for understanding and troubleshooting
flowchart rendering. The main component is TracedCanvas, which wraps a
regular Canvas and logs every character placement.

Key Components:
- TracedCanvas: Canvas wrapper that logs all character operations
- visual_diff: Compare two ASCII diagrams character-by-character
- CanvasInspector: Utilities for inspecting canvas state

Usage:
    # TracedCanvas is used internally by FlowchartGenerator when debug=True
    # You typically access traces via the generator:

    >>> generator = FlowchartGenerator()
    >>> result = generator.generate("A -> B", debug=True)
    >>> trace = generator.get_trace()

    # For comparing expected vs actual output:
    >>> from retroflow.debug import visual_diff
    >>> diff = visual_diff(expected_output, actual_output)
    >>> print(diff)
"""

from typing import List, Protocol

from .tracer import RenderTrace


class CanvasProtocol(Protocol):
    """Protocol for Canvas-like objects."""

    width: int
    height: int

    def set(self, x: int, y: int, char: str) -> None:
        """Set a character at position."""
        ...

    def get(self, x: int, y: int) -> str:
        """Get character at position."""
        ...

    def draw_text(self, x: int, y: int, text: str) -> None:
        """Draw text starting at position."""
        ...

    def render(self) -> str:
        """Render canvas to string."""
        ...


class TracedCanvas:
    """
    Canvas wrapper that logs all character placements to a RenderTrace.

    This wraps a regular Canvas object and intercepts all set() calls,
    recording them in a RenderTrace for later analysis. This is the key
    tool for understanding how the flowchart is built up character by character.

    The TracedCanvas maintains a "current source" context that identifies
    which part of the code is making placements. Use set_source() to update
    this context before making placements.

    Attributes:
        width: Canvas width (delegated to wrapped canvas)
        height: Canvas height (delegated to wrapped canvas)

    Example:
        >>> from retroflow.renderer import Canvas
        >>> from retroflow.tracer import RenderTrace
        >>> from retroflow.debug import TracedCanvas
        >>>
        >>> canvas = Canvas(80, 40)
        >>> trace = RenderTrace()
        >>> traced = TracedCanvas(canvas, trace)
        >>>
        >>> traced.set_source("EdgeDrawer._draw_vertical_line")
        >>> traced.set(10, 5, "│", reason="vertical_line")
        >>>
        >>> # Check what was recorded
        >>> print(trace.character_placements[-1])
    """

    def __init__(self, canvas: CanvasProtocol, trace: RenderTrace):
        """
        Initialize a TracedCanvas.

        Args:
            canvas: The underlying Canvas to wrap
            trace: The RenderTrace to record placements to
        """
        self._canvas = canvas
        self._trace = trace
        self._current_source = "unknown"

    @property
    def width(self) -> int:
        """Canvas width."""
        return self._canvas.width

    @property
    def height(self) -> int:
        """Canvas height."""
        return self._canvas.height

    def set_source(self, source: str) -> None:
        """
        Set the current source context for character placements.

        This should be called before making set() calls to identify
        which part of the code is responsible for the placements.

        Args:
            source: Identifier for the source (e.g., "EdgeDrawer._draw_edge")
        """
        self._current_source = source

    def set(self, x: int, y: int, char: str, reason: str = "") -> None:
        """
        Set a character at position (x, y) and record the placement.

        Args:
            x: X coordinate
            y: Y coordinate
            char: Character to place
            reason: Why this character is being placed (e.g., "vertical_line",
                    "corner_upgrade_to_cross"). If empty, a default reason
                    based on the character is used.
        """
        # Get the previous character before setting
        prev = self._canvas.get(x, y)

        # Set on the underlying canvas
        self._canvas.set(x, y, char)

        # Generate default reason if not provided
        if not reason:
            reason = self._infer_reason(char, prev)

        # Record the placement
        self._trace.add_placement(
            x=x,
            y=y,
            char=char,
            previous_char=prev,
            reason=reason,
            source=self._current_source,
        )

    def get(self, x: int, y: int) -> str:
        """Get character at position (x, y)."""
        return self._canvas.get(x, y)

    def draw_text(self, x: int, y: int, text: str) -> None:
        """
        Draw text starting at position (x, y).

        Each character is recorded as a separate placement.
        """
        for i, char in enumerate(text):
            self.set(x + i, y, char, reason="text")

    def render(self) -> str:
        """Render the canvas to a string."""
        return self._canvas.render()

    def _infer_reason(self, char: str, prev: str) -> str:
        """Infer a reason based on the character being placed."""
        # Line characters
        if char == "│":
            return "vertical_line"
        if char == "─":
            return "horizontal_line"

        # Corners
        if char in "┌┐└┘":
            corner_names = {
                "┌": "top_left",
                "┐": "top_right",
                "└": "bottom_left",
                "┘": "bottom_right",
            }
            return f"corner_{corner_names.get(char, 'unknown')}"

        # Tees (junctions)
        if char in "├┤┬┴":
            if prev in "┌┐└┘│─":
                return "upgrade_to_tee"
            return "tee"

        # Cross
        if char == "┼":
            return "upgrade_to_cross" if prev != " " else "cross"

        # Arrows
        if char in "▼▲◄►":
            return "arrow"

        # Box characters
        if char == "░":
            return "shadow"

        # Default
        return "char_placement"


def visual_diff(expected: str, actual: str, context_lines: int = 2) -> str:
    """
    Generate a visual character-by-character diff between two ASCII diagrams.

    This is useful for debugging test failures where the expected and actual
    outputs differ. It shows exactly where the differences are and what
    characters differ.

    Args:
        expected: The expected ASCII output
        actual: The actual ASCII output
        context_lines: Number of matching lines to show around differences

    Returns:
        A formatted string showing the differences

    Example:
        >>> expected = "┌───┐\\n│ A │\\n└───┘"
        >>> actual = "┌───┐\\n│ B │\\n└───┘"
        >>> print(visual_diff(expected, actual))
    """
    exp_lines = expected.split("\n")
    act_lines = actual.split("\n")

    output: List[str] = []
    output.append("=" * 60)
    output.append("VISUAL DIFF")
    output.append("=" * 60)

    max_lines = max(len(exp_lines), len(act_lines))
    differences_found = False

    # Track which lines have differences
    diff_line_indices: List[int] = []

    for i in range(max_lines):
        exp_line = exp_lines[i] if i < len(exp_lines) else ""
        act_line = act_lines[i] if i < len(act_lines) else ""

        if exp_line != act_line:
            diff_line_indices.append(i)
            differences_found = True

    if not differences_found:
        output.append("No differences found.")
        return "\n".join(output)

    output.append(f"Found {len(diff_line_indices)} differing line(s)")
    output.append("")

    # Show differences with context
    shown_lines: set = set()
    for diff_idx in diff_line_indices:
        # Add context lines before
        for ctx in range(max(0, diff_idx - context_lines), diff_idx):
            shown_lines.add(ctx)
        # Add the diff line
        shown_lines.add(diff_idx)
        # Add context lines after
        for ctx in range(diff_idx + 1, min(max_lines, diff_idx + context_lines + 1)):
            shown_lines.add(ctx)

    prev_shown = -2
    for i in sorted(shown_lines):
        # Show ellipsis for gaps
        if i > prev_shown + 1:
            output.append("...")

        exp_line = exp_lines[i] if i < len(exp_lines) else ""
        act_line = act_lines[i] if i < len(act_lines) else ""

        if exp_line == act_line:
            output.append(f"{i:3d}:   {act_line}")
        else:
            output.append(f"{i:3d}: E |{exp_line}|")
            output.append(f"     A |{act_line}|")

            # Show position of differences
            diff_positions: List[int] = []
            max_len = max(len(exp_line), len(act_line))
            for j in range(max_len):
                e = exp_line[j] if j < len(exp_line) else ""
                a = act_line[j] if j < len(act_line) else ""
                if e != a:
                    diff_positions.append(j)

            if diff_positions:
                # Create a marker line showing where differences are
                marker = [" "] * (max_len + 7)  # +7 for "     A |" prefix
                for pos in diff_positions:
                    if pos + 7 < len(marker):
                        marker[pos + 7] = "^"
                output.append("".join(marker))
                output.append(
                    f"     Diff at col(s): {diff_positions[:5]}"
                    f"{'...' if len(diff_positions) > 5 else ''}"
                )

        prev_shown = i

    return "\n".join(output)


class CanvasInspector:
    """
    Utilities for inspecting canvas state.

    Provides methods for analyzing what's on a canvas at various positions,
    finding specific characters, and extracting regions.
    """

    def __init__(self, canvas: CanvasProtocol):
        """
        Initialize the inspector.

        Args:
            canvas: The canvas to inspect
        """
        self._canvas = canvas

    def find_char(self, char: str) -> List[tuple]:
        """
        Find all positions of a specific character.

        Args:
            char: The character to find

        Returns:
            List of (x, y) tuples where the character appears
        """
        positions = []
        for y in range(self._canvas.height):
            for x in range(self._canvas.width):
                if self._canvas.get(x, y) == char:
                    positions.append((x, y))
        return positions

    def find_chars(self, chars: str) -> List[tuple]:
        """
        Find all positions of any character in the given set.

        Args:
            chars: String of characters to find (e.g., "┌┐└┘")

        Returns:
            List of (x, y, char) tuples
        """
        positions = []
        char_set = set(chars)
        for y in range(self._canvas.height):
            for x in range(self._canvas.width):
                c = self._canvas.get(x, y)
                if c in char_set:
                    positions.append((x, y, c))
        return positions

    def get_row(self, y: int) -> str:
        """Get a single row as a string."""
        if 0 <= y < self._canvas.height:
            return "".join(self._canvas.get(x, y) for x in range(self._canvas.width))
        return ""

    def get_column(self, x: int) -> str:
        """Get a single column as a string."""
        if 0 <= x < self._canvas.width:
            return "".join(self._canvas.get(x, y) for y in range(self._canvas.height))
        return ""

    def get_region(self, x: int, y: int, width: int, height: int) -> str:
        """
        Get a rectangular region of the canvas.

        Args:
            x: Left edge X coordinate
            y: Top edge Y coordinate
            width: Width of region
            height: Height of region

        Returns:
            Multi-line string of the region
        """
        lines = []
        for row in range(y, y + height):
            line = ""
            for col in range(x, x + width):
                line += self._canvas.get(col, row)
            lines.append(line)
        return "\n".join(lines)

    def count_char(self, char: str) -> int:
        """Count occurrences of a character."""
        return len(self.find_char(char))

    def get_line_chars_count(self) -> dict:
        """
        Count all line-drawing characters on the canvas.

        Returns:
            Dictionary mapping character to count
        """
        line_chars = "│─┌┐└┘├┤┬┴┼▼▲◄►"
        counts = {}
        for char in line_chars:
            count = self.count_char(char)
            if count > 0:
                counts[char] = count
        return counts
