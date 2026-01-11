"""
Layout module using networkx for hierarchical graph layout.

Uses networkx for:
- Graph representation
- Cycle detection
- Topological sorting / layer assignment
- Node ordering within layers
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

import networkx as nx

if TYPE_CHECKING:
    from .parser import Group


@dataclass
class NodeLayout:
    """Represents a node's layout information."""

    name: str
    layer: int = 0
    position: int = 0  # Position within layer
    x: int = 0  # Character x coordinate
    y: int = 0  # Character y coordinate
    width: int = 0
    height: int = 0


@dataclass
class LayoutResult:
    """Result of the layout algorithm."""

    nodes: Dict[str, NodeLayout] = field(default_factory=dict)
    layers: List[List[str]] = field(default_factory=list)
    edges: List[Tuple[str, str]] = field(default_factory=list)
    back_edges: Set[Tuple[str, str]] = field(default_factory=set)
    has_cycles: bool = False
    groups: List["Group"] = field(default_factory=list)


class NetworkXLayout:
    """
    Graph layout using networkx.

    For DAGs: uses topological_generations for layer assignment
    For cyclic graphs: identifies back edges, breaks cycles, then layouts
    """

    def __init__(self):
        self.graph: nx.DiGraph = None
        self.back_edges: Set[Tuple[str, str]] = set()

    def layout(
        self,
        connections: List[Tuple[str, str]],
        groups: List["Group"] = None,
    ) -> LayoutResult:
        """
        Compute layout for the given connections.

        Args:
            connections: List of (source, target) tuples
            groups: Optional list of Group objects for grouping nodes

        Returns:
            LayoutResult with node positions and layer assignments
        """
        if groups is None:
            groups = []
        # Build networkx graph
        self.graph = nx.DiGraph()
        self.graph.add_edges_from(connections)

        # Check for cycles
        has_cycles = not nx.is_directed_acyclic_graph(self.graph)
        self.back_edges = set()

        if has_cycles:
            # Find and remove back edges to create a DAG
            self._break_cycles()

        # Assign layers using topological generations
        layers = self._assign_layers()

        # Order nodes within each layer to minimize crossings
        layers = self._order_layers(layers)

        # Build result
        result = LayoutResult()
        result.has_cycles = has_cycles
        result.back_edges = self.back_edges
        result.layers = layers
        result.edges = list(connections)
        result.groups = groups

        # Create node layouts
        for layer_idx, layer in enumerate(layers):
            for pos_idx, node_name in enumerate(layer):
                result.nodes[node_name] = NodeLayout(
                    name=node_name, layer=layer_idx, position=pos_idx
                )

        return result

    def _break_cycles(self) -> None:
        """
        Identify back edges and create a DAG by conceptually removing them.
        Uses DFS to find back edges.
        """
        # Find all cycles
        try:
            cycles = list(nx.simple_cycles(self.graph))
        except Exception:
            cycles = []

        if not cycles:
            return

        # For each cycle, we need to identify one edge to "break"
        # We'll use a DFS-based approach to find back edges
        visited = set()
        rec_stack = set()

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)

            for successor in list(self.graph.successors(node)):
                if successor not in visited:
                    dfs(successor)
                elif successor in rec_stack:
                    # This is a back edge
                    self.back_edges.add((node, successor))

            rec_stack.remove(node)

        # Start DFS from nodes with no predecessors, or any node if all have them
        roots = [n for n in self.graph.nodes() if self.graph.in_degree(n) == 0]
        if not roots:
            roots = [list(self.graph.nodes())[0]]

        for root in roots:
            if root not in visited:
                dfs(root)

        # Visit any remaining unvisited nodes
        for node in self.graph.nodes():
            if node not in visited:
                dfs(node)

    def _assign_layers(self) -> List[List[str]]:
        """
        Assign nodes to layers using longest path method.
        """
        # Create a working graph without back edges
        working_graph = self.graph.copy()
        working_graph.remove_edges_from(self.back_edges)

        # Use longest path for layer assignment
        # This places nodes as far down as possible
        node_layer: Dict[str, int] = {}

        # Process in topological order
        try:
            topo_order = list(nx.topological_sort(working_graph))
        except nx.NetworkXUnfeasible:
            # Still has cycles somehow, fall back to simple ordering
            topo_order = list(working_graph.nodes())

        for node in topo_order:
            predecessors = list(working_graph.predecessors(node))
            if not predecessors:
                node_layer[node] = 0
            else:
                node_layer[node] = max(node_layer.get(p, 0) for p in predecessors) + 1

        # Group by layer
        if not node_layer:
            return []

        max_layer = max(node_layer.values())
        layers: List[List[str]] = [[] for _ in range(max_layer + 1)]

        for node, layer in node_layer.items():
            layers[layer].append(node)

        return layers

    def _order_layers(self, layers: List[List[str]]) -> List[List[str]]:
        """
        Order nodes within each layer to minimize edge crossings.
        Uses barycenter heuristic.
        """
        if len(layers) <= 1:
            return layers

        # Create working graph without back edges for ordering
        working_graph = self.graph.copy()
        working_graph.remove_edges_from(self.back_edges)

        # Multiple passes of barycenter ordering
        for _ in range(4):
            # Forward pass
            for i in range(1, len(layers)):
                layers[i] = self._order_layer_by_barycenter(
                    layers[i], layers[i - 1], working_graph, use_predecessors=True
                )

            # Backward pass
            for i in range(len(layers) - 2, -1, -1):
                layers[i] = self._order_layer_by_barycenter(
                    layers[i], layers[i + 1], working_graph, use_predecessors=False
                )

        return layers

    def _order_layer_by_barycenter(
        self,
        layer: List[str],
        ref_layer: List[str],
        graph: nx.DiGraph,
        use_predecessors: bool,
    ) -> List[str]:
        """
        Order nodes by barycenter (average position of connected nodes).
        """
        ref_positions = {node: i for i, node in enumerate(ref_layer)}

        def barycenter(node: str) -> float:
            if use_predecessors:
                neighbors = list(graph.predecessors(node))
            else:
                neighbors = list(graph.successors(node))

            positions = [ref_positions[n] for n in neighbors if n in ref_positions]

            if not positions:
                # Keep original order for nodes with no connections to ref layer
                return layer.index(node) if node in layer else 0

            return sum(positions) / len(positions)

        return sorted(layer, key=barycenter)


# Backward compatibility alias
SugiyamaLayout = NetworkXLayout
