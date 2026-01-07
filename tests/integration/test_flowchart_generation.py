"""Integration tests for complete flowchart generation.

These tests cover end-to-end scenarios based on real-world use cases,
inspired by the examples in testing_retroflow.py.
"""

import os
import tempfile

from retroflow import FlowchartGenerator
from retroflow.renderer import ARROW_CHARS, BOX_CHARS, LINE_CHARS


class TestSimpleLinearFlow:
    """Integration tests for simple linear flowcharts."""

    def test_simple_linear_a_to_d(self, generator):
        """Test simple A -> B -> C -> D linear flow."""
        input_text = """
        A -> B
        B -> C
        C -> D
        """
        result = generator.generate(input_text)

        # All nodes should be present
        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "D" in result

        # Should have box structure
        assert BOX_CHARS["top_left"] in result
        assert BOX_CHARS["bottom_right"] in result

        # Should have vertical connections (arrows going down)
        assert ARROW_CHARS["down"] in result

    def test_linear_flow_with_long_names(self, generator):
        """Test linear flow with longer node names."""
        input_text = """
        START -> INITIALIZE
        INITIALIZE -> PROCESS
        PROCESS -> COMPLETE
        """
        result = generator.generate(input_text)

        assert "START" in result
        assert "INITIALIZE" in result
        assert "PROCESS" in result
        assert "COMPLETE" in result


class TestBranchingFlow:
    """Integration tests for branching flowcharts."""

    def test_branching_and_merging(self, generator):
        """Test branching from one node to multiple and merging back."""
        input_text = """
        START -> PROCESS A
        START -> PROCESS B
        PROCESS A -> END
        PROCESS B -> END
        """
        result = generator.generate(input_text)

        assert "START" in result
        assert "PROCESS A" in result
        assert "PROCESS B" in result
        assert "END" in result

        # Should have multiple downward arrows
        assert result.count(ARROW_CHARS["down"]) >= 3

    def test_wide_branching(self, generator):
        """Test wide branching pattern."""
        input_text = """
        ROOT -> BRANCH1
        ROOT -> BRANCH2
        ROOT -> BRANCH3
        ROOT -> BRANCH4
        """
        result = generator.generate(input_text)

        assert "ROOT" in result
        assert "BRANCH1" in result
        assert "BRANCH4" in result


class TestDataPipelineFlow:
    """Integration tests for ETL/data pipeline patterns."""

    def test_etl_pipeline(self, generator):
        """Test ETL data pipeline pattern."""
        input_text = """
        EXTRACT -> TRANSFORM
        TRANSFORM -> VALIDATE
        VALIDATE -> LOAD
        LOAD -> DONE
        VALIDATE -> ERROR
        ERROR -> LOG
        """
        result = generator.generate(input_text)

        # All pipeline stages present
        assert "EXTRACT" in result
        assert "TRANSFORM" in result
        assert "VALIDATE" in result
        assert "LOAD" in result
        assert "DONE" in result
        assert "ERROR" in result
        assert "LOG" in result

        # Should have branching (VALIDATE goes to both LOAD and ERROR)
        assert result.count(ARROW_CHARS["down"]) >= 4


class TestCyclicFlow:
    """Integration tests for flowcharts with cycles."""

    def test_software_workflow_with_cycles(self, generator):
        """Test software development workflow with review cycles."""
        input_text = """
        PLAN -> DESIGN
        DESIGN -> CODE
        CODE -> TEST
        TEST -> REVIEW
        REVIEW -> DEPLOY
        TEST -> CODE
        REVIEW -> CODE
        """
        result = generator.generate(input_text)

        assert "PLAN" in result
        assert "DESIGN" in result
        assert "CODE" in result
        assert "TEST" in result
        assert "REVIEW" in result
        assert "DEPLOY" in result

        # Back edges should create arrows going back (right arrows for margin routing)
        assert ARROW_CHARS["right"] in result or ARROW_CHARS["down"] in result

    def test_simple_cycle(self, generator):
        """Test simple A -> B -> C -> A cycle."""
        input_text = """
        A -> B
        B -> C
        C -> A
        """
        result = generator.generate(input_text)

        assert "A" in result
        assert "B" in result
        assert "C" in result

    def test_retry_pattern(self, generator):
        """Test common retry pattern with cycle."""
        input_text = """
        REQUEST -> VALIDATE
        VALIDATE -> PROCESS
        PROCESS -> RESPONSE
        VALIDATE -> ERROR HANDLER
        PROCESS -> ERROR HANDLER
        ERROR HANDLER -> LOG
        ERROR HANDLER -> RETRY
        RETRY -> VALIDATE
        """
        result = generator.generate(input_text)

        assert "REQUEST" in result
        assert "VALIDATE" in result
        assert "ERROR HANDLER" in result
        assert "RETRY" in result


class TestMicroserviceArchitecture:
    """Integration tests for microservice architecture patterns."""

    def test_microservice_pattern(self, generator):
        """Test microservice architecture diagram."""
        input_text = """
        API GATEWAY -> AUTH SERVICE
        API GATEWAY -> USER SERVICE
        API GATEWAY -> ORDER SERVICE
        AUTH SERVICE -> DATABASE
        USER SERVICE -> DATABASE
        ORDER SERVICE -> DATABASE
        ORDER SERVICE -> PAYMENT SERVICE
        PAYMENT SERVICE -> NOTIFICATION
        """
        result = generator.generate(input_text)

        # All services present
        assert "API GATEWAY" in result
        assert "AUTH SERVICE" in result
        assert "USER SERVICE" in result
        assert "ORDER SERVICE" in result
        assert "DATABASE" in result
        assert "PAYMENT SERVICE" in result
        assert "NOTIFICATION" in result


class TestCICDPipeline:
    """Integration tests for CI/CD pipeline patterns."""

    def test_cicd_pipeline(self, generator):
        """Test CI/CD pipeline diagram."""
        input_text = """
        GIT PUSH -> BUILD
        BUILD -> UNIT TESTS
        UNIT TESTS -> INTEGRATION TESTS
        INTEGRATION TESTS -> SECURITY SCAN
        SECURITY SCAN -> DEPLOY STAGING
        DEPLOY STAGING -> E2E TESTS
        E2E TESTS -> DEPLOY PROD
        UNIT TESTS -> NOTIFY FAILURE
        INTEGRATION TESTS -> NOTIFY FAILURE
        SECURITY SCAN -> NOTIFY FAILURE
        """
        result = generator.generate(input_text)

        assert "GIT PUSH" in result
        assert "BUILD" in result
        assert "UNIT TESTS" in result
        assert "DEPLOY PROD" in result
        assert "NOTIFY FAILURE" in result


class TestAuthenticationFlow:
    """Integration tests for authentication flow patterns."""

    def test_auth_flow_with_cycles(self, generator):
        """Test authentication flow with login retry cycles."""
        input_text = """
        USER -> LOGIN
        LOGIN -> AUTHENTICATE
        AUTHENTICATE -> VALID TOKEN
        AUTHENTICATE -> INVALID
        VALID TOKEN -> DASHBOARD
        INVALID -> LOGIN
        DASHBOARD -> LOGOUT
        LOGOUT -> LOGIN
        """
        result = generator.generate(input_text)

        assert "USER" in result
        assert "LOGIN" in result
        assert "AUTHENTICATE" in result
        assert "VALID TOKEN" in result
        assert "INVALID" in result
        assert "DASHBOARD" in result
        assert "LOGOUT" in result


class TestFileOutput:
    """Integration tests for file output functionality."""

    def test_save_and_load_txt(self, generator):
        """Test saving flowchart to file and verifying content."""
        input_text = """
        START -> PROCESS
        PROCESS -> END
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            filename = f.name

        try:
            generator.save_txt(input_text, filename)

            # Read back and verify
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()

            assert "START" in content
            assert "PROCESS" in content
            assert "END" in content
            assert BOX_CHARS["top_left"] in content
        finally:
            if os.path.exists(filename):
                os.remove(filename)

    def test_save_complex_flowchart(self, generator, complex_input):
        """Test saving complex flowchart to file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            filename = f.name

        try:
            generator.save_txt(complex_input, filename)

            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()

            assert "Init" in content
            assert "Done" in content
            assert len(content) > 100  # Should have substantial content
        finally:
            if os.path.exists(filename):
                os.remove(filename)


class TestCustomConfiguration:
    """Integration tests for custom generator configuration."""

    def test_no_shadow_mode(self):
        """Test flowchart generation without shadows."""
        generator = FlowchartGenerator(shadow=False)
        result = generator.generate("A -> B")

        assert "A" in result
        assert "B" in result
        assert BOX_CHARS["shadow"] not in result

    def test_custom_spacing(self):
        """Test flowchart with custom spacing."""
        gen_default = FlowchartGenerator()
        gen_wide = FlowchartGenerator(horizontal_spacing=20, vertical_spacing=10)

        input_text = "A -> B\nA -> C"

        result_default = gen_default.generate(input_text)
        result_wide = gen_wide.generate(input_text)

        # Wide spacing should produce larger output
        assert len(result_wide) > len(result_default)

    def test_custom_min_box_width(self):
        """Test flowchart with custom minimum box width."""
        gen_narrow = FlowchartGenerator(min_box_width=5)
        gen_wide = FlowchartGenerator(min_box_width=20)

        input_text = "A -> B"

        result_narrow = gen_narrow.generate(input_text)
        result_wide = gen_wide.generate(input_text)

        # Wider minimum should produce wider output
        narrow_width = max(len(line) for line in result_narrow.split("\n"))
        wide_width = max(len(line) for line in result_wide.split("\n"))
        assert wide_width > narrow_width


class TestOutputStructure:
    """Integration tests for output structure verification."""

    def test_box_structure_complete(self, generator):
        """Test that generated boxes have complete structure."""
        result = generator.generate("Test -> Node")

        lines = result.split("\n")

        # Should have complete boxes
        has_top_left = any(BOX_CHARS["top_left"] in line for line in lines)
        has_top_right = any(BOX_CHARS["top_right"] in line for line in lines)
        has_bottom_left = any(BOX_CHARS["bottom_left"] in line for line in lines)
        has_bottom_right = any(BOX_CHARS["bottom_right"] in line for line in lines)

        assert has_top_left
        assert has_top_right
        assert has_bottom_left
        assert has_bottom_right

    def test_connections_present(self, generator):
        """Test that connections are drawn."""
        result = generator.generate("A -> B\nB -> C")

        # Should have vertical line characters (for connections)
        has_vertical = LINE_CHARS["vertical"] in result
        has_arrow = ARROW_CHARS["down"] in result

        assert has_vertical or has_arrow

    def test_horizontal_connections(self, generator):
        """Test horizontal connections in branching."""
        input_text = """
        A -> B
        A -> C
        B -> D
        C -> D
        """
        result = generator.generate(input_text)

        # Should have some horizontal elements for connecting branches
        lines = result.split("\n")
        has_horizontal_elements = any(
            LINE_CHARS["horizontal"] in line
            or LINE_CHARS["corner_bottom_left"] in line
            or LINE_CHARS["corner_bottom_right"] in line
            for line in lines
        )

        assert has_horizontal_elements or ARROW_CHARS["down"] in result


class TestEdgeCases:
    """Integration tests for edge cases."""

    def test_single_node_pair(self, generator):
        """Test simplest possible flowchart."""
        result = generator.generate("A -> B")

        assert "A" in result
        assert "B" in result
        assert BOX_CHARS["top_left"] in result

    def test_very_long_node_names(self, generator):
        """Test with very long node names."""
        input_text = """
        VERY LONG START NODE NAME HERE -> ANOTHER VERY LONG NODE NAME
        ANOTHER VERY LONG NODE NAME -> FINAL DESTINATION NODE
        """
        result = generator.generate(input_text)

        assert "VERY LONG START" in result
        assert "ANOTHER VERY LONG" in result
        assert "FINAL DESTINATION" in result

    def test_many_edges_to_single_node(self, generator):
        """Test many edges converging to single node."""
        input_text = """
        A -> END
        B -> END
        C -> END
        D -> END
        E -> END
        """
        result = generator.generate(input_text)

        assert "A" in result
        assert "E" in result
        assert "END" in result

    def test_many_edges_from_single_node(self, generator):
        """Test many edges diverging from single node."""
        input_text = """
        START -> A
        START -> B
        START -> C
        START -> D
        START -> E
        """
        result = generator.generate(input_text)

        assert "START" in result
        assert "A" in result
        assert "E" in result

    def test_self_loop(self, generator):
        """Test node with self-loop."""
        input_text = """
        A -> B
        B -> B
        B -> C
        """
        result = generator.generate(input_text)

        assert "A" in result
        assert "B" in result
        assert "C" in result

    def test_multiple_disconnected_chains(self, generator):
        """Test multiple disconnected chains."""
        input_text = """
        A -> B
        C -> D
        E -> F
        """
        result = generator.generate(input_text)

        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "D" in result
        assert "E" in result
        assert "F" in result
