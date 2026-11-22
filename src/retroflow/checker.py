"""
Diagram checker: decides whether a rendered flowchart is *clean*.

    boxes-only canvas (base) ──┐
                               ├──► edge layer (lines + arrows)
    finished canvas   (final) ─┘              │
                 ┌───────────────┬────────────┼─────────────────┐
                 ▼               ▼            ▼                 ▼
           boxes intact?   glyphs connect?   arrows attached?   edges == input?

The checker never looks at how a renderer made its decisions. It only reads
the picture, the way a person would, and compares what the picture *says*
with what the input asked for. That keeps it valid across any rewrite of the
layout or routing code, and lets ``FlowchartGenerator`` use it as a gate:
a rendering is only returned when it reads back as the graph that was typed.

How a picture is read
---------------------
* Every line glyph has "arms" (``┌`` reaches down and right, ``┬`` reaches
  left, right and down, ...). Two neighbouring cells are connected only when
  both reach toward each other.
* A line cell reaching into the side of a node box is an *exit* from that box.
* An arrowhead touching a node box is an *entry* into that box.
* Cells joined by arms form one line. Each line connects every box it exits
  to every box it enters, so a line read from the picture yields a set of
  ``(source, target)`` edges.
* ``┼`` means two lines crossing. It is only read as a four-way junction when
  one of the two lines would otherwise come from nowhere or lead nowhere
  (this is how a three-way LR fan-out is drawn).

Errors (the picture is wrong)
-----------------------------
``box_missing``            a node's box could not be found
``box_damaged``            edge drawing changed a box, title or group label
``group_border_damaged``   a line runs along / corrupts a dashed group border
``dangling_line``          a line arm reaches toward nothing
``dangling_port``          a port mark on a box has no line attached
``floating_arrow``         an arrowhead does not touch a node box
``arrow_no_tail``          nothing leads into the back of an arrowhead
``arrow_hit_sideways``     a line runs into the side or tip of an arrowhead
``missing_edge``           an input edge cannot be traced in the picture
``phantom_edge``           the picture shows an edge that is not in the input
``stray_line``             a line with no source box or no target box
``group_missing``          a group's dashed box or title cannot be found, or
                           does not enclose the group's members
``group_overlap``          a group box overlaps another group box, or frames
                           a node box that is not one of its members
``debug_mismatch``         debug and non-debug renders differ

Warnings (the picture is right but hard to read)
------------------------------------------------
``adjacent_lines``         two unconnected vertical strokes in touching columns
``group_crowded``          something sits too close to a group box (see below)
``group_crossing``         a line crosses a group border without needing to

Group boxes
-----------
A group is a dashed box with its title on the row above. The only thing that
may touch its border is a line crossing it at a right angle, and only where
the border is straight:

         Title            a member keeps 2 cells from the border,
    ┏╍╍╍╍╍╍╍╍╍╍╍╍╍┓       a line running along the border keeps 1 blank
    ╏             ╏░      cell from it and from its shadow,
    ╏  ┌─────┐    ╏░      an arrowhead never touches the border,
    ╏  │  A  │──────►     boxes and groups outside keep 1 blank cell, and
    ╏  └─────┘░   ╏░      nothing but blank space touches the title.
    ┗╍╍╍╍╍╍╍╍╍╍╍╍╍┛░
     ░░░░░░░░░░░░░░░

A line also crosses a group border only when it has to: an edge between two
members stays inside the box, and an edge between two outsiders stays out.
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .models import GroupDefinition
from .parser import Parser

Cell = Tuple[int, int]
Edge = Tuple[str, str]
Rect = Tuple[int, int, int, int]  # left, top, right, bottom (all inclusive)

# Arms of every line glyph the edge renderer may produce.
LINE_ARMS: Dict[str, str] = {
    "─": "LR",
    "│": "UD",
    "┌": "DR",
    "┐": "DL",
    "└": "UR",
    "┘": "UL",
    "├": "UDR",
    "┤": "UDL",
    "┬": "DLR",
    "┴": "ULR",
    "┼": "UDLR",
}

# Arrowhead glyph -> direction the head points.
ARROW_HEADS: Dict[str, str] = {"▼": "D", "▲": "U", "►": "R", "◄": "L"}

DELTA: Dict[str, Cell] = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
OPPOSITE: Dict[str, str] = {"U": "D", "D": "U", "L": "R", "R": "L"}

SHADOW = "░"
DASHED_VERTICAL = "╏"
DASHED_HORIZONTAL = "╍"
GROUP_CORNERS = "┏┓┗┛"  # top-left, top-right, bottom-left, bottom-right

# Which way a line must travel to enter each side of a box, and the glyph a
# port mark on that side is allowed to use (a tee whose stem points outward).
SIDE_ENTRY_DIRECTION = {"top": "D", "bottom": "U", "left": "R", "right": "L"}
SIDE_PORT_GLYPH = {"top": "┴", "bottom": "┬", "left": "┤", "right": "├"}
SIDE_OUTWARD = {"top": "U", "bottom": "D", "left": "L", "right": "R"}

ERROR_CODES = (
    "box_missing",
    "box_damaged",
    "group_border_damaged",
    "dangling_line",
    "dangling_port",
    "floating_arrow",
    "arrow_no_tail",
    "arrow_hit_sideways",
    "missing_edge",
    "phantom_edge",
    "stray_line",
    "group_missing",
    "group_overlap",
    "debug_mismatch",
)
WARNING_CODES = ("adjacent_lines", "group_crowded", "group_crossing")

# Cells a group member keeps between its own border and the group's border.
GROUP_MEMBER_CLEARANCE = 2
# Blank cells between a group box (shadow and title included) and anything
# outside it, and between a group border and a line running along it.
GROUP_CLEARANCE = 1


@dataclass(frozen=True)
class Issue:
    """One thing wrong with a rendered diagram."""

    code: str
    message: str
    x: int = -1
    y: int = -1

    def __str__(self) -> str:
        where = f" at (x={self.x}, y={self.y})" if self.x >= 0 else ""
        return f"[{self.code}]{where} {self.message}"


@dataclass(frozen=True)
class Box:
    """A node box found in the boxes-only canvas."""

    name: str
    x: int
    y: int
    width: int
    height: int

    def side_of(self, cx: int, cy: int) -> Optional[str]:
        """Which part of the border a cell is on (None if not on the border)."""
        right = self.x + self.width - 1
        bottom = self.y + self.height - 1
        if not (self.x <= cx <= right and self.y <= cy <= bottom):
            return None
        on_x_edge = cx in (self.x, right)
        on_y_edge = cy in (self.y, bottom)
        if on_x_edge and on_y_edge:
            return "corner"
        if cy == self.y:
            return "top"
        if cy == bottom:
            return "bottom"
        if cx == self.x:
            return "left"
        if cx == right:
            return "right"
        return "interior"


@dataclass(frozen=True)
class GroupBox:
    """A dashed group box found in the boxes-only canvas (title row excluded)."""

    x: int
    y: int
    width: int
    height: int
    shadow: bool = False
    name: str = ""  # filled in once the box is matched to a group

    @property
    def right(self) -> int:
        return self.x + self.width - 1

    @property
    def bottom(self) -> int:
        return self.y + self.height - 1

    def footprint(self) -> Tuple[int, int, int, int]:
        """(left, top, right, bottom) of the box and its shadow."""
        extra = 1 if self.shadow else 0
        return (self.x, self.y, self.right + extra, self.bottom + extra)

    def encloses(self, box: Box) -> bool:
        """Is a node box strictly inside the dashed border?"""
        return (
            self.x < box.x
            and box.x + box.width - 1 < self.right
            and self.y < box.y
            and box.y + box.height - 1 < self.bottom
        )

    def border_cells(self) -> Dict[Cell, str]:
        """Every border cell and the side it is on (corners: 'corner')."""
        cells: Dict[Cell, str] = {}
        for cx in range(self.x, self.right + 1):
            cells[(cx, self.y)] = "top"
            cells[(cx, self.bottom)] = "bottom"
        for cy in range(self.y, self.bottom + 1):
            cells[(self.x, cy)] = "left"
            cells[(self.right, cy)] = "right"
        for corner in (
            (self.x, self.y),
            (self.right, self.y),
            (self.x, self.bottom),
            (self.right, self.bottom),
        ):
            cells[corner] = "corner"
        return cells


@dataclass
class DiagramReport:
    """Everything the checker learned about one rendered diagram."""

    output: str
    expected_edges: Set[Edge]
    drawn_edges: Set[Edge] = field(default_factory=set)
    boxes: Dict[str, Box] = field(default_factory=dict)
    group_boxes: List[GroupBox] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    crossings: int = 0
    junctions: int = 0
    label: str = ""

    @property
    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.code in ERROR_CODES]

    @property
    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.code in WARNING_CODES]

    def of(self, *codes: str) -> List[Issue]:
        """Issues with any of the given codes."""
        return [i for i in self.issues if i.code in codes]

    def counts(self) -> Counter:
        return Counter(i.code for i in self.issues)

    def explain(self, *codes: str, limit: int = 12) -> str:
        """Readable failure text: the selected issues, then the diagram."""
        selected = self.of(*codes) if codes else self.issues
        lines = [f"{len(selected)} issue(s) in {self.label or 'diagram'}:"]
        lines += [f"  {issue}" for issue in selected[:limit]]
        if len(selected) > limit:
            lines.append(f"  ... and {len(selected) - limit} more")
        lines.append("")
        for row_idx, row in enumerate(self.output.split("\n")):
            lines.append(f"{row_idx:3d} {row}")
        return "\n".join(lines)


def normalize_name(name: str) -> str:
    """Node names are word-wrapped inside boxes, so compare on single spaces."""
    return " ".join(name.split())


def expected_edges_of(input_text: str) -> Set[Edge]:
    """The set of (source, target) edges the input text asks for."""
    connections = Parser().parse_with_groups(input_text).connections
    return {(normalize_name(s), normalize_name(t)) for s, t in connections}


def expected_groups_of(input_text: str) -> List[GroupDefinition]:
    """The groups the input text asks for."""
    return Parser().parse_with_groups(input_text).groups


def analyze_rendering(
    base_lines: Iterable[str],
    output: str,
    expected_edges: Set[Edge],
    groups: Optional[Sequence[GroupDefinition]] = None,
) -> DiagramReport:
    """
    Check a finished rendering against its boxes-only canvas.

    Args:
        base_lines: Canvas rows after boxes (and groups/title) were drawn,
            before any edge was drawn.
        output: The finished diagram text.
        expected_edges: Edges the diagram is supposed to show.
        groups: Groups the diagram is supposed to show. When given, every
            group must be drawn around exactly its members, under its title.
            Dashed boxes found in the picture are checked for crowding
            either way.

    Returns:
        A ``DiagramReport``.
    """
    return _Analysis(list(base_lines), output, set(expected_edges), groups).run()


class _Analysis:
    """Single-use worker behind ``analyze_rendering``."""

    def __init__(
        self,
        base_lines: List[str],
        output: str,
        expected: Set[Edge],
        groups: Optional[Sequence[GroupDefinition]] = None,
    ):
        self.groups = groups
        final_lines = output.split("\n")
        self.height = max(len(base_lines), len(final_lines))
        self.width = max((len(row) for row in base_lines + final_lines), default=0)
        self.base = self._pad(base_lines)
        self.final = self._pad(final_lines)
        self.report = DiagramReport(output=output, expected_edges=expected)

        # Filled in by the steps below.
        self.border: Dict[Cell, Tuple[str, str]] = {}  # cell -> (node, side)
        self.owner: Dict[Cell, str] = {}  # every cell of a node box -> node
        self.protected: Set[Cell] = set()
        self.arms: Dict[Cell, str] = {}  # line cells of the edge layer
        self.arrows: Dict[Cell, str] = {}  # arrow cells -> head direction
        self.ports: Dict[Cell, Tuple[str, str]] = {}  # port marks on borders
        self.parent: Dict[Tuple[Cell, str], Tuple[Cell, str]] = {}
        self.exits: List[Tuple[Tuple[Cell, str], str]] = []  # (line key, node)
        self.entries: List[Tuple[Tuple[Cell, str], str]] = []
        self.titles: Dict[int, Rect] = {}  # index in report.group_boxes -> title

    # ── grid helpers ────────────────────────────────────────────────────

    def _pad(self, lines: List[str]) -> List[str]:
        rows = [row.ljust(self.width) for row in lines]
        rows += [" " * self.width] * (self.height - len(rows))
        return rows

    def _at(self, grid: List[str], cell: Cell) -> str:
        x, y = cell
        if 0 <= y < self.height and 0 <= x < self.width:
            return grid[y][x]
        return " "

    @staticmethod
    def _step(cell: Cell, direction: str) -> Cell:
        dx, dy = DELTA[direction]
        return (cell[0] + dx, cell[1] + dy)

    def _add(self, code: str, message: str, cell: Optional[Cell] = None) -> None:
        x, y = cell if cell else (-1, -1)
        self.report.issues.append(Issue(code, message, x, y))

    # ── pipeline ────────────────────────────────────────────────────────

    def run(self) -> DiagramReport:
        self._find_boxes()
        self._find_groups()
        self._split_layers()
        self._add_group_border_passthroughs()
        self._check_glyph_connections()
        self._check_arrows()
        self._check_ports()
        self._read_edges()
        self._check_adjacent_lines()
        self._check_group_surroundings()
        self._check_group_crossings()
        return self.report

    # ── step 1: boxes ───────────────────────────────────────────────────

    def _find_boxes(self) -> None:
        """Locate node boxes (and the title banner) in the boxes-only canvas."""
        expected_nodes = {n for edge in self.report.expected_edges for n in edge}
        found: Dict[str, List[Box]] = {}

        for y in range(self.height):
            for x in range(self.width):
                corner = self.base[y][x]
                if corner in "┌╭":
                    rect = self._trace_rectangle(x, y, "─", "│", "┐╮", "└╰", "┘╯")
                    if rect:
                        box = Box(self._box_text(x, y, *rect), x, y, *rect)
                        found.setdefault(box.name, []).append(box)
                elif corner == "╔":
                    rect = self._trace_rectangle(x, y, "═", "║", "╗", "╚", "╝")
                    if rect:
                        self._protect_rectangle(x, y, *rect)

        for name in sorted(expected_nodes):
            candidates = found.get(name, [])
            if len(candidates) != 1:
                self._add(
                    "box_missing",
                    f"expected exactly one box for node '{name}', "
                    f"found {len(candidates)}",
                )
            if candidates:
                self.report.boxes[name] = candidates[0]

        for box in self.report.boxes.values():
            self._protect_rectangle(box.x, box.y, box.width, box.height)
            for cy in range(box.y, box.y + box.height):
                for cx in range(box.x, box.x + box.width):
                    side = box.side_of(cx, cy)
                    self.owner[(cx, cy)] = box.name
                    if side != "interior":
                        self.border[(cx, cy)] = (box.name, side)

    # ── step 1b: group boxes ────────────────────────────────────────────

    def _find_groups(self) -> None:
        """Locate dashed group boxes and match them to the expected groups."""
        found: List[GroupBox] = []
        for y in range(self.height):
            for x in range(self.width):
                if self.base[y][x] != GROUP_CORNERS[0]:
                    continue
                rect = self._trace_rectangle(
                    x, y, DASHED_HORIZONTAL, DASHED_VERTICAL, *GROUP_CORNERS[1:]
                )
                if rect:
                    shadow = self._at(self.base, (x + rect[0], y + 1)) == SHADOW
                    found.append(GroupBox(x, y, rect[0], rect[1], shadow))
        self.report.group_boxes = found

        for group in self.groups or ():
            members = [
                self.report.boxes[name]
                for name in map(normalize_name, group.members)
                if name in self.report.boxes
            ]
            holders = [
                index
                for index, candidate in enumerate(found)
                if members and all(candidate.encloses(box) for box in members)
            ]
            if not holders:
                self._add(
                    "group_missing",
                    f"no dashed box encloses the members of group '{group.name}'",
                )
                continue
            index = min(holders, key=lambda i: found[i].width * found[i].height)
            box = found[index] = GroupBox(
                found[index].x,
                found[index].y,
                found[index].width,
                found[index].height,
                found[index].shadow,
                group.name,
            )
            self._find_group_title(index, box)

    def _find_group_title(self, index: int, box: GroupBox) -> None:
        """A group's title sits on the row above its box, within its width."""
        row = box.y - 1
        start = self.base[row].find(box.name, box.x, box.right + 1) if row >= 0 else -1
        if start < 0:
            self._add(
                "group_missing",
                f"title of group '{box.name}' is not above its box",
                (box.x, box.y),
            )
            return
        end = start + len(box.name) - 1
        self.titles[index] = (start, row, end, row)
        # Blanks between the words of a title belong to the title too.
        for cx in range(start, end + 1):
            self.protected.add((cx, row))

    def _trace_rectangle(
        self,
        x: int,
        y: int,
        horizontal: str,
        vertical: str,
        top_right: str,
        bottom_left: str,
        bottom_right: str,
    ) -> Optional[Tuple[int, int]]:
        """Return (width, height) of a complete rectangle whose corner is (x, y)."""
        right = x + 1
        while self._at(self.base, (right, y)) == horizontal:
            right += 1
        if right == x + 1 or self._at(self.base, (right, y)) not in top_right:
            return None

        bottom = y + 1
        while (
            self._at(self.base, (x, bottom)) == vertical
            and self._at(self.base, (right, bottom)) == vertical
        ):
            bottom += 1
        if bottom == y + 1:
            return None
        if self._at(self.base, (x, bottom)) not in bottom_left:
            return None
        if self._at(self.base, (right, bottom)) not in bottom_right:
            return None
        if any(
            self._at(self.base, (cx, bottom)) != horizontal
            for cx in range(x + 1, right)
        ):
            return None
        return (right - x + 1, bottom - y + 1)

    def _box_text(self, x: int, y: int, width: int, height: int) -> str:
        rows = [
            self.base[cy][x + 1 : x + width - 1] for cy in range(y + 1, y + height - 1)
        ]
        return normalize_name(" ".join(rows))

    def _protect_rectangle(self, x: int, y: int, width: int, height: int) -> None:
        for cy in range(y, y + height):
            for cx in range(x, x + width):
                self.protected.add((cx, cy))

    # ── step 2: separate the edge layer from the box layer ──────────────

    def _split_layers(self) -> None:
        """
        Compare base and final cell by cell.

        Anything drawn over blank space, a shadow or a dashed group border
        belongs to the edge layer. Anything else that changed is damage,
        except a port mark on a node box border.
        """
        for y in range(self.height):
            for x in range(self.width):
                cell = (x, y)
                before, after = self.base[y][x], self.final[y][x]
                overwritable = before in (" ", SHADOW) and cell not in self.protected

                if before in (DASHED_VERTICAL, DASHED_HORIZONTAL):
                    self._classify_group_border_cell(cell, before, after)
                elif overwritable:
                    self._classify_edge_cell(cell, before, after)
                elif before != after:
                    self._classify_protected_change(cell, before, after)

    def _classify_edge_cell(self, cell: Cell, before: str, after: str) -> None:
        if after == before:
            return
        if after in LINE_ARMS:
            self.arms[cell] = LINE_ARMS[after]
        elif after in ARROW_HEADS:
            self.arrows[cell] = ARROW_HEADS[after]
        else:
            self._add(
                "box_damaged", f"unexpected '{after}' drawn over '{before}'", cell
            )

    def _classify_group_border_cell(self, cell: Cell, before: str, after: str) -> None:
        if after == before:
            return
        crossing = "─" if before == DASHED_VERTICAL else "│"
        if after in (crossing, "┼"):
            self.arms[cell] = LINE_ARMS[crossing]
        else:
            self._add(
                "group_border_damaged",
                f"group border '{before}' replaced by '{after}'",
                cell,
            )
            if after in LINE_ARMS:
                self.arms[cell] = LINE_ARMS[after]
            elif after in ARROW_HEADS:
                self.arrows[cell] = ARROW_HEADS[after]

    def _classify_protected_change(self, cell: Cell, before: str, after: str) -> None:
        node, side = self.border.get(cell, ("", ""))
        if side in SIDE_PORT_GLYPH and after == SIDE_PORT_GLYPH[side]:
            self.ports[cell] = (node, side)
            return
        node = self.owner.get(cell, "")
        owner = f"box '{node}'" if node else "a title or label"
        self._add("box_damaged", f"{owner}: '{before}' became '{after}'", cell)

    def _add_group_border_passthroughs(self) -> None:
        """
        A line may pass *under* a dashed group border (``──╏──``).

        When lines on both sides reach toward an untouched border cell, treat
        that cell as part of the line so the two halves stay connected.
        """
        for y in range(self.height):
            for x in range(self.width):
                cell = (x, y)
                if cell in self.arms or self.final[y][x] != self.base[y][x]:
                    continue
                for glyph, first, second in (
                    (DASHED_VERTICAL, "L", "R"),
                    (DASHED_HORIZONTAL, "U", "D"),
                ):
                    if self.base[y][x] != glyph:
                        continue
                    if self._reaches(self._step(cell, first), second) and (
                        self._reaches(self._step(cell, second), first)
                    ):
                        self.arms[cell] = first + second

    def _reaches(self, cell: Cell, direction: str) -> bool:
        """Does the edge-layer glyph at ``cell`` reach toward ``direction``?"""
        if cell in self.arms:
            return direction in self.arms[cell]
        if cell in self.arrows:
            return OPPOSITE[self.arrows[cell]] == direction
        return False

    # ── step 3: every arm must meet something ───────────────────────────

    def _key(self, cell: Cell, direction: str) -> Tuple[Cell, str]:
        """
        Identity of the line passing through ``cell`` along ``direction``.

        A crossing carries two independent lines, so it gets two keys.
        """
        if self.arms.get(cell) == "UDLR":
            return (cell, "h" if direction in "LR" else "v")
        return (cell, "*")

    def _find(self, key: Tuple[Cell, str]) -> Tuple[Cell, str]:
        self.parent.setdefault(key, key)
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def _union(self, a: Tuple[Cell, str], b: Tuple[Cell, str]) -> None:
        self.parent[self._find(a)] = self._find(b)

    def _check_glyph_connections(self) -> None:
        for cell, arms in sorted(self.arms.items()):
            glyph = self._at(self.final, cell)
            for direction in arms:
                self._find(self._key(cell, direction))
                neighbour = self._step(cell, direction)
                back = OPPOSITE[direction]

                if neighbour in self.arms:
                    if back in self.arms[neighbour]:
                        self._union(
                            self._key(cell, direction), self._key(neighbour, back)
                        )
                    else:
                        other = self._at(self.final, neighbour)
                        self._add(
                            "dangling_line",
                            f"'{glyph}' reaches {direction} toward '{other}', "
                            "which does not connect back",
                            cell,
                        )
                elif neighbour in self.arrows:
                    if OPPOSITE[self.arrows[neighbour]] == back:
                        self._union(self._key(cell, direction), (neighbour, "*"))
                    else:
                        self._add(
                            "arrow_hit_sideways",
                            f"'{glyph}' runs into the side or tip of arrowhead "
                            f"'{self._at(self.final, neighbour)}'",
                            neighbour,
                        )
                elif neighbour in self.border:
                    node, side = self.border[neighbour]
                    if SIDE_ENTRY_DIRECTION.get(side) == direction:
                        self.exits.append((self._key(cell, direction), node))
                    else:
                        self._add(
                            "dangling_line",
                            f"'{glyph}' reaches {direction} into the {side} of "
                            f"box '{node}' without attaching to it",
                            cell,
                        )
                else:
                    self._add(
                        "dangling_line",
                        f"'{glyph}' reaches {direction} toward nothing",
                        cell,
                    )

    # ── step 4: arrowheads ──────────────────────────────────────────────

    def _check_arrows(self) -> None:
        for cell, head in sorted(self.arrows.items()):
            glyph = self._at(self.final, cell)
            key = self._find((cell, "*"))

            tip = self._step(cell, head)
            node, side = self.border.get(tip, ("", ""))
            if SIDE_ENTRY_DIRECTION.get(side) == head:
                self.entries.append((key, node))
            else:
                self._add(
                    "floating_arrow",
                    f"arrowhead '{glyph}' does not touch the side of a node box",
                    cell,
                )

            tail = self._step(cell, OPPOSITE[head])
            port = self.ports.get(tail)
            if self._reaches(tail, head):
                continue
            if port and SIDE_OUTWARD[port[1]] == head:
                self.exits.append((key, port[0]))  # port mark feeds arrow directly
                continue
            self._add("arrow_no_tail", f"nothing leads into arrowhead '{glyph}'", cell)

    # ── step 5: port marks on box borders ───────────────────────────────

    def _check_ports(self) -> None:
        for cell, (node, side) in sorted(self.ports.items()):
            outward = SIDE_OUTWARD[side]
            if not self._reaches(self._step(cell, outward), OPPOSITE[outward]):
                self._add(
                    "dangling_port",
                    f"port mark on the {side} of box '{node}' has no line attached",
                    cell,
                )

    # ── step 6: read the edges the picture shows ────────────────────────

    def _read_edges(self) -> None:
        crossings = [cell for cell, arms in self.arms.items() if arms == "UDLR"]
        promoted: Set[Cell] = set()

        # A ┼ whose two lines cannot both stand alone is a four-way junction.
        changed = True
        while changed:
            changed = False
            sources, targets = self._line_endpoints()
            for cell in crossings:
                a, b = self._find((cell, "h")), self._find((cell, "v"))
                if a == b:
                    continue
                incomplete = any(
                    not sources.get(k) or not targets.get(k) for k in (a, b)
                )
                if incomplete:
                    self._union(a, b)
                    promoted.add(cell)
                    changed = True
                    break

        sources, targets = self._line_endpoints()
        lines = {self._find(key) for key in list(self.parent)}
        drawn: Set[Edge] = set()
        for line in sorted(lines):
            line_sources = sources.get(line, set())
            line_targets = targets.get(line, set())
            if line_sources and line_targets:
                drawn |= {(s, t) for s in line_sources for t in line_targets}
            else:
                missing = "no source box" if not line_sources else "no arrowhead"
                if not line_sources and not line_targets:
                    missing = "neither a source box nor an arrowhead"
                self._add("stray_line", f"a line here has {missing}", line[0])

        expected = self.report.expected_edges
        for source, target in sorted(expected - drawn):
            self._add("missing_edge", f"cannot trace '{source}' -> '{target}'")
        for source, target in sorted(drawn - expected):
            self._add(
                "phantom_edge",
                f"picture shows '{source}' -> '{target}', which is not in the input",
            )

        self.report.drawn_edges = drawn
        self.report.junctions = len(promoted)
        self.report.crossings = len(crossings) - len(promoted)

    def _line_endpoints(
        self,
    ) -> Tuple[Dict[Tuple[Cell, str], Set[str]], Dict[Tuple[Cell, str], Set[str]]]:
        sources: Dict[Tuple[Cell, str], Set[str]] = {}
        targets: Dict[Tuple[Cell, str], Set[str]] = {}
        for key, node in self.exits:
            sources.setdefault(self._find(key), set()).add(node)
        for key, node in self.entries:
            targets.setdefault(self._find(key), set()).add(node)
        return sources, targets

    # ── step 7: legibility ──────────────────────────────────────────────

    def _has_vertical_stroke(self, cell: Cell) -> bool:
        if cell in self.arrows:
            return self.arrows[cell] in "UD"
        return any(d in self.arms.get(cell, "") for d in "UD")

    def _has_horizontal_stroke(self, cell: Cell) -> bool:
        if cell in self.arrows:
            return self.arrows[cell] in "LR"
        return any(d in self.arms.get(cell, "") for d in "LR")

    def _check_adjacent_lines(self) -> None:
        """Flag vertical strokes in touching columns that are not one line."""
        for y in range(self.height):
            run_start = None
            for x in range(self.width + 1):
                left, cell = (x - 1, y), (x, y)
                touching = (
                    x < self.width
                    and self._has_vertical_stroke(left)
                    and self._has_vertical_stroke(cell)
                    and not (self._reaches(left, "R") and self._reaches(cell, "L"))
                )
                if touching and run_start is None:
                    run_start = x - 1
                elif not touching and run_start is not None:
                    text = self.final[y][run_start:x]
                    self._add(
                        "adjacent_lines",
                        f"unconnected strokes side by side: '{text}'",
                        (run_start, y),
                    )
                    run_start = None

    # ── step 8: group boxes keep their distance ─────────────────────────

    @staticmethod
    def _apart(a: Rect, b: Rect) -> int:
        """Blank cells between two rectangles (-1 when they overlap)."""
        across = max(a[0] - b[2], b[0] - a[2]) - 1
        down = max(a[1] - b[3], b[1] - a[3]) - 1
        return max(across, down, -1)

    def _box_footprint(self, box: Box) -> Rect:
        """A node box and its shadow."""
        shadow = self._at(self.base, (box.x + box.width, box.y + 1)) == SHADOW
        extra = 1 if shadow else 0
        return (
            box.x,
            box.y,
            box.x + box.width - 1 + extra,
            box.y + box.height - 1 + extra,
        )

    @staticmethod
    def _label(group: GroupBox) -> str:
        if group.name:
            return f"group '{group.name}'"
        return f"the group box at (x={group.x}, y={group.y})"

    def _check_group_surroundings(self) -> None:
        groups = self.report.group_boxes
        for index, group in enumerate(groups):
            self._check_group_neighbours(index, group)
            self._check_group_boxes(index, group)
            self._check_group_title(index, group)
            self._check_lines_along_border(group)
        self._check_arrows_at_borders()

    def _check_group_neighbours(self, index: int, group: GroupBox) -> None:
        """Group boxes (and their titles) never overlap or touch."""
        mine = [group.footprint()]
        if index in self.titles:
            mine.append(self.titles[index])
        for other_index in range(index + 1, len(self.report.group_boxes)):
            other = self.report.group_boxes[other_index]
            theirs = [other.footprint()]
            if other_index in self.titles:
                theirs.append(self.titles[other_index])
            apart = min(self._apart(a, b) for a in mine for b in theirs)
            pair = f"{self._label(group)} and {self._label(other)}"
            if apart < 0:
                self._add("group_overlap", f"{pair} overlap", (other.x, other.y))
            elif apart < GROUP_CLEARANCE:
                self._add("group_crowded", f"{pair} touch", (other.x, other.y))

    def _check_group_boxes(self, index: int, group: GroupBox) -> None:
        """Members sit well inside the border; every other box well outside."""
        members = None
        if self.groups is not None and group.name:
            members = {
                normalize_name(member)
                for definition in self.groups
                if definition.name == group.name
                for member in definition.members
            }
        rect = (group.x, group.y, group.right, group.bottom)
        label = self._label(group)

        for box in self.report.boxes.values():
            where = (box.x, box.y)
            box_rect = (
                box.x,
                box.y,
                box.x + box.width - 1,
                box.y + box.height - 1,
            )
            if group.encloses(box):
                if members is not None and box.name not in members:
                    self._add(
                        "group_overlap",
                        f"box '{box.name}' is inside {label} without being a member",
                        where,
                    )
                elif self._apart_inside(box_rect, rect) < GROUP_MEMBER_CLEARANCE:
                    self._add(
                        "group_crowded",
                        f"box '{box.name}' is too close to the border of {label}",
                        where,
                    )
            else:
                # A box that is not enclosed cannot be on the border either:
                # it would have overwritten the border, and the group would
                # not have been found. So it is outside; is it far enough?
                near = [group.footprint()]
                if index in self.titles:
                    near.append(self.titles[index])
                footprint = self._box_footprint(box)
                if min(self._apart(footprint, r) for r in near) < GROUP_CLEARANCE:
                    self._add(
                        "group_crowded", f"box '{box.name}' touches {label}", where
                    )

    @staticmethod
    def _apart_inside(inner: Rect, outer: Rect) -> int:
        """Smallest number of cells between an inner rectangle and its frame."""
        return (
            min(
                inner[0] - outer[0],
                inner[1] - outer[1],
                outer[2] - inner[2],
                outer[3] - inner[3],
            )
            - 1
        )

    def _check_group_title(self, index: int, group: GroupBox) -> None:
        """Nothing but blank space touches a title or runs right above it."""
        if index not in self.titles:
            return
        start, row, end, _ = self.titles[index]
        label = self._label(group)
        for cell in ((start - 1, row), (end + 1, row)):
            if self._at(self.final, cell) != " ":
                self._add(
                    "group_crowded",
                    f"'{self._at(self.final, cell)}' touches the title of {label}",
                    cell,
                )
        above = [
            (cx, row - 1)
            for cx in range(start, end + 1)
            if self._has_horizontal_stroke((cx, row - 1))
        ]
        if above:
            self._add(
                "group_crowded",
                f"a line runs right above the title of {label}",
                above[0],
            )

    def _check_lines_along_border(self, group: GroupBox) -> None:
        """A line running along a border keeps a blank cell away from it."""
        shadow = 1 if group.shadow else 0
        reach = GROUP_CLEARANCE
        # (cells of the side, step away from the box, distance to check on
        #  the outside, are the strokes to look for vertical?)
        columns = range(group.x, group.right + 1 + shadow)
        rows = range(group.y, group.bottom + 1 + shadow)
        sides = (
            ("left", [(group.x, cy) for cy in rows], (-1, 0), reach, True),
            ("right", [(group.right, cy) for cy in rows], (1, 0), reach + shadow, True),
            ("top", [(cx, group.y) for cx in columns], (0, -1), reach, False),
            (
                "bottom",
                [(cx, group.bottom) for cx in columns],
                (0, 1),
                reach + shadow,
                False,
            ),
        )
        for side, cells, (dx, dy), outside, vertical in sides:
            stroke = (
                self._has_vertical_stroke if vertical else self._has_horizontal_stroke
            )
            hugging: List[Cell] = []
            for cx, cy in cells:
                near = [(cx + dx * d, cy + dy * d) for d in range(1, outside + 1)] + [
                    (cx - dx * d, cy - dy * d) for d in range(1, reach + 1)
                ]
                hugging += [cell for cell in near if stroke(cell)]
            if hugging:
                first = min(hugging, key=lambda cell: (cell[1], cell[0]))
                self._add(
                    "group_crowded",
                    f"a line runs along the {side} border of {self._label(group)}",
                    first,
                )

    def _check_arrows_at_borders(self) -> None:
        """An arrowhead keeps a cell of line between itself and a border."""
        borders: Dict[Cell, GroupBox] = {}
        for group in self.report.group_boxes:
            for cell in group.border_cells():
                borders[cell] = group
        for cell, head in sorted(self.arrows.items()):
            tail = self._step(cell, OPPOSITE[head])
            if tail in borders:
                self._add(
                    "group_crowded",
                    f"an arrowhead touches the border of {self._label(borders[tail])}",
                    cell,
                )

    # ── step 9: lines cross a group border only when they have to ───────

    def _check_group_crossings(self) -> None:
        """
        A crossing says "this edge leaves the group".

        So an edge between two members must stay inside the box, and an edge
        between two boxes outside must not pass through it.
        """
        sources, targets = self._line_endpoints()
        for group in self.report.group_boxes:
            border = group.border_cells()
            crossed: Dict[Tuple[Cell, str], Cell] = {}
            for cell in sorted(border):
                for direction in self.arms.get(cell, ""):
                    crossed.setdefault(self._find(self._key(cell, direction)), cell)

            for line, cell in sorted(crossed.items(), key=lambda item: item[1]):
                ends = sources.get(line, set()) | targets.get(line, set())
                inside = {
                    name
                    for name in ends
                    if name in self.report.boxes
                    and group.encloses(self.report.boxes[name])
                }
                if not ends or (inside and inside != ends):
                    continue  # connects a member to the outside (or is stray)
                what = "between members leaves" if inside else "passes through"
                self._add(
                    "group_crossing",
                    f"a line {what} {self._label(group)}",
                    cell,
                )
