#!/usr/bin/env python
"""
Test script demonstrating a realistic payment flow with partial success and failure.

This script creates a simpler, more realistic flow where payment processing
succeeds initially but fails during settlement, demonstrating partial execution.
"""

import asyncio
import os
import time
from typing import Any

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:13370/v1")
API_KEY = os.getenv("API_KEY", "secret")


async def run_evaluation(
    client: httpx.AsyncClient, run_id: str, flow: str
) -> dict[str, Any]:
    """Run evaluation for a flow run."""
    response = await client.post(
        f"{API_BASE_URL}/run-eval",
        json={"run_id": run_id, "flow": flow},
        headers={"X-Api-Key": API_KEY},
    )
    if response.status_code != 200:
        raise Exception(
            f"Failed to evaluate run: {response.status_code} {response.text}"
        )
    return response.json()


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


def create_payment_flow_events(run_id: str) -> list[dict[str, Any]]:
    """Create a payment processing flow where it succeeds halfway then fails.

    Flow structure:
    1. payment_initiated (trigger) ✓
    2. validate_card (hook) ✓
    3. authorize_payment (act) ✓
    4. settle_payment (act) ✗ FAILS - no event sent (settlement timeout/error)
    5. send_receipt (act) ⊘ SKIPPED - depends on successful settlement

    This demonstrates a realistic scenario where authorization succeeds
    but settlement never completes (timeout, service unavailable, etc.)
    """
    base_ts = int(time.time() * 1_000_000_000)  # nanoseconds
    flow = "payment_processing"

    return [
        # 1. Payment initiated (trigger) - SUCCEEDS
        {
            "flow": flow,
            "id": "payment_initiated",
            "description": "Customer initiated payment",
            "run_id": run_id,
            "type": "trigger",
            "data": {
                "payment_id": "PAY-12345",
                "amount": 99.99,
                "currency": "USD",
                "customer_id": "CUST-789",
            },
            "dep_ids": [],
            "ts": base_ts,
        },
        # 2. Validate card (hook) - SUCCEEDS
        {
            "flow": flow,
            "id": "validate_card",
            "description": "Validate card details and security checks",
            "run_id": run_id,
            "type": "hook",
            "data": {
                "card_valid": True,
                "card_type": "visa",
                "last4": "4242",
                "cvv_check": "passed",
            },
            "validator": {
                "engine": "python",
                "script": "data.get('card_valid') == True",
            },
            "dep_ids": ["payment_initiated"],
            "ts": base_ts + 50_000_000,  # +50ms
        },
        # 3. Authorize payment (act) - SUCCEEDS
        {
            "flow": flow,
            "id": "authorize_payment",
            "description": "Authorize payment with card processor",
            "run_id": run_id,
            "type": "act",
            "data": {
                "authorization_code": "AUTH-ABC123",
                "authorized": True,
                "available_balance": 150.00,
            },
            "filter": {
                "engine": "python",
                "script": "data.get('authorized') == True",
            },
            "dep_ids": ["validate_card"],
            "ts": base_ts + 200_000_000,  # +200ms
        },
        # 4. Settle payment (act) - node definition only, NO EVENT SENT
        # This creates the node in the graph but doesn't send the event,
        # simulating a settlement timeout or service unavailability
        {
            "flow": flow,
            "id": "settle_payment",
            "description": "Settle payment with bank",
            "run_id": run_id,
            "type": "act",
            "data": {},  # Empty data - this node creates the definition
            "dep_ids": ["authorize_payment"],
            "ts": base_ts + 500_000_000,  # +500ms
        },
        # 5. Send receipt (act) - node definition only, NO EVENT SENT
        # This would depend on settlement, so it also doesn't execute
        {
            "flow": flow,
            "id": "send_receipt",
            "description": "Send payment receipt to customer",
            "run_id": run_id,
            "type": "act",
            "data": {},  # Empty data - this node creates the definition
            "dep_ids": ["settle_payment"],
            "ts": base_ts + 600_000_000,  # +600ms
        },
    ]


async def main() -> None:
    """Main entry point - demonstrates realistic partial failure flow."""
    print("=" * 70)
    print("Payment Processing Flow Test (Partial Success + Failure)")
    print("=" * 70)
    print(f"\nAPI URL: {API_BASE_URL}")
    print(f"API Key: {API_KEY[:10]}..." if len(API_KEY) > 10 else "API Key: (not set)")
    print()

    # Generate unique run ID
    run_id = f"run_{int(time.time())}"
    print(f"Run ID: {run_id}\n")

    # Create events (nodes will be auto-created via batch endpoint with source='code')
    events = create_payment_flow_events(run_id)
    print(f"Created {len(events)} events for payment processing flow:")
    print("  1. payment_initiated (trigger) ✓")
    print("  2. validate_card (hook) ✓")
    print("  3. authorize_payment (act) ✓")
    print("  4. settle_payment (act) ✗ FAILS - settlement rejected")
    print("  5. send_receipt (act) ⊘ SKIPPED - no event sent\n")
    print("This simulates a realistic scenario where authorization succeeds")
    print("but settlement fails (e.g., fraud detection, insufficient funds).")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Send batch events (this auto-creates nodes with source='code')
        try:
            await send_batch_events(client, events)
        except Exception as e:
            print(f"\n[ERROR] Failed to send batch events: {e}")
            raise

        # Wait a moment for events to be processed
        print("\n[INFO] Waiting for events to be processed...")
        await asyncio.sleep(0.5)

        # Run evaluation
        print(f"\n[INFO] Evaluating flow run: {run_id}")
        print("-" * 70)
        try:
            eval_result = await run_evaluation(client, run_id, "payment_processing")

            # Display results
            status = eval_result.get("status", "unknown")
            elapsed_ns = eval_result.get("elapsed_ns", 0)
            elapsed_ms = elapsed_ns / 1_000_000

            print(f"\n{'=' * 70}")
            print(f"EVALUATION RESULT: {status.upper()}")
            print(f"{'=' * 70}")
            print(f"Elapsed time: {elapsed_ms:.2f}ms")
            print(f"Events processed: {len(eval_result.get('ev_ids', []))}")

            # Show execution info
            exec_info = eval_result.get("exec_info", [])
            if exec_info:
                print("\nNode Execution Summary:")
                print("-" * 70)

                passed = sum(1 for item in exec_info if item.get("status") == "passed")
                failed = sum(1 for item in exec_info if item.get("status") == "failed")
                skipped = sum(
                    1 for item in exec_info if item.get("status") == "skipped"
                )

                print(f"  ✓ Passed:  {passed}")
                print(f"  ✗ Failed:  {failed}")
                print(f"  ⊘ Skipped: {skipped}")

                if failed > 0:
                    print("\nFailed Nodes:")
                    for item in exec_info:
                        if item.get("status") == "failed":
                            node_id = item.get("node_id")
                            message = item.get("message", "Unknown error")
                            print(f"  - {node_id}: {message}")

                # Show detailed execution
                print("\nDetailed Execution:")
                print("-" * 70)
                for item in exec_info:
                    node_id = item.get("node_id")
                    node_status = item.get("status")
                    node_elapsed = item.get("elapsed_ns", 0) / 1_000_000
                    deps = item.get("dep_node_ids", [])

                    status_symbol = {
                        "passed": "✓",
                        "failed": "✗",
                        "skipped": "⊘",
                    }.get(node_status, "?")

                    deps_str = f" (depends on: {', '.join(deps)})" if deps else ""
                    print(
                        f"  [{status_symbol}] {node_id}{deps_str} - {node_elapsed:.2f}ms"
                    )

            # Show graph structure
            graph = eval_result.get("graph", {})
            if graph:
                print("\nFlow Graph Structure:")
                print("-" * 70)
                for node_id, children in sorted(graph.items()):
                    if children:
                        print(f"  {node_id} → {', '.join(children)}")
                    else:
                        print(f"  {node_id} (leaf node)")

            print(f"\n{'=' * 70}")
            if status == "passed":
                print("✓ Flow evaluation PASSED - All nodes executed successfully!")
            else:
                print("✗ Flow evaluation FAILED - Check errors above")
            print(f"{'=' * 70}\n")

        except Exception as e:
            print(f"\n[ERROR] Evaluation failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
