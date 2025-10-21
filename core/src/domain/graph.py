"""Pure graph operations for flow node dependencies.

This module provides zero-dependency graph algorithms for building
and traversing flow graphs.
"""

from collections import defaultdict
from typing import Any

from src.domain.types import FlowGraph
from src.models import Node
from src.utils.sort import layered_topological_sort


def build_flow_graph(nodes: list[Node]) -> FlowGraph:
    """Build a directed acyclic graph from node definitions.

    Creates an adjacency list representation where each node points to
    its dependents (nodes that depend on it).

    Args:
        nodes: List of Node objects with dep_ids

    Returns:
        FlowGraph with adjacency list and node lookup map

    Example:
        >>> nodes = [
        ...     Node(id="a", dep_ids=[]),
        ...     Node(id="b", dep_ids=["a"]),
        ...     Node(id="c", dep_ids=["a", "b"]),
        ... ]
        >>> graph = build_flow_graph(nodes)
        >>> graph["graph"]
        {"a": ["b", "c"], "b": ["c"], "c": []}
    """
    graph: dict[str, list[str]] = defaultdict(list)
    nodes_map: dict[str, Any] = {}

    for node in nodes:
        # Ensure this node exists in the graph
        if node.id not in graph:
            graph[node.id] = []

        # Store node for quick lookup
        nodes_map[node.id] = node

        # Invert dependencies: for each dependency, create edge FROM dependency TO this node
        # This creates an adjacency list where graph[A] = [B, C] means A → B and A → C
        for dep_id in node.dep_ids or []:
            graph[dep_id].append(node.id)

    return FlowGraph(
        graph=dict(graph),  # Convert defaultdict to regular dict
        nodes=nodes_map,
    )


def topological_sort_layers(graph: dict[str, list[str]]) -> list[list[str]]:
    """Sort graph nodes into executable layers using topological sort.

    Each layer contains nodes that can execute concurrently (no dependencies
    between them). Layers must execute in order.

    Args:
        graph: Adjacency list where graph[node] = [dependent_nodes]

    Returns:
        List of layers, each layer is a list of node IDs

    Raises:
        ValueError: If graph has a cycle

    Example:
        >>> graph = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        >>> layers = topological_sort_layers(graph)
        >>> layers
        [["a"], ["b", "c"], ["d"]]
    """
    return layered_topological_sort(graph)


def filter_subgraph_from_node(
    flow_graph: FlowGraph,
    start_node_id: str,
) -> FlowGraph:
    """Extract a subgraph starting from a specific node.

    Returns only the start node and all nodes downstream from it
    (nodes that depend on it, directly or transitively).

    Args:
        flow_graph: Complete flow graph
        start_node_id: Node ID to start from

    Returns:
        FlowGraph containing only downstream nodes

    Raises:
        ValueError: If start_node_id not found in graph

    Example:
        >>> graph = FlowGraph(
        ...     graph={"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []},
        ...     nodes={...}
        ... )
        >>> subgraph = filter_subgraph_from_node(graph, "b")
        >>> subgraph["graph"]
        {"b": ["d"], "d": []}
    """
    if start_node_id not in flow_graph["graph"]:
        raise ValueError(f"Node {start_node_id} not found in graph")

    # BFS to find all downstream nodes
    visited: set[str] = set()
    queue: list[str] = [start_node_id]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue

        visited.add(current)

        # Add all children to queue
        for child in flow_graph["graph"].get(current, []):
            if child not in visited:
                queue.append(child)

    # Build filtered graph
    filtered_graph: dict[str, list[str]] = {}
    filtered_nodes: dict[str, Any] = {}

    for node_id in visited:
        # Only include edges to nodes also in the subgraph
        filtered_graph[node_id] = [
            child for child in flow_graph["graph"][node_id] if child in visited
        ]
        filtered_nodes[node_id] = flow_graph["nodes"][node_id]

    return FlowGraph(
        graph=filtered_graph,
        nodes=filtered_nodes,
    )
