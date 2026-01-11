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
from .parser import Group, ParseError, Parser, parse_flowchart
from .renderer import (
    BOX_CHARS_DOUBLE,
    BOX_CHARS_ROUNDED,
    BoxRenderer,
    Canvas,
    GroupBoxRenderer,
    LineRenderer,
    TitleRenderer,
)
from .router import BoxInfo, EdgeRoute, EdgeRouter

__version__ = "0.8.2"

__all__ = [
    "FlowchartGenerator",
    "Parser",
    "ParseError",
    "Group",
    "parse_flowchart",
    "SugiyamaLayout",
    "LayoutResult",
    "NodeLayout",
    "Canvas",
    "BoxRenderer",
    "BOX_CHARS_DOUBLE",
    "BOX_CHARS_ROUNDED",
    "GroupBoxRenderer",
    "LineRenderer",
    "TitleRenderer",
    "EdgeRouter",
    "EdgeRoute",
    "BoxInfo",
]
