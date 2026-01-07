"""Additional tests to improve code coverage."""

from retroflow import FlowchartGenerator
from retroflow.layout import NetworkXLayout
from retroflow.renderer import ARROW_CHARS, LINE_CHARS, Canvas, LineRenderer


class TestLayoutEdgeCases:
    """Additional tests for layout edge cases."""

    def test_layout_empty_result_handling(self):
        """Test layout handles edge cases in layer assignment."""
        layout = NetworkXLayout()

        # Graph with nodes that all have predecessors (fully connected cycle)
        connections = [("A", "B"), ("B", "A")]
        result = layout.layout(connections)

        assert len(result.nodes) == 2
        assert result.has_cycles is True

    def test_layout_exception_in_cycle_detection(self):
        """Test layout handles cycle detection gracefully."""
        layout = NetworkXLayout()

        # Simple graph that shouldn't cause issues
        connections = [("A", "B"), ("B", "C")]
        result = layout.layout(connections)

        assert len(result.nodes) == 3
        assert result.has_cycles is False


class TestLineRendererEdgeCases:
    """Additional tests for LineRenderer edge cases."""

    def test_vertical_line_overwrites_corner_top_left(self):
        """Test vertical line handling when crossing corner_top_left."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        # Set a corner first
        canvas.set(5, 5, LINE_CHARS["corner_top_left"])

        # Draw vertical line through it
        lr.draw_vertical_line(canvas, 5, 4, 7, arrow_at_end=False)

        # Should become tee_right
        assert canvas.get(5, 5) == LINE_CHARS["tee_right"]

    def test_vertical_line_overwrites_corner_top_right(self):
        """Test vertical line handling when crossing corner_top_right."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, LINE_CHARS["corner_top_right"])
        lr.draw_vertical_line(canvas, 5, 4, 7, arrow_at_end=False)

        assert canvas.get(5, 5) == LINE_CHARS["tee_left"]

    def test_vertical_line_overwrites_corner_bottom_left(self):
        """Test vertical line handling when crossing corner_bottom_left."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, LINE_CHARS["corner_bottom_left"])
        lr.draw_vertical_line(canvas, 5, 4, 7, arrow_at_end=False)

        assert canvas.get(5, 5) == LINE_CHARS["tee_right"]

    def test_vertical_line_overwrites_corner_bottom_right(self):
        """Test vertical line handling when crossing corner_bottom_right."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, LINE_CHARS["corner_bottom_right"])
        lr.draw_vertical_line(canvas, 5, 4, 7, arrow_at_end=False)

        assert canvas.get(5, 5) == LINE_CHARS["tee_left"]

    def test_vertical_line_preserves_down_arrow(self):
        """Test vertical line doesn't overwrite existing down arrow."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, ARROW_CHARS["down"])
        lr.draw_vertical_line(canvas, 5, 4, 7, arrow_at_end=False)

        # Arrow should be preserved
        assert canvas.get(5, 5) == ARROW_CHARS["down"]

    def test_vertical_line_preserves_up_arrow(self):
        """Test vertical line doesn't overwrite existing up arrow."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, ARROW_CHARS["up"])
        lr.draw_vertical_line(canvas, 5, 4, 7, arrow_at_end=False)

        assert canvas.get(5, 5) == ARROW_CHARS["up"]

    def test_horizontal_line_overwrites_corner_top_left(self):
        """Test horizontal line handling when crossing corner_top_left."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, LINE_CHARS["corner_top_left"])
        lr.draw_horizontal_line(canvas, 4, 7, 5, arrow_at_end=False)

        assert canvas.get(5, 5) == LINE_CHARS["tee_down"]

    def test_horizontal_line_overwrites_corner_top_right(self):
        """Test horizontal line handling when crossing corner_top_right."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, LINE_CHARS["corner_top_right"])
        lr.draw_horizontal_line(canvas, 4, 7, 5, arrow_at_end=False)

        assert canvas.get(5, 5) == LINE_CHARS["tee_down"]

    def test_horizontal_line_overwrites_corner_bottom_left(self):
        """Test horizontal line handling when crossing corner_bottom_left."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, LINE_CHARS["corner_bottom_left"])
        lr.draw_horizontal_line(canvas, 4, 7, 5, arrow_at_end=False)

        assert canvas.get(5, 5) == LINE_CHARS["tee_up"]

    def test_horizontal_line_overwrites_corner_bottom_right(self):
        """Test horizontal line handling when crossing corner_bottom_right."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, LINE_CHARS["corner_bottom_right"])
        lr.draw_horizontal_line(canvas, 4, 7, 5, arrow_at_end=False)

        assert canvas.get(5, 5) == LINE_CHARS["tee_up"]

    def test_horizontal_line_preserves_left_arrow(self):
        """Test horizontal line doesn't overwrite existing left arrow."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, ARROW_CHARS["left"])
        lr.draw_horizontal_line(canvas, 4, 7, 5, arrow_at_end=False)

        assert canvas.get(5, 5) == ARROW_CHARS["left"]

    def test_horizontal_line_preserves_right_arrow(self):
        """Test horizontal line doesn't overwrite existing right arrow."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, ARROW_CHARS["right"])
        lr.draw_horizontal_line(canvas, 4, 7, 5, arrow_at_end=False)

        assert canvas.get(5, 5) == ARROW_CHARS["right"]

    def test_corner_on_existing_corner_becomes_cross(self):
        """Test drawing corner on existing corner becomes cross."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        # Draw first corner
        canvas.set(5, 5, LINE_CHARS["corner_top_left"])

        # Drawing any corner should result in cross
        lr.draw_corner(canvas, 5, 5, "bottom_right")

        assert canvas.get(5, 5) == LINE_CHARS["cross"]

    def test_corner_bottom_on_horizontal(self):
        """Test bottom corners on horizontal line."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, LINE_CHARS["horizontal"])
        lr.draw_corner(canvas, 5, 5, "bottom_left")

        assert canvas.get(5, 5) == LINE_CHARS["tee_up"]

    def test_corner_right_on_vertical(self):
        """Test right corners on vertical line."""
        canvas = Canvas(20, 20)
        lr = LineRenderer()

        canvas.set(5, 5, LINE_CHARS["vertical"])
        lr.draw_corner(canvas, 5, 5, "top_right")

        assert canvas.get(5, 5) == LINE_CHARS["tee_left"]


class TestGeneratorEdgeRouting:
    """Tests for edge cases in generator's edge routing."""

    def test_generator_horizontal_routing(self):
        """Test generator handles horizontal edge routing."""
        gen = FlowchartGenerator()

        # Diamond pattern forces horizontal routing
        input_text = """
        A -> B
        A -> C
        B -> D
        C -> D
        """
        result = gen.generate(input_text)

        assert "A" in result
        assert "D" in result
        # Should render properly regardless of routing details
        assert len(result) > 0

    def test_generator_multiple_back_edges(self):
        """Test generator handles multiple back edges."""
        gen = FlowchartGenerator()

        input_text = """
        A -> B
        B -> C
        C -> D
        D -> B
        D -> A
        """
        result = gen.generate(input_text)

        assert "A" in result
        assert "D" in result
        # Should render all nodes
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_generator_deep_back_edge(self):
        """Test generator handles back edge spanning many layers."""
        gen = FlowchartGenerator()

        input_text = """
        A -> B
        B -> C
        C -> D
        D -> E
        E -> A
        """
        result = gen.generate(input_text)

        for node in ["A", "B", "C", "D", "E"]:
            assert node in result


class TestRouterEdgeCases:
    """Additional tests for router edge cases."""

    def test_waypoints_upward_same_x(self):
        """Test waypoints for upward edge with same x."""
        from retroflow.router import BoxInfo, EdgeRouter

        router = EdgeRouter()
        boxes = {
            "A": BoxInfo(name="A", x=10, y=0, width=10, height=5, layer=0, position=0),
            "B": BoxInfo(name="B", x=10, y=20, width=10, height=5, layer=1, position=0),
        }
        router.set_boxes(boxes)

        edges = [("B", "A")]  # Upward edge
        layers = [["A"], ["B"]]

        routes = router.route_edges(edges, layers)

        assert len(routes) == 1
        route = routes[0]
        # Upward edge, should have 2 waypoints for direct path
        assert len(route.waypoints) == 2

    def test_waypoints_upward_different_x(self):
        """Test waypoints for upward edge with different x."""
        from retroflow.router import BoxInfo, EdgeRouter

        router = EdgeRouter()
        boxes = {
            "A": BoxInfo(name="A", x=0, y=0, width=10, height=5, layer=0, position=0),
            "B": BoxInfo(name="B", x=30, y=20, width=10, height=5, layer=1, position=0),
        }
        router.set_boxes(boxes)

        edges = [("B", "A")]  # Upward edge
        layers = [["A"], ["B"]]

        routes = router.route_edges(edges, layers)

        assert len(routes) == 1
        route = routes[0]
        # Upward edge with different x needs more waypoints
        assert len(route.waypoints) >= 4


class TestLayoutSpecialCases:
    """Tests for special layout cases."""

    def test_layout_single_node(self):
        """Test layout with single isolated node."""
        layout = NetworkXLayout()
        # Self loop creates single node scenario
        connections = [("A", "A")]
        result = layout.layout(connections)

        assert len(result.nodes) == 1
        assert "A" in result.nodes

    def test_layout_two_node_bidirectional(self):
        """Test layout with bidirectional connection."""
        layout = NetworkXLayout()
        connections = [("A", "B"), ("B", "A")]
        result = layout.layout(connections)

        assert len(result.nodes) == 2
        assert result.has_cycles is True
        assert len(result.back_edges) >= 1
