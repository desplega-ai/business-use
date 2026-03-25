"""
Basic flow — happy path. All literal values, direct imports.
Scanner should extract all 3 nodes perfectly.
"""
from business_use import ensure


# Root node — no dependencies
ensure(
    id="cart_created",
    flow="checkout",
    run_id=lambda: get_run_id(),
    data={"items": cart.items},
    description="Shopping cart was created",
)

# Depends on cart_created
ensure(
    id="payment_processed",
    flow="checkout",
    run_id=lambda: get_run_id(),
    data={"amount": payment.amount, "currency": "USD"},
    dep_ids=["cart_created"],
    description="Payment was processed successfully",
    conditions=[{"timeout_ms": 5000}],
)

# Assert node — has validator
ensure(
    id="order_total_matches",
    flow="checkout",
    run_id=lambda: get_run_id(),
    data={"total": order.total},
    dep_ids=["cart_created", "payment_processed"],
    validator=lambda data, ctx: data["total"] == sum(d["data"]["amount"] for d in ctx["deps"]),
    description="Order total matches sum of payments",
)
