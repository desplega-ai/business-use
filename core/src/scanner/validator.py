"""Graph validation: check dep_ids references, duplicates, unreachable nodes."""

from src.scanner.models import ExtractedNode, ScanWarning


def validate_graph(
    flows: dict[str, list[ExtractedNode]],
) -> list[ScanWarning]:
    """Validate the graph structure of extracted nodes.

    Checks:
    - All dep_ids reference existing nodes within the same flow
    - No duplicate node IDs within a flow
    - Unreachable nodes (no path from a root node)
    """
    warnings: list[ScanWarning] = []

    for flow_name, nodes in flows.items():
        node_ids = {n.id for n in nodes}
        node_map = {n.id: n for n in nodes}

        # Check for duplicate IDs
        seen: set[str] = set()
        for node in nodes:
            if node.id in seen:
                warnings.append(
                    ScanWarning(
                        file=node.source_file,
                        line=node.source_line,
                        message=f"Duplicate node ID '{node.id}' in flow '{flow_name}'",
                    )
                )
            seen.add(node.id)

        # Check dep_ids references
        for node in nodes:
            for dep_id in node.dep_ids:
                if dep_id not in node_ids:
                    warnings.append(
                        ScanWarning(
                            file=node.source_file,
                            line=node.source_line,
                            message=f"Node '{node.id}' references unknown dep_id '{dep_id}' in flow '{flow_name}'",
                        )
                    )

        # Check for unreachable nodes
        # Root nodes have no dep_ids. Walk from roots via reverse edges.
        roots = {n.id for n in nodes if not n.dep_ids}
        if not roots and nodes:
            # All nodes have deps — everything is unreachable from a root
            warnings.append(
                ScanWarning(
                    file=nodes[0].source_file,
                    line=nodes[0].source_line,
                    message=f"Flow '{flow_name}' has no root nodes (all nodes have dependencies)",
                )
            )
        elif roots:
            # Build reverse adjacency: parent -> children who depend on it
            children_of: dict[str, set[str]] = {nid: set() for nid in node_ids}
            for node in nodes:
                for dep_id in node.dep_ids:
                    if dep_id in children_of:
                        children_of[dep_id].add(node.id)

            # BFS from roots
            reachable: set[str] = set()
            queue = list(roots)
            while queue:
                current = queue.pop(0)
                if current in reachable:
                    continue
                reachable.add(current)
                for child in children_of.get(current, set()):
                    if child not in reachable:
                        queue.append(child)

            unreachable = node_ids - reachable
            for nid in unreachable:
                node = node_map[nid]
                warnings.append(
                    ScanWarning(
                        file=node.source_file,
                        line=node.source_line,
                        message=f"Node '{nid}' is unreachable from any root in flow '{flow_name}'",
                    )
                )

    return warnings
