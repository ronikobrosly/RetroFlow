"""Unit tests for the parser module."""

import pytest

from retroflow import ParseError, Parser, parse_flowchart


class TestParser:
    """Tests for the Parser class."""

    def test_parse_simple_connection(self):
        """Parse a single connection."""
        parser = Parser()
        result = parser.parse("A -> B")
        assert result == [("A", "B")]

    def test_parse_multiple_connections(self):
        """Parse multiple connections."""
        parser = Parser()
        input_text = """
        A -> B
        B -> C
        C -> D
        """
        result = parser.parse(input_text)
        assert result == [("A", "B"), ("B", "C"), ("C", "D")]

    def test_parse_with_whitespace(self):
        """Parse handles various whitespace."""
        parser = Parser()
        input_text = "  A   ->   B  "
        result = parser.parse(input_text)
        assert result == [("A", "B")]

    def test_parse_skips_empty_lines(self):
        """Parser skips empty lines."""
        parser = Parser()
        input_text = """
        A -> B

        B -> C
        """
        result = parser.parse(input_text)
        assert result == [("A", "B"), ("B", "C")]

    def test_parse_skips_comments(self):
        """Parser skips comment lines."""
        parser = Parser()
        input_text = """
        # This is a comment
        A -> B
        # Another comment
        B -> C
        """
        result = parser.parse(input_text)
        assert result == [("A", "B"), ("B", "C")]

    def test_parse_multiword_nodes(self):
        """Parse nodes with multiple words."""
        parser = Parser()
        result = parser.parse("Start Process -> End Process")
        assert result == [("Start Process", "End Process")]

    def test_parse_error_missing_arrow(self):
        """Raise ParseError when arrow is missing."""
        parser = Parser()
        with pytest.raises(ParseError) as exc_info:
            parser.parse("A B")
        assert "Expected '->'" in str(exc_info.value)

    def test_parse_error_empty_source(self):
        """Raise ParseError for empty source node."""
        parser = Parser()
        with pytest.raises(ParseError) as exc_info:
            parser.parse("-> B")
        assert "Empty source" in str(exc_info.value)

    def test_parse_error_empty_target(self):
        """Raise ParseError for empty target node."""
        parser = Parser()
        with pytest.raises(ParseError) as exc_info:
            parser.parse("A ->")
        assert "Empty target" in str(exc_info.value)

    def test_parse_error_no_connections(self):
        """Raise ParseError when no connections found."""
        parser = Parser()
        with pytest.raises(ParseError) as exc_info:
            parser.parse("# Only comments")
        assert "No valid connections" in str(exc_info.value)

    def test_parse_error_empty_input(self):
        """Raise ParseError for empty input."""
        parser = Parser()
        with pytest.raises(ParseError):
            parser.parse("")

    def test_get_all_nodes(self):
        """Extract all unique nodes from connections."""
        parser = Parser()
        connections = [("A", "B"), ("B", "C"), ("A", "C")]
        nodes = parser.get_all_nodes(connections)
        assert sorted(nodes) == ["A", "B", "C"]


class TestParseFlowchartFunction:
    """Tests for the parse_flowchart convenience function."""

    def test_parse_flowchart_simple(self):
        """Convenience function parses correctly."""
        result = parse_flowchart("A -> B\nB -> C")
        assert result == [("A", "B"), ("B", "C")]

    def test_parse_flowchart_raises_error(self):
        """Convenience function propagates errors."""
        with pytest.raises(ParseError):
            parse_flowchart("invalid input")
