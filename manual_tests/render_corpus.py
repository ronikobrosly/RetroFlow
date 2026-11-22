"""
Render the test corpus to text files, for looking at with your own eyes.

    ┌─────────┐     ┌──────────────┐     ┌───────────────────────┐
    │ corpus  │────►│ this script  │────►│ manual_tests/output/  │
    └─────────┘     └──────────────┘     └───────────────────────┘

Every simple (golden) and complex diagram in tests/integration/diagram_corpus.py
is rendered in each of its directions and written to one .txt file. Diagrams
with group boxes get folders of their own:

    manual_tests/output/simple/<case>-<direction>.txt
    manual_tests/output/complex/<case>-<direction>.txt
    manual_tests/output/groups_simple/<case>-<direction>.txt
    manual_tests/output/groups_complex/<case>-<direction>.txt

Each file starts with a short header (case, direction, options, which renderer
won, what the checker thinks of the picture, the input text), followed by the
diagram exactly as ``generate()`` returns it. Old .txt files in those folders
are removed first, so the output always matches the current corpus.

    uv run python manual_tests/render_corpus.py              # everything
    uv run python manual_tests/render_corpus.py cicd tier    # names containing
                                                             # "cicd" or "tier"
    uv run python manual_tests/render_corpus.py groups_      # both group suites

A filter is matched against ``<suite>/<case>-<direction>``, so it can select a
whole suite, one case, or one direction of every case (``-LR``).
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from integration.diagram_corpus import (  # noqa: E402
    COMPLEX_CASES,
    COMPLEX_GROUP_CASES,
    SIMPLE_CASES,
    SIMPLE_GROUP_CASES,
    Case,
    rendering_id,
    renderings,
)

from retroflow import FlowchartGenerator  # noqa: E402
from retroflow.checker import (  # noqa: E402
    analyze_rendering,
    expected_edges_of,
    expected_groups_of,
)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"
SUITES: Dict[str, List[Case]] = {
    "simple": SIMPLE_CASES,
    "complex": COMPLEX_CASES,
    "groups_simple": SIMPLE_GROUP_CASES,
    "groups_complex": COMPLEX_GROUP_CASES,
}
RULE = "─" * 72


def render_file(case: Case, direction: str) -> Tuple[str, str]:
    """Render one case in one direction; return (file contents, renderer)."""
    generator = FlowchartGenerator(direction=direction, **case.options)
    diagram = generator.generate(case.text, debug=True)
    base = generator.get_trace().get_canvas_at_stage("boxes_drawn") or []
    report = analyze_rendering(
        base, diagram, expected_edges_of(case.text), expected_groups_of(case.text)
    )
    verdict = "; ".join(str(issue) for issue in report.issues) or "clean"
    options = ", ".join(f"{k}={v!r}" for k, v in sorted(case.options.items()))
    header = [
        f"case:      {case.name}",
        f"direction: {direction}",
        f"options:   {options or '(defaults)'}",
        f"renderer:  {generator.last_renderer}",
        f"checker:   {verdict}",
        RULE,
        case.text.strip("\n"),
        RULE,
        "",
    ]
    return "\n".join(header) + diagram + "\n", generator.last_renderer


def write_suite(
    suite: str,
    cases: Sequence[Case],
    output_dir: Path,
    filters: Sequence[str] = (),
) -> Dict[str, int]:
    """Render one suite into ``output_dir/suite``; return renderer counts."""
    suite_dir = output_dir / suite
    suite_dir.mkdir(parents=True, exist_ok=True)
    if not filters:
        for stale in suite_dir.glob("*.txt"):
            stale.unlink()

    counts: Dict[str, int] = {}
    for rendering in renderings(cases):
        name = rendering_id(rendering)
        if filters and not any(f in f"{suite}/{name}" for f in filters):
            continue
        contents, renderer = render_file(*rendering)
        # open() rather than write_text(): its newline= needs Python 3.10+
        with open(suite_dir / f"{name}.txt", "w", encoding="utf-8", newline="\n") as f:
            f.write(contents)
        counts[renderer] = counts.get(renderer, 0) + 1
    return counts


def main(argv: Sequence[str], output_dir: Optional[Path] = None) -> int:
    """Render every suite; ``argv`` holds optional name filters."""
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    filters = [arg for arg in argv if not arg.startswith("-")]

    for suite, cases in SUITES.items():
        counts = write_suite(suite, cases, output_dir, filters)
        total = sum(counts.values())
        detail = ", ".join(f"{r}={n}" for r, n in sorted(counts.items()))
        print(f"{suite:8s} {total:4d} files  ({detail or 'none matched'})")

    print(f"written to {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
