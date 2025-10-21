"""Background batch processor for event ingestion."""

import inspect
import logging
import queue
import threading
import time
from typing import Any

import httpx

from .models import EventBatchItem, Expr, QueuedEvent

logger = logging.getLogger("business-use")


class BatchProcessor:
    """Manages background batching and sending of events to the backend API."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        batch_size: int,
        batch_interval: int,
        max_queue_size: int,
    ):
        """Initialize the batch processor.

        Args:
            api_key: API key for authentication
            base_url: Backend API base URL
            batch_size: Number of events to batch before sending
            batch_interval: Time in seconds between flushes
            max_queue_size: Maximum queue size before dropping old events
        """
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._batch_size = batch_size
        self._batch_interval = batch_interval
        self._max_queue_size = max_queue_size

        # Thread-safe queue for events
        self._queue: queue.Queue[QueuedEvent] = queue.Queue(maxsize=max_queue_size)

        # Shutdown coordination
        self._shutdown_event = threading.Event()

        # Worker thread
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="BusinessUseWorker",
            daemon=True,
        )
        self._worker_thread.start()

        logger.debug("Batch processor started")

    def enqueue(self, event: QueuedEvent) -> None:
        """Add an event to the processing queue.

        If the queue is full, the oldest event is dropped.
        This method never raises exceptions.

        Args:
            event: The event to enqueue
        """
        try:
            # Try to add to queue without blocking
            self._queue.put_nowait(event)
        except queue.Full:
            # Queue is full - drop oldest event and try again
            try:
                self._queue.get_nowait()  # Remove oldest
                logger.warning("Queue overflow: Dropped oldest event")
                self._queue.put_nowait(event)  # Add new event
            except Exception as e:
                logger.error(f"Failed to enqueue event: {e}")

    def shutdown(self, timeout: float = 5.0) -> None:
        """Gracefully shutdown the batch processor.

        Attempts to flush all remaining events before stopping.

        Args:
            timeout: Maximum time to wait for shutdown in seconds
        """
        logger.debug("Shutting down batch processor")
        self._shutdown_event.set()
        self._worker_thread.join(timeout=timeout)

        if self._worker_thread.is_alive():
            logger.warning("Batch processor shutdown timed out")
        else:
            logger.debug("Batch processor shutdown complete")

    def _worker_loop(self) -> None:
        """Background worker thread that processes batches.

        Runs until shutdown event is set. Flushes batches based on:
        - Size threshold (batch_size events)
        - Time threshold (batch_interval seconds)
        """
        batch: list[QueuedEvent] = []
        last_flush_time = time.time()

        while not self._shutdown_event.is_set():
            # Wait for events with timeout for responsiveness
            try:
                event = self._queue.get(timeout=0.1)
                batch.append(event)
            except queue.Empty:
                pass

            # Check flush conditions
            time_elapsed = time.time() - last_flush_time
            should_flush_size = len(batch) >= self._batch_size
            should_flush_time = time_elapsed >= self._batch_interval

            if batch and (should_flush_size or should_flush_time):
                self._send_batch(batch)
                batch.clear()
                last_flush_time = time.time()

        # Final flush on shutdown
        if batch:
            logger.debug("Flushing remaining events on shutdown")
            self._send_batch(batch)

    def _send_batch(self, batch: list[QueuedEvent]) -> None:
        """Process and send a batch of events to the backend.

        Args:
            batch: List of queued events to process
        """
        try:
            # Transform queued events to API format
            items: list[EventBatchItem] = []

            for event in batch:
                try:
                    # Evaluate filter first - skip if False (client-side filtering)
                    if event.filter is not None:
                        if callable(event.filter):
                            if not event.filter():
                                logger.debug(f"Event {event.id} filtered out")
                                continue
                        elif not event.filter:
                            logger.debug(f"Event {event.id} filtered out")
                            continue

                    # Evaluate lambdas
                    run_id = event.run_id() if callable(event.run_id) else event.run_id
                    dep_ids = (
                        event.dep_ids() if callable(event.dep_ids) else event.dep_ids
                    )
                    conditions = (
                        event.conditions()
                        if callable(event.conditions)
                        else event.conditions
                    )

                    # Serialize filter if present and callable (send to backend)
                    filter_expr = None
                    if event.filter is not None and callable(event.filter):
                        filter_expr = self._serialize_lambda(event.filter)

                    # Serialize validator if present
                    validator_expr = None
                    if event.validator is not None:
                        validator_expr = self._serialize_lambda(event.validator)

                    # Create batch item
                    item = EventBatchItem(
                        flow=event.flow,
                        id=event.id,
                        run_id=run_id,
                        type=event.type,
                        data=event.data,
                        ts=int(time.time_ns()),
                        description=event.description,
                        dep_ids=dep_ids,
                        filter=filter_expr,
                        validator=validator_expr,
                        conditions=conditions,
                        additional_meta=event.additional_meta,
                    )
                    items.append(item)

                except Exception as e:
                    logger.error(f"Failed to process event {event.id}: {e}")
                    continue

            if not items:
                logger.debug("No events to send after filtering")
                return

            # Send to backend
            self._post_batch(items)

        except Exception as e:
            logger.error(f"Failed to send batch: {e}")

    def _post_batch(self, items: list[EventBatchItem]) -> None:
        """POST batch to backend API.

        Args:
            items: List of events to send
        """
        try:
            # Convert to JSON
            payload = [item.model_dump(exclude_none=True) for item in items]

            # Send request
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self._base_url}/v1/events-batch",
                    json=payload,
                    headers={"X-Api-Key": self._api_key},
                )

                if response.status_code == 200:
                    logger.debug(f"Batch sent successfully: {len(items)} events")
                else:
                    logger.error(
                        f"Batch send failed: HTTP {response.status_code} - {response.text}"
                    )

        except httpx.TimeoutException:
            logger.error("Batch send timed out")
        except httpx.RequestError as e:
            logger.error(f"Network error sending batch: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending batch: {e}")

    def _serialize_lambda(self, fn: Any) -> Expr:
        """Serialize a lambda/function to an Expr.

        Extracts just the function body/expression for easier backend execution.

        For lambdas: Extracts the expression after ':'
        For functions: Extracts the return statement or function body

        Args:
            fn: Function to serialize

        Returns:
            Expr object with Python engine and extracted body
        """
        try:
            source = inspect.getsource(fn).strip()

            # Handle lambda expressions
            if "lambda" in source:
                # Extract the expression after the colon
                # e.g., "lambda data, ctx: data['amount'] > 0" -> "data['amount'] > 0"
                if ":" in source:
                    # Get everything after the last colon (the lambda body)
                    body = source.split(":", 1)[1].strip()
                    # Remove trailing comma or parenthesis if present
                    body = body.rstrip(",).;")
                    return Expr(engine="python", script=body)
                # Fallback if no colon found in lambda
                return Expr(engine="python", script=source)

            # Handle regular functions
            else:
                # Try to extract just the return statement or function body
                lines = source.split("\n")

                # Skip the def line and docstrings
                body_lines = []
                in_docstring = False
                skip_def = True
                docstring_delim = None  # Track which delimiter opened the docstring

                for line in lines:
                    stripped = line.strip()

                    # Skip def line
                    if skip_def and stripped.startswith("def "):
                        skip_def = False
                        continue

                    # Handle docstrings
                    if not in_docstring:
                        # Check if this line starts a docstring
                        if stripped.startswith('"""') or stripped.startswith("'''"):
                            docstring_delim = (
                                '"""' if stripped.startswith('"""') else "'''"
                            )
                            in_docstring = True
                            # Check if it's a single-line docstring
                            if stripped.count(docstring_delim) >= 2:
                                in_docstring = False  # Closed on same line
                            continue
                    else:
                        # We're in a docstring, check if it closes
                        if docstring_delim is not None and docstring_delim in stripped:
                            in_docstring = False
                        continue

                    # Collect body lines (not in docstring, not comments)
                    if stripped and not stripped.startswith("#"):
                        body_lines.append(stripped)

                # If it's a simple return statement, extract just the expression
                if len(body_lines) == 1 and body_lines[0].startswith("return "):
                    return Expr(
                        engine="python", script=body_lines[0].replace("return ", "", 1)
                    )

                # Otherwise, return the full body
                return Expr(engine="python", script="\n".join(body_lines))

        except Exception as e:
            logger.error(f"Failed to serialize lambda: {e}")
            # Fallback: use function string representation
            return Expr(engine="python", script=str(fn))
