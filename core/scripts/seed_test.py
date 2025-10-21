#!/usr/bin/env python
"""
Test script demonstrating a complex e-commerce order fulfillment flow.

This script creates a realistic flow with multiple branches, dependencies,
and validation steps. It then sends batch events and evaluates the flow.
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


def create_complex_flow_events(run_id: str) -> list[dict[str, Any]]:
    """Create a complex e-commerce order fulfillment flow with events.

    Flow structure:
    1. order_created (trigger)
    2. validate_inventory (hook) + validate_payment (hook) - parallel
    3. reserve_inventory (act) + charge_payment (act) - parallel, depend on validations
    4. confirm_order (hook) - depends on both reserves
    5. notify_warehouse (act) + notify_customer (act) - parallel, depend on confirmation
    6. ship_order (act) - depends on warehouse notification
    7. update_tracking (hook) - depends on shipping
    """
    base_ts = int(time.time() * 1_000_000_000)  # nanoseconds
    flow = "order_fulfillment"

    return [
        # 1. Order created (trigger)
        {
            "flow": flow,
            "id": "order_created",
            "description": "Customer order created",
            "run_id": run_id,
            "type": "trigger",
            "data": {
                "order_id": "ORD-12345",
                "customer_id": "CUST-789",
                "items": [
                    {"sku": "WIDGET-A", "quantity": 2, "price": 29.99},
                    {"sku": "GADGET-B", "quantity": 1, "price": 149.99},
                ],
                "total": 209.97,
                "payment_method": "credit_card",
            },
            "filter": {
                "engine": "python",
                "script": "data.get('order_id') is not None",
            },
            "dep_ids": [],
            "ts": base_ts,
        },
        # 2a. Validate inventory (hook)
        {
            "flow": flow,
            "id": "validate_inventory",
            "description": "Validate items are in stock",
            "run_id": run_id,
            "type": "hook",
            "data": {
                "inventory_check": "passed",
                "available": {"WIDGET-A": 150, "GADGET-B": 25},
            },
            "validator": {
                "engine": "python",
                "script": "data.get('inventory_check') == 'passed'",
            },
            "dep_ids": ["order_created"],
            "ts": base_ts + 100_000_000,  # +100ms
        },
        # 2b. Validate payment (hook) - parallel with inventory
        {
            "flow": flow,
            "id": "validate_payment",
            "description": "Validate payment method and available funds",
            "run_id": run_id,
            "type": "hook",
            "data": {
                "payment_valid": True,
                "card_last4": "4242",
                "available_credit": 5000.0,
            },
            "validator": {
                "engine": "python",
                "script": "data.get('payment_valid') == True",
            },
            "dep_ids": ["order_created"],
            "ts": base_ts + 120_000_000,  # +120ms
        },
        # 3a. Reserve inventory (act)
        {
            "flow": flow,
            "id": "reserve_inventory",
            "description": "Reserve inventory for order",
            "run_id": run_id,
            "type": "act",
            "data": {
                "reservation_id": "RES-99887",
                "reserved_items": ["WIDGET-A", "GADGET-B"],
            },
            "filter": {
                "engine": "python",
                "script": "data.get('reservation_id') is not None",
            },
            "dep_ids": ["validate_inventory"],
            "ts": base_ts + 250_000_000,  # +250ms
        },
        # 3b. Charge payment (act) - parallel with reserve
        {
            "flow": flow,
            "id": "charge_payment",
            "description": "Charge customer payment method",
            "run_id": run_id,
            "type": "act",
            "data": {
                "transaction_id": "TXN-554433",
                "amount_charged": 209.97,
                "status": "succeeded",
            },
            "filter": {
                "engine": "python",
                "script": "data.get('status') == 'succeeded'",
            },
            "dep_ids": ["validate_payment"],
            "ts": base_ts + 300_000_000,  # +300ms
        },
        # 4. Confirm order (hook)
        {
            "flow": flow,
            "id": "confirm_order",
            "description": "Confirm order after inventory and payment secured",
            "run_id": run_id,
            "type": "hook",
            "data": {
                "order_confirmed": True,
                "confirmation_number": "CONF-ABC123",
            },
            "validator": {
                "engine": "python",
                "script": "data.get('order_confirmed') == True",
            },
            "dep_ids": ["reserve_inventory", "charge_payment"],
            "ts": base_ts + 400_000_000,  # +400ms
        },
        # 5a. Notify warehouse (act)
        {
            "flow": flow,
            "id": "notify_warehouse",
            "description": "Send fulfillment notification to warehouse",
            "run_id": run_id,
            "type": "act",
            "data": {
                "warehouse_id": "WH-001",
                "notification_sent": True,
                "pick_list_id": "PICK-7788",
            },
            "filter": {
                "engine": "python",
                "script": "data.get('notification_sent') == True",
            },
            "dep_ids": ["confirm_order"],
            "ts": base_ts + 500_000_000,  # +500ms
        },
        # 5b. Notify customer (act) - parallel with warehouse
        {
            "flow": flow,
            "id": "notify_customer",
            "description": "Send order confirmation email to customer",
            "run_id": run_id,
            "type": "act",
            "data": {
                "email_sent": True,
                "email_id": "EMAIL-9988",
                "customer_email": "customer@example.com",
            },
            "filter": {
                "engine": "python",
                "script": "data.get('email_sent') == True",
            },
            "dep_ids": ["confirm_order"],
            "ts": base_ts + 520_000_000,  # +520ms
        },
        # 6. Ship order (act)
        {
            "flow": flow,
            "id": "ship_order",
            "description": "Ship order from warehouse",
            "run_id": run_id,
            "type": "act",
            "data": {
                "shipped": True,
                "carrier": "FedEx",
                "tracking_number": "1Z999AA10123456784",
                "estimated_delivery": "2025-10-24",
            },
            "filter": {
                "engine": "python",
                "script": "data.get('shipped') == True",
            },
            "dep_ids": ["notify_warehouse"],
            "ts": base_ts
            + 3600_000_000_000,  # +1 hour (simulating warehouse processing)
        },
        # 7. Update tracking (hook)
        {
            "flow": flow,
            "id": "update_tracking",
            "description": "Update order with tracking information",
            "run_id": run_id,
            "type": "hook",
            "data": {
                "tracking_updated": True,
                "tracking_url": "https://fedex.com/track/1Z999AA10123456784",
            },
            "validator": {
                "engine": "python",
                "script": "data.get('tracking_updated') == True",
            },
            "dep_ids": ["ship_order"],
            "ts": base_ts + 3650_000_000_000,  # +50ms after shipping
        },
    ]


async def main() -> None:
    """Main entry point - demonstrates complex flow with batch events and evaluation."""
    print("=" * 70)
    print("Complex E-Commerce Order Fulfillment Flow Test")
    print("=" * 70)
    print(f"\nAPI URL: {API_BASE_URL}")
    print(f"API Key: {API_KEY[:10]}..." if len(API_KEY) > 10 else "API Key: (not set)")
    print()

    # Generate unique run ID
    run_id = f"run_{int(time.time())}"
    print(f"Run ID: {run_id}\n")

    # Create events (nodes will be auto-created via batch endpoint with source='code')
    events = create_complex_flow_events(run_id)
    print(f"Created {len(events)} events for order fulfillment flow:")
    print("  1. order_created (trigger)")
    print("  2. validate_inventory + validate_payment (parallel hooks)")
    print("  3. reserve_inventory + charge_payment (parallel acts)")
    print("  4. confirm_order (hook - joins both paths)")
    print("  5. notify_warehouse + notify_customer (parallel acts)")
    print("  6. ship_order (act - depends on warehouse)")
    print("  7. update_tracking (hook - final step)")

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
            eval_result = await run_evaluation(client, run_id, "order_fulfillment")

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
                            error = item.get("error", "Unknown error")
                            print(f"  - {node_id}: {error}")

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
