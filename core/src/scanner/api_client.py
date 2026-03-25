"""API client for pushing scan results to the backend."""

from typing import Any

import httpx

from src.scanner.models import ScanResult


class ScanPushError(Exception):
    """Error pushing scan results to the API."""


def _build_payload(result: ScanResult) -> dict[str, Any]:
    """Convert ScanResult to the ScanUploadPayload JSON format."""
    flows: dict[str, list[dict[str, Any]]] = {}
    for flow_name, nodes in result.flows.items():
        flows[flow_name] = [
            {
                "id": n.id,
                "flow": n.flow,
                "type": n.type,
                "dep_ids": n.dep_ids,
                "description": n.description,
                "conditions": n.conditions,
                "has_filter": n.has_filter,
                "has_validator": n.has_validator,
                "source_file": n.source_file,
                "source_line": n.source_line,
                "source_column": n.source_column,
            }
            for n in nodes
        ]

    return {
        "version": result.version,
        "scanned_at": result.scanned_at,
        "files_scanned": result.files_scanned,
        "flows": flows,
    }


def push_scan_result(
    result: ScanResult,
    url: str,
    api_key: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Push scan results to the backend API.

    Returns:
        API response dict with created/updated/deleted counts.

    Raises:
        ScanPushError: On any API or connection error.
    """
    endpoint = f"{url.rstrip('/')}/v1/nodes/scan"
    payload = _build_payload(result)

    try:
        response = httpx.post(
            endpoint,
            json=payload,
            headers={
                "X-Api-Key": api_key,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
    except httpx.ConnectError:
        raise ScanPushError(f"Connection refused: {url}") from None
    except httpx.TimeoutException:
        raise ScanPushError(f"Request timed out after {timeout}s") from None
    except httpx.HTTPError as e:
        raise ScanPushError(f"HTTP error: {e}") from e

    if response.status_code == 401:
        raise ScanPushError("Authentication failed: invalid API key")
    if response.status_code >= 500:
        raise ScanPushError(f"Server error ({response.status_code}): {response.text}")
    if response.status_code >= 400:
        raise ScanPushError(f"Client error ({response.status_code}): {response.text}")

    resp_data: dict[str, Any] = response.json()
    return resp_data
