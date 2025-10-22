"""Python expression evaluator implementation.

This module provides a safe Python expression evaluator that can be
swapped out for other implementations (CEL, JS, etc) at desplega.ai.
"""

import logging
from typing import Any

from src.models import Expr

logger = logging.getLogger(__name__)


class PythonEvaluator:
    """Python expression evaluator.

    Evaluates Python expressions in a restricted environment.
    Never raises exceptions - all errors are caught and logged.
    """

    def eval_expr(self, script: str, variables: dict[str, Any]) -> Any:
        """Evaluate a Python expression and return the result (any type).

        This is a lower-level method that returns the raw result without
        type checking. Use this when you need non-boolean returns (e.g., strings).

        Args:
            script: Python expression to evaluate
            variables: Variables available in the expression (e.g., {"data": {...}, "input": {...}})

        Returns:
            Any: Result of evaluation (can be any type)

        Raises:
            Exception: If evaluation fails (caller should handle)

        Example:
            >>> evaluator = PythonEvaluator()
            >>> evaluator.eval_expr("data['payment_id']", {"data": {"payment_id": "pmt_123"}})
            "pmt_123"
        """
        # Example of allowed built-in imports
        from random import randint, random

        # Execute expression in restricted environment
        result = eval(
            script,
            {
                "__builtins__": {
                    "str": str,
                    "int": int,
                    "float": float,
                    "bool": bool,
                    "len": len,
                    "min": min,
                    "max": max,
                    "sum": sum,
                    "randint": randint,
                    "random": random,
                }
            },
            variables,
        )

        return result

    def evaluate(self, expr: Expr, data: dict[str, Any], ctx: dict[str, Any]) -> bool:
        """Evaluate a Python expression against data and context.

        Args:
            expr: Expression to evaluate (must have engine="python")
            data: Target data (current event data)
            ctx: Context data (typically {\"data\": upstream_event_data})

        Returns:
            bool: Result of evaluation, False if error or non-Python engine

        Example:
            >>> evaluator = PythonEvaluator()
            >>> expr = Expr(engine="python", script="data['amount'] > 0")
            >>> evaluator.evaluate(expr, {"amount": 100}, {})
            True
        """
        # Only handle Python expressions
        if expr.engine != "python":
            logger.error(
                f"Unsupported expression engine: {expr.engine}. "
                f"PythonEvaluator only supports 'python'."
            )
            return False

        try:
            # Use eval_expr for the actual evaluation
            result = self.eval_expr(expr.script, {"data": data, "ctx": ctx})

            # Ensure result is boolean
            if not isinstance(result, bool):
                logger.error(
                    f"Expression '{expr.script}' returned non-boolean: {type(result).__name__}"
                )
                return False

            return result

        except Exception as e:
            logger.error(
                f"Failed to evaluate Python expression '{expr.script}': {e}",
                exc_info=True,
            )
            return False


# Placeholder for future implementations
class CELEvaluator:
    """CEL expression evaluator (not implemented)."""

    def evaluate(self, expr: Expr, data: dict[str, Any], ctx: dict[str, Any]) -> bool:
        logger.error("CEL evaluator not implemented")
        return False


class JSEvaluator:
    """JavaScript expression evaluator (not implemented)."""

    def evaluate(self, expr: Expr, data: dict[str, Any], ctx: dict[str, Any]) -> bool:
        logger.error("JavaScript evaluator not implemented")
        return False
