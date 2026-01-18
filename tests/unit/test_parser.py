"""Unit tests for the parser module."""

import pytest

from retroflow.models import GroupDefinition
from retroflow.parser import ParseError, ParseResult, parse_flowchart


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


class TestParseResult:
    """Tests for ParseResult dataclass."""

    def test_parse_result_default(self):
        """Test ParseResult with default values."""
        result = ParseResult()
        assert result.connections == []
        assert result.groups == []

    def test_parse_result_with_values(self):
        """Test ParseResult with provided values."""
        connections = [("A", "B"), ("B", "C")]
        groups = [GroupDefinition(name="Test", members=["A", "B"], order=0)]
        result = ParseResult(connections=connections, groups=groups)
        assert result.connections == connections
        assert result.groups == groups


class TestGroupParsing:
    """Tests for group definition parsing."""

    def test_parse_with_groups_simple(self, parser):
        """Test parsing a simple group definition."""
        input_text = """
        [My Group: A B]
        A -> B
        B -> C
        """
        result = parser.parse_with_groups(input_text)
        assert len(result.groups) == 1
        assert result.groups[0].name == "My Group"
        assert result.groups[0].members == ["A", "B"]
        assert result.groups[0].order == 0

    def test_parse_with_groups_multiple(self, parser):
        """Test parsing multiple group definitions."""
        input_text = """
        [Group One: A B]
        [Group Two: C D]
        A -> B
        B -> C
        C -> D
        """
        result = parser.parse_with_groups(input_text)
        assert len(result.groups) == 2
        assert result.groups[0].name == "Group One"
        assert result.groups[0].members == ["A", "B"]
        assert result.groups[0].order == 0
        assert result.groups[1].name == "Group Two"
        assert result.groups[1].members == ["C", "D"]
        assert result.groups[1].order == 1

    def test_parse_with_groups_multiword_nodes(self, parser):
        """Test parsing groups with multi-word node names."""
        input_text = """
        [API Layer: User Service Auth Service]
        User Service -> Auth Service
        Auth Service -> Database
        """
        result = parser.parse_with_groups(input_text)
        assert len(result.groups) == 1
        assert result.groups[0].members == ["User Service", "Auth Service"]

    def test_parse_with_groups_no_groups(self, parser):
        """Test parsing input with no groups returns empty groups list."""
        input_text = """
        A -> B
        B -> C
        """
        result = parser.parse_with_groups(input_text)
        assert len(result.groups) == 0
        assert result.connections == [("A", "B"), ("B", "C")]

    def test_parse_with_groups_preserves_connections(self, parser):
        """Test that connections are preserved when groups are present."""
        input_text = """
        [Test: A B]
        A -> B
        B -> C
        C -> A
        """
        result = parser.parse_with_groups(input_text)
        assert result.connections == [("A", "B"), ("B", "C"), ("C", "A")]

    def test_parse_with_groups_error_after_edges(self, parser):
        """Test error when group definition appears after edge definitions."""
        input_text = """
        A -> B
        [My Group: A B]
        B -> C
        """
        with pytest.raises(ParseError) as exc_info:
            parser.parse_with_groups(input_text)
        assert "Group definitions must appear before edge definitions" in str(
            exc_info.value
        )

    def test_parse_with_groups_error_duplicate_membership(self, parser):
        """Test error when a node belongs to multiple groups."""
        input_text = """
        [Group One: A B]
        [Group Two: B C]
        A -> B
        B -> C
        """
        with pytest.raises(ParseError) as exc_info:
            parser.parse_with_groups(input_text)
        assert "already belongs to group" in str(exc_info.value)

    def test_parse_with_groups_error_no_valid_members(self, parser):
        """Test error when group has no valid node names."""
        input_text = """
        [My Group: X Y Z]
        A -> B
        B -> C
        """
        with pytest.raises(ParseError) as exc_info:
            parser.parse_with_groups(input_text)
        assert "No valid node names found" in str(exc_info.value)

    def test_parse_with_groups_error_empty_group_name(self, parser):
        """Test error when group has empty name."""
        input_text = """
        [  : A B]
        A -> B
        """
        with pytest.raises(ParseError) as exc_info:
            parser.parse_with_groups(input_text)
        assert "Empty group name" in str(exc_info.value)

    def test_parse_with_groups_error_empty_member_list(self, parser):
        """Test error when group has empty member list."""
        input_text = """
        [My Group:   ]
        A -> B
        """
        # The regex won't match this case, so it will be treated as an edge
        # and fail with "Expected '->'"
        with pytest.raises(ParseError):
            parser.parse_with_groups(input_text)

    def test_parse_with_groups_skips_unknown_words(self, parser):
        """Test that unknown words in member list are skipped."""
        input_text = """
        [My Group: A unknown B another]
        A -> B
        B -> C
        """
        result = parser.parse_with_groups(input_text)
        assert result.groups[0].members == ["A", "B"]

    def test_parse_with_groups_greedy_matching(self, parser):
        """Test greedy longest-first matching for multi-word names."""
        input_text = """
        [My Group: Node One Node One Two]
        Node One -> Node One Two
        Node One Two -> End
        """
        result = parser.parse_with_groups(input_text)
        # Should match "Node One Two" first (longest), then "Node One"
        assert "Node One Two" in result.groups[0].members
        assert "Node One" in result.groups[0].members

    def test_parse_with_groups_avoids_duplicates(self, parser):
        """Test that duplicate node names in same group are avoided."""
        input_text = """
        [My Group: A A B B]
        A -> B
        B -> C
        """
        result = parser.parse_with_groups(input_text)
        # A and B should appear only once each
        assert result.groups[0].members.count("A") == 1
        assert result.groups[0].members.count("B") == 1

    def test_parse_with_groups_with_comments(self, parser):
        """Test parsing groups with comments."""
        input_text = """
        # This is a comment
        [My Group: A B]
        # Another comment
        A -> B
        B -> C
        """
        result = parser.parse_with_groups(input_text)
        assert len(result.groups) == 1
        assert result.groups[0].name == "My Group"


class TestMatchNodeNames:
    """Tests for the _match_node_names helper method."""

    def test_match_simple_nodes(self, parser):
        """Test matching simple single-word nodes."""
        known_nodes = {"A", "B", "C"}
        result = parser._match_node_names("A B C", known_nodes)
        assert result == ["A", "B", "C"]

    def test_match_multiword_nodes(self, parser):
        """Test matching multi-word node names."""
        known_nodes = {"Node One", "Node Two", "Simple"}
        result = parser._match_node_names("Node One Node Two Simple", known_nodes)
        assert "Node One" in result
        assert "Node Two" in result
        assert "Simple" in result

    def test_match_greedy_longest_first(self, parser):
        """Test that longer names are matched first."""
        known_nodes = {"A", "A B", "A B C"}
        result = parser._match_node_names("A B C", known_nodes)
        # Should match "A B C" as one node, not three separate nodes
        assert result == ["A B C"]

    def test_match_skips_unknown(self, parser):
        """Test that unknown words are skipped."""
        known_nodes = {"A", "C"}
        result = parser._match_node_names("A B C", known_nodes)
        assert result == ["A", "C"]

    def test_match_empty_input(self, parser):
        """Test matching with empty input."""
        known_nodes = {"A", "B"}
        result = parser._match_node_names("", known_nodes)
        assert result == []

    def test_match_whitespace_only(self, parser):
        """Test matching with whitespace-only input."""
        known_nodes = {"A", "B"}
        result = parser._match_node_names("   ", known_nodes)
        assert result == []

    def test_match_no_known_nodes(self, parser):
        """Test matching when no nodes are known."""
        known_nodes = set()
        result = parser._match_node_names("A B C", known_nodes)
        assert result == []

    def test_match_partial_word_boundary(self, parser):
        """Test that partial matches are not accepted."""
        known_nodes = {"A", "AB"}
        result = parser._match_node_names("ABC", known_nodes)
        # "ABC" should not match "A" or "AB" since it doesn't end at word boundary
        assert result == []

    def test_match_trailing_word(self, parser):
        """Test matching when last word doesn't match."""
        known_nodes = {"A", "B"}
        result = parser._match_node_names("A B unknown", known_nodes)
        assert result == ["A", "B"]

    def test_match_trailing_spaces(self, parser):
        """Test matching with trailing spaces (triggers lstrip break)."""
        known_nodes = {"A", "B"}
        result = parser._match_node_names("A B   ", known_nodes)
        assert result == ["A", "B"]

    def test_match_only_spaces(self, parser):
        """Test matching string of only spaces."""
        known_nodes = {"A", "B"}
        result = parser._match_node_names("     ", known_nodes)
        assert result == []
