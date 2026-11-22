"""
Unit tests for the renderer gate in ``FlowchartGenerator.generate``.

    input ──► classic renderer ──► reads back clean? ── yes ──► returned as is
                                          │ no
                                          ▼
              planned renderer ──► better than classic? ──► returned

The gate is what protects small diagrams (they keep their exact classic
output) while busy diagrams get the planned renderer.
"""

import pytest

from retroflow import FlowchartGenerator
from retroflow.checker import analyze_rendering, expected_edges_of
from retroflow.generator import WIRE_REASONS

SIMPLE = "A -> B\nB -> C"
# The smallest chain the classic renderer gets wrong in both directions:
# two skip edges out of A fuse on their way down.
SKIP_EDGE = "A -> B\nB -> C\nC -> D\nA -> C\nA -> D"
GROUPED = """
[API Layer: Gateway Auth]
[Data Layer: Database Cache]
Gateway -> Auth
Auth -> Database
Database -> Cache
Gateway -> Cache
"""


def is_clean(text: str, generator: FlowchartGenerator) -> bool:
    output = generator.generate(text, debug=True)
    base = generator.get_trace().get_canvas_at_stage("boxes_drawn")
    return not analyze_rendering(base, output, expected_edges_of(text)).issues


class TestWhichRendererIsUsed:
    def test_nothing_rendered_yet(self):
        assert FlowchartGenerator().last_renderer is None

    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_simple_diagram_keeps_the_classic_renderer(self, direction):
        generator = FlowchartGenerator(direction=direction)
        generator.generate(SIMPLE)
        assert generator.last_renderer == "classic"

    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_simple_diagram_output_is_the_classic_output(self, direction):
        generator = FlowchartGenerator(direction=direction)
        parsed = generator.parser.parse_with_groups(SIMPLE)
        classic, _ = generator._render_classic(parsed, None, None)
        assert generator.generate(SIMPLE) == classic

    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_diagram_the_classic_renderer_gets_wrong_is_planned(self, direction):
        generator = FlowchartGenerator(direction=direction)
        parsed = generator.parser.parse_with_groups(SKIP_EDGE)
        classic, base = generator._render_classic(parsed, None, None)
        assert analyze_rendering(base, classic, expected_edges_of(SKIP_EDGE)).errors

        output = generator.generate(SKIP_EDGE)
        assert generator.last_renderer == "planned"
        assert output != classic
        assert is_clean(SKIP_EDGE, generator)

    def test_cramped_but_correct_diagram_is_planned_too(self):
        # Three arrowheads in touching columns are correct but hard to read.
        text = "Hub -> Leaf 1\nHub -> Leaf 2\nHub -> Leaf 3\nHub -> Leaf 4"
        generator = FlowchartGenerator()
        parsed = generator.parser.parse_with_groups(text)
        classic, base = generator._render_classic(parsed, None, None)
        report = analyze_rendering(base, classic, expected_edges_of(text))
        assert not report.errors and report.warnings

        generator.generate(text)
        assert generator.last_renderer == "planned"
        assert is_clean(text, generator)

    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_grouped_diagram_is_clean(self, direction):
        assert is_clean(GROUPED, FlowchartGenerator(direction=direction))

    def test_renderer_can_change_between_calls(self):
        generator = FlowchartGenerator()
        generator.generate(SKIP_EDGE)
        assert generator.last_renderer == "planned"
        generator.generate(SIMPLE)
        assert generator.last_renderer == "classic"


class TestFallback:
    """The planned renderer may only ever improve on the classic one."""

    def test_planner_failure_falls_back_to_the_classic_picture(self, monkeypatch):
        generator = FlowchartGenerator()
        parsed = generator.parser.parse_with_groups(SKIP_EDGE)
        classic, _ = generator._render_classic(parsed, None, None)

        def explode(*args, **kwargs):
            raise RuntimeError("planner broke")

        monkeypatch.setattr(generator, "_render_planned", explode)
        assert generator.generate(SKIP_EDGE) == classic
        assert generator.last_renderer == "classic"

    def test_planner_failure_is_recorded_in_the_trace(self, monkeypatch):
        generator = FlowchartGenerator()

        def explode(*args, **kwargs):
            raise RuntimeError("planner broke")

        monkeypatch.setattr(generator, "_render_planned", explode)
        generator.generate(SKIP_EDGE, debug=True)
        stage = generator.get_trace().get_stage("renderer_selected")
        assert stage.data["renderer"] == "classic"
        assert stage.data["planner_error"] == "RuntimeError: planner broke"

    def test_planned_picture_that_is_no_better_is_not_used(self, monkeypatch):
        generator = FlowchartGenerator()
        parsed = generator.parser.parse_with_groups(SKIP_EDGE)
        classic, base = generator._render_classic(parsed, None, None)

        # A "planned" result identical to the classic one is not an improvement.
        monkeypatch.setattr(
            generator, "_render_planned", lambda *args, **kwargs: (classic, base)
        )
        assert generator.generate(SKIP_EDGE) == classic
        assert generator.last_renderer == "classic"

    def test_parse_errors_still_surface(self):
        from retroflow import ParseError

        with pytest.raises(ParseError):
            FlowchartGenerator().generate("not a connection")


class TestTraces:
    def test_no_trace_without_debug(self):
        generator = FlowchartGenerator()
        generator.generate(SKIP_EDGE)
        assert generator.get_trace() is None

    def test_classic_trace_records_the_choice(self):
        generator = FlowchartGenerator()
        generator.generate(SIMPLE, debug=True)
        trace = generator.get_trace()
        stage = trace.get_stage("renderer_selected")
        assert stage.data == {
            "renderer": "classic",
            "issues": {},
            "other_renderer_issues": None,
            "planner_error": None,
        }
        assert trace.get_stage("forward_edges_drawn") is not None

    def test_planned_trace_has_the_planned_stages(self):
        generator = FlowchartGenerator()
        generator.generate(SKIP_EDGE, debug=True)
        trace = generator.get_trace()
        names = [stage.name for stage in trace.stages]
        assert names == [
            "parse",
            "layout",
            "dimensions",
            "routes_planned",
            "positions",
            "canvas_created",
            "boxes_drawn",
            "edges_drawn",
            "renderer_selected",
        ]
        assert trace.get_stage("layout").data["layers"] == [["A"], ["B"], ["C"], ["D"]]
        selected = trace.get_stage("renderer_selected").data
        assert selected["renderer"] == "planned"
        assert selected["issues"] == {}
        assert selected["other_renderer_issues"]  # what was wrong with classic

    def test_planned_trace_describes_the_routes(self):
        generator = FlowchartGenerator()
        generator.generate(SKIP_EDGE, debug=True)
        routes = generator.get_trace().get_stage("routes_planned").data
        assert routes["layers"] == [["A"], ["B"], ["C"], ["D"]]
        assert routes["conflicts"] == []
        assert routes["crossings"] == 0
        assert len(routes["tracks_per_channel"]) == 3

    def test_planned_trace_has_group_stage_when_there_are_groups(self):
        generator = FlowchartGenerator(direction="LR")
        generator.generate(GROUPED, debug=True)
        assert generator.last_renderer == "planned"
        stage = generator.get_trace().get_stage("groups_drawn")
        assert stage.data == {"num_groups": 2}

    def test_boxes_snapshot_has_no_edges(self):
        generator = FlowchartGenerator()
        generator.generate(SKIP_EDGE, debug=True)
        snapshot = "\n".join(generator.get_trace().get_canvas_at_stage("boxes_drawn"))
        assert not set("▼▲►◄┬") & set(snapshot)
        assert "│   A    │" in snapshot

    def test_every_wire_placement_has_a_reason(self):
        generator = FlowchartGenerator()
        generator.generate(SKIP_EDGE, debug=True)
        placements = generator.get_trace().get_placements_by_source("RoutePlanner")
        assert placements
        reasons = {placement.reason for placement in placements}
        assert reasons <= set(WIRE_REASONS.values()) | {"exit_port"}
        assert {"wire_vertical", "arrow_down", "exit_port"} <= reasons

    @pytest.mark.parametrize("text", [SIMPLE, SKIP_EDGE, GROUPED])
    @pytest.mark.parametrize("direction", ["TB", "LR"])
    def test_debug_output_equals_normal_output(self, text, direction):
        plain = FlowchartGenerator(direction=direction).generate(text)
        traced = FlowchartGenerator(direction=direction).generate(text, debug=True)
        assert plain == traced


class TestPlannedRendererOptions:
    """Options have to reach the planned renderer as well as the classic one."""

    def test_title_is_drawn_above_a_planned_diagram(self):
        generator = FlowchartGenerator(title="Pipeline")
        output = generator.generate(SKIP_EDGE)
        assert generator.last_renderer == "planned"
        rows = output.split("\n")
        assert "╔" in rows[0] and "Pipeline" in rows[1] and "╚" in rows[2]
        assert is_clean(SKIP_EDGE, generator)

    def test_title_argument_overrides_the_instance_title(self):
        generator = FlowchartGenerator(title="Instance")
        output = generator.generate(SKIP_EDGE, title="Call")
        assert "Call" in output and "Instance" not in output

    def test_title_wider_than_the_diagram_centres_the_diagram(self):
        # Titles wrap at word boundaries, so one long word makes a wide banner.
        title = "Deployment_Pipeline_Overview_For_The_Whole_Platform"
        generator = FlowchartGenerator(title=title)
        output = generator.generate(SKIP_EDGE)
        assert generator.last_renderer == "planned"
        rows = output.split("\n")
        assert len(rows[0]) == len(title) + 6
        box_row = next(row for row in rows if "│   A    │" in row)
        assert box_row.index("│") == (len(rows[0]) - 19) // 2
        assert is_clean(SKIP_EDGE, generator)

    def test_no_shadow(self):
        generator = FlowchartGenerator(shadow=False)
        output = generator.generate(SKIP_EDGE)
        assert generator.last_renderer == "planned"
        assert "░" not in output

    def test_rounded_boxes(self):
        generator = FlowchartGenerator(rounded=True)
        output = generator.generate(SKIP_EDGE)
        assert generator.last_renderer == "planned"
        assert "╭" in output and "╯" in output
        assert is_clean(SKIP_EDGE, generator)

    def test_expanded_boxes(self):
        compact = FlowchartGenerator().generate(SKIP_EDGE)
        expanded = FlowchartGenerator(compact=False).generate(SKIP_EDGE)
        assert len(expanded.split("\n")) > len(compact.split("\n"))

    def test_spacing_options_change_the_size(self):
        narrow = FlowchartGenerator(horizontal_spacing=2, vertical_spacing=1)
        wide = FlowchartGenerator(horizontal_spacing=30, vertical_spacing=8)
        text = "A -> B\nA -> C\nA -> D\nB -> E\nC -> E\nD -> E\nA -> E"
        small, large = narrow.generate(text), wide.generate(text)
        assert narrow.last_renderer == wide.last_renderer == "planned"
        assert len(small.split("\n")) < len(large.split("\n"))
        assert max(map(len, small.split("\n"))) < max(map(len, large.split("\n")))

    def test_min_box_width_is_respected(self):
        generator = FlowchartGenerator(min_box_width=20)
        output = generator.generate(SKIP_EDGE)
        assert generator.last_renderer == "planned"
        assert "┌" + "─" * 18 + "┐" in output

    def test_long_names_wrap(self):
        text = (
            "Collect the quarterly figures -> Summarise them\n"
            "Summarise them -> Publish\n"
            "Collect the quarterly figures -> Publish"
        )
        generator = FlowchartGenerator(max_text_width=12)
        output = generator.generate(text)
        assert generator.last_renderer == "planned"
        assert "quarterly" in output and "Collect the quarterly" not in output
        assert is_clean(text, generator)

    def test_group_titles_are_drawn(self):
        output = FlowchartGenerator().generate(GROUPED)
        assert "API Layer" in output and "Data Layer" in output
        assert "┄" in output and "┆" in output

    def test_save_txt_writes_the_planned_diagram(self, tmp_path):
        generator = FlowchartGenerator()
        target = tmp_path / "diagram.txt"
        generator.save_txt(SKIP_EDGE, str(target))
        assert (
            target.read_text(encoding="utf-8").strip()
            == generator.generate(SKIP_EDGE).strip()
        )

    def test_save_png_works_for_a_planned_diagram(self, tmp_path):
        generator = FlowchartGenerator()
        target = tmp_path / "diagram.png"
        generator.save_png(SKIP_EDGE, str(target))
        assert target.stat().st_size > 0
