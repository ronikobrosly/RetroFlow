"""Unit tests for the router module."""

import pytest

from retroflow.router import (
    BoxInfo,
    EdgeRoute,
    EdgeRouter,
    Port,
    PortSide,
)


class TestPortSide:
    """Tests for PortSide enum."""

    def test_port_side_values(self):
        """Test PortSide enum values."""
        assert PortSide.TOP.value == "top"
        assert PortSide.BOTTOM.value == "bottom"
        assert PortSide.LEFT.value == "left"
        assert PortSide.RIGHT.value == "right"

    def test_port_side_count(self):
        """Test PortSide has exactly 4 values."""
        assert len(PortSide) == 4


class TestPort:
    """Tests for Port dataclass."""

    def test_port_creation(self):
        """Test Port creation with required fields."""
        port = Port(node="A", side=PortSide.BOTTOM, offset=5)
        assert port.node == "A"
        assert port.side == PortSide.BOTTOM
        assert port.offset == 5
        assert port.x == 0  # Default
        assert port.y == 0  # Default

    def test_port_with_coordinates(self):
        """Test Port creation with coordinates."""
        port = Port(node="B", side=PortSide.TOP, offset=3, x=10, y=20)
        assert port.x == 10
        assert port.y == 20


class TestBoxInfo:
    """Tests for BoxInfo dataclass."""

    def test_box_info_creation(self):
        """Test BoxInfo creation."""
        box = BoxInfo(name="Test", x=10, y=20, width=15, height=5, layer=0, position=0)
        assert box.name == "Test"
        assert box.x == 10
        assert box.y == 20
        assert box.width == 15
        assert box.height == 5
        assert box.layer == 0
        assert box.position == 0


class TestEdgeRoute:
    """Tests for EdgeRoute dataclass."""

    def test_edge_route_creation(self):
        """Test EdgeRoute creation."""
        src_port = Port(node="A", side=PortSide.BOTTOM, offset=5, x=10, y=5)
        tgt_port = Port(node="B", side=PortSide.TOP, offset=5, x=10, y=15)

        route = EdgeRoute(
            source="A", target="B", source_port=src_port, target_port=tgt_port
        )
        assert route.source == "A"
        assert route.target == "B"
        assert route.source_port == src_port
        assert route.target_port == tgt_port
        assert route.waypoints == []  # Default

    def test_edge_route_with_waypoints(self):
        """Test EdgeRoute with waypoints."""
        src_port = Port(node="A", side=PortSide.BOTTOM, offset=5)
        tgt_port = Port(node="B", side=PortSide.TOP, offset=5)

        waypoints = [(10, 5), (10, 10), (20, 10), (20, 15)]
        route = EdgeRoute(
            source="A",
            target="B",
            source_port=src_port,
            target_port=tgt_port,
            waypoints=waypoints,
        )
        assert route.waypoints == waypoints


class TestEdgeRouter:
    """Tests for EdgeRouter class."""

    @pytest.fixture
    def router(self):
        """Create a fresh EdgeRouter for testing."""
        return EdgeRouter()

    @pytest.fixture
    def simple_boxes(self):
        """Simple box setup for testing."""
        return {
            "A": BoxInfo(name="A", x=0, y=0, width=10, height=5, layer=0, position=0),
            "B": BoxInfo(name="B", x=0, y=15, width=10, height=5, layer=1, position=0),
        }

    @pytest.fixture
    def branching_boxes(self):
        """Branching box setup for testing."""
        return {
            "Start": BoxInfo(
                name="Start", x=20, y=0, width=10, height=5, layer=0, position=0
            ),
            "A": BoxInfo(name="A", x=0, y=15, width=10, height=5, layer=1, position=0),
            "B": BoxInfo(name="B", x=40, y=15, width=10, height=5, layer=1, position=1),
            "End": BoxInfo(
                name="End", x=20, y=30, width=10, height=5, layer=2, position=0
            ),
        }

    def test_router_initialization(self, router):
        """Test EdgeRouter initialization."""
        assert router.boxes == {}
        assert router.used_ports == {}

    def test_set_boxes(self, router, simple_boxes):
        """Test setting boxes."""
        router.set_boxes(simple_boxes)
        assert router.boxes == simple_boxes
        assert "A" in router.used_ports
        assert "B" in router.used_ports

    def test_set_boxes_initializes_port_tracking(self, router, simple_boxes):
        """Test that set_boxes initializes port tracking for all sides."""
        router.set_boxes(simple_boxes)

        for node in simple_boxes:
            for side in PortSide:
                assert side in router.used_ports[node]
                assert router.used_ports[node][side] == set()

    def test_route_edges_simple(self, router, simple_boxes):
        """Test routing simple edge."""
        router.set_boxes(simple_boxes)

        edges = [("A", "B")]
        layers = [["A"], ["B"]]

        routes = router.route_edges(edges, layers)

        assert len(routes) == 1
        route = routes[0]
        assert route.source == "A"
        assert route.target == "B"
        assert route.source_port.side == PortSide.BOTTOM
        assert route.target_port.side == PortSide.TOP

    def test_route_edges_multiple(self, router, branching_boxes):
        """Test routing multiple edges."""
        router.set_boxes(branching_boxes)

        edges = [("Start", "A"), ("Start", "B"), ("A", "End"), ("B", "End")]
        layers = [["Start"], ["A", "B"], ["End"]]

        routes = router.route_edges(edges, layers)

        assert len(routes) == 4

    def test_route_edges_missing_node_returns_none(self, router, simple_boxes):
        """Test routing edge with missing node."""
        router.set_boxes(simple_boxes)

        # Edge to non-existent node
        edges = [("A", "C")]
        layers = [["A"], ["C"]]

        routes = router.route_edges(edges, layers)

        # Should not include invalid route
        assert len(routes) == 0

    def test_route_edge_upward(self, router, simple_boxes):
        """Test routing edge going upward (back edge)."""
        router.set_boxes(simple_boxes)

        edges = [("B", "A")]  # B is in layer 1, A is in layer 0
        layers = [["A"], ["B"]]

        routes = router.route_edges(edges, layers)

        assert len(routes) == 1
        route = routes[0]
        assert route.source_port.side == PortSide.TOP
        assert route.target_port.side == PortSide.BOTTOM

    def test_route_edge_same_layer_right(self, router):
        """Test routing edge between nodes in same layer (left to right)."""
        boxes = {
            "A": BoxInfo(name="A", x=0, y=0, width=10, height=5, layer=0, position=0),
            "B": BoxInfo(name="B", x=30, y=0, width=10, height=5, layer=0, position=1),
        }
        router.set_boxes(boxes)

        edges = [("A", "B")]
        layers = [["A", "B"]]

        routes = router.route_edges(edges, layers)

        assert len(routes) == 1
        route = routes[0]
        assert route.source_port.side == PortSide.RIGHT
        assert route.target_port.side == PortSide.LEFT

    def test_route_edge_same_layer_left(self, router):
        """Test routing edge between nodes in same layer (right to left)."""
        boxes = {
            "A": BoxInfo(name="A", x=0, y=0, width=10, height=5, layer=0, position=0),
            "B": BoxInfo(name="B", x=30, y=0, width=10, height=5, layer=0, position=1),
        }
        router.set_boxes(boxes)

        edges = [("B", "A")]
        layers = [["A", "B"]]

        routes = router.route_edges(edges, layers)

        assert len(routes) == 1
        route = routes[0]
        assert route.source_port.side == PortSide.LEFT
        assert route.target_port.side == PortSide.RIGHT

    def test_dummy_node_routing(self, router):
        """Test routing through dummy nodes."""
        boxes = {
            "__dummy_1": BoxInfo(
                name="__dummy_1", x=0, y=0, width=10, height=5, layer=0, position=0
            ),
            "B": BoxInfo(name="B", x=0, y=15, width=10, height=5, layer=1, position=0),
        }
        router.set_boxes(boxes)

        edges = [("__dummy_1", "B")]
        layers = [["__dummy_1"], ["B"]]

        routes = router.route_edges(edges, layers)

        assert len(routes) == 1
        assert routes[0].source == "__dummy_1"

    def test_dummy_node_upward(self, router):
        """Test dummy node routing upward."""
        boxes = {
            "A": BoxInfo(name="A", x=0, y=0, width=10, height=5, layer=0, position=0),
            "__dummy_1": BoxInfo(
                name="__dummy_1", x=0, y=15, width=10, height=5, layer=1, position=0
            ),
        }
        router.set_boxes(boxes)

        edges = [("__dummy_1", "A")]
        layers = [["A"], ["__dummy_1"]]

        routes = router.route_edges(edges, layers)

        assert len(routes) == 1
        route = routes[0]
        assert route.source_port.side == PortSide.TOP

    def test_waypoints_direct_vertical(self, router, simple_boxes):
        """Test waypoints for direct vertical connection."""
        router.set_boxes(simple_boxes)

        edges = [("A", "B")]
        layers = [["A"], ["B"]]

        routes = router.route_edges(edges, layers)

        route = routes[0]
        # Should have start and end waypoints
        assert len(route.waypoints) >= 2

    def test_waypoints_with_horizontal_segment(self, router, branching_boxes):
        """Test waypoints when horizontal segment needed."""
        router.set_boxes(branching_boxes)

        edges = [("Start", "B")]
        layers = [["Start"], ["A", "B"], ["End"]]

        routes = router.route_edges(edges, layers)

        route = routes[0]
        # Should have waypoints for the path
        assert len(route.waypoints) >= 2

    def test_port_allocation_single(self, router, simple_boxes):
        """Test port allocation for single connection."""
        router.set_boxes(simple_boxes)

        edges = [("A", "B")]
        layers = [["A"], ["B"]]

        routes = router.route_edges(edges, layers)

        route = routes[0]
        # Single port should be centered
        assert route.source_port.offset > 0

    def test_port_allocation_multiple(self, router, branching_boxes):
        """Test port allocation for multiple connections from same node."""
        router.set_boxes(branching_boxes)

        edges = [("Start", "A"), ("Start", "B")]
        layers = [["Start"], ["A", "B"], ["End"]]

        routes = router.route_edges(edges, layers)

        # Both edges should have different port positions
        start_routes = [r for r in routes if r.source == "Start"]
        assert len(start_routes) == 2

        # Source ports should have different offsets
        offsets = {r.source_port.offset for r in start_routes}
        assert len(offsets) == 2  # Two different offsets

    def test_used_ports_tracking(self, router, simple_boxes):
        """Test that used ports are tracked."""
        router.set_boxes(simple_boxes)

        edges = [("A", "B")]
        layers = [["A"], ["B"]]

        router.route_edges(edges, layers)

        # Check that ports were marked as used
        assert len(router.used_ports["A"][PortSide.BOTTOM]) > 0
        assert len(router.used_ports["B"][PortSide.TOP]) > 0


class TestWaypointCalculation:
    """Tests for waypoint calculation edge cases."""

    @pytest.fixture
    def router(self):
        """Create a fresh EdgeRouter for testing."""
        return EdgeRouter()

    def test_waypoints_same_x_coordinate(self, router):
        """Test waypoints when source and target have same x."""
        boxes = {
            "A": BoxInfo(name="A", x=10, y=0, width=10, height=5, layer=0, position=0),
            "B": BoxInfo(name="B", x=10, y=20, width=10, height=5, layer=1, position=0),
        }
        router.set_boxes(boxes)

        edges = [("A", "B")]
        layers = [["A"], ["B"]]

        routes = router.route_edges(edges, layers)

        route = routes[0]
        # Direct vertical, should have just 2 waypoints
        assert len(route.waypoints) == 2

    def test_waypoints_different_x_coordinate(self, router):
        """Test waypoints when source and target have different x."""
        boxes = {
            "A": BoxInfo(name="A", x=0, y=0, width=10, height=5, layer=0, position=0),
            "B": BoxInfo(name="B", x=30, y=20, width=10, height=5, layer=1, position=0),
        }
        router.set_boxes(boxes)

        edges = [("A", "B")]
        layers = [["A"], ["B"]]

        routes = router.route_edges(edges, layers)

        route = routes[0]
        # Should have intermediate waypoints for horizontal segment
        assert len(route.waypoints) >= 4

    def test_waypoints_horizontal_same_y(self, router):
        """Test waypoints for horizontal edge with same y."""
        boxes = {
            "A": BoxInfo(name="A", x=0, y=10, width=10, height=5, layer=0, position=0),
            "B": BoxInfo(name="B", x=30, y=10, width=10, height=5, layer=0, position=1),
        }
        router.set_boxes(boxes)

        edges = [("A", "B")]
        layers = [["A", "B"]]

        routes = router.route_edges(edges, layers)

        route = routes[0]
        # Direct horizontal, should have 2 waypoints
        assert len(route.waypoints) == 2

    def test_waypoints_horizontal_different_y(self, router):
        """Test waypoints for horizontal edge with different y."""
        boxes = {
            "A": BoxInfo(name="A", x=0, y=0, width=10, height=5, layer=0, position=0),
            "B": BoxInfo(name="B", x=30, y=10, width=10, height=5, layer=0, position=1),
        }
        router.set_boxes(boxes)

        edges = [("A", "B")]
        layers = [["A", "B"]]

        routes = router.route_edges(edges, layers)

        route = routes[0]
        # Should have intermediate waypoints
        assert len(route.waypoints) >= 4
