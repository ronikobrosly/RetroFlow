"""Pytest configuration and shared fixtures for RetroFlow tests."""

import pytest

from retroflow import FlowchartGenerator, create_graph


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
def simple_graph():
    """Pre-built simple graph."""
    connections = [("A", "B"), ("B", "C"), ("C", "D")]
    return create_graph(connections)


@pytest.fixture
def branching_graph():
    """Pre-built branching graph."""
    connections = [
        ("Start", "Process1"),
        ("Start", "Process2"),
        ("Process1", "End"),
        ("Process2", "End"),
    ]
    return create_graph(connections)
