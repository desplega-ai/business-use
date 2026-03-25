"""Slack notifier — sends Block Kit messages via incoming webhooks."""

import logging
from collections import defaultdict

import httpx

from src.models import BaseEvalOutput

logger = logging.getLogger(__name__)

# Status → Slack attachment color
_COLOR_MAP: dict[str, str] = {
    "failed": "danger",
    "error": "danger",
    "timed_out": "danger",
    "passed": "good",
    "running": "warning",
}

# Node eval status → emoji
_NODE_EMOJI: dict[str, str] = {
    "passed": "✅",
    "failed": "❌",
    "error": "❌",
    "timed_out": "❌",
    "running": "⏳",
    "pending": "⏸️",
    "skipped": "⏸️",
}


def _status_emoji(status: str) -> str:
    """Return a header emoji for the overall flow status."""
    if status in ("failed", "error", "timed_out"):
        return "🔴"
    if status == "passed":
        return "🟢"
    return "🟡"


def _format_duration(elapsed_ns: int) -> str:
    """Convert nanoseconds to a human-readable duration string."""
    ms = elapsed_ns / 1_000_000
    if ms < 1000:
        return f"{ms:.0f}ms"
    secs = ms / 1000
    if secs < 60:
        return f"{secs:.1f}s"
    mins = secs / 60
    return f"{mins:.1f}m"


def _build_ascii_graph(result: BaseEvalOutput) -> str:
    """Build a text-based DAG from the evaluation result.

    Uses result.graph (adjacency list: node -> dependents) and
    result.exec_info (per-node status) to render a simple ASCII graph.

    Output looks like:
        ✅ cart_created
        └─→ ✅ payment_processed
            └─→ ❌ order_confirmed
    """
    graph = result.graph
    if not graph:
        return "(no graph)"

    # Build status lookup from exec_info
    status_map: dict[str, str] = {}
    for item in result.exec_info:
        status_map[item.node_id] = item.status

    # Build reverse map: node -> parents (who points to this node)
    parents: dict[str, list[str]] = defaultdict(list)
    all_nodes: set[str] = set()
    for parent, children in graph.items():
        all_nodes.add(parent)
        for child in children:
            all_nodes.add(child)
            parents[child].append(parent)

    # Find roots (nodes with no parents)
    roots = [n for n in all_nodes if not parents[n]]
    roots.sort()

    if not roots:
        # Fallback: just list all nodes
        fallback_lines: list[str] = []
        for node_id in sorted(all_nodes):
            emoji = _NODE_EMOJI.get(status_map.get(node_id, ""), "❓")
            fallback_lines.append(f"{emoji} {node_id}")
        return "\n".join(fallback_lines)

    # DFS render
    lines: list[str] = []
    visited: set[str] = set()

    def _render(node_id: str, prefix: str, is_last: bool, is_root: bool) -> None:
        if node_id in visited:
            return
        visited.add(node_id)

        emoji = _NODE_EMOJI.get(status_map.get(node_id, ""), "❓")

        if is_root:
            lines.append(f"{emoji} {node_id}")
        else:
            connector = "└─→ " if is_last else "├─→ "
            lines.append(f"{prefix}{connector}{emoji} {node_id}")

        children = sorted(graph.get(node_id, []))
        child_prefix = prefix + ("    " if is_last or is_root else "│   ")
        for i, child in enumerate(children):
            _render(child, child_prefix, i == len(children) - 1, False)

    for i, root in enumerate(roots):
        if i > 0:
            lines.append("")  # blank line between root trees
        _render(root, "", i == len(roots) - 1, True)

    return "\n".join(lines)


class SlackNotifier:
    """Sends flow evaluation notifications to Slack via incoming webhooks.

    Uses Block Kit with colored attachment sidebars. Never raises — all
    errors are caught and logged.
    """

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    async def notify(
        self,
        flow: str,
        run_id: str,
        result: BaseEvalOutput,
        transition: str | None = None,
    ) -> None:
        """Build and send a Slack Block Kit notification.

        Args:
            flow: The flow identifier.
            run_id: The run identifier.
            result: The evaluation output.
            transition: Optional status transition (e.g. "running -> failed").
        """
        try:
            payload = self._build_payload(flow, run_id, result, transition)
            await self._send(payload)
        except Exception:
            logger.exception(
                "SlackNotifier failed for flow=%s run_id=%s",
                flow,
                run_id,
            )

    def _build_payload(
        self,
        flow: str,
        run_id: str,
        result: BaseEvalOutput,
        transition: str | None,
    ) -> dict[str, object]:
        """Build the Slack webhook JSON payload."""
        status = result.status
        emoji = _status_emoji(status)

        # Determine color: resolved transitions get "good", otherwise map by status
        if transition is not None:
            color = "good"
        else:
            color = _COLOR_MAP.get(status, "#cccccc")

        # Header text
        if transition:
            header_text = f"{emoji} Flow *{flow}* resolved ({transition})"
        else:
            header_text = f"{emoji} Flow *{flow}* — {status}"

        # Section fields
        fields = [
            {"type": "mrkdwn", "text": f"*Flow:*\n`{flow}`"},
            {"type": "mrkdwn", "text": f"*Run ID:*\n`{run_id}`"},
            {"type": "mrkdwn", "text": f"*Status:*\n`{status}`"},
            {
                "type": "mrkdwn",
                "text": f"*Duration:*\n{_format_duration(result.elapsed_ns)}",
            },
        ]

        # ASCII graph
        ascii_graph = _build_ascii_graph(result)

        # Build blocks
        blocks: list[dict[str, object]] = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": header_text},
            },
            {
                "type": "section",
                "fields": fields,
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Graph:*\n```\n{ascii_graph}\n```",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Flow: `{flow}` | Run: `{run_id}`",
                    },
                ],
            },
        ]

        return {
            "attachments": [
                {
                    "color": color,
                    "blocks": blocks,
                }
            ]
        }

    async def _send(self, payload: dict[str, object]) -> None:
        """POST the payload to the Slack webhook URL."""
        timeout = httpx.Timeout(10.0)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._webhook_url,
                json=payload,
                timeout=timeout,
            )

        if response.status_code == 429:
            logger.warning("Slack webhook rate-limited (429): %s", response.text)
        elif response.status_code >= 400:
            logger.warning(
                "Slack webhook returned %d: %s",
                response.status_code,
                response.text,
            )
        else:
            logger.debug("Slack notification sent successfully")
