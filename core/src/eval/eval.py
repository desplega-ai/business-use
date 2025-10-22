"""Flow evaluation orchestration.

This module orchestrates the evaluation of flow execution by combining:
- Domain logic (graph building, validation)
- Execution logic (expression evaluation)
- Storage adapters (SQLite)

The architecture is designed to be pluggable - the core domain logic can
be reused with different storage backends and evaluators at desplega.ai.
"""

import logging

from src.adapters.sqlite import SqliteEventStorage
from src.db.transactional import transactional
from src.domain.evaluation import match_events_to_layers, validate_flow_execution
from src.domain.graph import (
    build_flow_graph,
    filter_subgraph_from_node,
    topological_sort_layers,
)
from src.execution.python_eval import PythonEvaluator
from src.models import BaseEvalOutput

logger = logging.getLogger(__name__)


async def eval_flow_run(
    run_id: str,
    flow: str,
    start_node_id: str | None = None,
) -> BaseEvalOutput:
    """Evaluate flow execution for a specific run.

    This is the NEW implementation that uses run_id + flow tuple instead
    of event ID + time-window heuristics.

    Args:
        run_id: The run identifier (e.g., user session, order ID)
        flow: The flow identifier (e.g., "checkout", "onboarding")
        start_node_id: Optional node to start evaluation from (subgraph only)

    Returns:
        BaseEvalOutput with evaluation results

    Raises:
        ValueError: If flow not found or no events for run

    Example:
        >>> result = await eval_flow_run("run_123", "checkout")
        >>> result.status
        "passed"
    """
    logger.info(f"Evaluating flow run: run_id={run_id}, flow={flow}")

    # 1. Fetch data from storage (adapter layer)
    storage = SqliteEventStorage()

    async with transactional() as session:
        # Fetch all events for this run + flow
        events = await storage.get_events_by_run(run_id, flow, session)

        # Fetch all node definitions for this flow
        nodes = await storage.get_nodes_by_flow(flow, session)

    if not events:
        raise ValueError(f"No events found for run_id={run_id}, flow={flow}")

    if not nodes:
        raise ValueError(f"No node definitions found for flow={flow}")

    logger.info(f"Found {len(events)} events and {len(nodes)} nodes for evaluation")

    # 2. Build flow graph (domain layer)
    flow_graph = build_flow_graph(nodes)

    # 3. Optionally filter to subgraph (domain layer)
    if start_node_id:
        logger.info(f"Filtering to subgraph starting from node: {start_node_id}")
        flow_graph = filter_subgraph_from_node(flow_graph, start_node_id)

    # 4. Topological sort (domain layer)
    layers = topological_sort_layers(flow_graph["graph"])
    logger.info(f"Graph has {len(layers)} layers and {len(events)} raw events")

    # 5. Match events to layers (domain + execution layers)
    evaluator = PythonEvaluator()
    matched = match_events_to_layers(
        events=events,
        layers=layers,
        nodes_map=flow_graph["nodes"],
        evaluator=evaluator,
    )

    logger.info(
        f"Matched {len(matched['events'])} events for {len(matched['layers'])} layers"
    )

    # 6. Validate flow execution (domain layer)
    result = validate_flow_execution(
        matched=matched,
        nodes_map=flow_graph["nodes"],
        layers=layers,
        evaluator=evaluator,
    )

    # 7. Convert to output model
    return BaseEvalOutput(
        status=result["status"],
        elapsed_ns=result["elapsed_ns"],
        graph=result["graph"],
        exec_info=result["items"],  # type: ignore
        ev_ids=result["ev_ids"],
    )
