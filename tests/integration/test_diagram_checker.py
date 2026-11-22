"""
Tests for the diagram checker itself.

The complex-diagram tests are only as trustworthy as the checker behind them,
so each rule is pinned here against small hand-drawn pictures: a clean
picture must pass, and each kind of defect must be reported under its own
code. The pictures are drawn by hand (not rendered) so these tests do not
depend on how the renderer currently routes anything.
"""

from typing import List

from retroflow.models import GroupDefinition

from .diagram_checker import (
    Box,
    GroupBox,
    Issue,
    analyze_rendering,
    check_diagram,
    expected_edges_of,
    expected_groups_of,
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

# A -> B where A sits in a group called "Team" and the line passes under the
# dashed border. The border is at x=0 and x=10, rows 1 to 9; A keeps two
# cells from it on every side.
GROUP_BASE = [
    "   Team",
    "┏╍╍╍╍╍╍╍╍╍┓",
    "╏         ╏",
    "╏         ╏",
    "╏  ┌───┐  ╏      ┌───┐",
    "╏  │ A │  ╏      │ B │",
    "╏  └───┘  ╏      └───┘",
    "╏         ╏",
    "╏         ╏",
    "┗╍╍╍╍╍╍╍╍╍┛",
]
GROUP_PASS_UNDER = [
    *GROUP_BASE[:5],
    "╏  │ A │──╏─────►│ B │",
    *GROUP_BASE[6:],
]
TEAM = [GroupDefinition("Team", ["A"])]

# The same group with its shadow (one column to the right, one row below).
GROUP_SHADOW_BASE = [
    "   Team",
    "┏╍╍╍╍╍╍╍╍╍┓",
    "╏         ╏░",
    "╏         ╏░",
    "╏  ┌───┐  ╏░     ┌───┐",
    "╏  │ A │  ╏░     │ B │",
    "╏  └───┘  ╏░     └───┘",
    "╏         ╏░",
    "╏         ╏░",
    "┗╍╍╍╍╍╍╍╍╍┛░",
    " ░░░░░░░░░░░",
]

# Two members, A and C, in a taller group: room for a line between them.
PAIR_BASE = [
    "       Team",
    "┏╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍┓",
    "╏                 ╏",
    "╏                 ╏",
    "╏  ┌───┐   ┌───┐  ╏",
    "╏  │ A │   │ C │  ╏",
    "╏  └───┘   └───┘  ╏",
    "╏                 ╏",
    "╏                 ╏",
    "╏                 ╏",
    "┗╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍┛",
    "",
    "",
]
# A -> C by an arc that stays inside the group.
PAIR_ARC_INSIDE = [
    *PAIR_BASE[:6],
    "╏  └─┬─┘   └───┘  ╏",
    "╏    │       ▲    ╏",
    "╏    └───────┘    ╏",
    *PAIR_BASE[9:],
]
# The same arc, but dipping out of the group and back in.
PAIR_ARC_OUTSIDE = [
    *PAIR_BASE[:6],
    "╏  └─┬─┘   └───┘  ╏",
    "╏    │       ▲    ╏",
    "╏    │       │    ╏",
    "╏    │       │    ╏",
    "┗╍╍╍╍│╍╍╍╍╍╍╍│╍╍╍╍┛",
    "     │       │",
    "     └───────┘",
]
PAIR = [GroupDefinition("Team", ["A", "C"])]


def check(base: List[str], final: List[str], edges, groups=None):
    return analyze_rendering(base, "\n".join(final), set(edges), groups)


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
        final = put(GROUP_PASS_UNDER, 10, 5, "─")
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
        final = put(GROUP_PASS_UNDER, 11, 5, "      ")
        report = check(GROUP_BASE, final, {("A", "B")})
        assert report.of("dangling_line")
        assert report.of("missing_edge")

    def test_line_running_along_a_group_border(self):
        final = put(GROUP_PASS_UNDER, 10, 4, "│")
        report = check(GROUP_BASE, final, {("A", "B")})
        assert report.of("group_border_damaged")

    def test_arrowhead_drawn_on_a_group_border(self):
        final = put(GROUP_PASS_UNDER, 10, 5, "►")
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


class TestGroupBoxes:
    """Group boxes: found, framed correctly, and given room."""

    def test_clean_group_is_found_and_named(self):
        final = put(GROUP_PASS_UNDER, 10, 5, "─")
        report = check(GROUP_BASE, final, {("A", "B")}, TEAM)
        assert report.issues == []
        assert report.group_boxes == [GroupBox(0, 1, 11, 9, False, "Team")]

    def test_group_is_found_without_being_told_about_it(self):
        report = check(GROUP_BASE, GROUP_PASS_UNDER, {("A", "B")})
        assert report.issues == []
        assert report.group_boxes == [GroupBox(0, 1, 11, 9, False, "")]

    def test_shadow_is_part_of_the_group_box(self):
        report = check(GROUP_SHADOW_BASE, GROUP_SHADOW_BASE, set())
        assert report.group_boxes[0].shadow
        assert report.group_boxes[0].footprint() == (0, 1, 11, 10)

    def test_arc_between_members_inside_the_group_is_clean(self):
        report = check(PAIR_BASE, PAIR_ARC_INSIDE, {("A", "C")}, PAIR)
        assert report.issues == []

    # ── group_missing ───────────────────────────────────────────────────

    def test_member_outside_its_group(self):
        groups = [GroupDefinition("Team", ["A", "B"])]
        report = check(GROUP_BASE, GROUP_PASS_UNDER, {("A", "B")}, groups)
        assert "no dashed box encloses" in report.of("group_missing")[0].message

    def test_group_border_with_a_hole_is_not_a_group_box(self):
        base = put(GROUP_BASE, 5, 1, " ")
        report = check(base, put(GROUP_PASS_UNDER, 5, 1, " "), {("A", "B")}, TEAM)
        assert report.of("group_missing")
        assert report.group_boxes == []

    def test_missing_title(self):
        base = put(GROUP_BASE, 0, 0, "       ")
        final = put(GROUP_PASS_UNDER, 0, 0, "       ")
        report = check(base, final, {("A", "B")}, TEAM)
        assert "title of group 'Team'" in report.of("group_missing")[0].message

    def test_title_beside_instead_of_above_its_box(self):
        base = put(put(GROUP_BASE, 0, 0, "       "), 12, 0, "Team")
        final = put(put(GROUP_PASS_UNDER, 0, 0, "       "), 12, 0, "Team")
        report = check(base, final, {("A", "B")}, TEAM)
        assert report.of("group_missing")

    def test_group_on_the_top_row_has_no_room_for_a_title(self):
        report = check(GROUP_BASE[1:], GROUP_PASS_UNDER[1:], {("A", "B")}, TEAM)
        assert report.of("group_missing")

    # ── group_overlap ───────────────────────────────────────────────────

    def test_outsider_framed_by_a_group(self):
        report = check(PAIR_BASE, PAIR_ARC_INSIDE, {("A", "C")}, TEAM)
        message = report.of("group_overlap")[0].message
        assert message == "box 'C' is inside group 'Team' without being a member"

    def test_nested_group_boxes_overlap(self):
        base = put(put(put(PAIR_BASE, 9, 3, "┏╍╍╍╍╍╍┓"), 9, 7, "┗╍╍╍╍╍╍┛"), 9, 4, "╏")
        base = put(put(put(base, 9, 5, "╏"), 9, 6, "╏"), 16, 4, "╏")
        base = put(put(base, 16, 5, "╏"), 16, 6, "╏")
        report = check(base, base, set())
        assert len(report.group_boxes) == 2
        assert "overlap" in report.of("group_overlap")[0].message

    def test_group_box_right_after_another_groups_shadow(self):
        left = ["┏╍╍╍╍┓", "╏    ╏░", "╏    ╏░", "┗╍╍╍╍┛░", " ░░░░░░"]
        base = [row.ljust(7) + other for row, other in zip(left, left)]
        report = check(base, base, set())
        assert len(report.group_boxes) == 2
        assert [issue.code for issue in report.issues] == ["group_crowded"]
        spaced = [row.ljust(8) + other for row, other in zip(left, left)]
        assert check(spaced, spaced, set()).issues == []

    # ── group_crowded ───────────────────────────────────────────────────

    def test_group_boxes_side_by_side_without_a_gap(self):
        left = ["┏╍╍╍╍┓", "╏    ╏", "╏    ╏", "┗╍╍╍╍┛"]
        base = [row + row for row in left]
        report = check(base, base, set())
        assert "touch" in report.of("group_crowded")[0].message
        spaced = [row + " " + row for row in left]
        assert check(spaced, spaced, set()).issues == []

    def test_member_too_close_to_the_border(self):
        base = ["┏╍╍╍╍╍╍╍┓", "╏ ┌───┐ ╏", "╏ │ A │ ╏", "╏ └───┘ ╏", "┗╍╍╍╍╍╍╍┛"]
        final = [*base, "", "┌───┐", "│ B │", "└───┘"]
        report = check(final, final, {("A", "B")})
        message = report.of("group_crowded")[0].message
        assert message == (
            "box 'A' is too close to the border of the group box at (x=0, y=0)"
        )

    def test_outsider_touching_a_group_box(self):
        base = [
            row.replace("╏      ┌", "╏┌").replace("╏      │", "╏│")
            for row in GROUP_BASE
        ]
        base = [row.replace("╏      └", "╏└") for row in base]
        report = check(base, base, {("A", "B")}, TEAM)
        assert report.of("group_crowded")[0].message == "box 'B' touches group 'Team'"

    def test_outsider_shadow_touching_a_group_title(self):
        base = ["┌───┐", "│ B │░", "└───┘░", " ░░░░░ Team", *GROUP_BASE[1:4]]
        base += ["╏  ┌───┐  ╏", "╏  │ A │  ╏", "╏  └───┘  ╏", *GROUP_BASE[7:]]
        report = check(base, base, {("A", "B")}, TEAM)
        assert any("touches group" in i.message for i in report.of("group_crowded"))

    def test_line_running_beside_a_border(self):
        beside = put(put(GROUP_PASS_UNDER, 11, 5, "┬"), 11, 6, "│")
        report = check(GROUP_BASE, beside, {("A", "B")}, TEAM)
        messages = [issue.message for issue in report.of("group_crowded")]
        assert "a line runs along the right border of group 'Team'" in messages

        clear = put(put(GROUP_PASS_UNDER, 12, 5, "┬"), 12, 6, "│")
        report = check(GROUP_BASE, clear, {("A", "B")}, TEAM)
        assert not report.of("group_crowded")

    def test_line_running_beside_a_shadow(self):
        base = GROUP_SHADOW_BASE
        final = put(base, 3, 5, "│ A │────────►")
        on_shadow = put(put(final, 11, 5, "┬"), 11, 6, "│")
        assert check(base, on_shadow, {("A", "B")}).of("group_crowded")
        beside = put(put(final, 12, 5, "┬"), 12, 6, "│")
        assert check(base, beside, {("A", "B")}).of("group_crowded")
        clear = put(put(final, 13, 5, "┬"), 13, 6, "│")
        assert not check(base, clear, {("A", "B")}).of("group_crowded")

    def test_line_running_along_the_inside_of_the_bottom_border(self):
        final = put(PAIR_ARC_INSIDE, 5, 8, "│       │")
        final = put(final, 5, 9, "└───────┘")
        report = check(PAIR_BASE, final, {("A", "C")}, PAIR)
        messages = [issue.message for issue in report.of("group_crowded")]
        assert messages == ["a line runs along the bottom border of group 'Team'"]

    def test_line_running_along_the_top_and_left_borders(self):
        final = put(GROUP_PASS_UNDER, 2, 2, "┌──")
        final = put(put(final, 1, 3, "│"), 1, 2, "┌─")
        messages = {
            issue.message
            for issue in check(GROUP_BASE, final, {("A", "B")}, TEAM).of(
                "group_crowded"
            )
        }
        assert "a line runs along the top border of group 'Team'" in messages
        assert "a line runs along the left border of group 'Team'" in messages

    def test_arrowhead_right_at_a_border(self):
        base = [
            "┏╍╍╍╍╍╍╍┓",
            "╏       ╏",
            "╏ ┌───┐ ╏",
            "╏ │ A │ ╏",
            "╏ └───┘ ╏",
            "┗╍╍╍╍╍╍╍┛",
        ]
        base = [("     " + row) for row in base]
        base = put(put(put(base, 0, 2, "┌──"), 0, 3, "│B│"), 0, 4, "└──")
        base = put(put(put(base, 0, 2, "┌─┐"), 0, 3, "│B│"), 0, 4, "└─┘")
        final = put(base, 3, 3, "───►")
        report = check(base, final, {("B", "A")})
        messages = [issue.message for issue in report.of("group_crowded")]
        assert any("an arrowhead touches the border" in m for m in messages)

    def test_line_touching_a_title(self):
        final = put(put(GROUP_PASS_UNDER, 7, 0, "│"), 7, 1, "│")
        report = check(GROUP_BASE, final, {("A", "B")}, TEAM)
        assert "'│' touches the title of group 'Team'" in [
            issue.message for issue in report.of("group_crowded")
        ]

    def test_line_through_the_blank_between_two_title_words(self):
        groups = [GroupDefinition("My Team", ["A"])]
        base = put(GROUP_BASE, 2, 0, "My Team")
        final = put(put(GROUP_PASS_UNDER, 2, 0, "My│Team"), 4, 1, "│")
        report = check(base, final, {("A", "B")}, groups)
        assert "title" in report.of("box_damaged")[0].message

    def test_line_right_above_a_title(self):
        base = ["", *GROUP_BASE]
        final = put(["", *GROUP_PASS_UNDER], 2, 0, "──────")
        report = check(base, final, {("A", "B")}, TEAM)
        assert "a line runs right above the title of group 'Team'" in [
            issue.message for issue in report.of("group_crowded")
        ]

    # ── group_crossing ──────────────────────────────────────────────────

    def test_edge_between_members_leaving_the_group(self):
        report = check(PAIR_BASE, PAIR_ARC_OUTSIDE, {("A", "C")}, PAIR)
        assert [issue.message for issue in report.of("group_crossing")] == [
            "a line between members leaves group 'Team'"
        ]
        assert report.drawn_edges == {("A", "C")}
        assert not report.errors

    def test_edge_between_outsiders_passing_through_a_group(self):
        base = [
            "               Team",
            "          ┏╍╍╍╍╍╍╍╍╍┓",
            "┌───┐     ╏         ╏     ┌───┐",
            "│ X │     ╏         ╏     │ Y │",
            "└───┘     ╏  ┌───┐  ╏     └───┘",
            "          ╏  │ A │  ╏",
            "          ╏  └───┘  ╏",
            "          ╏         ╏",
            "          ╏         ╏",
            "          ┗╍╍╍╍╍╍╍╍╍┛",
        ]
        final = put(base, 5, 3, "─────╏─────────╏────►")
        report = check(base, final, {("X", "Y"), ("A", "A")}, TEAM)
        assert [issue.message for issue in report.of("group_crossing")] == [
            "a line passes through group 'Team'"
        ]

    def test_edge_leaving_the_group_is_not_a_needless_crossing(self):
        report = check(GROUP_BASE, GROUP_PASS_UNDER, {("A", "B")}, TEAM)
        assert not report.of("group_crossing")

    def test_group_warnings_are_not_errors(self):
        report = check(PAIR_BASE, PAIR_ARC_OUTSIDE, {("A", "C")}, PAIR)
        assert report.warnings and not report.errors


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

    def test_expected_groups_come_from_the_input(self):
        groups = expected_groups_of("[Team: A B]\nA -> B\nB -> C")
        assert [(group.name, group.members) for group in groups] == [
            ("Team", ["A", "B"])
        ]
        assert expected_groups_of("A -> B") == []

    def test_group_box_geometry(self):
        group = GroupBox(2, 1, 6, 4)
        assert (group.right, group.bottom) == (7, 4)
        assert group.footprint() == (2, 1, 7, 4)
        assert GroupBox(2, 1, 6, 4, shadow=True).footprint() == (2, 1, 8, 5)
        cells = group.border_cells()
        assert cells[(2, 1)] == cells[(7, 4)] == "corner"
        assert (cells[(4, 1)], cells[(4, 4)]) == ("top", "bottom")
        assert (cells[(2, 2)], cells[(7, 3)]) == ("left", "right")
        assert (4, 2) not in cells
        assert GroupBox(0, 0, 9, 7).encloses(Box("A", 2, 2, 5, 3))
        assert not GroupBox(0, 0, 9, 7).encloses(Box("A", 0, 2, 5, 3))

    def test_debug_and_plain_renders_agree(self):
        assert not check_diagram("A -> B\nA -> C", "LR").of("debug_mismatch")
