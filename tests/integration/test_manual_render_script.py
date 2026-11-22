"""
The manual-inspection script (manual_tests/render_corpus.py) keeps working.

It is not part of the package, so only a smoke test lives here: render a
couple of diagrams into a temporary folder and check what lands on disk.
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "manual_tests" / "render_corpus.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("render_corpus", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_filtered_run_writes_matching_files(tmp_path, capsys):
    """A name filter renders only matching diagrams, header plus picture."""
    script = _load_script()
    assert script.main(["diamond"], output_dir=tmp_path) == 0

    written = sorted(p.name for p in (tmp_path / "simple").glob("*.txt"))
    assert written == ["diamond-LR.txt", "diamond-TB.txt"]

    golden = Path(__file__).parent / "golden" / "diamond-TB.txt"
    contents = (tmp_path / "simple" / "diamond-TB.txt").read_text(encoding="utf-8")
    assert contents.startswith("case:      diamond\ndirection: TB\n")
    assert contents.endswith(golden.read_text(encoding="utf-8"))
    assert "written to" in capsys.readouterr().out


def test_unfiltered_suite_replaces_stale_files(tmp_path):
    """Without filters, old .txt files in a suite folder are removed."""
    script = _load_script()
    stale = tmp_path / "simple" / "gone-TB.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")

    counts = script.write_suite("simple", script.SIMPLE_CASES[:1], tmp_path)

    assert not stale.exists()
    assert sum(counts.values()) == len(script.SIMPLE_CASES[0].directions)
