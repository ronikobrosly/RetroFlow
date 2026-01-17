"""
Tests for the debug module.

These tests verify the debug utilities including TracedCanvas,
visual_diff, and CanvasInspector.
"""

from retroflow.debug import CanvasInspector, TracedCanvas, visual_diff
from retroflow.renderer import Canvas
from retroflow.tracer import RenderTrace


class TestTracedCanvas:
    """Tests for TracedCanvas wrapper."""

    def test_creation(self):
        """Test creating a TracedCanvas."""
        canvas = Canvas(10, 10)
        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        assert traced.width == 10
        assert traced.height == 10

    def test_set_records_placement(self):
        """Test that set() records placements."""
        canvas = Canvas(10, 10)
        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set(5, 5, "X", reason="test_reason")

        assert len(trace.character_placements) == 1
        p = trace.character_placements[0]
        assert p.x == 5
        assert p.y == 5
        assert p.char == "X"
        assert p.reason == "test_reason"

    def test_set_records_previous_char(self):
        """Test that set() records the previous character."""
        canvas = Canvas(10, 10)
        canvas.set(5, 5, "A")  # Pre-set a character

        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set(5, 5, "B", reason="overwrite")

        p = trace.character_placements[0]
        assert p.previous_char == "A"
        assert p.char == "B"

    def test_set_source_context(self):
        """Test that source context is recorded."""
        canvas = Canvas(10, 10)
        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set_source("MyModule.my_method")
        traced.set(5, 5, "X", reason="test")

        p = trace.character_placements[0]
        assert p.source == "MyModule.my_method"

    def test_get_returns_character(self):
        """Test that get() returns correct character."""
        canvas = Canvas(10, 10)
        canvas.set(5, 5, "Z")

        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        assert traced.get(5, 5) == "Z"
        assert traced.get(0, 0) == " "

    def test_draw_text_records_placements(self):
        """Test that draw_text records each character."""
        canvas = Canvas(20, 10)
        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.draw_text(0, 0, "Hello")

        assert len(trace.character_placements) == 5
        chars = [p.char for p in trace.character_placements]
        assert chars == ["H", "e", "l", "l", "o"]

    def test_render_returns_string(self):
        """Test that render() returns the canvas as string."""
        canvas = Canvas(5, 2)
        canvas.set(0, 0, "X")

        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        result = traced.render()
        assert "X" in result

    def test_infer_reason_vertical(self):
        """Test reason inference for vertical line."""
        canvas = Canvas(10, 10)
        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set(5, 5, "│")  # No explicit reason

        p = trace.character_placements[0]
        assert p.reason == "vertical_line"

    def test_infer_reason_horizontal(self):
        """Test reason inference for horizontal line."""
        canvas = Canvas(10, 10)
        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set(5, 5, "─")

        p = trace.character_placements[0]
        assert p.reason == "horizontal_line"

    def test_infer_reason_corners(self):
        """Test reason inference for corners."""
        canvas = Canvas(10, 10)
        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set(0, 0, "┌")
        traced.set(1, 0, "┐")
        traced.set(0, 1, "└")
        traced.set(1, 1, "┘")

        reasons = [p.reason for p in trace.character_placements]
        assert "corner_top_left" in reasons
        assert "corner_top_right" in reasons
        assert "corner_bottom_left" in reasons
        assert "corner_bottom_right" in reasons

    def test_infer_reason_tee(self):
        """Test reason inference for tees."""
        canvas = Canvas(10, 10)
        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set(5, 5, "├")

        p = trace.character_placements[0]
        assert p.reason == "tee"

    def test_infer_reason_tee_upgrade(self):
        """Test reason inference for tee upgrade."""
        canvas = Canvas(10, 10)
        canvas.set(5, 5, "│")  # Pre-existing vertical

        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set(5, 5, "├")  # Upgrade to tee

        p = trace.character_placements[0]
        assert p.reason == "upgrade_to_tee"

    def test_infer_reason_cross(self):
        """Test reason inference for cross."""
        canvas = Canvas(10, 10)
        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set(5, 5, "┼")

        p = trace.character_placements[0]
        assert p.reason == "cross"

    def test_infer_reason_cross_upgrade(self):
        """Test reason inference for cross upgrade."""
        canvas = Canvas(10, 10)
        canvas.set(5, 5, "│")

        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set(5, 5, "┼")

        p = trace.character_placements[0]
        assert p.reason == "upgrade_to_cross"

    def test_infer_reason_arrow(self):
        """Test reason inference for arrows."""
        canvas = Canvas(10, 10)
        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set(5, 5, "▼")

        p = trace.character_placements[0]
        assert p.reason == "arrow"

    def test_infer_reason_shadow(self):
        """Test reason inference for shadow."""
        canvas = Canvas(10, 10)
        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set(5, 5, "░")

        p = trace.character_placements[0]
        assert p.reason == "shadow"

    def test_infer_reason_default(self):
        """Test default reason for unknown characters."""
        canvas = Canvas(10, 10)
        trace = RenderTrace()
        traced = TracedCanvas(canvas, trace)

        traced.set(5, 5, "Q")  # Random character

        p = trace.character_placements[0]
        assert p.reason == "char_placement"


class TestVisualDiff:
    """Tests for visual_diff function."""

    def test_identical_strings(self):
        """Test diff with identical strings."""
        text = "┌───┐\n│ A │\n└───┘"
        result = visual_diff(text, text)
        assert "No differences found" in result

    def test_single_character_diff(self):
        """Test diff with single character difference."""
        expected = "┌───┐\n│ A │\n└───┘"
        actual = "┌───┐\n│ B │\n└───┘"

        result = visual_diff(expected, actual)

        assert "VISUAL DIFF" in result
        assert "1 differing line" in result
        # Output uses "E" for expected and "A" for actual
        assert " E |" in result
        assert " A |" in result

    def test_multiple_line_diff(self):
        """Test diff with multiple line differences."""
        expected = "Line1\nLine2\nLine3"
        actual = "Line1\nDiff2\nDiff3"

        result = visual_diff(expected, actual)
        assert "2 differing line" in result

    def test_diff_shows_column_positions(self):
        """Test that diff shows column positions of differences."""
        expected = "AAAA"
        actual = "ABAA"

        result = visual_diff(expected, actual)
        assert "col" in result.lower()

    def test_diff_with_different_lengths(self):
        """Test diff with different length strings."""
        expected = "Short"
        actual = "Longer text here"

        result = visual_diff(expected, actual)
        assert "VISUAL DIFF" in result

    def test_context_lines(self):
        """Test that context lines are shown."""
        expected = "Line1\nLine2\nLine3\nLine4\nLine5"
        actual = "Line1\nLine2\nDIFF3\nLine4\nLine5"

        result = visual_diff(expected, actual, context_lines=1)
        # Should show Line2, DIFF3, and Line4
        assert "Line2" in result or "2:" in result


class TestCanvasInspector:
    """Tests for CanvasInspector class."""

    def test_creation(self):
        """Test creating a CanvasInspector."""
        canvas = Canvas(10, 10)
        inspector = CanvasInspector(canvas)
        assert inspector is not None

    def test_find_char(self):
        """Test finding all positions of a character."""
        canvas = Canvas(10, 10)
        canvas.set(0, 0, "X")
        canvas.set(5, 5, "X")
        canvas.set(9, 9, "X")

        inspector = CanvasInspector(canvas)
        positions = inspector.find_char("X")

        assert len(positions) == 3
        assert (0, 0) in positions
        assert (5, 5) in positions
        assert (9, 9) in positions

    def test_find_char_not_found(self):
        """Test finding character that doesn't exist."""
        canvas = Canvas(10, 10)
        inspector = CanvasInspector(canvas)

        positions = inspector.find_char("Z")
        assert len(positions) == 0

    def test_find_chars_multiple(self):
        """Test finding multiple character types."""
        canvas = Canvas(10, 10)
        canvas.set(0, 0, "┌")
        canvas.set(5, 0, "┐")
        canvas.set(0, 5, "└")
        canvas.set(5, 5, "┘")

        inspector = CanvasInspector(canvas)
        positions = inspector.find_chars("┌┐└┘")

        assert len(positions) == 4
        # Returns tuples of (x, y, char)
        chars = [p[2] for p in positions]
        assert "┌" in chars
        assert "┐" in chars
        assert "└" in chars
        assert "┘" in chars

    def test_get_row(self):
        """Test getting a single row."""
        canvas = Canvas(5, 3)
        canvas.draw_text(0, 1, "Hello")

        inspector = CanvasInspector(canvas)
        row = inspector.get_row(1)

        assert "Hello" in row

    def test_get_row_out_of_bounds(self):
        """Test getting row out of bounds."""
        canvas = Canvas(5, 3)
        inspector = CanvasInspector(canvas)

        row = inspector.get_row(100)
        assert row == ""

    def test_get_column(self):
        """Test getting a single column."""
        canvas = Canvas(5, 5)
        canvas.set(2, 0, "A")
        canvas.set(2, 1, "B")
        canvas.set(2, 2, "C")

        inspector = CanvasInspector(canvas)
        col = inspector.get_column(2)

        assert "ABC" in col

    def test_get_column_out_of_bounds(self):
        """Test getting column out of bounds."""
        canvas = Canvas(5, 5)
        inspector = CanvasInspector(canvas)

        col = inspector.get_column(100)
        assert col == ""

    def test_get_region(self):
        """Test getting a rectangular region."""
        canvas = Canvas(10, 10)
        canvas.set(2, 2, "A")
        canvas.set(3, 2, "B")
        canvas.set(2, 3, "C")
        canvas.set(3, 3, "D")

        inspector = CanvasInspector(canvas)
        region = inspector.get_region(2, 2, 2, 2)

        assert "AB" in region
        assert "CD" in region

    def test_count_char(self):
        """Test counting character occurrences."""
        canvas = Canvas(10, 10)
        canvas.set(0, 0, "│")
        canvas.set(0, 1, "│")
        canvas.set(0, 2, "│")

        inspector = CanvasInspector(canvas)
        count = inspector.count_char("│")

        assert count == 3

    def test_get_line_chars_count(self):
        """Test counting all line-drawing characters."""
        canvas = Canvas(10, 10)
        canvas.set(0, 0, "┌")
        canvas.set(1, 0, "─")
        canvas.set(2, 0, "┐")
        canvas.set(0, 1, "│")
        canvas.set(2, 1, "│")
        canvas.set(1, 2, "▼")

        inspector = CanvasInspector(canvas)
        counts = inspector.get_line_chars_count()

        assert counts["┌"] == 1
        assert counts["─"] == 1
        assert counts["┐"] == 1
        assert counts["│"] == 2
        assert counts["▼"] == 1


class TestDebugIntegration:
    """Integration tests for debug utilities with FlowchartGenerator."""

    def test_traced_canvas_in_generator(self):
        """Test that TracedCanvas works with FlowchartGenerator."""
        from retroflow import FlowchartGenerator

        gen = FlowchartGenerator()
        gen.generate("A -> B", debug=True)

        trace = gen.get_trace()

        # Should have recorded character placements
        assert len(trace.character_placements) > 0

        # Check for expected character types
        chars = [p.char for p in trace.character_placements]
        assert any(c in "│─┌┐└┘" for c in chars)

    def test_canvas_inspector_on_generated_flowchart(self):
        """Test CanvasInspector on a generated flowchart."""
        from retroflow import FlowchartGenerator

        gen = FlowchartGenerator()
        # Use separate lines for each connection
        result = gen.generate("A -> B\nB -> C", debug=True)

        # Create a canvas and populate it with the result
        lines = result.split("\n")
        width = max(len(line) for line in lines) if lines else 1
        height = len(lines)

        canvas = Canvas(width + 1, height + 1)
        for y, line in enumerate(lines):
            for x, char in enumerate(line):
                canvas.set(x, y, char)

        inspector = CanvasInspector(canvas)

        # Should find arrows
        arrows = inspector.find_char("▼")
        assert len(arrows) >= 2  # A->B and B->C
