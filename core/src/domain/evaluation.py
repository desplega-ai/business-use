"""Core flow validation logic.

This module provides pure business logic for matching events to graph layers
and validating flow execution. It has zero external dependencies except for
the evaluator protocol.
"""

import logging
from time import time_ns
from typing import Any, Protocol

from src.domain.types import LayeredEvents, ValidationItem, ValidationResult
from src.models import Event, Expr, Node
from src.utils.text import append_text

logger = logging.getLogger(__name__)


class ExprEvaluator(Protocol):
    """Protocol for expression evaluation.

    This allows the evaluation logic to be pluggable - different
    implementations can be swapped in (Python, CEL, JS, etc).
    """

    def evaluate(self, expr: Expr, data: dict[str, Any], ctx: dict[str, Any]) -> bool:
        """Evaluate an expression against data and context.

        Args:
            expr: Expression to evaluate
            data: Target data (current event data)
            ctx: Context data (typically upstream event data)

        Returns:
            True if expression evaluates to true, False otherwise.
            Never raises exceptions.
        """
        ...


def match_events_to_layers(
    events: list[Event],
    layers: list[list[str]],
    nodes_map: dict[str, Node],
    evaluator: ExprEvaluator,
) -> LayeredEvents:
    """Match events to graph layers based on run_id, flow, and filters.

    This implementation uses run_id + flow tuple and supports multiple
    upstream dependencies with Ctx structure.

    Args:
        events: List of events (already filtered by run_id + flow)
        layers: Topologically sorted layers of node IDs
        nodes_map: Map of node_id -> Node for lookup
        evaluator: Expression evaluator for filter evaluation

    Returns:
        LayeredEvents with matched events per layer

    Example:
        >>> events = [Event(id="e1", node_id="a", run_id="run1", ...)]
        >>> layers = [["a"], ["b", "c"]]
        >>> matched = match_events_to_layers(events, layers, nodes_map, evaluator)
        >>> matched["layers"]
        [["e1"], ["e2", "e3"]]
    """
    from typing import cast

    from src.domain.types import Ctx, DepData

    final_ev_list: list[list[str]] = []
    events_map: dict[str, Event] = {ev.id: ev for ev in events}

    # For each layer, find matching events
    for layer_index, layer_node_ids in enumerate(layers):
        layer_event_ids: list[str] = []

        for node_id in layer_node_ids:
            current_node = nodes_map.get(node_id)
            if current_node is None:
                continue

            current_node.ensure()  # Ensure node is properly initialized

            # Find events for this node
            for event in events:
                if event.node_id != node_id:
                    continue

                # Build context from ALL upstream dependencies
                ctx: Ctx = {"deps": []}

                if current_node.dep_ids:
                    # For each dep_id, find ALL matching events from previous layers
                    for dep_id in current_node.dep_ids:
                        # Search all previous layers for events matching this dep_id
                        for prev_layer_index in range(layer_index):
                            prev_layer_event_ids = final_ev_list[prev_layer_index]
                            for prev_event_id in prev_layer_event_ids:
                                prev_event = events_map[prev_event_id]
                                if prev_event.node_id == dep_id:
                                    # Add this event to deps
                                    dep_data: DepData = {
                                        "flow": prev_event.flow,
                                        "id": prev_event.node_id,
                                        "data": prev_event.data,
                                    }
                                    ctx["deps"].append(dep_data)

                # Evaluate filter if present
                include_event = True
                if current_node.filter:
                    # Evaluate filter with proper Ctx
                    filter_result = evaluator.evaluate(
                        current_node.filter,
                        data=event.data,
                        ctx=cast(dict[str, Any], ctx),
                    )
                    # If filter returns False, skip this event
                    # (node will get "passed" status during validation)
                    if not filter_result:
                        include_event = False

                # Include event only if filter passed (or no filter)
                if include_event:
                    layer_event_ids.append(event.id)

        final_ev_list.append(layer_event_ids)

    return LayeredEvents(
        layers=final_ev_list,
        events=events_map,
    )


def validate_flow_execution(
    matched: LayeredEvents,
    nodes_map: dict[str, Node],
    layers: list[list[str]],
    evaluator: ExprEvaluator | None = None,
) -> ValidationResult:
    """Validate that flow execution followed the expected graph.

    Checks:
    - All required nodes have events
    - Dependencies are satisfied
    - Timeout conditions are met
    - Validators pass

    Args:
        matched: Events matched to layers
        nodes_map: Map of node_id -> Node
        layers: Topologically sorted layers of node IDs
        evaluator: Optional expression evaluator for validator evaluation

    Returns:
        ValidationResult with status and detailed items
    """
    from typing import cast

    from src.domain.types import Ctx, DepData

    start_time = time_ns()
    items: list[ValidationItem] = []
    all_ev_ids: list[str] = []
    overall_status: str = "pending"

    # Collect all event IDs
    for layer_ev_ids in matched["layers"]:
        all_ev_ids.extend(layer_ev_ids)

    # Build graph for output
    graph: dict[str, list[str]] = {}
    for node_id, node in nodes_map.items():
        graph[node_id] = node.dep_ids or []

    # Validate each layer
    for layer_index, layer_node_ids in enumerate(layers):
        layer_ev_ids = matched["layers"][layer_index]

        for node_id in layer_node_ids:
            current_node = nodes_map.get(node_id)
            if current_node is None:
                continue

            current_node.ensure()

            # Early skip if previous failed
            if overall_status == "failed":
                items.append(
                    ValidationItem(
                        node_id=node_id,
                        dep_node_ids=current_node.dep_ids or [],
                        message="Skipped due to previous failure",
                        status="skipped",
                        elapsed_ns=0,
                        ev_ids=layer_ev_ids,
                        upstream_ev_ids=[],
                    )
                )
                continue

            item_start = time_ns()

            # Get current layer events for this node
            current_node_events = [
                matched["events"][ev_id]
                for ev_id in layer_ev_ids
                if matched["events"][ev_id].node_id == node_id
            ]

            # If no events for this node, determine status based on node type, conditions, and timing
            if not current_node_events:
                # Find the most recent upstream dependency event timestamp
                upstream_event_ts: int | None = None
                if current_node.dep_ids:
                    # Search all previous layers for the most recent dependency event
                    for prev_layer_index in range(layer_index):
                        prev_layer_event_ids = matched["layers"][prev_layer_index]
                        for prev_event_id in prev_layer_event_ids:
                            prev_event = matched["events"][prev_event_id]
                            if prev_event.node_id in current_node.dep_ids:
                                # Track the most recent (highest timestamp)
                                if (
                                    upstream_event_ts is None
                                    or prev_event.ts > upstream_event_ts
                                ):
                                    upstream_event_ts = prev_event.ts

                # Check if this node should fail/wait based on timing
                node_status = "skipped"
                node_message = "No events for this node"
                should_mark_overall_failed = False

                # Act nodes with conditions (especially timeout)
                if current_node.type == "act" and current_node.conditions:
                    # Find timeout_ms if present, default to 10 seconds
                    timeout_ms = None
                    for condition in current_node.conditions:
                        if condition.timeout_ms:
                            timeout_ms = condition.timeout_ms
                            break

                    # Default timeout: 10 seconds if not specified
                    if timeout_ms is None:
                        timeout_ms = 10000

                    if upstream_event_ts is not None:
                        # Calculate elapsed time since upstream event
                        current_time_ns = time_ns()
                        elapsed_ns = current_time_ns - upstream_event_ts
                        elapsed_ms = elapsed_ns / 1_000_000

                        if elapsed_ms < timeout_ms:
                            # Still within timeout window - keep waiting
                            node_status = "running"
                            remaining_ms = timeout_ms - elapsed_ms
                            node_message = f"Waiting for event ({elapsed_ms:.0f}ms / {timeout_ms}ms elapsed, {remaining_ms:.0f}ms remaining)"
                        else:
                            # Timeout expired - fail
                            node_status = "failed"
                            node_message = (
                                f"Timeout: No event received within {timeout_ms}ms"
                            )
                            should_mark_overall_failed = True
                    else:
                        # No upstream event - can't determine if timeout expired
                        if upstream_event_ts is None:
                            # No upstream event yet - skip (dependency hasn't completed)
                            node_status = "skipped"
                            node_message = "Waiting for upstream dependency"
                        else:
                            # Has upstream but something went wrong
                            node_status = "failed"
                            node_message = (
                                "No event received for act node with conditions"
                            )
                            should_mark_overall_failed = True

                # Assert nodes always should fail when missing (they have validators)
                elif current_node.type == "assert":
                    # Check if we have a timeout from conditions, default to 10 seconds
                    timeout_ms = None
                    if current_node.conditions:
                        for condition in current_node.conditions:
                            if condition.timeout_ms:
                                timeout_ms = condition.timeout_ms
                                break

                    # Default timeout: 10 seconds if not specified
                    if timeout_ms is None:
                        timeout_ms = 10000

                    if upstream_event_ts is not None:
                        # Calculate elapsed time since upstream event
                        current_time_ns = time_ns()
                        elapsed_ns = current_time_ns - upstream_event_ts
                        elapsed_ms = elapsed_ns / 1_000_000

                        if elapsed_ms < timeout_ms:
                            # Still within timeout window
                            node_status = "running"
                            remaining_ms = timeout_ms - elapsed_ms
                            node_message = f"Waiting for event ({elapsed_ms:.0f}ms / {timeout_ms}ms elapsed, {remaining_ms:.0f}ms remaining)"
                        else:
                            # Timeout expired
                            node_status = "failed"
                            node_message = (
                                f"Timeout: No event received within {timeout_ms}ms"
                            )
                            should_mark_overall_failed = True
                    else:
                        # No timeout or no upstream event
                        if upstream_event_ts is None:
                            # No upstream event yet - skip (dependency hasn't completed)
                            node_status = "skipped"
                            node_message = "Waiting for upstream dependency"
                        else:
                            # Has upstream but no timeout - fail
                            node_status = "failed"
                            node_message = "No event received for assert node"
                            should_mark_overall_failed = True

                # Mark overall status as failed only if actually failed (not running)
                if should_mark_overall_failed:
                    overall_status = "failed"

                items.append(
                    ValidationItem(
                        node_id=node_id,
                        dep_node_ids=current_node.dep_ids or [],
                        message=node_message,
                        status=node_status,  # type: ignore
                        elapsed_ns=time_ns() - item_start,
                        ev_ids=[],
                        upstream_ev_ids=[],
                    )
                )
                continue

            # Build Ctx from ALL upstream dependencies
            ctx: Ctx = {"deps": []}
            upstream_ev_ids: list[str] = []

            if current_node.dep_ids:
                # For each dep_id, find ALL matching events from previous layers
                for dep_id in current_node.dep_ids:
                    # Search all previous layers for events matching this dep_id
                    for prev_layer_index in range(layer_index):
                        prev_layer_event_ids = matched["layers"][prev_layer_index]
                        for prev_event_id in prev_layer_event_ids:
                            prev_event = matched["events"][prev_event_id]
                            if prev_event.node_id == dep_id:
                                # Add to upstream_ev_ids
                                upstream_ev_ids.append(prev_event_id)
                                # Add this event to deps
                                dep_data: DepData = {
                                    "flow": prev_event.flow,
                                    "id": prev_event.node_id,
                                    "data": prev_event.data,
                                }
                                ctx["deps"].append(dep_data)

            # Validate each event for this node
            status: str = "running"
            error: str | None = None
            message: str | None = None

            for current_ev in current_node_events:
                if status == "failed":
                    break

                # Call validator if present
                if current_node.validator and evaluator:
                    validator_passed = evaluator.evaluate(
                        current_node.validator,
                        data=current_ev.data,
                        ctx=cast(dict[str, Any], ctx),
                    )
                    if not validator_passed:
                        error = "Validator assertion failed"
                        status = "failed"
                        overall_status = "failed"
                        break
                    else:
                        message = "Validator passed"
                        status = "passed"

                # Check timeout conditions if present
                if current_node.conditions:
                    for cond in current_node.conditions:
                        if not cond.timeout_ms:
                            continue

                        # Check timeout against all upstream events
                        if ctx["deps"]:
                            # Find the most recent upstream event
                            max_upstream_ts = max(
                                matched["events"][ev_id].ts
                                for ev_id in upstream_ev_ids
                                if ev_id in matched["events"]
                            )
                            time_diff_ms = (current_ev.ts - max_upstream_ts) / 1_000_000

                            if time_diff_ms > cond.timeout_ms:
                                error = append_text(
                                    f"Timeout exceeded: {time_diff_ms}ms > {cond.timeout_ms}ms",
                                    error,
                                    "\n",
                                )
                                status = "failed"
                                overall_status = "failed"
                            else:
                                if not message:
                                    message = f"Timeout satisfied: {time_diff_ms}ms <= {cond.timeout_ms}ms"
                                if status == "running":
                                    status = "passed"

            # If no validator and no conditions, mark as passed
            if status == "running":
                if current_node.dep_ids and not ctx["deps"]:
                    message = "No upstream events found for dependencies"
                    status = "failed"
                    overall_status = "failed"
                else:
                    message = "Node validation passed"
                    status = "passed"

            items.append(
                ValidationItem(
                    node_id=node_id,
                    dep_node_ids=current_node.dep_ids or [],
                    status=status,  # type: ignore
                    message=message,
                    error=error,
                    elapsed_ns=time_ns() - item_start,
                    ev_ids=[ev.id for ev in current_node_events],
                    upstream_ev_ids=upstream_ev_ids,
                )
            )

    # Determine overall status
    if overall_status != "failed":
        # Check if any nodes are still running
        has_running = any(item["status"] == "running" for item in items)
        if has_running:
            overall_status = "running"
        else:
            overall_status = "passed"

    return ValidationResult(
        status=overall_status,  # type: ignore
        items=items,
        elapsed_ns=time_ns() - start_time,
        graph=graph,
        ev_ids=all_ev_ids,
    )
