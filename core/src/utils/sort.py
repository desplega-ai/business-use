from collections import deque


def layered_topological_sort(graph: dict[str, list[str]]) -> list[list[str]]:
    """
    Given an adjacency list where graph[node] = [successors/children],
    returns layers of nodes that can be executed concurrently.
    """
    all_nodes = set(graph.keys())
    for targets in graph.values():
        all_nodes.update(targets)

    in_degree = dict.fromkeys(all_nodes, 0)

    # Count incoming edges (how many things point TO each node)
    for u in graph:
        for v in graph[u]:
            in_degree[v] += 1

    queue = deque([node for node in all_nodes if in_degree[node] == 0])
    result: list[list[str]] = []
    processed = set()

    while queue:
        layer = list(queue)
        result.append(layer)
        next_queue: deque[str] = deque()
        for node in layer:
            processed.add(node)
            for neighbor in graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    next_queue.append(neighbor)
        queue = next_queue

    if len(processed) != len(all_nodes):
        raise ValueError("Graph has a cycle")

    return result
