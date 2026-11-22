"""
Integration tests: group boxes.

A group box is a dashed frame around some of the nodes, with a title on the
row above it. It is only helpful when it is unmistakable which boxes it
frames and which lines leave it, so these tests pin four promises:

    ┌┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┐      1. every group is drawn, under its title, around
    ┆                ┆░        exactly its own members
    ┆  ┌────────┐    ┆░     2. nothing overlaps a group border, and whatever
    ┆  │ member │──────►       is near one keeps a readable distance
    ┆  └────────┘░   ┆░     3. a line crosses a border only when its edge
    ┆                ┆░        really leaves or enters the group
    └┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘░     4. adding groups never costs an edge, a box or
     ░░░░░░░░░░░░░░░░░░        the look of a diagram that has no groups

The first three are checked twice, by two independent readers: the checker,
which only reads the finished *picture*, and the geometry tests here, which
only read the planner's *numbers*. The diagrams live in diagram_corpus.py
(``SIMPLE_GROUP_CASES``, ``COMPLEX_GROUP_CASES``, ``RANDOM_GROUP_CASES``); the
simple ones are also pinned character for character by the golden tests.

To look at the pictures themselves:

    uv run python manual_tests/render_corpus.py groups_
"""

import random
from functools import lru_cache
from typing import Dict, List, Tuple

import pytest

from retroflow import FlowchartGenerator
from retroflow.layout import LayoutResult, NodeLayout
from retroflow.route_planner import (
    PlannerOptions,
    RoutePlan,
    RoutePlanner,
    assign_ranks,
)

from .diagram_checker import (
    ARROW_HEADS,
    LINE_ARMS,
    DiagramReport,
    check_diagram,
    check_planned_diagram,
    expected_edges_of,
    expected_groups_of,
)
from .diagram_corpus import (
    COMPLEX_CASES,
    COMPLEX_GROUP_CASES,
    GROUP_CASES,
    SIMPLE_CASES,
    SIMPLE_GROUP_CASES,
    rendering_id,
    renderings,
)

GROUP_RENDERINGS = renderings(GROUP_CASES)
SIMPLE_GROUP_RENDERINGS = renderings(SIMPLE_GROUP_CASES)
COMPLEX_GROUP_RENDERINGS = renderings(COMPLEX_GROUP_CASES)

_CASES_BY_NAME = {case.name: case for case in GROUP_CASES}

GROUP_ERRORS = ("group_missing", "group_overlap", "group_border_damaged")
GROUP_WARNINGS = ("group_crowded", "group_crossing")


@lru_cache(maxsize=None)
def _report(case_name: str, direction: str) -> DiagramReport:
    """Render one grouped diagram through ``generate()`` and check it."""
    case = _CASES_BY_NAME[case_name]
    return check_diagram(
        case.text, direction, label=f"{case_name}-{direction}", **case.options
    )


def _assert_none(rendering, *codes: str) -> None:
    case, direction = rendering
    report = _report(case.name, direction)
    assert not report.of(*codes), report.explain(*codes)


# ── the picture, as the checker reads it ────────────────────────────────


@pytest.mark.parametrize("rendering", GROUP_RENDERINGS, ids=rendering_id)
class TestGroupBoxesInThePicture:
    """Every grouped diagram, simple, complex and random, one promise at a time."""

    def test_every_group_frames_its_members_under_its_title(self, rendering):
        """One dashed box per group, around all of its members, title on top."""
        _assert_none(rendering, "group_missing")

        case, direction = rendering
        report = _report(case.name, direction)
        wanted = {group.name for group in expected_groups_of(case.text)}
        assert {box.name for box in report.group_boxes} == wanted

    def test_group_boxes_do_not_overlap_boxes_or_each_other(self, rendering):
        """No outsider inside a group, no box on a border, no two groups overlapping."""
        _assert_none(rendering, "group_overlap")

    def test_lines_only_cross_borders_at_right_angles(self, rendering):
        """No line runs along a border, turns on one, or ends on one."""
        _assert_none(rendering, "group_border_damaged", "box_damaged")

    def test_everything_keeps_its_distance_from_a_group_box(self, rendering):
        """Members, outsiders, lines, arrowheads and titles all have a buffer."""
        _assert_none(rendering, "group_crowded")

    def test_lines_cross_a_border_only_when_the_edge_leaves_the_group(self, rendering):
        """Edges between members stay inside; other edges go around."""
        _assert_none(rendering, "group_crossing")

    def test_diagram_is_clean_in_every_other_respect(self, rendering):
        """Groups must not cost anything else: edges, arrowheads, legibility."""
        case, direction = rendering
        report = _report(case.name, direction)
        codes = sorted({issue.code for issue in report.issues})
        assert not report.issues, report.explain(*codes)

    def test_planned_renderer_draws_it(self, rendering):
        """Only the planned renderer routes around group boxes."""
        case, direction = rendering
        generator = FlowchartGenerator(direction=direction, **case.options)
        generator.generate(case.text)
        assert generator.last_renderer == "planned"


# ── the picture, read directly ──────────────────────────────────────────


def _dashed_cells(output: str) -> List[Tuple[int, int, str]]:
    return [
        (x, y, glyph)
        for y, row in enumerate(output.split("\n"))
        for x, glyph in enumerate(row)
        if glyph in "┆┄"
    ]


@pytest.mark.parametrize("rendering", GROUP_RENDERINGS, ids=rendering_id)
class TestGroupBordersGlyphByGlyph:
    """Simple facts about the text that need no line tracing at all."""

    def test_no_line_runs_beside_a_dashed_border(self, rendering):
        """
        ``│`` never sits left or right of ``┆``, ``─`` never above or below ``┄``.

        With a shadow, the cell after the border is the shadow, so the line
        must stay off the shadow and off the cell after it as well.
        """
        case, direction = rendering
        report = _report(case.name, direction)
        rows = report.output.split("\n")
        shadow = 1 if case.options.get("shadow", True) else 0

        def at(x: int, y: int) -> str:
            if 0 <= y < len(rows) and 0 <= x < len(rows[y]):
                return rows[y][x]
            return " "

        def vertical(glyph: str) -> bool:
            return any(arm in LINE_ARMS.get(glyph, "") for arm in "UD") or (
                ARROW_HEADS.get(glyph, "") in ("U", "D")
            )

        def horizontal(glyph: str) -> bool:
            return any(arm in LINE_ARMS.get(glyph, "") for arm in "LR") or (
                ARROW_HEADS.get(glyph, "") in ("L", "R")
            )

        offenders = []
        for x, y, glyph in _dashed_cells(report.output):
            if glyph == "┆":
                near = [at(x - 1, y), at(x + 1, y), at(x + 1 + shadow, y)]
                if any(vertical(g) for g in near):
                    offenders.append((x, y))
            else:
                near = [at(x, y - 1), at(x, y + 1), at(x, y + 1 + shadow)]
                if any(horizontal(g) for g in near):
                    offenders.append((x, y))
        assert not offenders, report.explain()

    def test_every_title_appears_exactly_once_on_a_row_of_its_own(self, rendering):
        """A title is never split, repeated or mixed up with box text."""
        case, direction = rendering
        report = _report(case.name, direction)
        rows = report.output.split("\n")
        for group in report.group_boxes:
            title_row = rows[group.y - 1]
            start = title_row.find(group.name, group.x, group.right + 1)
            assert start >= 0, report.explain()
            before = title_row[start - 1] if start else " "
            after = title_row[start + len(group.name) : start + len(group.name) + 1]
            assert before == " " and after in ("", " "), report.explain()

    def test_group_corners_are_never_touched(self, rendering):
        """The four corners of every group box survive edge drawing."""
        case, direction = rendering
        report = _report(case.name, direction)
        rows = report.output.split("\n")
        for group in report.group_boxes:
            corners = (
                rows[group.y][group.x],
                rows[group.y][group.right],
                rows[group.bottom][group.x],
                rows[group.bottom][group.right],
            )
            assert corners == ("┌", "┐", "└", "┘"), report.explain()


# ── the planner's numbers, without looking at the picture ───────────────


@lru_cache(maxsize=None)
def _case_plan(case_name: str, direction: str):
    """The plan of one corpus diagram (shared by the tests of that rendering)."""
    case = _CASES_BY_NAME[case_name]
    return _plan(case.text, direction, case.options)


def _plan(case_text: str, direction: str, options: Dict[str, object]):
    """Plan a diagram and return (RoutePlan, group definitions)."""
    generator = FlowchartGenerator(direction=direction, **options)
    parsed = generator.parser.parse_with_groups(case_text)
    layers = assign_ranks(parsed.connections, parsed.groups, generator.layout_engine)
    nodes = LayoutResult(
        nodes={name: NodeLayout(name=name) for layer in layers for name in layer}
    )
    dimensions = generator.position_calculator.calculate_all_box_dimensions(nodes)
    planner = RoutePlanner(
        PlannerOptions(
            direction=direction,
            horizontal_spacing=generator.horizontal_spacing,
            vertical_spacing=generator.vertical_spacing,
            shadow=generator.shadow,
        )
    )
    plan = planner.plan(parsed.connections, parsed.groups, layers, dimensions)
    return plan, parsed.groups


def _node_rect(plan: RoutePlan, name: str) -> Tuple[int, int, int, int]:
    x, y = plan.box_positions[name]
    dims = plan.box_dimensions[name]
    return (x, y, x + dims.width - 1, y + dims.height - 1)


@pytest.mark.parametrize("rendering", GROUP_RENDERINGS, ids=rendering_id)
class TestGroupGeometryInThePlan:
    """The same promises, verified on coordinates instead of glyphs."""

    def test_members_are_inside_with_padding_and_outsiders_are_outside(self, rendering):
        case, direction = rendering
        plan, groups = _case_plan(case.name, direction)
        shadow = 1 if case.options.get("shadow", True) else 0
        members_of = {group.name: set(group.members) for group in groups}

        for boundary in plan.group_boundaries:
            # GroupBoundary includes the title row; the dashed box starts below.
            left, top = boundary.x, boundary.y + 1
            right = boundary.x + boundary.width - 1
            bottom = boundary.y + boundary.height - 1
            assert set(boundary.members) == members_of[boundary.name]

            for name in plan.box_positions:
                x0, y0, x1, y1 = _node_rect(plan, name)
                if name in members_of[boundary.name]:
                    gaps = (x0 - left, y0 - top, right - x1, bottom - y1)
                    assert min(gaps) >= 3, f"{name} too close to {boundary.name}"
                else:
                    outside = (
                        x1 + shadow < left - 1
                        or x0 > right + shadow + 1
                        or y1 + shadow < top - 2  # the title row is in between
                        or y0 > bottom + shadow + 1
                    )
                    assert outside, f"{name} intrudes on group {boundary.name}"

    def test_group_boxes_are_disjoint(self, rendering):
        case, direction = rendering
        plan, _ = _case_plan(case.name, direction)
        shadow = 1 if case.options.get("shadow", True) else 0
        rects = [
            (b.name, b.x, b.y, b.x + b.width - 1 + shadow, b.y + b.height - 1 + shadow)
            for b in plan.group_boundaries
        ]
        for index, (name, x0, y0, x1, y1) in enumerate(rects):
            for other, ox0, oy0, ox1, oy1 in rects[index + 1 :]:
                apart = x1 + 1 < ox0 or ox1 + 1 < x0 or y1 + 1 < oy0 or oy1 + 1 < y0
                assert apart, f"groups {name} and {other} overlap or touch"

    def test_title_fits_above_its_own_box(self, rendering):
        case, direction = rendering
        plan, _ = _case_plan(case.name, direction)
        for boundary in plan.group_boundaries:
            start = plan.group_title_x[boundary.name]
            assert boundary.x <= start
            assert start + len(boundary.name) <= boundary.x + boundary.width

    def test_no_wire_cell_lies_on_a_border_it_does_not_cross(self, rendering):
        """Wires only meet a border cell as a straight perpendicular stroke."""
        case, direction = rendering
        plan, _ = _case_plan(case.name, direction)
        wires = dict(plan.grid.cells())
        for boundary in plan.group_boundaries:
            left, top = boundary.x, boundary.y + 1
            right = boundary.x + boundary.width - 1
            bottom = boundary.y + boundary.height - 1
            for (x, y), glyph in wires.items():
                on_side = x in (left, right) and top <= y <= bottom
                on_end = y in (top, bottom) and left <= x <= right
                if on_side and on_end:
                    pytest.fail(f"wire on a corner of group {boundary.name}")
                if on_side:
                    assert glyph == "─", f"'{glyph}' on a side of {boundary.name}"
                if on_end:
                    assert glyph == "│", f"'{glyph}' on an end of {boundary.name}"


# ── edges between the members of one group stay inside it ───────────────


class TestEdgesInsideAGroup:
    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_arc_between_far_apart_members_uses_an_inner_track(self, direction):
        plan, _ = _plan("[G: A B C]\nA -> B\nB -> C\nA -> C", direction, {})
        assert plan.tracks_per_group == {"G": 1}

    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_group_without_inner_edges_has_no_inner_tracks(self, direction):
        plan, _ = _plan("[G: A B]\nA -> C\nB -> C", direction, {})
        assert plan.tracks_per_group == {}

    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_self_loop_of_a_member_stays_inside(self, direction):
        report = check_planned_diagram("[G: A]\nIn -> A\nA -> A\nA -> Out", direction)
        assert not report.issues, report.explain()
        group = report.group_boxes[0]
        # Exactly two lines cross the border: the one in and the one out.
        rows = report.output.split("\n")
        crossings = sum(
            1 for (x, y), side in group.border_cells().items() if rows[y][x] in "│─"
        )
        assert crossings == 2, report.explain()

    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_two_way_pair_does_not_cross_itself(self, direction):
        """A -> C and C -> A nest; they never need a crossing."""
        text = "[G: A B C]\nA -> C\nC -> A\nA -> B\nB -> C"
        report = check_planned_diagram(text, direction)
        assert not report.issues, report.explain()
        assert report.crossings == 0, report.explain()

    def test_one_inner_track_costs_no_extra_height(self):
        """With a shadow, a single arc fits in the rows a TB group already has."""
        plain, _ = _plan("[G: A B C]\nA -> B\nB -> C", "TB", {})
        arced, _ = _plan("[G: A B C]\nA -> B\nB -> C\nA -> C", "TB", {})
        assert arced.group_boundaries[0].height == plain.group_boundaries[0].height

    def test_group_grows_by_one_row_per_extra_inner_track(self):
        chain = "[G: A B C D]\nA -> B\nB -> C\nC -> D\n"
        one, _ = _plan(chain + "A -> C", "TB", {})
        two, _ = _plan(chain + "A -> C\nA -> D", "TB", {})
        assert one.tracks_per_group == {"G": 1}
        assert two.tracks_per_group == {"G": 2}
        assert two.group_boundaries[0].height == one.group_boundaries[0].height + 1

    def test_lr_title_still_fits_when_inner_tracks_lengthen_the_box(self):
        text = "[A Title Longer Than The Box: A B C]\nA -> B\nB -> C\nA -> C"
        report = check_planned_diagram(text, "LR")
        assert not report.issues, report.explain()


# ── groups do not change anything about ungrouped diagrams ──────────────


def _without_groups(text: str) -> str:
    return "\n".join(
        line for line in text.split("\n") if not line.strip().startswith("[")
    )


class TestGroupsLeaveEverythingElseAlone:
    @pytest.mark.parametrize(
        "rendering", renderings(SIMPLE_CASES + COMPLEX_CASES[::6]), ids=rendering_id
    )
    def test_ungrouped_diagram_never_contains_group_glyphs(self, rendering):
        case, direction = rendering
        output = FlowchartGenerator(direction=direction, **case.options).generate(
            case.text
        )
        assert "┆" not in output and "┄" not in output

    @pytest.mark.parametrize("rendering", COMPLEX_GROUP_RENDERINGS, ids=rendering_id)
    def test_grouping_keeps_every_box_and_every_edge(self, rendering):
        """The grouped picture shows the same graph as the input without groups."""
        case, direction = rendering
        grouped = _report(case.name, direction)
        edges = expected_edges_of(_without_groups(case.text))
        assert set(grouped.boxes) == {name for edge in edges for name in edge}
        assert grouped.drawn_edges == edges

    @pytest.mark.parametrize("rendering", SIMPLE_GROUP_RENDERINGS, ids=rendering_id)
    def test_simple_grouped_picture_matches_its_ungrouped_twin(self, rendering):
        """Same boxes and same edges as the diagram drawn without its groups."""
        case, direction = rendering
        grouped = _report(case.name, direction)
        plain = check_diagram(_without_groups(case.text), direction, **case.options)
        assert set(grouped.boxes) == set(plain.boxes)
        assert grouped.drawn_edges == plain.drawn_edges

    @pytest.mark.parametrize("rendering", SIMPLE_GROUP_RENDERINGS, ids=rendering_id)
    def test_members_of_a_group_share_a_row_or_a_column(self, rendering):
        """Groups run across the flow: side by side in TB, stacked in LR."""
        case, direction = rendering
        report = _report(case.name, direction)
        for group in expected_groups_of(case.text):
            boxes = [report.boxes[name] for name in group.members]
            starts = {box.y if direction == "TB" else box.x for box in boxes}
            assert len(starts) == 1, report.explain()


# ── seeded fuzzing, always with groups ──────────────────────────────────

_FUZZ_NAMES = (
    "Api",
    "Queue",
    "Cache",
    "Billing Service",
    "Edge Router",
    "A",
    "Long Name For A Node That Wraps",
    "Db",
    "Worker Pool",
)
_FUZZ_TITLES = ("G", "Group", "A Rather Long Group Title Here", "Data Tier", "Zone")


def group_fuzz_input(seed: int) -> Tuple[str, Dict[str, object]]:
    """
    A seeded random diagram that always has groups.

    Half of the seeds scatter the members of a group all over the graph, so
    groups pull together nodes that would otherwise sit layers apart, with
    plenty of edges inside groups, around them and between them. Only
    ``Random.random()`` is used, so a seed means the same diagram on every
    supported Python version.
    """
    rng = random.Random(seed)

    def below(limit: int) -> int:
        return int(rng.random() * limit)

    def pick(choices):
        return choices[below(len(choices))]

    count = 2 + below(12)
    names = [f"{pick(_FUZZ_NAMES)} {i}" for i in range(count)]
    edges: List[Tuple[str, str]] = []
    for i in range(1, count):
        edges.append((names[below(i)], names[i]))
    for _ in range(below(2 * count + 1)):
        source = below(count)
        target = source if rng.random() < 0.12 else below(count)
        edges.append((names[source], names[target]))

    free = list(names)
    lines: List[str] = []
    scattered = rng.random() < 0.5
    for index in range(1 + below(4)):
        if not free:
            break
        size = min(len(free), 1 + below(4))
        if scattered:
            members = [free.pop(below(len(free))) for _ in range(size)]
        else:
            start = below(len(free) - size + 1)
            members = free[start : start + size]
            del free[start : start + size]
        lines.append(f"[{pick(_FUZZ_TITLES)} {index}: {' '.join(members)}]")
    lines += [f"{source} -> {target}" for source, target in edges]

    options = {
        "direction": pick(("TB", "LR")),
        "shadow": rng.random() < 0.7,
        "rounded": rng.random() < 0.3,
        "compact": rng.random() < 0.7,
        "horizontal_spacing": pick((0, 2, 4, 12, 20)),
        "vertical_spacing": pick((0, 1, 3, 6)),
        "max_text_width": pick((3, 12, 22, 40)),
        "min_box_width": pick((1, 10, 18)),
        "title": pick((None, None, "T", "A Very Long Diagram Title That Is Wide")),
    }
    return "\n".join(lines), options


@pytest.mark.parametrize("seed", range(250))
def test_fuzzed_grouped_diagram_is_clean(seed):
    """Random graphs, groups and options: always a clean picture, never a crash."""
    text, options = group_fuzz_input(seed)
    direction = options.pop("direction")
    report = check_planned_diagram(
        text, direction, label=f"group fuzz {seed}", **options
    )
    codes = sorted({issue.code for issue in report.issues})
    assert not report.issues, f"{options}\n{text}\n{report.explain(*codes)}"


@pytest.mark.parametrize("seed", range(0, 250, 5))
def test_fuzzed_grouped_diagram_goes_through_the_public_entry_point(seed):
    """Whatever ``generate()`` returns for a random grouped diagram is clean too."""
    text, options = group_fuzz_input(seed)
    direction = options.pop("direction")
    report = check_diagram(text, direction, label=f"group fuzz {seed}", **options)
    codes = sorted({issue.code for issue in report.issues})
    assert not report.issues, f"{options}\n{text}\n{report.explain(*codes)}"
