"""
Integration tests: complex diagrams must come out clean.

A diagram with many boxes and many edges is clean when, reading only the
rendered text, a person could recover exactly the graph that was asked for:

      boxes intact ── no broken line ends ── every arrowhead attached
                              │
            every input edge traceable, and no extra ones implied

plus one legibility rule: unrelated lines are not crammed into touching
columns. The rules live in diagram_checker.py; the diagrams in
diagram_corpus.py. For an overview across the whole corpus run:

    uv run python tests/integration/diagram_scorecard.py -v
"""

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

from retroflow import FlowchartGenerator

from .diagram_checker import DiagramReport, check_diagram
from .diagram_corpus import (
    COMPLEX_CASES,
    RANDOM_CASES,
    rendering_id,
    renderings,
)

COMPLEX_RENDERINGS = renderings(COMPLEX_CASES)
RANDOM_RENDERINGS = renderings(RANDOM_CASES)
CROSSING_FREE_RENDERINGS = renderings(c for c in COMPLEX_CASES if c.crossing_free)

_CASES_BY_NAME = {case.name: case for case in COMPLEX_CASES + RANDOM_CASES}


@lru_cache(maxsize=None)
def _report(case_name: str, direction: str) -> DiagramReport:
    """Render and check one diagram (shared by all tests for that rendering)."""
    case = _CASES_BY_NAME[case_name]
    return check_diagram(
        case.text, direction, label=f"{case_name}-{direction}", **case.options
    )


def _assert_none(rendering, *codes: str) -> None:
    case, direction = rendering
    report = _report(case.name, direction)
    assert not report.of(*codes), report.explain(*codes)


@pytest.mark.parametrize("rendering", COMPLEX_RENDERINGS, ids=rendering_id)
class TestComplexDiagramsAreClean:
    """Each complex diagram, checked one concern at a time."""

    def test_boxes_and_labels_are_intact(self, rendering):
        """No edge overwrites a box, its text, a title or a group label."""
        _assert_none(
            rendering,
            "box_missing",
            "box_damaged",
            "group_border_damaged",
            "debug_mismatch",
        )

    def test_no_broken_line_ends(self, rendering):
        """Every line glyph connects to a neighbour, a box or an arrowhead."""
        _assert_none(rendering, "dangling_line", "dangling_port")

    def test_no_floating_arrowheads(self, rendering):
        """Every arrowhead touches a box and has a line leading into it."""
        _assert_none(rendering, "floating_arrow", "arrow_no_tail", "arrow_hit_sideways")

    def test_picture_shows_exactly_the_input_edges(self, rendering):
        """Tracing the lines recovers the input graph: nothing lost or implied."""
        _assert_none(rendering, "missing_edge", "phantom_edge", "stray_line")

    def test_lines_are_not_crammed_together(self, rendering):
        """Unrelated vertical strokes never sit in touching columns."""
        _assert_none(rendering, "adjacent_lines")


@pytest.mark.parametrize("rendering", RANDOM_RENDERINGS, ids=rendering_id)
class TestRandomGraphsAreClean:
    """Seeded pseudo-random graphs, for breadth beyond hand-picked shapes."""

    def test_diagram_is_correct(self, rendering):
        """No structural errors of any kind."""
        case, direction = rendering
        report = _report(case.name, direction)
        codes = sorted({issue.code for issue in report.errors})
        assert not report.errors, report.explain(*codes)

    def test_lines_are_not_crammed_together(self, rendering):
        """Unrelated vertical strokes never sit in touching columns."""
        _assert_none(rendering, "adjacent_lines")


@pytest.mark.parametrize("rendering", CROSSING_FREE_RENDERINGS, ids=rendering_id)
def test_crossing_free_graphs_are_drawn_without_crossings(rendering):
    """Trees, fans and plain rings never need two edges to cross."""
    case, direction = rendering
    report = _report(case.name, direction)
    assert report.crossings == 0, report.explain()


@pytest.mark.parametrize(
    "rendering", COMPLEX_RENDERINGS + RANDOM_RENDERINGS, ids=rendering_id
)
def test_rendering_is_repeatable(rendering):
    """The same input always produces the same text."""
    case, direction = rendering
    first = FlowchartGenerator(direction=direction, **case.options)
    second = FlowchartGenerator(direction=direction, **case.options)
    output = first.generate(case.text)
    assert first.generate(case.text) == output
    assert second.generate(case.text) == output


# Rendered in a child process so each run gets its own string-hash seed.
_RENDER_SCRIPT = """
import json, sys
from retroflow import FlowchartGenerator
jobs = json.load(sys.stdin)
print(json.dumps([
    FlowchartGenerator(direction=direction, **options).generate(text)
    for text, direction, options in jobs
]))
"""


def _render_in_child_processes(jobs, hash_seeds):
    """Render ``jobs`` once per hash seed, all seeds at the same time."""
    src_dir = str(Path(__file__).resolve().parents[2] / "src")
    children = []
    for hash_seed in hash_seeds:
        env = dict(os.environ, PYTHONHASHSEED=str(hash_seed), PYTHONPATH=src_dir)
        child = subprocess.Popen(
            [sys.executable, "-c", _RENDER_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        # Each child gets its whole input up front so they all run at once.
        child.stdin.write(json.dumps(jobs))
        child.stdin.close()
        children.append(child)

    outputs = []
    for child in children:
        stdout = child.stdout.read()
        stderr = child.stderr.read()
        assert child.wait() == 0, stderr
        outputs.append(json.loads(stdout))
    return outputs


def test_rendering_does_not_depend_on_the_hash_seed():
    """
    A diagram must look the same in every Python process.

    Python randomizes string hashing per process, so any code that iterates a
    set of node names or edges can silently change the picture between runs.
    """
    all_renderings = COMPLEX_RENDERINGS + RANDOM_RENDERINGS
    jobs = [[case.text, direction, case.options] for case, direction in all_renderings]
    reference, *others = _render_in_child_processes(jobs, hash_seeds=range(6))

    unstable = set()
    for outputs in others:
        unstable |= {
            rendering_id(rendering)
            for rendering, expected, actual in zip(all_renderings, reference, outputs)
            if expected != actual
        }

    assert not unstable, (
        f"{len(unstable)} rendering(s) change between runs: {sorted(unstable)}"
    )
