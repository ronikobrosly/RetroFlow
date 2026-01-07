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
"""

from .generator import FlowchartGenerator
from .layout import LayoutResult, NodeLayout, SugiyamaLayout
from .parser import ParseError, Parser, parse_flowchart
from .renderer import BoxRenderer, Canvas, LineRenderer
from .router import BoxInfo, EdgeRoute, EdgeRouter

__version__ = "0.4.1"

__all__ = [
    "FlowchartGenerator",
    "Parser",
    "ParseError",
    "parse_flowchart",
    "SugiyamaLayout",
    "LayoutResult",
    "NodeLayout",
    "Canvas",
    "BoxRenderer",
    "LineRenderer",
    "EdgeRouter",
    "EdgeRoute",
    "BoxInfo",
]
