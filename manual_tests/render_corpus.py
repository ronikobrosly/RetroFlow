"""
Render the test corpus to text files, for looking at with your own eyes.

    ┌─────────┐     ┌──────────────┐     ┌───────────────────────┐
    │ corpus  │────►│ this script  │────►│ manual_tests/output/  │
    └─────────┘     └──────────────┘     └───────────────────────┘

Every simple (golden) and complex diagram in tests/integration/diagram_corpus.py
is rendered in each of its directions and written to one .txt file:

    manual_tests/output/simple/<case>-<direction>.txt
    manual_tests/output/complex/<case>-<direction>.txt

Each file starts with a short header (case, direction, options, which renderer
won, the input text), followed by the diagram exactly as ``generate()`` returns
it. Old .txt files in those folders are removed first, so the output always
matches the current corpus.

    uv run python manual_tests/render_corpus.py              # everything
    uv run python manual_tests/render_corpus.py cicd groups  # names containing
                                                             # "cicd" or "groups"
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from integration.diagram_corpus import (  # noqa: E402
    COMPLEX_CASES,
    SIMPLE_CASES,
    Case,
    rendering_id,
    renderings,
)

from retroflow import FlowchartGenerator  # noqa: E402

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"
SUITES: Dict[str, List[Case]] = {"simple": SIMPLE_CASES, "complex": COMPLEX_CASES}
RULE = "─" * 72


def render_file(case: Case, direction: str) -> Tuple[str, str]:
    """Render one case in one direction; return (file contents, renderer)."""
    generator = FlowchartGenerator(direction=direction, **case.options)
    diagram = generator.generate(case.text)
    options = ", ".join(f"{k}={v!r}" for k, v in sorted(case.options.items()))
    header = [
        f"case:      {case.name}",
        f"direction: {direction}",
        f"options:   {options or '(defaults)'}",
        f"renderer:  {generator.last_renderer}",
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
        if filters and not any(f in name for f in filters):
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
