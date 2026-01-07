"""Pytest configuration and shared fixtures for RetroFlow tests."""

import pytest

from retroflow import BoxRenderer, Canvas, FlowchartGenerator, Parser, SugiyamaLayout


@pytest.fixture
def simple_input():
    """Simple linear flowchart input."""
    return """
    A -> B
    B -> C
    C -> D
    """


@pytest.fixture
def branching_input():
    """Branching flowchart input."""
    return """
    Start -> Process1
    Start -> Process2
    Process1 -> End
    Process2 -> End
    """


@pytest.fixture
def cyclic_input():
    """Flowchart with a cycle."""
    return """
    A -> B
    B -> C
    C -> A
    """


@pytest.fixture
def complex_input():
    """Complex flowchart with multiple paths."""
    return """
    Init -> Validate
    Validate -> Process
    Validate -> Error
    Process -> Transform
    Transform -> Output
    Error -> Retry
    Retry -> Validate
    Output -> Done
    """


@pytest.fixture
def generator():
    """Default FlowchartGenerator instance."""
    return FlowchartGenerator()


@pytest.fixture
def parser():
    """Default Parser instance."""
    return Parser()


@pytest.fixture
def layout_engine():
    """Default SugiyamaLayout instance."""
    return SugiyamaLayout()


@pytest.fixture
def simple_connections():
    """Simple linear connections."""
    return [("A", "B"), ("B", "C"), ("C", "D")]


@pytest.fixture
def branching_connections():
    """Branching connections."""
    return [
        ("Start", "Process1"),
        ("Start", "Process2"),
        ("Process1", "End"),
        ("Process2", "End"),
    ]


@pytest.fixture
def cyclic_connections():
    """Cyclic connections."""
    return [("A", "B"), ("B", "C"), ("C", "A")]


@pytest.fixture
def canvas():
    """Default canvas for testing."""
    return Canvas(80, 40)


@pytest.fixture
def box_renderer():
    """Default BoxRenderer instance."""
    return BoxRenderer()
