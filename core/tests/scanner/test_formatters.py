"""Tests for scanner output formatters."""

import json

from src.scanner.formatters import format_json, format_table
from src.scanner.models import ExtractedNode, ScanResult, ScanWarning


def _make_result() -> ScanResult:
    """Create a sample ScanResult for testing."""
    return ScanResult(
        version="1.0",
        scanned_at="2026-01-01T00:00:00+00:00",
        files_scanned=2,
        files_skipped=0,
        flows={
            "checkout": [
                ExtractedNode(
                    id="cart_created",
                    flow="checkout",
                    type="act",
                    dep_ids=[],
                    source_file="src/cart/service.ts",
                    source_line=42,
                ),
                ExtractedNode(
                    id="payment_processed",
                    flow="checkout",
                    type="assert",
                    dep_ids=["cart_created"],
                    has_validator=True,
                    source_file="src/payment/handler.ts",
                    source_line=18,
                ),
            ],
        },
        warnings=[
            ScanWarning(
                file="src/utils/helper.ts",
                line=22,
                message="ensure() call with non-literal 'id' argument, skipped",
            ),
        ],
    )


class TestFormatJson:
    def test_valid_json(self) -> None:
        result = _make_result()
        output = format_json(result)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_contains_expected_keys(self) -> None:
        result = _make_result()
        output = format_json(result)
        parsed = json.loads(output)
        assert "version" in parsed
        assert "scanned_at" in parsed
        assert "files_scanned" in parsed
        assert "flows" in parsed
        assert "warnings" in parsed

    def test_flows_structure(self) -> None:
        result = _make_result()
        output = format_json(result)
        parsed = json.loads(output)
        assert "checkout" in parsed["flows"]
        assert len(parsed["flows"]["checkout"]) == 2

    def test_empty_result(self) -> None:
        result = ScanResult(scanned_at="2026-01-01T00:00:00+00:00")
        output = format_json(result)
        parsed = json.loads(output)
        assert parsed["flows"] == {}
        assert parsed["warnings"] == []
        assert parsed["files_scanned"] == 0


class TestFormatTable:
    def test_contains_columns(self) -> None:
        result = _make_result()
        output = format_table(result)
        assert "ID" in output
        assert "Type" in output
        assert "Dep IDs" in output
        assert "Source" in output

    def test_contains_flow_name(self) -> None:
        result = _make_result()
        output = format_table(result)
        assert "Flow: checkout (2 nodes)" in output

    def test_contains_node_data(self) -> None:
        result = _make_result()
        output = format_table(result)
        assert "cart_created" in output
        assert "payment_processed" in output
        assert "src/cart/service.ts:42" in output

    def test_contains_warnings(self) -> None:
        result = _make_result()
        output = format_table(result)
        assert "Warnings (1):" in output
        assert "src/utils/helper.ts:22" in output

    def test_empty_result(self) -> None:
        result = ScanResult(scanned_at="2026-01-01T00:00:00+00:00")
        output = format_table(result)
        assert "No flows found." in output

    def test_node_without_deps_shows_dash(self) -> None:
        result = _make_result()
        output = format_table(result)
        # cart_created has no deps, should show em-dash
        assert "\u2014" in output


class TestFlowFilter:
    def test_filter_matching_flow(self) -> None:
        result = _make_result()
        # Simulate flow filter like the CLI does
        flow_filter = "checkout"
        if flow_filter in result.flows:
            result.flows = {flow_filter: result.flows[flow_filter]}
        output = format_json(result)
        parsed = json.loads(output)
        assert "checkout" in parsed["flows"]
        assert len(parsed["flows"]) == 1

    def test_filter_non_matching_flow(self) -> None:
        result = _make_result()
        flow_filter = "nonexistent"
        if flow_filter in result.flows:
            result.flows = {flow_filter: result.flows[flow_filter]}
        else:
            result.flows = {}
        output = format_json(result)
        parsed = json.loads(output)
        assert parsed["flows"] == {}

    def test_filter_applied_to_table(self) -> None:
        result = _make_result()
        result.flows = {}
        output = format_table(result)
        assert "No flows found." in output
