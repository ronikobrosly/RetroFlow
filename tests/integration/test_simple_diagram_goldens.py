"""
Golden tests: simple diagrams must keep rendering exactly as they do today.

    ┌────────┐
    │ simple │░   pinned, character for character, in tests/integration/golden/
    └────────┘░
     ░░░░░░░░░░

These are the guard rail for any work on complex-diagram routing: a routing
change may make busy diagrams cleaner, but it must not move a single
character of these.

The small diagrams with group boxes (``SIMPLE_GROUP_CASES``) are pinned the
same way, so the look of a group box cannot drift either.

If a golden really should change, regenerate deliberately and review the diff:

    RETROFLOW_UPDATE_GOLDENS=1 uv run pytest -k goldens
    git diff tests/integration/golden/
"""

import os
from pathlib import Path

import pytest

from retroflow import FlowchartGenerator

from .diagram_checker import check_diagram
from .diagram_corpus import (
    SIMPLE_CASES,
    SIMPLE_GROUP_CASES,
    rendering_id,
    renderings,
)

GOLDEN_DIR = Path(__file__).parent / "golden"
UPDATE_GOLDENS = os.environ.get("RETROFLOW_UPDATE_GOLDENS") == "1"

SIMPLE_RENDERINGS = renderings(SIMPLE_CASES + SIMPLE_GROUP_CASES)


@pytest.mark.parametrize("rendering", SIMPLE_RENDERINGS, ids=rendering_id)
class TestSimpleDiagramsAreUnchanged:
    """Simple diagrams are pinned and stay clean."""

    def test_output_matches_golden_file(self, rendering):
        """The rendered text is identical to the reviewed golden file."""
        case, direction = rendering
        output = FlowchartGenerator(direction=direction, **case.options).generate(
            case.text
        )
        golden_path = GOLDEN_DIR / f"{rendering_id(rendering)}.txt"

        if UPDATE_GOLDENS:
            GOLDEN_DIR.mkdir(exist_ok=True)
            # open() rather than write_text(): its newline= needs Python 3.10+
            with open(golden_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(output + "\n")

        assert golden_path.exists(), (
            f"no golden file for {rendering_id(rendering)}; "
            "run with RETROFLOW_UPDATE_GOLDENS=1 to create it"
        )
        expected = golden_path.read_text(encoding="utf-8")
        assert output + "\n" == expected

    def test_output_is_clean(self, rendering):
        """Simple diagrams have no errors and no legibility warnings."""
        case, direction = rendering
        report = check_diagram(
            case.text, direction, label=rendering_id(rendering), **case.options
        )
        assert not report.issues, report.explain()


def test_no_stale_golden_files():
    """Every golden file belongs to a case that still exists."""
    expected = {f"{rendering_id(r)}.txt" for r in SIMPLE_RENDERINGS}
    actual = {path.name for path in GOLDEN_DIR.glob("*.txt")}
    assert actual == expected
