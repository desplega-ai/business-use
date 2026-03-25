"""Sentry notifier — sends capture_message events with structured tags and context."""

import logging
from typing import Literal

from src.models import BaseEvalOutput

logger = logging.getLogger(__name__)

try:
    import sentry_sdk

    HAS_SENTRY = True
except ImportError:
    sentry_sdk = None  # type: ignore[assignment]
    HAS_SENTRY = False

_sentry_warning_logged = False


class SentryNotifier:
    """Sends flow evaluation notifications to Sentry via capture_message.

    Uses tags for filtering, structured context for details, and fingerprints
    for issue grouping. Never raises — all errors are caught and logged.

    Requires sentry-sdk to be installed and initialized (via sentry_sdk.init()
    at app startup). If the SDK is not installed, logs a warning once and
    becomes a no-op.
    """

    async def notify(
        self,
        flow: str,
        run_id: str,
        result: BaseEvalOutput,
        transition: str | None = None,
    ) -> None:
        """Send a Sentry capture_message notification.

        Args:
            flow: The flow identifier.
            run_id: The run identifier.
            result: The evaluation output.
            transition: Optional status transition (e.g. "running -> failed").
        """
        global _sentry_warning_logged  # noqa: PLW0603

        if not HAS_SENTRY:
            if not _sentry_warning_logged:
                logger.warning(
                    "SentryNotifier: sentry-sdk not installed, skipping notifications"
                )
                _sentry_warning_logged = True
            return

        try:
            self._send(flow, run_id, result, transition)
        except Exception:
            logger.exception(
                "SentryNotifier failed for flow=%s run_id=%s",
                flow,
                run_id,
            )

    def _send(
        self,
        flow: str,
        run_id: str,
        result: BaseEvalOutput,
        transition: str | None,
    ) -> None:
        """Build tags, context, and send capture_message to Sentry."""
        assert sentry_sdk is not None

        status = result.status
        elapsed_ms = result.elapsed_ns / 1_000_000

        # Collect failed node IDs from exec_info
        failed_nodes = [
            item.node_id
            for item in result.exec_info
            if item.status in ("failed", "error", "timed_out")
        ]

        # Set tags for filtering in Sentry
        sentry_sdk.set_tag("flow", flow)
        sentry_sdk.set_tag("run_id", run_id)
        sentry_sdk.set_tag("eval_status", status)

        # Set structured context for the event detail panel
        context: dict[str, object] = {
            "flow": flow,
            "run_id": run_id,
            "status": status,
            "elapsed_ms": round(elapsed_ms, 2),
            "failed_nodes": failed_nodes,
        }
        if transition:
            context["transition"] = transition

        sentry_sdk.set_context("eval_result", context)

        # Determine message and level
        level: Literal["error", "info"]
        if status in ("failed", "error", "timed_out"):
            level = "error"
        else:
            level = "info"
        message = f"Flow '{flow}' evaluation {status} (run: {run_id})"

        # Fingerprint for issue grouping: group by flow + status
        sentry_sdk.capture_message(
            message,
            level=level,
            fingerprint=["flow-eval", flow, status],
        )

        logger.debug(
            "Sentry notification sent: flow=%s run_id=%s level=%s",
            flow,
            run_id,
            level,
        )
