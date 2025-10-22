import asyncio
import json
import logging
import secrets
import warnings
from pathlib import Path

import click
from alembic import command
from alembic.config import Config as AlembicConfig

from src.config import API_KEY, DATABASE_PATH
from src.logging import configure_logging

log = logging.getLogger(__name__)


configure_logging()

# Suppress Pydantic serialization warnings for dict-stored JSON fields
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="pydantic.main",
    message=".*Pydantic serializer warnings.*",
)


def get_alembic_config() -> AlembicConfig:
    """Get Alembic configuration.

    Configures Alembic programmatically to work with packaged migrations.
    """
    from src.config import DATABASE_URL

    # Create config programmatically (no alembic.ini needed)
    alembic_cfg = AlembicConfig()

    # Find migrations directory relative to this file
    # When installed, migrations will be at src/migrations
    src_dir = Path(__file__).parent
    migrations_dir = src_dir / "migrations"

    # Fallback to old location for development
    if not migrations_dir.exists():
        migrations_dir = src_dir.parent / "migrations"

    if not migrations_dir.exists():
        raise RuntimeError(
            f"Migrations directory not found. Looked in:\n"
            f"  - {src_dir / 'migrations'}\n"
            f"  - {src_dir.parent / 'migrations'}"
        )

    # Configure alembic
    alembic_cfg.set_main_option("script_location", str(migrations_dir))
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

    return alembic_cfg


def check_database_exists() -> bool:
    """Check if the database file exists.

    Returns:
        True if database exists, False otherwise
    """
    db_path = Path(DATABASE_PATH)
    return db_path.exists()


def ensure_database_or_exit() -> None:
    """Check if database exists, exit with helpful message if not."""
    if not check_database_exists():
        click.secho("Database not found!", fg="red", bold=True)
        click.echo(f"Expected location: {DATABASE_PATH}")
        click.echo()
        click.echo("To initialize the database, run:")
        click.secho("  business-use db migrate", fg="green", bold=True)
        click.echo()
        raise click.Abort()


def ensure_api_key_or_exit() -> None:
    """Check if API_KEY is configured, exit with helpful message if not."""
    if not API_KEY:
        click.secho("API_KEY not configured!", fg="red", bold=True)
        click.echo()
        click.echo("The API server requires an API key for authentication.")
        click.echo()
        click.echo("To generate and configure an API key, run:")
        click.secho("  business-use init", fg="green", bold=True)
        click.echo()
        click.echo("Or manually add it to your config file:")
        click.echo()
        if Path("./config.yaml").exists():
            click.secho("  Edit: ./config.yaml", fg="cyan")
        else:
            config_path = Path.home() / ".business-use" / "config.yaml"
            click.secho(f"  Edit: {config_path}", fg="cyan")
        click.echo()
        click.echo("Add the following line:")
        click.secho("  api_key: your_secret_key_here", fg="yellow")
        click.echo()
        raise click.Abort()


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return secrets.token_urlsafe(32)


@click.group()
def cli() -> None:
    """Business-Use CLI - Database management and utilities."""
    pass


@cli.command()
def init() -> None:
    """Initialize Business-Use configuration for first-time setup.

    This command will:
    - Generate a secure API key
    - Create config.yaml if it doesn't exist
    - Optionally run database migrations

    Examples:
        business-use init    # Interactive first-time setup
    """
    click.secho("🚀 Business-Use First-Time Setup", fg="cyan", bold=True)
    click.echo()

    # Check if config already exists
    local_config = Path("./config.yaml")
    user_config = Path.home() / ".business-use" / "config.yaml"

    config_path = local_config if local_config.exists() else user_config
    config_exists = config_path.exists()

    if config_exists:
        click.echo(f"Found existing config: {config_path}")
        click.echo()

    # Generate API key
    api_key = generate_api_key()
    click.secho("Generated API Key:", fg="green", bold=True)
    click.secho(f"  {api_key}", fg="yellow")
    click.echo()
    click.echo(
        "⚠️  Save this key securely - you'll need it to authenticate API requests."
    )
    click.echo()

    # Ask to save to config
    if click.confirm(f"Save API key to {config_path}?", default=True):
        try:
            import yaml

            # Determine which config to use
            if not local_config.exists() and not user_config.exists():
                # Neither exists, ask which to create
                click.echo()
                click.echo("Where should the config file be created?")
                click.echo(f"  1. {local_config} (recommended for development)")
                click.echo(f"  2. {user_config} (recommended for production)")
                choice = click.prompt(
                    "Choose", type=click.Choice(["1", "2"]), default="1"
                )
                config_path = local_config if choice == "1" else user_config

            # Load existing config or create from example
            if config_path.exists():
                with open(config_path) as f:
                    config_data = yaml.safe_load(f) or {}
            else:
                # Create from example
                example_path = Path("./config.yaml.example")
                if example_path.exists():
                    with open(example_path) as f:
                        config_data = yaml.safe_load(f) or {}
                else:
                    # Create minimal config
                    config_data = {
                        "database_path": "./db.sqlite"
                        if config_path == local_config
                        else str(Path.home() / ".business-use" / "db.sqlite"),
                        "log_level": "info",
                        "debug": False,
                        "env": "local",
                    }

            # Update API key
            config_data["api_key"] = api_key

            # Ensure parent directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write config
            with open(config_path, "w") as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

            click.echo()
            click.secho(f"✓ Configuration saved to: {config_path}", fg="green")

        except Exception as e:
            click.secho(f"✗ Failed to save config: {e}", fg="red")
            click.echo()
            click.echo("You can manually create the config file with:")
            click.echo(f"  echo 'api_key: {api_key}' > {config_path}")
            raise click.Abort() from e
    else:
        click.echo()
        click.echo("API key not saved. To save it later, add this to your config.yaml:")
        click.secho(f"  api_key: {api_key}", fg="yellow")

    # Ask about database migration
    click.echo()
    if not check_database_exists():
        if click.confirm("Initialize database now?", default=True):
            click.echo()
            click.secho("Running database migrations...", fg="cyan")
            try:
                alembic_cfg = get_alembic_config()
                command.upgrade(alembic_cfg, "head")
                click.secho("✓ Database initialized successfully", fg="green")
            except Exception as e:
                click.secho(f"✗ Database migration failed: {e}", fg="red")
                click.echo()
                click.echo("You can run migrations manually with:")
                click.secho("  business-use db migrate", fg="yellow")
        else:
            click.echo()
            click.echo("Skipping database initialization. Run this later:")
            click.secho("  business-use db migrate", fg="yellow")
    else:
        click.secho("✓ Database already exists", fg="green")

    # Show next steps
    click.echo()
    click.secho("=" * 60, fg="cyan")
    click.secho("✨ Setup Complete!", fg="green", bold=True)
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Start the server:")
    click.secho("     business-use serve --reload", fg="green")
    click.echo()
    click.echo("  2. Test with SDKs using this API key:")
    click.secho(f"     export BUSINESS_USE_API_KEY={api_key}", fg="yellow")
    click.secho("     export BUSINESS_USE_URL=http://localhost:13370", fg="yellow")
    click.secho("=" * 60, fg="cyan")


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
    ensure_api_key_or_exit()

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
    ensure_api_key_or_exit()

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
    children: set[str] = set()
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
                node_children = graph.get(node, [])
                if any(child in next_level for child in node_children):
                    arrows.append(" │")
                else:
                    arrows.append("  ")

            if any(a.strip() for a in arrows):
                lines.append("  " + "      ".join(arrows))
                lines.append(
                    "  " + "      ".join([" ↓" if a.strip() else "  " for a in arrows])
                )

    return "\n".join(lines)


@cli.command()
@click.argument("run_id")
@click.argument("flow")
@click.option(
    "--start-node", default=None, help="Start evaluation from specific node (subgraph)"
)
@click.option("--json-output", is_flag=True, help="Output results as JSON")
@click.option(
    "--verbose", "-v", is_flag=True, help="Verbose output with execution details"
)
@click.option("--show-graph", "-g", is_flag=True, help="Show ASCII graph visualization")
def eval_run(
    run_id: str,
    flow: str,
    start_node: str | None,
    json_output: bool,
    verbose: bool,
    show_graph: bool,
) -> None:
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
    ensure_database_or_exit()

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
                click.secho(
                    f"Status: {result.status.upper()}", fg=status_color, bold=True
                )
                click.echo(f"Elapsed: {result.elapsed_ns / 1_000_000:.2f}ms")
                click.echo(f"Events processed: {len(result.ev_ids)}")
                click.echo(f"Graph nodes: {len(result.graph)}")
                click.echo(f"{'=' * 60}\n")

                # Show graph visualization if requested
                if show_graph:
                    click.echo("Flow Graph:")
                    click.echo("-" * 60)

                    # Build status map from exec_info
                    status_map = {
                        item.node_id: item.status for item in result.exec_info
                    }

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
                        item_status_color = (
                            "green"
                            if item.status == "passed"
                            else ("yellow" if item.status == "skipped" else "red")
                        )

                        click.echo(f"\nNode: {item.node_id}")
                        click.secho(f"  Status: {item.status}", fg=item_status_color)

                        if item.dep_node_ids:
                            click.echo(
                                f"  Dependencies: {', '.join(item.dep_node_ids)}"
                            )

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
                    passed = sum(
                        1 for item in result.exec_info if item.status == "passed"
                    )
                    failed = sum(
                        1 for item in result.exec_info if item.status == "failed"
                    )
                    skipped = sum(
                        1 for item in result.exec_info if item.status == "skipped"
                    )

                    click.echo("Summary:")
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
            raise click.Abort() from e
        except Exception as e:
            click.secho(f"Unexpected error: {e}", fg="red", err=True)
            log.exception("Evaluation failed")
            raise click.Abort() from e

    asyncio.run(run_evaluation())


@cli.command()
@click.argument("flow", required=False)
@click.option(
    "--nodes-only", is_flag=True, help="Show only node names without visualization"
)
def show_graph(flow: str | None, nodes_only: bool) -> None:
    """Show the flow graph definition without running evaluation.

    Displays the graph structure for a flow based on node definitions.
    If no flow is specified, shows an interactive list to choose from.

    Examples:
        cli show-graph                    # Interactive flow selection
        cli show-graph checkout           # Show checkout flow graph
        cli show-graph checkout --nodes-only  # Just list nodes
    """
    ensure_database_or_exit()

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
                flows = sorted({node.flow for node in all_nodes})

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
                    deps_str = (
                        f" (depends on: {', '.join(node.dep_ids)})"
                        if node.dep_ids
                        else ""
                    )
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
                        filter_script = (
                            node.filter.script
                            if hasattr(node.filter, "script")
                            else str(node.filter)
                        )
                        click.echo(f"    Filter: {filter_script}")

                    if node.validator:
                        validator_script = (
                            node.validator.script
                            if hasattr(node.validator, "script")
                            else str(node.validator)
                        )
                        click.echo(f"    Validator: {validator_script}")

                    if node.conditions:
                        for cond in node.conditions:
                            if cond.timeout_ms:
                                click.echo(f"    Timeout: {cond.timeout_ms}ms")

        except Exception as e:
            click.secho(f"Error: {e}", fg="red", err=True)
            log.exception("Failed to show graph")
            raise click.Abort() from e

    asyncio.run(show_flow_graph())


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def sync_nodes(path: Path) -> None:
    """Sync node definitions from YAML file(s) to the database.

    Supports syncing from a single YAML file or directory containing YAML files.
    Nodes are upserted (created or updated) with source='code'.

    Examples:
        cli sync-nodes .business-use/checkout.yaml    # Sync single file
        cli sync-nodes .business-use/                 # Sync all YAML files in directory
    """
    ensure_database_or_exit()

    import asyncio

    from src.db.transactional import transactional
    from src.loaders.yaml_loader import load_nodes_from_yaml
    from src.models import Node
    from src.utils.time import now

    async def sync_yaml_nodes() -> None:
        try:
            # Collect all YAML files
            yaml_files: list[Path] = []
            if path.is_file():
                yaml_files = [path]
            elif path.is_dir():
                yaml_files = list(path.rglob("*.yaml")) + list(path.rglob("*.yml"))
            else:
                click.secho("Path must be a file or directory", fg="red")
                raise click.Abort()

            if not yaml_files:
                click.secho(f"No YAML files found in {path}", fg="yellow")
                return

            click.echo(f"Found {len(yaml_files)} YAML file(s) to process")

            total_synced = 0
            total_errors = 0

            for yaml_file in yaml_files:
                try:
                    click.echo(
                        f"\nProcessing: {yaml_file.relative_to(Path.cwd()) if yaml_file.is_relative_to(Path.cwd()) else yaml_file}"
                    )

                    # Load node definitions from YAML
                    node_defs = load_nodes_from_yaml(yaml_file)

                    if not node_defs:
                        click.secho(
                            f"  No nodes found in {yaml_file.name}", fg="yellow"
                        )
                        continue

                    # Sync to database
                    async with transactional() as session:
                        for node_def in node_defs:
                            schema = node_def.to_create_schema()

                            # Check if node exists
                            existing_node = await session.get(Node, schema.id)

                            node = Node(
                                id=schema.id,
                                flow=schema.flow,
                                type=schema.type,
                                source="code",  # YAML nodes are source='code'
                                description=schema.description,
                                dep_ids=schema.dep_ids or [],
                                filter=schema.filter,
                                validator=schema.validator,
                                conditions=schema.conditions or [],
                                handler=schema.handler,
                                handler_input=schema.handler_input,
                                additional_meta=schema.additional_meta,
                                created_at=existing_node.created_at
                                if existing_node
                                else now(),
                                updated_at=now(),
                                deleted_at=None,
                                status="active",
                            )

                            if existing_node:
                                await session.merge(node)
                                click.secho(f"  ✓ Updated: {node.id}", fg="green")
                            else:
                                session.add(node)
                                click.secho(f"  ✓ Created: {node.id}", fg="green")

                            total_synced += 1

                except Exception as e:
                    click.secho(f"  ✗ Error processing {yaml_file.name}: {e}", fg="red")
                    log.exception(f"Failed to process {yaml_file}")
                    total_errors += 1

            click.echo(f"\n{'=' * 60}")
            click.secho(
                f"Sync complete: {total_synced} node(s) synced", fg="cyan", bold=True
            )
            if total_errors > 0:
                click.secho(f"Errors: {total_errors}", fg="red")
            click.echo(f"{'=' * 60}")

        except Exception as e:
            click.secho(f"Error: {e}", fg="red", err=True)
            log.exception("Sync failed")
            raise click.Abort() from e

    asyncio.run(sync_yaml_nodes())


@cli.command()
@click.argument("flow")
@click.argument("output", type=click.Path(path_type=Path), required=False)
def export_nodes(flow: str, output: Path | None) -> None:
    """Export node definitions from database to YAML format.

    Examples:
        cli export-nodes checkout                      # Print to stdout
        cli export-nodes checkout checkout.yaml        # Save to file
        cli export-nodes checkout .business-use/checkout.yaml  # Save to specific path
    """
    ensure_database_or_exit()

    import asyncio

    from src.adapters.sqlite import SqliteEventStorage
    from src.db.transactional import transactional
    from src.loaders.yaml_loader import export_nodes_to_yaml

    async def export_flow_nodes() -> None:
        try:
            storage = SqliteEventStorage()

            async with transactional() as session:
                nodes = await storage.get_nodes_by_flow(flow, session)

            if not nodes:
                click.secho(f"No nodes found for flow: {flow}", fg="yellow")
                return

            # Convert nodes to dictionaries
            node_dicts = []
            for node in nodes:
                node.ensure()
                node_dict = {
                    "id": node.id,
                    "type": node.type,
                    "description": node.description,
                    "dep_ids": node.dep_ids,
                    "filter": node.filter,
                    "validator": node.validator,
                    "conditions": node.conditions,
                    "handler": node.handler,
                    "handler_input": node.handler_input,
                    "additional_meta": node.additional_meta,
                }
                node_dicts.append(node_dict)

            # Export to YAML
            yaml_content = export_nodes_to_yaml(flow, node_dicts)

            if output:
                # Write to file
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(yaml_content)
                click.secho(f"✓ Exported {len(nodes)} node(s) to {output}", fg="green")
            else:
                # Print to stdout
                click.echo(yaml_content)

        except Exception as e:
            click.secho(f"Error: {e}", fg="red", err=True)
            log.exception("Export failed")
            raise click.Abort() from e

    asyncio.run(export_flow_nodes())


@cli.command()
@click.option("--flow", default=None, help="Filter by flow name")
@click.option("--run-id", default=None, help="Filter by run ID")
@click.option("--limit", default=10, help="Number of results to show")
@click.option("--json-output", is_flag=True, help="Output results as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed execution info")
def runs(
    flow: str | None,
    run_id: str | None,
    limit: int,
    json_output: bool,
    verbose: bool,
) -> None:
    """View stored evaluation runs from the database.

    Shows past evaluations that have been stored automatically or via API.
    You can filter by flow name or run ID.

    Examples:
        cli runs                          # Show last 10 runs
        cli runs --flow checkout          # Show runs for checkout flow
        cli runs --run-id run_123         # Show specific run
        cli runs --limit 20               # Show last 20 runs
        cli runs --verbose                # Show detailed execution info
        cli runs --json-output            # Output as JSON
    """
    ensure_database_or_exit()

    import asyncio

    from sqlalchemy import desc
    from sqlmodel import select

    from src.db.transactional import transactional
    from src.models import EvalOutput

    async def show_runs() -> None:
        try:
            async with transactional() as session:
                stmt = select(EvalOutput)

                if flow:
                    stmt = stmt.where(EvalOutput.flow == flow)

                if run_id:
                    stmt = stmt.where(EvalOutput.run_id == run_id)

                stmt = stmt.order_by(desc(EvalOutput.created_at)).limit(limit)  # type: ignore

                result = await session.execute(stmt)
                eval_outputs = result.scalars().all()

            # Ensure output dicts are converted to objects
            for eval_out in eval_outputs:
                eval_out.ensure()

            if not eval_outputs:
                click.secho("No evaluation runs found", fg="yellow")
                return

            if json_output:
                # Output as JSON
                output = []
                for eval_out in eval_outputs:
                    output.append(
                        {
                            "id": eval_out.id,
                            "flow": eval_out.flow,
                            "run_id": eval_out.run_id,
                            "trigger_ev_id": eval_out.trigger_ev_id,
                            "status": eval_out.output.status,
                            "created_at": eval_out.created_at,
                            "elapsed_ms": eval_out.output.elapsed_ns / 1_000_000,
                            "events_processed": len(eval_out.output.ev_ids),
                            "exec_info": [
                                {
                                    "node_id": item.node_id,
                                    "status": item.status,
                                    "message": item.message,
                                    "error": item.error,
                                }
                                for item in eval_out.output.exec_info
                            ]
                            if verbose
                            else None,
                        }
                    )
                click.echo(json.dumps(output, indent=2, default=str))
            else:
                # Human-readable output
                click.echo(f"\n{'=' * 70}")
                click.secho(
                    f"Showing {len(eval_outputs)} evaluation run(s)",
                    fg="cyan",
                    bold=True,
                )
                click.echo(f"{'=' * 70}\n")

                for eval_out in eval_outputs:
                    status_color = (
                        "green" if eval_out.output.status == "passed" else "red"
                    )

                    click.echo(f"Run ID: {eval_out.run_id}")
                    click.echo(f"Flow: {eval_out.flow}")
                    click.secho(
                        f"Status: {eval_out.output.status.upper()}", fg=status_color
                    )
                    click.echo(
                        f"Created: {eval_out.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    click.echo(
                        f"Elapsed: {eval_out.output.elapsed_ns / 1_000_000:.2f}ms"
                    )
                    click.echo(f"Events: {len(eval_out.output.ev_ids)}")

                    if verbose and eval_out.output.exec_info:
                        click.echo("\nExecution Details:")
                        click.echo("-" * 60)

                        passed = sum(
                            1
                            for item in eval_out.output.exec_info
                            if item.status == "passed"
                        )
                        failed = sum(
                            1
                            for item in eval_out.output.exec_info
                            if item.status == "failed"
                        )
                        skipped = sum(
                            1
                            for item in eval_out.output.exec_info
                            if item.status == "skipped"
                        )

                        click.echo("Summary:")
                        click.secho(f"  ✓ Passed: {passed}", fg="green")
                        if failed > 0:
                            click.secho(f"  ✗ Failed: {failed}", fg="red")
                        if skipped > 0:
                            click.secho(f"  ⊘ Skipped: {skipped}", fg="yellow")

                        click.echo("\nNodes:")
                        for item in eval_out.output.exec_info:
                            item_status_color = (
                                "green"
                                if item.status == "passed"
                                else ("yellow" if item.status == "skipped" else "red")
                            )
                            status_symbol = (
                                "✓"
                                if item.status == "passed"
                                else ("⊘" if item.status == "skipped" else "✗")
                            )

                            msg = f"  [{status_symbol}] {item.node_id}"
                            if item.dep_node_ids:
                                msg += f" (depends on: {', '.join(item.dep_node_ids)})"

                            click.secho(msg, fg=item_status_color)

                            if item.message and item.status != "passed":
                                click.echo(f"      Message: {item.message}")
                            if item.error:
                                click.secho(f"      Error: {item.error}", fg="red")

                    click.echo("-" * 70)
                    click.echo()

                if not verbose:
                    click.echo("Use --verbose to see detailed execution info\n")

        except Exception as e:
            click.secho(f"Error: {e}", fg="red", err=True)
            log.exception("Failed to show runs")
            raise click.Abort() from e

    asyncio.run(show_runs())


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def validate_nodes(path: Path) -> None:
    """Validate YAML node definition file(s) without syncing to database.

    Examples:
        cli validate-nodes .business-use/checkout.yaml    # Validate single file
        cli validate-nodes .business-use/                 # Validate all YAML files
    """
    from src.loaders.yaml_loader import validate_yaml_file

    try:
        # Collect all YAML files
        yaml_files: list[Path] = []
        if path.is_file():
            yaml_files = [path]
        elif path.is_dir():
            yaml_files = list(path.rglob("*.yaml")) + list(path.rglob("*.yml"))
        else:
            click.secho("Path must be a file or directory", fg="red")
            raise click.Abort()

        if not yaml_files:
            click.secho(f"No YAML files found in {path}", fg="yellow")
            return

        click.echo(f"Validating {len(yaml_files)} YAML file(s)...\n")

        valid_count = 0
        invalid_count = 0

        for yaml_file in yaml_files:
            rel_path = (
                yaml_file.relative_to(Path.cwd())
                if yaml_file.is_relative_to(Path.cwd())
                else yaml_file
            )
            is_valid, error = validate_yaml_file(yaml_file)

            if is_valid:
                click.secho(f"✓ {rel_path}", fg="green")
                valid_count += 1
            else:
                click.secho(f"✗ {rel_path}", fg="red")
                click.echo(f"  Error: {error}")
                invalid_count += 1

        click.echo(f"\n{'=' * 60}")
        if invalid_count == 0:
            click.secho(f"All {valid_count} file(s) are valid!", fg="green", bold=True)
        else:
            click.secho(
                f"Valid: {valid_count}, Invalid: {invalid_count}",
                fg="yellow",
                bold=True,
            )
        click.echo(f"{'=' * 60}")

        if invalid_count > 0:
            raise click.Abort()

    except click.Abort:
        raise
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        log.exception("Validation failed")
        raise click.Abort() from e


def main() -> None:
    """Entry point for the CLI."""
    log.info("CLI is running")
    cli()


if __name__ == "__main__":
    log.info("Hi there!")
    main()
