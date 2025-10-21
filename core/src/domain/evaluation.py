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

    This is the NEW implementation that uses run_id + flow tuple instead
    of time-window heuristics.

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
    final_ev_list: list[list[str]] = []
    events_map: dict[str, Event] = {ev.id: ev for ev in events}

    # For each layer, find matching events
    for layer_index, layer_node_ids in enumerate(layers):
        layer_event_ids: list[str] = []

        for node_id in layer_node_ids:
            current_node = nodes_map.get(node_id)
            if current_node is None:
                continue

            current_node = current_node
            current_node.ensure()  # Ensure node is properly initialized

            # Find events for this node
            for event in events:
                if event.node_id != node_id:
                    continue

                # If no filter, include the event
                if not current_node.filter:
                    layer_event_ids.append(event.id)
                    continue

                # If filter exists, evaluate it against upstream events
                # Find the last layer with events (upstream)
                upstream_events: list[Event] = []
                for prev_layer_index in range(layer_index - 1, -1, -1):
                    if final_ev_list[prev_layer_index]:
                        upstream_event_ids = final_ev_list[prev_layer_index]
                        upstream_events = [
                            events_map[ev_id] for ev_id in upstream_event_ids
                        ]
                        break

                # Evaluate filter for each upstream event
                for upstream_ev in upstream_events:
                    if evaluator.evaluate(
                        current_node.filter,
                        data=event.data,
                        ctx=upstream_ev.data,
                    ):
                        layer_event_ids.append(event.id)
                        break  # Only add event once even if multiple upstream match

        final_ev_list.append(layer_event_ids)

    return LayeredEvents(
        layers=final_ev_list,
        events=events_map,
    )


def validate_flow_execution(
    matched: LayeredEvents,
    nodes_map: dict[str, Node],
    layers: list[list[str]],
) -> ValidationResult:
    """Validate that flow execution followed the expected graph.

    Checks:
    - All required nodes have events
    - Dependencies are satisfied
    - Timeout conditions are met
    - Validators pass (future)

    Args:
        matched: Events matched to layers
        nodes_map: Map of node_id -> Node
        layers: Topologically sorted layers of node IDs

    Returns:
        ValidationResult with status and detailed items
    """
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

        # Get upstream event IDs
        upstream_ev_ids: list[str] = []
        for prev_index in range(layer_index - 1, -1, -1):
            if matched["layers"][prev_index]:
                upstream_ev_ids = matched["layers"][prev_index]
                break

        # Get upstream events
        upstream_events: list[Event] = [
            matched["events"][ev_id] for ev_id in upstream_ev_ids
        ]

        for node_id in layer_node_ids:
            current_node = nodes_map.get(node_id)
            if current_node is None:
                continue

            current_node = current_node
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
                        upstream_ev_ids=upstream_ev_ids,
                    )
                )
                continue

            item_start = time_ns()

            # Check if upstream events exist (for non-first layers)
            if len(upstream_events) == 0:
                if layer_index == 0:
                    # First layer, no upstream needed
                    items.append(
                        ValidationItem(
                            node_id=node_id,
                            dep_node_ids=[],
                            message="Root node, no upstream dependencies",
                            status="passed",
                            elapsed_ns=time_ns() - item_start,
                            ev_ids=layer_ev_ids,
                            upstream_ev_ids=[],
                        )
                    )
                else:
                    # Non-first layer should have upstream
                    items.append(
                        ValidationItem(
                            node_id=node_id,
                            dep_node_ids=current_node.dep_ids or [],
                            message="No upstream events found for non-root node",
                            status="failed",
                            elapsed_ns=time_ns() - item_start,
                            ev_ids=layer_ev_ids,
                            upstream_ev_ids=[],
                        )
                    )
                    overall_status = "failed"
                continue

            # No dependencies = first layer, all good
            if len(current_node.dep_ids or []) == 0:
                items.append(
                    ValidationItem(
                        node_id=node_id,
                        dep_node_ids=[],
                        message=f"Node {current_node.id} has no dependencies",
                        status="passed",
                        elapsed_ns=time_ns() - item_start,
                        ev_ids=layer_ev_ids,
                        upstream_ev_ids=upstream_ev_ids,
                    )
                )
                continue

            # Validate conditions (timeouts, etc)
            status: str = "running"
            error: str | None = None
            message: str | None = None
            some_found = False

            # Get current layer events for this node
            current_node_events = [
                matched["events"][ev_id]
                for ev_id in layer_ev_ids
                if matched["events"][ev_id].node_id == node_id
            ]

            for current_ev in current_node_events:
                if status == "failed":
                    break

                for upstream_ev in upstream_events:
                    if status == "failed":
                        break

                    some_found = True

                    # Check conditions (timeout)
                    if len(current_node.conditions) == 0:
                        status = "passed"
                        message = (
                            f"Dependency found for {current_node.id}, no conditions"
                        )
                        continue

                    for cond in node.conditions:
                        if not cond.timeout_ms:
                            continue

                        time_diff_ms = (current_ev.ts - upstream_ev.ts) / 1_000_000

                        if time_diff_ms > cond.timeout_ms:
                            error = append_text(
                                f"Timeout exceeded: {time_diff_ms}ms > {cond.timeout_ms}ms",
                                error,
                                "\n",
                            )
                            status = "failed"
                        else:
                            message = f"Timeout satisfied: {time_diff_ms}ms <= {cond.timeout_ms}ms"
                            status = "passed"

            if not some_found:
                message = "No matching dependency events found"
                status = "skipped"

            if status == "running":
                message = "All conditions passed"
                status = "passed"

            if status == "failed":
                overall_status = "failed"

            items.append(
                ValidationItem(
                    node_id=node_id,
                    dep_node_ids=current_node.dep_ids or [],
                    status=status,  # type: ignore
                    message=message,
                    error=error,
                    elapsed_ns=time_ns() - item_start,
                    ev_ids=layer_ev_ids,
                    upstream_ev_ids=upstream_ev_ids,
                )
            )

    # Determine overall status
    if overall_status != "failed":
        overall_status = "passed"

    return ValidationResult(
        status=overall_status,  # type: ignore
        items=items,
        elapsed_ns=time_ns() - start_time,
        graph=graph,
        ev_ids=all_ev_ids,
    )
