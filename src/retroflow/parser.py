"""
Parser module for flowchart generator.

Handles parsing of input text into graph connections.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class Group:
    """Represents a group of nodes with a label."""

    name: str
    nodes: List[str]


class ParseError(Exception):
    """Raised when input parsing fails."""

    pass


class Parser:
    """Parses flowchart input text into connections."""

    # Pattern to match group definitions: [GROUP_NAME: node1 node2 node3 ...]
    GROUP_PATTERN = re.compile(r"^\s*\[([^:]+):\s*([^\]]+)\]\s*$")

    def __init__(self):
        self.connections = []
        self.groups: List[Group] = []

    def parse_groups(self, input_text: str) -> List[Group]:
        """
        Parse group definitions from input text.

        Group syntax: [GROUP_NAME: node1 node2 node3 ...]

        Args:
            input_text: Multi-line string that may contain group definitions

        Returns:
            List of Group objects
        """
        groups = []

        for line in input_text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            match = self.GROUP_PATTERN.match(line)
            if match:
                group_name = match.group(1).strip()
                nodes_str = match.group(2).strip()
                # Split by whitespace to get individual node names
                nodes = nodes_str.split()
                if group_name and nodes:
                    groups.append(Group(name=group_name, nodes=nodes))

        return groups

    def parse(self, input_text: str) -> List[Tuple[str, str]]:
        """
        Parse input text and return list of (source, target) connections.

        Also parses and stores group definitions in self.groups.

        Args:
            input_text: Multi-line string with connections in format "A -> B"
                        and optional group definitions "[GROUP: node1 node2 ...]"

        Returns:
            List of (source, target) tuples

        Raises:
            ParseError: If input format is invalid
        """
        connections = []

        # Parse groups first and store them
        self.groups = self.parse_groups(input_text)

        for line_num, line in enumerate(input_text.strip().split("\n"), 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Skip group definition lines
            if self.GROUP_PATTERN.match(line):
                continue

            # Check for arrow
            if "->" not in line:
                raise ParseError(
                    f"Line {line_num}: Expected '->' in connection: {line}"
                )

            # Split on arrow
            parts = line.split("->")
            if len(parts) != 2:
                raise ParseError(f"Line {line_num}: Invalid connection format: {line}")

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

        return connections

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
