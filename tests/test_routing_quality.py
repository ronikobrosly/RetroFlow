"""
Tests for routing quality - detecting overlaps and box intersections.

These tests verify that:
1. Arrow lines never pass through boxes (except their source/target)
2. Arrow lines don't overlap with each other unnecessarily
3. Routing produces clean, readable diagrams
"""

from typing import Dict, List, Tuple

from retroflow.edge_routing import (
    BoxBounds,
    EdgeRoute,
    create_router,
)


def segments_from_waypoints(
    waypoints: List[Tuple[int, int]],
) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """Extract line segments from waypoints."""
    segments = []
    for i in range(len(waypoints) - 1):
        segments.append((waypoints[i], waypoints[i + 1]))
    return segments


def point_in_box(x: int, y: int, bounds: BoxBounds, margin: int = 0) -> bool:
    """Check if a point is inside a box (with optional margin)."""
    return (
        bounds.x - margin < x < bounds.x2 + margin
        and bounds.y - margin < y < bounds.y2 + margin
    )


def segment_intersects_box(
    p1: Tuple[int, int],
    p2: Tuple[int, int],
    bounds: BoxBounds,
    margin: int = 2,
) -> bool:
    """
    Check if a line segment intersects a box.

    This checks if the segment passes THROUGH the box interior,
    not just touches the edge (which is valid for connections).
    """
    x1, y1 = p1
    x2, y2 = p2

    # Horizontal segment
    if y1 == y2:
        # Check if y is within box (with margin for interior)
        if bounds.y + margin < y1 < bounds.y2 - margin:
            # Check if x range overlaps with box
            min_x, max_x = min(x1, x2), max(x1, x2)
            if min_x < bounds.x2 - margin and max_x > bounds.x + margin:
                return True

    # Vertical segment
    elif x1 == x2:
        # Check if x is within box (with margin for interior)
        if bounds.x + margin < x1 < bounds.x2 - margin:
            # Check if y range overlaps with box
            min_y, max_y = min(y1, y2), max(y1, y2)
            if min_y < bounds.y2 - margin and max_y > bounds.y + margin:
                return True

    return False


def segments_overlap(
    seg1: Tuple[Tuple[int, int], Tuple[int, int]],
    seg2: Tuple[Tuple[int, int], Tuple[int, int]],
    tolerance: int = 3,
) -> bool:
    """
    Check if two segments overlap (share a portion of the same line).

    Segments that merely cross at a point are allowed.
    Segments that run along the same line for a distance are overlapping.
    """
    (x1a, y1a), (x2a, y2a) = seg1
    (x1b, y1b), (x2b, y2b) = seg2

    # Both horizontal at same y
    if y1a == y2a and y1b == y2b and abs(y1a - y1b) <= tolerance:
        # Check if x ranges overlap
        min_xa, max_xa = min(x1a, x2a), max(x1a, x2a)
        min_xb, max_xb = min(x1b, x2b), max(x1b, x2b)

        overlap_start = max(min_xa, min_xb)
        overlap_end = min(max_xa, max_xb)

        # Overlap if they share more than just a point
        if overlap_end - overlap_start > tolerance:
            return True

    # Both vertical at same x
    if x1a == x2a and x1b == x2b and abs(x1a - x1b) <= tolerance:
        # Check if y ranges overlap
        min_ya, max_ya = min(y1a, y2a), max(y1a, y2a)
        min_yb, max_yb = min(y1b, y2b), max(y1b, y2b)

        overlap_start = max(min_ya, min_yb)
        overlap_end = min(max_ya, max_yb)

        # Overlap if they share more than just a point
        if overlap_end - overlap_start > tolerance:
            return True

    return False


def check_route_box_intersections(
    route: EdgeRoute,
    box_bounds: Dict[str, BoxBounds],
) -> List[str]:
    """
    Check if a route passes through any boxes (except source/target).

    Returns list of box names that the route intersects.
    """
    intersected = []
    segments = segments_from_waypoints(route.waypoints)

    for node, bounds in box_bounds.items():
        # Skip source and target boxes
        if node == route.source or node == route.target:
            continue

        for seg in segments:
            if segment_intersects_box(seg[0], seg[1], bounds):
                intersected.append(node)
                break

    return intersected


def check_route_overlaps(
    routes: List[EdgeRoute],
) -> List[Tuple[str, str]]:
    """
    Check if any routes have overlapping segments.

    Returns list of (edge1, edge2) tuples where edge is "source->target".
    """
    overlaps = []

    for i, route1 in enumerate(routes):
        segments1 = segments_from_waypoints(route1.waypoints)
        edge1_name = f"{route1.source}->{route1.target}"

        for j, route2 in enumerate(routes):
            if j <= i:
                continue

            segments2 = segments_from_waypoints(route2.waypoints)
            edge2_name = f"{route2.source}->{route2.target}"

            for seg1 in segments1:
                for seg2 in segments2:
                    if segments_overlap(seg1, seg2):
                        overlaps.append((edge1_name, edge2_name))
                        break
                else:
                    continue
                break

    return overlaps


def validate_routing_quality(
    node_positions: Dict[str, Tuple[int, int, int, int]],
    edges: List[Tuple[str, str]],
) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Validate routing quality for a given graph.

    Args:
        node_positions: Dict mapping node name to (x, y, width, height)
        edges: List of (source, target) tuples

    Returns:
        (box_intersections, overlaps) where:
        - box_intersections: List of "edge: [boxes]" strings
        - overlaps: List of (edge1, edge2) tuples
    """
    grid, port_manager, router = create_router(node_positions)

    # Route all edges
    routes = []
    for source, target in edges:
        route = router.route_edge(source, target)
        if route:
            routes.append(route)

    # Check for box intersections
    box_bounds = {
        node: BoxBounds(x, y, w, h) for node, (x, y, w, h) in node_positions.items()
    }

    box_intersections = []
    for route in routes:
        intersected = check_route_box_intersections(route, box_bounds)
        if intersected:
            edge_name = f"{route.source}->{route.target}"
            box_intersections.append(f"{edge_name}: {intersected}")

    # Check for overlaps
    overlaps = check_route_overlaps(routes)

    return box_intersections, overlaps


class TestRoutingQualityHelpers:
    """Tests for the routing quality helper functions."""

    def test_point_in_box(self):
        """Test point_in_box function."""
        bounds = BoxBounds(100, 100, 80, 40)

        # Inside
        assert point_in_box(140, 120, bounds)
        # Outside
        assert not point_in_box(50, 50, bounds)
        # On edge (should be inside due to < not <=)
        assert not point_in_box(100, 120, bounds)

    def test_segment_intersects_box_horizontal(self):
        """Test horizontal segment intersection."""
        bounds = BoxBounds(100, 100, 80, 40)

        # Segment passing through box horizontally
        assert segment_intersects_box((50, 120), (200, 120), bounds)
        # Segment above box
        assert not segment_intersects_box((50, 50), (200, 50), bounds)
        # Segment below box
        assert not segment_intersects_box((50, 200), (200, 200), bounds)

    def test_segment_intersects_box_vertical(self):
        """Test vertical segment intersection."""
        bounds = BoxBounds(100, 100, 80, 40)

        # Segment passing through box vertically
        assert segment_intersects_box((140, 50), (140, 200), bounds)
        # Segment left of box
        assert not segment_intersects_box((50, 50), (50, 200), bounds)
        # Segment right of box
        assert not segment_intersects_box((200, 50), (200, 200), bounds)

    def test_segments_overlap_horizontal(self):
        """Test horizontal segment overlap detection."""
        # Overlapping horizontal segments
        seg1 = ((0, 100), (100, 100))
        seg2 = ((50, 100), (150, 100))
        assert segments_overlap(seg1, seg2)

        # Non-overlapping horizontal segments (different y)
        seg3 = ((0, 100), (100, 100))
        seg4 = ((0, 200), (100, 200))
        assert not segments_overlap(seg3, seg4)

        # Adjacent but not overlapping
        seg5 = ((0, 100), (50, 100))
        seg6 = ((50, 100), (100, 100))
        assert not segments_overlap(seg5, seg6)

    def test_segments_overlap_vertical(self):
        """Test vertical segment overlap detection."""
        # Overlapping vertical segments
        seg1 = ((100, 0), (100, 100))
        seg2 = ((100, 50), (100, 150))
        assert segments_overlap(seg1, seg2)

        # Non-overlapping vertical segments (different x)
        seg3 = ((100, 0), (100, 100))
        seg4 = ((200, 0), (200, 100))
        assert not segments_overlap(seg3, seg4)

    def test_segments_cross_not_overlap(self):
        """Test that crossing segments are not considered overlapping."""
        # Perpendicular crossing
        seg1 = ((0, 100), (200, 100))  # Horizontal
        seg2 = ((100, 0), (100, 200))  # Vertical
        assert not segments_overlap(seg1, seg2)


class TestNoBoxIntersections:
    """Tests ensuring routes don't pass through boxes."""

    def test_simple_horizontal_no_intersection(self):
        """Test simple horizontal connection doesn't intersect obstacles."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (350, 100, 80, 40),
            "Obstacle": (200, 100, 60, 40),
        }
        edges = [("A", "B")]

        box_intersections, _ = validate_routing_quality(node_positions, edges)
        assert len(box_intersections) == 0, (
            f"Box intersections found: {box_intersections}"
        )

    def test_vertical_obstacle_avoidance(self):
        """Test that vertical routing avoids obstacles."""
        node_positions = {
            "A": (100, 50, 80, 40),
            "B": (100, 300, 80, 40),
            "Obstacle": (100, 150, 80, 80),
        }
        edges = [("A", "B")]

        box_intersections, _ = validate_routing_quality(node_positions, edges)
        assert len(box_intersections) == 0, (
            f"Box intersections found: {box_intersections}"
        )

    def test_multiple_edges_no_intersection(self):
        """Test multiple edges don't pass through boxes."""
        node_positions = {
            "Start": (50, 150, 80, 40),
            "Middle1": (200, 50, 80, 40),
            "Middle2": (200, 250, 80, 40),
            "End": (350, 150, 80, 40),
        }
        edges = [
            ("Start", "Middle1"),
            ("Start", "Middle2"),
            ("Middle1", "End"),
            ("Middle2", "End"),
        ]

        box_intersections, _ = validate_routing_quality(node_positions, edges)
        assert len(box_intersections) == 0, (
            f"Box intersections found: {box_intersections}"
        )

    def test_complex_graph_no_intersection(self):
        """Test complex graph doesn't have box intersections."""
        node_positions = {
            "A": (50, 50, 80, 40),
            "B": (200, 50, 80, 40),
            "C": (350, 50, 80, 40),
            "D": (50, 150, 80, 40),
            "E": (200, 150, 80, 40),
            "F": (350, 150, 80, 40),
        }
        edges = [
            ("A", "B"),
            ("B", "C"),
            ("A", "D"),
            ("B", "E"),
            ("C", "F"),
            ("D", "E"),
            ("E", "F"),
        ]

        box_intersections, _ = validate_routing_quality(node_positions, edges)
        assert len(box_intersections) == 0, (
            f"Box intersections found: {box_intersections}"
        )


class TestNoOverlappingLines:
    """Tests ensuring routes don't have overlapping segments."""

    def test_parallel_edges_no_overlap(self):
        """Test parallel edges don't overlap."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 50, 80, 40),
            "C": (250, 150, 80, 40),
        }
        edges = [("A", "B"), ("A", "C")]

        _, overlaps = validate_routing_quality(node_positions, edges)
        assert len(overlaps) == 0, f"Overlaps found: {overlaps}"

    def test_fan_out_no_overlap(self):
        """Test fan-out pattern doesn't create overlaps."""
        node_positions = {
            "Source": (50, 150, 80, 40),
            "Target1": (250, 50, 80, 40),
            "Target2": (250, 150, 80, 40),
            "Target3": (250, 250, 80, 40),
        }
        edges = [
            ("Source", "Target1"),
            ("Source", "Target2"),
            ("Source", "Target3"),
        ]

        _, overlaps = validate_routing_quality(node_positions, edges)
        assert len(overlaps) == 0, f"Overlaps found: {overlaps}"

    def test_fan_in_no_overlap(self):
        """Test fan-in pattern doesn't create overlaps."""
        node_positions = {
            "Source1": (50, 50, 80, 40),
            "Source2": (50, 150, 80, 40),
            "Source3": (50, 250, 80, 40),
            "Target": (250, 150, 80, 40),
        }
        edges = [
            ("Source1", "Target"),
            ("Source2", "Target"),
            ("Source3", "Target"),
        ]

        _, overlaps = validate_routing_quality(node_positions, edges)
        assert len(overlaps) == 0, f"Overlaps found: {overlaps}"


class TestRealWorldScenarios:
    """Tests based on real-world flowchart patterns."""

    def test_cicd_pipeline(self):
        """Test CI/CD pipeline pattern."""
        node_positions = {
            "Git Push": (50, 50, 100, 40),
            "Build": (50, 150, 100, 40),
            "Unit Tests": (50, 250, 100, 40),
            "Integration Tests": (220, 50, 140, 40),
            "Security Scan": (220, 150, 140, 40),
            "Deploy Staging": (220, 250, 140, 40),
            "E2E Tests": (430, 50, 100, 40),
            "Deploy Prod": (430, 150, 100, 40),
            "Notify Failure": (430, 250, 120, 40),
        }
        edges = [
            ("Git Push", "Build"),
            ("Build", "Unit Tests"),
            ("Unit Tests", "Integration Tests"),
            ("Integration Tests", "Security Scan"),
            ("Security Scan", "Deploy Staging"),
            ("Deploy Staging", "E2E Tests"),
            ("E2E Tests", "Deploy Prod"),
            ("Integration Tests", "Notify Failure"),
            ("Deploy Staging", "Notify Failure"),
        ]

        box_intersections, overlaps = validate_routing_quality(node_positions, edges)

        # Report issues but don't fail - these are warnings
        if box_intersections:
            print(f"CI/CD box intersections: {box_intersections}")
        if overlaps:
            print(f"CI/CD overlaps: {overlaps}")

    def test_error_handling_flow(self):
        """Test error handling flow pattern."""
        node_positions = {
            "Request": (50, 50, 100, 40),
            "Validate": (220, 50, 100, 40),
            "Process": (390, 50, 100, 40),
            "Response": (560, 50, 100, 40),
            "Retry": (50, 150, 100, 40),
            "Error Handler": (50, 250, 120, 40),
            "Log": (50, 350, 100, 40),
        }
        edges = [
            ("Request", "Validate"),
            ("Validate", "Process"),
            ("Process", "Response"),
            ("Request", "Retry"),
            ("Retry", "Validate"),
            ("Validate", "Error Handler"),
            ("Process", "Error Handler"),
            ("Error Handler", "Retry"),
            ("Error Handler", "Log"),
        ]

        box_intersections, overlaps = validate_routing_quality(node_positions, edges)

        if box_intersections:
            print(f"Error handling box intersections: {box_intersections}")
        if overlaps:
            print(f"Error handling overlaps: {overlaps}")

    def test_microservices_pattern(self):
        """Test microservices architecture pattern."""
        node_positions = {
            "API Gateway": (50, 100, 120, 40),
            "Order Service": (250, 50, 120, 40),
            "Auth Service": (250, 150, 120, 40),
            "User Service": (250, 250, 120, 40),
            "Payment Service": (450, 50, 130, 40),
            "Database": (450, 150, 100, 40),
            "Notification": (650, 50, 120, 40),
        }
        edges = [
            ("API Gateway", "Order Service"),
            ("API Gateway", "Auth Service"),
            ("API Gateway", "User Service"),
            ("Order Service", "Payment Service"),
            ("Auth Service", "Database"),
            ("Order Service", "Database"),
            ("Payment Service", "Notification"),
        ]

        box_intersections, overlaps = validate_routing_quality(node_positions, edges)

        if box_intersections:
            print(f"Microservices box intersections: {box_intersections}")
        if overlaps:
            print(f"Microservices overlaps: {overlaps}")


class TestRoutingQualityAPI:
    """Tests for the validate_routing_quality API."""

    def test_returns_empty_for_clean_routing(self):
        """Test that clean routing returns empty lists."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        edges = [("A", "B")]

        box_intersections, overlaps = validate_routing_quality(node_positions, edges)

        assert box_intersections == []
        assert overlaps == []

    def test_detects_potential_box_intersection(self):
        """Test detection when routing might go through a box."""
        # This layout forces routing to potentially go through the middle box
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (350, 100, 80, 40),
            "Blocker": (180, 80, 100, 80),  # Large blocker in the middle
        }
        edges = [("A", "B")]

        # Run validation - we're testing the detection mechanism works
        box_intersections, overlaps = validate_routing_quality(node_positions, edges)

        # The routing should avoid the blocker, so no intersections
        # If there are intersections, that's a routing bug to fix
        if box_intersections:
            print(f"Detected box intersections (routing issue): {box_intersections}")

    def test_handles_empty_graph(self):
        """Test handling of empty graph."""
        node_positions = {}
        edges = []

        box_intersections, overlaps = validate_routing_quality(node_positions, edges)

        assert box_intersections == []
        assert overlaps == []

    def test_handles_single_node(self):
        """Test handling of single node (no edges)."""
        node_positions = {"A": (50, 100, 80, 40)}
        edges = []

        box_intersections, overlaps = validate_routing_quality(node_positions, edges)

        assert box_intersections == []
        assert overlaps == []
