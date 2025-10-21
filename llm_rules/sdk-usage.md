# Business-Use SDK Usage Guide for LLMs

This guide teaches LLMs (Claude, ChatGPT, etc.) how to properly integrate Business-Use SDK into applications.

## Core Concepts

Business-Use tracks **business flows** - sequences of events that represent user journeys through your application. Each flow consists of **nodes** that can be:

- **Actions (`act`)**: Events that happened (e.g., "payment_processed")
- **Assertions (`assert`)**: Events with validation rules (e.g., "order_total_matches")

The SDK automatically determines the type based on whether a `validator` is provided.

## Installation

**Python:**
```bash
pip install business-use
```

**JavaScript:**
```bash
npm install business-use
# or: pnpm add business-use
```

## Basic Usage Pattern

### 1. Initialize Once (Application Startup)

**Python:**
```python
from business_use import initialize

# At application startup (e.g., in __main__ or app.py)
initialize(
    api_key="your-api-key",  # Or set BUSINESS_USE_API_KEY env var
    url="http://localhost:13370",  # Optional, defaults to localhost
)
```

**JavaScript:**
```typescript
import { initialize } from 'business-use';

// At application startup
initialize({
  apiKey: 'your-api-key',  // Or set BUSINESS_USE_API_KEY env var
  url: 'http://localhost:13370',  // Optional
});
```

### 2. Track Events with `ensure()`

**Python:**
```python
from business_use import ensure

# Action node (no validator)
ensure(
    id="payment_processed",
    flow="checkout",
    run_id=order_id,  # Unique identifier for this flow run
    data={"amount": 100.00, "currency": "USD"},
)

# Assertion node (with validator)
ensure(
    id="order_total_valid",
    flow="checkout",
    run_id=order_id,
    data={"total": 100.00, "items": [...]},
    validator=lambda data, ctx: data["total"] > 0,
    description="Order total must be positive"
)
```

**JavaScript:**
```typescript
import { ensure } from 'business-use';

// Action node (no validator)
ensure({
  id: 'payment_processed',
  flow: 'checkout',
  runId: orderId,  // Unique identifier for this flow run
  data: { amount: 100.00, currency: 'USD' },
});

// Assertion node (with validator)
ensure({
  id: 'order_total_valid',
  flow: 'checkout',
  runId: orderId,
  data: { total: 100.00, items: [...] },
  validator: (data, ctx) => data.total > 0,
  description: 'Order total must be positive'
});
```

## When to Use Business-Use

Use Business-Use to track **critical business flows** where:

1. **Order matters**: Events must happen in a specific sequence
2. **Dependencies exist**: Some events depend on others completing first
3. **Validation required**: Business rules must be enforced
4. **Debugging needed**: You need to understand why a flow failed

### Good Use Cases ✅

- **E-commerce checkout**: cart → payment → fulfillment → confirmation
- **User onboarding**: signup → email verification → profile completion
- **Payment processing**: initiate → validate → process → receipt
- **Order fulfillment**: order → inventory check → shipping → delivery
- **Multi-step workflows**: Any process with dependencies

### Poor Use Cases ❌

- **Simple logging**: Use standard logging libraries
- **Metrics/analytics**: Use Prometheus, DataDog, etc.
- **Unrelated events**: Events with no dependencies or order requirements
- **High-frequency events**: Events triggered thousands of times per second

## Integration Patterns

### Pattern 1: Service Layer Integration

Integrate at the service/business logic layer, not in controllers/routes.

**Python (Django/Flask):**
```python
# services/checkout.py
from business_use import ensure

class CheckoutService:
    def process_order(self, order_id: str, user_id: str, items: list):
        # Business logic
        cart = self._create_cart(items)

        # Track with Business-Use
        ensure(
            id="cart_created",
            flow="checkout",
            run_id=order_id,
            data={"user_id": user_id, "items": items}
        )

        # More business logic
        payment = self._process_payment(cart)

        ensure(
            id="payment_processed",
            flow="checkout",
            run_id=order_id,
            data={"amount": payment.amount, "status": payment.status},
            dep_ids=["cart_created"],
            validator=lambda data, ctx: data["status"] == "success"
        )

        return order
```

**JavaScript (Express/NestJS):**
```typescript
// services/checkout.service.ts
import { ensure } from 'business-use';

export class CheckoutService {
  async processOrder(orderId: string, userId: string, items: Item[]) {
    // Business logic
    const cart = await this.createCart(items);

    // Track with Business-Use
    ensure({
      id: 'cart_created',
      flow: 'checkout',
      runId: orderId,
      data: { userId, items }
    });

    // More business logic
    const payment = await this.processPayment(cart);

    ensure({
      id: 'payment_processed',
      flow: 'checkout',
      runId: orderId,
      data: { amount: payment.amount, status: payment.status },
      depIds: ['cart_created'],
      validator: (data) => data.status === 'success'
    });

    return order;
  }
}
```

### Pattern 2: Decorator Pattern

Use decorators to automatically track function calls.

**Python:**
```python
from business_use import ensure
from functools import wraps

def track_flow(flow: str, node_id: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Extract run_id from result or args
            run_id = result.get('id') if isinstance(result, dict) else str(args[0])

            ensure(
                id=node_id,
                flow=flow,
                run_id=run_id,
                data={"result": result}
            )

            return result
        return wrapper
    return decorator

@track_flow(flow="checkout", node_id="order_created")
def create_order(user_id: str, items: list):
    # Your business logic
    return {"id": "order_123", "items": items}
```

### Pattern 3: Context Manager Pattern

Use context managers for tracking start/end of operations.

**Python:**
```python
from business_use import ensure
from contextlib import contextmanager

@contextmanager
def track_operation(operation_id: str, flow: str, run_id: str):
    ensure(
        id=f"{operation_id}_started",
        flow=flow,
        run_id=run_id,
        data={"status": "started"}
    )

    try:
        yield
    except Exception as e:
        ensure(
            id=f"{operation_id}_failed",
            flow=flow,
            run_id=run_id,
            data={"error": str(e), "status": "failed"}
        )
        raise
    else:
        ensure(
            id=f"{operation_id}_completed",
            flow=flow,
            run_id=run_id,
            data={"status": "completed"}
        )

# Usage
with track_operation("payment_processing", "checkout", order_id):
    process_payment(order_id)
```

## Best Practices

### 1. Choose Meaningful Node IDs

**Good:**
```python
ensure(id="payment_processed", ...)  # Clear what happened
ensure(id="email_verification_sent", ...)  # Descriptive
```

**Bad:**
```python
ensure(id="step_1", ...)  # Not descriptive
ensure(id="event_a", ...)  # Meaningless
```

### 2. Use Consistent `run_id` Across Flow

The `run_id` ties events together. Use the same value for all events in a flow.

**Good:**
```python
order_id = "order_12345"

ensure(id="cart_created", flow="checkout", run_id=order_id, ...)
ensure(id="payment_initiated", flow="checkout", run_id=order_id, ...)
ensure(id="order_confirmed", flow="checkout", run_id=order_id, ...)
```

**Bad:**
```python
ensure(id="cart_created", flow="checkout", run_id="cart_001", ...)
ensure(id="payment_initiated", flow="checkout", run_id="payment_002", ...)  # Different!
```

### 3. Use `dep_ids` to Express Dependencies

Explicitly declare dependencies between nodes:

```python
ensure(id="payment_initiated", flow="checkout", run_id=order_id,
       dep_ids=["cart_created"], ...)

ensure(id="order_confirmed", flow="checkout", run_id=order_id,
       dep_ids=["payment_initiated"], ...)
```

### 4. Write Meaningful Validators

Validators should check **business rules**, not just technical conditions:

**Good:**
```python
# Business rule: discounted price must be less than original
validator=lambda data, ctx: data["discounted_price"] < ctx["product_info"]["original_price"]

# Business rule: premium users get free shipping
validator=lambda data, ctx: (
    ctx["user_signup"]["plan"] == "premium" and data["shipping_cost"] == 0
)
```

**Bad:**
```python
# Just checking existence (not a business rule)
validator=lambda data, ctx: "price" in data

# Always true (pointless validation)
validator=lambda data, ctx: True
```

### 5. Use Filters to Skip Irrelevant Events

Use `filter` to conditionally skip events:

```python
# Only track paid orders
ensure(
    id="order_confirmed",
    flow="checkout",
    run_id=order_id,
    data={"amount": amount},
    filter=lambda data: data["amount"] > 0,  # Skip free orders
)
```

### 6. Include Enough Context in `data`

Include data needed for validation and debugging:

**Good:**
```python
ensure(
    id="payment_processed",
    flow="checkout",
    run_id=order_id,
    data={
        "amount": 99.99,
        "currency": "USD",
        "payment_method": "credit_card",
        "transaction_id": "txn_123",
        "timestamp": datetime.now().isoformat()
    }
)
```

**Bad:**
```python
ensure(
    id="payment_processed",
    flow="checkout",
    run_id=order_id,
    data={"status": "ok"}  # Not enough context!
)
```

## Common Mistakes to Avoid

### ❌ Mistake 1: Tracking Every Function Call

Don't track low-level implementation details:

```python
# Bad - too granular
ensure(id="database_query_started", ...)
ensure(id="cache_lookup", ...)
ensure(id="response_serialized", ...)
```

Track **business-level events** instead:

```python
# Good - business events
ensure(id="order_created", ...)
ensure(id="payment_processed", ...)
ensure(id="order_shipped", ...)
```

### ❌ Mistake 2: Forgetting to Initialize

Always call `initialize()` before using `ensure()`:

```python
# Wrong - will silently fail (no-op mode)
ensure(id="payment_processed", ...)  # SDK not initialized!

# Correct
initialize(api_key="your-key")
ensure(id="payment_processed", ...)
```

### ❌ Mistake 3: Using Different `flow` Names

Keep flow names consistent across your codebase:

```python
# Bad - inconsistent naming
ensure(id="cart_created", flow="checkout_flow", ...)
ensure(id="payment_processed", flow="checkout", ...)  # Different name!

# Good - consistent naming
ensure(id="cart_created", flow="checkout", ...)
ensure(id="payment_processed", flow="checkout", ...)
```

### ❌ Mistake 4: Blocking on SDK Calls

The SDK is non-blocking, but don't await it:

```python
# Wrong - no need to await
await ensure(...)  # ensure() is not async!

# Correct
ensure(...)  # Returns immediately
```

## Environment Configuration

For production, use environment variables:

```bash
# .env file
BUSINESS_USE_API_KEY=your-production-key
BUSINESS_USE_URL=https://business-use.example.com
```

```python
# In your code
from business_use import initialize

# Will automatically use BUSINESS_USE_API_KEY and BUSINESS_USE_URL
initialize()
```

## Testing

In tests, you can either:

1. **Mock the SDK**:
```python
from unittest.mock import patch

with patch('business_use.ensure'):
    # Your test code - SDK calls are mocked
    my_function()
```

2. **Use a test backend**:
```python
initialize(
    api_key="test-key",
    url="http://localhost:13370"  # Local test instance
)
```

## Validation and Debugging

After tracking events, validate flows:

```bash
# CLI
uvx business-use-core eval-run order_12345 checkout --verbose

# HTTP API
curl -X POST http://localhost:13370/v1/run-eval \
  -H "X-Api-Key: your-key" \
  -d '{"run_id": "order_12345", "flow": "checkout"}'
```

## Summary

1. **Initialize once** at application startup
2. **Track business events** with `ensure()`
3. **Use consistent `run_id`** to tie events together
4. **Add `validator`** for business rule validation
5. **Use `dep_ids`** to express dependencies
6. **Include context** in `data` for debugging
7. **Validate flows** using CLI or API

## Questions?

- GitHub: https://github.com/desplega-ai/business-use
- Issues: https://github.com/desplega-ai/business-use/issues
