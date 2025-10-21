"""Example usage of the Business-Use Python SDK."""

import logging
import time

from business_use import act, assert_, initialize, shutdown

# Enable debug logging to see what's happening
logging.basicConfig(level=logging.DEBUG)

# Initialize the SDK
print("Initializing SDK...")
initialize(
    api_key="secret",
    url="http://localhost:13370",
    batch_size=5,  # Small batch for testing
    batch_interval=2,  # Flush every 2 seconds
)

# Track some business actions
print("\nTracking business actions...")

act(
    id="user_signup",
    flow="onboarding",
    run_id="run_001",
    data={"email": "alice@example.com", "plan": "premium"},
    description="User signed up for premium plan",
)

act(
    id="email_verified",
    flow="onboarding",
    run_id="run_001",
    data={"email": "alice@example.com"},
    dep_ids=["user_signup"],
    description="Email verified successfully",
)

# Track an assertion
print("\nTracking business assertions...")


def validate_payment(data, ctx):
    """Validate payment amount is positive and currency is supported."""
    return data["amount"] > 0 and data["currency"] in ["USD", "EUR", "GBP"]


assert_(
    id="payment_valid",
    flow="checkout",
    run_id="run_002",
    data={"amount": 99.99, "currency": "USD"},
    validator=validate_payment,
    dep_ids=["email_verified"],
    description="Payment validation check",
)

# Example with filter (this will be skipped)
act(
    id="debug_event",
    flow="diagnostics",
    run_id="run_003",
    data={"debug": True},
    filter=False,  # This event will be filtered out
    description="This should not be sent",
)

# Example with lambda filter (this will be sent)
act(
    id="production_event",
    flow="diagnostics",
    run_id="run_003",
    data={"production": True},
    filter=lambda: True,  # This event will be sent
    description="This should be sent",
)

# Example with lambda run_id
act(
    id="dynamic_run",
    flow="testing",
    run_id=lambda: f"dynamic_{int(time.time())}",
    data={"test": True},
    description="Using dynamic run ID",
)

print("\nWaiting for batches to be sent...")
print("(Check the logs above for batch processing)")

# Wait a bit for batches to be processed
time.sleep(3)

# Gracefully shutdown
print("\nShutting down SDK...")
shutdown(timeout=5.0)

print("\nDone! Check if the backend received the events.")
