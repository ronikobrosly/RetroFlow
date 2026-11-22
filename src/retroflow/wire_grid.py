"""
Wire grid: the single place where edge glyphs are decided.

    route segments ──► arms per cell ──► one glyph per cell

        ─ + │ in one cell           two nets crossing     ┼
        ─ then │ of the same net    a bend                ┐ └ ┘ ┌
        three arms of one net       a junction            ├ ┤ ┬ ┴

The old edge drawer looked at the character already on the canvas and guessed
what to write next, which is how unrelated lines ended up fused together. The
wire grid never guesses. Every cell remembers which *net* (a set of edges that
are allowed to share a line) reaches out of it in which directions, and the
glyph is looked up from those arms once all routes have been added.

Two different nets may share a cell only when they cross at right angles.
Anything else is recorded in ``conflicts`` instead of being drawn as a
misleading junction, so a routing bug can never silently change the graph the
picture shows.

The grid works in canvas coordinates (x grows right, y grows down).
"""

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterator, List, Optional, Set, Tuple

Cell = Tuple[int, int]

UP, DOWN, LEFT, RIGHT = "U", "D", "L", "R"

DELTA: Dict[str, Cell] = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}
OPPOSITE: Dict[str, str] = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}

# Glyph for every combination of two or more arms.
ARM_GLYPHS: Dict[FrozenSet[str], str] = {
    frozenset("LR"): "─",
    frozenset("UD"): "│",
    frozenset("DR"): "┌",
    frozenset("DL"): "┐",
    frozenset("UR"): "└",
    frozenset("UL"): "┘",
    frozenset("UDR"): "├",
    frozenset("UDL"): "┤",
    frozenset("DLR"): "┬",
    frozenset("ULR"): "┴",
    frozenset("UDLR"): "┼",
}

# A cell with a single arm is the loose end of a line. It is drawn as a short
# stroke so the mistake stays visible, and it is reported as a conflict.
STUB_GLYPHS: Dict[str, str] = {UP: "│", DOWN: "│", LEFT: "─", RIGHT: "─"}

ARROW_GLYPHS: Dict[str, str] = {DOWN: "▼", UP: "▲", RIGHT: "►", LEFT: "◄"}

HORIZONTAL = frozenset("LR")
VERTICAL = frozenset("UD")


@dataclass(frozen=True)
class WireConflict:
    """Something the grid was asked to draw that would misrepresent the graph."""

    cell: Cell
    reason: str

    def __str__(self) -> str:
        return f"({self.cell[0]}, {self.cell[1]}): {self.reason}"


class WireGrid:
    """
    Collects route segments and turns them into line-drawing glyphs.

    Example:
        >>> grid = WireGrid()
        >>> grid.add_segment(net=1, start=(0, 0), end=(3, 0))
        >>> grid.add_segment(net=1, start=(3, 0), end=(3, 2))
        >>> grid.glyph_at((3, 0))
        '┐'
    """

    def __init__(self) -> None:
        self._arms: Dict[Cell, Dict[int, Set[str]]] = {}
        self._arrows: Dict[Cell, Tuple[int, str]] = {}

    # ── building ────────────────────────────────────────────────────────

    def add_arm(self, net: int, cell: Cell, direction: str) -> None:
        """
        Make ``cell`` reach toward ``direction`` on behalf of ``net``.

        Used on its own for the first cell of a line, which must reach back
        into the box border it leaves from.
        """
        self._arms.setdefault(cell, {}).setdefault(net, set()).add(direction)

    def add_segment(self, net: int, start: Cell, end: Cell) -> None:
        """
        Add a straight run of wire from ``start`` to ``end`` (both included).

        Every pair of neighbouring cells on the run reaches toward each other.
        The two end cells only reach inward, so runs are chained by sharing an
        end cell: a horizontal run ending where a vertical run starts yields a
        corner, a run ending in the middle of another yields a junction.

        Args:
            net: Identity of the line. Segments of one net merge freely.
            start: First cell of the run.
            end: Last cell of the run; must share a row or column with start.

        Raises:
            ValueError: If the run is not axis-aligned.
        """
        (x0, y0), (x1, y1) = start, end
        if x0 != x1 and y0 != y1:
            raise ValueError(f"segment {start} -> {end} is not axis-aligned")
        if start == end:
            return

        if y0 == y1:
            forward, step = (RIGHT, 1) if x1 > x0 else (LEFT, -1)
            cells = [(x, y0) for x in range(x0, x1 + step, step)]
        else:
            forward, step = (DOWN, 1) if y1 > y0 else (UP, -1)
            cells = [(x0, y) for y in range(y0, y1 + step, step)]

        backward = OPPOSITE[forward]
        for here, there in zip(cells, cells[1:]):
            self.add_arm(net, here, forward)
            self.add_arm(net, there, backward)

    def add_arrow(self, net: int, cell: Cell, direction: str) -> None:
        """
        Turn ``cell`` into an arrowhead pointing toward ``direction``.

        The cell must be the last cell of a segment arriving from behind the
        head, i.e. its only arm points away from ``direction``.
        """
        self._arrows[cell] = (net, direction)

    # ── reading ─────────────────────────────────────────────────────────

    def arms_at(self, cell: Cell) -> Dict[int, FrozenSet[str]]:
        """Arms of every net present in ``cell`` (empty if the cell is free)."""
        return {net: frozenset(arms) for net, arms in self._arms.get(cell, {}).items()}

    def glyph_at(self, cell: Cell) -> Optional[str]:
        """The glyph to draw in ``cell``, or None if no wire touches it."""
        glyph, _ = self._resolve(cell)
        return glyph

    def cells(self) -> Iterator[Tuple[Cell, str]]:
        """Every wire cell with its glyph, in reading order."""
        for cell in sorted(set(self._arms) | set(self._arrows), key=_reading_order):
            glyph, _ = self._resolve(cell)
            if glyph is not None:
                yield cell, glyph

    @property
    def conflicts(self) -> List[WireConflict]:
        """Everything in the grid that cannot be drawn truthfully."""
        found = []
        for cell in sorted(set(self._arms) | set(self._arrows), key=_reading_order):
            _, reason = self._resolve(cell)
            if reason:
                found.append(WireConflict(cell, reason))
        return found

    def crossing_count(self) -> int:
        """Number of cells where two different nets cross."""
        return sum(1 for nets in self._arms.values() if len(nets) == 2)

    def bounds(self) -> Optional[Tuple[int, int, int, int]]:
        """(min_x, min_y, max_x, max_y) over all wire cells, or None if empty."""
        occupied = set(self._arms) | set(self._arrows)
        if not occupied:
            return None
        xs = [x for x, _ in occupied]
        ys = [y for _, y in occupied]
        return min(xs), min(ys), max(xs), max(ys)

    def shifted(self, dx: int, dy: int) -> "WireGrid":
        """A copy of this grid moved by (dx, dy)."""
        moved = WireGrid()
        for (x, y), nets in self._arms.items():
            moved._arms[(x + dx, y + dy)] = {
                net: set(arms) for net, arms in nets.items()
            }
        for (x, y), arrow in self._arrows.items():
            moved._arrows[(x + dx, y + dy)] = arrow
        return moved

    # ── glyph rules ─────────────────────────────────────────────────────

    def _resolve(self, cell: Cell) -> Tuple[Optional[str], str]:
        """Return (glyph, conflict reason); the reason is "" when all is well."""
        nets = self._arms.get(cell, {})
        arrow = self._arrows.get(cell)

        if arrow is not None:
            return self._resolve_arrow(nets, arrow)
        if not nets:
            return None, ""
        if len(nets) == 1:
            (arms,) = nets.values()
            if len(arms) == 1:
                (only,) = arms
                return STUB_GLYPHS[only], "line ends without reaching anything"
            return ARM_GLYPHS[frozenset(arms)], ""
        if len(nets) == 2:
            first, second = (frozenset(arms) for arms in nets.values())
            if {first, second} == {HORIZONTAL, VERTICAL}:
                return "┼", ""
            return "┼", "two different lines share a cell without crossing cleanly"
        return "┼", "more than two lines share a cell"

    @staticmethod
    def _resolve_arrow(
        nets: Dict[int, Set[str]], arrow: Tuple[int, str]
    ) -> Tuple[Optional[str], str]:
        net, direction = arrow
        glyph = ARROW_GLYPHS[direction]
        if set(nets) != {net}:
            return glyph, "an arrowhead shares its cell with another line"
        if nets[net] != {OPPOSITE[direction]}:
            return glyph, "an arrowhead is not fed from directly behind"
        return glyph, ""


def _reading_order(cell: Cell) -> Tuple[int, int]:
    return (cell[1], cell[0])
