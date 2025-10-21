"""Business-Use Python SDK.

A lightweight SDK for tracking business events and assertions.

Example:
    >>> from business_use import initialize, ensure
    >>>
    >>> # Initialize the SDK
    >>> initialize(api_key="your-api-key")
    >>>
    >>> # Track an action (no validator)
    >>> ensure(
    ...     id="payment_processed",
    ...     flow="checkout",
    ...     run_id="run_12345",
    ...     data={"amount": 100, "currency": "USD"}
    ... )
    >>>
    >>> # Track an assertion (with validator)
    >>> def validate_total(data, ctx):
    ...     return data["total"] > 0
    >>>
    >>> ensure(
    ...     id="order_total_valid",
    ...     flow="checkout",
    ...     run_id="run_12345",
    ...     data={"total": 150},
    ...     validator=validate_total
    ... )
"""

import logging

from .client import ensure, initialize, shutdown
from .models import NodeCondition

__version__ = "0.1.0"

__all__ = [
    "initialize",
    "ensure",
    "shutdown",
    "NodeCondition",
]

# Configure logging with business-use prefix
logging.basicConfig(
    format="[business-use] [%(asctime)s] [%(levelname)s] %(message)s",
    level=logging.WARNING,
)
