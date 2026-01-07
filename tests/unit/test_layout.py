"""Unit tests for the layout module."""

from retroflow.layout import LayoutResult, NetworkXLayout, NodeLayout, SugiyamaLayout


class TestNodeLayout:
    """Tests for NodeLayout dataclass."""

    def test_node_layout_defaults(self):
        """Test NodeLayout default values."""
        node = NodeLayout(name="test")
        assert node.name == "test"
        assert node.layer == 0
        assert node.position == 0
        assert node.x == 0
        assert node.y == 0
        assert node.width == 0
        assert node.height == 0

    def test_node_layout_with_values(self):
        """Test NodeLayout with custom values."""
        node = NodeLayout(
            name="test", layer=2, position=1, x=10, y=20, width=15, height=5
        )
        assert node.name == "test"
        assert node.layer == 2
        assert node.position == 1
        assert node.x == 10
        assert node.y == 20
        assert node.width == 15
        assert node.height == 5


class TestLayoutResult:
    """Tests for LayoutResult dataclass."""

    def test_layout_result_defaults(self):
        """Test LayoutResult default values."""
        result = LayoutResult()
        assert result.nodes == {}
        assert result.layers == []
        assert result.edges == []
        assert result.back_edges == set()
        assert result.has_cycles is False

    def test_layout_result_with_values(self):
        """Test LayoutResult with custom values."""
        nodes = {"A": NodeLayout(name="A", layer=0)}
        layers = [["A"], ["B"]]
        edges = [("A", "B")]
        back_edges = {("B", "A")}

        result = LayoutResult(
            nodes=nodes,
            layers=layers,
            edges=edges,
            back_edges=back_edges,
            has_cycles=True,
        )
        assert result.nodes == nodes
        assert result.layers == layers
        assert result.edges == edges
        assert result.back_edges == back_edges
        assert result.has_cycles is True


class TestNetworkXLayout:
    """Tests for NetworkXLayout class."""

    def test_layout_simple_linear(self, layout_engine, simple_connections):
        """Test layout of simple linear graph."""
        result = layout_engine.layout(simple_connections)

        assert len(result.nodes) == 4
        assert "A" in result.nodes
        assert "B" in result.nodes
        assert "C" in result.nodes
        assert "D" in result.nodes
        assert result.has_cycles is False
        assert len(result.back_edges) == 0

    def test_layout_layer_assignment(self, layout_engine, simple_connections):
        """Test that nodes are assigned to correct layers."""
        result = layout_engine.layout(simple_connections)

        # In a linear A -> B -> C -> D, each should be in subsequent layers
        assert result.nodes["A"].layer == 0
        assert result.nodes["B"].layer == 1
        assert result.nodes["C"].layer == 2
        assert result.nodes["D"].layer == 3

    def test_layout_branching(self, layout_engine, branching_connections):
        """Test layout of branching graph."""
        result = layout_engine.layout(branching_connections)

        assert len(result.nodes) == 4
        assert result.has_cycles is False

        # Start should be in layer 0
        assert result.nodes["Start"].layer == 0

        # Process1 and Process2 should be in layer 1
        assert result.nodes["Process1"].layer == 1
        assert result.nodes["Process2"].layer == 1

        # End should be in layer 2
        assert result.nodes["End"].layer == 2

    def test_layout_with_cycle(self, layout_engine, cyclic_connections):
        """Test layout of cyclic graph."""
        result = layout_engine.layout(cyclic_connections)

        assert result.has_cycles is True
        assert len(result.back_edges) > 0
        assert len(result.nodes) == 3

    def test_layout_layers_list(self, layout_engine, simple_connections):
        """Test that layers list is populated correctly."""
        result = layout_engine.layout(simple_connections)

        assert len(result.layers) == 4
        assert result.layers[0] == ["A"]
        assert result.layers[1] == ["B"]
        assert result.layers[2] == ["C"]
        assert result.layers[3] == ["D"]

    def test_layout_edges_preserved(self, layout_engine, simple_connections):
        """Test that edges are preserved in result."""
        result = layout_engine.layout(simple_connections)

        assert len(result.edges) == len(simple_connections)
        for edge in simple_connections:
            assert edge in result.edges

    def test_layout_position_within_layer(self, layout_engine, branching_connections):
        """Test that positions within layers are assigned."""
        result = layout_engine.layout(branching_connections)

        # Process1 and Process2 should have different positions in layer 1
        pos1 = result.nodes["Process1"].position
        pos2 = result.nodes["Process2"].position
        assert pos1 != pos2 or (pos1 == 0 and pos2 == 1) or (pos1 == 1 and pos2 == 0)

    def test_layout_complex_graph(self, layout_engine):
        """Test layout of a more complex graph."""
        connections = [
            ("A", "B"),
            ("A", "C"),
            ("B", "D"),
            ("C", "D"),
            ("D", "E"),
        ]
        result = layout_engine.layout(connections)

        assert len(result.nodes) == 5
        assert result.has_cycles is False
        assert result.nodes["A"].layer == 0
        assert result.nodes["E"].layer == 3

    def test_layout_with_back_edge(self, layout_engine):
        """Test layout with explicit back edge."""
        connections = [
            ("A", "B"),
            ("B", "C"),
            ("C", "B"),  # Back edge
        ]
        result = layout_engine.layout(connections)

        assert result.has_cycles is True
        assert ("C", "B") in result.back_edges

    def test_layout_multiple_back_edges(self, layout_engine):
        """Test layout with multiple back edges."""
        connections = [
            ("A", "B"),
            ("B", "C"),
            ("C", "D"),
            ("D", "B"),  # Back edge
            ("C", "A"),  # Back edge
        ]
        result = layout_engine.layout(connections)

        assert result.has_cycles is True
        assert len(result.back_edges) >= 1

    def test_layout_single_node_self_loop(self, layout_engine):
        """Test layout with self-loop."""
        connections = [("A", "A")]
        result = layout_engine.layout(connections)

        assert result.has_cycles is True
        assert len(result.nodes) == 1

    def test_layout_disconnected_components(self, layout_engine):
        """Test layout with disconnected graph components."""
        connections = [
            ("A", "B"),
            ("C", "D"),  # Disconnected from A-B
        ]
        result = layout_engine.layout(connections)

        assert len(result.nodes) == 4
        assert "A" in result.nodes
        assert "C" in result.nodes


class TestSugiyamaLayoutAlias:
    """Tests for SugiyamaLayout alias."""

    def test_sugiyama_is_networkx_alias(self):
        """Test that SugiyamaLayout is an alias for NetworkXLayout."""
        assert SugiyamaLayout is NetworkXLayout

    def test_sugiyama_works_same_as_networkx(self, simple_connections):
        """Test that SugiyamaLayout produces same results."""
        nx_layout = NetworkXLayout()
        sugiyama = SugiyamaLayout()

        result1 = nx_layout.layout(simple_connections)
        result2 = sugiyama.layout(simple_connections)

        assert len(result1.nodes) == len(result2.nodes)
        assert result1.has_cycles == result2.has_cycles


class TestBarycenterOrdering:
    """Tests for barycenter-based node ordering."""

    def test_barycenter_reduces_crossings(self, layout_engine):
        """Test that barycenter ordering attempts to minimize crossings."""
        # Diamond pattern: A -> B, A -> C, B -> D, C -> D
        connections = [
            ("A", "B"),
            ("A", "C"),
            ("B", "D"),
            ("C", "D"),
        ]
        result = layout_engine.layout(connections)

        # B and C should be ordered consistently with their connections
        assert len(result.layers) >= 3
        assert "B" in result.layers[1]
        assert "C" in result.layers[1]

    def test_layer_ordering_with_many_edges(self, layout_engine):
        """Test ordering with multiple edges per node."""
        connections = [
            ("A", "X"),
            ("A", "Y"),
            ("A", "Z"),
            ("X", "B"),
            ("Y", "B"),
            ("Z", "B"),
        ]
        result = layout_engine.layout(connections)

        assert len(result.nodes) == 5
        middle_layer = result.layers[1]
        assert set(middle_layer) == {"X", "Y", "Z"}
