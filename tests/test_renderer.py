"""Unit tests for the renderer module."""

from retroflow import (
    ASCIICanvas,
    FlowchartRenderer,
    compute_layout,
    create_graph,
    render_flowchart,
)


class TestASCIICanvas:
    """Tests for the ASCIICanvas class."""

    def test_create_canvas(self):
        """Create canvas with dimensions."""
        canvas = ASCIICanvas(80, 24)
        assert canvas.width == 80
        assert canvas.height == 24

    def test_set_char(self):
        """Set character at position."""
        canvas = ASCIICanvas(10, 10)
        canvas.set_char(5, 5, "X")
        assert canvas.get_char(5, 5) == "X"

    def test_set_char_out_of_bounds(self):
        """Setting char out of bounds is safe."""
        canvas = ASCIICanvas(10, 10)
        canvas.set_char(100, 100, "X")  # Should not raise
        canvas.set_char(-1, -1, "X")  # Should not raise

    def test_get_char_default(self):
        """Default character is space."""
        canvas = ASCIICanvas(10, 10)
        assert canvas.get_char(5, 5) == " "

    def test_get_char_out_of_bounds(self):
        """Getting char out of bounds returns space."""
        canvas = ASCIICanvas(10, 10)
        assert canvas.get_char(100, 100) == " "

    def test_draw_box(self):
        """Draw a box on canvas."""
        canvas = ASCIICanvas(20, 10)
        canvas.draw_box(2, 2, 8, 3, "Test")
        result = canvas.to_string()
        assert "┌" in result
        assert "┐" in result
        assert "└" in result
        assert "┘" in result
        assert "Test" in result

    def test_draw_box_with_shadow(self):
        """Box includes shadow."""
        canvas = ASCIICanvas(20, 10)
        canvas.draw_box(2, 2, 8, 3, "Test")
        result = canvas.to_string()
        assert "░" in result

    def test_draw_line_vertical(self):
        """Draw vertical line."""
        canvas = ASCIICanvas(10, 10)
        canvas.draw_line(5, 2, 5, 7)
        for y in range(2, 8):
            assert canvas.get_char(5, y) == "│"

    def test_draw_line_horizontal(self):
        """Draw horizontal line."""
        canvas = ASCIICanvas(10, 10)
        canvas.draw_line(2, 5, 7, 5)
        for x in range(2, 8):
            assert canvas.get_char(x, 5) == "─"

    def test_draw_arrow_down(self):
        """Draw downward arrow."""
        canvas = ASCIICanvas(10, 10)
        canvas.draw_arrow_down(5, 5)
        assert canvas.get_char(5, 5) == "▼"

    def test_draw_arrow_up(self):
        """Draw upward arrow."""
        canvas = ASCIICanvas(10, 10)
        canvas.draw_arrow_up(5, 5)
        assert canvas.get_char(5, 5) == "▲"

    def test_to_string(self):
        """Convert canvas to string."""
        canvas = ASCIICanvas(10, 5)
        canvas.set_char(0, 0, "A")
        canvas.set_char(9, 4, "B")
        result = canvas.to_string()
        assert isinstance(result, str)
        assert "A" in result

    def test_to_string_trims_whitespace(self):
        """Canvas string trims trailing whitespace."""
        canvas = ASCIICanvas(20, 10)
        canvas.set_char(5, 5, "X")
        result = canvas.to_string()
        lines = result.split("\n")
        for line in lines:
            assert line == line.rstrip()


class TestFlowchartRenderer:
    """Tests for the FlowchartRenderer class."""

    def test_create_renderer(self):
        """Create renderer with default settings."""
        renderer = FlowchartRenderer()
        assert renderer.box_width == 11
        assert renderer.box_height == 3

    def test_create_renderer_custom(self):
        """Create renderer with custom settings."""
        renderer = FlowchartRenderer(
            box_width=15, box_height=5, horizontal_spacing=6, vertical_spacing=4
        )
        assert renderer.box_width == 15
        assert renderer.box_height == 5

    def test_render_simple(self, simple_graph):
        """Render simple graph."""
        layout = compute_layout(simple_graph, algorithm="layered")
        renderer = FlowchartRenderer()
        result = renderer.render(simple_graph, layout)
        assert isinstance(result, str)
        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "D" in result

    def test_render_contains_boxes(self, simple_graph):
        """Rendered output contains box characters."""
        layout = compute_layout(simple_graph, algorithm="layered")
        renderer = FlowchartRenderer()
        result = renderer.render(simple_graph, layout)
        assert "┌" in result
        assert "┘" in result

    def test_render_contains_arrows(self, simple_graph):
        """Rendered output contains arrow characters."""
        layout = compute_layout(simple_graph, algorithm="layered")
        renderer = FlowchartRenderer()
        result = renderer.render(simple_graph, layout)
        # Should have vertical lines or arrows
        assert "│" in result or "▼" in result

    def test_render_empty_graph(self):
        """Render empty graph."""
        graph = create_graph([])
        layout = compute_layout(graph)
        renderer = FlowchartRenderer()
        result = renderer.render(graph, layout)
        assert "Empty graph" in result


class TestRenderFlowchartFunction:
    """Tests for the render_flowchart convenience function."""

    def test_render_flowchart(self, simple_graph):
        """Convenience function renders correctly."""
        layout = compute_layout(simple_graph)
        result = render_flowchart(simple_graph, layout)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_flowchart_with_options(self, simple_graph):
        """Convenience function accepts options."""
        layout = compute_layout(simple_graph)
        result = render_flowchart(simple_graph, layout, box_width=15, box_height=5)
        assert isinstance(result, str)
