"""Notifier protocol for the notifications system.

Defines the interface that all concrete notifiers must implement.
"""

from typing import Protocol

from src.models import BaseEvalOutput


class Notifier(Protocol):
    """Protocol for sending notifications about flow evaluation results.

    Implementations must never raise — log and move on.
    """

    async def notify(
        self,
        flow: str,
        run_id: str,
        result: BaseEvalOutput,
        transition: str | None = None,
    ) -> None:
        """Send a notification about a flow evaluation result.

        Args:
            flow: The flow identifier.
            run_id: The run identifier.
            result: The evaluation output.
            transition: Optional status transition description (e.g. "running -> failed").

        Must never raise — log and move on.
        """
        ...
