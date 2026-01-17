"""
RetroFlow - Beautiful ASCII Flowcharts

A Python library for generating ASCII flowcharts with intelligent Sugiyama layout.

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

from .debug import CanvasInspector, TracedCanvas, visual_diff
from .generator import FlowchartGenerator
from .layout import LayoutResult, NodeLayout, SugiyamaLayout
from .parser import ParseError, Parser, parse_flowchart
from .renderer import (
    BOX_CHARS_DOUBLE,
    BOX_CHARS_ROUNDED,
    BoxRenderer,
    Canvas,
    LineRenderer,
    TitleRenderer,
)
from .router import BoxInfo, EdgeRoute, EdgeRouter
from .tracer import CharacterPlacement, PipelineStage, RenderTrace

__version__ = "0.9.1"

__all__ = [
    # Main API
    "FlowchartGenerator",
    # Parser
    "Parser",
    "ParseError",
    "parse_flowchart",
    # Layout
    "SugiyamaLayout",
    "LayoutResult",
    "NodeLayout",
    # Renderer
    "Canvas",
    "BoxRenderer",
    "BOX_CHARS_DOUBLE",
    "BOX_CHARS_ROUNDED",
    "LineRenderer",
    "TitleRenderer",
    # Router
    "EdgeRouter",
    "EdgeRoute",
    "BoxInfo",
    # Debug/Tracing (for development and debugging)
    "RenderTrace",
    "CharacterPlacement",
    "PipelineStage",
    "TracedCanvas",
    "CanvasInspector",
    "visual_diff",
]
