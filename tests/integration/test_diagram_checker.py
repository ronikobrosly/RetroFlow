"""
Tests for the diagram checker itself.

The complex-diagram tests are only as trustworthy as the checker behind them,
so each rule is pinned here against small hand-drawn pictures: a clean
picture must pass, and each kind of defect must be reported under its own
code. The pictures are drawn by hand (not rendered) so these tests do not
depend on how the renderer currently routes anything.
"""

from typing import List

from .diagram_checker import (
    Box,
    Issue,
    analyze_rendering,
    check_diagram,
    expected_edges_of,
    normalize_name,
)

# Four boxes in a 2x2 grid, with four blank rows between the two layers.
GRID_BASE = [
    "┌─────┐   ┌─────┐",
    "│  A  │   │  B  │",
    "└─────┘   └─────┘",
    "",
    "",
    "",
    "",
    "┌─────┐   ┌─────┐",
    "│  C  │   │  D  │",
    "└─────┘   └─────┘",
]

# A -> C and B -> D, straight down.
STRAIGHT = [
    "┌─────┐   ┌─────┐",
    "│  A  │   │  B  │",
    "└──┬──┘   └──┬──┘",
    "   │         │",
    "   │         │",
    "   │         │",
    "   ▼         ▼",
    "┌─────┐   ┌─────┐",
    "│  C  │   │  D  │",
    "└─────┘   └─────┘",
]
STRAIGHT_EDGES = {("A", "C"), ("B", "D")}

# A -> D and B -> C, crossing each other once.
CROSSING = [
    "┌─────┐   ┌─────┐",
    "│  A  │   │  B  │",
    "└──┬──┘   └─┬───┘",
    "   │        │",
    "   └────────┼─┐",
    "   ┌────────┘ │",
    "   ▼          ▼",
    "┌─────┐   ┌─────┐",
    "│  C  │   │  D  │",
    "└─────┘   └─────┘",
]
CROSSING_EDGES = {("A", "D"), ("B", "C")}

# A and B share one bus that feeds both C and D.
SHARED_BUS = [
    "┌─────┐   ┌─────┐",
    "│  A  │   │  B  │",
    "└──┬──┘   └──┬──┘",
    "   │         │",
    "   ├─────────┤",
    "   │         │",
    "   ▼         ▼",
    "┌─────┐   ┌─────┐",
    "│  C  │   │  D  │",
    "└─────┘   └─────┘",
]
ALL_FOUR_EDGES = {("A", "C"), ("A", "D"), ("B", "C"), ("B", "D")}

# A left-to-right three-way fan-out through a four-way junction.
FAN_BASE = [
    "           ┌───┐",
    "           │ B │",
    "           └───┘",
    "┌───┐      ┌───┐",
    "│ A │      │ C │",
    "└───┘      └───┘",
    "           ┌───┐",
    "           │ D │",
    "           └───┘",
]
FAN = [
    "           ┌───┐",
    "       ┌──►│ B │",
    "       │   └───┘",
    "┌───┐  │   ┌───┐",
    "│ A │──┼──►│ C │",
    "└───┘  │   └───┘",
    "       │   ┌───┐",
    "       └──►│ D │",
    "           └───┘",
]
FAN_EDGES = {("A", "B"), ("A", "C"), ("A", "D")}

# A -> B where the line passes under a dashed group border.
GROUP_BASE = [
    "┌┄┄┄┄┄┄┄┄┐",
    "┆ ┌───┐  ┆     ┌───┐",
    "┆ │ A │  ┆     │ B │",
    "┆ └───┘  ┆     └───┘",
    "└┄┄┄┄┄┄┄┄┘",
]
GROUP_PASS_UNDER = [
    "┌┄┄┄┄┄┄┄┄┐",
    "┆ ┌───┐  ┆     ┌───┐",
    "┆ │ A │──┆────►│ B │",
    "┆ └───┘  ┆     └───┘",
    "└┄┄┄┄┄┄┄┄┘",
]


def check(base: List[str], final: List[str], edges):
    return analyze_rendering(base, "\n".join(final), set(edges))


def put(lines: List[str], x: int, y: int, text: str) -> List[str]:
    """Return a copy of ``lines`` with ``text`` written at (x, y)."""
    result = list(lines) + [""] * (y + 1 - len(lines))
    row = result[y].ljust(x + len(text))
    result[y] = row[:x] + text + row[x + len(text) :]
    return result


def codes(report) -> set:
    return {issue.code for issue in report.issues}


class TestCleanPictures:
    """Correct pictures produce no issues and the right edges."""

    def test_straight_edges(self):
        report = check(GRID_BASE, STRAIGHT, STRAIGHT_EDGES)
        assert report.issues == []
        assert report.drawn_edges == STRAIGHT_EDGES
        assert set(report.boxes) == {"A", "B", "C", "D"}

    def test_crossing_is_two_separate_edges(self):
        report = check(GRID_BASE, CROSSING, CROSSING_EDGES)
        assert report.issues == []
        assert report.drawn_edges == CROSSING_EDGES
        assert report.crossings == 1
        assert report.junctions == 0

    def test_shared_bus_is_clean_when_all_edges_are_wanted(self):
        report = check(GRID_BASE, SHARED_BUS, ALL_FOUR_EDGES)
        assert report.issues == []
        assert report.drawn_edges == ALL_FOUR_EDGES

    def test_four_way_junction_is_read_as_a_fan_out(self):
        report = check(FAN_BASE, FAN, FAN_EDGES)
        assert report.issues == []
        assert report.drawn_edges == FAN_EDGES
        assert report.junctions == 1
        assert report.crossings == 0

    def test_line_may_pass_under_a_group_border(self):
        report = check(GROUP_BASE, GROUP_PASS_UNDER, {("A", "B")})
        assert report.issues == []
        assert report.drawn_edges == {("A", "B")}

    def test_line_may_replace_a_group_border_cell(self):
        final = put(GROUP_PASS_UNDER, 9, 2, "─")
        report = check(GROUP_BASE, final, {("A", "B")})
        assert report.issues == []

    def test_arrow_fed_directly_by_a_port_mark(self):
        base = ["┌───┐", "│ A │", "└───┘", "", "┌───┐", "│ B │", "└───┘"]
        final = ["┌───┐", "│ A │", "└─┬─┘", "  ▼", "┌───┐", "│ B │", "└───┘"]
        report = check(base, final, {("A", "B")})
        assert report.issues == []
        assert report.drawn_edges == {("A", "B")}

    def test_rendered_simple_diagram(self):
        for direction in ("TB", "LR"):
            report = check_diagram("A -> B\nB -> C", direction)
            assert report.issues == []
            assert report.drawn_edges == {("A", "B"), ("B", "C")}

    def test_rendered_self_loop(self):
        report = check_diagram("A -> B\nB -> B", "TB")
        assert report.issues == []
        assert ("B", "B") in report.drawn_edges


class TestLineDefects:
    """Broken, dangling and stray lines."""

    def test_gap_in_a_line(self):
        final = put(STRAIGHT, 3, 4, " ")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert len(report.of("dangling_line")) == 2
        assert [i.message for i in report.of("missing_edge")] == [
            "cannot trace 'A' -> 'C'"
        ]
        assert len(report.of("stray_line")) == 2

    def test_corner_that_does_not_connect_back(self):
        # '┌' reaches down and right, so the line arriving from above is cut.
        final = put(STRAIGHT, 3, 4, "┌")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        messages = [i.message for i in report.of("dangling_line")]
        assert any("does not connect back" in m for m in messages)
        assert any("toward nothing" in m for m in messages)

    def test_tee_with_unused_arms(self):
        final = put(STRAIGHT, 3, 4, "┼")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert len(report.of("dangling_line")) == 2
        assert not report.of("missing_edge")

    def test_line_touching_a_box_corner(self):
        final = put(STRAIGHT, 0, 3, "│")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        messages = [i.message for i in report.of("dangling_line")]
        assert any("without attaching" in m for m in messages)

    def test_port_mark_without_a_line(self):
        final = put(STRAIGHT, 5, 2, "┬")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert [i.code for i in report.errors] == ["dangling_port"]

    def test_line_with_no_boxes_at_all(self):
        final = put(STRAIGHT, 7, 4, "──")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert len(report.of("dangling_line")) == 2
        assert "neither" in report.of("stray_line")[0].message

    def test_line_between_boxes_without_an_arrowhead(self):
        final = put(STRAIGHT, 3, 6, "│")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert "no arrowhead" in report.of("stray_line")[0].message
        assert report.of("missing_edge")

    def test_line_dead_ending_at_a_group_border(self):
        final = put(GROUP_PASS_UNDER, 10, 2, "     ")
        report = check(GROUP_BASE, final, {("A", "B")})
        assert report.of("dangling_line")
        assert report.of("missing_edge")

    def test_line_running_along_a_group_border(self):
        final = put(GROUP_PASS_UNDER, 9, 1, "│")
        report = check(GROUP_BASE, final, {("A", "B")})
        assert report.of("group_border_damaged")

    def test_arrowhead_drawn_on_a_group_border(self):
        final = put(GROUP_PASS_UNDER, 9, 2, "►")
        report = check(GROUP_BASE, final, {("A", "B")})
        assert report.of("group_border_damaged")
        assert report.of("floating_arrow")


class TestArrowDefects:
    """Arrowheads that float, have no tail, or are run into."""

    def test_arrowhead_in_empty_space(self):
        final = put(STRAIGHT, 8, 4, "▼")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert len(report.of("floating_arrow")) == 1
        assert len(report.of("arrow_no_tail")) == 1

    def test_arrowhead_pointing_at_a_box_corner(self):
        final = put(put(STRAIGHT, 3, 6, " "), 0, 6, "▼")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert report.of("floating_arrow")

    def test_arrowhead_with_nothing_behind_it(self):
        final = put(STRAIGHT, 3, 5, " ")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert len(report.of("arrow_no_tail")) == 1
        assert report.of("missing_edge")

    def test_line_running_into_the_side_of_an_arrowhead(self):
        final = put(STRAIGHT, 4, 6, "─")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert len(report.of("arrow_hit_sideways")) == 1

    def test_arrowhead_pointing_the_wrong_way(self):
        final = put(STRAIGHT, 3, 6, "▲")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert report.of("floating_arrow")
        assert report.of("arrow_hit_sideways")


class TestBoxDefects:
    """Missing or overwritten boxes and labels."""

    def test_missing_node(self):
        report = check(GRID_BASE, STRAIGHT, STRAIGHT_EDGES | {("A", "Ghost")})
        assert [i.message for i in report.of("box_missing")] == [
            "expected exactly one box for node 'Ghost', found 0"
        ]

    def test_duplicate_node(self):
        base = [row.replace("D", "C") for row in GRID_BASE]
        final = [row.replace("D", "C") for row in STRAIGHT]
        report = check(base, final, {("A", "C"), ("B", "C")})
        assert "found 2" in report.of("box_missing")[0].message

    def test_broken_box_outline_is_not_a_box(self):
        base = put(GRID_BASE, 16, 1, " ")
        report = check(base, put(STRAIGHT, 16, 1, " "), STRAIGHT_EDGES)
        assert "'B'" in report.of("box_missing")[0].message

    def test_line_through_box_text(self):
        final = put(STRAIGHT, 3, 1, "│")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert "box 'A'" in report.of("box_damaged")[0].message

    def test_line_through_blank_box_interior(self):
        final = put(STRAIGHT, 1, 1, "│")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert report.of("box_damaged")

    def test_wrong_glyph_on_box_border(self):
        final = put(STRAIGHT, 3, 2, "┼")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert report.of("box_damaged")

    def test_overwritten_title(self):
        base = ["╔═══════╗", "║ Title ║", "╚═══════╝", *GRID_BASE]
        final = ["╔═══════╗", "║ Ti│le ║", "╚═══════╝", *STRAIGHT]
        report = check(base, final, STRAIGHT_EDGES)
        assert "title" in report.of("box_damaged")[0].message

    def test_unexpected_character_in_open_space(self):
        final = put(STRAIGHT, 8, 4, "?")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert "unexpected '?'" in report.of("box_damaged")[0].message

    def test_wrapped_node_name_is_matched(self):
        base = ["┌───────┐", "│ Send  │", "│ Email │", "└───────┘"]
        report = check(base, base, set())
        assert report.issues == []
        report = check(
            base + ["", "┌───┐", "│ B │", "└───┘"], base, {("Send Email", "B")}
        )
        assert not any("Send Email" in i.message for i in report.of("box_missing"))


class TestEdgeReading:
    """Comparing the edges in the picture with the edges in the input."""

    def test_shared_bus_implies_edges_nobody_asked_for(self):
        report = check(GRID_BASE, SHARED_BUS, STRAIGHT_EDGES)
        assert sorted(i.message for i in report.of("phantom_edge")) == [
            "picture shows 'A' -> 'D', which is not in the input",
            "picture shows 'B' -> 'C', which is not in the input",
        ]
        assert not report.of("missing_edge")

    def test_swapped_targets(self):
        report = check(GRID_BASE, CROSSING, STRAIGHT_EDGES)
        assert len(report.of("missing_edge")) == 2
        assert len(report.of("phantom_edge")) == 2

    def test_crossing_is_not_a_junction(self):
        # If ┼ were read as a junction, all four edges would appear drawn.
        report = check(GRID_BASE, CROSSING, ALL_FOUR_EDGES)
        assert len(report.of("missing_edge")) == 2

    def test_junction_is_only_assumed_when_a_line_cannot_stand_alone(self):
        # Give the fan's vertical trunk its own source: now ┼ is a crossing,
        # so A no longer reaches B and D.
        base = put(put(put(FAN_BASE, 5, 9, "┌───┐"), 5, 10, "│ E │"), 5, 11, "└───┘")
        final = put(put(put(FAN, 5, 9, "┌─┴─┐"), 5, 10, "│ E │"), 5, 11, "└───┘")
        final = put(put(final, 7, 7, "├"), 7, 8, "│")
        edges = {("A", "C"), ("E", "B"), ("E", "D")}
        report = check(base, final, edges)
        assert report.issues == []
        assert report.crossings == 1
        assert report.junctions == 0


class TestLegibility:
    """Lines crammed into touching columns."""

    def test_touching_vertical_lines(self):
        final = put(put(put(STRAIGHT, 4, 3, "│"), 4, 4, "│"), 4, 5, "│")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert len(report.of("adjacent_lines")) == 3
        assert report.of("adjacent_lines")[0].message.endswith("'││'")

    def test_touching_arrowheads(self):
        final = [row.replace("   ▼ ", "   ▼▼") for row in STRAIGHT]
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert any("▼▼" in i.message for i in report.warnings)

    def test_connected_neighbours_are_fine(self):
        # A one-column jog: └┐ are neighbours but they are the same line.
        base = ["┌───┐", "│ A │", "└───┘", "", "", "", " ┌───┐", " │ B │", " └───┘"]
        final = [
            "┌───┐",
            "│ A │",
            "└─┬─┘",
            "  │",
            "  └┐",
            "   ▼",
            " ┌───┐",
            " │ B │",
            " └───┘",
        ]
        report = check(base, final, {("A", "B")})
        assert report.issues == []

    def test_warnings_are_not_errors(self):
        final = put(put(put(STRAIGHT, 4, 3, "│"), 4, 4, "│"), 4, 5, "│")
        report = check(GRID_BASE, final, STRAIGHT_EDGES)
        assert report.warnings
        assert all(i.code != "adjacent_lines" for i in report.errors)


class TestReporting:
    """Helpers used in failure messages and by the scorecard."""

    def test_issue_text(self):
        assert str(Issue("stray_line", "oops", 3, 4)) == (
            "[stray_line] at (x=3, y=4) oops"
        )
        assert str(Issue("missing_edge", "gone")) == "[missing_edge] gone"

    def test_box_sides(self):
        box = Box("A", 2, 1, 5, 3)
        assert box.side_of(2, 1) == "corner"
        assert box.side_of(4, 1) == "top"
        assert box.side_of(4, 3) == "bottom"
        assert box.side_of(2, 2) == "left"
        assert box.side_of(6, 2) == "right"
        assert box.side_of(4, 2) == "interior"
        assert box.side_of(9, 9) is None

    def test_explain_lists_issues_then_the_picture(self):
        report = check(GRID_BASE, put(STRAIGHT, 3, 4, " "), STRAIGHT_EDGES)
        report.label = "demo"
        text = report.explain("missing_edge")
        assert text.startswith("1 issue(s) in demo:")
        assert "cannot trace 'A' -> 'C'" in text
        assert "  1 │  A  │   │  B  │" in text
        assert "and" in report.explain(limit=1)
        assert report.counts()["dangling_line"] == 2

    def test_expected_edges_are_normalized(self):
        text = "Send   Email -> B\nSend Email -> B"
        assert expected_edges_of(text) == {("Send Email", "B")}
        assert normalize_name("  a   b ") == "a b"

    def test_debug_and_plain_renders_agree(self):
        assert not check_diagram("A -> B\nA -> C", "LR").of("debug_mismatch")
