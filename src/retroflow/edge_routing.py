"""
Edge routing module for flowchart generator.

Implements orthogonal edge routing with:
- Occupancy grid for obstacle avoidance
- Discrete ports on box sides with smart assignment
- A* pathfinding for edge routing that avoids boxes
- Channel-based routing to prevent edge overlap
"""

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

# =============================================================================
# ROUTING CONFIGURATION - Adjust these values to tune routing behavior
# =============================================================================

# --- Distance/Spacing Parameters (in pixels) ---

# Minimum distance from box edge when routing alongside
# Higher values keep arrows further from boxes
MIN_BOX_CLEARANCE = 50  # 25 default

# Minimum segment length between a turn and a box connection
# Higher values give more room for arrowheads
MIN_SEGMENT_LENGTH = 50  # 30 default

# Minimum separation between parallel edges
# Higher values spread out parallel arrows more
MIN_EDGE_SEPARATION = 30  # 15 default

# Spacing for routing channels between boxes
CHANNEL_SPACING = 20  # 4 default

# Margin around boxes when marking them in the occupancy grid
BOX_MARGIN = 10  # 2 default

# --- Scoring Penalties for Side Selection ---
# Lower scores are preferred when choosing which sides to connect

# Penalty for routing against the natural flow direction
# (e.g., going left when target is to the right)
DIRECTION_PENALTY = 50  # 500 default

# Penalty when the path would go through a box
OBSTRUCTION_PENALTY = 100000  # 2000 default

# Penalty for paths requiring more turns (L-shaped vs straight)
TURN_PENALTY = 10  # 300 default

# Multiplier for already-used ports (spreads edges across ports)
PORT_USAGE_PENALTY = 100000  # 200 default

# Penalty for non-center ports (prefers middle ports when equal)
NON_CENTER_PORT_PENALTY = 1  # 100 default

# --- Layout Scoring Weights (used by score_layout and refine_routes) ---
# These control the global optimization scoring

# Weight for total wire length (lower = less penalty for long wires)
WIRE_LENGTH_WEIGHT = 0.005

# Penalty per edge crossing (higher = stronger avoidance of crossings)
CROSSING_PENALTY = 200

# Penalty multiplier for edge congestion (parallel edges too close)
CONGESTION_PENALTY = 100

# Multiplier for proximity violations (edges too close to boxes)
PROXIMITY_PENALTY_MULTIPLIER = 2

# =============================================================================


class CellType(Enum):
    """Types of cells in the occupancy grid."""

    EMPTY = 0
    BOX = 1
    HORIZONTAL_EDGE = 2
    VERTICAL_EDGE = 3
    JUNCTION = 4  # Where edges cross or meet


class PortPosition(Enum):
    """Discrete port positions on each side of a box."""

    START = 0.25  # Near the start (top/left) of the side
    MIDDLE = 0.5  # Middle of the side
    END = 0.75  # Near the end (bottom/right) of the side


@dataclass
class Port:
    """A connection port on a box."""

    node: str
    side: str  # 'top', 'bottom', 'left', 'right'
    position: PortPosition
    x: int  # Absolute x coordinate
    y: int  # Absolute y coordinate
    in_use: bool = False


@dataclass
class BoxBounds:
    """Bounding box for a node."""

    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2


@dataclass
class EdgeRoute:
    """A routed edge with waypoints."""

    source: str
    target: str
    source_port: Port
    target_port: Port
    waypoints: List[Tuple[int, int]]  # List of (x, y) points
    is_bidirectional: bool = False


@dataclass
class RoutingChannel:
    """A horizontal or vertical channel for routing edges."""

    position: int  # x for vertical channels, y for horizontal channels
    is_horizontal: bool
    used_segments: List[Tuple[int, int]] = field(
        default_factory=list
    )  # List of (start, end) ranges


class OccupancyGrid:
    """
    Tracks which cells are occupied by boxes or edges.

    Uses a sparse representation for efficiency.
    """

    def __init__(self, width: int, height: int, cell_size: int = 1):
        """
        Initialize the occupancy grid.

        Args:
            width: Grid width in pixels
            height: Grid height in pixels
            cell_size: Size of each cell in pixels (for coordinate conversion)
        """
        self.width = width
        self.height = height
        self.cell_size = cell_size
        self.cells: Dict[Tuple[int, int], CellType] = {}
        self.box_cells: Dict[str, Set[Tuple[int, int]]] = defaultdict(set)
        self.box_bounds: Dict[str, BoxBounds] = {}

    def mark_box(self, node: str, bounds: BoxBounds, margin: int = 1):
        """
        Mark cells occupied by a box (with margin for routing clearance).

        Args:
            node: Node name
            bounds: Box bounding box
            margin: Extra cells around box to keep clear
        """
        self.box_bounds[node] = bounds
        x1 = max(0, bounds.x - margin)
        y1 = max(0, bounds.y - margin)
        x2 = min(self.width, bounds.x2 + margin)
        y2 = min(self.height, bounds.y2 + margin)

        for x in range(x1, x2):
            for y in range(y1, y2):
                self.cells[(x, y)] = CellType.BOX
                self.box_cells[node].add((x, y))

    def mark_edge_segment(self, x1: int, y1: int, x2: int, y2: int, edge_id: str = ""):
        """Mark cells occupied by an edge segment."""
        if x1 == x2:  # Vertical line
            for y in range(min(y1, y2), max(y1, y2) + 1):
                cell = (x1, y)
                current = self.cells.get(cell, CellType.EMPTY)
                if current == CellType.EMPTY:
                    self.cells[cell] = CellType.VERTICAL_EDGE
                elif current == CellType.HORIZONTAL_EDGE:
                    self.cells[cell] = CellType.JUNCTION
        elif y1 == y2:  # Horizontal line
            for x in range(min(x1, x2), max(x1, x2) + 1):
                cell = (x, y1)
                current = self.cells.get(cell, CellType.EMPTY)
                if current == CellType.EMPTY:
                    self.cells[cell] = CellType.HORIZONTAL_EDGE
                elif current == CellType.VERTICAL_EDGE:
                    self.cells[cell] = CellType.JUNCTION

    def is_box(self, x: int, y: int) -> bool:
        """Check if a cell contains a box."""
        return self.cells.get((x, y), CellType.EMPTY) == CellType.BOX

    def is_free(self, x: int, y: int) -> bool:
        """Check if a cell is free for routing."""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return False
        cell_type = self.cells.get((x, y), CellType.EMPTY)
        return cell_type != CellType.BOX

    def is_empty(self, x: int, y: int) -> bool:
        """Check if a cell is completely empty."""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return False
        return (x, y) not in self.cells

    def has_edge(self, x: int, y: int) -> bool:
        """Check if a cell has an edge passing through it."""
        cell_type = self.cells.get((x, y), CellType.EMPTY)
        return cell_type in (
            CellType.HORIZONTAL_EDGE,
            CellType.VERTICAL_EDGE,
            CellType.JUNCTION,
        )

    def get_cell_type(self, x: int, y: int) -> CellType:
        """Get the type of a cell."""
        return self.cells.get((x, y), CellType.EMPTY)

    def point_in_any_box(self, x: int, y: int, exclude_nodes: Set[str] = None) -> bool:
        """Check if a point is inside any box (excluding specified nodes)."""
        exclude_nodes = exclude_nodes or set()
        for node, bounds in self.box_bounds.items():
            if node in exclude_nodes:
                continue
            if bounds.x <= x <= bounds.x2 and bounds.y <= y <= bounds.y2:
                return True
        return False

    def line_intersects_box(
        self, x1: int, y1: int, x2: int, y2: int, exclude_nodes: Set[str] = None
    ) -> bool:
        """Check if a line segment intersects any box."""
        exclude_nodes = exclude_nodes or set()

        for node, bounds in self.box_bounds.items():
            if node in exclude_nodes:
                continue

            # Check if line intersects this box
            if x1 == x2:  # Vertical line
                if bounds.x < x1 < bounds.x2:
                    if not (max(y1, y2) < bounds.y or min(y1, y2) > bounds.y2):
                        return True
            elif y1 == y2:  # Horizontal line
                if bounds.y < y1 < bounds.y2:
                    if not (max(x1, x2) < bounds.x or min(x1, x2) > bounds.x2):
                        return True

        return False


class PortManager:
    """
    Manages discrete ports on boxes.

    Each side of a box has 3 ports: START (25%), MIDDLE (50%), END (75%).
    Tracks usage to spread edges across available ports.
    """

    def __init__(self):
        self.ports: Dict[str, Dict[str, List[Port]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.port_usage: Dict[str, Dict[str, List[PortPosition]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def create_ports_for_box(self, node: str, bounds: BoxBounds):
        """Create all ports for a box."""
        # Top side ports (left to right)
        for pos in PortPosition:
            x = bounds.x + int(bounds.width * pos.value)
            self.ports[node]["top"].append(Port(node, "top", pos, x, bounds.y, False))

        # Bottom side ports (left to right)
        for pos in PortPosition:
            x = bounds.x + int(bounds.width * pos.value)
            self.ports[node]["bottom"].append(
                Port(node, "bottom", pos, x, bounds.y2, False)
            )

        # Left side ports (top to bottom)
        for pos in PortPosition:
            y = bounds.y + int(bounds.height * pos.value)
            self.ports[node]["left"].append(Port(node, "left", pos, bounds.x, y, False))

        # Right side ports (top to bottom)
        for pos in PortPosition:
            y = bounds.y + int(bounds.height * pos.value)
            self.ports[node]["right"].append(
                Port(node, "right", pos, bounds.x2, y, False)
            )

    def get_port_at_position(
        self, node: str, side: str, position: PortPosition
    ) -> Optional[Port]:
        """Get a specific port."""
        ports = self.ports.get(node, {}).get(side, [])
        for port in ports:
            if port.position == position:
                return port
        return None

    def get_available_port(
        self,
        node: str,
        side: str,
        target_coord: int,
        is_horizontal_side: bool,
    ) -> Optional[Port]:
        """
        Get the best available port on a side.

        Enforces strict one-edge-per-port rule: returns None if all ports
        on this side are already in use.

        Args:
            node: Node name
            side: Side of the box
            target_coord: Target x (for top/bottom) or y (for left/right)
            is_horizontal_side: True for top/bottom sides

        Returns:
            Available Port, or None if all ports on this side are taken
        """
        ports = self.ports.get(node, {}).get(side, [])
        if not ports:
            return None

        # Filter to only unused ports (strict one-edge-per-port rule)
        available_ports = [p for p in ports if not p.in_use]
        if not available_ports:
            return None  # All ports on this side are taken

        # Score available ports: prefer closest to target, then center
        scored_ports = []
        for port in available_ports:
            coord = port.x if is_horizontal_side else port.y
            dist = abs(coord - target_coord)
            # Small penalty for non-middle ports to prefer center when equal
            is_center = port.position == PortPosition.MIDDLE
            center_penalty = 0 if is_center else NON_CENTER_PORT_PENALTY
            score = dist + center_penalty
            scored_ports.append((score, port))

        scored_ports.sort(key=lambda x: x[0])
        best_port = scored_ports[0][1]

        # Mark as used
        self.port_usage[node][side].append(best_port.position)
        best_port.in_use = True

        return best_port

    def get_next_available_port(self, node: str, side: str) -> Optional[Port]:
        """
        Get the next unused port on a side, cycling through positions.

        Enforces strict one-edge-per-port rule: returns None if all ports
        on this side are already in use.
        """
        ports = self.ports.get(node, {}).get(side, [])
        if not ports:
            return None

        used_positions = self.port_usage[node][side]

        # Only return unused ports (strict one-edge-per-port rule)
        for port in ports:
            if port.position not in used_positions:
                self.port_usage[node][side].append(port.position)
                port.in_use = True
                return port

        # All ports on this side are taken - return None to force different side
        return None

    def count_used_ports(self, node: str, side: str) -> int:
        """Count how many ports are used on a side."""
        return len(self.port_usage[node][side])

    def validate_no_duplicate_ports(self) -> Tuple[bool, List[str]]:
        """
        Validate that no port is used more than once.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        for node, sides in self.ports.items():
            for side, ports in sides.items():
                used_positions = self.port_usage[node][side]

                # Check for duplicate positions in usage tracking
                if len(used_positions) != len(set(used_positions)):
                    duplicates = [
                        p for p in used_positions if used_positions.count(p) > 1
                    ]
                    errors.append(
                        f"Duplicate port positions on {node}.{side}: {duplicates}"
                    )

                # Check that in_use flag matches usage tracking
                for port in ports:
                    is_tracked = port.position in used_positions
                    if port.in_use != is_tracked:
                        errors.append(
                            f"Port state mismatch on {node}.{side}.{port.position}: "
                            f"in_use={port.in_use}, tracked={is_tracked}"
                        )

                # Check that we don't exceed 3 ports per side
                if len(set(used_positions)) > 3:
                    errors.append(
                        f"More than 3 ports used on {node}.{side}: {used_positions}"
                    )

        return (len(errors) == 0, errors)


class ChannelManager:
    """
    Manages routing channels to prevent edge overlap.

    Creates horizontal and vertical channels between boxes for routing.
    """

    def __init__(self, grid: OccupancyGrid, spacing: int = CHANNEL_SPACING):
        self.grid = grid
        self.spacing = spacing
        self.horizontal_channels: List[RoutingChannel] = []
        self.vertical_channels: List[RoutingChannel] = []
        self._compute_channels()

    def _compute_channels(self):
        """Compute available routing channels based on box positions."""
        if not self.grid.box_bounds:
            return

        # Get all box y-coordinates (for horizontal channels between rows)
        y_coords = set()
        x_coords = set()

        for bounds in self.grid.box_bounds.values():
            y_coords.add(bounds.y)
            y_coords.add(bounds.y2)
            x_coords.add(bounds.x)
            x_coords.add(bounds.x2)

        # Create horizontal channels between box rows
        sorted_y = sorted(y_coords)
        for i in range(len(sorted_y) - 1):
            y1, y2 = sorted_y[i], sorted_y[i + 1]
            if y2 - y1 > self.spacing * 2:
                # Create multiple channels in this gap
                mid = (y1 + y2) // 2
                self.horizontal_channels.append(RoutingChannel(mid, is_horizontal=True))

        # Create vertical channels between box columns
        sorted_x = sorted(x_coords)
        for i in range(len(sorted_x) - 1):
            x1, x2 = sorted_x[i], sorted_x[i + 1]
            if x2 - x1 > self.spacing * 2:
                mid = (x1 + x2) // 2
                self.vertical_channels.append(RoutingChannel(mid, is_horizontal=False))

    def get_horizontal_channel(
        self, y_min: int, y_max: int, x_start: int, x_end: int
    ) -> Optional[int]:
        """
        Get a horizontal channel y-coordinate for routing.

        Args:
            y_min: Minimum y bound
            y_max: Maximum y bound
            x_start: Start x of the segment
            x_end: End x of the segment

        Returns:
            Y coordinate of available channel, or None
        """
        for channel in self.horizontal_channels:
            if y_min <= channel.position <= y_max:
                # Check if this segment overlaps with existing usage
                segment = (min(x_start, x_end), max(x_start, x_end))
                overlap = False
                for used_start, used_end in channel.used_segments:
                    if not (segment[1] < used_start or segment[0] > used_end):
                        overlap = True
                        break
                if not overlap:
                    channel.used_segments.append(segment)
                    return channel.position

        # No free channel, compute a new position
        return (y_min + y_max) // 2

    def get_vertical_channel(
        self, x_min: int, x_max: int, y_start: int, y_end: int
    ) -> Optional[int]:
        """Get a vertical channel x-coordinate for routing."""
        for channel in self.vertical_channels:
            if x_min <= channel.position <= x_max:
                segment = (min(y_start, y_end), max(y_start, y_end))
                overlap = False
                for used_start, used_end in channel.used_segments:
                    if not (segment[1] < used_start or segment[0] > used_end):
                        overlap = True
                        break
                if not overlap:
                    channel.used_segments.append(segment)
                    return channel.position

        return (x_min + x_max) // 2


class OrthogonalRouter:
    """
    Routes edges using orthogonal (90-degree) paths.

    Uses A* pathfinding with proper obstacle avoidance.
    Configuration values are module-level globals for easy tuning.
    """

    def __init__(
        self,
        grid: OccupancyGrid,
        port_manager: PortManager,
        box_bounds: Dict[str, BoxBounds],
    ):
        self.grid = grid
        self.port_manager = port_manager
        self.box_bounds = box_bounds
        self.routes: List[EdgeRoute] = []
        self.channel_manager = ChannelManager(grid)
        self.edge_channels: Dict[str, int] = {}  # Track which channel each edge uses

        # Track used edge segments for overlap prevention
        # Vertical: (x, y_min, y_max), Horizontal: (y, x_min, x_max)
        self.used_vertical_segments: List[Tuple[int, int, int]] = []
        self.used_horizontal_segments: List[Tuple[int, int, int]] = []

        # Track exit counts per node/side for lane separation
        # Key: (node, side), Value: count of edges that have exited from that side
        self.exit_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        self.entry_counts: Dict[Tuple[str, str], int] = defaultdict(int)

    def _get_all_side_options(
        self, source: str, target: str
    ) -> List[Tuple[str, str, float]]:
        """
        Get all valid side combinations with scores.

        Returns list of (source_side, target_side, score) sorted by score.
        """
        src = self.box_bounds[source]
        tgt = self.box_bounds[target]

        options = []

        # All possible side combinations
        side_pairs = [
            ("right", "left"),
            ("left", "right"),
            ("bottom", "top"),
            ("top", "bottom"),
            ("right", "top"),
            ("right", "bottom"),
            ("left", "top"),
            ("left", "bottom"),
            ("bottom", "left"),
            ("bottom", "right"),
            ("top", "left"),
            ("top", "right"),
        ]

        for src_side, tgt_side in side_pairs:
            # Get port positions
            src_port = self._get_side_center(src, src_side)
            tgt_port = self._get_side_center(tgt, tgt_side)

            # Calculate base distance
            dist = abs(src_port[0] - tgt_port[0]) + abs(src_port[1] - tgt_port[1])

            # Penalize going against the natural flow direction
            dx = tgt.center_x - src.center_x
            dy = tgt.center_y - src.center_y

            direction_penalty = 0
            if dx > 0 and src_side == "left":
                direction_penalty += DIRECTION_PENALTY
            if dx < 0 and src_side == "right":
                direction_penalty += DIRECTION_PENALTY
            if dy > 0 and src_side == "top":
                direction_penalty += DIRECTION_PENALTY
            if dy < 0 and src_side == "bottom":
                direction_penalty += DIRECTION_PENALTY

            # Check if path would go through boxes
            path_clear = self._check_path_viable(
                src_port[0], src_port[1], tgt_port[0], tgt_port[1], {source, target}
            )
            obstruction_penalty = 0 if path_clear else OBSTRUCTION_PENALTY

            # Prefer simpler paths (fewer turns)
            turn_penalty = 0
            if src_side in ("left", "right") and tgt_side in ("top", "bottom"):
                turn_penalty = TURN_PENALTY
            elif src_side in ("top", "bottom") and tgt_side in ("left", "right"):
                turn_penalty = TURN_PENALTY

            # Penalize already-used sides
            src_usage = self.port_manager.count_used_ports(source, src_side)
            tgt_usage = self.port_manager.count_used_ports(target, tgt_side)
            usage_penalty = (src_usage + tgt_usage) * PORT_USAGE_PENALTY

            score = (
                dist
                + direction_penalty
                + obstruction_penalty
                + turn_penalty
                + usage_penalty
            )
            options.append((src_side, tgt_side, score))

        options.sort(key=lambda x: x[2])
        return options

    def _get_side_center(self, bounds: BoxBounds, side: str) -> Tuple[int, int]:
        """Get the center point of a box side."""
        if side == "top":
            return (bounds.center_x, bounds.y)
        elif side == "bottom":
            return (bounds.center_x, bounds.y2)
        elif side == "left":
            return (bounds.x, bounds.center_y)
        else:  # right
            return (bounds.x2, bounds.center_y)

    def _check_path_viable(
        self, x1: int, y1: int, x2: int, y2: int, exclude_nodes: Set[str]
    ) -> bool:
        """Check if a simple path is viable (doesn't go through boxes)."""
        # Check L-shaped path
        mid_x = (x1 + x2) // 2

        # Try horizontal-first path
        if not self.grid.line_intersects_box(x1, y1, x2, y1, exclude_nodes):
            if not self.grid.line_intersects_box(x2, y1, x2, y2, exclude_nodes):
                return True

        # Try vertical-first path
        if not self.grid.line_intersects_box(x1, y1, x1, y2, exclude_nodes):
            if not self.grid.line_intersects_box(x1, y2, x2, y2, exclude_nodes):
                return True

        # Try Z-shaped path through midpoint
        if not self.grid.line_intersects_box(x1, y1, mid_x, y1, exclude_nodes):
            if not self.grid.line_intersects_box(mid_x, y1, mid_x, y2, exclude_nodes):
                if not self.grid.line_intersects_box(mid_x, y2, x2, y2, exclude_nodes):
                    return True

        return False

    def route_edge(
        self,
        source: str,
        target: str,
        is_bidirectional: bool = False,
    ) -> Optional[EdgeRoute]:
        """
        Route an edge from source to target.

        Tries multiple side combinations until it finds one with available ports.
        Enforces strict one-edge-per-port rule.

        Args:
            source: Source node name
            target: Target node name
            is_bidirectional: Whether this is a bidirectional edge

        Returns:
            EdgeRoute with waypoints, or None if routing failed
        """
        if source not in self.box_bounds or target not in self.box_bounds:
            return None

        src_bounds = self.box_bounds[source]
        tgt_bounds = self.box_bounds[target]

        # Get all side combinations sorted by preference
        side_options = self._get_all_side_options(source, target)

        # Try each side combination until we find one with available ports
        for src_side, tgt_side, _ in side_options:
            is_src_horizontal = src_side in ("top", "bottom")
            is_tgt_horizontal = tgt_side in ("top", "bottom")

            # Try to get available ports (strict one-edge-per-port)
            src_port = self.port_manager.get_available_port(
                source,
                src_side,
                tgt_bounds.center_x if is_src_horizontal else tgt_bounds.center_y,
                is_src_horizontal,
            )
            if not src_port:
                continue  # No available port on this source side, try next

            tgt_port = self.port_manager.get_available_port(
                target,
                tgt_side,
                src_bounds.center_x if is_tgt_horizontal else src_bounds.center_y,
                is_tgt_horizontal,
            )
            if not tgt_port:
                # Release the source port we just claimed
                self._release_port(src_port)
                continue  # No available port on this target side, try next

            # Found valid ports - route the path
            waypoints = self._route_path(
                src_port.x,
                src_port.y,
                tgt_port.x,
                tgt_port.y,
                src_side,
                tgt_side,
                source,
                target,
            )

            # Mark the route in the grid
            self._mark_route(waypoints)

            route = EdgeRoute(
                source=source,
                target=target,
                source_port=src_port,
                target_port=tgt_port,
                waypoints=waypoints,
                is_bidirectional=is_bidirectional,
            )
            self.routes.append(route)
            return route

        # No valid side combination found with available ports
        return None

    def _release_port(self, port: Port):
        """Release a port that was claimed but not used."""
        port.in_use = False
        usage_list = self.port_manager.port_usage[port.node][port.side]
        if port.position in usage_list:
            usage_list.remove(port.position)

    def _route_path(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        src_side: str,
        tgt_side: str,
        source: str,
        target: str,
    ) -> List[Tuple[int, int]]:
        """
        Route a path from (x1, y1) to (x2, y2) with given side constraints.

        Ensures minimum segment length between turns and box connections.
        Uses lane separation when multiple edges exit/enter from the same side.
        """
        waypoints = [(x1, y1)]
        exclude_nodes = {source, target}

        # Get exit lane number and increment counter
        exit_lane = self.exit_counts[(source, src_side)]
        self.exit_counts[(source, src_side)] += 1

        # Get entry lane number and increment counter
        entry_lane = self.entry_counts[(target, tgt_side)]
        self.entry_counts[(target, tgt_side)] += 1

        # Base offset plus lane offset for separation
        exit_offset = MIN_SEGMENT_LENGTH + (exit_lane * MIN_EDGE_SEPARATION)
        entry_offset = MIN_SEGMENT_LENGTH + (entry_lane * MIN_EDGE_SEPARATION)

        # Calculate first waypoint (exit from source)
        if src_side == "right":
            wp1 = (x1 + exit_offset, y1)
        elif src_side == "left":
            wp1 = (x1 - exit_offset, y1)
        elif src_side == "bottom":
            wp1 = (x1, y1 + exit_offset)
        else:  # top
            wp1 = (x1, y1 - exit_offset)

        # Calculate last waypoint before target (entry to target)
        if tgt_side == "left":
            wp_entry = (x2 - entry_offset, y2)
        elif tgt_side == "right":
            wp_entry = (x2 + entry_offset, y2)
        elif tgt_side == "top":
            wp_entry = (x2, y2 - entry_offset)
        else:  # bottom
            wp_entry = (x2, y2 + entry_offset)

        waypoints.append(wp1)

        # Route from wp1 to wp_entry
        # Try to find a clear orthogonal path
        path_waypoints = self._find_orthogonal_path(
            wp1[0], wp1[1], wp_entry[0], wp_entry[1], src_side, tgt_side, exclude_nodes
        )

        waypoints.extend(path_waypoints)
        waypoints.append(wp_entry)
        waypoints.append((x2, y2))

        return self._simplify_waypoints(waypoints)

    def _find_orthogonal_path(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        src_side: str,
        tgt_side: str,
        exclude_nodes: Set[str],
    ) -> List[Tuple[int, int]]:
        """Find orthogonal path between two points, avoiding boxes."""
        waypoints = []

        # Determine if we start horizontal or vertical
        start_horizontal = src_side in ("left", "right")
        end_horizontal = tgt_side in ("left", "right")

        if start_horizontal and end_horizontal:
            # Both horizontal: need vertical segment in between
            # But first check if y1 == y2 and that horizontal line is already used
            if y1 == y2:
                # Direct horizontal path - check if it overlaps existing edges
                if self._horizontal_overlaps_existing(y1, min(x1, x2), max(x1, x2)):
                    # Need to offset to avoid overlap - route around
                    offset_y = self._find_clear_horizontal_y(
                        y1 - MIN_EDGE_SEPARATION * 2,
                        y1 + MIN_EDGE_SEPARATION * 2,
                        min(x1, x2),
                        max(x1, x2),
                        exclude_nodes,
                    )
                    mid_x = (x1 + x2) // 2
                    waypoints.append((mid_x, y1))
                    waypoints.append((mid_x, offset_y))
                    waypoints.append((x2, offset_y))
                else:
                    # No overlap, can use direct path (will be simplified)
                    mid_x = self._find_clear_vertical_x(x1, x2, y1, y1, exclude_nodes)
                    if x1 != mid_x:
                        waypoints.append((mid_x, y1))
            else:
                mid_x = self._find_clear_vertical_x(
                    x1, x2, min(y1, y2), max(y1, y2), exclude_nodes
                )
                if x1 != mid_x:
                    waypoints.append((mid_x, y1))
                waypoints.append((mid_x, y2))

        elif not start_horizontal and not end_horizontal:
            # Both vertical: need horizontal segment in between
            # But first check if x1 == x2 and that vertical line is already used
            if x1 == x2:
                # Direct vertical path - check if it overlaps existing edges
                if self._vertical_overlaps_existing(x1, min(y1, y2), max(y1, y2)):
                    # Need to offset to avoid overlap - route around
                    offset_x = self._find_clear_vertical_x(
                        x1 - MIN_EDGE_SEPARATION * 2,
                        x1 + MIN_EDGE_SEPARATION * 2,
                        min(y1, y2),
                        max(y1, y2),
                        exclude_nodes,
                    )
                    mid_y = (y1 + y2) // 2
                    waypoints.append((x1, mid_y))
                    waypoints.append((offset_x, mid_y))
                    waypoints.append((offset_x, y2))
                else:
                    # No overlap, can use direct path (will be simplified)
                    mid_y = self._find_clear_horizontal_y(y1, y2, x1, x1, exclude_nodes)
                    if y1 != mid_y:
                        waypoints.append((x1, mid_y))
            else:
                mid_y = self._find_clear_horizontal_y(
                    y1, y2, min(x1, x2), max(x1, x2), exclude_nodes
                )
                if y1 != mid_y:
                    waypoints.append((x1, mid_y))
                waypoints.append((x2, mid_y))

        elif start_horizontal and not end_horizontal:
            # Start horizontal, end vertical: L-shape
            # Go horizontal to x2, then vertical to y2
            if not self.grid.line_intersects_box(x1, y1, x2, y1, exclude_nodes):
                waypoints.append((x2, y1))
            else:
                # Need to go around
                mid_y = self._find_clear_horizontal_y(
                    y1, y2, min(x1, x2), max(x1, x2), exclude_nodes
                )
                waypoints.append((x1, mid_y))
                waypoints.append((x2, mid_y))

        else:
            # Start vertical, end horizontal: L-shape
            if not self.grid.line_intersects_box(x1, y1, x1, y2, exclude_nodes):
                waypoints.append((x1, y2))
            else:
                mid_x = self._find_clear_vertical_x(
                    x1, x2, min(y1, y2), max(y1, y2), exclude_nodes
                )
                waypoints.append((mid_x, y1))
                waypoints.append((mid_x, y2))

        return waypoints

    def _find_clear_vertical_x(
        self, x1: int, x2: int, y_min: int, y_max: int, exclude_nodes: Set[str]
    ) -> int:
        """Find a clear x-coordinate for a vertical segment."""
        # Try the midpoint first
        mid_x = (x1 + x2) // 2

        # Check if midpoint path is clear (no boxes AND no overlapping edges)
        if not self._vertical_line_blocked(mid_x, y_min, y_max, exclude_nodes):
            if not self._vertical_overlaps_existing(mid_x, y_min, y_max):
                return mid_x

        # Try positions between x1 and x2
        step = MIN_EDGE_SEPARATION
        search_range = max(abs(x2 - x1) // 2, 100)  # Search wider if needed

        for offset in range(step, search_range, step):
            # Try left of midpoint
            test_x = mid_x - offset
            if not self._vertical_line_blocked(test_x, y_min, y_max, exclude_nodes):
                if not self._vertical_overlaps_existing(test_x, y_min, y_max):
                    return test_x

            # Try right of midpoint
            test_x = mid_x + offset
            if not self._vertical_line_blocked(test_x, y_min, y_max, exclude_nodes):
                if not self._vertical_overlaps_existing(test_x, y_min, y_max):
                    return test_x

        # Fallback to offset from midpoint to avoid overlap
        return mid_x + MIN_EDGE_SEPARATION * len(self.used_vertical_segments)

    def _find_clear_horizontal_y(
        self, y1: int, y2: int, x_min: int, x_max: int, exclude_nodes: Set[str]
    ) -> int:
        """Find a clear y-coordinate for a horizontal segment."""
        mid_y = (y1 + y2) // 2

        # Check if midpoint is clear (no boxes AND no overlapping edges)
        if not self._horizontal_line_blocked(mid_y, x_min, x_max, exclude_nodes):
            if not self._horizontal_overlaps_existing(mid_y, x_min, x_max):
                return mid_y

        step = MIN_EDGE_SEPARATION
        search_range = max(abs(y2 - y1) // 2, 100)  # Search wider if needed

        for offset in range(step, search_range, step):
            test_y = mid_y - offset
            if not self._horizontal_line_blocked(test_y, x_min, x_max, exclude_nodes):
                if not self._horizontal_overlaps_existing(test_y, x_min, x_max):
                    return test_y

            test_y = mid_y + offset
            if not self._horizontal_line_blocked(test_y, x_min, x_max, exclude_nodes):
                if not self._horizontal_overlaps_existing(test_y, x_min, x_max):
                    return test_y

        # Fallback to offset from midpoint to avoid overlap
        return mid_y + MIN_EDGE_SEPARATION * len(self.used_horizontal_segments)

    def _vertical_line_blocked(
        self, x: int, y_min: int, y_max: int, exclude_nodes: Set[str]
    ) -> bool:
        """Check if a vertical line is blocked by or too close to boxes."""
        clearance = MIN_BOX_CLEARANCE
        for node, bounds in self.box_bounds.items():
            if node in exclude_nodes:
                continue
            # Check if line passes through box OR is too close to it
            # Line is too close if it's within clearance distance of box edges
            if (bounds.x - clearance) < x < (bounds.x2 + clearance):
                if not (y_max < bounds.y or y_min > bounds.y2):
                    return True
        return False

    def _horizontal_line_blocked(
        self, y: int, x_min: int, x_max: int, exclude_nodes: Set[str]
    ) -> bool:
        """Check if a horizontal line is blocked by or too close to boxes."""
        clearance = MIN_BOX_CLEARANCE
        for node, bounds in self.box_bounds.items():
            if node in exclude_nodes:
                continue
            # Check if line passes through box OR is too close to it
            if (bounds.y - clearance) < y < (bounds.y2 + clearance):
                if not (x_max < bounds.x or x_min > bounds.x2):
                    return True
        return False

    def _mark_route(self, waypoints: List[Tuple[int, int]]):
        """Mark the route in the occupancy grid and track segments."""
        for i in range(len(waypoints) - 1):
            x1, y1 = waypoints[i]
            x2, y2 = waypoints[i + 1]
            self.grid.mark_edge_segment(x1, y1, x2, y2)

            # Track segments for overlap prevention
            if x1 == x2:  # Vertical segment
                self.used_vertical_segments.append((x1, min(y1, y2), max(y1, y2)))
            elif y1 == y2:  # Horizontal segment
                self.used_horizontal_segments.append((y1, min(x1, x2), max(x1, x2)))

    def _vertical_overlaps_existing(self, x: int, y_min: int, y_max: int) -> bool:
        """Check if a vertical segment would overlap with existing edges."""
        sep = MIN_EDGE_SEPARATION
        for ex, ey_min, ey_max in self.used_vertical_segments:
            # Check if x is too close to existing segment's x
            if abs(x - ex) < sep:
                # Check if y ranges overlap
                if not (y_max < ey_min or y_min > ey_max):
                    return True
        return False

    def _horizontal_overlaps_existing(self, y: int, x_min: int, x_max: int) -> bool:
        """Check if a horizontal segment would overlap with existing edges."""
        sep = MIN_EDGE_SEPARATION
        for ey, ex_min, ex_max in self.used_horizontal_segments:
            # Check if y is too close to existing segment's y
            if abs(y - ey) < sep:
                # Check if x ranges overlap
                if not (x_max < ex_min or x_min > ex_max):
                    return True
        return False

    def _simplify_waypoints(
        self, waypoints: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """Remove redundant collinear waypoints."""
        if len(waypoints) <= 2:
            return waypoints

        simplified = [waypoints[0]]

        for i in range(1, len(waypoints) - 1):
            prev = simplified[-1]
            curr = waypoints[i]
            next_pt = waypoints[i + 1]

            # Check if curr is collinear with prev and next
            same_x = prev[0] == curr[0] == next_pt[0]
            same_y = prev[1] == curr[1] == next_pt[1]

            if not (same_x or same_y):
                simplified.append(curr)

        simplified.append(waypoints[-1])

        # Remove duplicate consecutive points
        final = [simplified[0]]
        for pt in simplified[1:]:
            if pt != final[-1]:
                final.append(pt)

        return final

    def remove_route(self, route: EdgeRoute) -> bool:
        """
        Remove a route and undo its state changes.

        Args:
            route: The EdgeRoute to remove

        Returns:
            True if route was removed, False if not found
        """
        if route not in self.routes:
            return False

        # Remove from routes list
        self.routes.remove(route)

        # Undo port usage tracking
        src_port = route.source_port
        tgt_port = route.target_port

        src_usage = self.port_manager.port_usage[src_port.node][src_port.side]
        if src_port.position in src_usage:
            src_usage.remove(src_port.position)
            src_port.in_use = False

        tgt_usage = self.port_manager.port_usage[tgt_port.node][tgt_port.side]
        if tgt_port.position in tgt_usage:
            tgt_usage.remove(tgt_port.position)
            tgt_port.in_use = False

        # Undo exit/entry counts
        exit_key = (route.source, src_port.side)
        if self.exit_counts[exit_key] > 0:
            self.exit_counts[exit_key] -= 1

        entry_key = (route.target, tgt_port.side)
        if self.entry_counts[entry_key] > 0:
            self.entry_counts[entry_key] -= 1

        # Remove edge segments from tracking lists and grid
        waypoints = route.waypoints
        for i in range(len(waypoints) - 1):
            x1, y1 = waypoints[i]
            x2, y2 = waypoints[i + 1]

            if x1 == x2:  # Vertical segment
                seg = (x1, min(y1, y2), max(y1, y2))
                if seg in self.used_vertical_segments:
                    self.used_vertical_segments.remove(seg)
            elif y1 == y2:  # Horizontal segment
                seg = (y1, min(x1, x2), max(x1, x2))
                if seg in self.used_horizontal_segments:
                    self.used_horizontal_segments.remove(seg)

            # Clear edge cells from grid (but not box cells)
            self._clear_edge_segment(x1, y1, x2, y2)

        return True

    def _clear_edge_segment(self, x1: int, y1: int, x2: int, y2: int):
        """Clear edge cells from the grid for a segment."""
        if x1 == x2:  # Vertical line
            for y in range(min(y1, y2), max(y1, y2) + 1):
                cell = (x1, y)
                cell_type = self.grid.cells.get(cell)
                if cell_type in (CellType.VERTICAL_EDGE, CellType.HORIZONTAL_EDGE):
                    del self.grid.cells[cell]
                elif cell_type == CellType.JUNCTION:
                    # Downgrade junction to the other edge type
                    self.grid.cells[cell] = CellType.HORIZONTAL_EDGE
        elif y1 == y2:  # Horizontal line
            for x in range(min(x1, x2), max(x1, x2) + 1):
                cell = (x, y1)
                cell_type = self.grid.cells.get(cell)
                if cell_type in (CellType.HORIZONTAL_EDGE, CellType.VERTICAL_EDGE):
                    del self.grid.cells[cell]
                elif cell_type == CellType.JUNCTION:
                    self.grid.cells[cell] = CellType.VERTICAL_EDGE

    def score_layout(self) -> float:
        """
        Calculate a global quality score for the current layout.

        Lower scores are better. Considers:
        - Total wire length
        - Number of bends/turns
        - Edge crossings
        - Proximity to boxes

        Returns:
            Float score (lower is better)
        """
        if not self.routes:
            return 0.0

        score = 0.0

        for route in self.routes:
            # Wire length penalty
            wire_length = self._calculate_wire_length(route.waypoints)
            score += wire_length * WIRE_LENGTH_WEIGHT

            # Bend penalty - count turns in the path
            num_bends = self._count_bends(route.waypoints)
            score += num_bends * TURN_PENALTY

            # Proximity to boxes penalty
            proximity_penalty = self._calculate_proximity_penalty(
                route.waypoints, route.source, route.target
            )
            score += proximity_penalty

        # Edge crossing penalty
        crossing_count = self._count_edge_crossings()
        score += crossing_count * CROSSING_PENALTY

        # Edge overlap/congestion penalty
        congestion = self._calculate_congestion()
        score += congestion * CONGESTION_PENALTY

        return score

    def _calculate_wire_length(self, waypoints: List[Tuple[int, int]]) -> float:
        """Calculate total wire length for a path."""
        length = 0.0
        for i in range(len(waypoints) - 1):
            x1, y1 = waypoints[i]
            x2, y2 = waypoints[i + 1]
            length += abs(x2 - x1) + abs(y2 - y1)
        return length

    def _count_bends(self, waypoints: List[Tuple[int, int]]) -> int:
        """Count the number of bends/turns in a path."""
        if len(waypoints) < 3:
            return 0

        bends = 0
        for i in range(1, len(waypoints) - 1):
            prev = waypoints[i - 1]
            curr = waypoints[i]
            next_pt = waypoints[i + 1]

            # Check if direction changes
            prev_horizontal = prev[1] == curr[1]
            next_horizontal = curr[1] == next_pt[1]

            if prev_horizontal != next_horizontal:
                bends += 1

        return bends

    def _calculate_proximity_penalty(
        self,
        waypoints: List[Tuple[int, int]],
        source: str,
        target: str,
    ) -> float:
        """Calculate penalty for edges passing too close to boxes."""
        penalty = 0.0
        exclude_nodes = {source, target}
        clearance = MIN_BOX_CLEARANCE // 2  # Check for half-clearance violations

        for i in range(len(waypoints) - 1):
            x1, y1 = waypoints[i]
            x2, y2 = waypoints[i + 1]

            for node, bounds in self.box_bounds.items():
                if node in exclude_nodes:
                    continue

                # Check proximity for vertical segments
                if x1 == x2:
                    dist_to_box = min(abs(x1 - bounds.x), abs(x1 - bounds.x2))
                    if dist_to_box < clearance:
                        # Check if y range overlaps with box
                        y_min, y_max = min(y1, y2), max(y1, y2)
                        if not (y_max < bounds.y or y_min > bounds.y2):
                            penalty += (
                                clearance - dist_to_box
                            ) * PROXIMITY_PENALTY_MULTIPLIER

                # Check proximity for horizontal segments
                elif y1 == y2:
                    dist_to_box = min(abs(y1 - bounds.y), abs(y1 - bounds.y2))
                    if dist_to_box < clearance:
                        x_min, x_max = min(x1, x2), max(x1, x2)
                        if not (x_max < bounds.x or x_min > bounds.x2):
                            penalty += (
                                clearance - dist_to_box
                            ) * PROXIMITY_PENALTY_MULTIPLIER

        return penalty

    def _count_edge_crossings(self) -> int:
        """Count the number of edge crossings in the layout."""
        crossings = 0

        # Collect all segments
        h_segments = []  # (y, x_min, x_max, route_idx)
        v_segments = []  # (x, y_min, y_max, route_idx)

        for route_idx, route in enumerate(self.routes):
            waypoints = route.waypoints
            for i in range(len(waypoints) - 1):
                x1, y1 = waypoints[i]
                x2, y2 = waypoints[i + 1]

                if x1 == x2:  # Vertical
                    v_segments.append((x1, min(y1, y2), max(y1, y2), route_idx))
                elif y1 == y2:  # Horizontal
                    h_segments.append((y1, min(x1, x2), max(x1, x2), route_idx))

        # Check for crossings between horizontal and vertical segments
        for h_y, h_x_min, h_x_max, h_idx in h_segments:
            for v_x, v_y_min, v_y_max, v_idx in v_segments:
                if h_idx == v_idx:
                    continue  # Same route, not a crossing

                # Check if they intersect
                if h_x_min < v_x < h_x_max and v_y_min < h_y < v_y_max:
                    crossings += 1

        return crossings

    def _calculate_congestion(self) -> float:
        """Calculate congestion penalty for edges running close together."""
        congestion = 0.0
        sep = MIN_EDGE_SEPARATION

        # Check vertical segment congestion
        for i, (x1, y1_min, y1_max) in enumerate(self.used_vertical_segments):
            for x2, y2_min, y2_max in self.used_vertical_segments[i + 1 :]:
                if abs(x1 - x2) < sep:
                    # Check y overlap
                    overlap = min(y1_max, y2_max) - max(y1_min, y2_min)
                    if overlap > 0:
                        congestion += overlap * (sep - abs(x1 - x2)) / sep

        # Check horizontal segment congestion
        for i, (y1, x1_min, x1_max) in enumerate(self.used_horizontal_segments):
            for y2, x2_min, x2_max in self.used_horizontal_segments[i + 1 :]:
                if abs(y1 - y2) < sep:
                    overlap = min(x1_max, x2_max) - max(x1_min, x2_min)
                    if overlap > 0:
                        congestion += overlap * (sep - abs(y1 - y2)) / sep

        return congestion

    def refine_routes(self, max_iterations: int = 10) -> Tuple[float, int]:
        """
        Iteratively refine routes to find a better global layout.

        For each edge, tries alternative side combinations and keeps
        improvements. Repeats until no improvement is found or max
        iterations reached.

        Args:
            max_iterations: Maximum refinement passes over all edges

        Returns:
            Tuple of (final_score, iterations_performed)
        """
        if len(self.routes) < 2:
            # Nothing to refine with 0 or 1 edges
            return self.score_layout(), 0

        best_score = self.score_layout()
        iterations = 0

        for iteration in range(max_iterations):
            improved = False
            iterations += 1

            # Try to improve each route
            for route_idx in range(len(self.routes)):
                route = self.routes[route_idx]
                source = route.source
                target = route.target
                is_bidirectional = route.is_bidirectional

                # Get alternative side options (skip the current best which is index 0)
                side_options = self._get_all_side_options(source, target)

                # Current sides being used
                current_src_side = route.source_port.side
                current_tgt_side = route.target_port.side

                # Try top alternative side combinations
                for src_side, tgt_side, _ in side_options[:6]:  # Try top 6 alternatives
                    if src_side == current_src_side and tgt_side == current_tgt_side:
                        continue  # Skip current configuration

                    # Remove current route
                    self.remove_route(route)

                    # Try new routing with specified sides
                    new_route = self._route_edge_with_sides(
                        source, target, src_side, tgt_side, is_bidirectional
                    )

                    if new_route:
                        new_score = self.score_layout()

                        if new_score < best_score:
                            # Keep the improvement
                            best_score = new_score
                            route = new_route
                            current_src_side = src_side
                            current_tgt_side = tgt_side
                            improved = True
                        else:
                            # Revert - remove new route and restore original
                            self.remove_route(new_route)
                            restored = self._route_edge_with_sides(
                                source,
                                target,
                                current_src_side,
                                current_tgt_side,
                                is_bidirectional,
                            )
                            if restored:
                                route = restored
                    else:
                        # Routing failed, restore original
                        restored = self._route_edge_with_sides(
                            source,
                            target,
                            current_src_side,
                            current_tgt_side,
                            is_bidirectional,
                        )
                        if restored:
                            route = restored

            if not improved:
                break

        return best_score, iterations

    def _route_edge_with_sides(
        self,
        source: str,
        target: str,
        src_side: str,
        tgt_side: str,
        is_bidirectional: bool = False,
    ) -> Optional[EdgeRoute]:
        """
        Route an edge using specific source and target sides.

        Args:
            source: Source node name
            target: Target node name
            src_side: Side of source box to use
            tgt_side: Side of target box to use
            is_bidirectional: Whether edge is bidirectional

        Returns:
            EdgeRoute if successful, None otherwise
        """
        if source not in self.box_bounds or target not in self.box_bounds:
            return None

        src_bounds = self.box_bounds[source]
        tgt_bounds = self.box_bounds[target]

        # Get appropriate ports for specified sides
        is_src_horizontal = src_side in ("top", "bottom")
        is_tgt_horizontal = tgt_side in ("top", "bottom")

        src_port = self.port_manager.get_available_port(
            source,
            src_side,
            tgt_bounds.center_x if is_src_horizontal else tgt_bounds.center_y,
            is_src_horizontal,
        )
        if not src_port:
            return None

        tgt_port = self.port_manager.get_available_port(
            target,
            tgt_side,
            src_bounds.center_x if is_tgt_horizontal else src_bounds.center_y,
            is_tgt_horizontal,
        )
        if not tgt_port:
            # Release the source port we claimed since routing failed
            self._release_port(src_port)
            return None

        # Route the path
        waypoints = self._route_path(
            src_port.x,
            src_port.y,
            tgt_port.x,
            tgt_port.y,
            src_side,
            tgt_side,
            source,
            target,
        )

        # Mark the route in the grid
        self._mark_route(waypoints)

        route = EdgeRoute(
            source=source,
            target=target,
            source_port=src_port,
            target_port=tgt_port,
            waypoints=waypoints,
            is_bidirectional=is_bidirectional,
        )
        self.routes.append(route)
        return route


def create_router(
    node_positions: Dict[str, Tuple[int, int, int, int]],
    grid_margin: int = 50,
) -> Tuple[OccupancyGrid, PortManager, OrthogonalRouter]:
    """
    Create a complete routing system for the given node positions.

    Args:
        node_positions: Dict mapping node name to (x, y, width, height)
        grid_margin: Extra margin around the grid

    Returns:
        (grid, port_manager, router) tuple
    """
    if not node_positions:
        # Handle empty case
        grid = OccupancyGrid(100, 100)
        port_manager = PortManager()
        router = OrthogonalRouter(grid, port_manager, {})
        return grid, port_manager, router

    # Calculate grid dimensions
    max_x = max(x + w for x, y, w, h in node_positions.values()) + grid_margin
    max_y = max(y + h for x, y, w, h in node_positions.values()) + grid_margin

    # Create grid
    grid = OccupancyGrid(max_x, max_y)

    # Create port manager
    port_manager = PortManager()

    # Create box bounds and mark boxes in grid
    box_bounds: Dict[str, BoxBounds] = {}
    for node, (x, y, w, h) in node_positions.items():
        bounds = BoxBounds(x, y, w, h)
        box_bounds[node] = bounds
        grid.mark_box(node, bounds, margin=BOX_MARGIN)
        port_manager.create_ports_for_box(node, bounds)

    # Create router
    router = OrthogonalRouter(grid, port_manager, box_bounds)

    return grid, port_manager, router


def route_edges_with_refinement(
    node_positions: Dict[str, Tuple[int, int, int, int]],
    edges: List[Tuple[str, str, bool]],
    refine: bool = True,
    max_iterations: int = 10,
) -> Tuple[List[EdgeRoute], float]:
    """
    Route all edges with optional iterative refinement.

    This is a convenience function that:
    1. Creates the routing infrastructure
    2. Routes all edges using the greedy algorithm
    3. Optionally refines routes to improve global layout quality

    Args:
        node_positions: Dict mapping node name to (x, y, width, height)
        edges: List of (source, target, is_bidirectional) tuples
        refine: Whether to run iterative refinement (default True)
        max_iterations: Max refinement iterations (default 10)

    Returns:
        Tuple of (list of EdgeRoute objects, final layout score)

    Example:
        >>> positions = {"A": (0, 0, 100, 50), "B": (200, 0, 100, 50)}
        >>> edges = [("A", "B", False)]
        >>> routes, score = route_edges_with_refinement(positions, edges)
    """
    _, _, router = create_router(node_positions)

    # Route all edges
    for source, target, is_bidirectional in edges:
        router.route_edge(source, target, is_bidirectional)

    # Optionally refine
    if refine and len(router.routes) >= 2:
        router.refine_routes(max_iterations)

    return router.routes, router.score_layout()
