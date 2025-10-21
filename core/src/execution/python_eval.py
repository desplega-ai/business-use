"""Python expression evaluator implementation.

This module provides a safe Python expression evaluator that can be
swapped out for other implementations (CEL, JS, etc) at desplega.ai.
"""

import logging

from src.models import Expr

logger = logging.getLogger(__name__)


class PythonEvaluator:
    """Python expression evaluator.

    Evaluates Python expressions in a restricted environment.
    Never raises exceptions - all errors are caught and logged.
    """

    def evaluate(self, expr: Expr, data: dict, ctx: dict) -> bool:
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
            # Execute expression in restricted environment
            # Only 'data' and 'ctx' are available as variables
            result = eval(
                expr.script,
                {"__builtins__": {}},  # No built-in functions
                {"data": data, "ctx": ctx},  # Only these variables
            )

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

    def evaluate(self, expr: Expr, data: dict, ctx: dict) -> bool:
        logger.error("CEL evaluator not implemented")
        return False


class JSEvaluator:
    """JavaScript expression evaluator (not implemented)."""

    def evaluate(self, expr: Expr, data: dict, ctx: dict) -> bool:
        logger.error("JavaScript evaluator not implemented")
        return False
