"""Unit tests for the graph module."""

from retroflow import Graph, create_graph


class TestGraph:
    """Tests for the Graph class."""

    def test_add_edge(self):
        """Add an edge to the graph."""
        graph = Graph()
        graph.add_edge("A", "B")
        assert "A" in graph.nodes
        assert "B" in graph.nodes
        assert ("A", "B") in graph.edges

    def test_get_nodes(self):
        """Get all nodes from graph."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        nodes = graph.get_nodes()
        assert set(nodes) == {"A", "B", "C"}

    def test_get_edges(self):
        """Get all edges from graph."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        edges = graph.get_edges()
        assert edges == [("A", "B"), ("B", "C")]

    def test_get_successors(self):
        """Get successor nodes."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("A", "C")
        successors = graph.get_successors("A")
        assert set(successors) == {"B", "C"}

    def test_get_successors_empty(self):
        """Get successors for leaf node."""
        graph = Graph()
        graph.add_edge("A", "B")
        successors = graph.get_successors("B")
        assert successors == []

    def test_get_predecessors(self):
        """Get predecessor nodes."""
        graph = Graph()
        graph.add_edge("A", "C")
        graph.add_edge("B", "C")
        predecessors = graph.get_predecessors("C")
        assert set(predecessors) == {"A", "B"}

    def test_get_predecessors_empty(self):
        """Get predecessors for root node."""
        graph = Graph()
        graph.add_edge("A", "B")
        predecessors = graph.get_predecessors("A")
        assert predecessors == []

    def test_get_roots(self):
        """Get root nodes (no incoming edges)."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        roots = graph.get_roots()
        assert roots == ["A"]

    def test_get_roots_multiple(self):
        """Get multiple root nodes."""
        graph = Graph()
        graph.add_edge("A", "C")
        graph.add_edge("B", "C")
        roots = graph.get_roots()
        assert set(roots) == {"A", "B"}

    def test_get_leaves(self):
        """Get leaf nodes (no outgoing edges)."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        leaves = graph.get_leaves()
        assert leaves == ["C"]

    def test_get_leaves_multiple(self):
        """Get multiple leaf nodes."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("A", "C")
        leaves = graph.get_leaves()
        assert set(leaves) == {"B", "C"}

    def test_has_cycle_false(self):
        """Detect no cycle in acyclic graph."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        assert graph.has_cycle() is False

    def test_has_cycle_true(self):
        """Detect cycle in cyclic graph."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        graph.add_edge("C", "A")
        assert graph.has_cycle() is True

    def test_has_cycle_self_loop(self):
        """Detect self-loop as cycle."""
        graph = Graph()
        graph.add_edge("A", "A")
        assert graph.has_cycle() is True

    def test_find_feedback_edges(self):
        """Find edges causing cycles."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        graph.add_edge("C", "A")
        feedback = graph.find_feedback_edges()
        # At least one feedback edge should be found to break the cycle
        assert len(feedback) >= 1
        # The feedback edge should be one of the cycle edges
        assert feedback[0] in [("A", "B"), ("B", "C"), ("C", "A")]

    def test_topological_sort_simple(self):
        """Topological sort of simple graph."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        order = graph.topological_sort()
        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")

    def test_topological_sort_branching(self):
        """Topological sort with branching."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("A", "C")
        graph.add_edge("B", "D")
        graph.add_edge("C", "D")
        order = graph.topological_sort()
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

    def test_get_longest_path_length(self):
        """Calculate longest path length."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        graph.add_edge("C", "D")
        assert graph.get_longest_path_length() == 3

    def test_get_longest_path_length_branching(self):
        """Longest path with branching."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("A", "C")
        graph.add_edge("B", "D")
        assert graph.get_longest_path_length() == 2

    def test_get_longest_path_length_empty(self):
        """Longest path in empty graph."""
        graph = Graph()
        assert graph.get_longest_path_length() == 0

    def test_get_max_width(self):
        """Calculate maximum width."""
        graph = Graph()
        graph.add_edge("A", "B")
        graph.add_edge("A", "C")
        graph.add_edge("A", "D")
        assert graph.get_max_width() == 3

    def test_get_max_width_empty(self):
        """Max width of empty graph."""
        graph = Graph()
        assert graph.get_max_width() == 0


class TestCreateGraphFunction:
    """Tests for the create_graph convenience function."""

    def test_create_graph_simple(self):
        """Create graph from connections."""
        connections = [("A", "B"), ("B", "C")]
        graph = create_graph(connections)
        assert set(graph.nodes) == {"A", "B", "C"}
        assert graph.edges == [("A", "B"), ("B", "C")]

    def test_create_graph_empty(self):
        """Create empty graph."""
        graph = create_graph([])
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
