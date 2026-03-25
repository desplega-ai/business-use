"""Tests for the NotificationDispatcher."""

import time
from unittest.mock import AsyncMock

import pytest

from src.models import BaseEvalItemOutput, BaseEvalOutput
from src.notifications.dispatcher import NotificationDispatcher


def _make_result(
    status: str = "failed",
    elapsed_ns: int = 5_000_000_000,
) -> BaseEvalOutput:
    """Build a minimal BaseEvalOutput for testing."""
    return BaseEvalOutput(
        status=status,
        elapsed_ns=elapsed_ns,
        graph={"a": ["b"], "b": []},
        exec_info=[
            BaseEvalItemOutput(
                node_id="a",
                dep_node_ids=[],
                status="passed",
                elapsed_ns=1_000_000_000,
            ),
            BaseEvalItemOutput(
                node_id="b",
                dep_node_ids=["a"],
                status=status,
                elapsed_ns=4_000_000_000,
            ),
        ],
    )


class TestDispatcherEmpty:
    """An empty dispatcher (no notifiers) is a no-op."""

    @pytest.mark.asyncio
    async def test_dispatch_with_no_notifiers_is_noop(self) -> None:
        """dispatch() returns immediately when there are no notifiers."""
        dispatcher = NotificationDispatcher()
        result = _make_result()

        # Should not raise or do anything
        await dispatcher.dispatch("checkout", "run_001", result)


class TestDispatcherSingleNotifier:
    """Dispatcher with one notifier calls it correctly."""

    @pytest.mark.asyncio
    async def test_notifier_called_with_correct_args(self) -> None:
        """Single registered notifier receives flow, run_id, result, and transition."""
        dispatcher = NotificationDispatcher()
        notifier = AsyncMock()
        dispatcher.register(notifier)

        result = _make_result()
        await dispatcher.dispatch(
            "checkout", "run_001", result, transition="running -> failed"
        )

        notifier.notify.assert_called_once_with(
            flow="checkout",
            run_id="run_001",
            result=result,
            transition="running -> failed",
        )

    @pytest.mark.asyncio
    async def test_notifier_called_without_transition(self) -> None:
        """When transition is None, notify receives transition=None."""
        dispatcher = NotificationDispatcher()
        notifier = AsyncMock()
        dispatcher.register(notifier)

        result = _make_result()
        await dispatcher.dispatch("checkout", "run_001", result)

        notifier.notify.assert_called_once_with(
            flow="checkout",
            run_id="run_001",
            result=result,
            transition=None,
        )


class TestDispatcherMultipleNotifiers:
    """Dispatcher calls all registered notifiers in order."""

    @pytest.mark.asyncio
    async def test_all_notifiers_called(self) -> None:
        """All registered notifiers are called."""
        dispatcher = NotificationDispatcher()
        notifier_a = AsyncMock()
        notifier_b = AsyncMock()
        notifier_c = AsyncMock()

        dispatcher.register(notifier_a)
        dispatcher.register(notifier_b)
        dispatcher.register(notifier_c)

        result = _make_result()
        await dispatcher.dispatch("checkout", "run_001", result)

        notifier_a.notify.assert_called_once()
        notifier_b.notify.assert_called_once()
        notifier_c.notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_notifiers_called_in_registration_order(self) -> None:
        """Notifiers are called in the order they were registered."""
        call_order: list[str] = []

        async def make_notifier(name: str) -> AsyncMock:
            notifier = AsyncMock()

            async def side_effect(**kwargs: object) -> None:
                call_order.append(name)

            notifier.notify.side_effect = side_effect
            return notifier

        dispatcher = NotificationDispatcher()
        notifier_a = await make_notifier("a")
        notifier_b = await make_notifier("b")
        notifier_c = await make_notifier("c")

        dispatcher.register(notifier_a)
        dispatcher.register(notifier_b)
        dispatcher.register(notifier_c)

        result = _make_result()
        await dispatcher.dispatch("checkout", "run_001", result)

        assert call_order == ["a", "b", "c"]


class TestDispatcherErrorIsolation:
    """One notifier failing does not prevent others from being called."""

    @pytest.mark.asyncio
    async def test_error_in_first_notifier_does_not_block_others(self) -> None:
        """If the first notifier raises, the second is still called."""
        dispatcher = NotificationDispatcher()

        failing_notifier = AsyncMock()
        failing_notifier.notify.side_effect = RuntimeError("boom")

        ok_notifier = AsyncMock()

        dispatcher.register(failing_notifier)
        dispatcher.register(ok_notifier)

        result = _make_result()
        await dispatcher.dispatch("checkout", "run_001", result)

        failing_notifier.notify.assert_called_once()
        ok_notifier.notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_in_middle_notifier_does_not_block_others(self) -> None:
        """If the middle notifier raises, first and last still complete."""
        dispatcher = NotificationDispatcher()

        first = AsyncMock()
        failing = AsyncMock()
        failing.notify.side_effect = ValueError("bad value")
        last = AsyncMock()

        dispatcher.register(first)
        dispatcher.register(failing)
        dispatcher.register(last)

        result = _make_result()
        await dispatcher.dispatch("checkout", "run_001", result)

        first.notify.assert_called_once()
        failing.notify.assert_called_once()
        last.notify.assert_called_once()


class TestDispatcherThrottle:
    """Throttle behavior: same (flow, status) within window is skipped."""

    @pytest.mark.asyncio
    async def test_same_flow_status_within_window_is_skipped(self) -> None:
        """Second dispatch with same (flow, status) within throttle window is skipped."""
        dispatcher = NotificationDispatcher(throttle_seconds=60)
        notifier = AsyncMock()
        dispatcher.register(notifier)

        result = _make_result(status="failed")

        await dispatcher.dispatch("checkout", "run_001", result)
        await dispatcher.dispatch("checkout", "run_002", result)

        # Only the first should have been dispatched
        notifier.notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_flow_not_throttled(self) -> None:
        """Different flow names are independent for throttling."""
        dispatcher = NotificationDispatcher(throttle_seconds=60)
        notifier = AsyncMock()
        dispatcher.register(notifier)

        result = _make_result(status="failed")

        await dispatcher.dispatch("checkout", "run_001", result)
        await dispatcher.dispatch("payments", "run_002", result)

        assert notifier.notify.call_count == 2

    @pytest.mark.asyncio
    async def test_different_status_not_throttled(self) -> None:
        """Different statuses for the same flow are independent for throttling."""
        dispatcher = NotificationDispatcher(throttle_seconds=60)
        notifier = AsyncMock()
        dispatcher.register(notifier)

        result_failed = _make_result(status="failed")
        result_passed = _make_result(status="passed")

        await dispatcher.dispatch("checkout", "run_001", result_failed)
        await dispatcher.dispatch("checkout", "run_002", result_passed)

        assert notifier.notify.call_count == 2

    @pytest.mark.asyncio
    async def test_throttle_disabled_with_zero(self) -> None:
        """With throttle_seconds=0, all notifications pass through."""
        dispatcher = NotificationDispatcher(throttle_seconds=0)
        notifier = AsyncMock()
        dispatcher.register(notifier)

        result = _make_result(status="failed")

        await dispatcher.dispatch("checkout", "run_001", result)
        await dispatcher.dispatch("checkout", "run_002", result)
        await dispatcher.dispatch("checkout", "run_003", result)

        assert notifier.notify.call_count == 3

    @pytest.mark.asyncio
    async def test_throttle_expires_after_window(self) -> None:
        """After the throttle window expires, notifications resume."""
        dispatcher = NotificationDispatcher(throttle_seconds=1)
        notifier = AsyncMock()
        dispatcher.register(notifier)

        result = _make_result(status="failed")

        await dispatcher.dispatch("checkout", "run_001", result)
        assert notifier.notify.call_count == 1

        # Manually expire the throttle by backdating _last_notified
        key = ("checkout", "failed")
        dispatcher._last_notified[key] = time.monotonic() - 2

        await dispatcher.dispatch("checkout", "run_002", result)
        assert notifier.notify.call_count == 2


class TestDispatcherTransition:
    """Transition parameter is forwarded to notifiers correctly."""

    @pytest.mark.asyncio
    async def test_transition_forwarded(self) -> None:
        """The transition string is passed through to notify()."""
        dispatcher = NotificationDispatcher()
        notifier = AsyncMock()
        dispatcher.register(notifier)

        result = _make_result(status="passed")
        await dispatcher.dispatch(
            "checkout", "run_001", result, transition="failed -> passed"
        )

        notifier.notify.assert_called_once_with(
            flow="checkout",
            run_id="run_001",
            result=result,
            transition="failed -> passed",
        )

    @pytest.mark.asyncio
    async def test_transition_none_by_default(self) -> None:
        """Without explicit transition, None is forwarded."""
        dispatcher = NotificationDispatcher()
        notifier = AsyncMock()
        dispatcher.register(notifier)

        result = _make_result()
        await dispatcher.dispatch("checkout", "run_001", result)

        _, kwargs = notifier.notify.call_args
        assert kwargs["transition"] is None
