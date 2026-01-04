"""
ASCII Flowchart Generator

A sophisticated library for generating ASCII flowcharts with intelligent layout.
"""

from .flowchart import FlowchartGenerator, generate_flowchart
from .parser import parse_flowchart, ParseError
from .graph import Graph, create_graph
from .layout import compute_layout
from .renderer import render_flowchart

__version__ = '1.0.0'
__all__ = [
    'FlowchartGenerator',
    'generate_flowchart',
    'parse_flowchart',
    'ParseError',
    'Graph',
    'create_graph',
    'compute_layout',
    'render_flowchart',
]
