"""
Main flowchart generator module.

This module provides the FlowchartGenerator class, which is the primary entry point
for creating ASCII flowcharts. It orchestrates the parsing, layout, positioning,
edge routing, and rendering pipeline to produce beautiful ASCII flowcharts from
simple text descriptions.

The generator supports:
- Top-to-bottom (TB) and left-to-right (LR) flow directions
- Box shadows and rounded corners
- Compact and expanded box styles
- Group boxes for organizing related nodes
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

from .debug import TracedCanvas
from .edge_drawing import EdgeDrawer
from .export import FlowchartExporter
from .layout import LayoutResult, NetworkXLayout
from .models import ColumnBoundary, GroupBoundingBox, LayerBoundary
from .parser import Parser
from .positioning import PositionCalculator
from .renderer import (
    BoxDimensions,
    BoxRenderer,
    Canvas,
    GroupBoxRenderer,
    TitleRenderer,
)
from .tracer import RenderTrace


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
        compact: bool = False,
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
        self.title_renderer = TitleRenderer()
        self.group_box_renderer = GroupBoxRenderer(padding=2)

        # Padding around grouped nodes inside group box
        self.group_padding = 2
        # Minimum spacing between group boxes (to prevent touching/overlapping)
        self.group_box_spacing = 2

        # Initialize helper objects
        self.position_calculator = PositionCalculator(
            box_renderer=self.box_renderer,
            group_box_renderer=self.group_box_renderer,
            min_box_width=min_box_width,
            horizontal_spacing=horizontal_spacing,
            vertical_spacing=vertical_spacing,
            shadow=shadow,
            group_padding=self.group_padding,
            group_box_spacing=self.group_box_spacing,
        )
        self.edge_drawer = EdgeDrawer(
            position_calculator=self.position_calculator,
            shadow=shadow,
        )
        self.exporter = FlowchartExporter(default_font=font)

        # Debug trace storage (populated when debug=True in generate())
        self._last_trace: Optional[RenderTrace] = None

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
        # Initialize debug trace if requested
        trace: Optional[RenderTrace] = None
        if debug:
            trace = RenderTrace(input_text=input_text, direction=self.direction)
            self._last_trace = trace
        else:
            self._last_trace = None

        # Use provided title or fall back to instance title
        effective_title = title if title is not None else self.title

        # Parse input (also parses groups and stores them in self.parser.groups)
        connections = self.parser.parse(input_text)
        groups = self.parser.groups

        if trace:
            trace.add_stage("parse", {
                "connections": connections,
                "groups": [(g.name, g.members) for g in groups],
            })

        # Run layout
        layout_result = self.layout_engine.layout(connections, groups)

        if trace:
            trace.add_stage("layout", {
                "layers": layout_result.layers,
                "back_edges": list(layout_result.back_edges),
                "node_positions": {
                    name: (node.layer, node.position)
                    for name, node in layout_result.nodes.items()
                },
            })

        # Calculate box dimensions for each node
        box_dimensions = self.position_calculator.calculate_all_box_dimensions(
            layout_result
        )

        if trace:
            trace.add_stage("dimensions", {
                "box_dimensions": {
                    name: (dims.width, dims.height)
                    for name, dims in box_dimensions.items()
                },
            })

        # Calculate actual pixel positions - leave margin for back edges
        # Each back edge needs 3 chars of space, plus 4 for min line before arrow
        num_back_edges = len(layout_result.back_edges)
        back_edge_margin = (4 + num_back_edges * 3) if num_back_edges > 0 else 0

        if self.direction == "LR":
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
            trace.add_stage("positions", {
                "box_positions": dict(box_positions),
                "back_edge_margin": back_edge_margin,
                "layer_boundaries": [
                    (lb.layer_idx, lb.top_y, lb.bottom_y, lb.gap_start_y, lb.gap_end_y)
                    for lb in layer_boundaries
                ],
            })

        # Calculate group bounding boxes (may have negative y values due to labels)
        group_boxes = self.position_calculator.calculate_group_bounding_boxes(
            layout_result, box_dimensions, box_positions
        )

        # Calculate extra margin needed for group labels
        group_top_margin = 0
        group_left_margin = 0
        if group_boxes:
            # Find how much extra space we need at top/left for group boxes
            for gb in group_boxes:
                if gb.y < 0:
                    group_top_margin = max(group_top_margin, -gb.y)
                if gb.x < 0:
                    group_left_margin = max(group_left_margin, -gb.x)

            # Offset all box positions to accommodate group margins
            if group_top_margin > 0 or group_left_margin > 0:
                box_positions = {
                    name: (x + group_left_margin, y + group_top_margin)
                    for name, (x, y) in box_positions.items()
                }
                # Recalculate group boxes with new positions
                group_boxes = self.position_calculator.calculate_group_bounding_boxes(
                    layout_result, box_dimensions, box_positions
                )
                # Also offset layer boundaries
                if group_top_margin > 0:
                    layer_boundaries = [
                        LayerBoundary(
                            layer_idx=lb.layer_idx,
                            top_y=lb.top_y + group_top_margin,
                            bottom_y=lb.bottom_y + group_top_margin,
                            gap_start_y=lb.gap_start_y + group_top_margin,
                            gap_end_y=lb.gap_end_y + group_top_margin,
                        )
                        for lb in layer_boundaries
                    ]
                # Also offset column boundaries for LR mode
                if group_left_margin > 0 and self.direction == "LR":
                    column_boundaries = [
                        ColumnBoundary(
                            layer_idx=cb.layer_idx,
                            left_x=cb.left_x + group_left_margin,
                            right_x=cb.right_x + group_left_margin,
                            gap_start_x=cb.gap_start_x + group_left_margin,
                            gap_end_x=cb.gap_end_x + group_left_margin,
                        )
                        for cb in column_boundaries
                    ]

        # Separate group boxes to ensure they don't touch or overlap
        if group_boxes:
            group_boxes = self.position_calculator.separate_group_boxes(group_boxes)

        # Calculate canvas size (including group boxes)
        canvas_width, canvas_height = self.position_calculator.calculate_canvas_size(
            box_dimensions, box_positions
        )

        # Expand canvas to fit group boxes
        if group_boxes:
            for gb in group_boxes:
                canvas_width = max(canvas_width, gb.x + gb.width + 2)
                canvas_height = max(canvas_height, gb.y + gb.height + 2)

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
            trace.add_stage("canvas_created", {
                "canvas_width": canvas_width + 5,
                "canvas_height": canvas_height + title_height + 5,
                "title_height": title_height,
            }, canvas)
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
            # Also offset group boxes
            if group_boxes:
                group_boxes = [
                    GroupBoundingBox(
                        group=gb.group,
                        x=gb.x + diagram_x_offset,
                        y=gb.y + title_height,
                        width=gb.width,
                        height=gb.height,
                        label_height=gb.label_height,
                    )
                    for gb in group_boxes
                ]

        # Draw group boxes first (before node boxes so nodes appear on top)
        if group_boxes:
            if isinstance(canvas, TracedCanvas):
                canvas.set_source("GroupBoxRenderer.draw_group_box")
            self._draw_group_boxes(canvas, group_boxes)

        # Draw node boxes
        if isinstance(canvas, TracedCanvas):
            canvas.set_source("BoxRenderer.draw_box")
        self._draw_boxes(canvas, box_dimensions, box_positions, layout_result)

        if trace:
            # Get underlying canvas for snapshot
            underlying = canvas._canvas if isinstance(canvas, TracedCanvas) else canvas
            trace.add_stage("boxes_drawn", {
                "num_boxes": len(box_positions),
                "num_group_boxes": len(group_boxes) if group_boxes else 0,
            }, underlying)

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
            trace.add_stage("forward_edges_drawn", {
                "num_forward_edges": len([
                    e for e in layout_result.edges
                    if e not in layout_result.back_edges
                ]),
            }, underlying)

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
                trace.add_stage("back_edges_drawn", {
                    "num_back_edges": len(layout_result.back_edges),
                }, underlying)

        return canvas.render()

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

    def _draw_group_boxes(
        self,
        canvas: Canvas,
        group_boxes: List[GroupBoundingBox],
    ) -> None:
        """
        Draw all group boxes on the canvas.

        Group boxes are drawn before node boxes so that nodes appear on top.

        Args:
            canvas: The canvas to draw on.
            group_boxes: List of GroupBoundingBox objects.
        """
        for group_box in group_boxes:
            self.group_box_renderer.draw_group_box(
                canvas,
                group_box.x,
                group_box.y,
                group_box.width,
                group_box.height,
                group_box.group.name,
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
