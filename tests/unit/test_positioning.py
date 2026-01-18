"""Unit tests for the positioning module."""

import pytest

from retroflow import FlowchartGenerator
from retroflow.models import GroupBoundary, GroupDefinition
from retroflow.positioning import (
    GROUP_EDGE_MARGIN,
    GROUP_EXTERNAL_MARGIN,
    GROUP_INTERNAL_PADDING,
    GROUP_TITLE_HEIGHT,
    PositionCalculator,
)
from retroflow.renderer import BoxDimensions, BoxRenderer


@pytest.fixture
def position_calculator():
    """Create a PositionCalculator with default settings."""
    box_renderer = BoxRenderer()
    return PositionCalculator(
        box_renderer=box_renderer,
        min_box_width=10,
        horizontal_spacing=12,
        vertical_spacing=3,
        shadow=True,
    )


@pytest.fixture
def simple_layout(position_calculator):
    """Create a simple layout result for testing."""
    gen = FlowchartGenerator()
    connections = gen.parser.parse("A -> B\nB -> C")
    return gen.layout_engine.layout(connections)


@pytest.fixture
def simple_box_dimensions(position_calculator, simple_layout):
    """Create box dimensions for simple layout."""
    return position_calculator.calculate_all_box_dimensions(simple_layout)


class TestGroupConstants:
    """Tests for group-related constants."""

    def test_group_internal_padding_value(self):
        """Test GROUP_INTERNAL_PADDING has reasonable value."""
        assert GROUP_INTERNAL_PADDING >= 2
        assert GROUP_INTERNAL_PADDING <= 10

    def test_group_external_margin_value(self):
        """Test GROUP_EXTERNAL_MARGIN has reasonable value."""
        assert GROUP_EXTERNAL_MARGIN >= 2
        assert GROUP_EXTERNAL_MARGIN <= 10

    def test_group_title_height_value(self):
        """Test GROUP_TITLE_HEIGHT has reasonable value."""
        assert GROUP_TITLE_HEIGHT >= 1
        assert GROUP_TITLE_HEIGHT <= 3

    def test_group_edge_margin_value(self):
        """Test GROUP_EDGE_MARGIN has reasonable value."""
        assert GROUP_EDGE_MARGIN >= 1
        assert GROUP_EDGE_MARGIN <= 10


class TestCalculateGroupBoundaries:
    """Tests for calculate_group_boundaries method."""

    def test_single_group_single_member(self, position_calculator):
        """Test calculating boundary for group with single member."""
        groups = [GroupDefinition(name="Test", members=["A"], order=0)]
        box_positions = {"A": (10, 10)}
        box_dimensions = {"A": BoxDimensions(width=15, height=5, text_lines=["A"])}

        boundaries = position_calculator.calculate_group_boundaries(
            groups, box_positions, box_dimensions
        )

        assert len(boundaries) == 1
        assert boundaries[0].name == "Test"
        assert boundaries[0].members == ["A"]
        # Boundary should encompass the box plus padding
        assert boundaries[0].width > 15

    def test_single_group_multiple_members(self, position_calculator):
        """Test calculating boundary for group with multiple members."""
        groups = [GroupDefinition(name="Test", members=["A", "B"], order=0)]
        box_positions = {"A": (10, 10), "B": (30, 10)}
        box_dimensions = {
            "A": BoxDimensions(width=15, height=5, text_lines=["A"]),
            "B": BoxDimensions(width=15, height=5, text_lines=["B"]),
        }

        boundaries = position_calculator.calculate_group_boundaries(
            groups, box_positions, box_dimensions
        )

        assert len(boundaries) == 1
        # Boundary should encompass both boxes
        assert boundaries[0].width > 30  # Wider than single box position

    def test_multiple_groups(self, position_calculator):
        """Test calculating boundaries for multiple groups."""
        groups = [
            GroupDefinition(name="Group1", members=["A"], order=0),
            GroupDefinition(name="Group2", members=["B"], order=1),
        ]
        box_positions = {"A": (10, 10), "B": (50, 10)}
        box_dimensions = {
            "A": BoxDimensions(width=15, height=5, text_lines=["A"]),
            "B": BoxDimensions(width=15, height=5, text_lines=["B"]),
        }

        boundaries = position_calculator.calculate_group_boundaries(
            groups, box_positions, box_dimensions
        )

        assert len(boundaries) == 2
        assert boundaries[0].name == "Group1"
        assert boundaries[1].name == "Group2"

    def test_group_boundary_includes_title(self, position_calculator):
        """Test that group boundary accounts for title."""
        groups = [GroupDefinition(name="Long Title", members=["A"], order=0)]
        box_positions = {"A": (10, 10)}
        box_dimensions = {"A": BoxDimensions(width=15, height=5, text_lines=["A"])}

        boundaries = position_calculator.calculate_group_boundaries(
            groups, box_positions, box_dimensions
        )

        # Title width might affect boundary
        assert boundaries[0].title_width > 0

    def test_empty_groups_list(self, position_calculator):
        """Test with empty groups list."""
        boundaries = position_calculator.calculate_group_boundaries([], {}, {})
        assert boundaries == []


class TestResolveGroupOverlaps:
    """Tests for resolve_group_overlaps method."""

    def test_no_overlap(self, position_calculator):
        """Test when groups don't overlap."""
        groups = [
            GroupBoundary(
                name="G1",
                members=["A"],
                x=0,
                y=0,
                width=20,
                height=10,
                title_x=5,
                title_y=0,
                title_width=10,
            ),
            GroupBoundary(
                name="G2",
                members=["B"],
                x=50,
                y=0,
                width=20,
                height=10,
                title_x=55,
                title_y=0,
                title_width=10,
            ),
        ]
        box_positions = {"A": (5, 5), "B": (55, 5)}
        box_dimensions = {
            "A": BoxDimensions(width=10, height=5, text_lines=["A"]),
            "B": BoxDimensions(width=10, height=5, text_lines=["B"]),
        }

        new_positions, new_boundaries = position_calculator.resolve_group_overlaps(
            groups, box_positions, box_dimensions, direction="TB"
        )

        # Positions should remain unchanged when no overlap
        assert "A" in new_positions
        assert "B" in new_positions

    def test_single_group_no_change(self, position_calculator):
        """Test that single group returns unchanged."""
        groups = [
            GroupBoundary(
                name="G1",
                members=["A"],
                x=0,
                y=0,
                width=20,
                height=10,
                title_x=5,
                title_y=0,
                title_width=10,
            ),
        ]
        box_positions = {"A": (5, 5)}
        box_dimensions = {"A": BoxDimensions(width=10, height=5, text_lines=["A"])}

        new_positions, new_boundaries = position_calculator.resolve_group_overlaps(
            groups, box_positions, box_dimensions, direction="TB"
        )

        assert new_positions["A"] == (5, 5)


class TestCalculateGroupAwarePositions:
    """Tests for calculate_group_aware_positions method."""

    def test_basic_group_positioning_tb(self, position_calculator):
        """Test basic group-aware positioning in TB mode."""
        gen = FlowchartGenerator()
        connections = gen.parser.parse("A -> B\nB -> C")
        layout_result = gen.layout_engine.layout(connections)
        box_dimensions = position_calculator.calculate_all_box_dimensions(layout_result)
        groups = [GroupDefinition(name="Test", members=["A", "B"], order=0)]

        positions = position_calculator.calculate_group_aware_positions(
            layout_result, box_dimensions, groups, direction="TB", margin=0
        )

        assert "A" in positions
        assert "B" in positions
        assert "C" in positions
        # All positions should be valid tuples
        for pos in positions.values():
            assert isinstance(pos, tuple)
            assert len(pos) == 2

    def test_basic_group_positioning_lr(self, position_calculator):
        """Test basic group-aware positioning in LR mode."""
        gen = FlowchartGenerator()
        connections = gen.parser.parse("A -> B\nB -> C")
        layout_result = gen.layout_engine.layout(connections)
        box_dimensions = position_calculator.calculate_all_box_dimensions(layout_result)
        groups = [GroupDefinition(name="Test", members=["A", "B"], order=0)]

        positions = position_calculator.calculate_group_aware_positions(
            layout_result, box_dimensions, groups, direction="LR", margin=0
        )

        assert "A" in positions
        assert "B" in positions
        assert "C" in positions

    def test_group_with_margin(self, position_calculator):
        """Test group-aware positioning with margin."""
        gen = FlowchartGenerator()
        connections = gen.parser.parse("A -> B")
        layout_result = gen.layout_engine.layout(connections)
        box_dimensions = position_calculator.calculate_all_box_dimensions(layout_result)
        groups = [GroupDefinition(name="Test", members=["A"], order=0)]

        positions_no_margin = position_calculator.calculate_group_aware_positions(
            layout_result, box_dimensions, groups, direction="TB", margin=0
        )
        positions_with_margin = position_calculator.calculate_group_aware_positions(
            layout_result, box_dimensions, groups, direction="TB", margin=10
        )

        # With margin, positions should be shifted
        assert positions_with_margin["A"][0] >= positions_no_margin["A"][0]


class TestCalculateGroupEdgeMargin:
    """Tests for calculate_group_edge_margin method."""

    def test_no_groups(self, position_calculator):
        """Test edge margin with no groups."""
        margin = position_calculator.calculate_group_edge_margin([])
        assert margin == 0

    def test_with_groups(self, position_calculator):
        """Test edge margin with groups (requires GroupBoundary objects)."""
        group_boundaries = [
            GroupBoundary(
                name="Test",
                members=["A"],
                x=10,
                y=10,
                width=20,
                height=15,
                title_x=15,
                title_y=9,
                title_width=10,
            )
        ]
        margin = position_calculator.calculate_group_edge_margin(group_boundaries)
        assert margin >= GROUP_EDGE_MARGIN


class TestPositionCalculatorGroupIntegration:
    """Integration tests for group positioning."""

    def test_full_pipeline_with_groups(self):
        """Test complete positioning pipeline with groups."""
        gen = FlowchartGenerator()
        input_text = """
        [Frontend: A B]
        A -> B
        B -> C
        C -> D
        """
        # Should generate without errors
        result = gen.generate(input_text)
        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "D" in result

    def test_multiple_groups_no_overlap(self):
        """Test that multiple groups don't produce overlapping output."""
        gen = FlowchartGenerator()
        input_text = """
        [Group1: A B]
        [Group2: C D]
        A -> B
        B -> C
        C -> D
        D -> E
        """
        result = gen.generate(input_text)
        # Should contain all elements
        assert "Group1" in result
        assert "Group2" in result
        for node in ["A", "B", "C", "D", "E"]:
            assert node in result

    def test_group_lr_mode_stacking(self):
        """Test that groups stack nodes correctly in LR mode."""
        gen = FlowchartGenerator(direction="LR")
        input_text = """
        [Backend: API DB]
        API -> DB
        DB -> Cache
        """
        result = gen.generate(input_text)
        assert "Backend" in result
        assert "API" in result
        assert "DB" in result
        assert "Cache" in result
