#!/usr/bin/env python
"""
Test script for batch upserting nodes to the Magic API.

This script demonstrates how to create multiple nodes in a flow using the API.
"""

import asyncio
import os
from typing import Any

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:13370/v1")
API_KEY = os.getenv("API_KEY", "secret")


async def create_node(
    client: httpx.AsyncClient, node_data: dict[str, Any]
) -> dict[str, Any]:
    """Create or update a single node."""
    response = await client.post(
        f"{API_BASE_URL}/nodes",
        json=node_data,
        headers={"X-Api-Key": API_KEY},
    )
    if response.status_code != 200:
        raise Exception(
            f"Failed to create/update node {node_data['id']}: "
            f"{response.status_code} {response.text}"
        )
    return response.json()


async def batch_upsert_nodes(nodes: list[dict[str, Any]]) -> None:
    """Batch upsert multiple nodes."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Verify API key
        check_response = await client.get(
            f"{API_BASE_URL}/check", headers={"X-Api-Key": API_KEY}
        )
        check_response.raise_for_status()
        print(f"[OK] API key is valid: {check_response.json()}")

        # Create nodes concurrently
        print(f"\n[INFO] Upserting {len(nodes)} nodes...")
        tasks = [create_node(client, node) for node in nodes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Report results
        success_count = 0
        error_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"[ERROR] Node {i + 1} ({nodes[i]['id']}): {result}")
                error_count += 1

            else:
                print(f"[OK] Node {i + 1} ({result['id']}): Created/Updated")
                success_count += 1

        print(f"\n[INFO] Summary: {success_count} succeeded, {error_count} failed")


async def send_batch_events(events: list[dict[str, Any]]) -> None:
    """Send batch events to the API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"\n[INFO] Sending {len(events)} events...")
        response = await client.post(
            f"{API_BASE_URL}/events-batch",
            json=events,
            headers={"X-Api-Key": API_KEY},
        )

        if response.status_code != 200:
            raise Exception(
                f"Failed to send batch events: {response.status_code} {response.text}"
            )

        result = response.json()
        print(f"[OK] Batch events sent successfully: {result}")
        return result


def create_sample_nodes() -> list[dict[str, Any]]:
    """Create sample node definitions for testing."""
    flow_name = "payment_refund"

    return [
        {
            "id": "refund_webhook_received",
            "flow": flow_name,
            "type": "trigger",
            "source": "manual",
            "description": "Webhook received from payment provider",
            "dep_ids": [],
            "filter": {
                "engine": "python",
                "script": "event.get('type') == 'refund.requested'",
            },
        },
        {
            "id": "validate_refund_amount",
            "flow": flow_name,
            "type": "hook",
            "source": "manual",
            "description": "Validate refund amount is within limits",
            "dep_ids": ["refund_webhook_received"],
            "validator": {
                "engine": "python",
                "script": "0 < event.get('amount', 0) <= 10000",
            },
            "conditions": [{"timeout_ms": 5000}],
        },
        {
            "id": "check_user_eligibility",
            "flow": flow_name,
            "type": "generic",
            "source": "manual",
            "description": "Check if user is eligible for refund",
            "dep_ids": ["validate_refund_amount"],
            "handler": "http_request",
            "handler_input": {
                "params": {
                    "url": "https://api.example.com/users/check-eligibility",
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"},
                    "timeout_ms": 10000,
                }
            },
        },
    ]


def create_sample_events() -> list[dict[str, Any]]:
    """Create sample events for testing."""
    import time

    run_id = f"run_{int(time.time())}"
    current_ts = int(time.time() * 1000)  # milliseconds

    return [
        {
            "flow": "payment_refund",
            "id": "refund_webhook_received",
            "description": "Webhook received from payment provider",
            "run_id": run_id,
            "type": "trigger",
            "data": {
                "type": "refund.requested",
                "amount": 5000,
                "user_id": "user_123",
                "payment_id": "pay_456",
            },
            "filter": {
                "engine": "python",
                "script": "event.get('type') == 'refund.requested'",
            },
            "dep_ids": [],
            "ts": current_ts,
        },
        {
            "flow": "payment_refund",
            "id": "refund_webhook_received",
            "description": "Webhook received from payment provider",
            "run_id": run_id,
            "type": "trigger",
            "data": {
                "type": "refund.requested",
                "amount": 2500,
                "user_id": "user_789",
                "payment_id": "pay_012",
            },
            "filter": {
                "engine": "python",
                "script": "event.get('type') == 'refund.requested'",
            },
            "dep_ids": [],
            "ts": current_ts + 1000,
        },
    ]


async def main() -> None:
    """Main entry point."""
    print("[INFO] Magic API Batch Upsert Test\n")
    print(f"API URL: {API_BASE_URL}")
    print(f"API Key: {API_KEY[:10]}..." if len(API_KEY) > 10 else "API Key: (not set)")
    print()

    # Create sample nodes
    nodes = create_sample_nodes()

    # Batch upsert nodes
    try:
        await batch_upsert_nodes(nodes)
        print("\n[SUCCESS] Batch upsert completed successfully!")
    except Exception as e:
        print(f"\n[ERROR] Batch upsert failed: {e}")
        raise

    # Send batch events
    events = create_sample_events()
    try:
        await send_batch_events(events)
        print("\n[SUCCESS] Batch events sent successfully!")
    except Exception as e:
        print(f"\n[ERROR] Sending batch events failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
