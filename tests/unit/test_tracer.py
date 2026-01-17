"""
Tests for the tracer module.

These tests verify the debug tracing infrastructure used to capture
detailed information about the flowchart generation pipeline.
"""


from retroflow.tracer import CharacterPlacement, PipelineStage, RenderTrace


class TestCharacterPlacement:
    """Tests for CharacterPlacement dataclass."""

    def test_creation(self):
        """Test basic creation of CharacterPlacement."""
        placement = CharacterPlacement(
            x=10, y=5, char="│", previous_char=" ", reason="vertical_line",
            source="EdgeDrawer._draw_vertical_line"
        )
        assert placement.x == 10
        assert placement.y == 5
        assert placement.char == "│"
        assert placement.previous_char == " "
        assert placement.reason == "vertical_line"
        assert placement.source == "EdgeDrawer._draw_vertical_line"

    def test_str_new_placement(self):
        """Test string representation for new placement (empty previous)."""
        placement = CharacterPlacement(
            x=10, y=5, char="│", previous_char=" ", reason="vertical_line",
            source="EdgeDrawer"
        )
        result = str(placement)
        assert "(10,5)" in result
        assert "'│'" in result
        assert "vertical_line" in result
        assert "EdgeDrawer" in result

    def test_str_upgrade_placement(self):
        """Test string representation for upgrade (non-empty previous)."""
        placement = CharacterPlacement(
            x=10, y=5, char="┼", previous_char="│",
            reason="vertical_crosses_horizontal", source="EdgeDrawer"
        )
        result = str(placement)
        assert "(10,5)" in result
        assert "'│' -> '┼'" in result
        assert "vertical_crosses_horizontal" in result


class TestPipelineStage:
    """Tests for PipelineStage dataclass."""

    def test_creation_basic(self):
        """Test basic creation without canvas snapshot."""
        stage = PipelineStage(
            name="parse",
            data={"connections": [("A", "B")]}
        )
        assert stage.name == "parse"
        assert stage.data["connections"] == [("A", "B")]
        assert stage.canvas_snapshot is None

    def test_creation_with_snapshot(self):
        """Test creation with canvas snapshot."""
        stage = PipelineStage(
            name="boxes_drawn",
            data={"num_boxes": 3},
            canvas_snapshot=["┌───┐", "│ A │", "└───┘"]
        )
        assert stage.name == "boxes_drawn"
        assert stage.canvas_snapshot is not None
        assert len(stage.canvas_snapshot) == 3

    def test_str_without_snapshot(self):
        """Test string representation without canvas."""
        stage = PipelineStage(name="parse", data={"connections": 5})
        result = str(stage)
        assert "parse" in result
        assert "connections" in result
        assert "5" in result

    def test_str_with_snapshot(self):
        """Test string representation with canvas preview."""
        stage = PipelineStage(
            name="boxes_drawn",
            data={"num_boxes": 2},
            canvas_snapshot=["line1", "line2"]
        )
        result = str(stage)
        assert "boxes_drawn" in result
        assert "Canvas preview" in result


class TestRenderTrace:
    """Tests for RenderTrace class."""

    def test_creation(self):
        """Test basic creation."""
        trace = RenderTrace()
        assert trace.stages == []
        assert trace.character_placements == []
        assert trace.input_text == ""
        assert trace.direction == "TB"

    def test_creation_with_params(self):
        """Test creation with parameters."""
        trace = RenderTrace(input_text="A -> B", direction="LR")
        assert trace.input_text == "A -> B"
        assert trace.direction == "LR"

    def test_add_stage(self):
        """Test adding a pipeline stage."""
        trace = RenderTrace()
        trace.add_stage("parse", {"connections": [("A", "B")]})

        assert len(trace.stages) == 1
        assert trace.stages[0].name == "parse"
        assert trace.stages[0].data["connections"] == [("A", "B")]

    def test_add_stage_with_canvas(self):
        """Test adding a stage with canvas snapshot."""
        from retroflow.renderer import Canvas

        trace = RenderTrace()
        canvas = Canvas(10, 3)
        canvas.set(0, 0, "┌")
        canvas.set(1, 0, "─")

        trace.add_stage("boxes_drawn", {"num_boxes": 1}, canvas)

        assert len(trace.stages) == 1
        assert trace.stages[0].canvas_snapshot is not None

    def test_add_placement(self):
        """Test adding a character placement."""
        trace = RenderTrace()
        trace.add_placement(10, 5, "│", " ", "vertical_line", "EdgeDrawer")

        assert len(trace.character_placements) == 1
        p = trace.character_placements[0]
        assert p.x == 10
        assert p.y == 5
        assert p.char == "│"

    def test_get_stage(self):
        """Test retrieving a stage by name."""
        trace = RenderTrace()
        trace.add_stage("parse", {"data": 1})
        trace.add_stage("layout", {"data": 2})

        stage = trace.get_stage("layout")
        assert stage is not None
        assert stage.data["data"] == 2

        missing = trace.get_stage("nonexistent")
        assert missing is None

    def test_get_canvas_at_stage(self):
        """Test retrieving canvas snapshot at a stage."""
        from retroflow.renderer import Canvas

        trace = RenderTrace()
        canvas = Canvas(5, 3)
        canvas.set(0, 0, "X")

        trace.add_stage("test", {}, canvas)

        snapshot = trace.get_canvas_at_stage("test")
        assert snapshot is not None
        assert len(snapshot) > 0

    def test_get_canvas_at_stage_missing(self):
        """Test retrieving canvas from non-existent stage."""
        trace = RenderTrace()
        trace.add_stage("test", {})  # No canvas

        result = trace.get_canvas_at_stage("test")
        assert result is None

        result = trace.get_canvas_at_stage("nonexistent")
        assert result is None

    def test_get_placements_at(self):
        """Test getting placements at specific coordinates."""
        trace = RenderTrace()
        trace.add_placement(10, 5, "│", " ", "r1", "s1")
        trace.add_placement(10, 5, "┼", "│", "r2", "s2")
        trace.add_placement(10, 6, "│", " ", "r3", "s3")

        at_10_5 = trace.get_placements_at(10, 5)
        assert len(at_10_5) == 2

        at_10_6 = trace.get_placements_at(10, 6)
        assert len(at_10_6) == 1

        at_0_0 = trace.get_placements_at(0, 0)
        assert len(at_0_0) == 0

    def test_get_character_upgrades(self):
        """Test finding character upgrade operations."""
        trace = RenderTrace()
        trace.add_placement(10, 5, "│", " ", "new", "s1")  # New
        trace.add_placement(10, 5, "┼", "│", "upgrade", "s2")  # Upgrade
        trace.add_placement(11, 5, "─", " ", "new", "s3")  # New
        trace.add_placement(11, 5, "┼", "─", "upgrade", "s4")  # Upgrade
        # Over shadow (not considered an upgrade)
        trace.add_placement(12, 5, "│", "░", "over_shadow", "s5")

        upgrades = trace.get_character_upgrades()
        assert len(upgrades) == 2
        assert all(p.previous_char not in (" ", "░") for p in upgrades)

    def test_get_placements_by_source(self):
        """Test filtering placements by source."""
        trace = RenderTrace()
        trace.add_placement(0, 0, "│", " ", "r", "EdgeDrawer.method1")
        trace.add_placement(0, 1, "─", " ", "r", "EdgeDrawer.method2")
        trace.add_placement(0, 2, "┌", " ", "r", "BoxRenderer.draw")

        edge_placements = trace.get_placements_by_source("EdgeDrawer")
        assert len(edge_placements) == 2

        box_placements = trace.get_placements_by_source("BoxRenderer")
        assert len(box_placements) == 1

    def test_get_placements_by_reason(self):
        """Test filtering placements by reason."""
        trace = RenderTrace()
        trace.add_placement(0, 0, "│", " ", "vertical_line", "s")
        trace.add_placement(0, 1, "│", " ", "vertical_line", "s")
        trace.add_placement(0, 2, "─", " ", "horizontal_line", "s")
        trace.add_placement(0, 3, "┼", "│", "upgrade_to_cross", "s")

        verticals = trace.get_placements_by_reason("vertical")
        assert len(verticals) == 2

        upgrades = trace.get_placements_by_reason("upgrade")
        assert len(upgrades) == 1

    def test_summary(self):
        """Test generating a summary."""
        trace = RenderTrace(input_text="A -> B", direction="TB")
        trace.add_stage("parse", {"connections": 1})
        trace.add_stage("layout", {"layers": 2})
        trace.add_placement(0, 0, "│", " ", "vertical_line", "s")
        trace.add_placement(0, 1, "┼", "│", "upgrade", "s")

        summary = trace.summary()

        assert "RENDER TRACE SUMMARY" in summary
        assert "Direction: TB" in summary
        assert "A -> B" in summary
        assert "Pipeline stages: 2" in summary
        assert "Total character placements: 2" in summary
        assert "Character upgrades (overwrites): 1" in summary

    def test_dump(self):
        """Test generating a full dump."""
        trace = RenderTrace(input_text="A -> B")
        trace.add_stage("parse", {"x": 1})
        trace.add_placement(0, 0, "X", " ", "test", "source")

        dump = trace.dump()

        assert "RENDER TRACE SUMMARY" in dump
        assert "DETAILED TRACE" in dump
        assert "PIPELINE STAGES" in dump
        assert "CHARACTER PLACEMENTS" in dump

    def test_dump_to_file(self, tmp_path):
        """Test dumping trace to a file."""
        trace = RenderTrace(input_text="A -> B")
        trace.add_stage("test", {"data": 1})

        filepath = tmp_path / "trace.txt"
        trace.dump_to_file(str(filepath))

        assert filepath.exists()
        content = filepath.read_text()
        assert "RENDER TRACE SUMMARY" in content

    def test_dump_canvas_evolution(self):
        """Test dumping canvas evolution through stages."""
        from retroflow.renderer import Canvas

        trace = RenderTrace()

        # Stage without canvas
        trace.add_stage("parse", {})

        # Stage with canvas
        canvas1 = Canvas(5, 2)
        canvas1.set(0, 0, "A")
        trace.add_stage("stage1", {}, canvas1)

        canvas2 = Canvas(5, 2)
        canvas2.set(0, 0, "B")
        trace.add_stage("stage2", {}, canvas2)

        evolution = trace.dump_canvas_evolution()

        assert "CANVAS EVOLUTION" in evolution
        assert "stage1" in evolution
        assert "stage2" in evolution


class TestRenderTraceIntegration:
    """Integration tests for RenderTrace with actual flowchart generation."""

    def test_debug_mode_captures_trace(self):
        """Test that debug mode captures a trace."""
        from retroflow import FlowchartGenerator

        gen = FlowchartGenerator()
        gen.generate("A -> B", debug=True)

        trace = gen.get_trace()
        assert trace is not None
        assert len(trace.stages) > 0
        assert len(trace.character_placements) > 0

    def test_debug_mode_captures_all_stages(self):
        """Test that all expected pipeline stages are captured."""
        from retroflow import FlowchartGenerator

        gen = FlowchartGenerator()
        gen.generate("A -> B\nB -> C", debug=True)

        trace = gen.get_trace()
        stage_names = [s.name for s in trace.stages]

        assert "parse" in stage_names
        assert "layout" in stage_names
        assert "dimensions" in stage_names
        assert "positions" in stage_names
        assert "canvas_created" in stage_names
        assert "boxes_drawn" in stage_names
        assert "forward_edges_drawn" in stage_names

    def test_debug_mode_off_no_trace(self):
        """Test that trace is None when debug mode is off."""
        from retroflow import FlowchartGenerator

        gen = FlowchartGenerator()
        gen.generate("A -> B", debug=False)

        trace = gen.get_trace()
        assert trace is None

    def test_debug_mode_with_back_edges(self):
        """Test trace capture with cyclic graphs."""
        from retroflow import FlowchartGenerator

        gen = FlowchartGenerator()
        gen.generate("A -> B\nB -> C\nC -> A", debug=True)

        trace = gen.get_trace()
        stage_names = [s.name for s in trace.stages]

        assert "back_edges_drawn" in stage_names
