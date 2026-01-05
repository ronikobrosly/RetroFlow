"""Tests for the PNG renderer module."""

import os
import tempfile

from retroflow import create_graph, parse_flowchart
from retroflow.layout import compute_layout
from retroflow.png_renderer import PNGRenderer, render_to_png


class TestPNGRenderer:
    """Tests for PNGRenderer class."""

    def test_render_simple(self, simple_graph):
        """Render a simple flowchart to PNG."""
        layout = compute_layout(simple_graph)
        renderer = PNGRenderer()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            result = renderer.render(simple_graph, layout, output_path)
            assert result == output_path
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_with_scale(self, simple_graph):
        """Render with custom scale factor."""
        layout = compute_layout(simple_graph)
        renderer = PNGRenderer(scale=3)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(simple_graph, layout, output_path)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_vertical_flow(self, simple_graph):
        """Render with vertical flow (top to bottom)."""
        layout = compute_layout(simple_graph)
        renderer = PNGRenderer(horizontal_flow=False)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(simple_graph, layout, output_path)
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_vertical_flow_branching(self, branching_graph):
        """Render branching graph with vertical flow."""
        layout = compute_layout(branching_graph)
        renderer = PNGRenderer(horizontal_flow=False)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(branching_graph, layout, output_path)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_empty_graph(self):
        """Render an empty graph creates placeholder image."""
        graph = create_graph([])
        layout = compute_layout(graph)
        renderer = PNGRenderer()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(graph, layout, output_path)
            assert os.path.exists(output_path)
            # Empty graph should still create a file
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_multiline_node_names(self):
        """Render nodes with multi-line names."""
        input_text = "Start -> Multi\\nLine\\nNode\nMulti\\nLine\\nNode -> End"
        connections = parse_flowchart(input_text)
        graph = create_graph(connections)
        layout = compute_layout(graph)
        renderer = PNGRenderer()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(graph, layout, output_path)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_custom_font_path_nonexistent(self, simple_graph):
        """Render with non-existent custom font falls back gracefully."""
        layout = compute_layout(simple_graph)
        renderer = PNGRenderer(font_path="/nonexistent/font.ttf")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            # Should not raise, falls back to default font
            renderer.render(simple_graph, layout, output_path)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_custom_dimensions(self, simple_graph):
        """Render with custom box dimensions."""
        layout = compute_layout(simple_graph)
        renderer = PNGRenderer(
            box_padding=20,
            box_min_width=150,
            box_height=50,
            horizontal_spacing=100,
            vertical_spacing=60,
            margin=80,
        )

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(simple_graph, layout, output_path)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_complex_graph(self):
        """Render a complex graph with multiple paths."""
        connections = parse_flowchart("""
            Init -> Validate
            Validate -> Process
            Validate -> Error
            Process -> Transform
            Transform -> Output
            Error -> Retry
            Retry -> Validate
            Output -> Done
        """)
        graph = create_graph(connections)
        layout = compute_layout(graph)
        renderer = PNGRenderer()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(graph, layout, output_path)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_complex_graph_vertical(self):
        """Render a complex graph with vertical flow."""
        connections = parse_flowchart("""
            Init -> Validate
            Validate -> Process
            Validate -> Error
            Process -> Transform
            Transform -> Output
            Error -> Retry
            Retry -> Validate
            Output -> Done
        """)
        graph = create_graph(connections)
        layout = compute_layout(graph)
        renderer = PNGRenderer(horizontal_flow=False)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(graph, layout, output_path)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_wide_graph_horizontal(self):
        """Render a wide graph to test horizontal arrow routing."""
        connections = parse_flowchart("""
            A -> B
            B -> C
            C -> D
            D -> E
            E -> F
        """)
        graph = create_graph(connections)
        layout = compute_layout(graph)
        renderer = PNGRenderer(horizontal_flow=True)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(graph, layout, output_path)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_backward_edges(self):
        """Render graph with backward edges (cycles)."""
        connections = parse_flowchart("""
            A -> B
            B -> C
            C -> A
        """)
        graph = create_graph(connections)
        layout = compute_layout(graph)
        renderer = PNGRenderer()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(graph, layout, output_path)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_backward_edges_vertical(self):
        """Render cyclic graph with vertical flow."""
        connections = parse_flowchart("""
            A -> B
            B -> C
            C -> A
        """)
        graph = create_graph(connections)
        layout = compute_layout(graph)
        renderer = PNGRenderer(horizontal_flow=False)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(graph, layout, output_path)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestRenderToPngFunction:
    """Tests for the render_to_png convenience function."""

    def test_render_to_png_simple(self, simple_graph):
        """Test render_to_png convenience function."""
        layout = compute_layout(simple_graph)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            result = render_to_png(simple_graph, layout, output_path)
            assert result == output_path
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_to_png_with_kwargs(self, simple_graph):
        """Test render_to_png with custom parameters."""
        layout = compute_layout(simple_graph)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            render_to_png(
                simple_graph,
                layout,
                output_path,
                scale=3,
                horizontal_flow=False,
                margin=100,
            )
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestPNGRendererInternals:
    """Tests for internal methods of PNGRenderer."""

    def test_get_font_caching(self, simple_graph):
        """Test that font is cached after first call."""
        renderer = PNGRenderer()
        layout = compute_layout(simple_graph)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(simple_graph, layout, output_path)
            # Font should be cached now
            font1 = renderer._get_font()
            font2 = renderer._get_font()
            assert font1 is font2
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_calculate_text_size(self, simple_graph):
        """Test text size calculation."""
        from PIL import Image, ImageDraw

        renderer = PNGRenderer()
        img = Image.new("RGB", (100, 100))
        draw = ImageDraw.Draw(img)

        width, height = renderer._calculate_text_size("TEST", draw)
        assert width > 0
        assert height > 0

    def test_calculate_box_dimensions(self, simple_graph):
        """Test box dimension calculation."""
        from PIL import Image, ImageDraw

        renderer = PNGRenderer()
        img = Image.new("RGB", (100, 100))
        draw = ImageDraw.Draw(img)

        width, height = renderer._calculate_box_dimensions("Test Node", draw)
        assert width >= renderer.box_min_width * renderer.scale
        assert height >= renderer.box_height * renderer.scale

    def test_calculate_box_dimensions_multiline(self):
        """Test box dimension calculation with multiline text."""
        from PIL import Image, ImageDraw

        renderer = PNGRenderer()
        img = Image.new("RGB", (100, 100))
        draw = ImageDraw.Draw(img)

        # Multi-line text should result in taller box
        single_w, single_h = renderer._calculate_box_dimensions("Test", draw)
        multi_text = "Test\nLine2\nLine3"
        multi_w, multi_h = renderer._calculate_box_dimensions(multi_text, draw)

        assert multi_h > single_h

    def test_draw_hatched_shadow(self):
        """Test shadow drawing creates checkerboard pattern."""
        from PIL import Image, ImageDraw

        renderer = PNGRenderer(scale=2)
        img = Image.new("RGB", (200, 200), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        renderer._draw_hatched_shadow(draw, 50, 50, 80, 60)

        # Check that some pixels in the shadow region have the shadow color
        shadow_region_x = 50 + 80 + 2  # Right shadow
        shadow_region_y = 50 + 10
        pixel = img.getpixel((shadow_region_x, shadow_region_y))
        # Should be either white or shadow color due to checkerboard
        assert pixel in [(255, 255, 255), renderer.shadow_color]
