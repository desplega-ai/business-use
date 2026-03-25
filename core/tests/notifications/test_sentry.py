"""Tests for the Sentry notifier."""

from unittest.mock import MagicMock, patch

import pytest

from src.models import BaseEvalItemOutput, BaseEvalOutput


def _make_result(
    status: str = "failed",
    elapsed_ns: int = 5_000_000_000,
    graph: dict | None = None,
    exec_info: list[BaseEvalItemOutput] | None = None,
) -> BaseEvalOutput:
    """Build a BaseEvalOutput for testing."""
    if graph is None:
        graph = {"cart_created": ["payment_processed"], "payment_processed": []}
    if exec_info is None:
        exec_info = [
            BaseEvalItemOutput(
                node_id="cart_created",
                dep_node_ids=[],
                status="passed",
                elapsed_ns=1_000_000_000,
            ),
            BaseEvalItemOutput(
                node_id="payment_processed",
                dep_node_ids=["cart_created"],
                status="failed",
                message="Timeout exceeded",
                elapsed_ns=4_000_000_000,
            ),
        ]
    return BaseEvalOutput(
        status=status,
        elapsed_ns=elapsed_ns,
        graph=graph,
        exec_info=exec_info,
    )


class TestSentryNotifierCaptureMessage:
    """Test that capture_message is called with correct level and fingerprint."""

    @pytest.mark.asyncio
    async def test_failed_flow_sends_error_level(self) -> None:
        """A failed flow sends capture_message with level='error'."""
        mock_sentry = MagicMock()
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            # Re-import to pick up the mock
            import importlib

            import src.notifications.sentry as sentry_mod

            sentry_mod.sentry_sdk = mock_sentry  # type: ignore[assignment]
            sentry_mod.HAS_SENTRY = True

            notifier = sentry_mod.SentryNotifier()
            result = _make_result(status="failed")

            await notifier.notify("checkout", "run_001", result)

            mock_sentry.capture_message.assert_called_once()
            call_kwargs = mock_sentry.capture_message.call_args
            assert call_kwargs[1]["level"] == "error"
            assert call_kwargs[1]["fingerprint"] == [
                "flow-eval",
                "checkout",
                "failed",
            ]
            assert "checkout" in call_kwargs[0][0]
            assert "run_001" in call_kwargs[0][0]

            # Restore
            importlib.reload(sentry_mod)

    @pytest.mark.asyncio
    async def test_passed_flow_sends_info_level(self) -> None:
        """A passed flow sends capture_message with level='info'."""
        mock_sentry = MagicMock()
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            import importlib

            import src.notifications.sentry as sentry_mod

            sentry_mod.sentry_sdk = mock_sentry  # type: ignore[assignment]
            sentry_mod.HAS_SENTRY = True

            notifier = sentry_mod.SentryNotifier()
            result = _make_result(status="passed")

            await notifier.notify("checkout", "run_002", result)

            call_kwargs = mock_sentry.capture_message.call_args
            assert call_kwargs[1]["level"] == "info"
            assert call_kwargs[1]["fingerprint"] == [
                "flow-eval",
                "checkout",
                "passed",
            ]

            importlib.reload(sentry_mod)

    @pytest.mark.asyncio
    async def test_error_status_sends_error_level(self) -> None:
        """An error status sends capture_message with level='error'."""
        mock_sentry = MagicMock()
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            import importlib

            import src.notifications.sentry as sentry_mod

            sentry_mod.sentry_sdk = mock_sentry  # type: ignore[assignment]
            sentry_mod.HAS_SENTRY = True

            notifier = sentry_mod.SentryNotifier()
            result = _make_result(status="error")

            await notifier.notify("checkout", "run_003", result)

            call_kwargs = mock_sentry.capture_message.call_args
            assert call_kwargs[1]["level"] == "error"

            importlib.reload(sentry_mod)

    @pytest.mark.asyncio
    async def test_timed_out_sends_error_level(self) -> None:
        """A timed_out status sends capture_message with level='error'."""
        mock_sentry = MagicMock()
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            import importlib

            import src.notifications.sentry as sentry_mod

            sentry_mod.sentry_sdk = mock_sentry  # type: ignore[assignment]
            sentry_mod.HAS_SENTRY = True

            notifier = sentry_mod.SentryNotifier()
            result = _make_result(status="timed_out")

            await notifier.notify("checkout", "run_004", result)

            call_kwargs = mock_sentry.capture_message.call_args
            assert call_kwargs[1]["level"] == "error"

            importlib.reload(sentry_mod)


class TestSentryNotifierTagsAndContext:
    """Test that tags and context are set correctly."""

    @pytest.mark.asyncio
    async def test_tags_set_correctly(self) -> None:
        """Tags are set for flow, run_id, and eval_status."""
        mock_sentry = MagicMock()
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            import importlib

            import src.notifications.sentry as sentry_mod

            sentry_mod.sentry_sdk = mock_sentry  # type: ignore[assignment]
            sentry_mod.HAS_SENTRY = True

            notifier = sentry_mod.SentryNotifier()
            result = _make_result(status="failed")

            await notifier.notify("checkout", "run_001", result)

            tag_calls = mock_sentry.set_tag.call_args_list
            tag_dict = {call[0][0]: call[0][1] for call in tag_calls}

            assert tag_dict["flow"] == "checkout"
            assert tag_dict["run_id"] == "run_001"
            assert tag_dict["eval_status"] == "failed"

            importlib.reload(sentry_mod)

    @pytest.mark.asyncio
    async def test_context_set_correctly(self) -> None:
        """Structured context includes flow, run_id, status, elapsed_ms, failed_nodes."""
        mock_sentry = MagicMock()
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            import importlib

            import src.notifications.sentry as sentry_mod

            sentry_mod.sentry_sdk = mock_sentry  # type: ignore[assignment]
            sentry_mod.HAS_SENTRY = True

            notifier = sentry_mod.SentryNotifier()
            result = _make_result(status="failed", elapsed_ns=5_000_000_000)

            await notifier.notify("checkout", "run_001", result)

            ctx_call = mock_sentry.set_context.call_args
            assert ctx_call[0][0] == "eval_result"

            ctx_data = ctx_call[0][1]
            assert ctx_data["flow"] == "checkout"
            assert ctx_data["run_id"] == "run_001"
            assert ctx_data["status"] == "failed"
            assert ctx_data["elapsed_ms"] == 5000.0
            assert ctx_data["failed_nodes"] == ["payment_processed"]

            importlib.reload(sentry_mod)

    @pytest.mark.asyncio
    async def test_context_includes_transition(self) -> None:
        """When transition is provided, it's included in context."""
        mock_sentry = MagicMock()
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            import importlib

            import src.notifications.sentry as sentry_mod

            sentry_mod.sentry_sdk = mock_sentry  # type: ignore[assignment]
            sentry_mod.HAS_SENTRY = True

            notifier = sentry_mod.SentryNotifier()
            result = _make_result(status="passed")

            await notifier.notify(
                "checkout", "run_001", result, transition="failed -> passed"
            )

            ctx_data = mock_sentry.set_context.call_args[0][1]
            assert ctx_data["transition"] == "failed -> passed"

            importlib.reload(sentry_mod)

    @pytest.mark.asyncio
    async def test_context_no_transition_when_none(self) -> None:
        """When transition is None, it's not included in context."""
        mock_sentry = MagicMock()
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            import importlib

            import src.notifications.sentry as sentry_mod

            sentry_mod.sentry_sdk = mock_sentry  # type: ignore[assignment]
            sentry_mod.HAS_SENTRY = True

            notifier = sentry_mod.SentryNotifier()
            result = _make_result(status="failed")

            await notifier.notify("checkout", "run_001", result, transition=None)

            ctx_data = mock_sentry.set_context.call_args[0][1]
            assert "transition" not in ctx_data

            importlib.reload(sentry_mod)


class TestSentryNotifierGracefulSkip:
    """Test graceful behavior when sentry-sdk is not installed."""

    @pytest.mark.asyncio
    async def test_no_sentry_sdk_logs_warning_once(self) -> None:
        """When HAS_SENTRY is False, logs a warning once and returns."""
        import importlib

        import src.notifications.sentry as sentry_mod

        sentry_mod.HAS_SENTRY = False
        sentry_mod._sentry_warning_logged = False

        notifier = sentry_mod.SentryNotifier()
        result = _make_result()

        with patch.object(sentry_mod.logger, "warning") as mock_warn:
            # First call: should log warning
            await notifier.notify("checkout", "run_001", result)
            mock_warn.assert_called_once()
            assert "sentry-sdk not installed" in mock_warn.call_args[0][0]

            # Second call: should NOT log again
            mock_warn.reset_mock()
            await notifier.notify("checkout", "run_002", result)
            mock_warn.assert_not_called()

        importlib.reload(sentry_mod)


class TestSentryNotifierErrorHandling:
    """Test that errors in capture_message are caught and logged."""

    @pytest.mark.asyncio
    async def test_capture_message_exception_does_not_raise(self) -> None:
        """If capture_message raises, notify catches it and logs."""
        mock_sentry = MagicMock()
        mock_sentry.capture_message.side_effect = RuntimeError("Sentry down")

        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            import importlib

            import src.notifications.sentry as sentry_mod

            sentry_mod.sentry_sdk = mock_sentry  # type: ignore[assignment]
            sentry_mod.HAS_SENTRY = True

            notifier = sentry_mod.SentryNotifier()
            result = _make_result()

            # Must not raise
            await notifier.notify("checkout", "run_001", result)

            importlib.reload(sentry_mod)

    @pytest.mark.asyncio
    async def test_set_tag_exception_does_not_raise(self) -> None:
        """If set_tag raises, notify catches it and logs."""
        mock_sentry = MagicMock()
        mock_sentry.set_tag.side_effect = RuntimeError("tag error")

        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            import importlib

            import src.notifications.sentry as sentry_mod

            sentry_mod.sentry_sdk = mock_sentry  # type: ignore[assignment]
            sentry_mod.HAS_SENTRY = True

            notifier = sentry_mod.SentryNotifier()
            result = _make_result()

            # Must not raise
            await notifier.notify("checkout", "run_001", result)

            importlib.reload(sentry_mod)
