"""
Layout module for flowchart generator.

Implements sophisticated layout algorithms for positioning nodes.
"""

import math
from collections import deque
from typing import Dict, List, Tuple


class LayoutAlgorithm:
    """
    Implements a layered graph layout algorithm (Sugiyama-style).

    The algorithm works in phases:
    1. Layer assignment - assign nodes to vertical layers
    2. Crossing minimization - order nodes within layers
    3. Horizontal positioning - position nodes to minimize width
    """

    def __init__(self, graph, horizontal_spacing=4, vertical_spacing=3):
        self.graph = graph
        self.horizontal_spacing = horizontal_spacing
        self.vertical_spacing = vertical_spacing
        self.layers = []  # List of lists of nodes
        self.positions = {}  # node -> (x, y) in layer coordinates
        self.feedback_edges = []

    def compute_layout(self) -> Dict[str, Tuple[int, int]]:
        """
        Compute layout positions for all nodes.

        Returns:
            Dictionary mapping node names to (layer, position_in_layer) tuples
        """
        # Phase 1: Handle cycles by finding feedback edges
        self._handle_cycles()

        # Phase 2: Assign nodes to layers
        self._assign_layers()

        # Phase 3: Minimize crossings
        self._minimize_crossings()

        # Phase 4: Optimize for square layout
        self._optimize_for_square_layout()

        # Phase 5: Assign final positions
        self._assign_positions()

        return self.positions

    def _handle_cycles(self):
        """Identify feedback edges to break cycles."""
        self.feedback_edges = self.graph.find_feedback_edges()

    def _is_feedback_edge(self, source: str, target: str) -> bool:
        """Check if an edge is a feedback edge."""
        return (source, target) in self.feedback_edges

    def _assign_layers(self):
        """
        Assign nodes to layers using longest path layering.
        This minimizes edge span.
        """
        # Calculate layer for each node (longest path from roots)
        node_layers = {}

        # Start with roots
        roots = self.graph.get_roots()
        if not roots:
            # If no roots (cycle), pick nodes with minimum in-degree
            in_degrees = {
                node: len(
                    [
                        s
                        for s in self.graph.get_predecessors(node)
                        if not self._is_feedback_edge(s, node)
                    ]
                )
                for node in self.graph.nodes
            }
            roots = [
                node
                for node, deg in in_degrees.items()
                if deg == min(in_degrees.values())
            ]

        # BFS to assign layers
        queue = deque([(node, 0) for node in roots])
        visited = set()

        while queue:
            node, layer = queue.popleft()

            if node in visited:
                # Update layer if we found a longer path
                node_layers[node] = max(node_layers.get(node, 0), layer)
                continue

            visited.add(node)
            node_layers[node] = layer

            # Add successors (ignoring feedback edges)
            for successor in self.graph.get_successors(node):
                if not self._is_feedback_edge(node, successor):
                    queue.append((successor, layer + 1))

        # Handle any unvisited nodes (shouldn't happen but be safe)
        for node in self.graph.nodes:
            if node not in node_layers:
                node_layers[node] = 0

        # Group nodes by layer
        max_layer = max(node_layers.values()) if node_layers else 0
        self.layers = [[] for _ in range(max_layer + 1)]

        for node, layer in node_layers.items():
            self.layers[layer].append(node)

    def _minimize_crossings(self):
        """
        Minimize edge crossings using barycenter heuristic.
        Iteratively reorder nodes within layers.
        """
        if len(self.layers) <= 1:
            return

        # Perform multiple passes
        for iteration in range(3):
            # Forward pass (top to bottom)
            for i in range(1, len(self.layers)):
                self._reorder_layer(i, self.layers[i - 1])

            # Backward pass (bottom to top)
            for i in range(len(self.layers) - 2, -1, -1):
                self._reorder_layer(i, self.layers[i + 1])

    def _reorder_layer(self, layer_idx: int, reference_layer: List[str]):
        """Reorder nodes in a layer based on barycenter of connected nodes."""
        layer = self.layers[layer_idx]

        # Calculate barycenter for each node
        barycenters = []
        for node in layer:
            positions = []

            # Get positions of connected nodes in reference layer
            for ref_node in reference_layer:
                ref_pos = reference_layer.index(ref_node)

                # Check if connected (either direction, skip feedback edges)
                if node in self.graph.get_successors(ref_node):
                    if not self._is_feedback_edge(ref_node, node):
                        positions.append(ref_pos)
                if node in self.graph.get_predecessors(ref_node):
                    if not self._is_feedback_edge(node, ref_node):
                        positions.append(ref_pos)

            # Calculate barycenter
            if positions:
                barycenter = sum(positions) / len(positions)
            else:
                barycenter = len(reference_layer) / 2  # Center if no connections

            barycenters.append((barycenter, node))

        # Sort by barycenter
        barycenters.sort()
        self.layers[layer_idx] = [node for _, node in barycenters]

    def _optimize_for_square_layout(self):
        """
        Optimize layer distribution to create a more square-like layout.
        Tries to balance height vs width.
        """
        total_nodes = len(self.graph.nodes)
        if total_nodes == 0:
            return

        # Calculate ideal aspect ratio (closer to 1 = more square)
        ideal_layers = math.ceil(math.sqrt(total_nodes))
        current_layers = len(self.layers)

        # If we have too many layers, try to redistribute
        if current_layers > ideal_layers * 1.5:
            self._redistribute_layers(ideal_layers)

    def _redistribute_layers(self, target_layer_count: int):
        """
        Redistribute nodes across fewer layers to create wider layout.
        This is a heuristic approach.
        """
        if len(self.layers) <= target_layer_count:
            return

        # Calculate compression ratio
        compression = len(self.layers) / target_layer_count

        # Create new layer assignment
        new_layers = [[] for _ in range(target_layer_count)]

        for old_layer_idx, layer in enumerate(self.layers):
            new_layer_idx = min(
                int(old_layer_idx / compression), target_layer_count - 1
            )
            new_layers[new_layer_idx].extend(layer)

        # Only apply if it doesn't create too-wide layers
        max_width = max(len(layer) for layer in new_layers)
        if max_width <= target_layer_count * 1.5:
            self.layers = new_layers

    def _assign_positions(self):
        """Assign final (x, y) positions to nodes."""
        self.positions = {}

        for layer_idx, layer in enumerate(self.layers):
            for pos_idx, node in enumerate(layer):
                # y position based on layer
                y = layer_idx
                # x position based on position in layer
                x = pos_idx
                self.positions[node] = (x, y)

    def get_layout_dimensions(self) -> Tuple[int, int]:
        """
        Get the dimensions of the layout in layer coordinates.

        Returns:
            (width, height) tuple
        """
        if not self.layers:
            return (0, 0)

        width = max(len(layer) for layer in self.layers)
        height = len(self.layers)

        return (width, height)

    def get_edges_for_rendering(self) -> List[Tuple[str, str, bool]]:
        """
        Get edges with information about whether they're reversed.

        Returns:
            List of (source, target, is_feedback) tuples
        """
        edges = []
        for source, target in self.graph.edges:
            is_feedback = self._is_feedback_edge(source, target)
            edges.append((source, target, is_feedback))
        return edges


class SimpleLayout:
    """Simpler vertical layout for small graphs."""

    def __init__(self, graph):
        self.graph = graph
        self.positions = {}

    def compute_layout(self) -> Dict[str, Tuple[int, int]]:
        """Compute simple vertical layout."""
        nodes = self.graph.topological_sort()

        for idx, node in enumerate(nodes):
            self.positions[node] = (0, idx)

        return self.positions

    def get_layout_dimensions(self) -> Tuple[int, int]:
        """Get layout dimensions."""
        if not self.positions:
            return (0, 0)
        return (1, len(self.positions))

    def get_edges_for_rendering(self) -> List[Tuple[str, str, bool]]:
        """Get edges for rendering."""
        return [(s, t, False) for s, t in self.graph.edges]


def compute_layout(graph, algorithm="layered", **kwargs) -> LayoutAlgorithm:
    """
    Compute layout for a graph.

    Args:
        graph: Graph object
        algorithm: 'layered' or 'simple'
        **kwargs: Additional parameters for layout algorithm

    Returns:
        Layout object with computed positions
    """
    if algorithm == "simple" or len(graph.nodes) <= 3:
        layout = SimpleLayout(graph)
        layout.compute_layout()
        return layout
    else:
        layout = LayoutAlgorithm(graph, **kwargs)
        layout.compute_layout()
        return layout
