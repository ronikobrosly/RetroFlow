"""Unit tests for the parser module."""

import pytest

from retroflow.parser import Group, ParseError, parse_flowchart


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


class TestGroup:
    """Tests for Group dataclass."""

    def test_group_creation(self):
        """Test Group dataclass creation."""
        group = Group(name="MyGroup", nodes=["A", "B", "C"])
        assert group.name == "MyGroup"
        assert group.nodes == ["A", "B", "C"]

    def test_group_empty_nodes(self):
        """Test Group with empty nodes list."""
        group = Group(name="Empty", nodes=[])
        assert group.name == "Empty"
        assert group.nodes == []


class TestParserGroups:
    """Tests for group parsing functionality."""

    def test_parse_groups_simple(self, parser):
        """Test parsing a simple group definition."""
        input_text = "[MyGroup: A B C]"
        groups = parser.parse_groups(input_text)
        assert len(groups) == 1
        assert groups[0].name == "MyGroup"
        assert groups[0].nodes == ["A", "B", "C"]

    def test_parse_groups_multiple(self, parser):
        """Test parsing multiple group definitions."""
        input_text = """
        [Group1: A B]
        [Group2: C D E]
        """
        groups = parser.parse_groups(input_text)
        assert len(groups) == 2
        assert groups[0].name == "Group1"
        assert groups[0].nodes == ["A", "B"]
        assert groups[1].name == "Group2"
        assert groups[1].nodes == ["C", "D", "E"]

    def test_parse_groups_with_spaces_in_name(self, parser):
        """Test parsing group with spaces in name."""
        input_text = "[My Group Name: A B]"
        groups = parser.parse_groups(input_text)
        assert len(groups) == 1
        assert groups[0].name == "My Group Name"
        assert groups[0].nodes == ["A", "B"]

    def test_parse_groups_mixed_with_connections(self, parser):
        """Test parsing groups mixed with connection lines."""
        input_text = """
        A -> B
        [MyGroup: A B]
        B -> C
        """
        groups = parser.parse_groups(input_text)
        assert len(groups) == 1
        assert groups[0].name == "MyGroup"

    def test_parse_groups_empty_input(self, parser):
        """Test parsing empty input returns empty list."""
        groups = parser.parse_groups("")
        assert groups == []

    def test_parse_groups_no_groups(self, parser):
        """Test parsing input with no groups returns empty list."""
        input_text = """
        A -> B
        B -> C
        """
        groups = parser.parse_groups(input_text)
        assert groups == []

    def test_parse_stores_groups(self, parser):
        """Test that parse() stores groups in parser.groups."""
        input_text = """
        [MyGroup: A B]
        A -> B
        B -> C
        """
        parser.parse(input_text)
        assert len(parser.groups) == 1
        assert parser.groups[0].name == "MyGroup"
        assert parser.groups[0].nodes == ["A", "B"]

    def test_parse_skips_group_lines_for_connections(self, parser):
        """Test that parse() skips group lines when parsing connections."""
        input_text = """
        [MyGroup: A B]
        A -> B
        B -> C
        """
        connections = parser.parse(input_text)
        assert connections == [("A", "B"), ("B", "C")]

    def test_parse_groups_single_node(self, parser):
        """Test parsing group with single node."""
        input_text = "[SingleNode: X]"
        groups = parser.parse_groups(input_text)
        assert len(groups) == 1
        assert groups[0].nodes == ["X"]

    def test_parse_groups_ignores_empty_group_name(self, parser):
        """Test that groups with empty names are ignored."""
        input_text = "[: A B]"
        groups = parser.parse_groups(input_text)
        assert groups == []

    def test_parse_groups_ignores_empty_nodes(self, parser):
        """Test that groups with no nodes are ignored."""
        input_text = "[EmptyGroup:]"
        groups = parser.parse_groups(input_text)
        assert groups == []
