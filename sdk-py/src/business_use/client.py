"""Main client module for Business-Use SDK."""

import inspect
import logging
import os
import threading
from collections.abc import Callable
from typing import Any

import httpx

from .batch import BatchProcessor
from .models import Ctx, NodeCondition, NodeType, QueuedEvent

logger = logging.getLogger("business-use")


class _SDKState:
    """Internal SDK state (singleton pattern)."""

    def __init__(self):
        self.initialized = False
        self.batch_processor: BatchProcessor | None = None
        self.lock = threading.Lock()


# Global SDK state
_state = _SDKState()


def initialize(
    api_key: str | None = None,
    url: str | None = None,
    batch_size: int = 100,
    batch_interval: int = 5,
    max_queue_size: int | None = None,
) -> None:
    """Initialize the Business-Use SDK.

    This function must be called before using `ensure()`.
    It validates the connection to the backend and starts the background
    batch processor.

    This function never raises exceptions. Errors are logged internally.
    If initialization fails, the SDK enters no-op mode.

    Args:
        api_key: API key for authentication (default: from BUSINESS_USE_API_KEY env var)
        url: Backend API URL (default: from BUSINESS_USE_URL env var or http://localhost:13370)
        batch_size: Number of events per batch (default: 100)
        batch_interval: Flush interval in seconds (default: 5)
        max_queue_size: Max queue size (default: batch_size * 10)

    Example:
        >>> from business_use import initialize, ensure
        >>> initialize(api_key="your-api-key")
        >>> ensure(id="user_signup", flow="onboarding", run_id="123", data={"email": "user@example.com"})

        Or using environment variables:
        >>> # Set BUSINESS_USE_API_KEY=your-api-key in environment
        >>> initialize()  # Will use env vars
    """
    with _state.lock:
        if _state.initialized:
            logger.warning("SDK already initialized")
            return

        try:
            # Get API key from parameter or environment
            final_api_key = api_key or os.getenv("BUSINESS_USE_API_KEY")
            if not final_api_key:
                logger.error(
                    "API key not provided. Set api_key parameter or BUSINESS_USE_API_KEY environment variable"
                )
                return

            # Get URL from parameter or environment
            final_url = url or os.getenv("BUSINESS_USE_URL") or "http://localhost:13370"

            # Normalize URL
            base_url = final_url.rstrip("/")

            # Validate connection
            if not _check_connection(final_api_key, base_url):
                logger.error("Connection check failed - SDK entering no-op mode")
                return

            # Calculate max queue size
            if max_queue_size is None:
                max_queue_size = batch_size * 10

            # Start batch processor
            _state.batch_processor = BatchProcessor(
                api_key=final_api_key,
                base_url=base_url,
                batch_size=batch_size,
                batch_interval=batch_interval,
                max_queue_size=max_queue_size,
            )

            _state.initialized = True
            logger.info("Business-Use SDK initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize SDK: {e}")
            _state.initialized = False


def ensure(
    id: str,
    flow: str,
    run_id: str | Callable[[], str],
    data: dict[str, Any],
    filter: bool | Callable[[dict[str, Any], Ctx], bool] | None = None,
    dep_ids: list[str] | Callable[[], list[str]] | None = None,
    validator: Callable[[dict[str, Any], Ctx], bool] | None = None,
    description: str | None = None,
    conditions: list[NodeCondition] | Callable[[], list[NodeCondition]] | None = None,
    additional_meta: dict[str, Any] | None = None,
) -> None:
    """Track a business event. Type is auto-determined by validator presence.

    This function is synchronous and non-blocking. Events are queued and
    sent in batches to the backend.

    The event type is automatically determined:
    - If `validator` is provided: creates an "assert" node
    - If `validator` is None: creates an "act" node

    This function never raises exceptions. If the SDK is not initialized,
    this is a no-op.

    Args:
        id: Unique node/event identifier (e.g., "payment_processed")
        flow: Flow identifier (e.g., "checkout")
        run_id: Run identifier (string or lambda returning string)
        data: Event data payload
        filter: Optional filter function (data, ctx) -> bool. Evaluated on backend.
        dep_ids: Optional dependency node IDs (list or lambda)
        validator: Optional validation function (data, ctx) -> bool. Executed on backend. If provided, creates "assert" node.
        description: Optional human-readable description
        conditions: Optional list of conditions (e.g., timeout constraints)
        additional_meta: Optional additional metadata dict

    Example:
        >>> # Action node (no validator)
        >>> ensure(
        ...     id="payment_processed",
        ...     flow="checkout",
        ...     run_id="run_12345",
        ...     data={"amount": 100, "currency": "USD"},
        ...     dep_ids=["cart_created", "payment_initiated"],
        ...     description="Payment processed successfully"
        ... )

        >>> # Assertion node (with validator accessing upstream deps)
        >>> def validate_order_total(data, ctx):
        ...     # ctx.deps contains all upstream dependency events
        ...     return data["total"] == sum(dep["data"]["price"] for dep in ctx["deps"])
        ...
        >>> ensure(
        ...     id="order_total_matches",
        ...     flow="checkout",
        ...     run_id="run_12345",
        ...     data={"total": 150},
        ...     validator=validate_order_total,
        ...     dep_ids=["item_added"],
        ...     description="Order total matches sum of items"
        ... )

        Using filter with upstream context:
        >>> from business_use import NodeCondition
        >>> def check_approved(data, ctx):
        ...     # Filter based on upstream event data
        ...     return all(dep["data"].get("status") == "approved" for dep in ctx["deps"])
        ...
        >>> ensure(
        ...     id="order_completed",
        ...     flow="checkout",
        ...     run_id=lambda: get_current_run_id(),
        ...     data={"order_id": order.id},
        ...     filter=check_approved,
        ...     dep_ids=["payment_processed", "inventory_reserved"],
        ...     conditions=[NodeCondition(timeout_ms=5000)],
        ...     additional_meta={"source": "api"}
        ... )
    """
    _enqueue_event(
        type="assert" if validator else "act",
        id=id,
        flow=flow,
        run_id=run_id,
        data=data,
        filter=filter,
        dep_ids=dep_ids,
        description=description,
        validator=validator,
        conditions=conditions,
        additional_meta=additional_meta,
    )


def shutdown(timeout: float = 5.0) -> None:
    """Gracefully shutdown the SDK.

    Attempts to flush all remaining events before stopping.
    This is optional - the SDK will auto-shutdown when the program exits.

    Args:
        timeout: Maximum time to wait for shutdown in seconds (default: 5.0)

    Example:
        >>> shutdown()
    """
    with _state.lock:
        if not _state.initialized:
            logger.debug("SDK not initialized, nothing to shutdown")
            return

        if _state.batch_processor:
            _state.batch_processor.shutdown(timeout=timeout)

        _state.initialized = False
        _state.batch_processor = None
        logger.info("SDK shutdown complete")


def act(
    id: str,
    flow: str,
    run_id: str | Callable[[], str],
    data: dict[str, Any],
    *,
    filter: bool | Callable[[dict[str, Any], Ctx], bool] | None = None,
    dep_ids: list[str] | Callable[[], list[str]] | None = None,
    description: str | None = None,
    conditions: list[NodeCondition] | Callable[[], list[NodeCondition]] | None = None,
    additional_meta: dict[str, Any] | None = None,
) -> None:
    """Helper function to track an action (event without validator).

    This is a convenience wrapper around `ensure()` without a validator.

    Args:
        id: Unique identifier for this event
        flow: Flow identifier
        run_id: Run identifier or lambda that returns one
        data: Event data payload
        filter: Optional filter function (data, ctx) -> bool. Evaluated on backend.
        dep_ids: Optional list of dependency IDs or lambda that returns them
        description: Optional human-readable description
        conditions: Optional list of conditions or lambda that returns them
        additional_meta: Optional additional metadata

    Example:
        >>> act(
        ...     id="payment_processed",
        ...     flow="checkout",
        ...     run_id="run_123",
        ...     data={"amount": 100, "currency": "USD"}
        ... )
    """
    ensure(
        id=id,
        flow=flow,
        run_id=run_id,
        data=data,
        filter=filter,
        dep_ids=dep_ids,
        description=description,
        conditions=conditions,
        additional_meta=additional_meta,
    )


def assert_(
    id: str,
    flow: str,
    run_id: str | Callable[[], str],
    data: dict[str, Any],
    *,
    validator: Callable[[dict[str, Any], Ctx], bool] | None = None,
    filter: bool | Callable[[dict[str, Any], Ctx], bool] | None = None,
    dep_ids: list[str] | Callable[[], list[str]] | None = None,
    description: str | None = None,
    conditions: list[NodeCondition] | Callable[[], list[NodeCondition]] | None = None,
    additional_meta: dict[str, Any] | None = None,
) -> None:
    """Helper function to track an assertion (event with validator).

    This is a convenience wrapper around `ensure()` with a validator.
    Named `assert_` to avoid conflict with Python's built-in `assert` keyword.

    Args:
        id: Unique identifier for this event
        flow: Flow identifier
        run_id: Run identifier or lambda that returns one
        data: Event data payload
        validator: Optional validation function (data, ctx) -> bool. Executed on backend.
        filter: Optional filter function (data, ctx) -> bool. Evaluated on backend.
        dep_ids: Optional list of dependency IDs or lambda that returns them
        description: Optional human-readable description
        conditions: Optional list of conditions or lambda that returns them
        additional_meta: Optional additional metadata

    Example:
        >>> def validate_total(data, ctx):
        ...     # Access upstream events via ctx.deps
        ...     return data["total"] > 0 and len(ctx["deps"]) > 0
        >>>
        >>> assert_(
        ...     id="order_total_valid",
        ...     flow="checkout",
        ...     run_id="run_123",
        ...     data={"total": 150},
        ...     validator=validate_total,
        ...     dep_ids=["cart_created"]
        ... )
    """
    ensure(
        id=id,
        flow=flow,
        run_id=run_id,
        data=data,
        validator=validator,
        filter=filter,
        dep_ids=dep_ids,
        description=description,
        conditions=conditions,
        additional_meta=additional_meta,
    )


def _enqueue_event(
    type: NodeType,
    id: str,
    flow: str,
    run_id: str | Callable[[], str],
    data: dict[str, Any],
    filter: bool | Callable[[dict[str, Any], Ctx], bool] | None,
    dep_ids: list[str] | Callable[[], list[str]] | None,
    description: str | None,
    validator: Callable[[dict[str, Any], Ctx], bool] | None,
    conditions: list[NodeCondition] | Callable[[], list[NodeCondition]] | None,
    additional_meta: dict[str, Any] | None,
) -> None:
    """Internal helper to enqueue an event.

    Args:
        type: Event type (act or assert)
        id: Event ID
        flow: Flow identifier
        run_id: Run ID or lambda
        data: Event data
        filter: Filter function (data, ctx) -> bool. Evaluated on backend.
        dep_ids: Dependencies or lambda
        description: Optional description
        validator: Optional validator function (data, ctx) -> bool. Executed on backend.
        conditions: Optional conditions or lambda
        additional_meta: Optional additional metadata
    """
    # No-op if not initialized
    if not _state.initialized or _state.batch_processor is None:
        return

    try:
        # Validate that no async functions are used
        if callable(run_id) and inspect.iscoroutinefunction(run_id):
            logger.error(f"Event {id}: run_id cannot be an async function")
            return

        if callable(filter) and inspect.iscoroutinefunction(filter):
            logger.error(f"Event {id}: filter cannot be an async function")
            return

        if callable(dep_ids) and inspect.iscoroutinefunction(dep_ids):
            logger.error(f"Event {id}: dep_ids cannot be an async function")
            return

        if validator is not None and inspect.iscoroutinefunction(validator):
            logger.error(f"Event {id}: validator cannot be an async function")
            return

        if callable(conditions) and inspect.iscoroutinefunction(conditions):
            logger.error(f"Event {id}: conditions cannot be an async function")
            return

        event = QueuedEvent(
            type=type,
            id=id,
            flow=flow,
            run_id=run_id,
            data=data,
            filter=filter,
            dep_ids=dep_ids,
            description=description,
            validator=validator,
            conditions=conditions,
            additional_meta=additional_meta,
        )

        _state.batch_processor.enqueue(event)

    except Exception as e:
        logger.error(f"Failed to enqueue event {id}: {e}")


def _check_connection(api_key: str, base_url: str) -> bool:
    """Validate connection to backend API.

    Args:
        api_key: API key for authentication
        base_url: Backend API URL

    Returns:
        True if connection is valid, False otherwise
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{base_url}/v1/check",
                headers={"X-Api-Key": api_key},
            )

            if response.status_code == 200:
                logger.info("Connection check successful")
                return True
            else:
                logger.error(
                    f"Connection check failed: HTTP {response.status_code} - {response.text}"
                )
                return False

    except httpx.TimeoutException:
        logger.error("Connection check timed out")
        return False
    except httpx.RequestError as e:
        logger.error(f"Connection check failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during connection check: {e}")
        return False
