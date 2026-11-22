"""
Route planner: plans every edge of a diagram before a single glyph is drawn.

    ranks ──► lanes ──► order ──► ports ──► positions ──► tracks ──► wire grid
    └──────────────────── pure data, no canvas ───────────────────┘

The original edge drawer routed and painted one edge at a time, with the
character canvas as its only memory. That works for small diagrams and falls
apart for busy ones: unrelated edges land on the same row and fuse. The planner
replaces it for those busy diagrams and follows five rules:

1. A glyph is computed from the lines that pass through its cell (WireGrid).
2. Edges share a line only as a *star* (one source fanning out, or several
   sources fanning into one target), so a shared line never implies an edge
   that was not asked for.
3. One allocator per box side hands out ports for all edges on that side.
4. Every segment lies in space reserved for it: a lane next to the boxes it
   passes, a track in the channel between two layers.
5. Every ordering is total and derived from input order.

Coordinates
-----------
All planning happens in *flow coordinates*: ``flow`` runs along the direction
of the diagram and ``cross`` runs across it.

    TB:  cross = x, flow = y          LR:  cross = y, flow = x

Left-to-right diagrams are therefore planned by exactly the same code as
top-to-bottom ones; only the final conversion to canvas cells differs.

How an edge attaches to a box
-----------------------------
``F``  through the box side that faces the flow (bottom/top in TB,
       right/left in LR), ending in a channel.
``X``  through a side that runs along the flow, by a short *hook* to a lane
       right next to the box. This is how a back edge enters the left side
       of its target in TB, and how skip and back edges use the top and
       bottom borders in LR, where the facing sides only have one row.
``A``  an *arc*: the edge re-enters on the same side it left from. Used
       between boxes of one layer and for self loops inside groups.
``D``  a direct line between two neighbouring boxes of one layer.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from .channel_router import ChannelPlan, Link, Terminal, route_channel
from .models import GroupBoundary, GroupDefinition
from .renderer import BoxDimensions
from .wire_grid import DOWN, LEFT, RIGHT, UP, Cell, WireGrid

# How far a group box extends beyond its members (matches the group renderer).
GROUP_PADDING = 3
GROUP_TITLE_ROWS = 1
GROUP_UNIT_PREFIX = "\x00group:"

BEFORE, AFTER = -1, 1


@dataclass(frozen=True)
class PlannerOptions:
    """Everything about the look of a diagram that affects routing."""

    direction: str = "TB"
    horizontal_spacing: int = 12
    vertical_spacing: int = 3
    shadow: bool = True


@dataclass
class RoutePlan:
    """
    A fully planned diagram, in canvas coordinates.

    Attributes:
        box_dimensions: Final size of each box (boxes grow to fit ports).
        box_positions: Top-left corner of each box.
        group_boundaries: Dashed group boxes to draw behind the node boxes.
        group_title_x: Column where each group's title starts.
        grid: Every edge, as arms in a wire grid.
        port_marks: Border cells that get a tee where a line leaves a box.
        width: Columns needed to draw everything.
        height: Rows needed to draw everything.
        layers: Node names per layer, in drawing order.
        tracks_per_channel: Tracks used in each gap, upstream gap first.
    """

    box_dimensions: Dict[str, BoxDimensions]
    box_positions: Dict[str, Tuple[int, int]]
    group_boundaries: List[GroupBoundary]
    group_title_x: Dict[str, int]
    grid: WireGrid
    port_marks: Dict[Cell, str]
    width: int
    height: int
    layers: List[List[str]]
    tracks_per_channel: List[int]


# ── internal model ──────────────────────────────────────────────────────


@dataclass(eq=False)
class _Box:
    """A node box while it is being planned (sizes in flow coordinates)."""

    name: str
    dims: BoxDimensions
    rank: int
    cross_size: int
    flow_size: int
    group: Optional[str] = None
    order: int = 0
    cross: int = 0
    ups: List[object] = field(default_factory=list)
    downs: List[object] = field(default_factory=list)
    out_ports: List["_Port"] = field(default_factory=list)
    in_ports: List["_Port"] = field(default_factory=list)
    hooks: Dict[int, List["_Hook"]] = field(default_factory=lambda: {-1: [], 1: []})
    direct: Dict[int, "_Edge"] = field(default_factory=dict)
    is_lane = False


@dataclass(eq=False)
class _Lane:
    """One layer's worth of an edge that travels past boxes."""

    edge: "_Edge"
    rank: int
    anchor: Optional[_Box] = None  # box this lane should sit right next to
    side: int = BEFORE  # which side of the anchor
    hooked: bool = False  # attached to the anchor by a hook (must be adjacent)
    order: int = 0
    cross: int = 0
    ups: List[object] = field(default_factory=list)
    downs: List[object] = field(default_factory=list)
    points: List[int] = field(default_factory=list)  # flow coords it must reach
    is_lane = True
    group = None


@dataclass(eq=False)
class _Edge:
    """One input edge and how it attaches at each end."""

    index: int
    src: _Box
    dst: _Box
    kind: str = ""  # adjacent, skip, back, self, peer
    src_mode: str = "F"
    dst_mode: str = "F"
    src_shared: bool = False
    dst_shared: bool = False
    lanes: List[_Lane] = field(default_factory=list)
    src_port: Optional["_Port"] = None
    dst_port: Optional["_Port"] = None
    net: int = 0

    @property
    def span(self) -> int:
        return abs(self.dst.rank - self.src.rank)


@dataclass(eq=False)
class _Port:
    """A place on a flow-facing box side where one line attaches."""

    box: _Box
    role: str  # exit, entry, arc
    edges: List[_Edge]
    sort_key: Tuple[float, float, int] = (0, 0, 0)
    offset: int = 0

    @property
    def position(self) -> int:
        return self.box.cross + self.offset


@dataclass(eq=False)
class _Hook:
    """A short connection from a lane to a box side that runs along the flow."""

    box: _Box
    lane: _Lane
    edge: _Edge
    role: str  # exit, entry
    toward: int  # where the lane continues: -1 upstream, +1 downstream, 0 loop
    offset: int = 0


@dataclass(eq=False)
class _PendingLink:
    """A connection inside one channel; ends are resolved once ports exist."""

    channel: int
    edge: _Edge
    first: object  # "S", "T" or a _Lane
    first_upstream: bool
    second: object
    second_upstream: bool


@dataclass(frozen=True)
class _Metrics:
    """Orientation-dependent spacing constants."""

    tb: bool
    shadow: bool
    spacing_cross: int  # blank cells between neighbouring boxes of a layer
    spacing_flow: int  # nominal gap between two layers
    pad_cross: int  # extra cells the old layout reserved for a box shadow
    pad_flow: int
    port_pitch: int  # distance between ports on a flow-facing side
    hook_pitch: int  # distance between hooks on a side along the flow
    track_pitch: int  # distance between tracks in a channel
    lane_pitch: int  # distance between neighbouring lanes
    lane_gap: int  # blank cells between a lane and a box
    hook_gap: int  # distance from a box border to its nearest hooked lane
    arrow_lead: int  # cells of line required right before an arrowhead
    stroke_gap: int  # see channel_router.route_channel
    group_gap: int  # blank cells outside a group border

    @property
    def shadow_size(self) -> int:
        return 1 if self.shadow else 0

    @classmethod
    def for_options(cls, options: PlannerOptions) -> "_Metrics":
        shadow = options.shadow
        if options.direction == "TB":
            return cls(
                tb=True,
                shadow=shadow,
                spacing_cross=options.horizontal_spacing,
                spacing_flow=options.vertical_spacing,
                pad_cross=1 if shadow else 0,
                pad_flow=2 if shadow else 0,
                port_pitch=2,
                hook_pitch=1,
                track_pitch=1,
                lane_pitch=3,
                lane_gap=3,
                hook_gap=5,
                arrow_lead=0,
                stroke_gap=1,
                group_gap=4,
            )
        return cls(
            tb=False,
            shadow=shadow,
            spacing_cross=options.vertical_spacing,
            spacing_flow=options.horizontal_spacing,
            pad_cross=2 if shadow else 0,
            pad_flow=1 if shadow else 0,
            port_pitch=1,
            hook_pitch=2,
            track_pitch=2,
            lane_pitch=2,
            lane_gap=1,
            hook_gap=2,
            arrow_lead=1,
            stroke_gap=0,
            group_gap=2,
        )


# ── ranks ───────────────────────────────────────────────────────────────


def unique_edges(connections: Sequence[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Input edges without repeats, in the order they were first written."""
    return list(dict.fromkeys(connections))


def assign_ranks(
    connections: Sequence[Tuple[str, str]],
    groups: Sequence[GroupDefinition],
    layout_engine,
) -> List[List[str]]:
    """
    Decide which layer every node belongs to.

    Without groups this is exactly the layering the layout engine produces.
    With groups, every group is first collapsed into a single unit so that
    all of its members land in the same layer (groups are drawn across the
    flow), and the units are layered instead.

    Args:
        connections: Input edges.
        groups: Group definitions (may be empty).
        layout_engine: Object with a ``layout(connections)`` method returning
            a result with ``layers``.

    Returns:
        Node names per layer, upstream layer first.
    """
    edges = unique_edges(connections)
    nodes = list(dict.fromkeys(name for edge in edges for name in edge))
    if not groups:
        return [list(layer) for layer in layout_engine.layout(edges).layers]

    unit_of = {name: name for name in nodes}
    for group in groups:
        for member in group.members:
            if member in unit_of:
                unit_of[member] = GROUP_UNIT_PREFIX + group.name

    unit_edges = unique_edges(
        [(unit_of[s], unit_of[t]) for s, t in edges if unit_of[s] != unit_of[t]]
    )
    unit_rank: Dict[str, int] = {}
    if unit_edges:
        for rank, layer in enumerate(layout_engine.layout(unit_edges).layers):
            for unit in layer:
                unit_rank[unit] = rank

    layers: List[List[str]] = [
        [] for _ in range(1 + max(unit_rank.values(), default=0))
    ]
    for name in nodes:
        layers[unit_rank.get(unit_of[name], 0)].append(name)
    return [layer for layer in layers if layer]


# ── small helpers ───────────────────────────────────────────────────────


def spread_offsets(
    count: int, size: int, pitch: int, round_up: bool
) -> Tuple[List[int], int]:
    """
    Place ``count`` attachment points along a box side of length ``size``.

    Points stay off the corners and at least ``pitch`` apart. One point sits
    in the middle; two or more are spread evenly when the side is roomy and
    packed around the middle otherwise. A side that is too short is grown.

    Args:
        count: Number of points wanted.
        size: Length of the side, corners included.
        pitch: Minimum distance between two points.
        round_up: Which of the two middle cells an even-length side uses.

    Returns:
        (offsets from the start of the side, possibly larger side length).
    """
    if count == 0:
        return [], size
    span = (count - 1) * pitch
    # Points that need a blank cell between them also keep one border cell
    # between themselves and the corners, so the side reads as "─┬─┬─".
    margin = 2 if pitch > 1 and count > 1 else 1
    size = max(size, span + 2 * margin + 1)
    if count == 1:
        return [size // 2 if round_up else (size - 1) // 2], size

    step = (size - 4) // (count + 1)
    if pitch > 1 and step >= pitch:
        return [2 + step * (i + 1) for i in range(count)], size

    start = (size - span) // 2 if round_up else (size - 1 - span) // 2
    start = max(margin, min(start, size - 1 - margin - span))
    return [start + i * pitch for i in range(count)], size


def settle(desired: Sequence[float], weights: Sequence[float], gaps: Sequence[int]):
    """
    Put items as close as possible to where they want to be, in order.

    Minimises the weighted squared distance of every item from its desired
    position, subject to item ``i + 1`` being at least ``gaps[i]`` after item
    ``i`` (pool-adjacent-violators on the gap-adjusted positions).

    Args:
        desired: Wanted position of each item, in order.
        weights: How strongly each item insists.
        gaps: Minimum distance between consecutive items (one fewer than items).

    Returns:
        Integer positions, one per item.
    """
    offsets = [0]
    for gap in gaps:
        offsets.append(offsets[-1] + gap)

    # Each block: [weighted sum, weight, item count]
    blocks: List[List[float]] = []
    for want, weight, offset in zip(desired, weights, offsets):
        blocks.append([(want - offset) * weight, weight, 1])
        while len(blocks) > 1 and (
            blocks[-2][0] / blocks[-2][1] >= blocks[-1][0] / blocks[-1][1]
        ):
            total, weight_sum, count = blocks.pop()
            blocks[-1][0] += total
            blocks[-1][1] += weight_sum
            blocks[-1][2] += count

    positions: List[int] = []
    for total, weight_sum, count in blocks:
        base = _round_half_down(total / weight_sum)
        for _ in range(int(count)):
            positions.append(base + offsets[len(positions)])
    return positions


def _round_half_down(value: float) -> int:
    whole = int(value // 1)
    return whole + 1 if value - whole > 0.5 else whole


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _sorted_keeping_slots(
    items: List, key: Callable[[object], Optional[float]]
) -> List:
    """Sort the items that have a key; items without one keep their slot."""
    keyed = [(key(item), index, item) for index, item in enumerate(items)]
    slots = [index for value, index, _ in keyed if value is not None]
    movers = sorted((entry for entry in keyed if entry[0] is not None))
    result = list(items)
    for slot, (_, _, item) in zip(slots, movers):
        result[slot] = item
    return result


# ── the planner ─────────────────────────────────────────────────────────


class RoutePlanner:
    """
    Plans box positions and edge routes for one diagram.

    Example:
        >>> planner = RoutePlanner(PlannerOptions(direction="TB"))
        >>> plan = planner.plan(connections, groups, layers, box_dimensions)
        >>> for (x, y), glyph in plan.grid.cells():
        ...     canvas.set(x, y, glyph)
    """

    def __init__(self, options: Optional[PlannerOptions] = None):
        self.options = options or PlannerOptions()
        self.m = _Metrics.for_options(self.options)

    # ── entry point ─────────────────────────────────────────────────────

    def plan(
        self,
        connections: Sequence[Tuple[str, str]],
        groups: Sequence[GroupDefinition],
        layers: Sequence[Sequence[str]],
        box_dimensions: Dict[str, BoxDimensions],
    ) -> RoutePlan:
        """
        Plan a whole diagram.

        Args:
            connections: Input edges as (source, target) names.
            groups: Group definitions (may be empty).
            layers: Node names per layer, from ``assign_ranks``.
            box_dimensions: Natural size of every node box.

        Returns:
            A ``RoutePlan`` ready to be painted.
        """
        self._setup(connections, groups, layers, box_dimensions)
        self._choose_attachments()
        self._build_lanes()
        self._order_layers()
        self._settle_peers()
        self._allocate_ports()
        self._allocate_hooks()
        self._reserve_group_titles()
        self._assign_cross_positions()
        self._straighten_ports()
        self._route_channels()
        self._assign_flow_positions()
        return self._assemble()

    # ── step 1: model ───────────────────────────────────────────────────

    def _setup(self, connections, groups, layers, box_dimensions) -> None:
        m = self.m
        self.groups: List[GroupDefinition] = [g for g in groups if g.members]
        group_of = {
            member: group.name for group in self.groups for member in group.members
        }

        self.boxes: Dict[str, _Box] = {}
        self.layers: List[List[object]] = []
        for rank, layer in enumerate(layers):
            row: List[object] = []
            for name in layer:
                dims = box_dimensions[name]
                box = _Box(
                    name=name,
                    dims=dims,
                    rank=rank,
                    cross_size=dims.width if m.tb else dims.height,
                    flow_size=dims.height if m.tb else dims.width,
                    group=group_of.get(name),
                )
                self.boxes[name] = box
                row.append(box)
            self.layers.append(self._with_groups_together(row))

        self.edges: List[_Edge] = [
            _Edge(index, self.boxes[s], self.boxes[t])
            for index, (s, t) in enumerate(unique_edges(connections))
        ]
        self.links: List[_PendingLink] = []
        self.lanes: List[_Lane] = []
        self.title_reserve: Dict[str, Tuple[int, int]] = {}

    def _with_groups_together(self, row: List[_Box]) -> List[object]:
        """Reorder a layer so members of one group sit next to each other."""
        members: Dict[str, List[_Box]] = {}
        for box in row:
            if box.group:
                members.setdefault(box.group, []).append(box)
        result: List[object] = []
        placed: Set[str] = set()
        for box in row:
            if not box.group:
                result.append(box)
            elif box.group not in placed:
                placed.add(box.group)
                result.extend(members[box.group])
        return result

    # ── step 2: how each edge attaches ──────────────────────────────────

    def _choose_attachments(self) -> None:
        for edge in self.edges:
            a, b = edge.src.rank, edge.dst.rank
            if edge.src is edge.dst:
                edge.kind = "self"
            elif b == a:
                edge.kind = "peer"
            elif b < a:
                edge.kind = "back"
            else:
                edge.kind = "adjacent" if b == a + 1 else "skip"

        if self.m.tb:
            self._choose_attachments_tb()
        else:
            self._choose_attachments_lr()

    def _choose_attachments_tb(self) -> None:
        """
        TB: bottoms and tops are long, so every edge gets its own port there.

        Back edges and self loops enter the *side* of their target while a
        content row is free (the familiar ``┌───►│ box │`` look) and fall back
        to the top border after that.
        """
        side_entries: Dict[_Box, int] = {}
        for edge in self.edges:
            if edge.kind not in ("back", "self"):
                continue
            target = edge.dst
            room = 2 * (target.flow_size - 2)
            if not target.group and side_entries.get(target, 0) < room:
                side_entries[target] = side_entries.get(target, 0) + 1
                edge.dst_mode = "X"
            elif edge.kind == "self":
                edge.dst_mode = "A"

    def _choose_attachments_lr(self) -> None:
        """
        LR: the facing sides usually have a single row, so they are shared.

        Edges between neighbouring columns share a line as a star. Skip
        edges, back edges and whatever does not fit use the roomy top and
        bottom borders instead. Boxes inside groups have other boxes above
        and below, so they keep everything on the facing sides and grow
        taller when needed.
        """
        for edge in self.edges:
            if edge.kind in ("skip", "back"):
                edge.src_mode = "F" if edge.src.group else "X"
                edge.dst_mode = "F" if edge.dst.group else "X"
            elif edge.kind == "self":
                if edge.src.group:
                    edge.dst_mode = "A"
                else:
                    edge.src_mode = edge.dst_mode = "X"

        adjacent = [edge for edge in self.edges if edge.kind == "adjacent"]
        fan_out: Dict[_Box, int] = {}
        fan_in: Dict[_Box, int] = {}
        for edge in adjacent:
            fan_out[edge.src] = fan_out.get(edge.src, 0) + 1
            fan_in[edge.dst] = fan_in.get(edge.dst, 0) + 1

        centred_on_source: Dict[_Edge, bool] = {}
        for edge in adjacent:
            out_degree, in_degree = fan_out[edge.src], fan_in[edge.dst]
            centred_on_source[edge] = in_degree == 1 or (
                out_degree > 1 and out_degree >= in_degree
            )

        # A side holds one shared port plus one port per edge whose star is
        # centred at the other end. Edges that do not fit leave by a hook.
        for box in self.boxes.values():
            if box.group:
                continue
            rows = box.cross_size - 2
            outgoing = [e for e in adjacent if e.src is box]
            lone = [e for e in outgoing if not centred_on_source[e]]
            shared = 1 if len(lone) < len(outgoing) else 0
            for edge in lone[max(0, rows - shared) :]:
                edge.src_mode = "X"

            incoming = [e for e in adjacent if e.dst is box]
            lone = [e for e in incoming if centred_on_source[e]]
            shared = 1 if len(lone) < len(incoming) else 0
            for edge in lone[max(0, rows - shared) :]:
                edge.dst_mode = "X"

        for edge in adjacent:
            edge.src_shared = centred_on_source[edge] and edge.src_mode == "F"
            edge.dst_shared = not centred_on_source[edge] and edge.dst_mode == "F"

    # ── step 3: lanes ───────────────────────────────────────────────────

    def _new_lane(self, edge: _Edge, rank: int) -> _Lane:
        lane = _Lane(edge=edge, rank=rank)
        edge.lanes.append(lane)
        self.lanes.append(lane)
        return lane

    def _link(self, channel, edge, first, first_up, second, second_up) -> None:
        self.links.append(
            _PendingLink(channel, edge, first, first_up, second, second_up)
        )

    def _build_lanes(self) -> None:
        """
        Give every edge a lane in each layer it has to travel past.

            forward edge             back edge (source below target)

            src ─┐                   ┌──► dst        lane in dst's layer
                 │  lane             │
                 └─► dst             └─── src        lane in src's layer
        """
        for edge in self.edges:
            a, b = edge.src.rank, edge.dst.rank
            if edge.kind in ("adjacent", "skip"):
                self._build_forward(edge, a, b)
            elif edge.kind == "back" or (edge.kind == "self" and edge.dst_mode != "A"):
                self._build_backward(edge, a, b)
            elif edge.kind == "self":
                self._link(a, edge, "S", True, "T", True)
            # Peers get no lanes; they are settled once the order is known.
        self._choose_lane_sides()

    def _choose_lane_sides(self) -> None:
        """
        Pick the side of the boxes each travelling edge starts out on.

        Back edges default to the "before" side (the left margin in TB, above
        the row in LR) and forward edges to the "after" side. Edges hooked
        onto the long box borders in LR read as arcs over and under a row of
        boxes, and two arcs on the same side cross when their ends
        interleave, so each arc takes the side where it interleaves least:

            ┌───────────┐                 arcs 0-2 and 1-3 interleave;
            │     ┌─────┼─────┐           drawn on opposite sides they
            0     1     2     3           do not cross at all
        """
        placed: Dict[int, List[Tuple[int, int]]] = {BEFORE: [], AFTER: []}
        for edge in self.edges:
            if not edge.lanes:
                continue
            usual = AFTER if edge.kind in ("adjacent", "skip") else BEFORE
            side = usual
            hooked_both_ends = edge.src_mode == "X" and edge.dst_mode == "X"
            if not self.m.tb and hooked_both_ends and edge.kind != "self":
                low, high = sorted((edge.src.rank, edge.dst.rank))

                def clashes(candidate: int) -> int:
                    return sum(
                        1
                        for other_low, other_high in placed[candidate]
                        if low < other_low < high < other_high
                        or other_low < low < other_high < high
                    )

                side = min((usual, -usual), key=clashes)
                placed[side].append((low, high))
            for lane in edge.lanes:
                lane.side = side

    def _build_forward(self, edge: _Edge, a: int, b: int) -> None:
        ranks = list(range(a + 1, b))
        if edge.src_mode == "X":
            ranks.insert(0, a)
        if edge.dst_mode == "X":
            ranks.append(b)
        lanes = [self._new_lane(edge, rank) for rank in ranks]

        if edge.src_mode == "X":
            lanes[0].anchor, lanes[0].hooked = edge.src, True
        if edge.dst_mode == "X":
            lanes[-1].anchor, lanes[-1].hooked = edge.dst, True

        stations: List[object] = list(lanes)
        if edge.src_mode == "F":
            stations.insert(0, "S")
        if edge.dst_mode == "F":
            stations.append("T")

        # Stations sit in consecutive layers, starting with the source's.
        for offset, (upper, lower) in enumerate(zip(stations, stations[1:])):
            self._link(a + offset, edge, upper, True, lower, False)
            upper_item = edge.src if upper == "S" else upper
            lower_item = edge.dst if lower == "T" else lower
            upper_item.downs.append(lower_item)
            lower_item.ups.append(upper_item)

    def _build_backward(self, edge: _Edge, a: int, b: int) -> None:
        by_rank = {rank: self._new_lane(edge, rank) for rank in range(a, b - 1, -1)}
        first, last = by_rank[a], by_rank[b]
        # Only a hooked lane has to stay beside its box. The lane of a
        # U-turn is free to line up with the rest of its edge instead.
        if edge.src_mode == "X":
            first.anchor, first.hooked = edge.src, True
        if edge.dst_mode == "X":
            last.anchor, last.hooked = edge.dst, True

        if edge.src_mode == "F":
            self._link(a, edge, "S", True, first, True)
        for rank in range(b, a):
            upper, lower = by_rank[rank], by_rank[rank + 1]
            self._link(rank, edge, upper, True, lower, False)
            upper.downs.append(lower)
            lower.ups.append(upper)
        if edge.dst_mode == "F":
            self._link(b - 1, edge, last, False, "T", False)

    # ── step 4: order within layers ─────────────────────────────────────

    def _order_layers(self) -> None:
        """
        Order boxes and lanes in every layer to keep crossings low.

        Barycenter sweeps move free items toward the average position of
        their neighbours in the layer above (then below). Lanes that belong
        next to a box (hooks, U-turns) are then put back right beside it, on
        the side their own neighbours pull them toward.
        """
        self._place_free_lanes()
        for rank in range(len(self.layers)):
            self._place_anchored_lanes(rank, lambda item: None)
        self._number()

        best = (self._crossings(), self._snapshot())
        for _ in range(6):
            for downward in (True, False):
                self._sweep(downward)
                score = self._crossings()
                if score < best[0]:
                    best = (score, self._snapshot())
        self._restore(best[1])

    def _place_free_lanes(self) -> None:
        """Insert pass-through lanes between the positions of their two ends."""

        def fraction(box: _Box) -> float:
            layer = self.layers[box.rank]
            return layer.index(box) / max(1, len(layer) - 1)

        box_fraction = {box: fraction(box) for box in self.boxes.values()}
        pending: Dict[int, List[Tuple[float, int, int, _Lane]]] = {}
        for lane in self.lanes:
            if lane.anchor is not None:
                continue
            edge = lane.edge
            start, end = box_fraction[edge.src], box_fraction[edge.dst]
            travelled = abs(lane.rank - edge.src.rank) / max(1, edge.span)
            where = start + (end - start) * travelled
            # Next to a box at the same spot: back edges start out before
            # it (the margin they have always used), forward edges after.
            tie = -1 if lane.side == BEFORE else 1
            pending.setdefault(lane.rank, []).append((where, tie, edge.index, lane))

        for rank, entries in pending.items():
            layer = self.layers[rank]
            keyed = [(box_fraction[box], 0, i, box) for i, box in enumerate(layer)]
            keyed += entries
            ordered = [item for *_, item in sorted(keyed, key=lambda t: t[:3])]
            self.layers[rank] = self._regroup(ordered)

    def _regroup(self, items: List[object]) -> List[object]:
        """Move lanes that ended up inside a group to just after it."""
        result: List[object] = []
        waiting: List[object] = []
        open_group: Optional[str] = None
        remaining: Dict[str, int] = {}
        for item in items:
            if item.group:
                remaining[item.group] = remaining.get(item.group, 0) + 1
        for item in items:
            if item.group:
                open_group = item.group
                remaining[item.group] -= 1
                result.append(item)
                if remaining[item.group] == 0:
                    open_group = None
                    result.extend(waiting)
                    waiting = []
            elif open_group:
                waiting.append(item)
            else:
                result.append(item)
        return result + waiting

    def _number(self) -> None:
        for layer in self.layers:
            for index, item in enumerate(layer):
                item.order = index

    def _snapshot(self):
        return (
            [list(layer) for layer in self.layers],
            {lane: lane.side for lane in self.lanes},
        )

    def _restore(self, snapshot) -> None:
        layers, sides = snapshot
        self.layers = [list(layer) for layer in layers]
        for lane, side in sides.items():
            lane.side = side
        self._number()

    def _crossings(self) -> int:
        """Crossings between consecutive layers, counted on item order."""
        total = 0
        for layer in self.layers[:-1]:
            pairs = sorted(
                (item.order, lower.order) for item in layer for lower in item.downs
            )
            for i, (upper_a, lower_a) in enumerate(pairs):
                for upper_b, lower_b in pairs[i + 1 :]:
                    if upper_a < upper_b and lower_a > lower_b:
                        total += 1
        return total

    def _sweep(self, downward: bool) -> None:
        count = len(self.layers)
        ranks = range(1, count) if downward else range(count - 2, -1, -1)
        for rank in ranks:

            def barycenter(item, downward=downward) -> Optional[float]:
                neighbours = item.ups if downward else item.downs
                if not neighbours:
                    return None
                return sum(n.order for n in neighbours) / len(neighbours)

            layer = self.layers[rank]
            free = [item for item in layer if not (item.is_lane and item.anchor)]

            units: List[List[object]] = []
            for item in free:
                if item.group and units and units[-1][0].group == item.group:
                    units[-1].append(item)
                else:
                    units.append([item])

            def unit_key(unit) -> Optional[float]:
                values = [v for v in map(barycenter, unit) if v is not None]
                return sum(values) / len(values) if values else None

            units = _sorted_keeping_slots(units, unit_key)
            ordered = [
                item
                for unit in units
                for item in _sorted_keeping_slots(unit, barycenter)
            ]
            self.layers[rank] = ordered
            self._place_anchored_lanes(rank, barycenter)
            for index, item in enumerate(self.layers[rank]):
                item.order = index

    def _place_anchored_lanes(self, rank: int, barycenter) -> None:
        """
        Put every anchored lane of a layer right next to its box.

        ``self.layers[rank]`` must hold only the free items when this is
        called. A lane goes on the side its own neighbours pull it toward;
        without such a pull it keeps the side it had.
        """
        layer = self.layers[rank]
        used: Dict[Tuple[_Box, int], int] = {}
        slots: Dict[Tuple[int, int], List[Tuple[float, int, int, _Lane]]] = {}
        for lane in self.lanes:
            if lane.rank != rank or lane.anchor is None:
                continue
            box = lane.anchor
            pull, own = barycenter(lane), barycenter(box)
            side = lane.side
            if pull is not None and own is not None and pull != own:
                side = BEFORE if pull < own else AFTER
            if lane.hooked and self.m.tb:
                # A TB box side only has as many hook rows as text rows.
                if used.get((box, side), 0) >= box.flow_size - 2:
                    side = -side
                used[(box, side)] = used.get((box, side), 0) + 1
            lane.side = side

            block = [
                index
                for index, item in enumerate(layer)
                if item is box or (box.group and item.group == box.group)
            ]
            at = block[0] if side == BEFORE else block[-1] + 1
            near = own if own is not None else 0.0
            # Longer edges nest outside shorter ones.
            nest = -lane.edge.span if side == BEFORE else lane.edge.span
            slots.setdefault((at, side), []).append(
                (pull if pull is not None else near, nest, lane.edge.index, lane)
            )

        # Insert from the end so earlier indexes stay valid. Where two boxes
        # share a gap, the lanes of the right-hand box go in first so that
        # the lanes of the left-hand box end up next to their own box.
        for at, side in sorted(slots, key=lambda slot: (-slot[0], slot[1])):
            entries = sorted(slots[(at, side)], key=lambda t: t[:3])
            layer[at:at] = [lane for *_, lane in entries]

    # ── step 5: edges between boxes of one layer ────────────────────────

    def _settle_peers(self) -> None:
        """
        Same-layer edges: a direct line between neighbours, else an arc.

            ┌───┐      ┌───┐          ┌───┐   ┌───┐   ┌───┐
            │ A │─────►│ B │          │ A │   │ B │   │ C │
            └───┘      └───┘          └─┬─┘   └───┘   └─▲─┘
                                        └───────────────┘
        """
        for edge in self.edges:
            if edge.kind != "peer":
                continue
            src, dst = edge.src, edge.dst
            side = AFTER if dst.order > src.order else BEFORE
            neighbours = abs(dst.order - src.order) == 1
            if neighbours and side not in src.direct and -side not in dst.direct:
                src.direct[side] = dst.direct[-side] = edge
                edge.src_mode = edge.dst_mode = "D"
            else:
                edge.dst_mode = "A"
                self._link(src.rank, edge, "S", True, "T", True)

    # ── step 6: ports on the flow-facing sides ──────────────────────────

    def _allocate_ports(self) -> None:
        for edge in self.edges:
            if edge.src_mode == "F":
                self._port_for(edge, edge.src, edge.src.out_ports, "exit", "src")
            if edge.dst_mode == "F":
                self._port_for(edge, edge.dst, edge.dst.in_ports, "entry", "dst")
            elif edge.dst_mode == "A":
                port = _Port(edge.dst, "arc", [edge])
                edge.dst.out_ports.append(port)
                edge.dst_port = port

        self.links_of: Dict[_Edge, List[_PendingLink]] = {}
        for link in self.links:
            self.links_of.setdefault(link.edge, []).append(link)
        for port in self._all_ports():
            keys = [self._port_key(port, edge) for edge in port.edges]
            port.sort_key = (
                sum(k[0] for k in keys) / len(keys),
                sum(k[1] for k in keys) / len(keys),
                port.edges[0].index,
            )

        m = self.m
        for box in self.boxes.values():
            sides = (box.out_ports, box.in_ports)
            for ports in sides:
                ports.sort(key=lambda port: port.sort_key)
                # A side that is too short makes the whole box grow.
                _, box.cross_size = spread_offsets(
                    len(ports), box.cross_size, m.port_pitch, round_up=m.tb
                )
            for ports in sides:
                offsets, _ = spread_offsets(
                    len(ports), box.cross_size, m.port_pitch, round_up=m.tb
                )
                for port, offset in zip(ports, offsets):
                    port.offset = offset

        # Edges that share a port share a line, and therefore a net.
        next_net = 1
        for port in self._all_ports():
            if len(port.edges) > 1:
                for edge in port.edges:
                    edge.net = next_net
                next_net += 1
        for edge in self.edges:
            if not edge.net:
                edge.net = next_net
                next_net += 1

    def _port_for(self, edge, box, ports, role, end) -> None:
        shared = edge.src_shared if end == "src" else edge.dst_shared
        port = None
        if shared:
            for candidate in ports:
                mate = candidate.edges[0]
                mate_shared = mate.src_shared if end == "src" else mate.dst_shared
                if candidate.role == role and mate_shared:
                    port = candidate
                    break
        if port is None:
            port = _Port(box, role, [])
            ports.append(port)
        port.edges.append(edge)
        if end == "src":
            edge.src_port = port
        else:
            edge.dst_port = port

    def _all_ports(self) -> List[_Port]:
        return [
            port for box in self.boxes.values() for port in box.out_ports + box.in_ports
        ]

    def _port_key(self, port: _Port, edge: _Edge) -> Tuple[float, float]:
        """
        Where along the side a port belongs.

        Lines that turn back toward an item on the left come first (nearest
        item outermost... innermost last), then lines that cross the channel
        in the order of what they connect to, then lines that turn back
        toward the right. That keeps lines of one box from crossing.
        """
        box = port.box
        other = self._other_end(port, edge)
        if other.rank != box.rank:
            return (1.0, float(other.order))
        if other is box:
            # A self arc: exit first, re-entry right after it.
            return (1.5, 0.0 if port.role == "exit" else 1.0)
        return (0.0 if other.order < box.order else 2.0, -float(other.order))

    def _other_end(self, port: _Port, edge: _Edge):
        """The item a port's line reaches first inside its channel."""
        here = "S" if port is edge.src_port else "T"
        for link in self.links_of[edge]:
            ends = (link.first, link.second)
            if here in ends:
                other = ends[1] if ends[0] == here else ends[0]
                if other == "S":
                    return edge.src
                return edge.dst if other == "T" else other
        raise AssertionError(  # pragma: no cover - every port is made for a link
            f"edge {edge.index} has a port without a link"
        )

    # ── step 7: hooks on the sides that run along the flow ──────────────

    def _allocate_hooks(self) -> None:
        for lane in self.lanes:
            if not lane.hooked:
                continue
            edge, box = lane.edge, lane.anchor
            forward = edge.kind in ("adjacent", "skip")
            if edge.src_mode == "X" and edge.src is box and lane is edge.lanes[0]:
                toward = 0 if edge.kind == "self" else (1 if forward else -1)
                box.hooks[lane.side].append(_Hook(box, lane, edge, "exit", toward))
            if edge.dst_mode == "X" and edge.dst is box and lane is edge.lanes[-1]:
                toward = -1 if forward else 1
                if edge.kind == "self" and edge.src_mode == "X":
                    toward = 0
                box.hooks[lane.side].append(_Hook(box, lane, edge, "entry", toward))

        m = self.m
        for box in self.boxes.values():
            for side in (BEFORE, AFTER):
                hooks = box.hooks[side]

                def nesting(hook, box=box):
                    distance = abs(hook.lane.order - box.order)
                    if hook.toward < 0:
                        return (0, distance, 0)
                    if hook.toward == 0:
                        return (1, hook.edge.index, 0 if hook.role == "exit" else 1)
                    return (2, -distance, 0)

                hooks.sort(key=nesting)
                _, box.flow_size = spread_offsets(
                    len(hooks), box.flow_size, m.hook_pitch, round_up=not m.tb
                )
            for side in (BEFORE, AFTER):
                offsets, _ = spread_offsets(
                    len(box.hooks[side]), box.flow_size, m.hook_pitch, round_up=not m.tb
                )
                for hook, offset in zip(box.hooks[side], offsets):
                    hook.offset = offset

    # ── step 8: positions across the flow ───────────────────────────────

    def _group_members(self, name: str) -> List[_Box]:
        rank = next(box.rank for box in self.boxes.values() if box.group == name)
        return [item for item in self.layers[rank] if item.group == name]

    def _reserve_group_titles(self) -> None:
        """
        Make sure every group title has room.

        A title sits on its own row above the group box. In TB the lines
        entering the group from above cross that row, so the title must fit
        beside them; a group that is too narrow for that is widened.
        """
        m = self.m
        for group in self.groups:
            members = self._group_members(group.name) if self._has(group) else []
            if not members:
                continue
            title = len(group.name)
            if not m.tb:
                widest = max(box.flow_size for box in members)
                natural = widest + m.pad_flow + 2 * GROUP_PADDING
                extra = max(0, title + 2 - natural)
                self.title_reserve[group.name] = (extra // 2, extra - extra // 2)
                continue

            # Lay the members out at their tightest and look for a free slot.
            start, blocked = 0, set()
            for box in members:
                for port in box.in_ports:
                    blocked.update(
                        range(start + port.offset - 1, start + port.offset + 2)
                    )
                end = start + box.cross_size + m.pad_cross
                start = end + m.spacing_cross
            left, right = -GROUP_PADDING, end + GROUP_PADDING - 1
            extra = max(0, title + 2 - (right - left + 1))
            before, after = extra // 2, extra - extra // 2
            if self._title_slot(left - before, right + after, title, blocked) is None:
                after = max(after, max(blocked) + 2 + title - right)
            self.title_reserve[group.name] = (before, after)

    def _has(self, group: GroupDefinition) -> bool:
        return any(box.group == group.name for box in self.boxes.values())

    @staticmethod
    def _title_slot(left: int, right: int, title: int, blocked: Set[int]):
        """Start column for a title between two borders, nearest the centre."""
        centred = left + (right - left + 1 - title) // 2
        candidates = range(left + 1, right - title + 1)
        for start in sorted(candidates, key=lambda s: (abs(s - centred), s)):
            if not any(c in blocked for c in range(start, start + title)):
                return start
        return None

    def _extent_before(self, item) -> int:
        """
        Cells an item occupies before its own position.

        Only asked about the first item after a gap, so a grouped box here is
        always the first member of its group: the group border (and in LR
        the title row) lies before it.
        """
        if item.is_lane or not item.group:
            return 0
        if self.m.tb:
            return GROUP_PADDING + self.title_reserve[item.group][0]
        return GROUP_PADDING + GROUP_TITLE_ROWS

    def _extent_after(self, item) -> int:
        """Offset of the last cell an item occupies after its own position."""
        if item.is_lane:
            return 0
        m = self.m
        if item.group and self._group_members(item.group)[-1] is item:
            reserve = self.title_reserve[item.group][1] if m.tb else 0
            return item.cross_size + m.pad_cross + 2 + reserve + m.shadow_size
        return item.cross_size - 1 + m.shadow_size

    def _separation(self, left, right) -> int:
        """Minimum distance between the positions of two neighbouring items."""
        m = self.m
        if left.is_lane and right.is_lane:
            return m.lane_pitch
        if left.is_lane and not right.is_lane:
            if left.hooked and left.anchor is right and not right.group:
                return m.hook_gap
            return m.lane_gap + 1 + self._extent_before(right)
        if right.is_lane:
            if right.hooked and right.anchor is left and not left.group:
                return left.cross_size - 1 + m.hook_gap
            return self._extent_after(left) + m.lane_gap + 1
        if left.group and left.group == right.group:
            usual = left.cross_size + m.pad_cross + m.spacing_cross
            if left.direct.get(AFTER) is not None:
                # A direct line needs room for at least "──►" between boxes.
                return max(usual, left.cross_size + 3)
            return usual
        if left.group or right.group:
            gap = m.group_gap
            return self._extent_after(left) + gap + 1 + self._extent_before(right)
        return left.cross_size + m.pad_cross + m.spacing_cross

    def _assign_cross_positions(self) -> None:
        """
        Place every box and lane across the flow.

        Each layer starts packed and centred, as the original layout did.
        Sweeps then pull every item toward the items it connects to (so
        lanes run straight and parents sit over their children) while
        keeping the order and the minimum distances. The last pass works
        outward from the widest layer so that symmetric diagrams stay
        symmetric.
        """
        self._collect_ties()
        gaps = [
            [self._separation(a, b) for a, b in zip(layer, layer[1:])]
            for layer in self.layers
        ]
        widths = []
        for layer, layer_gaps in zip(self.layers, gaps):
            position = 0
            for item, gap in zip(layer, [0] + layer_gaps):
                position += gap
                item.cross = position
            widths.append(position + self._extent_after(layer[-1]) + 1)
        widest = max(widths)
        for layer, width in zip(self.layers, widths):
            for item in layer:
                item.cross += (widest - width) // 2

        count = len(self.layers)
        for _ in range(3):
            for rank in range(1, count):
                self._settle_layer(rank, gaps[rank], use_up=True, use_down=False)
            for rank in range(count - 2, -1, -1):
                self._settle_layer(rank, gaps[rank], use_up=False, use_down=True)

        anchor = widths.index(widest)
        for rank in range(anchor + 1, count):
            self._settle_layer(rank, gaps[rank], use_up=True, use_down=False)
        for rank in range(anchor - 1, -1, -1):
            self._settle_layer(rank, gaps[rank], use_up=False, use_down=True)

    def _collect_ties(self) -> None:
        """For every item, the points in neighbouring layers it lines up with."""
        self.ties_up: Dict[object, List[Tuple[object, object]]] = {}
        self.ties_down: Dict[object, List[Tuple[object, object]]] = {}
        for link in self.links:
            if link.first_upstream == link.second_upstream:
                continue  # both ends in one layer: a U-turn, not a tie
            upper = self._resolve(link.edge, link.first)
            lower = self._resolve(link.edge, link.second)
            upper_item = upper.box if isinstance(upper, _Port) else upper
            lower_item = lower.box if isinstance(lower, _Port) else lower
            self.ties_down.setdefault(upper_item, []).append((upper, lower))
            self.ties_up.setdefault(lower_item, []).append((lower, upper))

    @staticmethod
    def _resolve(edge: _Edge, end):
        if end == "S":
            return edge.src_port
        if end == "T":
            return edge.dst_port
        return end

    @staticmethod
    def _position_of(point) -> int:
        return point.position if isinstance(point, _Port) else point.cross

    def _settle_layer(self, rank, gaps, use_up: bool, use_down: bool) -> None:
        layer = self.layers[rank]
        desired, weights = [], []
        for item in layer:
            ties = []
            if use_up:
                ties += self.ties_up.get(item, [])
            if use_down:
                ties += self.ties_down.get(item, [])
            # A box lines up with the boxes it connects to when it has any;
            # lines to lanes then simply get a longer track.
            box_ties = [
                tie for tie in ties if all(isinstance(end, _Port) for end in tie)
            ]
            if box_ties and not item.is_lane:
                ties = box_ties
            wants = [self._wanted_position(item, mine, theirs) for mine, theirs in ties]
            if wants:
                desired.append(_median(wants))
                weights.append(self._insistence(item, ties))
            else:
                desired.append(float(item.cross))
                weights.append(0.25)
        for item, position in zip(layer, settle(desired, weights, gaps)):
            item.cross = position

    @staticmethod
    def _insistence(item, ties) -> float:
        """
        How strongly an item holds on to its wanted position.

        A lane following another lane insists most, so long edges run
        straight. A lane that only connects to boxes gives way to them:
        moving it merely lengthens a track, while moving a box bends the
        column of boxes it belongs to.
        """
        if not item.is_lane:
            return 1.0
        follows_a_lane = any(not isinstance(theirs, _Port) for _, theirs in ties)
        return 4.0 if follows_a_lane else 0.5

    def _middle(self, box: _Box) -> int:
        """Offset of the middle cell of a box's flow-facing side."""
        size = box.cross_size
        return size // 2 if self.m.tb else (size - 1) // 2

    def _wanted_position(self, item, mine, theirs) -> int:
        """
        Where ``item`` would sit to line up with one of its connections.

        Two boxes line up middle to middle, which keeps chains in a straight
        column; their ports are slid into line afterwards. A lane cannot
        slide, so anything connected to a lane lines up with it exactly.
        """
        if isinstance(mine, _Port) and isinstance(theirs, _Port):
            return theirs.box.cross + self._middle(theirs.box) - self._middle(item)
        return self._position_of(theirs) - (self._position_of(mine) - item.cross)

    def _straighten_ports(self) -> None:
        """
        Slide lone ports sideways when that makes their line straight.

            ┌────────┐                 ┌────────┐
            │   A    │                 │   A    │
            └───┬─┬──┘                 └───┬─┬──┘
                │ └┐        becomes        │ │
                │  ▼                       │ ▼
                │ ┌────────┐             ┌────────┐
                  │   B    │             │   B    │

        Only a port that is alone on its side moves, and only when the other
        end of its line is within the straight part of the side, clear of
        the corners.
        """
        peer: Dict[_Port, List[object]] = {}
        for ties in list(self.ties_up.values()) + list(self.ties_down.values()):
            for mine, theirs in ties:
                if isinstance(mine, _Port):
                    peer.setdefault(mine, []).append(theirs)

        for side in ("in_ports", "out_ports"):
            for box in self.boxes.values():
                ports = getattr(box, side)
                if len(ports) != 1 or len(peer.get(ports[0], [])) != 1:
                    continue
                port = ports[0]
                offset = self._position_of(peer[port][0]) - box.cross
                # Stay a cell away from the corners where there is room.
                margin = 2 if box.cross_size >= 5 else 1
                if not margin <= offset <= box.cross_size - 1 - margin:
                    continue
                previous, port.offset = port.offset, offset
                # A line entering a group from above must not run through
                # the group's title; if sliding leaves the title no room,
                # the port stays where it was.
                if self.m.tb and box.group and side == "in_ports":
                    if self._group_title_start(box.group) is None:
                        port.offset = previous

    # ── step 9: tracks in the channels ──────────────────────────────────

    def _route_channels(self) -> None:
        """Route every gap between layers (and the two outer margins)."""
        by_channel: Dict[int, List[Link]] = {}
        for link in self.links:
            first = self._resolve(link.edge, link.first)
            second = self._resolve(link.edge, link.second)
            by_channel.setdefault(link.channel, []).append(
                Link(
                    link.edge.net,
                    Terminal(first, self._position_of(first), link.first_upstream),
                    Terminal(second, self._position_of(second), link.second_upstream),
                )
            )
        self.channels: Dict[int, ChannelPlan] = {
            channel: route_channel(links, self.m.stroke_gap)
            for channel, links in sorted(by_channel.items())
        }

    # ── step 10: positions along the flow ───────────────────────────────

    def _layer_groups(self, rank: int) -> List[str]:
        return list(
            dict.fromkeys(item.group for item in self.layers[rank] if item.group)
        )

    def _layer_before(self, rank: int) -> int:
        """Cells before a layer that tracks of the channel above must avoid."""
        m = self.m
        reserved = 1 + m.arrow_lead
        for name in self._layer_groups(rank):
            extent = GROUP_PADDING + (
                GROUP_TITLE_ROWS if m.tb else self.title_reserve[name][0]
            )
            reserved = max(reserved, extent + 1)
        return reserved

    def _group_border_after(self, name: str) -> int:
        """Offset from the layer start to a group's downstream border."""
        m = self.m
        body = max(box.flow_size for box in self._group_members(name))
        reserve = 0 if m.tb else self.title_reserve[name][1]
        return body + m.pad_flow + 2 + reserve

    def _layer_after(self, rank: int) -> int:
        """Offset from a layer's start to the first cell usable by tracks."""
        m = self.m
        body = max(item.flow_size for item in self.layers[rank] if not item.is_lane)
        first = body + 1
        for name in self._layer_groups(rank):
            first = max(first, self._group_border_after(name) + m.shadow_size + 2)
        return first

    def _assign_flow_positions(self) -> None:
        """
        Stack the layers along the flow, each gap as tall as its tracks need.

        A gap keeps its familiar size (and its one track keeps its familiar
        row) whenever that is enough; it only grows for extra tracks.
        """
        m = self.m
        count = len(self.layers)
        self.layer_flow: List[int] = []
        self.first_track: Dict[int, int] = {}
        usual_room = max(1, m.pad_flow + m.spacing_flow - 2 - m.arrow_lead)

        def needed(channel: int) -> int:
            plan = self.channels.get(channel)
            if plan is None or plan.levels == 0:
                return 0
            return (plan.levels - 1) * m.track_pitch + 1

        # Margin before the first layer.
        before = self._layer_before(0)
        if needed(-1):
            start = needed(-1) + before
            self.first_track[-1] = 0
        else:
            start = before - (1 + m.arrow_lead)
        self.layer_flow.append(start)

        for rank in range(count):
            flow = self.layer_flow[rank]
            low = flow + self._layer_after(rank)
            need = needed(rank)
            span = max(0, need - 1)
            if rank == count - 1:
                self.first_track[rank] = low
                break

            before = self._layer_before(rank + 1)
            following = low + max(usual_room, need) + before
            self.layer_flow.append(following)
            high = following - before - 1

            if self._layer_groups(rank) or self._layer_groups(rank + 1):
                first = low + (high - low - span) // 2
            else:
                body = max(
                    item.flow_size for item in self.layers[rank] if not item.is_lane
                )
                middle = (flow + body + m.pad_flow + following - 1) // 2
                first = middle - span // 2
            self.first_track[rank] = max(low, min(first, high - span))

    def _track_flow(self, channel: int, level: int) -> int:
        return self.first_track[channel] + level * self.m.track_pitch

    # ── step 11: wires ──────────────────────────────────────────────────

    def _cell(self, cross: int, flow: int) -> Cell:
        return (cross, flow) if self.m.tb else (flow, cross)

    def _direction(self, along_flow: bool, positive: bool) -> str:
        if self.m.tb:
            return (
                (DOWN if positive else UP)
                if along_flow
                else (RIGHT if positive else LEFT)
            )
        return (
            (RIGHT if positive else LEFT) if along_flow else (DOWN if positive else UP)
        )

    def _wire(self, net: int, start: Tuple[int, int], end: Tuple[int, int]) -> None:
        """Add a segment given as (cross, flow) pairs."""
        self.grid.add_segment(net, self._cell(*start), self._cell(*end))

    def _exit(self, net, border: Tuple[int, int], first: Tuple[int, int]) -> None:
        """Start a line at ``first``, reaching back into the box at ``border``."""
        border_cell, first_cell = self._cell(*border), self._cell(*first)
        dx, dy = border_cell[0] - first_cell[0], border_cell[1] - first_cell[1]
        toward = {(0, -1): UP, (0, 1): DOWN, (-1, 0): LEFT, (1, 0): RIGHT}[(dx, dy)]
        self.grid.add_arm(net, first_cell, toward)
        if toward == UP:
            self.marks[border_cell] = "┬"
        elif toward == DOWN:
            self.marks[border_cell] = "┴"

    def _assemble(self) -> RoutePlan:
        self.grid = WireGrid()
        self.marks: Dict[Cell, str] = {}

        self._wire_ports()
        self._wire_channels()
        self._wire_hooks()
        self._wire_lanes()
        self._wire_direct_links()
        return self._finish()

    def _port_cells(self, port: _Port):
        """(border cell, first cell outside the box) of a port, as (cross, flow)."""
        box = port.box
        flow = self.layer_flow[box.rank]
        if port.role == "entry":
            return (port.position, flow), (port.position, flow - 1)
        last = flow + box.flow_size - 1
        return (port.position, last), (port.position, last + 1)

    def _wire_ports(self) -> None:
        for port in self._all_ports():
            net = port.edges[0].net
            border, outside = self._port_cells(port)
            if port.role == "exit":
                self._exit(net, border, outside)
            else:
                forward = port.role == "entry"
                self.grid.add_arrow(
                    net, self._cell(*outside), self._direction(True, forward)
                )

    def _wire_channels(self) -> None:
        for channel, plan in self.channels.items():
            for track in plan.tracks:
                flow = self._track_flow(channel, track.level)
                self._wire(track.net, (track.low, flow), (track.high, flow))
            for jog in plan.jogs:
                self._wire(
                    jog.net,
                    (jog.position, self._track_flow(channel, jog.upper_level)),
                    (jog.position, self._track_flow(channel, jog.lower_level)),
                )
            for terminal, level in plan.terminal_level.items():
                flow = self._track_flow(channel, level)
                if isinstance(terminal, _Port):
                    _, outside = self._port_cells(terminal)
                    self._wire(terminal.edges[0].net, outside, (outside[0], flow))
                else:
                    terminal.points.append(flow)
            for upper, lower in plan.straight:
                self._wire_straight(channel, upper, lower)

    def _wire_straight(self, channel: int, upper, lower) -> None:
        """Two terminals facing each other: one straight line, no track."""
        upper_port, lower_port = isinstance(upper, _Port), isinstance(lower, _Port)
        if upper_port and lower_port:
            _, start = self._port_cells(upper)
            _, end = self._port_cells(lower)
            self._wire(upper.edges[0].net, start, end)
        elif upper_port:
            lower.points.append(self._port_cells(upper)[1][1])
        elif lower_port:
            upper.points.append(self._port_cells(lower)[1][1])
        else:
            meeting = self.layer_flow[channel] + self._layer_after(channel)
            upper.points.append(meeting)
            lower.points.append(meeting)

    def _wire_hooks(self) -> None:
        for box in self.boxes.values():
            flow = self.layer_flow[box.rank]
            for side in (BEFORE, AFTER):
                for hook in box.hooks[side]:
                    at = flow + hook.offset
                    net = hook.edge.net
                    border = (
                        box.cross if side == BEFORE else box.cross + box.cross_size - 1
                    )
                    outside = border + side
                    hook.lane.points.append(at)
                    self._wire(net, (outside, at), (hook.lane.cross, at))
                    if hook.role == "exit":
                        self._exit(net, (border, at), (outside, at))
                    else:
                        self.grid.add_arrow(
                            net,
                            self._cell(outside, at),
                            self._direction(False, side == BEFORE),
                        )

    def _wire_lanes(self) -> None:
        for lane in self.lanes:
            if len(lane.points) >= 2:
                self._wire(
                    lane.edge.net,
                    (lane.cross, min(lane.points)),
                    (lane.cross, max(lane.points)),
                )

    def _wire_direct_links(self) -> None:
        m = self.m
        for edge in self.edges:
            if edge.src_mode != "D":
                continue
            src, dst = edge.src, edge.dst
            shortest = min(src.flow_size, dst.flow_size)
            offset = (shortest - 1) // 2 if m.tb else shortest // 2
            at = self.layer_flow[src.rank] + offset
            if dst.order > src.order:
                border = src.cross + src.cross_size - 1
                start, end, positive = border + 1, dst.cross - 1, True
            else:
                border = src.cross
                start, end, positive = border - 1, dst.cross + dst.cross_size, False
            self._exit(edge.net, (border, at), (start, at))
            self._wire(edge.net, (start, at), (end, at))
            self.grid.add_arrow(
                edge.net, self._cell(end, at), self._direction(False, positive)
            )

    # ── step 12: canvas coordinates ─────────────────────────────────────

    def _finish(self) -> RoutePlan:
        m = self.m
        dimensions: Dict[str, BoxDimensions] = {}
        positions: Dict[str, Tuple[int, int]] = {}
        for box in self.boxes.values():
            width = box.cross_size if m.tb else box.flow_size
            height = box.flow_size if m.tb else box.cross_size
            dimensions[box.name] = self._resized(box.dims, width, height)
            positions[box.name] = self._cell(box.cross, self.layer_flow[box.rank])

        boundaries, title_x = self._group_boundaries()

        # Shift everything so the drawing starts at the canvas origin.
        min_x = min(x for x, _ in positions.values())
        min_y = min(y for _, y in positions.values())
        max_x = max(
            positions[n][0] + dimensions[n].width + m.shadow_size for n in positions
        )
        max_y = max(
            positions[n][1] + dimensions[n].height + m.shadow_size for n in positions
        )
        for boundary in boundaries:
            min_x, min_y = min(min_x, boundary.x), min(min_y, boundary.y)
            max_x = max(max_x, boundary.x + boundary.width + m.shadow_size)
            max_y = max(max_y, boundary.y + boundary.height + m.shadow_size)
        wire_bounds = self.grid.bounds()
        if wire_bounds:
            min_x, min_y = min(min_x, wire_bounds[0]), min(min_y, wire_bounds[1])
            max_x = max(max_x, wire_bounds[2] + 1)
            max_y = max(max_y, wire_bounds[3] + 1)

        dx, dy = -min_x, -min_y
        positions = {name: (x + dx, y + dy) for name, (x, y) in positions.items()}
        for boundary in boundaries:
            boundary.x += dx
            boundary.y += dy
            boundary.title_x += dx
            boundary.title_y += dy
        return RoutePlan(
            box_dimensions=dimensions,
            box_positions=positions,
            group_boundaries=boundaries,
            group_title_x={name: x + dx for name, x in title_x.items()},
            grid=self.grid.shifted(dx, dy),
            port_marks={(x + dx, y + dy): g for (x, y), g in self.marks.items()},
            width=max_x - min_x,
            height=max_y - min_y,
            layers=[
                [item.name for item in layer if not item.is_lane]
                for layer in self.layers
            ],
            tracks_per_channel=[plan.levels for plan in self.channels.values()],
        )

    @staticmethod
    def _resized(dims: BoxDimensions, width: int, height: int) -> BoxDimensions:
        """Box dimensions grown to ``width`` x ``height``, text kept centred."""
        lines = list(dims.text_lines)
        extra = height - dims.height
        if extra > 0:
            lines = [""] * (extra // 2) + lines
        return BoxDimensions(
            width=width, height=height, text_lines=lines, padding=dims.padding
        )

    def _group_cross_span(self, name: str) -> Tuple[int, int]:
        """Positions of a group's two borders that run along the flow."""
        m = self.m
        members = self._group_members(name)
        first, last = members[0], members[-1]
        low = first.cross - GROUP_PADDING
        high = last.cross + last.cross_size + m.pad_cross + 2
        if m.tb:
            before, after = self.title_reserve[name]
            return low - before, high + after
        return low, high

    def _group_title_start(self, name: str) -> Optional[int]:
        """
        Column where a TB group's title can start, or None if nothing fits.

        The title avoids the columns (and their neighbours) where lines
        enter the group's boxes from above.
        """
        left, right = self._group_cross_span(name)
        blocked = {
            port.position + offset
            for box in self._group_members(name)
            for port in box.in_ports
            for offset in (-1, 0, 1)
        }
        return self._title_slot(left, right, len(name), blocked)

    def _group_boundaries(self):
        """Dashed boxes around the members of each group, with title columns."""
        m = self.m
        boundaries: List[GroupBoundary] = []
        title_x: Dict[str, int] = {}
        for group in self.groups:
            if not self._has(group):
                continue
            members = self._group_members(group.name)
            flow = self.layer_flow[members[0].rank]
            before, _ = self.title_reserve[group.name]
            title = len(group.name)

            cross_low, cross_high = self._group_cross_span(group.name)
            flow_low = flow - GROUP_PADDING
            flow_high = flow + self._group_border_after(group.name)
            if m.tb:
                x, right = cross_low, cross_high
                y, bottom = flow_low - GROUP_TITLE_ROWS, flow_high
                slot = self._group_title_start(group.name)
            else:
                x, right = flow_low - before, flow_high
                y, bottom = cross_low - GROUP_TITLE_ROWS, cross_high
                slot = None
            width, height = right - x + 1, bottom - y + 1
            if slot is None:
                slot = x + (width - title) // 2

            title_x[group.name] = slot
            boundaries.append(
                GroupBoundary(
                    name=group.name,
                    members=[box.name for box in members],
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    title_x=slot,
                    title_y=y,
                    title_width=title,
                )
            )
        return boundaries, title_x
