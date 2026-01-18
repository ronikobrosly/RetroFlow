"""
Parser module for flowchart generator.

Handles parsing of input text into graph connections and group definitions.
"""

import re
from dataclasses import dataclass, field
from typing import List, Set, Tuple

from .models import GroupDefinition


class ParseError(Exception):
    """Raised when input parsing fails."""

    pass


@dataclass
class ParseResult:
    """Result of parsing input text."""

    connections: List[Tuple[str, str]] = field(default_factory=list)
    groups: List[GroupDefinition] = field(default_factory=list)


class Parser:
    """Parses flowchart input text into connections and groups."""

    # Regex for group definition: [GROUP NAME: node1 node2 node3]
    GROUP_PATTERN = re.compile(r"^\s*\[([^:]+):\s*(.+)\]\s*$")

    def __init__(self):
        self.connections = []

    def parse(self, input_text: str) -> List[Tuple[str, str]]:
        """
        Parse input text and return list of (source, target) connections.

        This method is maintained for backwards compatibility.
        For full parsing including groups, use parse_with_groups().

        Args:
            input_text: Multi-line string with connections in format "A -> B"

        Returns:
            List of (source, target) tuples

        Raises:
            ParseError: If input format is invalid
        """
        result = self.parse_with_groups(input_text)
        return result.connections

    def parse_with_groups(self, input_text: str) -> ParseResult:
        """
        Parse input text and return connections and group definitions.

        Uses two-pass parsing:
        1. First pass: Parse all edges to discover valid node names
        2. Second pass: Parse group definitions, matching against known nodes

        Args:
            input_text: Multi-line string with optional group definitions
                        followed by connections in format "A -> B"

        Returns:
            ParseResult with connections and groups

        Raises:
            ParseError: If input format is invalid
        """
        lines = input_text.strip().split("\n")
        connections: List[Tuple[str, str]] = []
        group_lines: List[Tuple[int, str]] = []  # (line_num, line)
        edge_started = False

        # First pass: separate group lines from edge lines and parse edges
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                continue

            # Check if this is a group definition
            if self.GROUP_PATTERN.match(stripped):
                if edge_started:
                    raise ParseError(
                        f"Line {line_num}: Group definitions must appear before "
                        f"edge definitions: {stripped}"
                    )
                group_lines.append((line_num, stripped))
                continue

            # This is an edge definition
            edge_started = True

            # Check for arrow
            if "->" not in stripped:
                raise ParseError(
                    f"Line {line_num}: Expected '->' in connection: {stripped}"
                )

            # Split on arrow
            parts = stripped.split("->")
            if len(parts) != 2:
                raise ParseError(
                    f"Line {line_num}: Invalid connection format: {stripped}"
                )

            source = parts[0].strip()
            target = parts[1].strip()

            # Validate node names
            if not source:
                raise ParseError(f"Line {line_num}: Empty source node")
            if not target:
                raise ParseError(f"Line {line_num}: Empty target node")

            connections.append((source, target))

        if not connections:
            raise ParseError("No valid connections found in input")

        # Collect all known node names from edges
        all_nodes = self.get_all_nodes(connections)
        all_nodes_set = set(all_nodes)

        # Second pass: parse group definitions
        groups = self._parse_groups(group_lines, all_nodes_set)

        return ParseResult(connections=connections, groups=groups)

    def _parse_groups(
        self, group_lines: List[Tuple[int, str]], known_nodes: Set[str]
    ) -> List[GroupDefinition]:
        """
        Parse group definitions, matching member names against known nodes.

        Args:
            group_lines: List of (line_num, line) tuples for group definitions.
            known_nodes: Set of valid node names from edges.

        Returns:
            List of GroupDefinition objects.

        Raises:
            ParseError: If group syntax is invalid or node appears in multiple groups.
        """
        groups: List[GroupDefinition] = []
        node_to_group: dict = {}  # Track which group each node belongs to

        for order, (line_num, line) in enumerate(group_lines):
            match = self.GROUP_PATTERN.match(line)
            if not match:
                raise ParseError(
                    f"Line {line_num}: Invalid group definition format: {line}"
                )

            group_name = match.group(1).strip()
            member_text = match.group(2).strip()

            if not group_name:
                raise ParseError(f"Line {line_num}: Empty group name")
            if not member_text:
                raise ParseError(f"Line {line_num}: Empty member list for group")

            # Match member names against known nodes using greedy longest-match
            members = self._match_node_names(member_text, known_nodes)

            if not members:
                raise ParseError(
                    f"Line {line_num}: No valid node names found in group members: "
                    f"'{member_text}'"
                )

            # Check for duplicate membership
            for member in members:
                if member in node_to_group:
                    raise ParseError(
                        f"Line {line_num}: Node '{member}' already belongs to group "
                        f"'{node_to_group[member]}'"
                    )
                node_to_group[member] = group_name

            groups.append(
                GroupDefinition(name=group_name, members=members, order=order)
            )

        return groups

    def _match_node_names(
        self, member_text: str, known_nodes: Set[str]
    ) -> List[str]:
        """
        Match member text against known node names using greedy longest-first.

        This handles multi-word node names by trying to match the longest
        possible node name at each position.

        Args:
            member_text: Space-separated text from group definition.
            known_nodes: Set of valid node names.

        Returns:
            List of matched node names in order of appearance.
        """
        members: List[str] = []
        remaining = member_text.strip()

        # Sort known nodes by length (descending) for greedy matching
        sorted_nodes = sorted(known_nodes, key=len, reverse=True)

        while remaining:
            remaining = remaining.lstrip()
            if not remaining:
                break

            matched = False
            for node in sorted_nodes:
                if remaining.startswith(node):
                    # Check that the match ends at a word boundary
                    end_idx = len(node)
                    if end_idx == len(remaining) or remaining[end_idx] == " ":
                        if node not in members:  # Avoid duplicates within same group
                            members.append(node)
                        remaining = remaining[end_idx:].lstrip()
                        matched = True
                        break

            if not matched:
                # Skip the current word if no match found
                space_idx = remaining.find(" ")
                if space_idx == -1:
                    break
                remaining = remaining[space_idx:].lstrip()

        return members

    def get_all_nodes(self, connections: List[Tuple[str, str]]) -> List[str]:
        """
        Extract all unique nodes from connections.

        Args:
            connections: List of (source, target) tuples

        Returns:
            Sorted list of unique node names
        """
        nodes = set()
        for source, target in connections:
            nodes.add(source)
            nodes.add(target)
        return sorted(nodes)


def parse_flowchart(input_text: str) -> List[Tuple[str, str]]:
    """
    Convenience function to parse flowchart input.

    Args:
        input_text: Multi-line string with connections

    Returns:
        List of (source, target) tuples
    """
    parser = Parser()
    return parser.parse(input_text)
