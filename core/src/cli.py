import asyncio
import json
import logging
import secrets
import warnings
from pathlib import Path

import click
import questionary
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


def mask_api_key(api_key: str) -> str:
    """Mask an API key for display purposes.

    Shows first 6 and last 3 characters, masks the middle.
    Example: sk_abc...xyz
    """
    if len(api_key) <= 9:
        return "*" * len(api_key)
    return f"{api_key[:6]}...{api_key[-3:]}"


def find_workspace() -> Path | None:
    """Find the Business-Use workspace directory.

    Priority:
    1. ./.business-use/ (project-level)
    2. ~/.business-use/ (global)

    Returns:
        Path to workspace directory if found, None otherwise
    """
    # Check project-level workspace first
    local_workspace = Path("./.business-use")
    if local_workspace.exists() and local_workspace.is_dir():
        return local_workspace

    # Check global workspace
    global_workspace = Path.home() / ".business-use"
    if global_workspace.exists() and global_workspace.is_dir():
        return global_workspace

    return None


def ensure_workspace_or_exit() -> Path:
    """Find workspace or exit with helpful message.

    Returns:
        Path to workspace directory

    Raises:
        click.Abort if no workspace found
    """
    workspace = find_workspace()
    if workspace is None:
        click.secho("✗ No workspace found!", fg="red", bold=True)
        click.echo()
        click.echo("Run 'business-use workspace init' to create .business-use/")
        click.echo("Or provide a path explicitly")
        raise click.Abort()
    return workspace


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

    If already initialized, use 'business-use config' to modify settings.

    Examples:
        business-use init    # Interactive first-time setup
    """
    click.secho("🚀 Business-Use First-Time Setup", fg="cyan", bold=True)
    click.echo()

    # Check if config already exists (check all locations)
    project_config = Path(".business-use") / "config.yaml"
    local_config = Path("./config.yaml")
    user_config = Path.home() / ".business-use" / "config.yaml"

    if project_config.exists() or local_config.exists() or user_config.exists():
        # Prefer project config, then local (legacy), then global
        if project_config.exists():
            config_path = project_config
        elif local_config.exists():
            config_path = local_config
        else:
            config_path = user_config
        click.secho("✓ Already initialized!", fg="green", bold=True)
        click.echo(f"Configuration file: {config_path}")
        click.echo()
        click.echo("To modify your configuration, use:")
        click.secho("  business-use config", fg="cyan", bold=True)
        click.echo()

        # Check database status
        if not check_database_exists():
            click.echo("Note: Database not initialized yet.")
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
        return

    # First-time setup
    click.echo("No configuration found. Let's set up Business-Use!")
    click.echo()

    # Ask which config location to use
    click.echo("Where should the config file be created?")
    click.echo(f"  1. {project_config} (recommended for project-level)")
    click.echo(f"  2. {user_config} (recommended for global/production)")
    choice = click.prompt("Choose", type=click.Choice(["1", "2"]), default="1")
    config_path = project_config if choice == "1" else user_config
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

    # Create config
    try:
        import yaml

        # Create from example or minimal defaults
        example_path = Path("./config.yaml.example")
        if example_path.exists():
            with open(example_path) as f:
                config_data = yaml.safe_load(f) or {}
        else:
            # Create minimal config
            config_data = {
                "database_path": "./.business-use/db.sqlite"
                if config_path == project_config
                else str(Path.home() / ".business-use" / "db.sqlite"),
                "log_level": "info",
                "debug": False,
                "env": "local",
            }

        # Set API key
        config_data["api_key"] = api_key

        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write config
        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

        click.secho(f"✓ Configuration saved to: {config_path}", fg="green")

    except Exception as e:
        click.secho(f"✗ Failed to save config: {e}", fg="red")
        click.echo()
        click.echo("You can manually create the config file with:")
        click.echo(f"  echo 'api_key: {api_key}' > {config_path}")
        raise click.Abort() from e

    # Initialize database
    click.echo()
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
    click.echo()
    click.echo("  3. To modify configuration later:")
    click.secho("     business-use config", fg="cyan")
    click.secho("=" * 60, fg="cyan")


@cli.command()
def config() -> None:
    """Interactively view and modify Business-Use configuration.

    This command provides an interactive menu to:
    - View current configuration
    - Regenerate API key
    - Change database path
    - Set log level
    - Toggle debug mode
    - Set environment name

    Examples:
        business-use config    # Interactive configuration menu
    """
    import yaml

    click.secho("⚙️  Business-Use Configuration", fg="cyan", bold=True)
    click.echo()

    # Find config file (check all locations)
    project_config = Path(".business-use") / "config.yaml"
    local_config = Path("./config.yaml")
    user_config = Path.home() / ".business-use" / "config.yaml"

    if project_config.exists():
        config_path = project_config
    elif local_config.exists():
        config_path = local_config
        click.secho("⚠️  Using legacy config at ./config.yaml", fg="yellow")
        click.echo("Consider moving to .business-use/config.yaml")
        click.echo()
    elif user_config.exists():
        config_path = user_config
    else:
        click.secho("✗ No configuration found!", fg="red", bold=True)
        click.echo()
        click.echo("Run first-time setup with:")
        click.secho("  business-use init", fg="cyan", bold=True)
        raise click.Abort()

    # Load current config
    with open(config_path) as f:
        config_data = yaml.safe_load(f) or {}

    # Interactive menu loop
    while True:
        click.clear()
        click.secho("⚙️  Business-Use Configuration", fg="cyan", bold=True)
        click.echo(f"Config file: {config_path}")
        click.echo()

        # Display current config
        click.secho("Current Configuration:", fg="white", bold=True)
        click.echo("-" * 60)

        api_key = config_data.get("api_key", "")
        if api_key:
            click.echo(f"  API Key:       {mask_api_key(api_key)}")
        else:
            click.secho("  API Key:       (not configured)", fg="yellow")

        db_path = config_data.get("database_path", "")
        click.echo(f"  Database:      {db_path or '(not configured)'}")

        log_level = config_data.get("log_level", "info")
        click.echo(f"  Log Level:     {log_level}")

        debug = config_data.get("debug", False)
        click.echo(f"  Debug Mode:    {debug}")

        env = config_data.get("env", "local")
        click.echo(f"  Environment:   {env}")

        click.echo("-" * 60)
        click.echo()

        # Menu options
        choices = [
            "Regenerate API key",
            "Change database path",
            "Set log level",
            f"Toggle debug mode (currently: {debug})",
            "Set environment name",
            "Save and exit",
        ]

        try:
            choice = questionary.select(
                "What would you like to do?",
                choices=choices,
                style=questionary.Style(
                    [
                        ("highlighted", "fg:cyan bold"),
                        ("pointer", "fg:cyan bold"),
                    ]
                ),
            ).ask()

            if choice is None:  # User pressed Ctrl+C
                click.echo()
                click.secho("Configuration not saved.", fg="yellow")
                raise click.Abort()

            if choice == "Save and exit":
                break

            elif choice == "Regenerate API key":
                confirm = questionary.confirm(
                    "⚠️  This will generate a new API key. The old key will stop working. Continue?",
                    default=False,
                ).ask()

                if confirm:
                    new_key = generate_api_key()
                    config_data["api_key"] = new_key
                    click.echo()
                    click.secho("✓ New API key generated:", fg="green")
                    click.secho(f"  {new_key}", fg="yellow")
                    click.echo()
                    click.echo("⚠️  Save this key securely!")
                    click.echo()
                    questionary.press_any_key_to_continue(
                        "Press any key to continue..."
                    ).ask()

            elif choice == "Change database path":
                current = config_data.get("database_path", "./db.sqlite")
                new_path = questionary.text(
                    "Enter database path:", default=current
                ).ask()

                if new_path and new_path != current:
                    config_data["database_path"] = new_path
                    click.secho(f"✓ Database path updated to: {new_path}", fg="green")
                    click.echo()
                    questionary.press_any_key_to_continue(
                        "Press any key to continue..."
                    ).ask()

            elif choice == "Set log level":
                new_level = questionary.select(
                    "Choose log level:",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                    default=config_data.get("log_level", "INFO").upper(),
                ).ask()

                if new_level:
                    config_data["log_level"] = new_level.lower()
                    click.secho(f"✓ Log level set to: {new_level}", fg="green")
                    click.echo()
                    questionary.press_any_key_to_continue(
                        "Press any key to continue..."
                    ).ask()

            elif choice.startswith("Toggle debug mode"):
                current_debug = config_data.get("debug", False)
                config_data["debug"] = not current_debug
                new_state = "enabled" if not current_debug else "disabled"
                click.secho(f"✓ Debug mode {new_state}", fg="green")
                click.echo()
                questionary.press_any_key_to_continue(
                    "Press any key to continue..."
                ).ask()

            elif choice == "Set environment name":
                current = config_data.get("env", "local")
                new_env = questionary.text(
                    "Enter environment name:", default=current
                ).ask()

                if new_env and new_env != current:
                    config_data["env"] = new_env
                    click.secho(f"✓ Environment set to: {new_env}", fg="green")
                    click.echo()
                    questionary.press_any_key_to_continue(
                        "Press any key to continue..."
                    ).ask()

        except KeyboardInterrupt:
            click.echo()
            click.secho("Configuration not saved.", fg="yellow")
            raise click.Abort() from None

    # Save config
    try:
        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

        click.echo()
        click.secho("=" * 60, fg="cyan")
        click.secho("✓ Configuration saved successfully!", fg="green", bold=True)
        click.echo(f"Location: {config_path}")
        click.secho("=" * 60, fg="cyan")

    except Exception as e:
        click.secho(f"✗ Failed to save config: {e}", fg="red")
        raise click.Abort() from e


@cli.group()
def workspace() -> None:
    """Workspace management commands."""
    pass


@workspace.command(name="init")
@click.option("--global", "is_global", is_flag=True, help="Create global workspace")
def workspace_init(is_global: bool) -> None:
    """Initialize a Business-Use workspace directory.

    Creates .business-use/ directory with:
    - .gitkeep file (ensures git tracks the directory)
    - example.yaml (sample flow definition)

    By default creates project-level workspace (./.business-use/).
    Use --global to create global workspace (~/.business-use/).

    Examples:
        business-use workspace init           # Create project workspace
        business-use workspace init --global  # Create global workspace
    """
    import yaml

    # Determine workspace path
    if is_global:
        workspace_path = Path.home() / ".business-use"
        workspace_type = "global"
    else:
        workspace_path = Path("./.business-use")
        workspace_type = "project"

    click.secho(f"🚀 Initializing {workspace_type} workspace", fg="cyan", bold=True)
    click.echo(f"Location: {workspace_path}")
    click.echo()

    # Check if workspace already exists
    if workspace_path.exists():
        click.secho(f"✓ Workspace already exists at {workspace_path}", fg="yellow")
        if not click.confirm("Overwrite existing files?", default=False):
            click.echo("Cancelled.")
            return

    # Create workspace directory
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Create .gitkeep
    gitkeep_path = workspace_path / ".gitkeep"
    gitkeep_path.touch()
    click.secho(f"✓ Created {gitkeep_path}", fg="green")

    # Create example.yaml
    example_path = workspace_path / "example.yaml"
    example_content = {
        "flow": "example",
        "nodes": [
            {
                "id": "step_1",
                "type": "act",
                "description": "First step in the flow",
            },
            {
                "id": "step_2",
                "type": "act",
                "description": "Second step, depends on step_1",
                "dep_ids": ["step_1"],
                "conditions": [{"timeout_ms": 5000}],
            },
            {
                "id": "step_3",
                "type": "assert",
                "description": "Final validation step",
                "dep_ids": ["step_2"],
                "validator": {
                    "engine": "python",
                    "script": "data.get('status') == 'complete'",
                },
            },
        ],
    }

    with open(example_path, "w") as f:
        yaml.dump(example_content, f, default_flow_style=False, sort_keys=False)

    click.secho(f"✓ Created {example_path}", fg="green")

    # Show next steps
    click.echo()
    click.secho("=" * 60, fg="cyan")
    click.secho("✨ Workspace initialized!", fg="green", bold=True)
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Edit flow definitions in {workspace_path}/")
    click.secho("     cp example.yaml my-flow.yaml", fg="yellow")
    click.echo()
    click.echo("  2. Sync flows to database:")
    click.secho("     business-use nodes sync", fg="green")
    click.echo()
    click.echo("  3. View flow graphs:")
    click.secho("     business-use flow graph", fg="green")
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


@cli.group()
def server() -> None:
    """Server management commands."""
    pass


@server.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=13370, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def dev(host: str, port: int, reload: bool) -> None:
    """Run the FastAPI server in development mode.

    Examples:
        business-use server dev                    # Run on default port 13370
        business-use server dev --port 8000        # Run on custom port
        business-use server dev --reload           # Run with auto-reload
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


@server.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=13370, help="Port to bind to")
@click.option("--workers", default=4, help="Number of worker processes")
def prod(host: str, port: int, workers: int) -> None:
    """Run the FastAPI server in production mode with multiple workers.

    Examples:
        business-use server prod                     # Run on default port with 4 workers
        business-use server prod --port 8000         # Run on custom port
        business-use server prod --workers 8         # Run with 8 workers
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


@cli.group()
def flow() -> None:
    """Flow evaluation and visualization commands."""
    pass


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


@flow.command()
@click.argument("run_id")
@click.argument("flow_name")
@click.option(
    "--start-node", default=None, help="Start evaluation from specific node (subgraph)"
)
@click.option("--json-output", is_flag=True, help="Output results as JSON")
@click.option(
    "--verbose", "-v", is_flag=True, help="Verbose output with execution details"
)
@click.option("--show-graph", "-g", is_flag=True, help="Show ASCII graph visualization")
def eval(
    run_id: str,
    flow_name: str,
    start_node: str | None,
    json_output: bool,
    verbose: bool,
    show_graph: bool,
) -> None:
    """Evaluate a flow run by run_id and flow.

    This command evaluates whether all events for a given run followed
    the expected flow graph, checking dependencies, timeouts, and conditions.

    Examples:
        business-use flow eval run_123 checkout              # Evaluate checkout flow
        business-use flow eval run_123 checkout --verbose    # With detailed execution
        business-use flow eval run_123 checkout --show-graph # Show ASCII graph
        business-use flow eval run_123 checkout -g -v        # Graph + verbose
        business-use flow eval run_123 checkout --json-output # Output as JSON
        business-use flow eval run_123 checkout --start-node payment_processed  # Subgraph
    """
    ensure_database_or_exit()

    from src.eval import eval_flow_run

    async def run_evaluation():
        try:
            click.echo(f"Evaluating flow run: run_id={run_id}, flow={flow_name}")
            if start_node:
                click.echo(f"Starting from node: {start_node}")

            result = await eval_flow_run(
                run_id=run_id,
                flow=flow_name,
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


@flow.command()
@click.argument("flow_name", required=False)
@click.option(
    "--nodes-only", is_flag=True, help="Show only node names without visualization"
)
def graph(flow_name: str | None, nodes_only: bool) -> None:
    """Show the flow graph definition without running evaluation.

    Displays the graph structure for a flow based on node definitions.
    If no flow is specified, shows an interactive list to choose from.

    Examples:
        business-use flow graph                    # Interactive flow selection
        business-use flow graph checkout           # Show checkout flow graph
        business-use flow graph checkout --nodes-only  # Just list nodes
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
            if not flow_name:
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
                for idx, f_name in enumerate(flows, 1):
                    node_count = sum(1 for n in all_nodes if n.flow == f_name)
                    click.echo(f"  {idx}. {f_name} ({node_count} nodes)")

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
                selected_flow = flow_name

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


@cli.group()
def nodes() -> None:
    """Node definition management commands."""
    pass


@nodes.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), required=False)
def sync(path: Path | None) -> None:
    """Sync node definitions from YAML file(s) to the database.

    Supports syncing from a single YAML file or directory containing YAML files.
    Nodes are upserted (created or updated) with source='code'.

    If no path is provided, automatically finds workspace directory:
    - ./.business-use/ (project-level, priority)
    - ~/.business-use/ (global fallback)

    Examples:
        business-use nodes sync                        # Auto-find workspace
        business-use nodes sync .business-use/checkout.yaml    # Sync single file
        business-use nodes sync ./custom-flows/        # Sync custom directory
    """
    ensure_database_or_exit()

    # If no path provided, use workspace hierarchy
    if path is None:
        path = ensure_workspace_or_exit()
        click.echo(f"Using workspace: {path}")

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
                if yaml_file.name.startswith(
                    "secrets.yaml"
                ) or yaml_file.name.startswith("config.yaml"):
                    continue

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


@nodes.command()
@click.argument("flow_name")
@click.argument("output", type=click.Path(path_type=Path), required=False)
def export(flow_name: str, output: Path | None) -> None:
    """Export node definitions from database to YAML format.

    If no output path is provided:
    - Finds workspace (./.business-use/ or ~/.business-use/)
    - Saves to <workspace>/<flow>.yaml
    - Or prints to stdout if no workspace found

    Examples:
        business-use nodes export checkout                      # Save to workspace or stdout
        business-use nodes export checkout checkout.yaml        # Save to file
        business-use nodes export checkout ./custom/path.yaml   # Save to specific path
    """
    ensure_database_or_exit()

    # If no output provided, try to use workspace
    if output is None:
        workspace = find_workspace()
        if workspace:
            output = workspace / f"{flow_name}.yaml"
            click.echo(f"Exporting to workspace: {output}")
        # If no workspace, will print to stdout (handled below)

    import asyncio

    from src.adapters.sqlite import SqliteEventStorage
    from src.db.transactional import transactional
    from src.loaders.yaml_loader import export_nodes_to_yaml

    async def export_flow_nodes() -> None:
        try:
            storage = SqliteEventStorage()

            async with transactional() as session:
                nodes = await storage.get_nodes_by_flow(flow_name, session)

            if not nodes:
                click.secho(f"No nodes found for flow: {flow_name}", fg="yellow")
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
            yaml_content = export_nodes_to_yaml(flow_name, node_dicts)

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


@flow.command()
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
        business-use flow runs                          # Show last 10 runs
        business-use flow runs --flow checkout          # Show runs for checkout flow
        business-use flow runs --run-id run_123         # Show specific run
        business-use flow runs --limit 20               # Show last 20 runs
        business-use flow runs --verbose                # Show detailed execution info
        business-use flow runs --json-output            # Output as JSON
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


@flow.command()
@click.argument("flow_name", required=False)
@click.option("--parallel", "-p", default=1, help="Run N flows concurrently")
@click.option(
    "--polling-interval", default=2000, help="Poll interval in ms (default: 2000)"
)
@click.option("--max-timeout", default=30000, help="Max timeout in ms (default: 30000)")
@click.option("--live", is_flag=True, help="Interactive live display with spinners")
@click.option("--json-output", is_flag=True, help="Output results as JSON")
@click.option("--no-sync-check", is_flag=True, help="Skip sync status check")
def ensure(
    flow_name: str | None,
    parallel: int,
    polling_interval: int,
    max_timeout: int,
    live: bool,
    json_output: bool,
    no_sync_check: bool,
) -> None:
    """Execute flow triggers and poll until completion.

    Runs flows from trigger node to completion, polling evaluations until
    the flow passes, fails, or times out. Supports parallel execution of
    multiple flows with controlled concurrency.

    The command will:
    1. Find flows with trigger nodes
    2. Validate trigger configuration
    3. Execute HTTP requests or commands
    4. Extract run_id from response
    5. Poll flow evaluation until done

    Examples:
        business-use flow ensure                       # All flows
        business-use flow ensure payment_approval      # Specific flow
        business-use flow ensure --parallel 3          # Run 3 flows concurrently
        business-use flow ensure --live                # Interactive display
        business-use flow ensure --json-output         # JSON output for automation
        business-use flow ensure --max-timeout 60000   # 60s timeout
    """
    import json
    import time

    from src.ensure import (
        LiveDisplay,
        StructuredLogger,
        format_json_output,
        get_flows_with_triggers,
        run_flow_ensure,
        run_flows_parallel,
    )

    ensure_database_or_exit()

    async def run_ensure():
        start_time = time.time()

        # Initialize display
        display = LiveDisplay() if live else StructuredLogger()

        try:
            # Find workspace
            workspace = find_workspace()
            if not workspace:
                click.secho("✗ No workspace found!", fg="red", bold=True)
                click.echo()
                click.echo("Run 'business-use workspace init' to create .business-use/")
                raise click.Abort()

            if live:
                display.show_header("Flow Ensure - Execute & Verify")
                display.show_step("1/5", "Checking workspace...")
                display.show_success(f"Workspace: {workspace}", indent=1)
            else:
                display.log_step("1/5", f"Workspace: {workspace}")

            # Check sync status
            if not no_sync_check:
                if live:
                    display.show_step("2/5", "Checking sync status...")
                else:
                    display.log_step("2/5", "Checking sync status")

                from src.sync import check_sync_status

                out_of_sync_files = await check_sync_status(workspace)
                if out_of_sync_files:
                    # Files are out of sync - abort and tell user to sync
                    click.echo()
                    click.secho(
                        "⚠️  Flow definitions out of sync:", fg="yellow", bold=True
                    )
                    for file_name in out_of_sync_files:
                        click.secho(f"  - {file_name}", fg="yellow")
                    click.echo()
                    click.echo("The YAML files differ from database nodes.")
                    click.echo("Please run:")
                    click.secho("  business-use nodes sync", fg="cyan")
                    click.echo()
                    raise click.Abort()
                # Otherwise, files are in sync - continue

            # Determine flows to run
            if flow_name:
                flows_to_run = [flow_name]
                if live:
                    display.show_step("3/5", f"Running flow: {flow_name}")
                else:
                    display.log_step("3/5", f"Running flow: {flow_name}")
            else:
                # Get all flows with triggers
                all_trigger_flows = await get_flows_with_triggers()
                if not all_trigger_flows:
                    click.secho("✗ No flows with trigger nodes found", fg="red")
                    click.echo()
                    click.echo("Add a trigger node to a flow to use ensure command")
                    raise click.Abort()

                flows_to_run = all_trigger_flows
                if live:
                    display.show_step(
                        "3/5", f"Found {len(flows_to_run)} flows with triggers"
                    )
                    for f in flows_to_run:
                        display.show_info(f"  - {f}", indent=1)
                else:
                    display.log_step(
                        "3/5",
                        f"Found {len(flows_to_run)} flows with triggers: {', '.join(flows_to_run)}",
                    )

            # Run flows
            if live:
                display.show_step(
                    "4/5", f"Executing triggers (concurrency: {parallel})..."
                )
            else:
                display.log_step("4/5", f"Executing triggers (concurrency: {parallel})")

            if len(flows_to_run) == 1:
                # Single flow
                flow_name_single = flows_to_run[0]
                result = await run_flow_ensure(
                    flow_name_single,
                    polling_interval_ms=polling_interval,
                    max_timeout_ms=max_timeout,
                    display=display,
                )
                results = [result]
            else:
                # Multiple flows
                results = await run_flows_parallel(
                    flows=flows_to_run,
                    concurrency=parallel,
                    polling_interval_ms=polling_interval,
                    max_timeout_ms=max_timeout,
                    display=display,
                )

            # Show results
            if live:
                display.show_step("5/5", "Results")
            else:
                display.log_step("5/5", "Results")

            total_elapsed = time.time() - start_time
            passed_count = sum(1 for _, r in results if r.status == "passed")
            failed_count = sum(
                1 for _, r in results if r.status in ["failed", "error", "timed_out"]
            )

            # Display each flow result
            for flow_name_result, output in results:
                elapsed_s = output.elapsed_ns / 1_000_000_000
                if live:
                    display.show_progress(flow_name_result, output.status, elapsed_s)
                else:
                    display.log_progress(flow_name_result, output.status, elapsed_s)

            # Output
            if json_output:
                json_result = format_json_output(results)
                click.echo(json.dumps(json_result, indent=2))
            else:
                if live:
                    display.show_summary(
                        {
                            "total": len(results),
                            "passed": passed_count,
                            "failed": failed_count,
                            "elapsed": total_elapsed,
                        }
                    )
                else:
                    click.echo()
                    click.secho("=" * 60, fg="cyan")
                    click.secho("Summary", fg="cyan", bold=True)
                    click.echo(f"  Flows: {len(results)}")
                    if passed_count > 0:
                        click.secho(f"  ✓ Passed: {passed_count}", fg="green")
                    if failed_count > 0:
                        click.secho(f"  ✗ Failed: {failed_count}", fg="red")
                    click.echo(f"  Total time: {total_elapsed:.1f}s")
                    click.secho("=" * 60, fg="cyan")

            # Exit code
            if failed_count > 0:
                raise click.Abort()

        except click.Abort:
            raise
        except Exception as e:
            click.secho(f"✗ Error: {e}", fg="red", err=True)
            log.exception("Ensure command failed")
            raise click.Abort() from e

    asyncio.run(run_ensure())


@nodes.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), required=False)
def validate(path: Path | None) -> None:
    """Validate YAML node definition file(s) without syncing to database.

    If no path is provided, automatically finds workspace directory:
    - ./.business-use/ (project-level, priority)
    - ~/.business-use/ (global fallback)

    Examples:
        business-use nodes validate                        # Auto-find workspace
        business-use nodes validate .business-use/checkout.yaml    # Validate single file
        business-use nodes validate ./custom-flows/        # Validate custom directory
    """
    from src.loaders.yaml_loader import validate_yaml_file

    # If no path provided, use workspace hierarchy
    if path is None:
        path = ensure_workspace_or_exit()
        click.echo(f"Using workspace: {path}")

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
