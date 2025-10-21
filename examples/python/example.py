"""Example usage of the Business-Use Python SDK.

This example demonstrates a complete e-commerce checkout flow with:
- Multiple dependent nodes
- Filter functions to skip events conditionally
- Validator functions to assert business rules
- Timeout conditions between steps
"""

import logging
import time
from datetime import datetime

from business_use import NodeCondition, act, assert_, initialize, shutdown

# Enable debug logging to see what's happening
logging.basicConfig(level=logging.DEBUG)

# Initialize the SDK
print("Initializing SDK...")
initialize(
    api_key="secret",
    url="http://localhost:13370",
    batch_size=10,
    batch_interval=2,  # Flush every 2 seconds
)

print("\n" + "=" * 70)
print("EXAMPLE: E-Commerce Checkout Flow")
print("=" * 70)

# Simulate a checkout session
session_id = f"checkout_{int(time.time())}"
print(f"\nSession ID: {session_id}")

# Step 1: Cart Created (action node)
# This tracks when a user creates their shopping cart
print("\n[1/4] Creating shopping cart...")
act(
    id="cart_created",
    flow="checkout",
    run_id=session_id,
    data={
        "cart_id": "cart_12345",
        "items": [
            {"sku": "LAPTOP-001", "price": 999.99, "quantity": 1},
            {"sku": "MOUSE-042", "price": 29.99, "quantity": 2},
        ],
        "total": 1059.97,
        "currency": "USD",
        "timestamp": datetime.now().isoformat(),
    },
    description="Shopping cart initialized with items",
)

# Step 2: Inventory Reserved (action node with dependency and filter)
# Only reserve inventory if cart total is above $50
print("\n[2/4] Reserving inventory...")
act(
    id="inventory_reserved",
    flow="checkout",
    run_id=session_id,
    data={
        "cart_id": "cart_12345",
        "reservation_id": "res_98765",
        "items_reserved": 3,
        "total": 1059.97,
    },
    dep_ids=["cart_created"],  # Must happen after cart creation
    filter=lambda: True,  # Only process if total > 50 (evaluated client-side)
    conditions=[NodeCondition(timeout_ms=5000)],  # Must happen within 5s of cart
    description="Inventory reserved for cart items",
)

# Step 3: Payment Processed (assertion node with validation)
# This validates that payment was successful and amount matches cart total
print("\n[3/4] Processing payment...")


def validate_payment_success(data, ctx):
    """Validate payment was successful and amount is correct."""
    # Check payment status
    if data.get("status") != "success":
        print(f"  ❌ Payment failed with status: {data.get('status')}")
        return False

    # Verify amount is positive
    if data.get("amount", 0) <= 0:
        print(f"  ❌ Invalid payment amount: {data.get('amount')}")
        return False

    # Check currency is supported
    if data.get("currency") not in ["USD", "EUR", "GBP"]:
        print(f"  ❌ Unsupported currency: {data.get('currency')}")
        return False

    print(f"  ✅ Payment validated: ${data['amount']} {data['currency']}")
    return True


assert_(
    id="payment_processed",
    flow="checkout",
    run_id=session_id,
    data={
        "cart_id": "cart_12345",
        "payment_id": "pay_abc123",
        "amount": 1059.97,
        "currency": "USD",
        "status": "success",
        "payment_method": "credit_card",
        "last4": "4242",
    },
    validator=validate_payment_success,
    dep_ids=["inventory_reserved"],  # Must happen after inventory reservation
    conditions=[NodeCondition(timeout_ms=10000)],  # 10s timeout from inventory
    description="Payment processed and validated",
)

# Step 4: Order Confirmed (assertion node with complex validation)
# Final step that validates the entire order state
print("\n[4/4] Confirming order...")


def validate_order_confirmation(data, ctx):
    """Validate order confirmation contains all required fields."""
    required_fields = ["order_id", "customer_email", "total", "status"]

    # Check all required fields exist
    for field in required_fields:
        if field not in data:
            print(f"  ❌ Missing required field: {field}")
            return False

    # Validate email format (simple check)
    if "@" not in data.get("customer_email", ""):
        print(f"  ❌ Invalid email: {data.get('customer_email')}")
        return False

    # Validate order status
    if data.get("status") != "confirmed":
        print(f"  ❌ Order not confirmed: {data.get('status')}")
        return False

    print(f"  ✅ Order confirmed: {data['order_id']} for {data['customer_email']}")
    return True


assert_(
    id="order_confirmed",
    flow="checkout",
    run_id=session_id,
    data={
        "order_id": "ord_xyz789",
        "cart_id": "cart_12345",
        "customer_email": "alice@example.com",
        "total": 1059.97,
        "currency": "USD",
        "status": "confirmed",
        "items_count": 3,
        "shipping_address": {
            "street": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94102",
        },
    },
    validator=validate_order_confirmation,
    dep_ids=["payment_processed"],  # Must happen after payment
    conditions=[NodeCondition(timeout_ms=3000)],  # 3s timeout from payment
    additional_meta={
        "priority": "high",
        "source": "web_checkout",
        "version": "2.0",
    },
    description="Order confirmed and ready for fulfillment",
)

print("\n" + "=" * 70)
print("All events tracked! Flow summary:")
print("  cart_created → inventory_reserved → payment_processed → order_confirmed")
print("=" * 70)

print("\nWaiting for batches to be sent...")
print("(Check the logs above for batch processing)")

# Wait for batches to be processed
time.sleep(3)

# Gracefully shutdown
print("\nShutting down SDK...")
shutdown(timeout=5.0)

print("\n✅ Done! Check the backend to evaluate the flow.")
print(f"   Run: uv run cli eval-run {session_id} checkout --verbose")
