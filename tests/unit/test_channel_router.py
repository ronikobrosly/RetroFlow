"""
Unit tests for the channel router.

    upstream     ┬   ┬
    tracks       └───┼──┐
                 ┌───┘  │
    downstream   ▼      ▼

A channel is plain data, so every rule can be checked without rendering:
which pieces share a track, which must be above which, and where a piece is
split to break a contradiction.
"""

from typing import Dict, List, Tuple

import pytest

from retroflow.channel_router import (
    ChannelPlan,
    Link,
    Terminal,
    route_channel,
)


def link(net: int, up: int, down: int) -> Link:
    """A connection from the upstream side at ``up`` to downstream at ``down``."""
    return Link(
        net,
        Terminal(("up", net, up), up, True),
        Terminal(("dn", net, down), down, False),
    )


def u_turn(net: int, first: int, second: int, upstream: bool = True) -> Link:
    """A connection between two terminals on the same side of the channel."""
    side = "up" if upstream else "dn"
    return Link(
        net,
        Terminal((side, net, first), first, upstream),
        Terminal((side, net, second), second, upstream),
    )


def levels(plan: ChannelPlan) -> Dict[int, List[int]]:
    """Track levels used by each net, upstream first."""
    found: Dict[int, List[int]] = {}
    for track in plan.tracks:
        found.setdefault(track.net, []).append(track.level)
    return {net: sorted(values) for net, values in found.items()}


def spans(plan: ChannelPlan) -> Dict[int, List[Tuple[int, int]]]:
    found: Dict[int, List[Tuple[int, int]]] = {}
    for track in plan.tracks:
        found.setdefault(track.net, []).append((track.low, track.high))
    return found


def assert_tracks_do_not_overlap(plan: ChannelPlan) -> None:
    """No two runs on one track touch or overlap (one blank cell apart)."""
    by_level: Dict[int, List[Tuple[int, int]]] = {}
    for track in plan.tracks:
        by_level.setdefault(track.level, []).append((track.low, track.high))
    for runs in by_level.values():
        runs.sort()
        for (_, first_high), (second_low, _) in zip(runs, runs[1:]):
            assert second_low > first_high + 1


class TestSimpleChannels:
    def test_empty_channel(self):
        plan = route_channel([])
        assert plan.levels == 0
        assert plan.tracks == []
        assert plan.straight == []

    def test_facing_terminals_need_no_track(self):
        plan = route_channel([link(1, 5, 5)])
        assert plan.levels == 0
        assert plan.tracks == []
        assert plan.straight == [(("up", 1, 5), ("dn", 1, 5))]
        assert plan.terminal_level == {}

    def test_offset_terminals_get_one_track(self):
        plan = route_channel([link(1, 2, 9)])
        assert plan.levels == 1
        assert spans(plan) == {1: [(2, 9)]}
        assert plan.terminal_level == {("up", 1, 2): 0, ("dn", 1, 9): 0}

    def test_pieces_that_do_not_overlap_share_a_track(self):
        plan = route_channel([link(1, 15, 5), link(2, 17, 28)])
        assert plan.levels == 1
        assert levels(plan) == {1: [0], 2: [0]}

    def test_pieces_one_cell_apart_do_not_share_a_track(self):
        plan = route_channel([link(1, 0, 10), link(2, 11, 20)])
        assert plan.levels == 2
        assert_tracks_do_not_overlap(plan)

    def test_overlapping_pieces_get_different_tracks(self):
        plan = route_channel([link(1, 0, 10), link(2, 4, 14), link(3, 8, 18)])
        assert plan.levels == 3
        assert_tracks_do_not_overlap(plan)

    def test_same_side_terminals_are_joined_by_a_track(self):
        plan = route_channel([u_turn(1, 3, 12)])
        assert plan.levels == 1
        assert spans(plan) == {1: [(3, 12)]}

    def test_downstream_u_turn(self):
        plan = route_channel([u_turn(1, 3, 12, upstream=False)])
        assert plan.levels == 1
        assert plan.terminal_level == {("dn", 1, 3): 0, ("dn", 1, 12): 0}


class TestSharedLines:
    """Links of one net that share a terminal become one piece."""

    def test_fan_out_shares_a_track(self):
        source = Terminal("src", 10, True)
        links = [Link(1, source, Terminal(f"t{p}", p, False)) for p in (2, 20, 30)]
        plan = route_channel(links)
        assert plan.levels == 1
        assert spans(plan) == {1: [(2, 30)]}
        assert set(plan.terminal_level) == {"src", "t2", "t20", "t30"}

    def test_fan_in_shares_a_track(self):
        target = Terminal("dst", 10, False)
        links = [Link(1, Terminal(f"s{p}", p, True), target) for p in (0, 22)]
        plan = route_channel(links)
        assert plan.levels == 1
        assert spans(plan) == {1: [(0, 22)]}

    def test_links_of_one_net_without_a_shared_terminal_stay_apart(self):
        plan = route_channel([link(1, 0, 6), link(1, 20, 26)])
        assert len(plan.tracks) == 2
        assert plan.levels == 1

    def test_branch_straight_ahead_with_trunk_on_one_side_is_one_piece(self):
        source = Terminal("src", 10, True)
        links = [Link(1, source, Terminal(f"t{p}", p, False)) for p in (10, 20)]
        plan = route_channel(links)
        assert plan.jogs == []
        assert spans(plan) == {1: [(10, 20)]}

    def test_four_way_meeting_is_split_into_two_tees(self):
        """
        A branch straight ahead plus trunk on both sides would draw ``┼``,
        which reads as two unrelated lines crossing.
        """
        source = Terminal("src", 10, True)
        links = [Link(1, source, Terminal(f"t{p}", p, False)) for p in (2, 10, 20)]
        plan = route_channel(links)

        assert plan.levels == 2
        assert sorted(spans(plan)[1]) == [(2, 10), (10, 20)]
        (jog,) = plan.jogs
        assert (jog.position, jog.upper_level, jog.lower_level) == (10, 0, 1)
        # Upstream stub ends on the upper track, the facing stub on the lower.
        assert plan.terminal_level["src"] == 0
        assert plan.terminal_level["t10"] == 1
        assert plan.terminal_level["t2"] == 0
        assert plan.terminal_level["t20"] == 1

    def test_four_way_meeting_of_a_fan_in_is_split_too(self):
        target = Terminal("dst", 10, False)
        links = [Link(1, Terminal(f"s{p}", p, True), target) for p in (0, 10, 22)]
        plan = route_channel(links)
        assert len(plan.jogs) == 1
        assert plan.terminal_level["s10"] < plan.terminal_level["dst"]


class TestOrdering:
    """Which piece gets the higher track."""

    def test_stub_above_another_stub_forces_the_order(self):
        # Net 1 comes down at 10; net 2 goes down at 10. Net 1 must be on top.
        plan = route_channel([link(1, 10, 0), link(2, 20, 10)])
        assert levels(plan)[1] < levels(plan)[2]

    def test_touching_columns_force_the_order_for_vertical_strokes(self):
        plan = route_channel([link(1, 10, 0), link(2, 20, 11)], stroke_gap=1)
        assert levels(plan)[1] < levels(plan)[2]

    def test_touching_rows_are_fine_for_horizontal_strokes(self):
        plan = route_channel([link(1, 10, 0), link(2, 20, 11)], stroke_gap=0)
        assert plan.levels == 2  # still overlapping, but either order is legal

    def test_order_with_fewer_crossings_wins(self):
        # Two nets heading right: the one further right must turn first.
        plan = route_channel([link(1, 0, 10), link(2, 2, 12)])
        assert levels(plan)[2] < levels(plan)[1]

    def test_two_nets_heading_left(self):
        plan = route_channel([link(1, 10, 0), link(2, 12, 2)])
        assert levels(plan)[1] < levels(plan)[2]

    def test_nested_u_turns_nest(self):
        plan = route_channel([u_turn(1, 0, 20), u_turn(2, 4, 16)])
        assert levels(plan)[2] < levels(plan)[1]

    def test_nested_downstream_u_turns_nest_the_other_way(self):
        plan = route_channel(
            [u_turn(1, 0, 20, upstream=False), u_turn(2, 4, 16, upstream=False)]
        )
        assert levels(plan)[1] < levels(plan)[2]

    def test_result_does_not_depend_on_link_order(self):
        links = [link(1, 0, 10), link(2, 2, 12), link(3, 30, 4), u_turn(4, 6, 26)]
        first = route_channel(links)
        second = route_channel(list(reversed(links)))
        assert levels(first) == levels(second)


class TestContradictions:
    """Ordering rules that cannot all hold are fixed with a jog."""

    def test_two_edges_swapping_columns_get_a_jog(self):
        """
        Net 1 goes 4 -> 20 and net 2 goes 20 -> 4. Each would have to be above
        the other, so one of them is split.
        """
        plan = route_channel([link(1, 4, 20), link(2, 20, 4)])

        (jog,) = plan.jogs
        assert 4 < jog.position < 20
        assert jog.upper_level < jog.lower_level
        assert plan.levels == 3
        assert_tracks_do_not_overlap(plan)

        split_net = jog.net
        other_net = 3 - split_net
        (other_level,) = levels(plan)[other_net]
        assert levels(plan)[split_net] == [jog.upper_level, jog.lower_level]
        assert jog.upper_level < other_level < jog.lower_level

    def test_jog_stays_clear_of_other_strokes(self):
        blockers = [link(10 + p, p, p) for p in (10, 12, 14)]
        plan = route_channel([link(1, 4, 20), link(2, 20, 4), *blockers])
        (jog,) = plan.jogs
        busy = {4, 20, 10, 12, 14}
        assert all(abs(jog.position - position) > 1 for position in busy)

    def test_jog_may_sit_next_to_other_rows_when_strokes_are_horizontal(self):
        plan = route_channel([link(1, 4, 6), link(2, 6, 4)], stroke_gap=0)
        (jog,) = plan.jogs
        assert jog.position == 5

    def test_three_way_rotation_is_resolved(self):
        plan = route_channel([link(1, 0, 10), link(2, 10, 20), link(3, 20, 0)])
        assert_tracks_do_not_overlap(plan)
        assert len(plan.jogs) >= 1
        for jog in plan.jogs:
            assert jog.upper_level < jog.lower_level

    def test_every_stub_ends_on_a_track_of_its_own_net(self):
        links = [link(1, 4, 20), link(2, 20, 4), link(3, 12, 30), u_turn(4, 0, 34)]
        plan = route_channel(links)
        tracks_by_net: Dict[int, List[Tuple[int, int, int]]] = {}
        for track in plan.tracks:
            tracks_by_net.setdefault(track.net, []).append(
                (track.level, track.low, track.high)
            )
        for a_link in links:
            for terminal in (a_link.first, a_link.second):
                level = plan.terminal_level[terminal.key]
                assert any(
                    track_level == level and low <= terminal.position <= high
                    for track_level, low, high in tracks_by_net[a_link.net]
                )


@pytest.mark.parametrize("seed", range(40))
def test_random_channels_obey_every_rule(seed):
    """Random channels: no shared cells, stubs never run into each other."""
    import random

    rng = random.Random(seed)
    ups = rng.sample(range(0, 60, 2), 8)
    downs = rng.sample(range(0, 60, 2), 8)
    links = [link(net, up, down) for net, (up, down) in enumerate(zip(ups, downs))]
    plan = route_channel(links, stroke_gap=1)

    assert_tracks_do_not_overlap(plan)

    # Rebuild every stroke that runs across the channel and check that two
    # strokes of different nets never sit in the same or touching columns
    # on the same track row.
    strokes: List[Tuple[int, int, int, int]] = []  # (net, position, from, to)
    bottom = plan.levels
    for a_link in links:
        for terminal in (a_link.first, a_link.second):
            if terminal.key not in plan.terminal_level:
                strokes.append((a_link.net, terminal.position, -1, bottom))
                continue
            level = plan.terminal_level[terminal.key]
            if terminal.upstream:
                strokes.append((a_link.net, terminal.position, -1, level))
            else:
                strokes.append((a_link.net, terminal.position, level, bottom))
    for jog in plan.jogs:
        strokes.append((jog.net, jog.position, jog.upper_level, jog.lower_level))

    for i, (net_a, pos_a, top_a, end_a) in enumerate(strokes):
        for net_b, pos_b, top_b, end_b in strokes[i + 1 :]:
            if net_a == net_b or abs(pos_a - pos_b) > 1:
                continue
            assert end_a < top_b or end_b < top_a, (
                f"strokes of nets {net_a} and {net_b} run into each other"
            )
