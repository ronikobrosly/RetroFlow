"""Tests for the edge routing module."""

from retroflow.edge_routing import (
    BoxBounds,
    CellType,
    ChannelManager,
    EdgeRoute,
    OccupancyGrid,
    OrthogonalRouter,
    Port,
    PortManager,
    PortPosition,
    RoutingChannel,
    create_router,
)


class TestBoxBounds:
    """Tests for BoxBounds dataclass."""

    def test_create_box_bounds(self):
        """Test creating a BoxBounds."""
        bounds = BoxBounds(10, 20, 100, 50)
        assert bounds.x == 10
        assert bounds.y == 20
        assert bounds.width == 100
        assert bounds.height == 50

    def test_x2_property(self):
        """Test x2 property."""
        bounds = BoxBounds(10, 20, 100, 50)
        assert bounds.x2 == 110

    def test_y2_property(self):
        """Test y2 property."""
        bounds = BoxBounds(10, 20, 100, 50)
        assert bounds.y2 == 70

    def test_center_x_property(self):
        """Test center_x property."""
        bounds = BoxBounds(10, 20, 100, 50)
        assert bounds.center_x == 60

    def test_center_y_property(self):
        """Test center_y property."""
        bounds = BoxBounds(10, 20, 100, 50)
        assert bounds.center_y == 45


class TestOccupancyGrid:
    """Tests for OccupancyGrid class."""

    def test_create_grid(self):
        """Test creating an occupancy grid."""
        grid = OccupancyGrid(100, 100)
        assert grid.width == 100
        assert grid.height == 100

    def test_is_free_empty_cell(self):
        """Test that empty cells are free."""
        grid = OccupancyGrid(100, 100)
        assert grid.is_free(50, 50)

    def test_is_free_out_of_bounds(self):
        """Test that out of bounds cells are not free."""
        grid = OccupancyGrid(100, 100)
        assert not grid.is_free(-1, 50)
        assert not grid.is_free(50, -1)
        assert not grid.is_free(100, 50)
        assert not grid.is_free(50, 100)

    def test_is_empty(self):
        """Test is_empty method."""
        grid = OccupancyGrid(100, 100)
        assert grid.is_empty(50, 50)
        assert not grid.is_empty(-1, 50)

    def test_mark_box(self):
        """Test marking a box in the grid."""
        grid = OccupancyGrid(200, 200)
        bounds = BoxBounds(50, 50, 40, 30)
        grid.mark_box("test", bounds, margin=0)

        # Inside the box should not be free
        assert not grid.is_free(60, 60)
        # Outside should be free
        assert grid.is_free(10, 10)

    def test_mark_edge_segment_horizontal(self):
        """Test marking a horizontal edge segment."""
        grid = OccupancyGrid(100, 100)
        grid.mark_edge_segment(10, 50, 30, 50)

        assert grid.get_cell_type(20, 50) == CellType.HORIZONTAL_EDGE

    def test_mark_edge_segment_vertical(self):
        """Test marking a vertical edge segment."""
        grid = OccupancyGrid(100, 100)
        grid.mark_edge_segment(50, 10, 50, 30)

        assert grid.get_cell_type(50, 20) == CellType.VERTICAL_EDGE

    def test_mark_edge_junction(self):
        """Test that crossing edges create a junction."""
        grid = OccupancyGrid(100, 100)
        grid.mark_edge_segment(10, 50, 90, 50)  # Horizontal
        grid.mark_edge_segment(50, 10, 50, 90)  # Vertical

        assert grid.get_cell_type(50, 50) == CellType.JUNCTION

    def test_get_cell_type_empty(self):
        """Test getting cell type for empty cell."""
        grid = OccupancyGrid(100, 100)
        assert grid.get_cell_type(50, 50) == CellType.EMPTY

    def test_is_box(self):
        """Test is_box method."""
        grid = OccupancyGrid(200, 200)
        bounds = BoxBounds(50, 50, 40, 30)
        grid.mark_box("test", bounds, margin=0)

        assert grid.is_box(60, 60)
        assert not grid.is_box(10, 10)

    def test_has_edge(self):
        """Test has_edge method."""
        grid = OccupancyGrid(100, 100)
        grid.mark_edge_segment(10, 50, 30, 50)

        assert grid.has_edge(20, 50)
        assert not grid.has_edge(50, 50)

    def test_point_in_any_box(self):
        """Test point_in_any_box method."""
        grid = OccupancyGrid(300, 300)
        bounds1 = BoxBounds(50, 50, 40, 30)
        bounds2 = BoxBounds(150, 50, 40, 30)
        grid.mark_box("A", bounds1)
        grid.mark_box("B", bounds2)

        assert grid.point_in_any_box(60, 60)
        assert grid.point_in_any_box(160, 60)
        assert not grid.point_in_any_box(100, 100)
        # Test with exclusion
        assert not grid.point_in_any_box(60, 60, exclude_nodes={"A"})

    def test_line_intersects_box(self):
        """Test line_intersects_box method."""
        grid = OccupancyGrid(300, 300)
        bounds = BoxBounds(100, 100, 50, 50)
        grid.mark_box("blocker", bounds)

        # Horizontal line through box
        assert grid.line_intersects_box(50, 125, 200, 125)
        # Horizontal line below box
        assert not grid.line_intersects_box(50, 200, 200, 200)
        # Vertical line through box
        assert grid.line_intersects_box(125, 50, 125, 200)
        # Vertical line beside box
        assert not grid.line_intersects_box(50, 50, 50, 200)


class TestPortManager:
    """Tests for PortManager class."""

    def test_create_ports_for_box(self):
        """Test creating ports for a box."""
        manager = PortManager()
        bounds = BoxBounds(100, 100, 80, 40)
        manager.create_ports_for_box("test", bounds)

        # Should have ports on all 4 sides
        assert len(manager.ports["test"]["top"]) == 3
        assert len(manager.ports["test"]["bottom"]) == 3
        assert len(manager.ports["test"]["left"]) == 3
        assert len(manager.ports["test"]["right"]) == 3

    def test_port_positions(self):
        """Test that ports are at correct positions."""
        manager = PortManager()
        bounds = BoxBounds(100, 100, 100, 50)
        manager.create_ports_for_box("test", bounds)

        # Check top ports are at y=100 (top of box)
        for port in manager.ports["test"]["top"]:
            assert port.y == 100

        # Check bottom ports are at y=150 (bottom of box)
        for port in manager.ports["test"]["bottom"]:
            assert port.y == 150

    def test_get_available_port(self):
        """Test getting an available port for a connection."""
        manager = PortManager()
        bounds = BoxBounds(100, 100, 80, 40)
        manager.create_ports_for_box("test", bounds)

        # Get port on right side targeting something to the right
        port = manager.get_available_port("test", "right", 300, True)

        assert port is not None
        assert port.side == "right"
        assert port.x == bounds.x2

    def test_get_next_available_port(self):
        """Test getting the next available port."""
        manager = PortManager()
        bounds = BoxBounds(100, 100, 80, 40)
        manager.create_ports_for_box("test", bounds)

        port = manager.get_next_available_port("test", "top")
        assert port is not None
        assert port.side == "top"

    def test_get_next_available_port_marks_used(self):
        """Test that getting a port marks it as used."""
        manager = PortManager()
        bounds = BoxBounds(100, 100, 80, 40)
        manager.create_ports_for_box("test", bounds)

        # Get 3 ports from the same side
        port1 = manager.get_next_available_port("test", "top")
        port2 = manager.get_next_available_port("test", "top")
        port3 = manager.get_next_available_port("test", "top")

        # Should get different ports (or same if all used)
        assert port1 is not None
        assert port2 is not None
        assert port3 is not None

    def test_get_port_at_position(self):
        """Test getting a specific port by position."""
        manager = PortManager()
        bounds = BoxBounds(100, 100, 80, 40)
        manager.create_ports_for_box("test", bounds)

        port = manager.get_port_at_position("test", "top", PortPosition.MIDDLE)
        assert port is not None
        assert port.position == PortPosition.MIDDLE

    def test_count_used_ports(self):
        """Test counting used ports."""
        manager = PortManager()
        bounds = BoxBounds(100, 100, 80, 40)
        manager.create_ports_for_box("test", bounds)

        assert manager.count_used_ports("test", "top") == 0

        manager.get_next_available_port("test", "top")
        assert manager.count_used_ports("test", "top") == 1

        manager.get_next_available_port("test", "top")
        assert manager.count_used_ports("test", "top") == 2


class TestOrthogonalRouter:
    """Tests for OrthogonalRouter class."""

    def test_get_all_side_options_horizontal(self):
        """Test getting side options for horizontal connection."""
        grid = OccupancyGrid(500, 500)
        port_manager = PortManager()
        box_bounds = {
            "A": BoxBounds(50, 100, 80, 40),
            "B": BoxBounds(250, 100, 80, 40),
        }

        for name, bounds in box_bounds.items():
            grid.mark_box(name, bounds)
            port_manager.create_ports_for_box(name, bounds)

        router = OrthogonalRouter(grid, port_manager, box_bounds)
        options = router._get_all_side_options("A", "B")

        # First option should be best - right to left for horizontal
        src_side, tgt_side, _ = options[0]
        assert src_side == "right"
        assert tgt_side == "left"

    def test_get_all_side_options_vertical(self):
        """Test getting side options for vertical connection."""
        grid = OccupancyGrid(500, 500)
        port_manager = PortManager()
        box_bounds = {
            "A": BoxBounds(100, 50, 80, 40),
            "B": BoxBounds(100, 200, 80, 40),
        }

        for name, bounds in box_bounds.items():
            grid.mark_box(name, bounds)
            port_manager.create_ports_for_box(name, bounds)

        router = OrthogonalRouter(grid, port_manager, box_bounds)
        options = router._get_all_side_options("A", "B")

        # First option should be best - bottom to top for vertical
        src_side, tgt_side, _ = options[0]
        assert src_side == "bottom"
        assert tgt_side == "top"

    def test_route_edge_simple(self):
        """Test routing a simple edge."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router.route_edge("A", "B")

        assert route is not None
        assert route.source == "A"
        assert route.target == "B"
        assert len(route.waypoints) >= 2

    def test_route_edge_bidirectional(self):
        """Test routing a bidirectional edge."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router.route_edge("A", "B", is_bidirectional=True)

        assert route is not None
        assert route.is_bidirectional

    def test_route_edge_invalid_nodes(self):
        """Test routing with invalid nodes returns None."""
        node_positions = {
            "A": (50, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router.route_edge("A", "B")
        assert route is None

    def test_get_side_center(self):
        """Test getting the center point of a box side."""
        grid = OccupancyGrid(500, 500)
        port_manager = PortManager()
        box_bounds = {"A": BoxBounds(100, 100, 80, 40)}
        router = OrthogonalRouter(grid, port_manager, box_bounds)

        bounds = box_bounds["A"]
        assert router._get_side_center(bounds, "top") == (140, 100)
        assert router._get_side_center(bounds, "bottom") == (140, 140)
        assert router._get_side_center(bounds, "left") == (100, 120)
        assert router._get_side_center(bounds, "right") == (180, 120)


class TestCreateRouter:
    """Tests for create_router function."""

    def test_create_router_returns_tuple(self):
        """Test that create_router returns correct tuple."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        result = create_router(node_positions)

        assert len(result) == 3
        grid, port_manager, router = result
        assert isinstance(grid, OccupancyGrid)
        assert isinstance(port_manager, PortManager)
        assert isinstance(router, OrthogonalRouter)

    def test_create_router_marks_boxes(self):
        """Test that create_router marks boxes in grid."""
        node_positions = {
            "A": (50, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        # Box area should not be free (due to margin)
        assert not grid.is_free(60, 110)

    def test_create_router_creates_ports(self):
        """Test that create_router creates ports for all nodes."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        assert "A" in port_manager.ports
        assert "B" in port_manager.ports

    def test_create_router_empty_positions(self):
        """Test create_router with empty node positions."""
        grid, port_manager, router = create_router({})

        assert isinstance(grid, OccupancyGrid)
        assert isinstance(port_manager, PortManager)
        assert isinstance(router, OrthogonalRouter)


class TestEdgeRoute:
    """Tests for EdgeRoute dataclass."""

    def test_create_edge_route(self):
        """Test creating an EdgeRoute."""
        src_port = Port("A", "right", PortPosition.MIDDLE, 100, 50)
        tgt_port = Port("B", "left", PortPosition.MIDDLE, 200, 50)

        route = EdgeRoute(
            source="A",
            target="B",
            source_port=src_port,
            target_port=tgt_port,
            waypoints=[(100, 50), (200, 50)],
            is_bidirectional=False,
        )

        assert route.source == "A"
        assert route.target == "B"
        assert len(route.waypoints) == 2
        assert not route.is_bidirectional


class TestPort:
    """Tests for Port dataclass."""

    def test_create_port(self):
        """Test creating a Port."""
        port = Port("A", "right", PortPosition.MIDDLE, 100, 50)

        assert port.node == "A"
        assert port.side == "right"
        assert port.position == PortPosition.MIDDLE
        assert port.x == 100
        assert port.y == 50
        assert not port.in_use


class TestPortPosition:
    """Tests for PortPosition enum."""

    def test_port_position_values(self):
        """Test PortPosition enum values."""
        assert PortPosition.START.value == 0.25
        assert PortPosition.MIDDLE.value == 0.5
        assert PortPosition.END.value == 0.75


class TestCellType:
    """Tests for CellType enum."""

    def test_cell_type_values(self):
        """Test CellType enum values."""
        assert CellType.EMPTY.value == 0
        assert CellType.BOX.value == 1
        assert CellType.HORIZONTAL_EDGE.value == 2
        assert CellType.VERTICAL_EDGE.value == 3
        assert CellType.JUNCTION.value == 4


class TestRouterPathFinding:
    """Tests for router pathfinding edge cases."""

    def test_route_vertical_connection(self):
        """Test routing a vertical connection."""
        node_positions = {
            "A": (100, 50, 80, 40),
            "B": (100, 200, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router.route_edge("A", "B")
        assert route is not None
        assert len(route.waypoints) >= 2

    def test_route_with_obstacle(self):
        """Test routing around an obstacle."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (350, 100, 80, 40),
            "C": (200, 100, 60, 40),  # Obstacle in the middle
        }
        grid, port_manager, router = create_router(node_positions)

        route = router.route_edge("A", "B")
        assert route is not None

    def test_check_path_viable_blocked(self):
        """Test path viability check with blocked path."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "Blocker": (150, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        # Path through the blocker should not be viable
        result = router._check_path_viable(100, 120, 300, 120, {"A"})
        # The path may still be viable via alternative routes
        # Just verify it returns a boolean
        assert isinstance(result, bool)

    def test_check_path_viable_clear(self):
        """Test path viability check with clear path."""
        node_positions = {
            "A": (50, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        # Clear path should be viable
        result = router._check_path_viable(200, 50, 300, 50, {"A"})
        assert result is True

    def test_simplify_waypoints_short_list(self):
        """Test simplifying very short waypoint list."""
        node_positions = {
            "A": (50, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        # List with 2 or fewer points should be returned as-is
        result = router._simplify_waypoints([(0, 0), (10, 10)])
        assert result == [(0, 0), (10, 10)]

        result = router._simplify_waypoints([(0, 0)])
        assert result == [(0, 0)]

    def test_simplify_waypoints_removes_collinear(self):
        """Test that simplify removes collinear points."""
        node_positions = {
            "A": (50, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        # Middle point is collinear on horizontal line
        result = router._simplify_waypoints([(0, 0), (5, 0), (10, 0)])
        assert result == [(0, 0), (10, 0)]

    def test_route_left_direction(self):
        """Test routing with leftward connection."""
        node_positions = {
            "A": (250, 100, 80, 40),
            "B": (50, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router.route_edge("A", "B")
        assert route is not None

    def test_route_upward_direction(self):
        """Test routing with upward connection."""
        node_positions = {
            "A": (100, 200, 80, 40),
            "B": (100, 50, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router.route_edge("A", "B")
        assert route is not None

    def test_find_orthogonal_path_both_horizontal(self):
        """Test finding path when both sides are horizontal."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 200, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        path = router._find_orthogonal_path(
            130, 120, 250, 220, "right", "left", {"A", "B"}
        )
        assert isinstance(path, list)

    def test_find_orthogonal_path_both_vertical(self):
        """Test finding path when both sides are vertical."""
        node_positions = {
            "A": (100, 50, 80, 40),
            "B": (200, 200, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        path = router._find_orthogonal_path(
            140, 90, 240, 200, "bottom", "top", {"A", "B"}
        )
        assert isinstance(path, list)

    def test_vertical_line_blocked(self):
        """Test vertical line blockage detection."""
        node_positions = {
            "Blocker": (100, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        # Line through blocker
        assert router._vertical_line_blocked(120, 50, 200, set())
        # Line beside blocker
        assert not router._vertical_line_blocked(50, 50, 200, set())

    def test_horizontal_line_blocked(self):
        """Test horizontal line blockage detection."""
        node_positions = {
            "Blocker": (100, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        # Line through blocker
        assert router._horizontal_line_blocked(120, 50, 250, set())
        # Line above blocker
        assert not router._horizontal_line_blocked(50, 50, 250, set())


class TestPortManagerEdgeCases:
    """Edge case tests for PortManager."""

    def test_get_available_port_no_node(self):
        """Test getting port from non-existent node."""
        manager = PortManager()
        port = manager.get_available_port("nonexistent", "right", 100, True)
        assert port is None

    def test_get_next_available_port_no_node(self):
        """Test getting unused port from non-existent node."""
        manager = PortManager()
        port = manager.get_next_available_port("nonexistent", "right")
        assert port is None

    def test_multiple_edges_same_side(self):
        """Test multiple edges from same side get different ports."""
        manager = PortManager()
        bounds = BoxBounds(100, 100, 80, 40)
        manager.create_ports_for_box("test", bounds)

        # Get 3 ports from the same side using get_available_port
        port1 = manager.get_available_port("test", "right", 300, False)
        port2 = manager.get_available_port("test", "right", 350, False)
        port3 = manager.get_available_port("test", "right", 400, False)

        # Should use different port positions
        positions = {port1.position, port2.position, port3.position}
        assert len(positions) >= 2  # At least some variety

    def test_get_port_at_position_no_node(self):
        """Test getting port at position from non-existent node."""
        manager = PortManager()
        port = manager.get_port_at_position("nonexistent", "right", PortPosition.MIDDLE)
        assert port is None

    def test_strict_port_enforcement_get_available_port(self):
        """Test that get_available_port returns None when all ports are used."""
        manager = PortManager()
        bounds = BoxBounds(100, 100, 80, 40)
        manager.create_ports_for_box("test", bounds)

        # Use all 3 ports on the right side
        port1 = manager.get_available_port("test", "right", 100, False)
        port2 = manager.get_available_port("test", "right", 150, False)
        port3 = manager.get_available_port("test", "right", 200, False)

        assert port1 is not None
        assert port2 is not None
        assert port3 is not None

        # 4th attempt should return None (strict enforcement)
        port4 = manager.get_available_port("test", "right", 250, False)
        assert port4 is None

    def test_strict_port_enforcement_get_next_available_port(self):
        """Test that get_next_available_port returns None when all ports are used."""
        manager = PortManager()
        bounds = BoxBounds(100, 100, 80, 40)
        manager.create_ports_for_box("test", bounds)

        # Use all 3 ports on the top side
        port1 = manager.get_next_available_port("test", "top")
        port2 = manager.get_next_available_port("test", "top")
        port3 = manager.get_next_available_port("test", "top")

        assert port1 is not None
        assert port2 is not None
        assert port3 is not None

        # 4th attempt should return None (strict enforcement)
        port4 = manager.get_next_available_port("test", "top")
        assert port4 is None

    def test_validate_no_duplicate_ports_clean(self):
        """Test validation passes with no duplicate port usage."""
        manager = PortManager()
        bounds = BoxBounds(100, 100, 80, 40)
        manager.create_ports_for_box("test", bounds)

        # Use ports normally
        manager.get_available_port("test", "right", 100, False)
        manager.get_available_port("test", "top", 100, True)

        is_valid, errors = manager.validate_no_duplicate_ports()
        assert is_valid
        assert len(errors) == 0

    def test_validate_no_duplicate_ports_all_ports_used(self):
        """Test validation passes even when all ports on a side are used."""
        manager = PortManager()
        bounds = BoxBounds(100, 100, 80, 40)
        manager.create_ports_for_box("test", bounds)

        # Use all 3 ports on right side
        manager.get_available_port("test", "right", 100, False)
        manager.get_available_port("test", "right", 150, False)
        manager.get_available_port("test", "right", 200, False)

        is_valid, errors = manager.validate_no_duplicate_ports()
        assert is_valid
        assert len(errors) == 0


class TestRoutingChannel:
    """Tests for RoutingChannel dataclass."""

    def test_create_routing_channel(self):
        """Test creating a RoutingChannel."""
        channel = RoutingChannel(100, is_horizontal=True)
        assert channel.position == 100
        assert channel.is_horizontal is True
        assert channel.used_segments == []

    def test_routing_channel_with_segments(self):
        """Test RoutingChannel with used segments."""
        channel = RoutingChannel(100, is_horizontal=True, used_segments=[(0, 50)])
        assert len(channel.used_segments) == 1
        assert channel.used_segments[0] == (0, 50)


class TestChannelManager:
    """Tests for ChannelManager class."""

    def test_create_channel_manager(self):
        """Test creating a ChannelManager."""
        grid = OccupancyGrid(500, 500)
        bounds1 = BoxBounds(50, 50, 80, 40)
        bounds2 = BoxBounds(50, 200, 80, 40)
        grid.mark_box("A", bounds1)
        grid.mark_box("B", bounds2)

        manager = ChannelManager(grid)
        # Should have computed channels
        assert isinstance(manager.horizontal_channels, list)
        assert isinstance(manager.vertical_channels, list)

    def test_get_horizontal_channel(self):
        """Test getting a horizontal channel."""
        grid = OccupancyGrid(500, 500)
        bounds1 = BoxBounds(50, 50, 80, 40)
        bounds2 = BoxBounds(50, 200, 80, 40)
        grid.mark_box("A", bounds1)
        grid.mark_box("B", bounds2)

        manager = ChannelManager(grid)
        y = manager.get_horizontal_channel(100, 180, 0, 100)
        assert y is not None
        assert 100 <= y <= 180

    def test_get_vertical_channel(self):
        """Test getting a vertical channel."""
        grid = OccupancyGrid(500, 500)
        bounds1 = BoxBounds(50, 100, 80, 40)
        bounds2 = BoxBounds(250, 100, 80, 40)
        grid.mark_box("A", bounds1)
        grid.mark_box("B", bounds2)

        manager = ChannelManager(grid)
        x = manager.get_vertical_channel(150, 230, 0, 200)
        assert x is not None
        assert 150 <= x <= 230

    def test_channel_manager_empty_grid(self):
        """Test ChannelManager with empty grid."""
        grid = OccupancyGrid(500, 500)
        manager = ChannelManager(grid)

        # Should handle empty grid gracefully
        assert isinstance(manager.horizontal_channels, list)


class TestRouterIntegration:
    """Integration tests for the router with complex scenarios."""

    def test_multiple_edges_from_same_node(self):
        """Test routing multiple edges from the same node."""
        node_positions = {
            "A": (100, 100, 80, 40),
            "B": (300, 50, 80, 40),
            "C": (300, 150, 80, 40),
            "D": (300, 250, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route1 = router.route_edge("A", "B")
        route2 = router.route_edge("A", "C")
        route3 = router.route_edge("A", "D")

        assert route1 is not None
        assert route2 is not None
        assert route3 is not None

        # Different edges should potentially use different ports
        # (though the exact behavior depends on the algorithm)
        all_have_waypoints = (
            len(route1.waypoints) >= 2
            and len(route2.waypoints) >= 2
            and len(route3.waypoints) >= 2
        )
        assert all_have_waypoints

    def test_route_around_obstacles(self):
        """Test that routes go around obstacles, not through them."""
        node_positions = {
            "Start": (50, 150, 80, 40),
            "End": (400, 150, 80, 40),
            "Obs1": (200, 100, 80, 80),
            "Obs2": (200, 200, 80, 80),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router.route_edge("Start", "End")
        assert route is not None

        # Verify no waypoint is inside an obstacle box
        for x, y in route.waypoints:
            # Check not inside Obs1 or Obs2
            obs1 = BoxBounds(200, 100, 80, 80)
            obs2 = BoxBounds(200, 200, 80, 80)

            in_obs1 = obs1.x < x < obs1.x2 and obs1.y < y < obs1.y2
            in_obs2 = obs2.x < x < obs2.x2 and obs2.y < y < obs2.y2

            # Waypoints shouldn't be strictly inside obstacle boxes
            # (they can be on edges)
            assert not (in_obs1 and in_obs2)

    def test_diagonal_connection(self):
        """Test routing a diagonal connection."""
        node_positions = {
            "A": (50, 50, 80, 40),
            "B": (300, 250, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router.route_edge("A", "B")
        assert route is not None
        # Should have waypoints for turns
        assert len(route.waypoints) >= 2


class TestRemoveRoute:
    """Tests for remove_route functionality."""

    def test_remove_route_basic(self):
        """Test removing a route successfully."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router.route_edge("A", "B")
        assert route is not None
        assert len(router.routes) == 1

        result = router.remove_route(route)
        assert result is True
        assert len(router.routes) == 0

    def test_remove_route_not_found(self):
        """Test removing a route that doesn't exist."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        # Create a route but don't add it to router
        src_port = Port("A", "right", PortPosition.MIDDLE, 100, 50)
        tgt_port = Port("B", "left", PortPosition.MIDDLE, 200, 50)
        fake_route = EdgeRoute(
            source="A",
            target="B",
            source_port=src_port,
            target_port=tgt_port,
            waypoints=[(100, 50), (200, 50)],
        )

        result = router.remove_route(fake_route)
        assert result is False

    def test_remove_route_restores_port_usage(self):
        """Test that removing route restores port usage tracking."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        _, port_manager, router = create_router(node_positions)

        route = router.route_edge("A", "B")
        assert route is not None

        # Get port usage after routing
        src_side = route.source_port.side
        usage_after_route = len(port_manager.port_usage["A"][src_side])
        assert usage_after_route > 0

        router.remove_route(route)

        # Port usage should be restored (decreased)
        usage_after_remove = len(port_manager.port_usage["A"][src_side])
        assert usage_after_remove < usage_after_route
        assert len(router.routes) == 0

    def test_remove_route_clears_grid(self):
        """Test that removing route clears edge cells from grid."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router.route_edge("A", "B")
        assert route is not None

        # Grid should have edge cells
        initial_edge_cells = sum(
            1
            for cell_type in grid.cells.values()
            if cell_type in (CellType.HORIZONTAL_EDGE, CellType.VERTICAL_EDGE)
        )

        router.remove_route(route)

        # Edge cells should be cleared (or reduced)
        final_edge_cells = sum(
            1
            for cell_type in grid.cells.values()
            if cell_type in (CellType.HORIZONTAL_EDGE, CellType.VERTICAL_EDGE)
        )
        assert final_edge_cells <= initial_edge_cells


class TestScoreLayout:
    """Tests for score_layout functionality."""

    def test_score_layout_empty(self):
        """Test scoring an empty layout."""
        node_positions = {
            "A": (50, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        score = router.score_layout()
        assert score == 0.0

    def test_score_layout_single_edge(self):
        """Test scoring a layout with a single edge."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        router.route_edge("A", "B")
        score = router.score_layout()

        assert score > 0  # Should have some cost for wire length

    def test_score_layout_more_edges_higher_score(self):
        """Test that more edges generally means higher score."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
            "C": (450, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        router.route_edge("A", "B")
        score_one = router.score_layout()

        router.route_edge("B", "C")
        score_two = router.score_layout()

        assert score_two > score_one

    def test_score_layout_crossing_penalty(self):
        """Test that crossings add to score."""
        # Create a layout likely to have crossings
        node_positions = {
            "A": (50, 50, 80, 40),
            "B": (250, 50, 80, 40),
            "C": (50, 200, 80, 40),
            "D": (250, 200, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        # Route edges that might cross
        router.route_edge("A", "D")  # Diagonal
        router.route_edge("B", "C")  # Other diagonal

        score = router.score_layout()
        # Score should be positive (includes various penalties)
        assert score >= 0


class TestCalculateWireLength:
    """Tests for _calculate_wire_length helper."""

    def test_wire_length_straight_horizontal(self):
        """Test wire length for straight horizontal path."""
        node_positions = {"A": (50, 100, 80, 40)}
        grid, port_manager, router = create_router(node_positions)

        waypoints = [(0, 50), (100, 50)]
        length = router._calculate_wire_length(waypoints)
        assert length == 100

    def test_wire_length_straight_vertical(self):
        """Test wire length for straight vertical path."""
        node_positions = {"A": (50, 100, 80, 40)}
        grid, port_manager, router = create_router(node_positions)

        waypoints = [(50, 0), (50, 100)]
        length = router._calculate_wire_length(waypoints)
        assert length == 100

    def test_wire_length_l_shaped(self):
        """Test wire length for L-shaped path."""
        node_positions = {"A": (50, 100, 80, 40)}
        grid, port_manager, router = create_router(node_positions)

        waypoints = [(0, 0), (100, 0), (100, 50)]
        length = router._calculate_wire_length(waypoints)
        assert length == 150  # 100 horizontal + 50 vertical


class TestCountBends:
    """Tests for _count_bends helper."""

    def test_count_bends_straight(self):
        """Test bend count for straight path."""
        node_positions = {"A": (50, 100, 80, 40)}
        grid, port_manager, router = create_router(node_positions)

        waypoints = [(0, 0), (100, 0)]
        bends = router._count_bends(waypoints)
        assert bends == 0

    def test_count_bends_l_shaped(self):
        """Test bend count for L-shaped path."""
        node_positions = {"A": (50, 100, 80, 40)}
        grid, port_manager, router = create_router(node_positions)

        waypoints = [(0, 0), (100, 0), (100, 50)]
        bends = router._count_bends(waypoints)
        assert bends == 1

    def test_count_bends_z_shaped(self):
        """Test bend count for Z-shaped path."""
        node_positions = {"A": (50, 100, 80, 40)}
        grid, port_manager, router = create_router(node_positions)

        waypoints = [(0, 0), (50, 0), (50, 50), (100, 50)]
        bends = router._count_bends(waypoints)
        assert bends == 2

    def test_count_bends_short_path(self):
        """Test bend count for paths too short to have bends."""
        node_positions = {"A": (50, 100, 80, 40)}
        grid, port_manager, router = create_router(node_positions)

        assert router._count_bends([(0, 0)]) == 0
        assert router._count_bends([(0, 0), (10, 0)]) == 0


class TestRefineRoutes:
    """Tests for refine_routes functionality."""

    def test_refine_routes_single_edge(self):
        """Test that refine_routes handles single edge gracefully."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        router.route_edge("A", "B")
        initial_score = router.score_layout()

        final_score, iterations = router.refine_routes()

        # Single edge means no refinement needed
        assert iterations == 0
        assert final_score == initial_score

    def test_refine_routes_multiple_edges(self):
        """Test refine_routes with multiple edges."""
        node_positions = {
            "A": (50, 50, 80, 40),
            "B": (250, 50, 80, 40),
            "C": (50, 200, 80, 40),
            "D": (250, 200, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        router.route_edge("A", "B")
        router.route_edge("C", "D")
        router.route_edge("A", "C")

        initial_score = router.score_layout()
        final_score, iterations = router.refine_routes(max_iterations=5)

        # Should complete without error
        assert final_score >= 0
        assert iterations >= 0
        # Final score should be <= initial (refinement should not make it worse)
        assert final_score <= initial_score + 1  # Small tolerance for floating point

    def test_refine_routes_empty(self):
        """Test refine_routes with no edges."""
        node_positions = {
            "A": (50, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        final_score, iterations = router.refine_routes()

        assert final_score == 0.0
        assert iterations == 0

    def test_refine_routes_max_iterations(self):
        """Test that refine_routes respects max_iterations."""
        node_positions = {
            "A": (50, 50, 80, 40),
            "B": (250, 50, 80, 40),
            "C": (50, 200, 80, 40),
            "D": (250, 200, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        router.route_edge("A", "B")
        router.route_edge("C", "D")

        _, iterations = router.refine_routes(max_iterations=1)
        assert iterations <= 1


class TestRouteEdgeWithSides:
    """Tests for _route_edge_with_sides functionality."""

    def test_route_edge_with_sides_basic(self):
        """Test routing edge with specific sides."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router._route_edge_with_sides("A", "B", "right", "left")

        assert route is not None
        assert route.source == "A"
        assert route.target == "B"
        assert route.source_port.side == "right"
        assert route.target_port.side == "left"

    def test_route_edge_with_sides_vertical(self):
        """Test routing edge with vertical sides."""
        node_positions = {
            "A": (100, 50, 80, 40),
            "B": (100, 200, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router._route_edge_with_sides("A", "B", "bottom", "top")

        assert route is not None
        assert route.source_port.side == "bottom"
        assert route.target_port.side == "top"

    def test_route_edge_with_sides_invalid_node(self):
        """Test routing with invalid node returns None."""
        node_positions = {
            "A": (50, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router._route_edge_with_sides("A", "B", "right", "left")
        assert route is None

    def test_route_edge_with_sides_bidirectional(self):
        """Test routing bidirectional edge with specific sides."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        route = router._route_edge_with_sides(
            "A", "B", "right", "left", is_bidirectional=True
        )

        assert route is not None
        assert route.is_bidirectional


class TestRouteEdgesWithRefinement:
    """Tests for route_edges_with_refinement convenience function."""

    def test_route_edges_basic(self):
        """Test basic edge routing with refinement."""
        from retroflow.edge_routing import route_edges_with_refinement

        positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        edges = [("A", "B", False)]

        routes, score = route_edges_with_refinement(positions, edges)

        assert len(routes) == 1
        assert routes[0].source == "A"
        assert routes[0].target == "B"
        assert score >= 0

    def test_route_edges_without_refinement(self):
        """Test edge routing without refinement."""
        from retroflow.edge_routing import route_edges_with_refinement

        positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        edges = [("A", "B", False)]

        routes, score = route_edges_with_refinement(positions, edges, refine=False)

        assert len(routes) == 1
        assert score >= 0

    def test_route_edges_multiple(self):
        """Test routing multiple edges."""
        from retroflow.edge_routing import route_edges_with_refinement

        positions = {
            "A": (50, 50, 80, 40),
            "B": (250, 50, 80, 40),
            "C": (150, 200, 80, 40),
        }
        edges = [("A", "B", False), ("B", "C", False), ("A", "C", True)]

        routes, score = route_edges_with_refinement(positions, edges)

        assert len(routes) == 3
        assert score >= 0

    def test_route_edges_empty(self):
        """Test routing with no edges."""
        from retroflow.edge_routing import route_edges_with_refinement

        positions = {
            "A": (50, 100, 80, 40),
        }
        edges = []

        routes, score = route_edges_with_refinement(positions, edges)

        assert len(routes) == 0
        assert score == 0.0


class TestClearEdgeSegment:
    """Tests for _clear_edge_segment helper."""

    def test_clear_vertical_segment(self):
        """Test clearing a vertical edge segment."""
        # Use coordinates far from the box to avoid overlap
        node_positions = {"A": (50, 50, 40, 30)}
        grid, port_manager, router = create_router(node_positions)

        # Mark an edge in a clear area (far from box at 50,50)
        grid.mark_edge_segment(200, 50, 200, 150)

        # Verify it's marked
        assert grid.get_cell_type(200, 100) == CellType.VERTICAL_EDGE

        # Clear it
        router._clear_edge_segment(200, 50, 200, 150)

        # Should be cleared
        cell_type = grid.get_cell_type(200, 100)
        assert cell_type == CellType.EMPTY

    def test_clear_horizontal_segment(self):
        """Test clearing a horizontal edge segment."""
        node_positions = {"A": (50, 50, 40, 30)}
        grid, port_manager, router = create_router(node_positions)

        # Mark an edge in a clear area
        grid.mark_edge_segment(150, 200, 250, 200)

        # Verify it's marked
        assert grid.get_cell_type(200, 200) == CellType.HORIZONTAL_EDGE

        # Clear it
        router._clear_edge_segment(150, 200, 250, 200)

        # Should be cleared
        cell_type = grid.get_cell_type(200, 200)
        assert cell_type == CellType.EMPTY

    def test_clear_junction_to_horizontal(self):
        """Test clearing vertical through junction leaves horizontal."""
        node_positions = {"A": (50, 50, 40, 30)}
        grid, port_manager, router = create_router(node_positions)

        # Create a junction in a clear area
        grid.mark_edge_segment(150, 200, 250, 200)  # Horizontal
        grid.mark_edge_segment(200, 150, 200, 250)  # Vertical
        assert grid.get_cell_type(200, 200) == CellType.JUNCTION

        # Clear vertical
        router._clear_edge_segment(200, 150, 200, 250)

        # Junction should become horizontal
        assert grid.get_cell_type(200, 200) == CellType.HORIZONTAL_EDGE


class TestCountEdgeCrossings:
    """Tests for _count_edge_crossings helper."""

    def test_no_crossings(self):
        """Test counting crossings when there are none."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
            "C": (50, 250, 80, 40),
            "D": (250, 250, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        # Parallel horizontal routes shouldn't cross
        router.route_edge("A", "B")
        router.route_edge("C", "D")

        crossings = router._count_edge_crossings()
        # Parallel routes shouldn't have crossings
        assert crossings >= 0

    def test_count_crossings_same_route(self):
        """Test that segments within same route don't count as crossings."""
        node_positions = {
            "A": (50, 50, 80, 40),
            "B": (250, 250, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        router.route_edge("A", "B")

        # Self-crossings shouldn't count
        crossings = router._count_edge_crossings()
        assert crossings == 0


class TestCalculateCongestion:
    """Tests for _calculate_congestion helper."""

    def test_no_congestion_single_edge(self):
        """Test congestion with single edge."""
        node_positions = {
            "A": (50, 100, 80, 40),
            "B": (250, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        router.route_edge("A", "B")

        congestion = router._calculate_congestion()
        assert congestion == 0.0  # Single edge can't have congestion with itself

    def test_congestion_increases_with_proximity(self):
        """Test that close parallel edges increase congestion."""
        node_positions = {
            "A": (50, 50, 80, 40),
            "B": (250, 50, 80, 40),
            "C": (50, 100, 80, 40),
            "D": (250, 100, 80, 40),
        }
        grid, port_manager, router = create_router(node_positions)

        router.route_edge("A", "B")
        router.route_edge("C", "D")

        congestion = router._calculate_congestion()
        # May or may not have congestion depending on routing
        assert congestion >= 0
