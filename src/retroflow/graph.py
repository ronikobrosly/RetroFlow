"""
Graph module for flowchart generator.

Provides graph data structure and analysis algorithms.
"""

from collections import defaultdict, deque
from typing import List, Tuple


class Graph:
    """Directed graph structure for flowchart representation."""

    def __init__(self):
        self.nodes = set()
        self.edges = []  # List of (source, target) tuples
        self.adjacency = defaultdict(list)  # source -> [targets]
        self.reverse_adjacency = defaultdict(list)  # target -> [sources]

    def add_edge(self, source: str, target: str):
        """Add a directed edge from source to target."""
        self.nodes.add(source)
        self.nodes.add(target)
        self.edges.append((source, target))
        self.adjacency[source].append(target)
        self.reverse_adjacency[target].append(source)

    def get_nodes(self) -> List[str]:
        """Return list of all nodes."""
        return list(self.nodes)

    def get_edges(self) -> List[Tuple[str, str]]:
        """Return list of all edges."""
        return self.edges

    def get_successors(self, node: str) -> List[str]:
        """Get all nodes that this node points to."""
        return self.adjacency.get(node, [])

    def get_predecessors(self, node: str) -> List[str]:
        """Get all nodes that point to this node."""
        return self.reverse_adjacency.get(node, [])

    def get_roots(self) -> List[str]:
        """Get nodes with no incoming edges."""
        return [node for node in self.nodes if not self.get_predecessors(node)]

    def get_leaves(self) -> List[str]:
        """Get nodes with no outgoing edges."""
        return [node for node in self.nodes if not self.get_successors(node)]

    def has_cycle(self) -> bool:
        """Check if graph contains a cycle using DFS."""
        visited = set()
        rec_stack = set()

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.get_successors(node):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in self.nodes:
            if node not in visited:
                if dfs(node):
                    return True

        return False

    def find_feedback_edges(self) -> List[Tuple[str, str]]:
        """
        Find edges that need to be reversed to make graph acyclic.
        Uses DFS to find back edges.
        """
        visited = set()
        rec_stack = set()
        feedback_edges = []

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.get_successors(node):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Back edge found
                    feedback_edges.append((node, neighbor))

            rec_stack.remove(node)

        for node in self.nodes:
            if node not in visited:
                dfs(node)

        return feedback_edges

    def topological_sort(self) -> List[str]:
        """
        Return nodes in topological order (if acyclic).
        Uses Kahn's algorithm.
        """
        in_degree = {node: len(self.get_predecessors(node)) for node in self.nodes}
        queue = deque([node for node in self.nodes if in_degree[node] == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            for neighbor in self.get_successors(node):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If not all nodes processed, there's a cycle
        if len(result) != len(self.nodes):
            return sorted(self.nodes)  # Fallback to alphabetical

        return result

    def get_longest_path_length(self) -> int:
        """
        Calculate the length of the longest path in the graph.
        Useful for estimating layout height.
        """
        if not self.nodes:
            return 0

        # Use dynamic programming with topological sort
        topo_order = self.topological_sort()
        distances = {node: 0 for node in self.nodes}

        for node in topo_order:
            for successor in self.get_successors(node):
                distances[successor] = max(distances[successor], distances[node] + 1)

        return max(distances.values()) if distances else 0

    def get_max_width(self) -> int:
        """
        Estimate maximum width by counting nodes at each level.
        Useful for estimating layout width.
        """
        if not self.nodes:
            return 0

        # Assign levels using BFS
        levels = defaultdict(list)
        visited = set()
        queue = deque([(node, 0) for node in self.get_roots()])

        if not queue:  # No roots means cycle, start from any node
            queue.append((next(iter(self.nodes)), 0))

        while queue:
            node, level = queue.popleft()
            if node in visited:
                continue

            visited.add(node)
            levels[level].append(node)

            for successor in self.get_successors(node):
                if successor not in visited:
                    queue.append((successor, level + 1))

        return max(len(nodes) for nodes in levels.values()) if levels else 1


def create_graph(connections: List[Tuple[str, str]]) -> Graph:
    """
    Create a Graph from a list of connections.

    Args:
        connections: List of (source, target) tuples

    Returns:
        Graph object
    """
    graph = Graph()
    for source, target in connections:
        graph.add_edge(source, target)
    return graph
