"""Sync status checker for flow definitions.

Compares YAML files in workspace with database nodes to detect out-of-sync state.
"""

import logging
from pathlib import Path

from src.adapters.sqlite import SqliteEventStorage
from src.db.transactional import transactional
from src.loaders.yaml_loader import load_nodes_from_yaml

log = logging.getLogger(__name__)


async def check_sync_status(workspace_path: Path) -> list[str]:
    """Compare .business-use/*.yaml files with database nodes.

    Args:
        workspace_path: Path to workspace directory (e.g., ./.business-use/)

    Returns:
        List of out-of-sync file paths (relative to workspace).
        Empty list if all files are in sync.

    Example:
        >>> await check_sync_status(Path(".business-use"))
        ["payment_approval.yaml", "checkout.yaml"]
    """
    out_of_sync_files: list[str] = []

    # Find all YAML flow definition files
    yaml_files = list(workspace_path.glob("*.yaml")) + list(
        workspace_path.glob("*.yml")
    )

    # Filter out example and config files
    flow_files = [
        f
        for f in yaml_files
        if not f.name.endswith((".example", "config.yaml", "secrets.yaml"))
    ]

    if not flow_files:
        log.debug("No flow definition files found in workspace")
        return out_of_sync_files

    storage = SqliteEventStorage()

    for yaml_file in flow_files:
        try:
            # Load nodes from YAML
            yaml_nodes = load_nodes_from_yaml(yaml_file)

            if not yaml_nodes:
                continue

            # Get flow name
            flow_name = yaml_nodes[0].flow

            # Get nodes from database for this flow
            async with transactional() as session:
                db_nodes = await storage.get_nodes_by_flow(flow_name, session)

            # Compare node counts
            if len(yaml_nodes) != len(db_nodes):
                log.debug(
                    f"Node count mismatch for {yaml_file.name}: "
                    f"YAML={len(yaml_nodes)}, DB={len(db_nodes)}"
                )
                out_of_sync_files.append(yaml_file.name)
                continue

            # Compare node IDs
            yaml_node_ids = {node.node_data["id"] for node in yaml_nodes}
            db_node_ids = {node.id for node in db_nodes}

            if yaml_node_ids != db_node_ids:
                log.debug(
                    f"Node IDs mismatch for {yaml_file.name}: "
                    f"diff={yaml_node_ids.symmetric_difference(db_node_ids)}"
                )
                out_of_sync_files.append(yaml_file.name)
                continue

            # Could add more detailed comparison here (node properties, etc.)
            # For now, count + IDs is sufficient

        except Exception as e:
            log.warning(f"Error checking sync status for {yaml_file.name}: {e}")
            # Don't add to out_of_sync_files if we can't determine status
            continue

    return out_of_sync_files


async def prompt_sync_if_needed(workspace_path: Path) -> bool:
    """Check sync status and prompt user if out of sync.

    Args:
        workspace_path: Path to workspace directory

    Returns:
        True if user chose to sync (or if already in sync)
        False if user declined to sync

    Note:
        This is a no-op if all files are in sync.
        Default answer is 'no' (safe default).
    """
    import click

    out_of_sync = await check_sync_status(workspace_path)

    if not out_of_sync:
        log.debug("All flow definitions are in sync")
        return True

    # Show warning
    click.echo()
    click.secho("⚠️  Flow definitions out of sync:", fg="yellow", bold=True)
    for file_name in out_of_sync:
        click.secho(f"  - {file_name}", fg="yellow")
    click.echo()
    click.echo("The YAML files differ from database nodes.")
    click.echo()

    # Ask user
    sync_now = click.confirm("Sync now?", default=False)

    if not sync_now:
        click.echo()
        click.secho("Continuing without sync...", fg="yellow")
        click.echo("You can sync manually with:")
        click.secho("  business-use nodes sync", fg="cyan")
        click.echo()

    return sync_now
