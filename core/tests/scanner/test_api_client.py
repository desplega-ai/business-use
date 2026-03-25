"""Test API client with mocked httpx responses."""

from unittest.mock import patch

import httpx
import pytest

from src.scanner.api_client import ScanPushError, _build_payload, push_scan_result
from src.scanner.models import ExtractedNode, ScanResult


def _sample_result() -> ScanResult:
    return ScanResult(
        files_scanned=1,
        flows={
            "checkout": [
                ExtractedNode(
                    id="cart_created",
                    flow="checkout",
                    type="act",
                    source_file="src/cart.ts",
                    source_line=10,
                    source_column=1,
                ),
            ]
        },
    )


class TestBuildPayload:
    def test_basic_payload(self):
        result = _sample_result()
        payload = _build_payload(result)
        assert payload["version"] == "1.0"
        assert payload["files_scanned"] == 1
        assert "checkout" in payload["flows"]
        assert len(payload["flows"]["checkout"]) == 1
        node = payload["flows"]["checkout"][0]
        assert node["id"] == "cart_created"
        assert node["flow"] == "checkout"
        assert node["type"] == "act"

    def test_excludes_warnings(self):
        result = _sample_result()
        payload = _build_payload(result)
        # Warnings should not be in payload
        assert "warnings" not in payload
        for nodes in payload["flows"].values():
            for node in nodes:
                assert "warnings" not in node


class TestPushScanResult:
    def test_success(self):
        result = _sample_result()
        mock_response = httpx.Response(
            200,
            json={"created": 1, "updated": 0, "deleted": 0, "flows": ["checkout"]},
        )
        with patch("src.scanner.api_client.httpx.post", return_value=mock_response):
            resp = push_scan_result(result, "http://localhost:13370", "test-key")
        assert resp["created"] == 1
        assert resp["flows"] == ["checkout"]

    def test_auth_failure(self):
        result = _sample_result()
        mock_response = httpx.Response(401, text="Unauthorized")
        with patch("src.scanner.api_client.httpx.post", return_value=mock_response):
            with pytest.raises(ScanPushError, match="Authentication failed"):
                push_scan_result(result, "http://localhost:13370", "bad-key")

    def test_server_error(self):
        result = _sample_result()
        mock_response = httpx.Response(500, text="Internal Server Error")
        with patch("src.scanner.api_client.httpx.post", return_value=mock_response):
            with pytest.raises(ScanPushError, match="Server error"):
                push_scan_result(result, "http://localhost:13370", "test-key")

    def test_connection_error(self):
        result = _sample_result()
        with patch(
            "src.scanner.api_client.httpx.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(ScanPushError, match="Connection refused"):
                push_scan_result(result, "http://localhost:99999", "test-key")

    def test_timeout_error(self):
        result = _sample_result()
        with patch(
            "src.scanner.api_client.httpx.post",
            side_effect=httpx.ReadTimeout("timeout"),
        ):
            with pytest.raises(ScanPushError, match="timed out"):
                push_scan_result(result, "http://localhost:13370", "test-key")
