"""Tests for the Slack notifier."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.models import BaseEvalItemOutput, BaseEvalOutput
from src.notifications.slack import SlackNotifier, _build_ascii_graph


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


class TestSlackPayloadConstruction:
    """Test that payload is built correctly for various scenarios."""

    def test_failed_flow_payload(self) -> None:
        """Payload for a failed flow has danger color and correct blocks."""
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        result = _make_result(status="failed")

        payload = notifier._build_payload("checkout", "run_001", result, transition=None)

        # Check attachment color
        assert payload["attachments"][0]["color"] == "danger"

        blocks = payload["attachments"][0]["blocks"]
        # Header block
        header_text = blocks[0]["text"]["text"]
        assert "checkout" in header_text
        assert "failed" in header_text

        # Fields block
        fields = blocks[1]["fields"]
        field_texts = [f["text"] for f in fields]
        assert any("`checkout`" in t for t in field_texts)
        assert any("`run_001`" in t for t in field_texts)
        assert any("`failed`" in t for t in field_texts)

    def test_resolved_transition_payload(self) -> None:
        """Resolved transition gets 'good' color and transition text."""
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        result = _make_result(status="passed")

        payload = notifier._build_payload(
            "checkout", "run_002", result, transition="failed -> passed"
        )

        assert payload["attachments"][0]["color"] == "good"

        header_text = payload["attachments"][0]["blocks"][0]["text"]["text"]
        assert "resolved" in header_text
        assert "failed -> passed" in header_text

    def test_running_flow_payload_color(self) -> None:
        """Running status maps to warning color."""
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        result = _make_result(status="running")

        payload = notifier._build_payload("checkout", "run_003", result, transition=None)
        assert payload["attachments"][0]["color"] == "warning"

    def test_duration_formatting(self) -> None:
        """Duration is formatted in human-readable form."""
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")

        # 500ms
        result = _make_result(elapsed_ns=500_000_000)
        payload = notifier._build_payload("f", "r", result, transition=None)
        fields = payload["attachments"][0]["blocks"][1]["fields"]
        duration_field = [f for f in fields if "Duration" in f["text"]][0]
        assert "500ms" in duration_field["text"]

        # 2.5s
        result = _make_result(elapsed_ns=2_500_000_000)
        payload = notifier._build_payload("f", "r", result, transition=None)
        fields = payload["attachments"][0]["blocks"][1]["fields"]
        duration_field = [f for f in fields if "Duration" in f["text"]][0]
        assert "2.5s" in duration_field["text"]


class TestAsciiGraph:
    """Test the ASCII graph renderer."""

    def test_simple_linear_graph(self) -> None:
        """Linear A -> B -> C renders correctly."""
        result = _make_result(
            graph={
                "a": ["b"],
                "b": ["c"],
                "c": [],
            },
            exec_info=[
                BaseEvalItemOutput(
                    node_id="a", dep_node_ids=[], status="passed", elapsed_ns=0
                ),
                BaseEvalItemOutput(
                    node_id="b", dep_node_ids=["a"], status="passed", elapsed_ns=0
                ),
                BaseEvalItemOutput(
                    node_id="c", dep_node_ids=["b"], status="failed", elapsed_ns=0
                ),
            ],
        )
        text = _build_ascii_graph(result)
        assert "✅ a" in text
        assert "✅ b" in text
        assert "❌ c" in text

    def test_multi_child_graph(self) -> None:
        """Node with two children renders both branches."""
        result = _make_result(
            graph={
                "root": ["left", "right"],
                "left": [],
                "right": [],
            },
            exec_info=[
                BaseEvalItemOutput(
                    node_id="root", dep_node_ids=[], status="passed", elapsed_ns=0
                ),
                BaseEvalItemOutput(
                    node_id="left", dep_node_ids=["root"], status="passed", elapsed_ns=0
                ),
                BaseEvalItemOutput(
                    node_id="right",
                    dep_node_ids=["root"],
                    status="pending",
                    elapsed_ns=0,
                ),
            ],
        )
        text = _build_ascii_graph(result)
        assert "✅ root" in text
        assert "✅ left" in text
        assert "⏸️ right" in text

    def test_empty_graph(self) -> None:
        """Empty graph returns placeholder text."""
        result = _make_result(graph={}, exec_info=[])
        text = _build_ascii_graph(result)
        assert text == "(no graph)"


class TestSlackNotifyHTTP:
    """Test the HTTP sending behavior of SlackNotifier."""

    @pytest.mark.asyncio
    async def test_successful_send(self) -> None:
        """Successful webhook POST completes without raising."""
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        result = _make_result()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        mock_post = AsyncMock(return_value=mock_response)

        with patch("src.notifications.slack.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # Should not raise
            await notifier.notify("checkout", "run_001", result)

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert call_kwargs[1]["json"]["attachments"][0]["color"] == "danger"

    @pytest.mark.asyncio
    async def test_webhook_500_does_not_raise(self) -> None:
        """A 500 from the webhook logs a warning but does not propagate."""
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        result = _make_result()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "internal error"

        mock_post = AsyncMock(return_value=mock_response)

        with patch("src.notifications.slack.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # Must not raise
            await notifier.notify("checkout", "run_001", result)

    @pytest.mark.asyncio
    async def test_webhook_429_does_not_raise(self) -> None:
        """A 429 (rate limit) from the webhook logs but does not propagate."""
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        result = _make_result()

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "rate limited"

        mock_post = AsyncMock(return_value=mock_response)

        with patch("src.notifications.slack.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # Must not raise
            await notifier.notify("checkout", "run_001", result)

    @pytest.mark.asyncio
    async def test_network_error_does_not_raise(self) -> None:
        """A network-level exception is caught and logged."""
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        result = _make_result()

        with patch("src.notifications.slack.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.ConnectError("connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # Must not raise
            await notifier.notify("checkout", "run_001", result)
