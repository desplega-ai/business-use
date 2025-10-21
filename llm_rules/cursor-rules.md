# Cursor Rules for Business-Use Integration

These rules help Cursor AI (or similar tools) integrate Business-Use SDK into codebases effectively.

## When to Suggest Business-Use

Suggest Business-Use when you see:
- Multi-step business processes with dependencies
- Critical user journeys (signup, checkout, publishing, etc.)
- Code with business validation logic
- Functions that modify state across multiple entities
- Operations where ordering matters

## Integration Principles

### 1. Always Ask First
Before suggesting instrumentation:
- Ask what the application does
- Identify critical business flows
- Understand which flows cause issues
- Confirm business importance with the user

### 2. Track Business Events, Not Technical Details
**Good candidates:**
- User registration completed
- Order placed and confirmed
- Content published to production
- Subscription upgraded
- Data migration completed

**Bad candidates:**
- Database query executed
- Cache hit/miss
- HTTP request logged
- Function called
- Variable updated

### 3. Instrument at the Service Layer
Add `ensure()` calls in:
- ✅ Service classes/modules
- ✅ Business logic functions
- ✅ Domain layer
- ✅ Use case handlers

Avoid instrumenting:
- ❌ Controllers/route handlers
- ❌ Database repositories
- ❌ Middleware
- ❌ Utility functions

### 4. Use the Unified `ensure()` API

**Action nodes** (events without validation):
```python
ensure(
    id="action_completed",
    flow="business_flow",
    run_id=identifier,
    data={"key": "value"}
)
```

**Assertion nodes** (events with validation):
```python
ensure(
    id="validation_passed",
    flow="business_flow",
    run_id=identifier,
    data={"key": "value"},
    validator=lambda data, ctx: data["key"] == "expected_value"
)
```

### 5. Node ID Naming Convention
Use descriptive, past-tense names:
- ✅ `user_registered`, `order_placed`, `payment_processed`
- ❌ `step_1`, `event_a`, `do_thing`

### 6. Keep Flow Names Consistent
Within the same business process, always use the same flow name:
```python
ensure(id="started", flow="checkout", ...)
ensure(id="validated", flow="checkout", ...)  # Same flow name
ensure(id="completed", flow="checkout", ...)  # Same flow name
```

### 7. Use Same run_id for Entire Flow
The `run_id` connects all events in a flow:
```python
order_id = "ord_123"
ensure(id="created", flow="checkout", run_id=order_id, ...)
ensure(id="paid", flow="checkout", run_id=order_id, ...)
ensure(id="shipped", flow="checkout", run_id=order_id, ...)
```

## Code Patterns

### Pattern: Service Method Instrumentation

**Before:**
```python
class OrderService:
    def place_order(self, user_id: str, items: list) -> Order:
        order = Order.create(user_id, items)
        payment = PaymentService.process(order)
        if payment.success:
            order.mark_as_paid()
        return order
```

**After:**
```python
from business_use import ensure

class OrderService:
    def place_order(self, user_id: str, items: list) -> Order:
        order = Order.create(user_id, items)

        ensure(
            id="order_created",
            flow="checkout",
            run_id=order.id,
            data={"user_id": user_id, "items": items}
        )

        payment = PaymentService.process(order)

        ensure(
            id="payment_processed",
            flow="checkout",
            run_id=order.id,
            data={"amount": payment.amount, "status": payment.status},
            dep_ids=["order_created"],
            validator=lambda data, ctx: data["status"] == "success"
        )

        if payment.success:
            order.mark_as_paid()
        return order
```

### Pattern: Initialization (App Startup)

**Python (Flask/Django):**
```python
# app.py or manage.py
from business_use import initialize
import os

initialize(
    api_key=os.getenv("BUSINESS_USE_API_KEY"),
    url=os.getenv("BUSINESS_USE_URL", "http://localhost:13370")
)
```

**JavaScript (Express/NestJS):**
```typescript
// main.ts
import { initialize } from 'business-use';

initialize({
  apiKey: process.env.BUSINESS_USE_API_KEY,
  url: process.env.BUSINESS_USE_URL || 'http://localhost:13370'
});
```

### Pattern: Using Dependencies

When steps must happen in order:
```python
ensure(id="step_1", flow="process", run_id=id, data=...)

ensure(
    id="step_2",
    flow="process",
    run_id=id,
    dep_ids=["step_1"],  # Must happen after step_1
    data=...
)

ensure(
    id="step_3",
    flow="process",
    run_id=id,
    dep_ids=["step_2"],  # Must happen after step_2
    data=...
)
```

### Pattern: Validators for Business Rules

Add validators when there are business rules to enforce:

```python
# Example: Validate discount is applied correctly
ensure(
    id="discount_applied",
    flow="checkout",
    run_id=order_id,
    data={"original": 100, "discounted": 80},
    validator=lambda data, ctx: data["discounted"] < data["original"]
)

# Example: Validate user tier matches benefits
ensure(
    id="benefits_assigned",
    flow="subscription",
    run_id=user_id,
    data={"tier": "premium", "free_shipping": True},
    validator=lambda data, ctx: (
        data["tier"] == "premium" and data["free_shipping"] == True
    )
)
```

### Pattern: Conditional Tracking with Filters

Skip events based on conditions:
```python
ensure(
    id="notification_sent",
    flow="order",
    run_id=order_id,
    data={"type": "email"},
    filter=lambda data: user.wants_notifications,  # Only track if true
)
```

## Quick Reference

### Installation
```bash
# Python
pip install business-use

# JavaScript
npm install business-use
```

### Basic Usage
```python
from business_use import initialize, ensure

# Initialize once
initialize(api_key="key")

# Track events
ensure(id="event_id", flow="flow_name", run_id="unique_id", data={...})
```

### Validation
```bash
# CLI
uvx business-use-core eval-run <run_id> <flow> --verbose

# API
curl -X POST http://localhost:13370/v1/run-eval \
  -H "X-Api-Key: key" \
  -d '{"run_id": "id", "flow": "flow_name"}'
```

## Things to Avoid

1. **Don't track too granularly** - Focus on business events, not every function
2. **Don't assume importance** - Ask user which flows matter most
3. **Don't use generic IDs** - Use descriptive names (not "step_1", "event_a")
4. **Don't forget dependencies** - Use `dep_ids` when order matters
5. **Don't skip validators** - Add them for business rule checkpoints
6. **Don't instrument controllers** - Use service/business layer
7. **Don't hardcode examples** - Use generic terms until user confirms context

## Interactive Workflow

1. **Analyze** - Scan codebase for business logic
2. **Ask** - Confirm business context and priorities with user
3. **Propose** - Show flow structure and instrumentation points
4. **Confirm** - Wait for user approval before implementing
5. **Implement** - Add instrumentation with proper error handling
6. **Validate** - Show how to test the instrumentation

## Remember

- Business-Use tracks **business outcomes**, not technical events
- Always **ask before instrumenting** - don't assume
- **One flow** at a time - start small, expand based on value
- **Test after adding** - ensure events are being tracked
- **Include context** in `data` for debugging

---

For detailed usage, see: `llm_rules/sdk-usage.md`
For auto-instrumentation workflow, see: `.claude/commands/auto-instrument.md`
