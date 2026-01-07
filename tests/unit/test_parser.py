"""Unit tests for the parser module."""

import pytest

from retroflow.parser import ParseError, parse_flowchart


class TestParser:
    """Tests for Parser class."""

    def test_parse_simple_connection(self, parser):
        """Test parsing a single connection."""
        result = parser.parse("A -> B")
        assert result == [("A", "B")]

    def test_parse_multiple_connections(self, parser):
        """Test parsing multiple connections."""
        input_text = """
        A -> B
        B -> C
        C -> D
        """
        result = parser.parse(input_text)
        assert result == [("A", "B"), ("B", "C"), ("C", "D")]

    def test_parse_with_spaces_in_names(self, parser):
        """Test parsing node names with spaces."""
        input_text = """
        Start Node -> End Node
        Process One -> Process Two
        """
        result = parser.parse(input_text)
        assert result == [
            ("Start Node", "End Node"),
            ("Process One", "Process Two"),
        ]

    def test_parse_skips_empty_lines(self, parser):
        """Test that empty lines are skipped."""
        input_text = """
        A -> B

        B -> C

        """
        result = parser.parse(input_text)
        assert result == [("A", "B"), ("B", "C")]

    def test_parse_skips_comments(self, parser):
        """Test that comment lines are skipped."""
        input_text = """
        # This is a comment
        A -> B
        # Another comment
        B -> C
        """
        result = parser.parse(input_text)
        assert result == [("A", "B"), ("B", "C")]

    def test_parse_error_no_arrow(self, parser):
        """Test that missing arrow raises ParseError."""
        with pytest.raises(ParseError) as exc_info:
            parser.parse("A B")
        assert "Expected '->'" in str(exc_info.value)

    def test_parse_error_empty_source(self, parser):
        """Test that empty source node raises ParseError."""
        with pytest.raises(ParseError) as exc_info:
            parser.parse(" -> B")
        assert "Empty source node" in str(exc_info.value)

    def test_parse_error_empty_target(self, parser):
        """Test that empty target node raises ParseError."""
        with pytest.raises(ParseError) as exc_info:
            parser.parse("A -> ")
        assert "Empty target node" in str(exc_info.value)

    def test_parse_error_multiple_arrows(self, parser):
        """Test that multiple arrows in one line raises ParseError."""
        with pytest.raises(ParseError) as exc_info:
            parser.parse("A -> B -> C")
        assert "Invalid connection format" in str(exc_info.value)

    def test_parse_error_no_connections(self, parser):
        """Test that empty input raises ParseError."""
        with pytest.raises(ParseError) as exc_info:
            parser.parse("")
        assert "No valid connections" in str(exc_info.value)

    def test_parse_error_only_comments(self, parser):
        """Test that only comments raises ParseError."""
        with pytest.raises(ParseError) as exc_info:
            parser.parse("# Just a comment")
        assert "No valid connections" in str(exc_info.value)

    def test_parse_error_only_whitespace(self, parser):
        """Test that only whitespace raises ParseError."""
        with pytest.raises(ParseError) as exc_info:
            parser.parse("   \n   \n   ")
        assert "No valid connections" in str(exc_info.value)

    def test_get_all_nodes(self, parser):
        """Test extracting all unique nodes from connections."""
        connections = [("A", "B"), ("B", "C"), ("A", "C")]
        nodes = parser.get_all_nodes(connections)
        assert sorted(nodes) == ["A", "B", "C"]

    def test_get_all_nodes_empty(self, parser):
        """Test extracting nodes from empty connections."""
        nodes = parser.get_all_nodes([])
        assert nodes == []

    def test_get_all_nodes_single_connection(self, parser):
        """Test extracting nodes from single connection."""
        connections = [("Start", "End")]
        nodes = parser.get_all_nodes(connections)
        assert sorted(nodes) == ["End", "Start"]


class TestParseFlowchartFunction:
    """Tests for parse_flowchart convenience function."""

    def test_parse_flowchart_simple(self):
        """Test the convenience function with simple input."""
        result = parse_flowchart("A -> B\nB -> C")
        assert result == [("A", "B"), ("B", "C")]

    def test_parse_flowchart_with_spaces(self):
        """Test the convenience function with spaces."""
        result = parse_flowchart("  A -> B  \n  B -> C  ")
        assert result == [("A", "B"), ("B", "C")]

    def test_parse_flowchart_error(self):
        """Test the convenience function raises errors."""
        with pytest.raises(ParseError):
            parse_flowchart("invalid input")


class TestParseError:
    """Tests for ParseError exception."""

    def test_parse_error_message(self):
        """Test ParseError can be raised with a message."""
        with pytest.raises(ParseError) as exc_info:
            raise ParseError("Test error message")
        assert str(exc_info.value) == "Test error message"

    def test_parse_error_is_exception(self):
        """Test ParseError is an Exception subclass."""
        assert issubclass(ParseError, Exception)
