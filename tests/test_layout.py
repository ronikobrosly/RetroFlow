"""Unit tests for the layout module."""

from retroflow import Graph, LayoutAlgorithm, SimpleLayout, compute_layout, create_graph


class TestLayoutAlgorithm:
    """Tests for the LayoutAlgorithm class."""

    def test_compute_layout_simple(self, simple_graph):
        """Compute layout for simple linear graph."""
        layout = LayoutAlgorithm(simple_graph)
        positions = layout.compute_layout()
        assert len(positions) == 4
        assert all(node in positions for node in ["A", "B", "C", "D"])

    def test_compute_layout_positions_valid(self, simple_graph):
        """Layout positions are tuples of integers."""
        layout = LayoutAlgorithm(simple_graph)
        positions = layout.compute_layout()
        for node, pos in positions.items():
            assert isinstance(pos, tuple)
            assert len(pos) == 2
            assert isinstance(pos[0], int)
            assert isinstance(pos[1], int)

    def test_compute_layout_layered(self, simple_graph):
        """Linear graph has sequential layers."""
        layout = LayoutAlgorithm(simple_graph)
        positions = layout.compute_layout()
        # In a linear graph A->B->C->D, each should be in a different layer
        layers = [positions[n][1] for n in ["A", "B", "C", "D"]]
        # Each subsequent node should be in same or later layer
        for i in range(len(layers) - 1):
            assert layers[i] <= layers[i + 1]

    def test_compute_layout_branching(self, branching_graph):
        """Branching graph layout."""
        layout = LayoutAlgorithm(branching_graph)
        positions = layout.compute_layout()
        # Start should be at top (layer 0)
        assert positions["Start"][1] == 0
        # Process1 and Process2 should be at same layer
        assert positions["Process1"][1] == positions["Process2"][1]

    def test_get_layout_dimensions(self, simple_graph):
        """Get layout dimensions."""
        layout = LayoutAlgorithm(simple_graph)
        layout.compute_layout()
        width, height = layout.get_layout_dimensions()
        assert width >= 1
        assert height >= 1

    def test_get_edges_for_rendering(self, simple_graph):
        """Get edges with feedback information."""
        layout = LayoutAlgorithm(simple_graph)
        layout.compute_layout()
        edges = layout.get_edges_for_rendering()
        assert len(edges) == 3
        for source, target, is_feedback in edges:
            assert isinstance(is_feedback, bool)
            # Simple linear graph has no feedback edges
            assert is_feedback is False

    def test_handles_cycles(self):
        """Layout handles cyclic graphs."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        graph.add_edge("C", "A")
        layout = LayoutAlgorithm(graph)
        positions = layout.compute_layout()
        assert len(positions) == 3

    def test_feedback_edges_identified(self):
        """Feedback edges are correctly identified."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        graph.add_edge("C", "A")
        layout = LayoutAlgorithm(graph)
        layout.compute_layout()
        edges = layout.get_edges_for_rendering()
        feedback_edges = [e for e in edges if e[2] is True]
        assert len(feedback_edges) == 1


class TestSimpleLayout:
    """Tests for the SimpleLayout class."""

    def test_compute_layout(self, simple_graph):
        """Simple layout computes positions."""
        layout = SimpleLayout(simple_graph)
        positions = layout.compute_layout()
        assert len(positions) == 4

    def test_vertical_arrangement(self, simple_graph):
        """Simple layout arranges vertically."""
        layout = SimpleLayout(simple_graph)
        positions = layout.compute_layout()
        # All nodes should have x=0 (single column)
        for pos in positions.values():
            assert pos[0] == 0

    def test_get_layout_dimensions(self, simple_graph):
        """Get simple layout dimensions."""
        layout = SimpleLayout(simple_graph)
        layout.compute_layout()
        width, height = layout.get_layout_dimensions()
        assert width == 1
        assert height == 4

    def test_get_edges_for_rendering(self, simple_graph):
        """Simple layout provides edges."""
        layout = SimpleLayout(simple_graph)
        layout.compute_layout()
        edges = layout.get_edges_for_rendering()
        assert len(edges) == 3
        # Simple layout marks no edges as feedback
        for _, _, is_feedback in edges:
            assert is_feedback is False


class TestComputeLayoutFunction:
    """Tests for the compute_layout convenience function."""

    def test_compute_layout_default(self, simple_graph):
        """Default algorithm for larger graphs."""
        layout = compute_layout(simple_graph)
        assert hasattr(layout, "positions")
        assert len(layout.positions) == 4

    def test_compute_layout_simple_algorithm(self, simple_graph):
        """Explicitly use simple algorithm."""
        layout = compute_layout(simple_graph, algorithm="simple")
        assert isinstance(layout, SimpleLayout)

    def test_compute_layout_layered_algorithm(self, simple_graph):
        """Explicitly use layered algorithm."""
        layout = compute_layout(simple_graph, algorithm="layered")
        assert isinstance(layout, LayoutAlgorithm)

    def test_compute_layout_small_graph_uses_simple(self):
        """Small graphs (<=3 nodes) use simple layout."""
        graph = create_graph([("A", "B"), ("B", "C")])
        layout = compute_layout(graph)
        assert isinstance(layout, SimpleLayout)

    def test_compute_layout_with_spacing(self, simple_graph):
        """Layout accepts spacing parameters."""
        layout = compute_layout(
            simple_graph,
            algorithm="layered",
            horizontal_spacing=10,
            vertical_spacing=5,
        )
        assert layout.horizontal_spacing == 10
        assert layout.vertical_spacing == 5
