#!/usr/bin/env python
"""
Test script for payment_approval flow with dummy events.

This script sends dummy events for testing the ensure command locally.
It simulates a payment approval flow where a payment is created and confirmed.
"""

import asyncio
import os
import time
from typing import Any

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:13370/v1")
API_KEY = os.getenv("API_KEY", "secret")


async def send_batch_events(
    client: httpx.AsyncClient, events: list[dict[str, Any]]
) -> dict[str, Any]:
    """Send batch events to the API."""
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
    print(f"[OK] Batch events sent: {result['message']}")
    return result


def create_payment_approval_events(run_id: str) -> list[dict[str, Any]]:
    """Create dummy events for payment_approval flow.

    Flow structure (from .business-use/payment_approval.yaml):
    1. create_payment (trigger) - Created by ensure command, not SDK
    2. payment_confirmed (act) - Payment confirmation received
    3. receipt_sent (assert) - Receipt sent confirmation
    """
    base_ts = int(time.time() * 1_000_000_000)  # nanoseconds
    flow = "payment_approval"

    return [
        # Payment confirmation (act node)
        {
            "flow": flow,
            "id": "payment_confirmed",
            "description": "Payment confirmation webhook received",
            "run_id": run_id,
            "type": "act",
            "data": {
                "payment_id": run_id,
                "status": "confirmed",
                "amount": 100,
                "currency": "USD",
                "confirmed_at": time.time(),
            },
            "dep_ids": ["create_payment"],
            "ts": base_ts + 1_000_000_000,  # +1s after trigger
        },
        # Receipt sent (assert node)
        {
            "flow": flow,
            "id": "receipt_sent",
            "description": "Receipt sent to customer",
            "run_id": run_id,
            "type": "assert",
            "data": {
                "receipt_sent": True,
                "receipt_id": f"receipt_{run_id}",
                "sent_at": time.time(),
            },
            "validator": {
                "engine": "python",
                "script": "data.get('receipt_sent') == True",
            },
            "dep_ids": ["payment_confirmed"],
            "ts": base_ts + 2_000_000_000,  # +2s after trigger
        },
    ]


async def main() -> None:
    """Main entry point - seeds dummy events for testing."""
    print("=" * 70)
    print("Payment Approval Flow - Dummy Event Seeder")
    print("=" * 70)
    print(f"\nAPI URL: {API_BASE_URL}")
    print(f"API Key: {API_KEY[:10]}..." if len(API_KEY) > 10 else "API Key: (not set)")
    print()
    print("This script sends dummy events for the payment_confirmed and")
    print("receipt_sent nodes. The create_payment (trigger) node should be")
    print("executed by the 'business-use flow ensure' command.\n")

    # Get run_id from command line or generate one
    import sys

    if len(sys.argv) > 1:
        run_id = sys.argv[1]
        print(f"Using provided run_id: {run_id}")
    else:
        run_id = f"payment_{int(time.time())}"
        print(f"Generated run_id: {run_id}")
        print("(You can also provide a run_id as first argument)\n")

    # Create events
    events = create_payment_approval_events(run_id)
    print(f"\nCreated {len(events)} dummy events:")
    print("  1. payment_confirmed (act) - Payment webhook received")
    print("  2. receipt_sent (assert) - Receipt delivery confirmed")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            await send_batch_events(client, events)
            print("\n✓ Events sent successfully!")
            print("\nTo test the flow with ensure command:")
            print(
                f"  1. Make sure these events are in the database for run_id: {run_id}"
            )
            print("  2. Run: business-use flow ensure payment_approval")
            print("  3. The trigger will create the payment and extract the run_id")
            print("  4. The evaluation will check if events exist for that run_id\n")

        except Exception as e:
            print(f"\n[ERROR] Failed to send events: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
