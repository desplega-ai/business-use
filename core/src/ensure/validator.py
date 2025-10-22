"""Validation logic for trigger nodes and ensure command."""

import logging

from src.adapters.sqlite import SqliteEventStorage
from src.db.transactional import transactional
from src.models import Node

log = logging.getLogger(__name__)


def validate_trigger_node(node: Node) -> None:
    """Validate trigger node constraints.

    Enforces:
    - Must have type='trigger'
    - Must be root node (no dep_ids)
    - Must have handler + handler_input
    - Must have run_id_extractor in handler_input.params
    - Handler must be 'http_request' or 'command'

    Args:
        node: Trigger node to validate

    Raises:
        ValueError: If any validation fails with descriptive message
    """
    node.ensure()

    # Check type
    if node.type != "trigger":
        raise ValueError(f"Node '{node.id}' has type='{node.type}', expected 'trigger'")

    # Check root node (no dependencies)
    if node.dep_ids:
        raise ValueError(
            f"Trigger node '{node.id}' cannot have dependencies\n"
            f"  Current dep_ids: {node.dep_ids}\n"
            f"  Remove dep_ids - triggers must be root nodes"
        )

    # Check handler exists
    if not node.handler:
        raise ValueError(
            f"Trigger node '{node.id}' missing handler\n"
            f"  Supported handlers: http_request, command"
        )

    # Check handler type
    if node.handler not in ["http_request", "command", "test_run", "test_suite_run"]:
        raise ValueError(
            f"Trigger node '{node.id}' has unsupported handler: {node.handler}\n"
            f"  Supported handlers: http_request, command"
        )

    # Check handler_input exists
    if not node.handler_input:
        raise ValueError(
            f"Trigger node '{node.id}' missing handler_input\n"
            f"  Add handler_input with params"
        )

    # Check params exists
    if not node.handler_input.params:
        raise ValueError(
            f"Trigger node '{node.id}' missing handler_input.params\n"
            f"  Add params with url/command and run_id_extractor"
        )

    # Check run_id_extractor exists
    if not node.handler_input.params.run_id_extractor:
        raise ValueError(
            f"Trigger node '{node.id}' missing handler_input.params.run_id_extractor\n"
            f"  Add run_id_extractor to extract run_id from trigger response\n"
            f"  Example: run_id_extractor:\n"
            f"    engine: python\n"
            f"    script: \"output['data']['id']\""
        )

    # Handler-specific validation
    if node.handler == "http_request":
        if not node.handler_input.params.url:
            raise ValueError(
                f"Trigger node '{node.id}' with handler='http_request' missing url\n"
                f"  Add url to handler_input.params"
            )
    elif node.handler == "command":
        if not node.handler_input.params.command:
            raise ValueError(
                f"Trigger node '{node.id}' with handler='command' missing command\n"
                f"  Add command to handler_input.params"
            )


async def get_flow_trigger_node(flow: str) -> Node:
    """Get trigger node for a flow, ensuring exactly one exists.

    Args:
        flow: Flow name

    Returns:
        The trigger node

    Raises:
        ValueError: If flow has no trigger or multiple triggers
    """
    storage = SqliteEventStorage()

    async with transactional() as session:
        nodes = await storage.get_nodes_by_flow(flow, session)

    if not nodes:
        raise ValueError(f"No nodes found for flow '{flow}'")

    # Find trigger nodes
    trigger_nodes = [n for n in nodes if n.type == "trigger"]

    if len(trigger_nodes) == 0:
        raise ValueError(
            f"Flow '{flow}' has no trigger nodes\n"
            f"  Add a trigger node with type='trigger' to enable ensure command"
        )

    if len(trigger_nodes) > 1:
        trigger_ids = [n.id for n in trigger_nodes]
        raise ValueError(
            f"Flow '{flow}' has {len(trigger_nodes)} trigger nodes (expected exactly 1)\n"
            f"  Found: {', '.join(trigger_ids)}\n"
            f"  Keep only one trigger node per flow"
        )

    trigger_node = trigger_nodes[0]

    # Validate the trigger node
    validate_trigger_node(trigger_node)

    return trigger_node


async def get_flows_with_triggers() -> list[str]:
    """Get list of all flow names that have trigger nodes.

    Returns:
        List of flow names with at least one trigger node

    Example:
        >>> await get_flows_with_triggers()
        ["payment_approval", "checkout", "user_registration"]
    """
    storage = SqliteEventStorage()

    async with transactional() as session:
        all_nodes = await storage.get_all_nodes(session)

    if not all_nodes:
        return []

    # Find flows with trigger nodes
    flows_with_triggers = {node.flow for node in all_nodes if node.type == "trigger"}

    return sorted(flows_with_triggers)
