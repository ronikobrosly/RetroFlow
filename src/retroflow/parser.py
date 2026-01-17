"""
Parser module for flowchart generator.

Handles parsing of input text into graph connections.
"""

from typing import List, Tuple


class ParseError(Exception):
    """Raised when input parsing fails."""

    pass


class Parser:
    """Parses flowchart input text into connections."""

    def __init__(self):
        self.connections = []

    def parse(self, input_text: str) -> List[Tuple[str, str]]:
        """
        Parse input text and return list of (source, target) connections.

        Args:
            input_text: Multi-line string with connections in format "A -> B"

        Returns:
            List of (source, target) tuples

        Raises:
            ParseError: If input format is invalid
        """
        connections = []

        for line_num, line in enumerate(input_text.strip().split("\n"), 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
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
