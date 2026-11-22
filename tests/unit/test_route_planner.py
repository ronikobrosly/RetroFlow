"""
Unit tests for the route planner.

The planner is pure data in, pure data out, so most of these tests build a
tiny graph, plan it and look at the plan itself: where boxes ended up, how
big they grew, which cells carry wire. A few render the plan to text, because
"the chain is a straight column" is easiest to see in a picture.
"""

from typing import Dict, List, Optional, Sequence, Tuple

import pytest

from retroflow.layout import NetworkXLayout
from retroflow.models import GroupDefinition
from retroflow.renderer import BoxDimensions
from retroflow.route_planner import (
    PlannerOptions,
    RoutePlan,
    RoutePlanner,
    assign_ranks,
    settle,
    spread_offsets,
    unique_edges,
)

Edge = Tuple[str, str]


def boxes_for(names: Sequence[str], width: int = 10, height: int = 3):
    return {
        name: BoxDimensions(width=width, height=height, text_lines=[name])
        for name in names
    }


def plan_graph(
    edges: Sequence[Edge],
    direction: str = "TB",
    groups: Sequence[GroupDefinition] = (),
    dimensions: Optional[Dict[str, BoxDimensions]] = None,
    **options,
) -> RoutePlan:
    """Plan a graph the way the generator does, with 10x3 boxes by default."""
    layers = assign_ranks(edges, groups, NetworkXLayout())
    names = [name for layer in layers for name in layer]
    planner = RoutePlanner(PlannerOptions(direction=direction, **options))
    return planner.plan(edges, groups, layers, dimensions or boxes_for(names))


def picture(plan: RoutePlan) -> List[str]:
    """Draw box outlines and wires of a plan (no text, no shadows)."""
    rows = [[" "] * (plan.width + 2) for _ in range(plan.height + 2)]
    for name, (x, y) in plan.box_positions.items():
        dims = plan.box_dimensions[name]
        for dy in range(dims.height):
            for dx in range(dims.width):
                edge = dy in (0, dims.height - 1) or dx in (0, dims.width - 1)
                rows[y + dy][x + dx] = "#" if edge else "."
    for (x, y), glyph in plan.port_marks.items():
        rows[y][x] = glyph
    for (x, y), glyph in plan.grid.cells():
        rows[y][x] = glyph
    return ["".join(row).rstrip() for row in rows]


def chain(*names: str) -> List[Edge]:
    return list(zip(names, names[1:]))


# ── helpers ─────────────────────────────────────────────────────────────


class TestUniqueEdges:
    def test_keeps_first_occurrence_order(self):
        edges = [("A", "B"), ("B", "C"), ("A", "B"), ("A", "C"), ("B", "C")]
        assert unique_edges(edges) == [("A", "B"), ("B", "C"), ("A", "C")]


class TestSpreadOffsets:
    def test_nothing_to_place(self):
        assert spread_offsets(0, 10, 2, True) == ([], 10)

    @pytest.mark.parametrize("size, expected", [(10, 5), (11, 5), (4, 2)])
    def test_single_point_on_a_horizontal_side(self, size, expected):
        assert spread_offsets(1, size, 2, round_up=True) == ([expected], size)

    @pytest.mark.parametrize("size, expected", [(3, 1), (4, 1), (5, 2)])
    def test_single_point_on_a_vertical_side(self, size, expected):
        assert spread_offsets(1, size, 1, round_up=False) == ([expected], size)

    def test_two_points_match_the_classic_layout(self):
        assert spread_offsets(2, 10, 2, True) == ([4, 6], 10)

    def test_points_are_spread_when_the_side_is_roomy(self):
        offsets, size = spread_offsets(2, 24, 2, True)
        assert (offsets, size) == ([8, 14], 24)

    def test_points_pack_around_the_middle_when_tight(self):
        offsets, size = spread_offsets(3, 10, 2, True)
        assert (offsets, size) == ([3, 5, 7], 10)

    def test_side_grows_when_points_do_not_fit(self):
        offsets, size = spread_offsets(6, 10, 2, True)
        assert size == 15
        assert offsets == [2, 4, 6, 8, 10, 12]

    def test_vertical_side_grows_one_row_per_point(self):
        offsets, size = spread_offsets(3, 3, 1, False)
        assert (offsets, size) == ([1, 2, 3], 5)

    @pytest.mark.parametrize("count", range(1, 9))
    @pytest.mark.parametrize("size", (3, 6, 10, 17, 30))
    @pytest.mark.parametrize("pitch, round_up", [(1, False), (2, True)])
    def test_points_stay_off_corners_and_apart(self, count, size, pitch, round_up):
        offsets, new_size = spread_offsets(count, size, pitch, round_up)
        assert len(offsets) == count
        assert new_size >= size
        assert offsets[0] >= 1 and offsets[-1] <= new_size - 2
        assert all(b - a >= pitch for a, b in zip(offsets, offsets[1:]))


class TestSettle:
    def test_items_get_what_they_want_when_there_is_room(self):
        assert settle([0, 20, 40], [1, 1, 1], [10, 10]) == [0, 20, 40]

    def test_gap_is_enforced(self):
        positions = settle([10, 12], [1, 1], [23])
        assert positions[1] - positions[0] == 23

    def test_crowded_items_share_the_displacement(self):
        assert settle([10, 10], [1, 1], [10]) == [5, 15]

    def test_heavier_item_moves_less(self):
        light_first = settle([10, 10], [1, 9], [10])
        assert light_first == [1, 11]

    def test_order_is_kept_even_if_wishes_cross(self):
        positions = settle([50, 0], [1, 1], [5])
        assert positions[0] < positions[1]

    def test_single_item(self):
        assert settle([7.4], [1], []) == [7]

    def test_halves_round_down(self):
        assert settle([11.5], [1], []) == [11]
        assert settle([-0.5], [1], []) == [-1]

    @pytest.mark.parametrize("seed", range(20))
    def test_gaps_always_hold(self, seed):
        import random

        rng = random.Random(seed)
        count = rng.randint(1, 9)
        desired = [rng.uniform(-30, 30) for _ in range(count)]
        weights = [rng.choice([0.25, 1.0, 4.0]) for _ in range(count)]
        gaps = [rng.randint(1, 15) for _ in range(count - 1)]
        positions = settle(desired, weights, gaps)
        assert all(b - a >= gap for a, b, gap in zip(positions, positions[1:], gaps))


class TestAssignRanks:
    def test_without_groups_layers_come_from_the_layout_engine(self):
        edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]
        layers = assign_ranks(edges, [], NetworkXLayout())
        assert [sorted(layer) for layer in layers] == [["A"], ["B", "C"], ["D"]]

    def test_group_members_share_a_layer(self):
        edges = chain("A", "B", "C", "D")
        groups = [GroupDefinition("G", ["A", "B"]), GroupDefinition("H", ["C", "D"])]
        layers = assign_ranks(edges, groups, NetworkXLayout())
        assert layers == [["A", "B"], ["C", "D"]]

    def test_ungrouped_nodes_keep_their_own_layers(self):
        edges = chain("A", "B", "C", "D")
        groups = [GroupDefinition("G", ["B", "C"])]
        layers = assign_ranks(edges, groups, NetworkXLayout())
        assert layers == [["A"], ["B", "C"], ["D"]]

    def test_group_with_only_internal_edges_lands_in_the_first_layer(self):
        groups = [GroupDefinition("G", ["A", "B"])]
        layers = assign_ranks([("A", "B"), ("B", "A")], groups, NetworkXLayout())
        assert layers == [["A", "B"]]

    def test_group_members_not_in_any_edge_are_ignored(self):
        groups = [GroupDefinition("G", ["A", "Ghost"])]
        layers = assign_ranks([("A", "B")], groups, NetworkXLayout())
        assert layers == [["A"], ["B"]]

    def test_repeated_edges_do_not_matter(self):
        once = assign_ranks([("A", "B"), ("B", "C")], [], NetworkXLayout())
        twice = assign_ranks([("A", "B"), ("B", "C"), ("A", "B")], [], NetworkXLayout())
        assert once == twice


# ── whole plans ─────────────────────────────────────────────────────────


def box_rectangles(plan: RoutePlan, shadow: bool = True):
    """(left, top, right, bottom) of every box, shadows included."""
    extra = 1 if shadow else 0
    return {
        name: (
            x,
            y,
            x + plan.box_dimensions[name].width - 1 + extra,
            y + plan.box_dimensions[name].height - 1 + extra,
        )
        for name, (x, y) in plan.box_positions.items()
    }


def assert_plan_is_sound(plan: RoutePlan, shadow: bool = True) -> None:
    """Checks every plan must pass, whatever the graph."""
    assert plan.grid.conflicts == []

    rectangles = box_rectangles(plan, shadow)
    names = sorted(rectangles)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            ax0, ay0, ax1, ay1 = rectangles[first]
            bx0, by0, bx1, by1 = rectangles[second]
            apart = ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0
            assert apart, f"boxes {first} and {second} overlap"

    # No wire runs through a box (borders, text or interior).
    inside = set()
    for name, (x, y) in plan.box_positions.items():
        dims = plan.box_dimensions[name]
        inside |= {
            (x + dx, y + dy) for dx in range(dims.width) for dy in range(dims.height)
        }
    wire_cells = {cell for cell, _ in plan.grid.cells()}
    assert not wire_cells & inside

    # Port marks sit on box borders, never on corners.
    for cell in plan.port_marks:
        assert cell in inside

    # Everything fits in the reported canvas, starting at the origin.
    for x, y in wire_cells | inside:
        assert 0 <= x < plan.width and 0 <= y < plan.height
    assert min(x for x, _ in plan.box_positions.values()) >= 0
    assert min(y for _, y in plan.box_positions.values()) >= 0


class TestPlansAreSound:
    @pytest.mark.parametrize("direction", ["TB", "LR"])
    @pytest.mark.parametrize(
        "edges",
        [
            [("A", "B")],
            chain("A", "B", "C", "D"),
            [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")],
            chain("A", "B", "C") + [("A", "C")],
            chain("A", "B", "C") + [("C", "A")],
            [("A", "A")],
            [("A", "B"), ("B", "A")],
            [("A", "B"), ("B", "B"), ("B", "C")],
            [(f"T{i}", f"B{j}") for i in range(3) for j in range(3)],
            [(f"N{i}", f"N{j}") for i in range(5) for j in range(5) if i != j],
        ],
        ids=[
            "pair",
            "chain",
            "diamond",
            "skip",
            "cycle",
            "self_loop",
            "two_way",
            "loop_in_chain",
            "bipartite",
            "complete_digraph",
        ],
    )
    def test_shapes(self, edges, direction):
        assert_plan_is_sound(plan_graph(edges, direction))

    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_without_shadows(self, direction):
        edges = chain("A", "B", "C") + [("A", "C"), ("C", "A")]
        assert_plan_is_sound(plan_graph(edges, direction, shadow=False), shadow=False)

    @pytest.mark.parametrize("direction", ["TB", "LR"])
    @pytest.mark.parametrize("spacing", [0, 1, 2, 30])
    def test_extreme_spacing(self, direction, spacing):
        edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"), ("D", "A")]
        plan = plan_graph(
            edges, direction, horizontal_spacing=spacing, vertical_spacing=spacing
        )
        assert_plan_is_sound(plan)

    def test_layers_list_every_node_once(self):
        edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]
        plan = plan_graph(edges)
        assert sorted(name for layer in plan.layers for name in layer) == list("ABCD")
        assert [len(layer) for layer in plan.layers] == [1, 2, 1]

    def test_default_options(self):
        planner = RoutePlanner()
        assert planner.options == PlannerOptions()
        assert planner.options.direction == "TB"


class TestTopToBottomLayout:
    def test_chain_is_a_straight_column(self):
        plan = plan_graph(chain("A", "B", "C", "D"))
        assert len({x for x, _ in plan.box_positions.values()}) == 1
        assert plan.tracks_per_channel == [0, 0, 0]

    def test_layers_keep_the_classic_distance(self):
        plan = plan_graph(chain("A", "B", "C"))
        ys = sorted(y for _, y in plan.box_positions.values())
        assert ys == [0, 8, 16]  # box 3 + shadow 2 + spacing 3

    def test_layers_keep_the_classic_distance_without_shadow(self):
        plan = plan_graph(chain("A", "B", "C"), shadow=False)
        ys = sorted(y for _, y in plan.box_positions.values())
        assert ys == [0, 6, 12]

    def test_gap_grows_only_when_tracks_need_it(self):
        dense = [(f"T{i}", f"B{j}") for i in range(4) for j in range(4)]
        plan = plan_graph(dense)
        top = plan.box_positions["T0"][1]
        bottom = plan.box_positions["B0"][1]
        assert bottom - top > 8
        assert plan.tracks_per_channel[0] > 3

    def test_parent_sits_over_its_children(self):
        plan = plan_graph([("Root", "Left"), ("Root", "Right")])
        root, left, right = (
            plan.box_positions[n][0] for n in ("Root", "Left", "Right")
        )
        assert left < root < right
        assert abs((root - left) - (right - root)) <= 1

    def test_symmetric_diamond_is_symmetric(self):
        plan = plan_graph([("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")])
        assert plan.box_positions["A"][0] == plan.box_positions["D"][0]

    def test_every_edge_gets_its_own_port(self):
        plan = plan_graph([("Hub", f"Leaf {i}") for i in range(4)])
        hub_x, hub_y = plan.box_positions["Hub"]
        bottom = hub_y + plan.box_dimensions["Hub"].height - 1
        marks = sorted(x for (x, y) in plan.port_marks if y == bottom)
        assert len(marks) == 4
        assert all(b - a >= 2 for a, b in zip(marks, marks[1:]))

    def test_box_widens_to_fit_its_ports(self):
        plan = plan_graph([("Hub", f"Leaf {i}") for i in range(8)])
        assert plan.box_dimensions["Hub"].width == 19
        assert plan.box_dimensions["Leaf 0"].width == 10
        assert plan.box_dimensions["Hub"].height == 3

    def test_arrowheads_are_never_side_by_side(self):
        plan = plan_graph([(f"Feed {i}", "Sink") for i in range(6)])
        arrows = sorted(x for (x, y), glyph in plan.grid.cells() if glyph == "▼")
        assert len(arrows) == 6
        assert all(b - a >= 2 for a, b in zip(arrows, arrows[1:]))

    def test_skip_edge_gets_a_lane_beside_the_boxes(self):
        plan = plan_graph(chain("A", "B", "C") + [("A", "C")])
        b_left, b_top, b_right, b_bottom = box_rectangles(plan)["B"]
        beside = [
            x
            for (x, y), glyph in plan.grid.cells()
            if glyph == "│" and b_top <= y < b_bottom  # not the shadow row
        ]
        assert beside, "the skip edge should pass B in its own column"
        assert len(set(beside)) == 1
        assert beside[0] > b_right + 1

    def test_boxes_line_up_even_when_a_lane_runs_past(self):
        plan = plan_graph(chain("A", "B", "C") + [("A", "C")])
        assert len({x for x, _ in plan.box_positions.values()}) == 1

    def test_back_edge_enters_the_side_of_its_target(self):
        plan = plan_graph(chain("A", "B", "C") + [("C", "A")])
        ax, ay = plan.box_positions["A"]
        assert plan.grid.glyph_at((ax - 1, ay + 1)) == "►"

    def test_self_loop_enters_the_side_too(self):
        plan = plan_graph([("A", "B"), ("B", "B")])
        bx, by = plan.box_positions["B"]
        assert plan.grid.glyph_at((bx - 1, by + 1)) == "►"

    def test_back_edges_beyond_the_side_rows_use_the_top(self):
        # A one-row box has one row per side, so a third back edge has to
        # come in through the top like a forward edge does.
        edges = chain("A", "B", "C", "D") + [("B", "A"), ("C", "A"), ("D", "A")]
        plan = plan_graph(edges)
        ax, ay = plan.box_positions["A"]
        width = plan.box_dimensions["A"].width
        sides = [
            plan.grid.glyph_at((ax - 1, ay + 1)),
            plan.grid.glyph_at((ax + width, ay + 1)),
        ]
        assert sides == ["►", "◄"]
        above = [plan.grid.glyph_at((x, ay - 1)) for x in range(ax, ax + width)]
        assert above.count("▼") == 1
        assert_plan_is_sound(plan)

    def test_taller_box_takes_more_side_entries(self):
        names = list("ABCD")
        dimensions = boxes_for(names)
        dimensions["A"] = BoxDimensions(width=10, height=5, text_lines=["A", "a", "a"])
        edges = chain(*names) + [("B", "A"), ("C", "A"), ("D", "A")]
        plan = plan_graph(edges, dimensions=dimensions)
        ax, ay = plan.box_positions["A"]
        left = [plan.grid.glyph_at((ax - 1, ay + dy)) for dy in range(1, 4)]
        assert left.count("►") == 3

    def test_crossing_edges_between_aligned_pairs_get_a_jog(self):
        edges = [("A0", "A1"), ("A0", "B1"), ("B0", "B1"), ("B0", "A1")]
        plan = plan_graph(edges)
        assert plan.tracks_per_channel == [3]
        assert plan.grid.crossing_count() == 1

    def test_repeated_edges_are_drawn_once(self):
        once = plan_graph([("A", "B"), ("B", "C")])
        twice = plan_graph([("A", "B"), ("B", "C"), ("A", "B"), ("B", "C")])
        assert dict(once.grid.cells()) == dict(twice.grid.cells())

    def test_port_slides_to_keep_a_line_straight(self):
        # A has a loop port and a port for B. B lines up under A, and its
        # single entry slides over to meet A's port, so the line is straight.
        plan = plan_graph([("A", "A"), ("A", "B")])
        ax, ay = plan.box_positions["A"]
        bx, by = plan.box_positions["B"]
        assert ax == bx
        (arrow_x,) = [x for (x, y), g in plan.grid.cells() if g == "▼" and y == by - 1]
        column = [plan.grid.glyph_at((arrow_x, y)) for y in range(ay + 3, by - 1)]
        assert set(column) == {"│"}
        assert arrow_x - bx != plan.box_dimensions["B"].width // 2

    def test_slid_port_keeps_clear_of_the_corners(self):
        plan = plan_graph(
            chain("S0", "S1", "S2", "S3", "S4", "S5")
            + [
                ("S0", "S2"),
                ("S1", "S3"),
                ("S2", "S4"),
                ("S3", "S5"),
                ("S0", "S4"),
                ("S1", "S5"),
            ]
        )
        for name, (x, y) in plan.box_positions.items():
            dims = plan.box_dimensions[name]
            for mark_x, mark_y in plan.port_marks:
                if mark_y == y + dims.height - 1 and x <= mark_x < x + dims.width:
                    assert 2 <= mark_x - x <= dims.width - 3


class TestLeftToRightLayout:
    def test_chain_is_a_straight_row(self):
        plan = plan_graph(chain("A", "B", "C", "D"), "LR")
        assert len({y for _, y in plan.box_positions.values()}) == 1

    def test_columns_keep_the_classic_distance(self):
        plan = plan_graph(chain("A", "B", "C"), "LR")
        xs = sorted(x for x, _ in plan.box_positions.values())
        assert xs == [0, 23, 46]  # box 10 + shadow 1 + spacing 12

    def test_fan_out_shares_one_line(self):
        plan = plan_graph([("Hub", f"Leaf {i}") for i in range(3)], "LR")
        hub_x, hub_y = plan.box_positions["Hub"]
        width = plan.box_dimensions["Hub"].width
        leaving = [y for (x, y), glyph in plan.grid.cells() if x == hub_x + width]
        assert leaving == [hub_y + 1]
        assert plan.box_dimensions["Hub"].height == 3
        arrows = [glyph for _, glyph in plan.grid.cells() if glyph == "►"]
        assert len(arrows) == 3

    def test_fan_in_shares_one_arrowhead(self):
        plan = plan_graph([(f"Feed {i}", "Sink") for i in range(3)], "LR")
        arrows = [glyph for _, glyph in plan.grid.cells() if glyph == "►"]
        assert len(arrows) == 1

    def test_fan_through_the_hub_row_is_drawn_as_two_tees(self):
        # The middle leaf is level with the hub. A four-way glyph there
        # would read as two lines crossing, so the trunk is offset instead.
        plan = plan_graph([("Hub", f"Leaf {i}") for i in range(3)], "LR")
        glyphs = {glyph for _, glyph in plan.grid.cells()}
        assert "┼" not in glyphs
        assert {"┴", "┬"} <= glyphs or {"├", "┤"} <= glyphs

    def test_skip_edge_uses_the_bottom_borders(self):
        plan = plan_graph(chain("A", "B", "C") + [("A", "C")], "LR")
        ax, ay = plan.box_positions["A"]
        cx, cy = plan.box_positions["C"]
        height = plan.box_dimensions["A"].height
        marks = [cell for cell, glyph in plan.port_marks.items() if glyph == "┬"]
        assert marks and all(y == ay + height - 1 for _, y in marks)
        below_c = [plan.grid.glyph_at((x, cy + height)) for x in range(cx, cx + 10)]
        assert "▲" in below_c
        assert plan.box_dimensions["C"].height == 3  # boxes stay one row tall

    def test_back_edge_arcs_over_the_top(self):
        plan = plan_graph(chain("A", "B", "C") + [("C", "A")], "LR")
        ax, ay = plan.box_positions["A"]
        above_a = [plan.grid.glyph_at((x, ay - 1)) for x in range(ax, ax + 10)]
        assert "▼" in above_a
        assert "┴" in plan.port_marks.values()

    def test_self_loop_sits_on_top_of_its_box(self):
        plan = plan_graph([("A", "A")], "LR")
        ax, ay = plan.box_positions["A"]
        assert ay == 2
        glyphs = sorted(glyph for _, glyph in plan.grid.cells())
        assert glyphs == sorted("┌─┐│▼")

    def test_interleaving_arcs_take_opposite_sides(self):
        # Arcs 0-2 and 1-3 would cross on one side of the row.
        edges = chain("N0", "N1", "N2", "N3") + [("N0", "N2"), ("N1", "N3")]
        plan = plan_graph(edges, "LR")
        assert plan.grid.crossing_count() == 0
        assert {"┬", "┴"} <= set(plan.port_marks.values())

    def test_box_widens_for_many_top_and_bottom_ports(self):
        edges = chain(*[f"N{i}" for i in range(8)])
        edges += [("N0", f"N{i}") for i in range(2, 8)]
        plan = plan_graph(edges, "LR")
        assert plan.box_dimensions["N0"].width > 10
        assert plan.box_dimensions["N0"].height == 3
        assert_plan_is_sound(plan)

    def test_same_graph_has_no_more_tracks_than_it_needs(self):
        plan = plan_graph([("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")], "LR")
        assert plan.tracks_per_channel == [1, 1]


class TestGroups:
    def groups(self):
        return [
            GroupDefinition("API Layer", ["Gateway", "Auth"]),
            GroupDefinition("Data Layer", ["Database", "Cache"]),
        ]

    edges = [
        ("Gateway", "Auth"),
        ("Auth", "Database"),
        ("Database", "Cache"),
        ("Gateway", "Cache"),
    ]

    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_plan_is_sound(self, direction):
        assert_plan_is_sound(plan_graph(self.edges, direction, self.groups()))

    def test_members_sit_side_by_side_in_tb(self):
        plan = plan_graph(self.edges, "TB", self.groups())
        assert plan.box_positions["Gateway"][1] == plan.box_positions["Auth"][1]
        assert plan.box_positions["Gateway"][0] != plan.box_positions["Auth"][0]

    def test_members_are_stacked_in_lr(self):
        plan = plan_graph(self.edges, "LR", self.groups())
        assert plan.box_positions["Gateway"][0] == plan.box_positions["Auth"][0]
        assert plan.box_positions["Gateway"][1] != plan.box_positions["Auth"][1]

    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_group_box_surrounds_its_members(self, direction):
        plan = plan_graph(self.edges, direction, self.groups())
        rectangles = box_rectangles(plan)
        assert [g.name for g in plan.group_boundaries] == ["API Layer", "Data Layer"]
        for boundary in plan.group_boundaries:
            for member in boundary.members:
                left, top, right, bottom = rectangles[member]
                assert boundary.x < left and right < boundary.x + boundary.width - 1
                # One extra row above the top border holds the title.
                assert boundary.y + 1 < top
                assert bottom < boundary.y + boundary.height - 1

    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_group_boxes_do_not_overlap(self, direction):
        plan = plan_graph(self.edges, direction, self.groups())
        first, second = plan.group_boundaries
        apart = (
            first.x + first.width < second.x
            or second.x + second.width < first.x
            or first.y + first.height < second.y
            or second.y + second.height < first.y
        )
        assert apart

    def test_neighbours_in_a_group_are_joined_directly(self):
        plan = plan_graph(self.edges, "TB", self.groups())
        gx, gy = plan.box_positions["Gateway"]
        ax, _ = plan.box_positions["Auth"]
        row = [plan.grid.glyph_at((x, gy + 1)) for x in range(gx + 10, ax)]
        assert row[-1] == "►"
        assert set(row[:-1]) == {"─"}

    def test_second_edge_between_neighbours_arcs_underneath(self):
        groups = [GroupDefinition("Pair", ["Ping", "Pong"])]
        plan = plan_graph([("Ping", "Pong"), ("Pong", "Ping")], "TB", groups)
        glyphs = [glyph for _, glyph in plan.grid.cells()]
        assert glyphs.count("►") + glyphs.count("◄") == 1
        assert glyphs.count("▲") == 1
        assert_plan_is_sound(plan)

    def test_title_avoids_lines_entering_from_above(self):
        groups = [GroupDefinition("A Long Group Title", ["Target"])]
        plan = plan_graph([("Source", "Target")], "TB", groups)
        (boundary,) = plan.group_boundaries
        start = plan.group_title_x["A Long Group Title"]
        title_cells = {(x, boundary.y) for x in range(start, start + 18)}
        assert not title_cells & {cell for cell, _ in plan.grid.cells()}
        assert boundary.x < start
        assert start + 18 <= boundary.x + boundary.width - 1

    def test_port_is_not_slid_into_a_title(self):
        # T's single entry would slide sideways to straighten its line, which
        # here would leave the long title no gap to sit in. It stays put.
        title = "A Rather Long Group Title"
        groups = [GroupDefinition(title, ["T"])]
        edges = [("A", "A"), ("A", "B"), ("C", "T"), ("T", "B")]
        plan = plan_graph(edges, "TB", groups)
        (boundary,) = plan.group_boundaries
        start = plan.group_title_x[title]
        title_cells = {(x, boundary.y) for x in range(start, start + len(title))}
        assert not title_cells & {cell for cell, _ in plan.grid.cells()}
        assert boundary.x < start
        assert start + len(title) <= boundary.x + boundary.width - 1
        assert_plan_is_sound(plan)

    def test_group_naming_only_unknown_nodes_is_ignored(self):
        plan = plan_graph([("A", "B")], "TB", [GroupDefinition("Ghosts", ["Nobody"])])
        assert plan.group_boundaries == []
        assert plan.group_title_x == {}
        assert_plan_is_sound(plan)

    def test_title_is_centred_when_nothing_is_in_the_way(self):
        groups = [GroupDefinition("Top", ["Source"])]
        plan = plan_graph([("Source", "Target")], "TB", groups)
        (boundary,) = plan.group_boundaries
        assert plan.group_title_x["Top"] == boundary.x + (boundary.width - 3) // 2

    def test_group_wider_than_its_members_fits_a_long_title_in_lr(self):
        title = "An Extremely Long Group Title"
        groups = [GroupDefinition(title, ["A"])]
        plan = plan_graph([("A", "B")], "LR", groups)
        (boundary,) = plan.group_boundaries
        assert boundary.width >= len(title) + 2
        assert_plan_is_sound(plan)

    def test_grouped_box_grows_taller_in_lr_when_its_side_is_full(self):
        groups = [GroupDefinition("G", ["Hub", "Other"])]
        edges = [("In 1", "Hub"), ("In 2", "Hub"), ("In 1", "Other"), ("Hub", "Other")]
        plan = plan_graph(edges, "LR", groups)
        assert plan.box_dimensions["Hub"].height > 3
        lines = plan.box_dimensions["Hub"].text_lines
        assert "Hub" in lines and len(lines) >= 1
        assert_plan_is_sound(plan)

    def test_empty_group_is_ignored(self):
        plan = plan_graph([("A", "B")], "TB", [GroupDefinition("Nobody", [])])
        assert plan.group_boundaries == []


class TestPictures:
    """A few plans drawn out, to pin the look as well as the data."""

    def test_skip_edge_tb(self):
        plan = plan_graph(chain("A", "B", "C") + [("A", "C")])
        assert picture(plan)[:19] == [
            "##########",
            "#........#",
            "####┬#┬###",
            "    │ │",
            "    │ │",
            "    │ │",
            "    │ └───────┐",
            "    ▼         │",
            "##########    │",
            "#........#    │",
            "####┬#####    │",
            "    │         │",
            "    │         │",
            "    │         │",
            "    │ ┌───────┘",
            "    ▼ ▼",
            "##########",
            "#........#",
            "##########",
        ]

    def test_skip_edge_lr(self):
        plan = plan_graph(chain("A", "B", "C") + [("A", "C")], "LR")
        rows = picture(plan)
        assert rows[1] == "#........#────────────►#........#────────────►#........#"
        assert rows[2].startswith("#####┬####")
        assert "▲" in rows[3]
        assert rows[5].strip().startswith("└") and rows[5].strip().endswith("┘")

    def test_retry_loop_tb(self):
        plan = plan_graph([("Fetch", "Parse"), ("Parse", "Save"), ("Parse", "Fetch")])
        rows = picture(plan)
        assert rows[1].startswith("┌───►#")
        assert rows[14].startswith("└────────┘")
