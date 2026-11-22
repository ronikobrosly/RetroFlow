"""
Scorecard: how clean is every diagram in the corpus right now?

    uv run python tests/integration/diagram_scorecard.py            # summary
    uv run python tests/integration/diagram_scorecard.py -v         # + per diagram
    uv run python tests/integration/diagram_scorecard.py cicd-TB    # show one

Run it before and after a routing change to see what moved.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integration.diagram_checker import (  # noqa: E402
    ERROR_CODES,
    WARNING_CODES,
    check_diagram,
)
from integration.diagram_corpus import (  # noqa: E402
    COMPLEX_CASES,
    COMPLEX_GROUP_CASES,
    RANDOM_CASES,
    RANDOM_GROUP_CASES,
    SIMPLE_CASES,
    SIMPLE_GROUP_CASES,
    rendering_id,
    renderings,
)


def main(argv: list) -> int:
    verbose = "-v" in argv
    wanted = [arg for arg in argv if not arg.startswith("-")]
    suites = (
        ("simple", SIMPLE_CASES),
        ("complex", COMPLEX_CASES),
        ("random", RANDOM_CASES),
        ("groups simple", SIMPLE_GROUP_CASES),
        ("groups complex", COMPLEX_GROUP_CASES),
        ("groups random", RANDOM_GROUP_CASES),
    )

    for suite_name, cases in suites:
        totals: Counter = Counter()
        affected: Counter = Counter()
        clean = correct = count = 0

        for case, direction in renderings(cases):
            name = rendering_id((case, direction))
            report = check_diagram(case.text, direction, label=name, **case.options)
            if name in wanted:
                print(report.explain())
            count += 1
            clean += not report.issues
            correct += not report.errors
            totals.update(report.counts())
            affected.update(set(report.counts()))
            if verbose:
                found = ", ".join(
                    f"{c}={n}" for c, n in sorted(report.counts().items())
                )
                print(
                    f"  {name:32s} crossings={report.crossings:<3d} {found or 'clean'}"
                )

        print(f"\n{suite_name}: {count} renderings")
        print(f"  no errors              {correct:4d}  ({100 * correct // count}%)")
        print(f"  no errors or warnings  {clean:4d}  ({100 * clean // count}%)")
        for code in ERROR_CODES + WARNING_CODES:
            if totals[code]:
                print(
                    f"  {code:22s} {totals[code]:4d} issue(s) "
                    f"in {affected[code]} rendering(s)"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
