"""
RetroFlow - Beautiful ASCII Flowcharts

A Python library for generating ASCII and PNG flowcharts with intelligent layout.

Example:
    >>> from retroflow import FlowchartGenerator
    >>> generator = FlowchartGenerator()
    >>> flowchart = generator.generate('''
    ...     A -> B
    ...     B -> C
    ... ''')
    >>> print(flowchart)
"""

from .edge_routing import route_edges_with_refinement
from .flowchart import FlowchartGenerator, generate_flowchart
from .graph import Graph, create_graph
from .layout import LayoutAlgorithm, SimpleLayout, compute_layout
from .parser import ParseError, Parser, parse_flowchart
from .png_renderer import PNGRenderer, render_to_png
from .renderer import ASCIICanvas, FlowchartRenderer, render_flowchart

__version__ = "0.1.0"
__all__ = [
    # Main API
    "FlowchartGenerator",
    "generate_flowchart",
    # Parser
    "parse_flowchart",
    "ParseError",
    "Parser",
    # Graph
    "Graph",
    "create_graph",
    # Layout
    "compute_layout",
    "LayoutAlgorithm",
    "SimpleLayout",
    # Renderers
    "render_flowchart",
    "FlowchartRenderer",
    "ASCIICanvas",
    "render_to_png",
    "PNGRenderer",
    # Edge routing
    "route_edges_with_refinement",
]
