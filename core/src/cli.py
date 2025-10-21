import asyncio
import json
import logging

import click
from alembic import command
from alembic.config import Config as AlembicConfig

from src.logging import configure_logging

log = logging.getLogger(__name__)


configure_logging()


def get_alembic_config() -> AlembicConfig:
    """Get Alembic configuration."""
    alembic_cfg = AlembicConfig("alembic.ini")
    return alembic_cfg


@click.group()
def cli() -> None:
    """Magic CLI - Database management and utilities."""
    pass


@cli.group()
def db() -> None:
    """Database migration commands."""
    pass


@db.command()
@click.argument("revision", default="head")
def migrate(revision: str) -> None:
    """Run database migrations (upgrade to a later version).

    Examples:
        cli db migrate           # Upgrade to latest
        cli db migrate head      # Upgrade to latest
        cli db migrate +1        # Upgrade one version
        cli db migrate ae1027a6  # Upgrade to specific revision
    """
    click.echo(f"Running migrations to: {revision}")
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, revision)
    click.echo("✓ Migrations completed successfully")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=13370, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host: str, port: int, reload: bool) -> None:
    """Run the FastAPI server in development mode.

    Examples:
        cli serve                    # Run on default port 13370
        cli serve --port 8000        # Run on custom port
        cli serve --reload           # Run with auto-reload for development
    """
    import uvicorn

    click.echo(f"Starting API server on {host}:{port}")
    if reload:
        click.echo("Auto-reload enabled")

    uvicorn.run(
        "src.api.api:app",
        host=host,
        port=port,
        reload=reload,
    )


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=13370, help="Port to bind to")
@click.option("--workers", default=4, help="Number of worker processes")
def prod(host: str, port: int, workers: int) -> None:
    """Run the FastAPI server in production mode with multiple workers.

    Examples:
        cli prod                     # Run on default port 13370 with 4 workers
        cli prod --port 8000         # Run on custom port
        cli prod --workers 8         # Run with 8 worker processes
    """
    import uvicorn

    click.echo(f"Starting API server in production mode on {host}:{port}")
    click.echo(f"Workers: {workers}")

    uvicorn.run(
        "src.api.api:app",
        host=host,
        port=port,
        workers=workers,
        log_level="info",
        access_log=True,
    )


def render_graph(graph: dict[str, list[str]], status_map: dict[str, str]) -> str:
    """Render a simple ASCII graph visualization.

    Args:
        graph: Adjacency list of nodes
        status_map: Map of node_id -> status (passed/failed/skipped)

    Returns:
        ASCII art representation of the graph
    """
    from collections import deque

    # Build levels using BFS for cleaner visualization
    levels: list[list[str]] = []
    visited: set[str] = set()

    # Find root nodes (no incoming edges)
    all_nodes = set(graph.keys())
    children = set()
    for deps in graph.values():
        children.update(deps)

    roots = all_nodes - children
    if not roots:
        # Handle cycles - just use all nodes
        roots = all_nodes

    queue: deque[tuple[str, int]] = deque()
    for root in sorted(roots):
        queue.append((root, 0))

    while queue:
        node, level = queue.popleft()
        if node in visited:
            continue

        visited.add(node)

        # Extend levels if needed
        while len(levels) <= level:
            levels.append([])

        levels[level].append(node)

        # Add children
        for child in sorted(graph.get(node, [])):
            if child not in visited:
                queue.append((child, level + 1))

    # Render the graph
    lines: list[str] = []
    status_symbols = {
        "passed": "✓",
        "failed": "✗",
        "skipped": "⊘",
        "pending": "○",
    }

    for level_idx, level_nodes in enumerate(levels):
        # Render nodes at this level
        node_strs = []
        for node in level_nodes:
            status = status_map.get(node, "pending")
            symbol = status_symbols.get(status, "?")
            node_strs.append(f"[{symbol}] {node}")

        lines.append("  " + "    ".join(node_strs))

        # Render connections to next level
        if level_idx < len(levels) - 1:
            next_level = levels[level_idx + 1]

            # Simple arrow indicators
            arrows = []
            for node in level_nodes:
                children = graph.get(node, [])
                if any(child in next_level for child in children):
                    arrows.append(" │")
                else:
                    arrows.append("  ")

            if any(a.strip() for a in arrows):
                lines.append("  " + "      ".join(arrows))
                lines.append("  " + "      ".join([" ↓" if a.strip() else "  " for a in arrows]))

    return "\n".join(lines)


@cli.command()
@click.argument("run_id")
@click.argument("flow")
@click.option("--start-node", default=None, help="Start evaluation from specific node (subgraph)")
@click.option("--json-output", is_flag=True, help="Output results as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output with execution details")
@click.option("--show-graph", "-g", is_flag=True, help="Show ASCII graph visualization")
def eval_run(run_id: str, flow: str, start_node: str | None, json_output: bool, verbose: bool, show_graph: bool) -> None:
    """Evaluate a flow run by run_id and flow.

    This command evaluates whether all events for a given run followed
    the expected flow graph, checking dependencies, timeouts, and conditions.

    Examples:
        cli eval-run run_123 checkout              # Evaluate checkout flow for run_123
        cli eval-run run_123 checkout --verbose    # With detailed execution info
        cli eval-run run_123 checkout --show-graph # Show ASCII graph visualization
        cli eval-run run_123 checkout -g -v        # Graph + verbose details
        cli eval-run run_123 checkout --json-output # Output as JSON
        cli eval-run run_123 checkout --start-node payment_processed  # Subgraph eval
    """
    from src.eval import eval_flow_run

    async def run_evaluation():
        try:
            click.echo(f"Evaluating flow run: run_id={run_id}, flow={flow}")
            if start_node:
                click.echo(f"Starting from node: {start_node}")

            result = await eval_flow_run(
                run_id=run_id,
                flow=flow,
                start_node_id=start_node,
            )

            if json_output:
                # Output as JSON
                output = {
                    "run_id": run_id,
                    "flow": flow,
                    "status": result.status,
                    "elapsed_ns": result.elapsed_ns,
                    "elapsed_ms": result.elapsed_ns / 1_000_000,
                    "graph": result.graph,
                    "exec_info": [
                        {
                            "node_id": item.node_id,
                            "dep_node_ids": item.dep_node_ids,
                            "status": item.status,
                            "message": item.message,
                            "error": item.error,
                            "elapsed_ns": item.elapsed_ns,
                            "ev_ids": item.ev_ids,
                            "upstream_ev_ids": item.upstream_ev_ids,
                        }
                        for item in result.exec_info
                    ],
                    "ev_ids": result.ev_ids,
                }
                click.echo(json.dumps(output, indent=2))
            else:
                # Human-readable output
                status_color = "green" if result.status == "passed" else "red"
                click.echo(f"\n{'=' * 60}")
                click.secho(f"Status: {result.status.upper()}", fg=status_color, bold=True)
                click.echo(f"Elapsed: {result.elapsed_ns / 1_000_000:.2f}ms")
                click.echo(f"Events processed: {len(result.ev_ids)}")
                click.echo(f"Graph nodes: {len(result.graph)}")
                click.echo(f"{'=' * 60}\n")

                # Show graph visualization if requested
                if show_graph:
                    click.echo("Flow Graph:")
                    click.echo("-" * 60)

                    # Build status map from exec_info
                    status_map = {item.node_id: item.status for item in result.exec_info}

                    graph_viz = render_graph(result.graph, status_map)

                    # Color the output
                    for line in graph_viz.split("\n"):
                        if "✓" in line:
                            click.secho(line, fg="green")
                        elif "✗" in line:
                            click.secho(line, fg="red")
                        elif "⊘" in line:
                            click.secho(line, fg="yellow")
                        else:
                            click.echo(line)

                    click.echo("-" * 60)
                    click.echo()

                if verbose:
                    click.echo("Execution Details:")
                    click.echo("-" * 60)

                    for item in result.exec_info:
                        item_status_color = "green" if item.status == "passed" else (
                            "yellow" if item.status == "skipped" else "red"
                        )

                        click.echo(f"\nNode: {item.node_id}")
                        click.secho(f"  Status: {item.status}", fg=item_status_color)

                        if item.dep_node_ids:
                            click.echo(f"  Dependencies: {', '.join(item.dep_node_ids)}")

                        if item.message:
                            click.echo(f"  Message: {item.message}")

                        if item.error:
                            click.secho(f"  Error: {item.error}", fg="red")

                        click.echo(f"  Events: {len(item.ev_ids)}")
                        click.echo(f"  Upstream events: {len(item.upstream_ev_ids)}")
                        click.echo(f"  Elapsed: {item.elapsed_ns / 1_000_000:.2f}ms")

                    click.echo("-" * 60)
                else:
                    # Summary view
                    passed = sum(1 for item in result.exec_info if item.status == "passed")
                    failed = sum(1 for item in result.exec_info if item.status == "failed")
                    skipped = sum(1 for item in result.exec_info if item.status == "skipped")

                    click.echo(f"Summary:")
                    click.secho(f"  ✓ Passed: {passed}", fg="green")
                    if failed > 0:
                        click.secho(f"  ✗ Failed: {failed}", fg="red")
                    if skipped > 0:
                        click.secho(f"  ⊘ Skipped: {skipped}", fg="yellow")

                    if failed > 0:
                        click.echo("\nFailed nodes:")
                        for item in result.exec_info:
                            if item.status == "failed":
                                click.secho(f"  - {item.node_id}", fg="red")
                                if item.error:
                                    click.echo(f"    {item.error}")

                    click.echo("\nUse --verbose for detailed execution info")

        except ValueError as e:
            click.secho(f"Error: {e}", fg="red", err=True)
            raise click.Abort()
        except Exception as e:
            click.secho(f"Unexpected error: {e}", fg="red", err=True)
            log.exception("Evaluation failed")
            raise click.Abort()

    asyncio.run(run_evaluation())


@cli.command()
@click.argument("flow", required=False)
@click.option("--nodes-only", is_flag=True, help="Show only node names without visualization")
def show_graph(flow: str | None, nodes_only: bool) -> None:
    """Show the flow graph definition without running evaluation.

    Displays the graph structure for a flow based on node definitions.
    If no flow is specified, shows an interactive list to choose from.

    Examples:
        cli show-graph                    # Interactive flow selection
        cli show-graph checkout           # Show checkout flow graph
        cli show-graph checkout --nodes-only  # Just list nodes
    """
    import asyncio

    from src.adapters.sqlite import SqliteEventStorage
    from src.db.transactional import transactional
    from src.domain.graph import build_flow_graph, topological_sort_layers

    async def show_flow_graph():
        try:
            storage = SqliteEventStorage()

            # If no flow specified, show interactive selection
            if not flow:
                async with transactional() as session:
                    all_nodes = await storage.get_all_nodes(session)

                if not all_nodes:
                    click.secho("No flows found in database", fg="yellow")
                    return

                # Get unique flows
                flows = sorted(set(node.flow for node in all_nodes))

                if len(flows) == 0:
                    click.secho("No flows found", fg="yellow")
                    return

                click.echo("Available flows:")
                for idx, flow_name in enumerate(flows, 1):
                    node_count = sum(1 for n in all_nodes if n.flow == flow_name)
                    click.echo(f"  {idx}. {flow_name} ({node_count} nodes)")

                # Prompt for selection
                click.echo()
                try:
                    selection = click.prompt(
                        "Select flow number (or 'q' to quit)",
                        type=str,
                    )

                    if selection.lower() == "q":
                        return

                    selected_idx = int(selection) - 1
                    if selected_idx < 0 or selected_idx >= len(flows):
                        click.secho("Invalid selection", fg="red")
                        return

                    selected_flow = flows[selected_idx]
                except (ValueError, click.Abort):
                    click.secho("\nCancelled", fg="yellow")
                    return
            else:
                selected_flow = flow

            # Fetch nodes for selected flow
            async with transactional() as session:
                nodes = await storage.get_nodes_by_flow(selected_flow, session)

            if not nodes:
                click.secho(f"No nodes found for flow: {selected_flow}", fg="yellow")
                return

            click.echo(f"\n{'=' * 60}")
            click.secho(f"Flow: {selected_flow}", fg="cyan", bold=True)
            click.echo(f"Nodes: {len(nodes)}")
            click.echo(f"{'=' * 60}\n")

            if nodes_only:
                # Just list the nodes
                click.echo("Nodes:")
                for node in sorted(nodes, key=lambda n: n.id):
                    deps_str = f" (depends on: {', '.join(node.dep_ids)})" if node.dep_ids else ""
                    type_str = f"[{node.type}]"
                    click.echo(f"  {type_str:12} {node.id}{deps_str}")
            else:
                # Build and display graph
                flow_graph = build_flow_graph(nodes)
                layers = topological_sort_layers(flow_graph["graph"])

                click.echo("Flow Graph:")
                click.echo("-" * 60)

                # Build a "no status" map (all pending)
                status_map = {node.id: "pending" for node in nodes}
                graph_viz = render_graph(flow_graph["graph"], status_map)

                # Display without colors (all pending)
                click.echo(graph_viz)
                click.echo("-" * 60)
                click.echo()

                # Show layer information
                click.echo("Execution Layers:")
                for layer_idx, layer_nodes in enumerate(layers):
                    click.echo(f"  Layer {layer_idx}: {', '.join(layer_nodes)}")

                click.echo()

                # Show node details
                click.echo("Node Details:")
                for node in sorted(nodes, key=lambda n: n.id):
                    # Ensure node is properly initialized (converts dicts to objects)
                    node.ensure()

                    click.echo(f"\n  {node.id}:")
                    click.echo(f"    Type: {node.type}")
                    click.echo(f"    Source: {node.source}")

                    if node.dep_ids:
                        click.echo(f"    Dependencies: {', '.join(node.dep_ids)}")

                    if node.description:
                        click.echo(f"    Description: {node.description}")

                    if node.filter:
                        filter_script = node.filter.script if hasattr(node.filter, 'script') else str(node.filter)
                        click.echo(f"    Filter: {filter_script}")

                    if node.validator:
                        validator_script = node.validator.script if hasattr(node.validator, 'script') else str(node.validator)
                        click.echo(f"    Validator: {validator_script}")

                    if node.conditions:
                        for cond in node.conditions:
                            if cond.timeout_ms:
                                click.echo(f"    Timeout: {cond.timeout_ms}ms")

        except Exception as e:
            click.secho(f"Error: {e}", fg="red", err=True)
            log.exception("Failed to show graph")
            raise click.Abort()

    asyncio.run(show_flow_graph())


def main() -> None:
    """Entry point for the CLI."""
    log.info("CLI is running")
    cli()


if __name__ == "__main__":
    log.info("Hi there!")
    main()
