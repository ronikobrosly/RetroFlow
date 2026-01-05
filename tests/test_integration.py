"""Integration tests for the FlowchartGenerator."""

import os
import tempfile

import pytest

from retroflow import FlowchartGenerator, ParseError, generate_flowchart


class TestFlowchartGenerator:
    """Integration tests for FlowchartGenerator class."""

    def test_generate_simple(self, simple_input, generator):
        """Generate flowchart from simple input."""
        result = generator.generate(simple_input)
        assert isinstance(result, str)
        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "D" in result

    def test_generate_branching(self, branching_input, generator):
        """Generate flowchart with branching."""
        result = generator.generate(branching_input)
        assert "Start" in result
        assert "Process1" in result
        assert "Process2" in result
        assert "End" in result

    def test_generate_cyclic(self, cyclic_input, generator):
        """Generate flowchart with cycles."""
        result = generator.generate(cyclic_input)
        assert "A" in result
        assert "B" in result
        assert "C" in result

    def test_generate_complex(self, complex_input, generator):
        """Generate complex flowchart."""
        result = generator.generate(complex_input)
        assert "Init" in result
        assert "Done" in result

    def test_generate_with_custom_box_size(self, simple_input):
        """Generate with custom box dimensions."""
        generator = FlowchartGenerator(box_width=15, box_height=5)
        result = generator.generate(simple_input)
        assert isinstance(result, str)

    def test_generate_with_custom_spacing(self, simple_input):
        """Generate with custom spacing."""
        generator = FlowchartGenerator(horizontal_spacing=8, vertical_spacing=5)
        result = generator.generate(simple_input)
        assert isinstance(result, str)

    def test_generate_with_simple_layout(self, simple_input):
        """Generate using simple layout algorithm."""
        generator = FlowchartGenerator(layout_algorithm="simple")
        result = generator.generate(simple_input)
        assert isinstance(result, str)

    def test_generate_invalid_input(self, generator):
        """Generate raises error for invalid input."""
        with pytest.raises(ParseError):
            generator.generate("not a valid flowchart")

    def test_generate_empty_input(self, generator):
        """Generate raises error for empty input."""
        with pytest.raises(ParseError):
            generator.generate("")

    def test_generate_with_stats(self, simple_input, generator):
        """Generate flowchart with statistics."""
        flowchart, stats = generator.generate_with_stats(simple_input)
        assert isinstance(flowchart, str)
        assert isinstance(stats, dict)
        assert "nodes" in stats
        assert "edges" in stats
        assert stats["nodes"] == 4
        assert stats["edges"] == 3

    def test_generate_with_stats_has_cycle_info(self, cyclic_input, generator):
        """Stats include cycle information."""
        _, stats = generator.generate_with_stats(cyclic_input)
        assert "has_cycle" in stats
        assert stats["has_cycle"] is True

    def test_generate_with_stats_acyclic(self, simple_input, generator):
        """Stats correctly identify acyclic graph."""
        _, stats = generator.generate_with_stats(simple_input)
        assert stats["has_cycle"] is False

    def test_save_txt(self, simple_input, generator):
        """Save flowchart as text file."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            output_path = f.name

        try:
            result_path = generator.save_txt(simple_input, output_path)
            assert result_path == output_path
            assert os.path.exists(output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "A" in content
            assert "B" in content
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_save_png(self, simple_input, generator):
        """Save flowchart as PNG image."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            result_path = generator.save_png(simple_input, output_path)
            assert result_path == output_path
            assert os.path.exists(output_path)
            # Check file is not empty
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_save_png_with_scale(self, simple_input, generator):
        """Save PNG with custom scale."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            generator.save_png(simple_input, output_path, scale=3)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestGenerateFlowchartFunction:
    """Tests for the generate_flowchart convenience function."""

    def test_generate_flowchart_simple(self, simple_input):
        """Convenience function generates flowchart."""
        result = generate_flowchart(simple_input)
        assert isinstance(result, str)
        assert "A" in result

    def test_generate_flowchart_with_options(self, simple_input):
        """Convenience function accepts options."""
        result = generate_flowchart(
            simple_input, box_width=15, layout_algorithm="simple"
        )
        assert isinstance(result, str)


class TestEndToEndWorkflows:
    """End-to-end workflow tests."""

    def test_workflow_parse_to_render(self):
        """Complete workflow from input to rendered output."""
        input_text = """
        Login -> Validate
        Validate -> Success
        Validate -> Failure
        Success -> Dashboard
        Failure -> Login
        """
        generator = FlowchartGenerator()
        result = generator.generate(input_text)

        # Verify all nodes present
        for node in ["Login", "Validate", "Success", "Failure", "Dashboard"]:
            assert node in result

    def test_workflow_large_graph(self):
        """Handle larger graphs."""
        # Create a 10-node chain
        connections = [f"Node{i} -> Node{i + 1}" for i in range(10)]
        input_text = "\n".join(connections)

        generator = FlowchartGenerator()
        result = generator.generate(input_text)

        for i in range(11):
            assert f"Node{i}" in result

    def test_workflow_diamond_pattern(self):
        """Diamond pattern graph."""
        input_text = """
        Start -> Left
        Start -> Right
        Left -> End
        Right -> End
        """
        generator = FlowchartGenerator()
        flowchart, stats = generator.generate_with_stats(input_text)

        assert stats["nodes"] == 4
        assert stats["edges"] == 4
        assert stats["has_cycle"] is False

    def test_workflow_multiline_node_names(self):
        """Nodes with spaces in names."""
        input_text = """
        User Login -> Check Credentials
        Check Credentials -> Access Granted
        Check Credentials -> Access Denied
        """
        # Use wider boxes to fit longer node names
        generator = FlowchartGenerator(box_width=20)
        result = generator.generate(input_text)

        assert "User Login" in result
        assert "Check Credentials" in result
