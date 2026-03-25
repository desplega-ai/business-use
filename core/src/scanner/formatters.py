"""Output formatters for scan results."""

import json
from dataclasses import asdict

from src.scanner.models import ScanResult, ScanWarning


def format_json(result: ScanResult) -> str:
    """Serialize a ScanResult to a JSON string."""
    return json.dumps(asdict(result), indent=2)


def _fmt_row(cells: tuple[str, ...], col_widths: list[int]) -> str:
    parts = []
    for i, cell in enumerate(cells):
        parts.append(f" {cell:<{col_widths[i] - 1}}")
    return "\u2502" + "\u2502".join(parts) + "\u2502"


def _border(left: str, mid: str, right: str, col_widths: list[int]) -> str:
    return left + mid.join("\u2500" * w for w in col_widths) + right


def format_table(result: ScanResult) -> str:
    """Render a ScanResult as a human-readable table."""
    lines: list[str] = []

    if not result.flows:
        lines.append("No flows found.")
        _append_warnings(lines, result.warnings)
        return "\n".join(lines)

    for flow_name, nodes in sorted(result.flows.items()):
        lines.append(f"Flow: {flow_name} ({len(nodes)} nodes)")

        # Compute column widths
        headers = ("ID", "Type", "Dep IDs", "Source")
        rows: list[tuple[str, str, str, str]] = []
        for node in nodes:
            dep_ids_str = ", ".join(node.dep_ids) if node.dep_ids else "\u2014"
            source = (
                f"{node.source_file}:{node.source_line}"
                if node.source_file
                else "\u2014"
            )
            rows.append((node.id, node.type, dep_ids_str, source))

        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(cell))

        # Add padding
        col_widths = [w + 2 for w in col_widths]

        lines.append(_border("\u250c", "\u252c", "\u2510", col_widths))
        lines.append(_fmt_row(headers, col_widths))
        lines.append(_border("\u251c", "\u253c", "\u2524", col_widths))
        for row in rows:
            lines.append(_fmt_row(row, col_widths))
        lines.append(_border("\u2514", "\u2534", "\u2518", col_widths))
        lines.append("")

    _append_warnings(lines, result.warnings)
    return "\n".join(lines)


def _append_warnings(lines: list[str], warnings: list[ScanWarning]) -> None:
    """Append formatted warnings to the output lines."""
    if not warnings:
        return
    lines.append(f"Warnings ({len(warnings)}):")
    for w in warnings:
        loc = f"{w.file}:{w.line}" if w.line is not None else w.file
        lines.append(f"  \u26a0 {loc} - {w.message}")
