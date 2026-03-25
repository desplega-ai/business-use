"""NotificationDispatcher routes evaluation results to registered notifiers."""

import logging
import time

from src.models import BaseEvalOutput
from src.notifications.protocol import Notifier

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Dispatches notifications to all registered notifiers with optional throttling.

    Throttling is keyed on (flow, status) to avoid spamming the same notification.
    A throttle_seconds of 0 disables throttling entirely.
    """

    def __init__(self, throttle_seconds: int = 0) -> None:
        self.notifiers: list[Notifier] = []
        self._throttle_seconds = throttle_seconds
        self._last_notified: dict[tuple[str, str], float] = {}

    def register(self, notifier: Notifier) -> None:
        """Add a notifier to the dispatch list."""
        self.notifiers.append(notifier)

    async def dispatch(
        self,
        flow: str,
        run_id: str,
        result: BaseEvalOutput,
        transition: str | None = None,
    ) -> None:
        """Send a notification to all registered notifiers.

        Respects throttle settings: skips if (flow, status) was notified
        within the last throttle_seconds. Each notifier is called independently;
        exceptions in one notifier do not affect others.
        """
        if not self.notifiers:
            return

        # Throttle check
        if self._throttle_seconds > 0:
            key = (flow, result.status)
            now = time.monotonic()
            last = self._last_notified.get(key)
            if last is not None and (now - last) < self._throttle_seconds:
                logger.debug(
                    "Throttled notification for flow=%s status=%s",
                    flow,
                    result.status,
                )
                return
            self._last_notified[key] = now

        for notifier in self.notifiers:
            try:
                await notifier.notify(
                    flow=flow,
                    run_id=run_id,
                    result=result,
                    transition=transition,
                )
            except Exception:
                logger.exception(
                    "Notifier %s failed for flow=%s run_id=%s",
                    type(notifier).__name__,
                    flow,
                    run_id,
                )
