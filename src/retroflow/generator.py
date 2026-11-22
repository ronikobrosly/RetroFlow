"""
Main flowchart generator module.

This module provides the FlowchartGenerator class, which is the primary entry point
for creating ASCII flowcharts. It orchestrates the parsing, layout, positioning,
edge routing, and rendering pipeline to produce beautiful ASCII flowcharts from
simple text descriptions.

Two renderers sit behind ``generate()``. The classic one draws edges one at a
time and gives small diagrams their familiar look. The planned one
(``route_planner`` + ``wire_grid``) plans every edge before drawing and is
used whenever the classic picture would not read back as the graph that was
asked for. ``checker`` decides between them.

The generator supports:
- Top-to-bottom (TB) and left-to-right (LR) flow directions
- Box shadows and rounded corners
- Compact and expanded box styles
- Cycle detection with back-edge routing
- PNG and text file export
- Debug mode for tracing rendering decisions

Example:
    >>> from retroflow import FlowchartGenerator
    >>> generator = FlowchartGenerator()
    >>> flowchart = generator.generate('''
    ...     A -> B
    ...     B -> C
    ... ''')
    >>> print(flowchart)

Debug Mode Example:
    >>> generator = FlowchartGenerator()
    >>> flowchart = generator.generate("A -> B", debug=True)
    >>> trace = generator.get_trace()
    >>> print(trace.summary())
"""

from typing import Dict, List, Optional, Tuple, Union

from .checker import DiagramReport, analyze_rendering, normalize_name
from .debug import TracedCanvas
from .edge_drawing import EdgeDrawer
from .export import FlowchartExporter
from .layout import LayoutResult, NetworkXLayout, NodeLayout
from .models import ColumnBoundary, GroupBoundary, LayerBoundary
from .parser import Parser, ParseResult
from .positioning import PositionCalculator
from .renderer import (
    BoxDimensions,
    BoxRenderer,
    Canvas,
    GroupBoxRenderer,
    TitleRenderer,
)
from .route_planner import PlannerOptions, RoutePlanner, assign_ranks
from .tracer import RenderTrace

# Reason recorded for each wire glyph when tracing (see TracedCanvas).
WIRE_REASONS = {
    "─": "wire_horizontal",
    "│": "wire_vertical",
    "┌": "wire_corner",
    "┐": "wire_corner",
    "└": "wire_corner",
    "┘": "wire_corner",
    "├": "wire_junction",
    "┤": "wire_junction",
    "┬": "wire_junction",
    "┴": "wire_junction",
    "┼": "wire_crossing",
    "▼": "arrow_down",
    "▲": "arrow_up",
    "►": "arrow_right",
    "◄": "arrow_left",
}


class FlowchartGenerator:
    """
    Generate ASCII flowcharts from simple text descriptions.

    This is the main class for creating flowcharts. It coordinates parsing,
    layout, positioning, and rendering to produce ASCII art flowcharts.

    Example:
        >>> generator = FlowchartGenerator()
        >>> flowchart = generator.generate('''
        ...     A -> B
        ...     B -> C
        ... ''')
        >>> print(flowchart)
    """

    def __init__(
        self,
        max_text_width: int = 22,
        min_box_width: int = 10,
        horizontal_spacing: int = 12,
        vertical_spacing: int = 3,
        shadow: bool = True,
        rounded: bool = False,
        compact: bool = True,
        font: Optional[str] = None,
        title: Optional[str] = None,
        direction: str = "TB",
    ):
        """
        Initialize the flowchart generator.

        Args:
            max_text_width: Maximum width for text inside boxes before wrapping.
            min_box_width: Minimum box width.
            horizontal_spacing: Space between boxes horizontally.
            vertical_spacing: Space between boxes vertically.
            shadow: Whether to draw box shadows.
            rounded: Whether to use rounded corners instead of square.
            compact: Whether to use compact boxes (no vertical padding).
            font: Font name for PNG output (e.g., "Cascadia Code", "Monaco").
            title: Optional title to display above the flowchart.
            direction: Flow direction - "TB" (top-to-bottom) or "LR" (left-to-right).
        """
        self.max_text_width = max_text_width
        self.min_box_width = min_box_width
        self.horizontal_spacing = horizontal_spacing
        self.vertical_spacing = vertical_spacing
        self.shadow = shadow
        self.rounded = rounded
        self.compact = compact
        self.font = font
        self.title = title
        self.direction = direction.upper()

        if self.direction not in ("TB", "LR"):
            raise ValueError(
                "direction must be 'TB' (top-to-bottom) or 'LR' (left-to-right)"
            )

        # Initialize component objects
        self.parser = Parser()
        self.layout_engine = NetworkXLayout()
        self.box_renderer = BoxRenderer(
            max_text_width=max_text_width,
            shadow=shadow,
            rounded=rounded,
            compact=compact,
        )
        self.group_box_renderer = GroupBoxRenderer(shadow=shadow)
        self.title_renderer = TitleRenderer()

        # Initialize helper objects
        self.position_calculator = PositionCalculator(
            box_renderer=self.box_renderer,
            min_box_width=min_box_width,
            horizontal_spacing=horizontal_spacing,
            vertical_spacing=vertical_spacing,
            shadow=shadow,
        )
        self.edge_drawer = EdgeDrawer(
            position_calculator=self.position_calculator,
            shadow=shadow,
        )
        self.exporter = FlowchartExporter(default_font=font)

        # Debug trace storage (populated when debug=True in generate())
        self._last_trace: Optional[RenderTrace] = None

        # Which renderer produced the last diagram: "classic" or "planned".
        self.last_renderer: Optional[str] = None

    def get_trace(self) -> Optional[RenderTrace]:
        """
        Get the trace from the last generate() call with debug=True.

        Returns:
            The RenderTrace from the last debug run, or None if debug
            mode was not used or generate() hasn't been called.

        Example:
            >>> generator = FlowchartGenerator()
            >>> result = generator.generate("A -> B", debug=True)
            >>> trace = generator.get_trace()
            >>> print(trace.summary())
        """
        return self._last_trace

    def generate(
        self, input_text: str, title: Optional[str] = None, debug: bool = False
    ) -> str:
        """
        Generate an ASCII flowchart from input text.

        Args:
            input_text: Multi-line string with connections like "A -> B".
            title: Optional title to display (overrides instance title).
            debug: If True, capture detailed trace information about the
                   rendering process. Access via get_trace() after calling.

        Returns:
            ASCII art flowchart as a string.

        How the picture is chosen:
            Two renderers can draw a diagram, and a checker picks between
            them by reading the finished picture back::

                input ──► classic renderer ──► reads back clean? ── yes ──► done
                                                      │ no
                                                      ▼
                          planned renderer ──► better than classic? ──► done

            The classic renderer draws each edge on its own. Small diagrams
            come out exactly as they always have. When its picture would be
            misleading (fused lines, missing arrowheads, cramped strokes), the
            planned renderer routes all edges together instead. After the
            call, ``last_renderer`` says which one was used.

        Debug Mode:
            When debug=True, a detailed trace is captured that includes:
            - Pipeline stages (parse, layout, positions, etc.)
            - Canvas snapshots at each stage
            - Every character placement with coordinates and reasons

            Access the trace via get_trace() after calling generate():

            >>> generator = FlowchartGenerator()
            >>> result = generator.generate("A -> B", debug=True)
            >>> trace = generator.get_trace()
            >>> print(trace.summary())
            >>> trace.dump_to_file("debug_trace.txt")
        """
        self._last_trace = None

        # Use provided title or fall back to instance title
        effective_title = title if title is not None else self.title

        # Parse input (including groups)
        parse_result = self.parser.parse_with_groups(input_text)
        expected_edges = {
            (normalize_name(source), normalize_name(target))
            for source, target in parse_result.connections
        }

        def new_trace() -> Optional[RenderTrace]:
            if not debug:
                return None
            return RenderTrace(input_text=input_text, direction=self.direction)

        # The classic renderer goes first. Whatever it draws cleanly is
        # returned exactly as it always was.
        classic_trace = new_trace()
        classic_output, classic_base = self._render_classic(
            parse_result, effective_title, classic_trace
        )
        classic_report = analyze_rendering(classic_base, classic_output, expected_edges)
        if not classic_report.issues:
            return self._finish_generate(
                "classic", classic_output, classic_trace, classic_report, None
            )

        # Otherwise the diagram is planned edge by edge before it is drawn.
        # The planned picture only replaces the classic one when it checks
        # out better, so an unexpected failure in the planner must never cost
        # the caller the diagram they would have got anyway.
        planned_trace = new_trace()
        try:
            planned_output, planned_base = self._render_planned(
                parse_result, effective_title, planned_trace
            )
        except Exception as error:  # noqa: BLE001 - see comment above
            return self._finish_generate(
                "classic",
                classic_output,
                classic_trace,
                classic_report,
                None,
                planner_error=f"{type(error).__name__}: {error}",
            )
        planned_report = analyze_rendering(planned_base, planned_output, expected_edges)

        def badness(report: DiagramReport) -> Tuple[int, int]:
            return (len(report.errors), len(report.warnings))

        if badness(planned_report) < badness(classic_report):
            return self._finish_generate(
                "planned", planned_output, planned_trace, planned_report, classic_report
            )
        return self._finish_generate(
            "classic", classic_output, classic_trace, classic_report, planned_report
        )

    def _finish_generate(
        self,
        renderer: str,
        output: str,
        trace: Optional[RenderTrace],
        report: DiagramReport,
        other_report: Optional[DiagramReport],
        planner_error: Optional[str] = None,
    ) -> str:
        """Record which renderer won (debug mode only) and return its output."""
        self.last_renderer = renderer
        if trace is not None:
            trace.add_stage(
                "renderer_selected",
                {
                    "renderer": renderer,
                    "issues": dict(report.counts()),
                    "other_renderer_issues": (
                        dict(other_report.counts()) if other_report else None
                    ),
                    "planner_error": planner_error,
                },
            )
            self._last_trace = trace
        return output

    def _render_classic(
        self,
        parse_result: ParseResult,
        effective_title: Optional[str],
        trace: Optional[RenderTrace],
    ) -> Tuple[str, List[str]]:
        """
        Draw the diagram with the original edge drawer.

        Each edge is routed and painted on its own. This is what produces the
        familiar look of small diagrams; busy diagrams can come out with
        fused or broken lines, which is why ``generate`` checks the result.

        Args:
            parse_result: Parsed connections and groups.
            effective_title: Title to draw above the diagram, if any.
            trace: Trace to fill in, or None when not in debug mode.

        Returns:
            (finished diagram, canvas rows as they were before edges).
        """
        connections = parse_result.connections
        groups = parse_result.groups

        if trace:
            trace.add_stage(
                "parse",
                {
                    "connections": connections,
                    "groups": [(g.name, g.members) for g in groups],
                },
            )

        # Run layout
        layout_result = self.layout_engine.layout(connections)

        if trace:
            trace.add_stage(
                "layout",
                {
                    "layers": layout_result.layers,
                    "back_edges": list(layout_result.back_edges),
                    "node_positions": {
                        name: (node.layer, node.position)
                        for name, node in layout_result.nodes.items()
                    },
                },
            )

        # Calculate box dimensions for each node
        box_dimensions = self.position_calculator.calculate_all_box_dimensions(
            layout_result
        )

        if trace:
            trace.add_stage(
                "dimensions",
                {
                    "box_dimensions": {
                        name: (dims.width, dims.height)
                        for name, dims in box_dimensions.items()
                    },
                },
            )

        # Calculate actual pixel positions - leave margin for back edges
        # Each back edge needs 3 chars of space, plus 4 for min line before arrow
        num_back_edges = len(layout_result.back_edges)
        back_edge_margin = (4 + num_back_edges * 3) if num_back_edges > 0 else 0

        # Add extra margin if groups are present to ensure edges don't run
        # too close to group boundaries
        if groups:
            from .positioning import GROUP_EDGE_MARGIN

            back_edge_margin = max(back_edge_margin, GROUP_EDGE_MARGIN + 2)

        if groups:
            # Use group-aware positioning
            box_positions = self.position_calculator.calculate_group_aware_positions(
                layout_result,
                box_dimensions,
                groups,
                direction=self.direction,
                margin=back_edge_margin,
            )
        elif self.direction == "LR":
            box_positions = self.position_calculator.calculate_positions_horizontal(
                layout_result, box_dimensions, top_margin=back_edge_margin
            )
        else:
            box_positions = self.position_calculator.calculate_positions(
                layout_result, box_dimensions, left_margin=back_edge_margin
            )

        # Calculate layer boundaries for safe edge routing
        layer_boundaries = self.position_calculator.calculate_layer_boundaries(
            layout_result, box_dimensions
        )

        # Calculate column boundaries for LR mode
        column_boundaries: List[ColumnBoundary] = []
        if self.direction == "LR":
            column_boundaries = self.position_calculator.calculate_column_boundaries(
                layout_result, box_dimensions
            )

        if trace:
            trace.add_stage(
                "positions",
                {
                    "box_positions": dict(box_positions),
                    "back_edge_margin": back_edge_margin,
                    "layer_boundaries": [
                        (
                            lb.layer_idx,
                            lb.top_y,
                            lb.bottom_y,
                            lb.gap_start_y,
                            lb.gap_end_y,
                        )
                        for lb in layer_boundaries
                    ],
                },
            )

        # Calculate group boundaries (if any groups defined)
        # We calculate them here to determine if we need offsets for negative coords
        group_boundaries: List[GroupBoundary] = []
        group_x_offset = 0
        group_y_offset = 0

        if groups:
            temp_boundaries = self.position_calculator.calculate_group_boundaries(
                groups, box_positions, box_dimensions
            )
            # Find minimum x/y to determine offset needed
            for gb in temp_boundaries:
                if gb.x < 0:
                    group_x_offset = max(group_x_offset, abs(gb.x))
                if gb.y < 0:
                    group_y_offset = max(group_y_offset, abs(gb.y))

        # Apply group offset to box positions if needed
        if group_x_offset > 0 or group_y_offset > 0:
            box_positions = {
                name: (x + group_x_offset, y + group_y_offset)
                for name, (x, y) in box_positions.items()
            }
            # Recalculate group boundaries with offset positions
            if groups:
                group_boundaries = self.position_calculator.calculate_group_boundaries(
                    groups, box_positions, box_dimensions
                )
            # Offset layer boundaries for TB mode
            layer_boundaries = [
                LayerBoundary(
                    layer_idx=lb.layer_idx,
                    top_y=lb.top_y + group_y_offset,
                    bottom_y=lb.bottom_y + group_y_offset,
                    gap_start_y=lb.gap_start_y + group_y_offset,
                    gap_end_y=lb.gap_end_y + group_y_offset,
                )
                for lb in layer_boundaries
            ]
            # Offset column boundaries for LR mode
            if self.direction == "LR":
                column_boundaries = [
                    ColumnBoundary(
                        layer_idx=cb.layer_idx,
                        left_x=cb.left_x + group_x_offset,
                        right_x=cb.right_x + group_x_offset,
                        gap_start_x=cb.gap_start_x + group_x_offset,
                        gap_end_x=cb.gap_end_x + group_x_offset,
                    )
                    for cb in column_boundaries
                ]
        else:
            # Just calculate group boundaries with current positions
            if groups:
                group_boundaries = self.position_calculator.calculate_group_boundaries(
                    groups, box_positions, box_dimensions
                )

        # Resolve any overlapping group boundaries
        if len(group_boundaries) >= 2:
            box_positions, group_boundaries = (
                self.position_calculator.resolve_group_overlaps(
                    group_boundaries,
                    box_positions,
                    box_dimensions,
                    direction=self.direction,
                )
            )

            # Recalculate canvas size after overlap resolution
            # (groups may have been shifted)

        # Calculate canvas size from nodes
        canvas_width, canvas_height = self.position_calculator.calculate_canvas_size(
            box_dimensions, box_positions
        )

        # Expand canvas to fit group boxes (which may extend beyond nodes)
        for gb in group_boundaries:
            group_right = gb.x + gb.width + (2 if self.shadow else 0)
            group_bottom = gb.y + gb.height + (2 if self.shadow else 0)
            canvas_width = max(canvas_width, group_right)
            canvas_height = max(canvas_height, group_bottom)

        # Calculate title dimensions and offset
        title_height = 0
        title_width = 0
        diagram_x_offset = 0
        title_x_offset = 0

        if effective_title:
            title_width, title_height = self.title_renderer.calculate_title_dimensions(
                effective_title
            )
            title_height += 2  # Add spacing below title

            # Determine centering: center title above diagram or diagram under title
            if title_width > canvas_width:
                # Title is wider - center diagram under title
                diagram_x_offset = (title_width - canvas_width) // 2
                canvas_width = title_width
            else:
                # Diagram is wider - center title above diagram
                title_x_offset = (canvas_width - title_width) // 2

        # Create canvas with padding and title space
        canvas: Union[Canvas, TracedCanvas] = Canvas(
            canvas_width + 5, canvas_height + title_height + 5
        )

        if trace:
            trace.add_stage(
                "canvas_created",
                {
                    "canvas_width": canvas_width + 5,
                    "canvas_height": canvas_height + title_height + 5,
                    "title_height": title_height,
                },
                canvas,
            )
            # Wrap canvas with TracedCanvas for character-level tracing
            canvas = TracedCanvas(canvas, trace)

        # Draw title if present, centered above the diagram
        if effective_title:
            if isinstance(canvas, TracedCanvas):
                canvas.set_source("TitleRenderer.draw_title")
            self.title_renderer.draw_title(
                canvas, title_x_offset, 0, effective_title, title_width
            )

        # Offset box positions for title and centering
        if title_height > 0 or diagram_x_offset > 0:
            box_positions = {
                name: (x + diagram_x_offset, y + title_height)
                for name, (x, y) in box_positions.items()
            }
            # Also offset layer boundaries by title height
            if title_height > 0:
                layer_boundaries = [
                    LayerBoundary(
                        layer_idx=lb.layer_idx,
                        top_y=lb.top_y + title_height,
                        bottom_y=lb.bottom_y + title_height,
                        gap_start_y=lb.gap_start_y + title_height,
                        gap_end_y=lb.gap_end_y + title_height,
                    )
                    for lb in layer_boundaries
                ]
                # And column boundaries for LR mode
                if self.direction == "LR" and diagram_x_offset > 0:
                    column_boundaries = [
                        ColumnBoundary(
                            layer_idx=cb.layer_idx,
                            left_x=cb.left_x + diagram_x_offset,
                            right_x=cb.right_x + diagram_x_offset,
                            gap_start_x=cb.gap_start_x + diagram_x_offset,
                            gap_end_x=cb.gap_end_x + diagram_x_offset,
                        )
                        for cb in column_boundaries
                    ]

        # Recalculate group boundaries after box positions are offset
        if groups:
            group_boundaries = self.position_calculator.calculate_group_boundaries(
                groups, box_positions, box_dimensions
            )

        # Draw group boxes FIRST (so nodes appear on top)
        if group_boundaries:
            if isinstance(canvas, TracedCanvas):
                canvas.set_source("GroupBoxRenderer.draw_group_box")
            self._draw_groups(canvas, group_boundaries)

            if trace:
                underlying = (
                    canvas._canvas if isinstance(canvas, TracedCanvas) else canvas
                )
                trace.add_stage(
                    "groups_drawn",
                    {
                        "num_groups": len(group_boundaries),
                    },
                    underlying,
                )

        # Draw node boxes
        if isinstance(canvas, TracedCanvas):
            canvas.set_source("BoxRenderer.draw_box")
        self._draw_boxes(canvas, box_dimensions, box_positions, layout_result)

        base_lines = self._snapshot(canvas)
        if trace:
            # Get underlying canvas for snapshot
            underlying = canvas._canvas if isinstance(canvas, TracedCanvas) else canvas
            trace.add_stage(
                "boxes_drawn",
                {
                    "num_boxes": len(box_positions),
                },
                underlying,
            )

        # Draw forward edges with layer-aware routing
        if isinstance(canvas, TracedCanvas):
            canvas.set_source("EdgeDrawer.draw_edges")
        if self.direction == "LR":
            self.edge_drawer.draw_edges_horizontal(
                canvas,
                layout_result,
                box_dimensions,
                box_positions,
                column_boundaries,
                title_height,
            )
        else:
            self.edge_drawer.draw_edges(
                canvas, layout_result, box_dimensions, box_positions, layer_boundaries
            )

        if trace:
            underlying = canvas._canvas if isinstance(canvas, TracedCanvas) else canvas
            trace.add_stage(
                "forward_edges_drawn",
                {
                    "num_forward_edges": len(
                        [
                            e
                            for e in layout_result.edges
                            if e not in layout_result.back_edges
                        ]
                    ),
                },
                underlying,
            )

        # Draw back edges along the margin
        if layout_result.back_edges:
            if isinstance(canvas, TracedCanvas):
                canvas.set_source("EdgeDrawer.draw_back_edges")
            if self.direction == "LR":
                self.edge_drawer.draw_back_edges_horizontal(
                    canvas, layout_result, box_dimensions, box_positions, title_height
                )
            else:
                self.edge_drawer.draw_back_edges(
                    canvas, layout_result, box_dimensions, box_positions
                )

            if trace:
                if isinstance(canvas, TracedCanvas):
                    underlying = canvas._canvas
                else:
                    underlying = canvas
                trace.add_stage(
                    "back_edges_drawn",
                    {
                        "num_back_edges": len(layout_result.back_edges),
                    },
                    underlying,
                )

        return canvas.render(), base_lines

    def _render_planned(
        self,
        parse_result: ParseResult,
        effective_title: Optional[str],
        trace: Optional[RenderTrace],
    ) -> Tuple[str, List[str]]:
        """
        Draw the diagram with every edge planned before anything is painted.

            ranks ──► lanes ──► ports ──► tracks ──► wire grid ──► glyphs

        Ports, lanes and tracks are handed out so that unrelated edges never
        share a cell, and each glyph is derived from the lines that actually
        pass through it (see ``route_planner`` and ``wire_grid``).

        Args:
            parse_result: Parsed connections and groups.
            effective_title: Title to draw above the diagram, if any.
            trace: Trace to fill in, or None when not in debug mode.

        Returns:
            (finished diagram, canvas rows as they were before edges).
        """
        connections = parse_result.connections
        groups = parse_result.groups
        if trace:
            trace.add_stage(
                "parse",
                {
                    "connections": connections,
                    "groups": [(g.name, g.members) for g in groups],
                },
            )

        layers = assign_ranks(connections, groups, self.layout_engine)
        if trace:
            trace.add_stage("layout", {"layers": layers})

        nodes = LayoutResult(
            nodes={name: NodeLayout(name=name) for layer in layers for name in layer}
        )
        natural_dimensions = self.position_calculator.calculate_all_box_dimensions(
            nodes
        )
        planner = RoutePlanner(
            PlannerOptions(
                direction=self.direction,
                horizontal_spacing=self.horizontal_spacing,
                vertical_spacing=self.vertical_spacing,
                shadow=self.shadow,
            )
        )
        plan = planner.plan(connections, groups, layers, natural_dimensions)

        if trace:
            trace.add_stage(
                "dimensions",
                {
                    "box_dimensions": {
                        name: (dims.width, dims.height)
                        for name, dims in plan.box_dimensions.items()
                    },
                },
            )
            trace.add_stage(
                "routes_planned",
                {
                    "layers": plan.layers,
                    "tracks_per_channel": plan.tracks_per_channel,
                    "crossings": plan.grid.crossing_count(),
                    "conflicts": [str(c) for c in plan.grid.conflicts],
                },
            )

        # Centre the title over the diagram, or the diagram under the title.
        title_height = 0
        title_width = 0
        diagram_x_offset = 0
        title_x_offset = 0
        canvas_width = plan.width
        if effective_title:
            title_width, title_height = self.title_renderer.calculate_title_dimensions(
                effective_title
            )
            title_height += 2  # Add spacing below title
            if title_width > canvas_width:
                diagram_x_offset = (title_width - canvas_width) // 2
                canvas_width = title_width
            else:
                title_x_offset = (canvas_width - title_width) // 2

        box_positions = {
            name: (x + diagram_x_offset, y + title_height)
            for name, (x, y) in plan.box_positions.items()
        }
        if trace:
            trace.add_stage("positions", {"box_positions": dict(box_positions)})

        canvas: Union[Canvas, TracedCanvas] = Canvas(
            canvas_width + 2, plan.height + title_height + 2
        )
        if trace:
            trace.add_stage(
                "canvas_created",
                {
                    "canvas_width": canvas.width,
                    "canvas_height": canvas.height,
                    "title_height": title_height,
                },
                canvas,
            )
            canvas = TracedCanvas(canvas, trace)

        if effective_title:
            if isinstance(canvas, TracedCanvas):
                canvas.set_source("TitleRenderer.draw_title")
            self.title_renderer.draw_title(
                canvas, title_x_offset, 0, effective_title, title_width
            )

        if plan.group_boundaries:
            if isinstance(canvas, TracedCanvas):
                canvas.set_source("GroupBoxRenderer.draw_group_box")
            for group in plan.group_boundaries:
                self.group_box_renderer.draw_group_box(
                    canvas,
                    group.x + diagram_x_offset,
                    group.y + title_height,
                    group.width,
                    group.height,
                    group.name,
                    title_x=plan.group_title_x[group.name] + diagram_x_offset,
                )
            if trace:
                trace.add_stage(
                    "groups_drawn",
                    {"num_groups": len(plan.group_boundaries)},
                    self._underlying(canvas),
                )

        if isinstance(canvas, TracedCanvas):
            canvas.set_source("BoxRenderer.draw_box")
        for layer in plan.layers:
            for name in layer:
                x, y = box_positions[name]
                self.box_renderer.draw_box(canvas, x, y, plan.box_dimensions[name])

        base_lines = self._snapshot(canvas)
        if trace:
            trace.add_stage(
                "boxes_drawn",
                {"num_boxes": len(box_positions)},
                self._underlying(canvas),
            )

        if isinstance(canvas, TracedCanvas):
            canvas.set_source("RoutePlanner.wire_grid")
        for (x, y), glyph in plan.port_marks.items():
            canvas.set(x + diagram_x_offset, y + title_height, glyph, "exit_port")
        for (x, y), glyph in plan.grid.cells():
            canvas.set(
                x + diagram_x_offset,
                y + title_height,
                glyph,
                WIRE_REASONS.get(glyph, "wire"),
            )

        if trace:
            trace.add_stage(
                "edges_drawn",
                {"num_edges": len(set(connections))},
                self._underlying(canvas),
            )

        return canvas.render(), base_lines

    @staticmethod
    def _underlying(canvas: Union[Canvas, TracedCanvas]) -> Canvas:
        """The plain canvas behind a possibly traced one."""
        return canvas._canvas if isinstance(canvas, TracedCanvas) else canvas

    @classmethod
    def _snapshot(cls, canvas: Union[Canvas, TracedCanvas]) -> List[str]:
        """The canvas as rows of text, as it is right now."""
        rendered = cls._underlying(canvas).render()
        return rendered.split("\n") if rendered else []

    def save_txt(
        self, input_text: str, filename: str, boxes_only: bool = False
    ) -> None:
        """
        Generate flowchart and save to a text file.

        Args:
            input_text: Multi-line string with connections.
            filename: Output filename (should end in .txt).
            boxes_only: If True, only draw boxes without edges (ignored).
        """
        flowchart = self.generate(input_text)
        self.exporter.save_txt(flowchart, filename)

    def save_png(
        self,
        input_text: str,
        filename: str,
        font_size: int = 16,
        bg_color: str = "#FFFFFF",
        fg_color: str = "#000000",
        padding: int = 20,
        font: Optional[str] = None,
        scale: int = 2,
    ) -> None:
        """
        Generate flowchart and save as a high-resolution PNG image.

        The PNG rendering is faithful to the ASCII version, using a monospace
        font to preserve the exact character layout and box-drawing characters.

        Args:
            input_text: Multi-line string with connections like "A -> B".
            filename: Output filename (should end in .png).
            font_size: Font size in points (higher = higher resolution).
            bg_color: Background color as hex string (e.g., "#FFFFFF").
            fg_color: Foreground/text color as hex string (e.g., "#000000").
            padding: Padding around the diagram in pixels.
            font: Font name to use (overrides instance font if provided).
            scale: Resolution multiplier for crisp output (default 2 for retina).

        Example:
            >>> generator = FlowchartGenerator(font="Cascadia Code")
            >>> generator.save_png("A -> B -> C", "flowchart.png", font_size=24)
        """
        flowchart = self.generate(input_text)
        self.exporter.save_png(
            flowchart,
            filename,
            font_size=font_size,
            bg_color=bg_color,
            fg_color=fg_color,
            padding=padding,
            font=font or self.font,
            scale=scale,
        )

    def _draw_groups(
        self,
        canvas: Canvas,
        group_boundaries: List[GroupBoundary],
    ) -> None:
        """
        Draw all group boxes on the canvas.

        Groups should be drawn before node boxes so nodes appear on top.

        Args:
            canvas: The canvas to draw on.
            group_boundaries: List of calculated group boundaries.
        """
        for group in group_boundaries:
            self.group_box_renderer.draw_group_box(
                canvas,
                group.x,
                group.y,
                group.width,
                group.height,
                group.name,
            )

    def _draw_boxes(
        self,
        canvas: Canvas,
        box_dimensions: Dict[str, BoxDimensions],
        box_positions: Dict[str, Tuple[int, int]],
        layout_result: LayoutResult,
    ) -> None:
        """
        Draw all node boxes on the canvas.

        Args:
            canvas: The canvas to draw on.
            box_dimensions: Dictionary of box dimensions.
            box_positions: Dictionary of box positions.
            layout_result: The layout result with node information.
        """
        for node_name in layout_result.nodes:
            dims = box_dimensions[node_name]
            x, y = box_positions[node_name]
            self.box_renderer.draw_box(canvas, x, y, dims)
