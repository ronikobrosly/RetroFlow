"""
Channel router: gives every line crossing a gap its own track.

A *channel* is the empty band between two neighbouring layers of boxes. Lines
enter it from the upstream side (out of the boxes above) and from the
downstream side (into the boxes below):

        upstream terminals     ┬      ┬   ┬
                               │      │   │
        track 0                └──────┼─┐ │        each piece owns one track
        track 1                ┌──────┘ │ │        (a row in TB, a column in LR)
                               │        │ │
        downstream terminals   ▼        ▼ ▼

Everything here is plain data in *channel coordinates*: positions run along
the channel, tracks are counted from the upstream side. The planner turns
tracks into rows or columns afterwards, so the same code serves top-to-bottom
and left-to-right diagrams.

Rules enforced
--------------
* Two pieces whose spans overlap never share a track.
* When a stub coming down from the upstream side sits in (or right next to)
  the column of another piece's stub going down to the downstream side, the
  first piece's track must be the higher one. Otherwise the stubs would run
  on top of each other.
* When those ordering rules contradict each other (the classic case is two
  edges swapping columns), one piece is split in two halves joined by a
  short *jog* in a free column, which always removes the contradiction.
* Among the orders that remain legal, the one with fewer crossings wins.
"""

from dataclasses import dataclass, field
from typing import Dict, Hashable, Iterable, List, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class Terminal:
    """A point where a line enters the channel."""

    key: Hashable
    position: int
    upstream: bool


@dataclass(frozen=True)
class Link:
    """Two terminals of one net that must be connected inside the channel."""

    net: int
    first: Terminal
    second: Terminal


@dataclass(frozen=True)
class Track:
    """A run along the channel on one track, from ``low`` to ``high``."""

    net: int
    level: int
    low: int
    high: int


@dataclass(frozen=True)
class Jog:
    """A short run across the channel joining the two halves of a split piece."""

    net: int
    position: int
    upper_level: int
    lower_level: int


@dataclass
class ChannelPlan:
    """
    The routed channel.

    Attributes:
        levels: Number of tracks the channel needs.
        tracks: Every run along the channel.
        jogs: Runs across the channel that join split pieces.
        terminal_level: Track each terminal's stub ends on. Terminals that are
            connected straight across the channel are absent.
        straight: Pairs of (upstream key, downstream key) connected by a
            straight line with no track at all.
    """

    levels: int = 0
    tracks: List[Track] = field(default_factory=list)
    jogs: List[Jog] = field(default_factory=list)
    terminal_level: Dict[Hashable, int] = field(default_factory=dict)
    straight: List[Tuple[Hashable, Hashable]] = field(default_factory=list)


@dataclass
class _Piece:
    """One connected thing to route: a set of terminals of one net."""

    ident: int
    net: int
    ups: List[Terminal]
    downs: List[Terminal]
    jog_from_above: Optional[int] = None  # lower half of a split piece
    jog_to_below: Optional[int] = None  # upper half of a split piece
    lower_half: Optional[int] = None  # identity of the half the jog leads to
    level: int = 0

    def positions(self) -> List[int]:
        found = [t.position for t in self.ups + self.downs]
        for jog in (self.jog_from_above, self.jog_to_below):
            if jog is not None:
                found.append(jog)
        return found

    @property
    def low(self) -> int:
        return min(self.positions())

    @property
    def high(self) -> int:
        return max(self.positions())

    def reaching_up(self) -> List[int]:
        """Positions where this piece has a stroke above its track."""
        found = [t.position for t in self.ups]
        if self.jog_from_above is not None:
            found.append(self.jog_from_above)
        return found

    def reaching_down(self) -> List[int]:
        """Positions where this piece has a stroke below its track."""
        found = [t.position for t in self.downs]
        if self.jog_to_below is not None:
            found.append(self.jog_to_below)
        return found


def route_channel(links: Iterable[Link], stroke_gap: int = 1) -> ChannelPlan:
    """
    Assign a track to every connection in one channel.

    Args:
        links: Connections to make. Links of one net that share a terminal
            are merged into a single piece with one shared track.
        stroke_gap: How close two unrelated stubs may be before they count as
            running into each other. 1 when stubs are vertical strokes (they
            must not sit in touching columns), 0 when they are horizontal.

    Returns:
        A ``ChannelPlan``.
    """
    plan = ChannelPlan()
    pieces = _build_pieces(links, plan)
    if not pieces:
        return plan

    pieces = _break_ordering_cycles(pieces, stroke_gap, _occupied_positions(links))
    above = _hard_constraints(pieces, stroke_gap)
    _add_crossing_preferences(pieces, above)
    _assign_levels(pieces, above)

    for piece in pieces:
        for terminal in piece.ups + piece.downs:
            plan.terminal_level[terminal.key] = piece.level
        if piece.low < piece.high:
            plan.tracks.append(Track(piece.net, piece.level, piece.low, piece.high))
    plan.levels = 1 + max(piece.level for piece in pieces)

    by_ident = {piece.ident: piece for piece in pieces}
    for piece in pieces:
        if piece.lower_half is not None:
            lower = by_ident[piece.lower_half]
            plan.jogs.append(
                Jog(piece.net, piece.jog_to_below, piece.level, lower.level)
            )
    return plan


# ── step 1: pieces ──────────────────────────────────────────────────────


def _build_pieces(links: Iterable[Link], plan: ChannelPlan) -> List[_Piece]:
    """Merge links that share a terminal; set straight connections aside."""
    parent: Dict[Hashable, Hashable] = {}
    terminals: Dict[Hashable, Terminal] = {}
    nets: Dict[Hashable, int] = {}

    def find(key: Hashable) -> Hashable:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    ordered_links = list(links)
    for link in ordered_links:
        for terminal in (link.first, link.second):
            parent.setdefault(terminal.key, terminal.key)
            terminals[terminal.key] = terminal
            nets.setdefault(terminal.key, link.net)
        parent[find(link.first.key)] = find(link.second.key)

    members: Dict[Hashable, List[Terminal]] = {}
    for key, terminal in terminals.items():
        members.setdefault(find(key), []).append(terminal)

    pieces: List[_Piece] = []
    for root, group in members.items():
        ups = sorted((t for t in group if t.upstream), key=lambda t: t.position)
        downs = sorted((t for t in group if not t.upstream), key=lambda t: t.position)
        if len(ups) == 1 and len(downs) == 1 and ups[0].position == downs[0].position:
            plan.straight.append((ups[0].key, downs[0].key))
            continue
        # Identities are spaced out so the halves of a split piece can take
        # the numbers right after it and keep the ordering deterministic.
        ident = 4 * (len(pieces) + len(plan.straight))
        pieces.extend(_without_four_way_junction(_Piece(ident, nets[root], ups, downs)))
    return pieces


def _without_four_way_junction(piece: _Piece) -> List[_Piece]:
    """
    Split a piece that would otherwise draw an ambiguous ``┼``.

    When a stub from upstream and a stub to downstream of the same piece face
    each other and the track continues on both sides, the meeting point has
    four arms and reads exactly like two unrelated lines crossing:

        │                      │
      ──┼──      becomes     ──┤        two tees, which can only be
        │                      ├──      read one way
                               │

    The left part keeps the upstream stub, the right part the downstream
    stub, and the two are joined by a jog in their shared column.
    """
    up_positions = {terminal.position for terminal in piece.ups}
    shared = sorted(
        terminal.position
        for terminal in piece.downs
        if terminal.position in up_positions
        and piece.low < terminal.position < piece.high
    )
    if not shared:
        return [piece]

    pivot = shared[0]
    upper = _Piece(
        piece.ident,
        piece.net,
        [t for t in piece.ups if t.position <= pivot],
        [t for t in piece.downs if t.position < pivot],
        jog_to_below=pivot,
        lower_half=piece.ident + 1,
    )
    lower = _Piece(
        piece.ident + 1,
        piece.net,
        [t for t in piece.ups if t.position > pivot],
        [t for t in piece.downs if t.position >= pivot],
        jog_from_above=pivot,
    )
    return [upper, lower]


def _occupied_positions(links: Iterable[Link]) -> Set[int]:
    return {t.position for link in links for t in (link.first, link.second)}


# ── step 2: ordering rules that must hold ───────────────────────────────


def _hard_constraints(pieces: Sequence[_Piece], stroke_gap: int) -> Dict[int, Set[int]]:
    """
    Map each piece to the pieces whose track must lie below its own.

    A stub from the upstream side stops at its piece's track; a stub to the
    downstream side starts at its piece's track. When the two are in the same
    or touching positions, the first piece has to be the upper one.
    """
    above: Dict[int, Set[int]] = {piece.ident: set() for piece in pieces}
    going_down: Dict[int, List[int]] = {}
    for piece in pieces:
        for terminal in piece.downs:
            going_down.setdefault(terminal.position, []).append(piece.ident)

    for piece in pieces:
        for terminal in piece.ups:
            for offset in range(-stroke_gap, stroke_gap + 1):
                for other in going_down.get(terminal.position + offset, ()):
                    if other != piece.ident:
                        above[piece.ident].add(other)

    for piece in pieces:
        if piece.lower_half is not None:
            above[piece.ident].add(piece.lower_half)
    return above


def _find_cycle(above: Dict[int, Set[int]]) -> Optional[List[int]]:
    """Return the identities on one ordering cycle, or None if there is none."""
    state: Dict[int, int] = {}  # 1 = on the current path, 2 = finished
    path: List[int] = []

    def visit(node: int) -> Optional[List[int]]:
        state[node] = 1
        path.append(node)
        for successor in sorted(above[node]):
            if state.get(successor) == 1:
                return path[path.index(successor) :]
            if successor not in state:
                found = visit(successor)
                if found:
                    return found
        path.pop()
        state[node] = 2
        return None

    for node in sorted(above):
        if node not in state:
            found = visit(node)
            if found:
                return found
    return None


def _break_ordering_cycles(
    pieces: List[_Piece], stroke_gap: int, occupied: Set[int]
) -> List[_Piece]:
    """
    Split pieces until the ordering rules no longer contradict each other.

    A split piece becomes an upper half (its upstream stubs plus a jog down)
    and a lower half (the jog plus its downstream stubs). The upper half is
    only ever required to be *above* other pieces and the lower half only
    *below*, so neither can take part in a cycle again.
    """
    occupied = set(occupied)
    while True:
        cycle = _find_cycle(_hard_constraints(pieces, stroke_gap))
        if cycle is None:
            return pieces

        by_ident = {piece.ident: piece for piece in pieces}
        victim = min(
            (
                by_ident[ident]
                for ident in cycle
                if by_ident[ident].jog_to_below is None
                and by_ident[ident].jog_from_above is None
            ),
            key=lambda piece: (len(piece.ups) + len(piece.downs), piece.ident),
        )
        jog = _free_position(victim, occupied, stroke_gap)
        occupied.add(jog)

        upper = _Piece(
            victim.ident,
            victim.net,
            victim.ups,
            [],
            jog_to_below=jog,
            lower_half=victim.ident + 2,
        )
        lower = _Piece(
            victim.ident + 2, victim.net, [], victim.downs, jog_from_above=jog
        )
        index = pieces.index(victim)
        pieces = pieces[:index] + [upper, lower] + pieces[index + 1 :]


def _free_position(piece: _Piece, occupied: Set[int], stroke_gap: int) -> int:
    """The position nearest the middle of ``piece`` with room for a jog."""
    middle = (piece.low + piece.high) // 2
    clearance = stroke_gap + 1 if stroke_gap else 0
    distance = 0
    while True:
        for candidate in (middle + distance, middle - distance):
            nearby = range(candidate - clearance, candidate + clearance + 1)
            if not any(position in occupied for position in nearby):
                return candidate
        distance += 1


# ── step 3: prefer the order with fewer crossings ───────────────────────


def _spans_overlap(first: _Piece, second: _Piece) -> bool:
    """True when the two pieces cannot share a track (one blank cell apart)."""
    return first.low <= second.high + 1 and second.low <= first.high + 1


def _crossings_if_above(upper: _Piece, lower: _Piece) -> int:
    """Crossings between two pieces when ``upper`` gets the higher track."""
    through_upper = sum(
        1 for position in lower.reaching_up() if upper.low < position < upper.high
    )
    through_lower = sum(
        1 for position in upper.reaching_down() if lower.low < position < lower.high
    )
    return through_upper + through_lower


def _add_crossing_preferences(
    pieces: Sequence[_Piece], above: Dict[int, Set[int]]
) -> None:
    """
    Order every pair of overlapping pieces, keeping ``above`` free of cycles.

    Pairs are settled strongest preference first, so a pair that barely
    cares gives way to one where the wrong order costs several crossings.
    """
    below_all = _transitive_closure(above)

    candidates = []
    for i, first in enumerate(pieces):
        for second in pieces[i + 1 :]:
            if not _spans_overlap(first, second):
                continue
            first_above = _crossings_if_above(first, second)
            second_above = _crossings_if_above(second, first)
            if second_above < first_above:
                upper, lower = second, first
            elif first_above < second_above:
                upper, lower = first, second
            else:
                upper, lower = sorted(
                    (first, second), key=lambda p: (p.low, p.high, p.ident)
                )
            weight = abs(first_above - second_above)
            candidates.append((-weight, upper.ident, lower.ident))

    for _, upper, lower in sorted(candidates):
        if lower in below_all[upper] or upper in below_all[lower]:
            continue  # already ordered, directly or through other pieces
        above[upper].add(lower)
        gained = below_all[lower] | {lower}
        for ident, reachable in below_all.items():
            if ident == upper or upper in reachable:
                reachable |= gained


def _transitive_closure(above: Dict[int, Set[int]]) -> Dict[int, Set[int]]:
    closure: Dict[int, Set[int]] = {}

    def reach(node: int) -> Set[int]:
        if node not in closure:
            closure[node] = set()
            for successor in above[node]:
                closure[node] |= {successor} | reach(successor)
        return closure[node]

    for node in above:
        reach(node)
    return closure


# ── step 4: tracks ──────────────────────────────────────────────────────


def _assign_levels(pieces: Sequence[_Piece], above: Dict[int, Set[int]]) -> None:
    """Give each piece the highest track its ordering rules allow."""
    by_ident = {piece.ident: piece for piece in pieces}
    waiting = {ident: 0 for ident in above}
    for lowers in above.values():
        for lower in lowers:
            waiting[lower] += 1

    ready = sorted(ident for ident, count in waiting.items() if count == 0)
    while ready:
        ident = ready.pop(0)
        for lower in sorted(above[ident]):
            by_ident[lower].level = max(
                by_ident[lower].level, by_ident[ident].level + 1
            )
            waiting[lower] -= 1
            if waiting[lower] == 0:
                ready.append(lower)
        ready.sort()
