"""Business-Use Python SDK.

A lightweight SDK for tracking business events and assertions.

Example:
    >>> from business_use import initialize, act, assert_
    >>>
    >>> # Initialize the SDK
    >>> initialize(api_key="your-api-key")
    >>>
    >>> # Track an action
    >>> act(
    ...     id="payment_processed",
    ...     flow="checkout",
    ...     run_id="run_12345",
    ...     data={"amount": 100, "currency": "USD"}
    ... )
    >>>
    >>> # Track an assertion
    >>> def validate_total(data, ctx):
    ...     return data["total"] > 0
    >>>
    >>> assert_(
    ...     id="order_total_valid",
    ...     flow="checkout",
    ...     run_id="run_12345",
    ...     data={"total": 150},
    ...     validator=validate_total
    ... )
"""

import logging

from .client import act, assert_, initialize, shutdown

__version__ = "0.1.0"

__all__ = [
    "initialize",
    "act",
    "assert_",
    "shutdown",
]

# Configure logging with business-use prefix
logging.basicConfig(
    format="[business-use] [%(asctime)s] [%(levelname)s] %(message)s",
    level=logging.WARNING,
)
