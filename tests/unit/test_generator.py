"""Unit tests for the generator module."""

import os
import tempfile

from retroflow.generator import FlowchartGenerator
from retroflow.renderer import ARROW_CHARS, BOX_CHARS


class TestFlowchartGeneratorInit:
    """Tests for FlowchartGenerator initialization."""

    def test_default_initialization(self):
        """Test FlowchartGenerator with default parameters."""
        gen = FlowchartGenerator()
        assert gen.max_text_width == 22
        assert gen.min_box_width == 10
        assert gen.horizontal_spacing == 12
        assert gen.vertical_spacing == 6
        assert gen.shadow is True

    def test_custom_max_text_width(self):
        """Test FlowchartGenerator with custom max_text_width."""
        gen = FlowchartGenerator(max_text_width=30)
        assert gen.max_text_width == 30

    def test_custom_min_box_width(self):
        """Test FlowchartGenerator with custom min_box_width."""
        gen = FlowchartGenerator(min_box_width=15)
        assert gen.min_box_width == 15

    def test_custom_horizontal_spacing(self):
        """Test FlowchartGenerator with custom horizontal_spacing."""
        gen = FlowchartGenerator(horizontal_spacing=20)
        assert gen.horizontal_spacing == 20

    def test_custom_vertical_spacing(self):
        """Test FlowchartGenerator with custom vertical_spacing."""
        gen = FlowchartGenerator(vertical_spacing=10)
        assert gen.vertical_spacing == 10

    def test_shadow_disabled(self):
        """Test FlowchartGenerator with shadow disabled."""
        gen = FlowchartGenerator(shadow=False)
        assert gen.shadow is False

    def test_all_custom_parameters(self):
        """Test FlowchartGenerator with all custom parameters."""
        gen = FlowchartGenerator(
            max_text_width=25,
            min_box_width=12,
            horizontal_spacing=15,
            vertical_spacing=8,
            shadow=False,
        )
        assert gen.max_text_width == 25
        assert gen.min_box_width == 12
        assert gen.horizontal_spacing == 15
        assert gen.vertical_spacing == 8
        assert gen.shadow is False

    def test_components_initialized(self):
        """Test that internal components are initialized."""
        gen = FlowchartGenerator()
        assert gen.parser is not None
        assert gen.layout_engine is not None
        assert gen.box_renderer is not None


class TestFlowchartGeneratorGenerate:
    """Tests for FlowchartGenerator.generate method."""

    def test_generate_simple_linear(self, generator, simple_input):
        """Test generating simple linear flowchart."""
        result = generator.generate(simple_input)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_contains_node_names(self, generator, simple_input):
        """Test that generated output contains node names."""
        result = generator.generate(simple_input)
        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "D" in result

    def test_generate_contains_box_characters(self, generator, simple_input):
        """Test that generated output contains box characters."""
        result = generator.generate(simple_input)
        assert BOX_CHARS["top_left"] in result
        assert BOX_CHARS["top_right"] in result
        assert BOX_CHARS["bottom_left"] in result
        assert BOX_CHARS["bottom_right"] in result

    def test_generate_contains_arrows(self, generator, simple_input):
        """Test that generated output contains arrow characters."""
        result = generator.generate(simple_input)
        assert ARROW_CHARS["down"] in result

    def test_generate_contains_shadows(self, generator, simple_input):
        """Test that generated output contains shadow characters."""
        result = generator.generate(simple_input)
        assert BOX_CHARS["shadow"] in result

    def test_generate_without_shadows(self, simple_input):
        """Test generating without shadows."""
        gen = FlowchartGenerator(shadow=False)
        result = gen.generate(simple_input)
        assert BOX_CHARS["shadow"] not in result

    def test_generate_branching(self, generator, branching_input):
        """Test generating branching flowchart."""
        result = generator.generate(branching_input)
        assert "Start" in result
        assert "Process1" in result
        assert "Process2" in result
        assert "End" in result

    def test_generate_cyclic(self, generator, cyclic_input):
        """Test generating cyclic flowchart."""
        result = generator.generate(cyclic_input)
        assert "A" in result
        assert "B" in result
        assert "C" in result
        # Should have arrows for back edges too
        assert ARROW_CHARS["right"] in result or ARROW_CHARS["down"] in result

    def test_generate_complex(self, generator, complex_input):
        """Test generating complex flowchart."""
        result = generator.generate(complex_input)
        assert "Init" in result
        assert "Validate" in result
        assert "Process" in result
        assert "Done" in result

    def test_generate_with_spaces_in_names(self, generator):
        """Test generating with multi-word node names."""
        input_text = """
        Start Here -> Process Data
        Process Data -> End Here
        """
        result = generator.generate(input_text)
        assert "Start Here" in result
        assert "Process Data" in result
        assert "End Here" in result

    def test_generate_single_edge(self, generator):
        """Test generating with single edge."""
        result = generator.generate("A -> B")
        assert "A" in result
        assert "B" in result

    def test_generate_long_chain(self, generator):
        """Test generating a long chain of nodes."""
        input_text = """
        N1 -> N2
        N2 -> N3
        N3 -> N4
        N4 -> N5
        N5 -> N6
        """
        result = generator.generate(input_text)
        for i in range(1, 7):
            assert f"N{i}" in result


class TestFlowchartGeneratorSaveTxt:
    """Tests for FlowchartGenerator.save_txt method."""

    def test_save_txt_creates_file(self, generator, simple_input):
        """Test that save_txt creates a file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            filename = f.name

        try:
            generator.save_txt(simple_input, filename)
            assert os.path.exists(filename)
        finally:
            if os.path.exists(filename):
                os.remove(filename)

    def test_save_txt_content(self, generator, simple_input):
        """Test that save_txt writes correct content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            filename = f.name

        try:
            generator.save_txt(simple_input, filename)
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
            assert "A" in content
            assert "B" in content
            assert BOX_CHARS["top_left"] in content
        finally:
            if os.path.exists(filename):
                os.remove(filename)

    def test_save_txt_boxes_only_parameter(self, generator, simple_input):
        """Test that boxes_only parameter is accepted (but ignored)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            filename = f.name

        try:
            # Should not raise even with boxes_only parameter
            generator.save_txt(simple_input, filename, boxes_only=True)
            assert os.path.exists(filename)
        finally:
            if os.path.exists(filename):
                os.remove(filename)

    def test_save_txt_overwrites_existing(self, generator, simple_input):
        """Test that save_txt overwrites existing file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Original content")
            filename = f.name

        try:
            generator.save_txt(simple_input, filename)
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
            assert "Original content" not in content
            assert "A" in content
        finally:
            if os.path.exists(filename):
                os.remove(filename)


class TestFlowchartGeneratorInternalMethods:
    """Tests for FlowchartGenerator internal methods."""

    def test_calculate_all_box_dimensions(self, generator):
        """Test _calculate_all_box_dimensions method."""
        input_text = "A -> B"
        connections = generator.parser.parse(input_text)
        layout_result = generator.layout_engine.layout(connections)

        dimensions = generator._calculate_all_box_dimensions(layout_result)

        assert "A" in dimensions
        assert "B" in dimensions
        assert dimensions["A"].width >= generator.min_box_width
        assert dimensions["B"].width >= generator.min_box_width

    def test_min_box_width_enforced(self, generator):
        """Test that minimum box width is enforced."""
        # Use a very short node name
        input_text = "X -> Y"
        connections = generator.parser.parse(input_text)
        layout_result = generator.layout_engine.layout(connections)

        dimensions = generator._calculate_all_box_dimensions(layout_result)

        assert dimensions["X"].width >= generator.min_box_width
        assert dimensions["Y"].width >= generator.min_box_width

    def test_calculate_positions(self, generator):
        """Test _calculate_positions method."""
        input_text = "A -> B\nB -> C"
        connections = generator.parser.parse(input_text)
        layout_result = generator.layout_engine.layout(connections)
        box_dimensions = generator._calculate_all_box_dimensions(layout_result)

        positions = generator._calculate_positions(layout_result, box_dimensions)

        assert "A" in positions
        assert "B" in positions
        assert "C" in positions

        # Each position should be (x, y) tuple
        for name, pos in positions.items():
            assert isinstance(pos, tuple)
            assert len(pos) == 2

    def test_calculate_positions_with_margin(self, generator):
        """Test _calculate_positions with left margin."""
        input_text = "A -> B"
        connections = generator.parser.parse(input_text)
        layout_result = generator.layout_engine.layout(connections)
        box_dimensions = generator._calculate_all_box_dimensions(layout_result)

        positions_no_margin = generator._calculate_positions(
            layout_result, box_dimensions, left_margin=0
        )
        positions_with_margin = generator._calculate_positions(
            layout_result, box_dimensions, left_margin=10
        )

        # With margin, x positions should be shifted
        for name in positions_no_margin:
            assert positions_with_margin[name][0] >= positions_no_margin[name][0]

    def test_calculate_canvas_size(self, generator):
        """Test _calculate_canvas_size method."""
        input_text = "A -> B"
        connections = generator.parser.parse(input_text)
        layout_result = generator.layout_engine.layout(connections)
        box_dimensions = generator._calculate_all_box_dimensions(layout_result)
        box_positions = generator._calculate_positions(layout_result, box_dimensions)

        width, height = generator._calculate_canvas_size(box_dimensions, box_positions)

        assert width > 0
        assert height > 0

    def test_calculate_port_x_single(self, generator):
        """Test _calculate_port_x for single port."""
        box_x = 10
        box_width = 20

        port_x = generator._calculate_port_x(box_x, box_width, 0, 1)

        # Single port should be centered
        expected_center = box_x + box_width // 2
        assert port_x == expected_center

    def test_calculate_port_x_multiple(self, generator):
        """Test _calculate_port_x for multiple ports."""
        box_x = 10
        box_width = 20

        port_x_0 = generator._calculate_port_x(box_x, box_width, 0, 3)
        port_x_1 = generator._calculate_port_x(box_x, box_width, 1, 3)
        port_x_2 = generator._calculate_port_x(box_x, box_width, 2, 3)

        # Ports should be distributed
        assert port_x_0 < port_x_1 < port_x_2


class TestFlowchartGeneratorEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_generate_with_back_edges(self, generator):
        """Test generation with back edges (cycles)."""
        input_text = """
        A -> B
        B -> C
        C -> B
        """
        result = generator.generate(input_text)
        assert "A" in result
        assert "B" in result
        assert "C" in result

    def test_generate_diamond_pattern(self, generator):
        """Test generation with diamond pattern."""
        input_text = """
        A -> B
        A -> C
        B -> D
        C -> D
        """
        result = generator.generate(input_text)
        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "D" in result

    def test_generate_wide_branching(self, generator):
        """Test generation with wide branching."""
        input_text = """
        Start -> A
        Start -> B
        Start -> C
        Start -> D
        """
        result = generator.generate(input_text)
        assert "Start" in result
        assert "A" in result
        assert "D" in result

    def test_generate_deep_nesting(self, generator):
        """Test generation with deep nesting."""
        input_text = """
        L1 -> L2
        L2 -> L3
        L3 -> L4
        L4 -> L5
        L5 -> L6
        L6 -> L7
        L7 -> L8
        """
        result = generator.generate(input_text)
        for i in range(1, 9):
            assert f"L{i}" in result

    def test_generate_multiple_roots(self, generator):
        """Test generation with multiple root nodes."""
        input_text = """
        A -> C
        B -> C
        """
        result = generator.generate(input_text)
        assert "A" in result
        assert "B" in result
        assert "C" in result

    def test_generate_multiple_sinks(self, generator):
        """Test generation with multiple sink nodes."""
        input_text = """
        A -> B
        A -> C
        """
        result = generator.generate(input_text)
        assert "A" in result
        assert "B" in result
        assert "C" in result
