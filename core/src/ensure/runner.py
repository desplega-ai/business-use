"""Ensure runner for executing flows from trigger to completion."""

import asyncio
import logging
import time
from typing import Any
from uuid import uuid4

from src.db.transactional import transactional
from src.ensure.validator import get_flow_trigger_node
from src.eval import eval_flow_run
from src.models import BaseEvalOutput, EvalOutput, EvalStatus, Event
from src.triggers import execute_trigger, extract_run_id
from src.utils.time import now

log = logging.getLogger(__name__)


async def run_flow_ensure(
    flow_name: str,
    polling_interval_ms: int = 2000,
    max_timeout_ms: int = 30000,
    display: Any | None = None,
) -> tuple[str, BaseEvalOutput]:
    """Run flow from trigger to completion.

    Execution steps:
    1. Load & validate trigger node (root only, exactly one)
    2. Execute trigger (HTTP request or command)
    3. Extract run_id from trigger response
    4. Poll eval_flow_run() until passed/failed/timeout

    Args:
        flow_name: Name of flow to run
        polling_interval_ms: Polling interval in milliseconds (default: 2000)
        max_timeout_ms: Maximum timeout in milliseconds (default: 30000)
        display: Optional display object for live updates (LiveDisplay or StructuredLogger)

    Returns:
        Tuple of (flow_name, BaseEvalOutput)

    Raises:
        ValueError: If validation fails or trigger execution fails
    """
    # Only log in non-live mode
    is_live_mode = display and hasattr(display, "update_progress")

    if not is_live_mode:
        log.info(f"Starting ensure for flow: {flow_name}")
    start_time = time.time()

    # Step 1: Get and validate trigger node
    trigger_node = await get_flow_trigger_node(flow_name)
    if not is_live_mode:
        log.info(f"Found trigger node: {trigger_node.id}")

    # Step 2: Execute trigger
    if not is_live_mode:
        log.info(f"Executing trigger: {trigger_node.handler}")
    context = await execute_trigger(trigger_node)

    # Step 3: Extract run_id
    if not trigger_node.handler_input or not trigger_node.handler_input.params:
        raise ValueError(f"Trigger node '{trigger_node.id}' missing handler_input")

    extractor = trigger_node.handler_input.params.run_id_extractor
    if not extractor:
        raise ValueError(f"Trigger node '{trigger_node.id}' missing run_id_extractor")

    run_id = extract_run_id(context, extractor)
    if not is_live_mode:
        log.info(f"Extracted run_id: {run_id}")

    # Step 3.5: Persist trigger event to database
    # The trigger node itself needs to exist as an event so evaluation can find it
    trigger_event = Event(
        id=str(uuid4()),
        flow=flow_name,
        node_id=trigger_node.id,
        run_id=run_id,
        type=trigger_node.type,
        data=context["output"],  # Store the trigger response as event data
        ts=int(time.time() * 1_000_000_000),  # Current time in nanoseconds
    )

    async with transactional() as session:
        session.add(trigger_event)
        await session.commit()

    if not is_live_mode:
        log.info(f"Persisted trigger event: {trigger_event.id}")

    # Step 4: Poll evaluation until completion
    polling_interval_s = polling_interval_ms / 1000.0
    max_timeout_s = max_timeout_ms / 1000.0
    timeout_at = time.time() + max_timeout_s

    result: BaseEvalOutput | None = None
    last_status: EvalStatus = "pending"

    while time.time() < timeout_at:
        try:
            # Run evaluation
            result = await eval_flow_run(
                run_id=run_id,
                flow=flow_name,
            )

            # Check if flow is complete
            if result.status in ["passed", "failed", "error", "cancelled"]:
                # Print newline to finish the live update line
                if display and hasattr(display, "update_progress"):
                    import click

                    click.echo()  # Move to next line after live updates
                else:
                    log.info(f"Flow completed with status: {result.status}")
                break

            # Log status changes (only when not in live mode)
            if result.status != last_status:
                if not (display and hasattr(display, "update_progress")):
                    log.debug(f"Flow status changed: {last_status} → {result.status}")
                last_status = result.status

            # Update live display if provided
            if display and hasattr(display, "update_progress"):
                elapsed_s = time.time() - start_time
                # Extract a meaningful message from exec_info if available
                message = None
                if result.exec_info:
                    # Find a running node to show its message
                    for item in result.exec_info:
                        if item.status == "running":
                            message = item.message
                            break
                display.update_progress(flow_name, result.status, elapsed_s, message)

            # Wait before next poll
            await asyncio.sleep(polling_interval_s)

        except Exception as e:
            log.error(f"Error during evaluation poll: {e}", exc_info=True)
            # Create error result
            elapsed_ns = int((time.time() - start_time) * 1_000_000_000)
            result = BaseEvalOutput(
                status="error",
                elapsed_ns=elapsed_ns,
                graph={},
                exec_info=[],
                ev_ids=[],
            )
            break

    # Check for timeout
    if result is None or (
        time.time() >= timeout_at and result.status not in ["passed", "failed"]
    ):
        if not is_live_mode:
            log.warning(f"Flow timed out after {max_timeout_ms}ms")
        elapsed_ns = int((time.time() - start_time) * 1_000_000_000)
        result = BaseEvalOutput(
            status="timed_out",
            elapsed_ns=elapsed_ns,
            graph={},
            exec_info=[],
            ev_ids=[],
        )

    # Step 5: Persist evaluation result to database
    eval_output = EvalOutput(
        id=str(uuid4()),
        flow=flow_name,
        run_id=run_id,
        trigger_ev_id=trigger_event.id,
        output=result,
        created_at=now(),
    )

    async with transactional() as session:
        session.add(eval_output)
        await session.commit()

    if not is_live_mode:
        log.info(
            f"Persisted evaluation result: {eval_output.id} (status: {result.status})"
        )

    return (flow_name, result)


async def run_flows_parallel(
    flows: list[str],
    concurrency: int,
    polling_interval_ms: int = 2000,
    max_timeout_ms: int = 30000,
    display: Any | None = None,
) -> list[tuple[str, BaseEvalOutput]]:
    """Run multiple flows in parallel with controlled concurrency.

    Uses asyncio.Semaphore for concurrency control.

    Args:
        flows: List of flow names to run
        concurrency: Maximum number of concurrent flows
        polling_interval_ms: Polling interval for each flow
        max_timeout_ms: Max timeout for each flow
        display: Optional display object for live updates

    Returns:
        List of (flow_name, BaseEvalOutput) tuples

    Example:
        >>> results = await run_flows_parallel(
        ...     flows=["payment", "checkout", "signup"],
        ...     concurrency=2,
        ... )
        >>> for flow_name, output in results:
        ...     print(f"{flow_name}: {output.status}")
    """
    if concurrency < 1:
        concurrency = 1

    log.info(f"Running {len(flows)} flows with concurrency={concurrency}")

    # Create semaphore for concurrency control
    sem = asyncio.Semaphore(concurrency)

    async def run_with_sem(flow: str) -> tuple[str, BaseEvalOutput]:
        """Run flow with semaphore."""
        async with sem:
            return await run_flow_ensure(
                flow, polling_interval_ms, max_timeout_ms, display
            )

    # Run all flows concurrently (limited by semaphore)
    tasks = [run_with_sem(flow) for flow in flows]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle exceptions
    final_results: list[tuple[str, BaseEvalOutput]] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            flow_name = flows[i]
            log.error(f"Flow '{flow_name}' failed with exception: {result}")
            # Create error result
            error_output = BaseEvalOutput(
                status="error",
                elapsed_ns=0,
                graph={},
                exec_info=[],
                ev_ids=[],
            )
            final_results.append((flow_name, error_output))

        else:
            # mypy doesn't know that non-Exception results are tuples
            final_results.append(result)  # type: ignore[arg-type]

    return final_results
