"""
Unit tests for the wire grid.

The grid is the one place where edge glyphs are decided, so these tests pin
the rule it exists for: a glyph comes from the lines in its cell, never from
whatever character happened to be drawn there first.
"""

import pytest

from retroflow.wire_grid import (
    ARM_GLYPHS,
    DOWN,
    LEFT,
    RIGHT,
    UP,
    WireConflict,
    WireGrid,
)


def drawing(grid: WireGrid) -> str:
    """Render a grid as text (blank cells as spaces)."""
    min_x, min_y, max_x, max_y = grid.bounds()
    cells = dict(grid.cells())
    return "\n".join(
        "".join(cells.get((x, y), " ") for x in range(min_x, max_x + 1)).rstrip()
        for y in range(min_y, max_y + 1)
    )


class TestSegments:
    """Straight runs and how they join."""

    def test_horizontal_run(self):
        grid = WireGrid()
        grid.add_segment(1, (0, 0), (4, 0))
        assert [grid.glyph_at((x, 0)) for x in (1, 2, 3)] == ["─", "─", "─"]

    def test_vertical_run(self):
        grid = WireGrid()
        grid.add_segment(1, (2, 0), (2, 3))
        assert [grid.glyph_at((2, y)) for y in (1, 2)] == ["│", "│"]

    def test_direction_of_travel_does_not_matter(self):
        forward, backward = WireGrid(), WireGrid()
        forward.add_segment(1, (0, 0), (5, 0))
        backward.add_segment(1, (5, 0), (0, 0))
        assert dict(forward.cells()) == dict(backward.cells())

    @pytest.mark.parametrize(
        "second_end, expected",
        [((3, 2), "┐"), ((3, -2), "┘")],
    )
    def test_two_runs_sharing_an_end_make_a_corner(self, second_end, expected):
        grid = WireGrid()
        grid.add_segment(1, (0, 0), (3, 0))
        grid.add_segment(1, (3, 0), second_end)
        assert grid.glyph_at((3, 0)) == expected

    def test_all_four_corners(self):
        grid = WireGrid()
        grid.add_segment(1, (0, 0), (4, 0))
        grid.add_segment(1, (4, 0), (4, 2))
        grid.add_segment(1, (4, 2), (0, 2))
        grid.add_segment(1, (0, 2), (0, 0))
        assert drawing(grid) == "┌───┐\n│   │\n└───┘"

    def test_a_run_ending_on_another_makes_a_tee(self):
        grid = WireGrid()
        grid.add_segment(1, (0, 1), (6, 1))
        grid.add_segment(1, (3, 1), (3, 3))
        assert grid.glyph_at((3, 1)) == "┬"

    @pytest.mark.parametrize(
        "branch_end, expected",
        [((3, 3), "┬"), ((3, -1), "┴")],
    )
    def test_tees_on_a_horizontal_trunk(self, branch_end, expected):
        grid = WireGrid()
        grid.add_segment(7, (0, 1), (6, 1))
        grid.add_segment(7, (3, 1), branch_end)
        assert grid.glyph_at((3, 1)) == expected

    @pytest.mark.parametrize(
        "branch_end, expected",
        [((5, 2), "├"), ((0, 2), "┤")],
    )
    def test_tees_on_a_vertical_trunk(self, branch_end, expected):
        grid = WireGrid()
        grid.add_segment(7, (2, 0), (2, 4))
        grid.add_segment(7, (2, 2), branch_end)
        assert grid.glyph_at((2, 2)) == expected

    def test_same_net_four_way_meeting_is_one_glyph(self):
        grid = WireGrid()
        grid.add_segment(1, (0, 2), (4, 2))
        grid.add_segment(1, (2, 0), (2, 4))
        assert grid.glyph_at((2, 2)) == "┼"
        assert (2, 2) not in {conflict.cell for conflict in grid.conflicts}

    def test_overlapping_runs_of_one_net_merge(self):
        grid = WireGrid()
        grid.add_segment(1, (0, 0), (5, 0))
        grid.add_segment(1, (2, 0), (8, 0))
        assert drawing(grid) == "─" * 9
        assert grid.conflicts[0].cell == (0, 0)  # only the loose ends remain

    def test_zero_length_segment_adds_nothing(self):
        grid = WireGrid()
        grid.add_segment(1, (3, 3), (3, 3))
        assert grid.bounds() is None
        assert list(grid.cells()) == []

    def test_diagonal_segment_is_rejected(self):
        with pytest.raises(ValueError, match="not axis-aligned"):
            WireGrid().add_segment(1, (0, 0), (2, 2))


class TestCrossings:
    """Two different nets may only meet at a clean right angle."""

    def test_perpendicular_nets_cross(self):
        grid = WireGrid()
        grid.add_segment(1, (0, 2), (4, 2))
        grid.add_segment(2, (2, 0), (2, 4))
        assert grid.glyph_at((2, 2)) == "┼"
        assert grid.crossing_count() == 1
        assert [c for c in grid.conflicts if c.cell == (2, 2)] == []

    def test_nets_running_along_each_other_are_a_conflict(self):
        grid = WireGrid()
        grid.add_segment(1, (0, 0), (6, 0))
        grid.add_segment(2, (2, 0), (4, 0))
        cells = {conflict.cell for conflict in grid.conflicts}
        assert (3, 0) in cells

    def test_a_bend_on_another_net_is_a_conflict(self):
        grid = WireGrid()
        grid.add_segment(1, (0, 2), (4, 2))
        grid.add_segment(2, (2, 0), (2, 2))
        grid.add_segment(2, (2, 2), (5, 2))
        reasons = {c.reason for c in grid.conflicts if c.cell == (2, 2)}
        assert reasons == {"two different lines share a cell without crossing cleanly"}

    def test_three_nets_in_one_cell_are_a_conflict(self):
        grid = WireGrid()
        grid.add_segment(1, (0, 1), (2, 1))
        grid.add_segment(2, (1, 0), (1, 2))
        grid.add_segment(3, (0, 1), (2, 1))
        reasons = {c.reason for c in grid.conflicts if c.cell == (1, 1)}
        assert reasons == {"more than two lines share a cell"}

    def test_a_loose_end_is_reported(self):
        grid = WireGrid()
        grid.add_segment(1, (0, 0), (3, 0))
        ends = {conflict.cell for conflict in grid.conflicts}
        assert ends == {(0, 0), (3, 0)}
        assert grid.glyph_at((0, 0)) == "─"

    def test_conflict_reads_as_a_sentence(self):
        conflict = WireConflict((4, 9), "line ends without reaching anything")
        assert str(conflict) == "(4, 9): line ends without reaching anything"


class TestArrowsAndExits:
    """Line ends that attach to boxes."""

    @pytest.mark.parametrize(
        "start, end, direction, glyph",
        [
            ((2, 0), (2, 3), DOWN, "▼"),
            ((2, 3), (2, 0), UP, "▲"),
            ((0, 1), (4, 1), RIGHT, "►"),
            ((4, 1), (0, 1), LEFT, "◄"),
        ],
    )
    def test_arrowhead_at_the_end_of_a_run(self, start, end, direction, glyph):
        grid = WireGrid()
        grid.add_arm(
            1, start, {DOWN: UP, UP: DOWN, RIGHT: LEFT, LEFT: RIGHT}[direction]
        )
        grid.add_segment(1, start, end)
        grid.add_arrow(1, end, direction)
        assert grid.glyph_at(end) == glyph
        assert grid.conflicts == []

    def test_arrowhead_fed_from_the_side_is_a_conflict(self):
        grid = WireGrid()
        grid.add_segment(1, (0, 0), (3, 0))
        grid.add_arrow(1, (3, 0), DOWN)
        reasons = {c.reason for c in grid.conflicts if c.cell == (3, 0)}
        assert reasons == {"an arrowhead is not fed from directly behind"}

    def test_arrowhead_sharing_a_cell_is_a_conflict(self):
        grid = WireGrid()
        grid.add_segment(1, (2, 0), (2, 3))
        grid.add_arrow(1, (2, 3), DOWN)
        grid.add_segment(2, (0, 3), (4, 3))
        reasons = {c.reason for c in grid.conflicts if c.cell == (2, 3)}
        assert reasons == {"an arrowhead shares its cell with another line"}

    def test_first_cell_reaches_back_into_its_box(self):
        grid = WireGrid()
        grid.add_arm(1, (2, 1), UP)  # the box border is at (2, 0)
        grid.add_segment(1, (2, 1), (2, 4))
        grid.add_arrow(1, (2, 4), DOWN)
        assert drawing(grid) == "│\n│\n│\n▼"
        assert grid.conflicts == []


class TestReading:
    """Looking at what is in the grid."""

    def test_empty_grid(self):
        grid = WireGrid()
        assert grid.bounds() is None
        assert grid.glyph_at((0, 0)) is None
        assert grid.arms_at((0, 0)) == {}
        assert grid.conflicts == []
        assert grid.crossing_count() == 0

    def test_arms_are_reported_per_net(self):
        grid = WireGrid()
        grid.add_segment(1, (0, 1), (2, 1))
        grid.add_segment(2, (1, 0), (1, 2))
        assert grid.arms_at((1, 1)) == {1: frozenset("LR"), 2: frozenset("UD")}

    def test_cells_come_in_reading_order(self):
        grid = WireGrid()
        grid.add_segment(1, (3, 2), (0, 2))
        grid.add_segment(1, (3, 0), (3, 2))
        assert [cell for cell, _ in grid.cells()] == [
            (3, 0),
            (3, 1),
            (0, 2),
            (1, 2),
            (2, 2),
            (3, 2),
        ]

    def test_bounds_cover_arrows_too(self):
        grid = WireGrid()
        grid.add_segment(1, (1, 1), (1, 5))
        grid.add_arrow(1, (1, 5), DOWN)
        assert grid.bounds() == (1, 1, 1, 5)

    def test_shifted_moves_everything_and_leaves_the_original_alone(self):
        grid = WireGrid()
        grid.add_arm(1, (2, 0), UP)
        grid.add_segment(1, (2, 0), (2, 3))
        grid.add_arrow(1, (2, 3), DOWN)
        moved = grid.shifted(10, 5)

        assert moved.bounds() == (12, 5, 12, 8)
        assert moved.glyph_at((12, 8)) == "▼"
        assert grid.bounds() == (2, 0, 2, 3)

        moved.add_segment(1, (12, 6), (20, 6))
        assert grid.glyph_at((2, 1)) == "│"  # a tee only in the copy

    def test_every_arm_combination_has_a_glyph(self):
        arms = "UDLR"
        combinations = {
            frozenset(a for a, keep in zip(arms, f"{bits:04b}") if keep == "1")
            for bits in range(16)
        }
        with_two_or_more = {c for c in combinations if len(c) >= 2}
        assert set(ARM_GLYPHS) == with_two_or_more
