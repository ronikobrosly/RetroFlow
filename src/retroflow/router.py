"""
Edge routing module for flowchart generation.

Handles orthogonal routing of edges between boxes with:
- Port assignment (where edges connect to boxes)
- Non-overlapping edge paths
- Minimal crossings
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class PortSide(Enum):
    """Which side of a box a port is on."""

    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


@dataclass
class Port:
    """A connection point on a box."""

    node: str
    side: PortSide
    offset: int  # Offset from left/top of box
    x: int = 0  # Absolute x coordinate
    y: int = 0  # Absolute y coordinate


@dataclass
class BoxInfo:
    """Information about a rendered box."""

    name: str
    x: int
    y: int
    width: int
    height: int
    layer: int
    position: int


@dataclass
class EdgeRoute:
    """A routed edge between two boxes."""

    source: str
    target: str
    source_port: Port
    target_port: Port
    waypoints: List[Tuple[int, int]] = field(default_factory=list)


class EdgeRouter:
    """
    Routes edges between boxes using orthogonal paths.
    """

    def __init__(self):
        self.boxes: Dict[str, BoxInfo] = {}
        self.used_ports: Dict[str, Dict[PortSide, Set[int]]] = {}

    def set_boxes(self, boxes: Dict[str, BoxInfo]) -> None:
        """Set the box information for routing."""
        self.boxes = boxes
        self.used_ports = {name: {side: set() for side in PortSide} for name in boxes}

    def route_edges(
        self, edges: List[Tuple[str, str]], layers: List[List[str]]
    ) -> List[EdgeRoute]:
        """
        Route all edges between boxes.

        Args:
            edges: List of (source, target) node pairs
            layers: List of layers, each containing node names

        Returns:
            List of EdgeRoute objects with routing information
        """
        routes: List[EdgeRoute] = []

        # Build layer lookup
        node_layer = {}
        node_position = {}
        for layer_idx, layer in enumerate(layers):
            for pos_idx, node in enumerate(layer):
                node_layer[node] = layer_idx
                node_position[node] = pos_idx

        # Group edges by source for port allocation
        edges_by_source: Dict[str, List[str]] = {}
        edges_by_target: Dict[str, List[str]] = {}

        for source, target in edges:
            if source not in edges_by_source:
                edges_by_source[source] = []
            edges_by_source[source].append(target)

            if target not in edges_by_target:
                edges_by_target[target] = []
            edges_by_target[target].append(source)

        # Sort edges by target position for consistent port allocation
        for source in edges_by_source:
            edges_by_source[source].sort(key=lambda t: node_position.get(t, 0))

        for target in edges_by_target:
            edges_by_target[target].sort(key=lambda s: node_position.get(s, 0))

        # Route each edge
        for source, target in edges:
            # Skip dummy nodes - they're handled in the path
            if source.startswith("__dummy_") or target.startswith("__dummy_"):
                # For dummy nodes, we just pass through
                route = self._route_through_dummy(
                    source, target, node_layer, node_position, edges
                )
            else:
                route = self._route_edge(
                    source,
                    target,
                    node_layer,
                    node_position,
                    edges_by_source.get(source, []),
                    edges_by_target.get(target, []),
                )

            if route:
                routes.append(route)

        return routes

    def _route_edge(
        self,
        source: str,
        target: str,
        node_layer: Dict[str, int],
        node_position: Dict[str, int],
        source_targets: List[str],
        target_sources: List[str],
    ) -> Optional[EdgeRoute]:
        """Route a single edge between two boxes."""
        if source not in self.boxes or target not in self.boxes:
            return None

        src_box = self.boxes[source]
        tgt_box = self.boxes[target]

        src_layer = node_layer.get(source, 0)
        tgt_layer = node_layer.get(target, 0)

        # Determine port sides based on relative layer positions
        if tgt_layer > src_layer:
            # Target is below source - standard downward flow
            src_side = PortSide.BOTTOM
            tgt_side = PortSide.TOP
        elif tgt_layer < src_layer:
            # Target is above source - upward flow (back edge)
            src_side = PortSide.TOP
            tgt_side = PortSide.BOTTOM
        else:
            # Same layer - horizontal flow
            if node_position.get(target, 0) > node_position.get(source, 0):
                src_side = PortSide.RIGHT
                tgt_side = PortSide.LEFT
            else:
                src_side = PortSide.LEFT
                tgt_side = PortSide.RIGHT

        # Allocate ports
        src_port = self._allocate_port(
            source,
            src_side,
            src_box,
            source_targets.index(target) if target in source_targets else 0,
            len(source_targets),
        )
        tgt_port = self._allocate_port(
            target,
            tgt_side,
            tgt_box,
            target_sources.index(source) if source in target_sources else 0,
            len(target_sources),
        )

        # Calculate waypoints for orthogonal routing
        waypoints = self._calculate_waypoints(src_port, tgt_port, src_box, tgt_box)

        return EdgeRoute(
            source=source,
            target=target,
            source_port=src_port,
            target_port=tgt_port,
            waypoints=waypoints,
        )

    def _route_through_dummy(
        self,
        source: str,
        target: str,
        node_layer: Dict[str, int],
        node_position: Dict[str, int],
        all_edges: List[Tuple[str, str]],
    ) -> Optional[EdgeRoute]:
        """Handle routing through dummy nodes."""
        # For dummy nodes, just create straight vertical segments
        if source not in self.boxes or target not in self.boxes:
            return None

        src_box = self.boxes[source]
        tgt_box = self.boxes[target]

        src_layer = node_layer.get(source, 0)
        tgt_layer = node_layer.get(target, 0)

        if tgt_layer > src_layer:
            src_side = PortSide.BOTTOM
            tgt_side = PortSide.TOP
        else:
            src_side = PortSide.TOP
            tgt_side = PortSide.BOTTOM

        src_port = Port(
            node=source,
            side=src_side,
            offset=0,
            x=src_box.x + src_box.width // 2,
            y=src_box.y + src_box.height if src_side == PortSide.BOTTOM else src_box.y,
        )

        tgt_port = Port(
            node=target,
            side=tgt_side,
            offset=0,
            x=tgt_box.x + tgt_box.width // 2,
            y=tgt_box.y if tgt_side == PortSide.TOP else tgt_box.y + tgt_box.height,
        )

        return EdgeRoute(
            source=source,
            target=target,
            source_port=src_port,
            target_port=tgt_port,
            waypoints=[(src_port.x, src_port.y), (tgt_port.x, tgt_port.y)],
        )

    def _allocate_port(
        self, node: str, side: PortSide, box: BoxInfo, index: int, total: int
    ) -> Port:
        """
        Allocate a port on a box side, distributing ports evenly.
        For bottom ports, y is at the bottom border (box.y + box.height - 1).
        For top ports, y is at the top border (box.y).
        """
        if side in (PortSide.TOP, PortSide.BOTTOM):
            # Distribute horizontally across the box width
            available_width = box.width - 2  # Exclude corners
            if total == 1:
                offset = available_width // 2
            else:
                spacing = available_width // (total + 1)
                offset = spacing * (index + 1)

            x = box.x + 1 + offset
            # Bottom port at the bottom border, top port at top border
            if side == PortSide.BOTTOM:
                y = box.y + box.height - 1  # At bottom border
            else:
                y = box.y  # At top border

        else:  # LEFT or RIGHT
            # Distribute vertically
            available_height = box.height - 2  # Exclude corners
            if total == 1:
                offset = available_height // 2
            else:
                spacing = available_height // (total + 1)
                offset = spacing * (index + 1)

            x = box.x if side == PortSide.LEFT else box.x + box.width - 1
            y = box.y + 1 + offset

        # Track used port
        self.used_ports[node][side].add(offset)

        return Port(node=node, side=side, offset=offset, x=x, y=y)

    def _calculate_waypoints(
        self, src_port: Port, tgt_port: Port, src_box: BoxInfo, tgt_box: BoxInfo
    ) -> List[Tuple[int, int]]:
        """
        Calculate waypoints for orthogonal edge routing.
        Returns list of (x, y) coordinates for the path.
        """
        waypoints = [(src_port.x, src_port.y)]

        src_x, src_y = src_port.x, src_port.y
        tgt_x, tgt_y = tgt_port.x, tgt_port.y

        if src_port.side == PortSide.BOTTOM and tgt_port.side == PortSide.TOP:
            # Standard downward flow
            if src_x == tgt_x:
                # Direct vertical line
                waypoints.append((tgt_x, tgt_y))
            else:
                # Need horizontal segment in between
                mid_y = src_y + (tgt_y - src_y) // 2
                waypoints.append((src_x, mid_y))
                waypoints.append((tgt_x, mid_y))
                waypoints.append((tgt_x, tgt_y))

        elif src_port.side == PortSide.TOP and tgt_port.side == PortSide.BOTTOM:
            # Upward flow (back edge)
            # Route around the side
            if src_x == tgt_x:
                waypoints.append((tgt_x, tgt_y))
            else:
                mid_y = src_y - 2
                waypoints.append((src_x, mid_y))
                waypoints.append((tgt_x, mid_y))
                waypoints.append((tgt_x, tgt_y))

        elif src_port.side in (PortSide.LEFT, PortSide.RIGHT):
            # Horizontal flow
            if src_y == tgt_y:
                waypoints.append((tgt_x, tgt_y))
            else:
                mid_x = src_x + (tgt_x - src_x) // 2
                waypoints.append((mid_x, src_y))
                waypoints.append((mid_x, tgt_y))
                waypoints.append((tgt_x, tgt_y))

        else:
            # Default: direct path
            waypoints.append((tgt_x, tgt_y))

        return waypoints
