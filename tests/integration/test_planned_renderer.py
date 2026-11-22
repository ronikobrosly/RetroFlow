"""
Integration tests: the planned renderer on its own.

    generate() ──► classic clean? ── yes ──► classic output   (planner unused)
                        │ no
                        ▼
                  planned renderer                             (what we test)

Going through ``generate()`` only exercises the planner on the diagrams the
classic renderer gets wrong. These tests call the planned renderer directly,
so it has to draw *everything* cleanly: the simple diagrams too, every
complex one, every option, and a few hundred seeded random graphs.
"""

import random
from functools import lru_cache
from typing import Dict, List, Tuple

import pytest

from retroflow import FlowchartGenerator, ParseError

from .diagram_checker import (
    ARROW_HEADS,
    LINE_ARMS,
    DiagramReport,
    check_planned_diagram,
    expected_edges_of,
)
from .diagram_corpus import (
    COMPLEX_CASES,
    COMPLEX_GROUP_CASES,
    GROUP_CASES,
    RANDOM_CASES,
    SIMPLE_CASES,
    rendering_id,
    renderings,
)

ALL_CASES = SIMPLE_CASES + COMPLEX_CASES + RANDOM_CASES + GROUP_CASES
ALL_RENDERINGS = renderings(ALL_CASES)
CROSSING_FREE_RENDERINGS = renderings(c for c in ALL_CASES if c.crossing_free)
SIMPLE_RENDERINGS = renderings(SIMPLE_CASES)

_CASES_BY_NAME = {case.name: case for case in ALL_CASES}


@lru_cache(maxsize=None)
def _planned(case_name: str, direction: str) -> DiagramReport:
    case = _CASES_BY_NAME[case_name]
    return check_planned_diagram(
        case.text, direction, label=f"{case_name}-{direction} (planned)", **case.options
    )


@pytest.mark.parametrize("rendering", ALL_RENDERINGS, ids=rendering_id)
class TestPlannedRendererOnTheWholeCorpus:
    def test_picture_is_correct(self, rendering):
        """No structural error of any kind, whichever renderer the gate picks."""
        case, direction = rendering
        report = _planned(case.name, direction)
        codes = sorted({issue.code for issue in report.errors})
        assert not report.errors, report.explain(*codes)

    def test_picture_is_legible(self, rendering):
        """No cramped strokes, and nothing crowding or needlessly crossing a group."""
        case, direction = rendering
        report = _planned(case.name, direction)
        codes = sorted({issue.code for issue in report.warnings})
        assert not report.warnings, report.explain(*codes)

    def test_text_is_tidy(self, rendering):
        """No trailing blanks, no blank tail, only glyphs the renderer owns."""
        case, direction = rendering
        rows = _planned(case.name, direction).output.split("\n")
        assert rows[-1].strip(), "diagram ends with a blank row"
        assert all(row == row.rstrip() for row in rows)

        # Characters that are neither box text nor a known drawing glyph
        # would mean the wire grid invented something.
        drawing = set(LINE_ARMS) | set(ARROW_HEADS) | set("░┆┄╭╮╰╯╔╗╚╝═║ ")
        text = set(case.text) | set(str(case.options.get("title", "")))
        unexpected = {ch for row in rows for ch in row} - drawing - text
        assert not unexpected, f"unexpected characters: {sorted(unexpected)}"


@pytest.mark.parametrize("rendering", CROSSING_FREE_RENDERINGS, ids=rendering_id)
def test_planned_trees_fans_and_rings_have_no_crossings(rendering):
    case, direction = rendering
    report = _planned(case.name, direction)
    assert report.crossings == 0, report.explain()


@pytest.mark.parametrize("rendering", SIMPLE_RENDERINGS, ids=rendering_id)
def test_planned_simple_diagrams_have_no_crossings(rendering):
    """Nothing in the simple corpus needs two edges to cross."""
    case, direction = rendering
    report = _planned(case.name, direction)
    assert report.crossings == 0, report.explain()


# Tracing records every character placed, which is slow, so the comparison
# runs on the simple corpus plus an evenly spread sample of everything else.
TRACED_RENDERINGS = SIMPLE_RENDERINGS + ALL_RENDERINGS[len(SIMPLE_RENDERINGS) :: 5]


@pytest.mark.parametrize("rendering", TRACED_RENDERINGS, ids=rendering_id)
def test_planned_trace_matches_untraced_output(rendering):
    """Tracing must never change what the planned renderer draws."""
    case, direction = rendering
    generator = FlowchartGenerator(direction=direction, **case.options)
    parsed = generator.parser.parse_with_groups(case.text)
    plain, plain_base = generator._render_planned(parsed, generator.title, None)

    from retroflow.tracer import RenderTrace

    trace = RenderTrace(input_text=case.text, direction=direction)
    traced, traced_base = generator._render_planned(parsed, generator.title, trace)
    assert traced == plain
    assert traced_base == plain_base
    assert trace.get_canvas_at_stage("boxes_drawn") == plain_base
    assert trace.get_stage("routes_planned").data["conflicts"] == []


class TestArrowheads:
    """How many arrowheads a planned diagram shows."""

    @staticmethod
    def _arrowheads(output: str) -> int:
        return sum(output.count(glyph) for glyph in ARROW_HEADS)

    @pytest.mark.parametrize(
        "case",
        [c for c in COMPLEX_CASES + COMPLEX_GROUP_CASES if "TB" in c.directions],
        ids=lambda case: case.name,
    )
    def test_tb_gives_every_edge_its_own_arrowhead(self, case):
        report = _planned(case.name, "TB")
        assert self._arrowheads(report.output) == len(expected_edges_of(case.text))

    @pytest.mark.parametrize(
        "case",
        [c for c in COMPLEX_CASES + COMPLEX_GROUP_CASES if "LR" in c.directions],
        ids=lambda case: case.name,
    )
    def test_lr_never_draws_more_arrowheads_than_edges(self, case):
        report = _planned(case.name, "LR")
        edges = expected_edges_of(case.text)
        targets = {target for _, target in edges}
        assert len(targets) <= self._arrowheads(report.output) <= len(edges)


# ── seeded fuzzing ──────────────────────────────────────────────────────

_FUZZ_NAMES = (
    "Api",
    "Queue",
    "Cache",
    "Billing Service",
    "Edge Router",
    "A",
    "Long Name For A Node That Wraps",
    "Db",
    "Worker Pool",
)
_FUZZ_TITLES = ("G", "Group", "A Rather Long Group Title Here")


def fuzz_input(seed: int) -> Tuple[str, Dict[str, object]]:
    """
    A seeded random diagram: graph, optional groups and generator options.

    Only ``Random.random()`` is used, so a seed means the same diagram on
    every supported Python version.
    """
    rng = random.Random(seed)

    def below(limit: int) -> int:
        return int(rng.random() * limit)

    def pick(choices):
        return choices[below(len(choices))]

    count = 2 + below(13)
    names = [f"{pick(_FUZZ_NAMES)} {i}" for i in range(count)]
    edges: List[Tuple[str, str]] = []
    for i in range(1, count):
        edges.append((names[below(i)], names[i]))
    for _ in range(below(2 * count + 1)):
        source = below(count)
        target = source if rng.random() < 0.15 else below(count)
        edges.append((names[source], names[target]))

    lines: List[str] = []
    if rng.random() < 0.4:
        position = below(3)
        while position < count and len(lines) < 3:
            size = 1 + below(4)
            members = names[position : position + size]
            lines.append(f"[{pick(_FUZZ_TITLES)}{len(lines)}: {' '.join(members)}]")
            position += size + below(3)
    lines += [f"{source} -> {target}" for source, target in edges]

    options = {
        "direction": pick(("TB", "LR")),
        "shadow": rng.random() < 0.7,
        "rounded": rng.random() < 0.3,
        "compact": rng.random() < 0.7,
        "horizontal_spacing": pick((0, 2, 4, 12, 20)),
        "vertical_spacing": pick((0, 1, 3, 6)),
        "max_text_width": pick((3, 12, 22, 40)),
        "min_box_width": pick((1, 10, 18)),
        "title": pick((None, None, "T", "A Very Long Diagram Title That Is Wide")),
    }
    return "\n".join(lines), options


@pytest.mark.parametrize("seed", range(300))
def test_fuzzed_diagram_is_clean(seed):
    """Random graphs, groups and options: always a clean picture, never a crash."""
    text, options = fuzz_input(seed)
    direction = options.pop("direction")
    try:
        FlowchartGenerator().parser.parse_with_groups(text)
    except ParseError:  # pragma: no cover - the generator above avoids these
        pytest.skip("random group definition was not valid input")

    report = check_planned_diagram(text, direction, label=f"fuzz {seed}", **options)
    codes = sorted({issue.code for issue in report.issues})
    assert not report.issues, f"{options}\n{text}\n{report.explain(*codes)}"


@pytest.mark.parametrize("seed", range(0, 300, 7))
def test_fuzzed_diagram_goes_through_the_public_entry_point(seed):
    """Whatever the gate picks for a random diagram is clean as well."""
    from .diagram_checker import check_diagram

    text, options = fuzz_input(seed)
    direction = options.pop("direction")
    report = check_diagram(text, direction, label=f"fuzz {seed}", **options)
    codes = sorted({issue.code for issue in report.issues})
    assert not report.issues, f"{options}\n{text}\n{report.explain(*codes)}"
