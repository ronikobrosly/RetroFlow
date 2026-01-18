"""Unit tests for the edge_drawing module."""

import pytest

from retroflow import FlowchartGenerator
from retroflow.edge_drawing import EdgeDrawer
from retroflow.positioning import PositionCalculator
from retroflow.renderer import BoxRenderer


@pytest.fixture
def box_renderer():
    """Create a BoxRenderer instance."""
    return BoxRenderer()


@pytest.fixture
def position_calculator(box_renderer):
    """Create a PositionCalculator instance."""
    return PositionCalculator(
        box_renderer=box_renderer,
        min_box_width=10,
        horizontal_spacing=12,
        vertical_spacing=3,
        shadow=True,
    )


@pytest.fixture
def edge_drawer(position_calculator):
    """Create an EdgeDrawer instance."""
    return EdgeDrawer(
        position_calculator=position_calculator,
        shadow=True,
    )


@pytest.fixture
def edge_drawer_no_shadow(position_calculator):
    """Create an EdgeDrawer instance without shadow."""
    return EdgeDrawer(
        position_calculator=position_calculator,
        shadow=False,
    )


class TestEdgeDrawerInit:
    """Tests for EdgeDrawer initialization."""

    def test_init_with_shadow(self, position_calculator):
        """Test EdgeDrawer initialization with shadow."""
        drawer = EdgeDrawer(
            position_calculator=position_calculator,
            shadow=True,
        )
        assert drawer.shadow is True
        assert drawer.position_calculator is position_calculator

    def test_init_without_shadow(self, position_calculator):
        """Test EdgeDrawer initialization without shadow."""
        drawer = EdgeDrawer(
            position_calculator=position_calculator,
            shadow=False,
        )
        assert drawer.shadow is False


class TestEdgeDrawingIntegration:
    """Integration tests for edge drawing with various scenarios."""

    def test_simple_vertical_edge_tb(self):
        """Test simple vertical edge in TB mode."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate("A -> B")
        # Should have down arrow
        assert "A" in result
        assert "B" in result

    def test_simple_horizontal_edge_lr(self):
        """Test simple horizontal edge in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate("A -> B")
        # Should have right arrow
        assert "A" in result
        assert "B" in result

    def test_diagonal_routing_tb(self):
        """Test diagonal routing in TB mode (source and target not aligned)."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> B
            A -> C
            B -> D
            C -> D
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_diagonal_routing_lr(self):
        """Test diagonal routing in LR mode (source and target not aligned)."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            A -> B
            A -> C
            B -> D
            C -> D
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_back_edge_tb(self):
        """Test back edge (cycle) in TB mode."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> B
            B -> C
            C -> A
            """
        )
        for node in ["A", "B", "C"]:
            assert node in result

    def test_back_edge_lr(self):
        """Test back edge (cycle) in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            A -> B
            B -> C
            C -> A
            """
        )
        for node in ["A", "B", "C"]:
            assert node in result

    def test_multiple_back_edges_tb(self):
        """Test multiple back edges in TB mode."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> B
            B -> C
            C -> D
            D -> B
            D -> A
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_fan_out_tb(self):
        """Test fan-out (one to many) in TB mode."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> B
            A -> C
            A -> D
            A -> E
            """
        )
        for node in ["A", "B", "C", "D", "E"]:
            assert node in result

    def test_fan_in_tb(self):
        """Test fan-in (many to one) in TB mode."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> E
            B -> E
            C -> E
            D -> E
            """
        )
        for node in ["A", "B", "C", "D", "E"]:
            assert node in result

    def test_fan_out_lr(self):
        """Test fan-out in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            A -> B
            A -> C
            A -> D
            A -> E
            """
        )
        for node in ["A", "B", "C", "D", "E"]:
            assert node in result

    def test_fan_in_lr(self):
        """Test fan-in in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            A -> E
            B -> E
            C -> E
            D -> E
            """
        )
        for node in ["A", "B", "C", "D", "E"]:
            assert node in result

    def test_wide_graph_tb(self):
        """Test wide graph in TB mode."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> B
            A -> C
            A -> D
            A -> E
            A -> F
            B -> G
            C -> G
            D -> G
            E -> G
            F -> G
            """
        )
        for node in ["A", "B", "C", "D", "E", "F", "G"]:
            assert node in result

    def test_deep_graph_lr(self):
        """Test deep graph in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            A -> B
            B -> C
            C -> D
            D -> E
            E -> F
            F -> G
            G -> H
            """
        )
        for node in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            assert node in result


class TestGroupEdgeDrawing:
    """Tests for edge drawing with groups."""

    def test_grouped_nodes_tb(self):
        """Test edge drawing with grouped nodes in TB mode."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [Group: B C D]
            A -> B
            B -> C
            C -> D
            D -> E
            """
        )
        for node in ["A", "B", "C", "D", "E"]:
            assert node in result

    def test_grouped_nodes_lr(self):
        """Test edge drawing with grouped nodes in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            [Group: B C D]
            A -> B
            B -> C
            C -> D
            D -> E
            """
        )
        for node in ["A", "B", "C", "D", "E"]:
            assert node in result

    def test_multiple_groups_tb(self):
        """Test edge drawing with multiple groups in TB mode."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [Group1: A B]
            [Group2: C D]
            A -> B
            B -> C
            C -> D
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_edges_within_group_tb(self):
        """Test edges within a group in TB mode."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [All: A B C D E]
            A -> B
            B -> C
            C -> D
            D -> E
            """
        )
        for node in ["A", "B", "C", "D", "E"]:
            assert node in result

    def test_back_edge_in_group_tb(self):
        """Test back edge within a group in TB mode."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [Loop: B C D]
            A -> B
            B -> C
            C -> D
            D -> B
            D -> E
            """
        )
        for node in ["A", "B", "C", "D", "E"]:
            assert node in result

    def test_back_edge_across_groups(self):
        """Test back edge crossing group boundaries."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [Start: A B]
            [End: C D]
            A -> B
            B -> C
            C -> D
            D -> A
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_group_with_wide_fanout(self):
        """Test group with wide fan-out pattern."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [Fan: A B C D E]
            Start -> A
            A -> B
            A -> C
            A -> D
            A -> E
            B -> End
            C -> End
            D -> End
            E -> End
            """
        )
        for node in ["Start", "A", "B", "C", "D", "E", "End"]:
            assert node in result

    def test_group_dense_connections_lr(self):
        """Test dense connections within group in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            [Dense: B C D E]
            A -> B
            A -> C
            B -> D
            C -> D
            B -> E
            C -> E
            D -> F
            E -> F
            """
        )
        for node in ["A", "B", "C", "D", "E", "F"]:
            assert node in result


class TestEdgeDrawingEdgeCases:
    """Tests for edge cases in edge drawing."""

    def test_self_loop(self):
        """Test self-loop edge."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> B
            B -> B
            B -> C
            """
        )
        for node in ["A", "B", "C"]:
            assert node in result

    def test_parallel_edges_same_layer(self):
        """Test parallel edges between same layer nodes."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> B
            A -> C
            B -> D
            C -> D
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_long_node_names(self):
        """Test edges with long node names."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            VeryLongNodeNameStart -> Process
            Process -> VeryLongNodeNameEnd
            """
        )
        assert "VeryLongNodeNameStart" in result
        assert "VeryLongNodeNameEnd" in result

    def test_no_shadow_mode(self):
        """Test edge drawing without shadows."""
        gen = FlowchartGenerator(direction="TB", shadow=False)
        result = gen.generate(
            """
            A -> B
            B -> C
            C -> D
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_complex_topology_tb(self):
        """Test complex topology in TB mode."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> B
            A -> C
            A -> D
            B -> E
            C -> E
            C -> F
            D -> F
            E -> G
            F -> G
            G -> H
            H -> A
            """
        )
        for node in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            assert node in result

    def test_complex_topology_lr(self):
        """Test complex topology in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            A -> B
            A -> C
            A -> D
            B -> E
            C -> E
            C -> F
            D -> F
            E -> G
            F -> G
            G -> H
            H -> A
            """
        )
        for node in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            assert node in result

    def test_many_layers_tb(self):
        """Test many layers in TB mode."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            L1 -> L2
            L2 -> L3
            L3 -> L4
            L4 -> L5
            L5 -> L6
            L6 -> L7
            L7 -> L8
            L8 -> L9
            L9 -> L10
            """
        )
        for i in range(1, 11):
            assert f"L{i}" in result

    def test_many_layers_lr(self):
        """Test many layers in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            L1 -> L2
            L2 -> L3
            L3 -> L4
            L4 -> L5
            L5 -> L6
            L6 -> L7
            L7 -> L8
            L8 -> L9
            L9 -> L10
            """
        )
        for i in range(1, 11):
            assert f"L{i}" in result

    def test_wide_and_deep_graph(self):
        """Test graph that is both wide and deep."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> B
            A -> C
            A -> D
            B -> E
            B -> F
            C -> G
            C -> H
            D -> I
            D -> J
            E -> K
            F -> K
            G -> K
            H -> K
            I -> K
            J -> K
            """
        )
        for letter in "ABCDEFGHIJK":
            assert letter in result

    def test_multiple_roots(self):
        """Test graph with multiple root nodes."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> D
            B -> D
            C -> D
            D -> E
            """
        )
        for letter in "ABCDE":
            assert letter in result

    def test_multiple_sinks(self):
        """Test graph with multiple sink nodes."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> B
            B -> C
            B -> D
            B -> E
            """
        )
        for letter in "ABCDE":
            assert letter in result

    def test_diamond_with_groups(self):
        """Test diamond pattern with groups."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [Top: A]
            [Middle: B C]
            [Bottom: D]
            A -> B
            A -> C
            B -> D
            C -> D
            """
        )
        for letter in "ABCD":
            assert letter in result

    def test_parallel_chains_with_groups(self):
        """Test parallel chains with groups."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [Chain1: A B C]
            [Chain2: D E F]
            Start -> A
            Start -> D
            A -> B
            B -> C
            D -> E
            E -> F
            C -> End
            F -> End
            """
        )
        for node in ["Start", "A", "B", "C", "D", "E", "F", "End"]:
            assert node in result


class TestUpwardEdgeRouting:
    """Tests for upward edge routing (target above source)."""

    def test_grouped_nodes_different_layers_tb(self):
        """Test edge routing when grouped nodes span multiple layers."""
        gen = FlowchartGenerator(direction="TB")
        # Group containing nodes from different layers should
        # create upward edge routing scenarios
        result = gen.generate(
            """
            [Grouped: A C]
            A -> B
            B -> C
            C -> D
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_grouped_nodes_upward_with_middle_node_tb(self):
        """Test upward edge when middle node goes to grouped node above."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [Top: A B]
            [Bottom: D E]
            A -> B
            B -> C
            C -> D
            D -> E
            E -> A
            """
        )
        for node in ["A", "B", "C", "D", "E"]:
            assert node in result

    def test_grouped_nodes_with_wide_group_tb(self):
        """Test upward routing with wide groups."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [Wide: A B C D E]
            Start -> A
            A -> B
            B -> C
            C -> D
            D -> E
            E -> End
            End -> B
            """
        )
        for node in ["Start", "A", "B", "C", "D", "E", "End"]:
            assert node in result

    def test_edge_to_earlier_layer_in_group(self):
        """Test edge from later layer to earlier layer within group."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [All: A B C D]
            A -> B
            B -> C
            C -> D
            D -> A
            D -> B
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_complex_upward_routing_with_boxes_in_path(self):
        """Test upward routing when boxes block the direct path."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [Group1: A E]
            [Group2: B C D]
            A -> B
            B -> C
            C -> D
            D -> E
            E -> F
            F -> A
            """
        )
        for node in ["A", "B", "C", "D", "E", "F"]:
            assert node in result


class TestLRModeEdgeRouting:
    """Tests for LR mode edge routing with various blocking scenarios."""

    def test_lr_boxes_blocking_direct_path(self):
        """Test LR mode when boxes block direct horizontal path."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            [Frontend: A B]
            [Backend: C D]
            A -> B
            B -> C
            C -> D
            A -> D
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_lr_complex_blocking_scenario(self):
        """Test complex blocking in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            [Layer1: A B C]
            [Layer2: D E F]
            A -> B
            B -> C
            A -> D
            D -> E
            E -> F
            B -> E
            C -> F
            F -> G
            """
        )
        for node in ["A", "B", "C", "D", "E", "F", "G"]:
            assert node in result

    def test_lr_back_edge_with_blocking_boxes(self):
        """Test back edge in LR mode with boxes in path."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            [Process: B C D]
            A -> B
            B -> C
            C -> D
            D -> E
            E -> A
            D -> B
            """
        )
        for node in ["A", "B", "C", "D", "E"]:
            assert node in result

    def test_lr_wide_fanout_with_groups(self):
        """Test wide fanout in LR mode with grouped nodes."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            [Fanout: B C D E]
            A -> B
            A -> C
            A -> D
            A -> E
            B -> F
            C -> F
            D -> F
            E -> F
            """
        )
        for node in ["A", "B", "C", "D", "E", "F"]:
            assert node in result

    def test_lr_dense_connections_with_groups(self):
        """Test dense connections in LR mode with multiple groups."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            [Input: A B]
            [Process: C D E]
            [Output: F G]
            A -> C
            A -> D
            B -> D
            B -> E
            C -> F
            D -> F
            D -> G
            E -> G
            """
        )
        for node in ["A", "B", "C", "D", "E", "F", "G"]:
            assert node in result

    def test_lr_tall_boxes_blocking(self):
        """Test LR mode with tall boxes that block horizontal paths."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            [Tall: A B C D E]
            Start -> A
            A -> B
            B -> C
            C -> D
            D -> E
            E -> End
            Start -> End
            """
        )
        for node in ["Start", "A", "B", "C", "D", "E", "End"]:
            assert node in result


class TestBorderOverlayScenarios:
    """Tests for edge routing that touches box borders."""

    def test_edge_touches_top_border(self):
        """Test edge that routes near top border."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            A -> B
            A -> C
            B -> D
            C -> D
            D -> E
            E -> A
            """
        )
        for node in ["A", "B", "C", "D", "E"]:
            assert node in result

    def test_edge_touches_bottom_border(self):
        """Test edge that routes near bottom border."""
        gen = FlowchartGenerator(direction="TB")
        result = gen.generate(
            """
            [Top: A B]
            A -> B
            B -> C
            C -> D
            D -> A
            D -> B
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_edge_touches_left_border_lr(self):
        """Test edge near left border in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            [Box: B C]
            A -> B
            B -> C
            C -> D
            D -> A
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result

    def test_edge_touches_right_border_lr(self):
        """Test edge near right border in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        result = gen.generate(
            """
            [Box: A B]
            A -> B
            B -> C
            C -> D
            D -> B
            """
        )
        for node in ["A", "B", "C", "D"]:
            assert node in result
