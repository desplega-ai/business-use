"""Display helpers for ensure command output."""

import logging
import time
from datetime import datetime
from typing import Any

import click

from src.models import BaseEvalOutput, EvalStatus

log = logging.getLogger(__name__)


class StructuredLogger:
    """Default structured log output for ensure command.

    Outputs timestamped log lines, easy to parse and pipe.
    """

    def log_step(self, step: str, message: str) -> None:
        """Log a step with timestamp.

        Args:
            step: Step label (e.g., "1/5")
            message: Step message
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        click.echo(f"[{timestamp}] [{step}] {message}")

    def log_info(self, message: str) -> None:
        """Log an info message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        click.echo(f"[{timestamp}] {message}")

    def log_success(self, message: str) -> None:
        """Log a success message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        click.secho(f"[{timestamp}] ✓ {message}", fg="green")

    def log_warning(self, message: str) -> None:
        """Log a warning message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        click.secho(f"[{timestamp}] ⚠️  {message}", fg="yellow")

    def log_error(self, message: str) -> None:
        """Log an error message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        click.secho(f"[{timestamp}] ✗ {message}", fg="red")

    def log_progress(
        self, flow: str, status: EvalStatus, elapsed: float, run_id: str | None = None
    ) -> None:
        """Log flow progress update.

        Args:
            flow: Flow name
            status: Current status
            elapsed: Elapsed time in seconds
            run_id: Run ID (optional)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_symbol = self._get_status_symbol(status)
        status_color = self._get_status_color(status)

        run_id_str = f" (run_id: {run_id})" if run_id else ""
        message = f"{status_symbol} {flow}: {status} [{elapsed:.1f}s]{run_id_str}"

        click.secho(f"[{timestamp}] {message}", fg=status_color)

    def update_progress(
        self, flow: str, status: EvalStatus, elapsed: float, message: str | None = None
    ) -> None:
        """Update progress (for structured logger, same as log_progress but without run_id)."""
        # For structured logger, we don't update in-place, just log each poll
        # This makes it easier to pipe/parse output
        pass  # Don't log every poll iteration to avoid spam

    def _get_status_symbol(self, status: EvalStatus) -> str:
        """Get symbol for status."""
        symbols = {
            "pending": "○",
            "running": "⏳",
            "passed": "✓",
            "failed": "✗",
            "skipped": "⊘",
            "error": "✗",
            "cancelled": "⊘",
            "timed_out": "⏱",
            "flaky": "~",
        }
        return symbols.get(status, "?")

    def _get_status_color(self, status: EvalStatus) -> str:
        """Get color for status."""
        colors = {
            "pending": "white",
            "running": "cyan",
            "passed": "green",
            "failed": "red",
            "skipped": "yellow",
            "error": "red",
            "cancelled": "yellow",
            "timed_out": "red",
            "flaky": "yellow",
        }
        return colors.get(status, "white")


class LiveDisplay:
    """Interactive live display for ensure command (--live mode).

    Shows spinners, progress bars, and real-time updates.
    """

    def __init__(self) -> None:
        self.start_time = time.time()

    def show_header(self, title: str) -> None:
        """Show section header."""
        click.echo()
        click.secho(f"{'=' * 60}", fg="cyan")
        click.secho(title, fg="cyan", bold=True)
        click.secho(f"{'=' * 60}", fg="cyan")
        click.echo()

    def show_step(self, step: str, message: str) -> None:
        """Show step header."""
        click.secho(f"[{step}] {message}", fg="white", bold=True)

    def show_success(self, message: str, indent: int = 0) -> None:
        """Show success message."""
        prefix = "  " * indent
        click.secho(f"{prefix}✓ {message}", fg="green")

    def show_info(self, message: str, indent: int = 0) -> None:
        """Show info message."""
        prefix = "  " * indent
        click.echo(f"{prefix}{message}")

    def show_warning(self, message: str, indent: int = 0) -> None:
        """Show warning message."""
        prefix = "  " * indent
        click.secho(f"{prefix}⚠️  {message}", fg="yellow")

    def show_error(self, message: str, indent: int = 0) -> None:
        """Show error message."""
        prefix = "  " * indent
        click.secho(f"{prefix}✗ {message}", fg="red")

    def show_progress(
        self, flow: str, status: EvalStatus, elapsed: float, message: str | None = None
    ) -> None:
        """Show flow progress update."""
        status_symbol = self._get_status_symbol(status)
        status_color = self._get_status_color(status)

        msg = f"  [{elapsed:05.1f}s] {status_symbol} {flow}: {status}"
        if message:
            msg += f" - {message}"

        click.secho(msg, fg=status_color)

    def update_progress(
        self, flow: str, status: EvalStatus, elapsed: float, message: str | None = None
    ) -> None:
        """Update progress in-place (overwrites previous line).

        Use this for live polling updates that should replace the previous line.
        """
        status_symbol = self._get_status_symbol(status)
        status_color = self._get_status_color(status)

        msg = f"  [{elapsed:05.1f}s] {status_symbol} {flow}: {status}"
        if message:
            msg += f" - {message}"

        # Clear line and update in-place
        import sys

        click.echo("\r" + " " * 100 + "\r", nl=False)  # Clear line
        click.secho(msg, fg=status_color, nl=False)  # Write without newline
        sys.stdout.flush()  # Flush output

    def show_final_result(
        self, status: EvalStatus, elapsed: float, details: str | None = None
    ) -> None:
        """Show final result."""
        click.echo()
        status_color = "green" if status == "passed" else "red"
        status_symbol = "✅" if status == "passed" else "❌"

        click.secho(
            f"{status_symbol} Flow completed: {status.upper()} (total: {elapsed:.1f}s)",
            fg=status_color,
            bold=True,
        )

        if details:
            click.echo(details)

    def show_summary(self, results: dict[str, Any]) -> None:
        """Show summary of ensure run."""
        click.echo()
        click.secho("Summary:", fg="white", bold=True)

        total = results.get("total", 0)
        passed = results.get("passed", 0)
        failed = results.get("failed", 0)
        elapsed = results.get("elapsed", 0.0)

        click.echo(f"  Flows run: {total}")
        if passed > 0:
            click.secho(f"  ✓ Passed: {passed}", fg="green")
        if failed > 0:
            click.secho(f"  ✗ Failed: {failed}", fg="red")
        click.echo(f"  Total time: {elapsed:.1f}s")

    def _get_status_symbol(self, status: EvalStatus) -> str:
        """Get symbol for status."""
        symbols = {
            "pending": "○",
            "running": "⏳",
            "passed": "✓",
            "failed": "✗",
            "skipped": "⊘",
            "error": "✗",
            "cancelled": "⊘",
            "timed_out": "⏱",
            "flaky": "~",
        }
        return symbols.get(status, "?")

    def _get_status_color(self, status: EvalStatus) -> str:
        """Get color for status."""
        colors = {
            "pending": "white",
            "running": "cyan",
            "passed": "green",
            "failed": "red",
            "skipped": "yellow",
            "error": "red",
            "cancelled": "yellow",
            "timed_out": "red",
            "flaky": "yellow",
        }
        return colors.get(status, "white")


def format_json_output(results: list[tuple[str, BaseEvalOutput]]) -> dict[str, Any]:
    """Format ensure results as JSON.

    Args:
        results: List of (flow_name, eval_output) tuples

    Returns:
        JSON-serializable dictionary
    """
    flows = []
    total_passed = 0
    total_failed = 0
    total_elapsed = 0.0

    for flow_name, output in results:
        flow_result = {
            "flow": flow_name,
            "status": output.status,
            "elapsed_ms": output.elapsed_ns / 1_000_000,
            "nodes": len(output.graph),
            "events": len(output.ev_ids),
            "exec_info": [
                {
                    "node_id": item.node_id,
                    "status": item.status,
                    "message": item.message,
                    "error": item.error,
                    "elapsed_ms": item.elapsed_ns / 1_000_000,
                }
                for item in output.exec_info
            ],
        }
        flows.append(flow_result)

        if output.status == "passed":
            total_passed += 1
        else:
            total_failed += 1

        total_elapsed += output.elapsed_ns / 1_000_000

    return {
        "summary": {
            "total": len(results),
            "passed": total_passed,
            "failed": total_failed,
            "total_elapsed_ms": total_elapsed,
        },
        "flows": flows,
    }
