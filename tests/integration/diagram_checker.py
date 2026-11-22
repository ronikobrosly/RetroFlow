"""
Test-side entry point for the diagram checker.

    input text ──► generate(debug=True) ──┬──► boxes-only canvas  (base)
                                          └──► finished canvas    (final)
                                                     │
                                       retroflow.checker.analyze_rendering

The checker itself lives in ``src/retroflow/checker.py`` because the
generator uses it as a gate. This module adds the one thing only tests need:
``check_diagram``, which renders an input and checks the result, including
that debug and non-debug renders agree.
"""

from retroflow import FlowchartGenerator
from retroflow.checker import (  # noqa: F401  (re-exported for the tests)
    ARROW_HEADS,
    ERROR_CODES,
    LINE_ARMS,
    WARNING_CODES,
    Box,
    DiagramReport,
    Issue,
    analyze_rendering,
    expected_edges_of,
    normalize_name,
)


def check_diagram(
    input_text: str, direction: str = "TB", label: str = "", **generator_kwargs
) -> DiagramReport:
    """
    Render ``input_text`` and check the result.

    Args:
        input_text: Flowchart source in RetroFlow syntax.
        direction: "TB" or "LR".
        label: Name used in failure messages.
        **generator_kwargs: Passed straight to ``FlowchartGenerator``.

    Returns:
        A ``DiagramReport`` whose ``issues`` list is empty for a clean diagram.
    """
    generator = FlowchartGenerator(direction=direction, **generator_kwargs)
    output = generator.generate(input_text, debug=True)
    base = generator.get_trace().get_canvas_at_stage("boxes_drawn") or []

    report = analyze_rendering(base, output, expected_edges_of(input_text))
    report.label = label or f"{direction} diagram"

    plain = FlowchartGenerator(direction=direction, **generator_kwargs).generate(
        input_text
    )
    if plain != output:
        report.issues.append(
            Issue("debug_mismatch", "debug=True output differs from normal output")
        )
    return report


def check_planned_diagram(
    input_text: str, direction: str = "TB", label: str = "", **generator_kwargs
) -> DiagramReport:
    """
    Render ``input_text`` with the planned renderer only, and check the result.

    ``generate()`` only falls back on the planned renderer when the classic
    one draws something misleading, so going through the public entry point
    never exercises the planner on the diagrams the classic renderer handles.
    This helper bypasses that gate: every diagram, simple or not, must come
    out clean from the planner on its own.

    Args:
        input_text: Flowchart source in RetroFlow syntax.
        direction: "TB" or "LR".
        label: Name used in failure messages.
        **generator_kwargs: Passed straight to ``FlowchartGenerator``.

    Returns:
        A ``DiagramReport`` whose ``issues`` list is empty for a clean diagram.
    """
    generator = FlowchartGenerator(direction=direction, **generator_kwargs)
    parsed = generator.parser.parse_with_groups(input_text)
    output, base = generator._render_planned(parsed, generator.title, None)

    report = analyze_rendering(base, output, expected_edges_of(input_text))
    report.label = label or f"{direction} diagram (planned)"
    return report
