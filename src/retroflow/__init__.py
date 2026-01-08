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
from .renderer import (
    BOX_CHARS_DOUBLE,
    BOX_CHARS_ROUNDED,
    BoxRenderer,
    Canvas,
    LineRenderer,
    TitleRenderer,
)
from .router import BoxInfo, EdgeRoute, EdgeRouter

__version__ = "0.7.0"

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
    "BOX_CHARS_DOUBLE",
    "BOX_CHARS_ROUNDED",
    "LineRenderer",
    "TitleRenderer",
    "EdgeRouter",
    "EdgeRoute",
    "BoxInfo",
]
