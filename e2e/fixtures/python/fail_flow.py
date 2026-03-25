"""E2E fixture: checkout flow that should FAIL evaluation.

The payment_processed node sends status="declined" which fails the validator.
"""

import os
import time

from business_use import NodeCondition, act, assert_, initialize, shutdown

run_id = os.environ.get("E2E_RUN_ID", f"py_fail_{int(time.time())}")
api_key = os.environ.get("BUSINESS_USE_API_KEY", "test-e2e-key")
url = os.environ.get("BUSINESS_USE_URL", "http://localhost:13399")

initialize(api_key=api_key, url=url, batch_size=10, batch_interval=1)

# Step 1: Cart Created
act(
    id="cart_created",
    flow="checkout",
    run_id=run_id,
    data={"cart_id": "cart_002", "total": 99.99, "currency": "USD"},
    description="Shopping cart initialized",
)

# Step 2: Inventory Reserved
act(
    id="inventory_reserved",
    flow="checkout",
    run_id=run_id,
    data={"cart_id": "cart_002", "reservation_id": "res_002", "items_reserved": 2},
    dep_ids=["cart_created"],
    conditions=[NodeCondition(timeout_ms=5000)],
    description="Inventory reserved for cart items",
)

# Step 3: Payment Processed — DELIBERATELY FAILS (status="declined")
assert_(
    id="payment_processed",
    flow="checkout",
    run_id=run_id,
    data={
        "cart_id": "cart_002",
        "payment_id": "pay_002",
        "amount": 99.99,
        "currency": "USD",
        "status": "declined",  # <-- This will fail the validator
    },
    validator=lambda data, ctx: data.get("status") == "success" and data.get("amount", 0) > 0,
    dep_ids=["inventory_reserved"],
    conditions=[NodeCondition(timeout_ms=10000)],
    description="Payment processed and validated",
)

# Step 4: Order Confirmed — valid data, but flow should still fail due to step 3
assert_(
    id="order_confirmed",
    flow="checkout",
    run_id=run_id,
    data={
        "order_id": "ord_002",
        "customer_email": "test@example.com",
        "total": 99.99,
        "status": "confirmed",
    },
    validator=lambda data, ctx: data.get("status") == "confirmed" and "@" in data.get("customer_email", ""),
    dep_ids=["payment_processed"],
    conditions=[NodeCondition(timeout_ms=3000)],
    description="Order confirmed",
)

time.sleep(2)
shutdown(timeout=5.0)
print(f"DONE run_id={run_id}")
