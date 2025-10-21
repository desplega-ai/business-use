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
from importlib.metadata import version

from .client import act, assert_, ensure, initialize, shutdown
from .models import NodeCondition

try:
    __version__ = version("business-use")
except Exception:
    __version__ = "0.0.0"  # Fallback for development

__all__ = [
    "initialize",
    "ensure",
    "shutdown",
    "act",
    "assert_",
    "NodeCondition",
]

# Configure logging with business-use prefix
logging.basicConfig(
    format="[business-use] [%(asctime)s] [%(levelname)s] %(message)s",
    level=logging.WARNING,
)
