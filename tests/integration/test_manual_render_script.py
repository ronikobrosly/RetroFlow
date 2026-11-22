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
    assert "\nrenderer:  classic\nchecker:   clean\n" in contents
    assert contents.endswith(golden.read_text(encoding="utf-8"))
    assert "written to" in capsys.readouterr().out


def test_group_diagrams_get_their_own_folders(tmp_path):
    """Grouped diagrams land in groups_simple/ and groups_complex/."""
    script = _load_script()
    assert script.main(["group_pair", "groups_three_tier"], output_dir=tmp_path) == 0

    simple = sorted(p.name for p in (tmp_path / "groups_simple").glob("*.txt"))
    assert simple == ["group_pair-LR.txt", "group_pair-TB.txt"]
    busy = sorted(p.name for p in (tmp_path / "groups_complex").glob("*.txt"))
    assert busy == ["groups_three_tier-LR.txt", "groups_three_tier-TB.txt"]
    assert not list((tmp_path / "simple").glob("*.txt"))
    assert not list((tmp_path / "complex").glob("*.txt"))

    golden = Path(__file__).parent / "golden" / "group_pair-LR.txt"
    contents = (tmp_path / "groups_simple" / "group_pair-LR.txt").read_text(
        encoding="utf-8"
    )
    assert "\nrenderer:  planned\nchecker:   clean\n" in contents
    assert "[Team: A B]" in contents
    assert contents.endswith(golden.read_text(encoding="utf-8"))


def test_filter_can_select_a_whole_suite(tmp_path):
    """A filter is matched against <suite>/<case>-<direction>."""
    script = _load_script()
    assert script.main(["groups_simple/"], output_dir=tmp_path) == 0

    written = list((tmp_path / "groups_simple").glob("*.txt"))
    assert len(written) == sum(len(c.directions) for c in script.SIMPLE_GROUP_CASES)
    assert not list((tmp_path / "groups_complex").glob("*.txt"))


def test_header_reports_what_the_checker_found(tmp_path, monkeypatch):
    """A picture with issues says so in its header instead of 'clean'."""
    script = _load_script()
    case = script.SIMPLE_CASES[0]
    monkeypatch.setattr(script, "expected_edges_of", lambda text: {("A", "Nobody")})
    contents, _ = script.render_file(case, "TB")
    assert "\nchecker:   [box_missing]" in contents


def test_unfiltered_suite_replaces_stale_files(tmp_path):
    """Without filters, old .txt files in a suite folder are removed."""
    script = _load_script()
    stale = tmp_path / "simple" / "gone-TB.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")

    counts = script.write_suite("simple", script.SIMPLE_CASES[:1], tmp_path)

    assert not stale.exists()
    assert sum(counts.values()) == len(script.SIMPLE_CASES[0].directions)
