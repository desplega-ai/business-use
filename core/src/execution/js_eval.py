"""JavaScript expression evaluator implementation using QuickJS.

This module provides a safe JavaScript expression evaluator that can be
used alongside the Python evaluator for filter and validator expressions.
"""

import logging
from typing import Any

from quickjs import Function  # type: ignore[import-untyped]

from src.models import Expr

logger = logging.getLogger(__name__)


class JSEvaluator:
    """JavaScript expression evaluator using QuickJS.

    Evaluates JavaScript expressions in a sandboxed QuickJS environment.
    Never raises exceptions - all errors are caught and logged.
    """

    def eval_expr(self, script: str, variables: dict[str, Any]) -> Any:
        """Evaluate a JavaScript expression and return the result (any type).

        This is a lower-level method that returns the raw result without
        type checking. Use this when you need non-boolean returns (e.g., strings).

        Args:
            script: JavaScript expression to evaluate
            variables: Variables available in the expression (e.g., {"data": {...}, "ctx": {...}})

        Returns:
            Any: Result of evaluation (can be any type)

        Raises:
            Exception: If evaluation fails (caller should handle)

        Example:
            >>> evaluator = JSEvaluator()
            >>> evaluator.eval_expr("data.payment_id", {"data": {"payment_id": "pmt_123"}})
            "pmt_123"
        """
        # Build function parameters from variables
        param_names = list(variables.keys())
        param_values = [variables[name] for name in param_names]

        # Check if script contains 'return' keyword (indicates it's a function body)
        # This handles cases where SDK serialization didn't strip 'return' (e.g., with comments)
        if "return" in script:
            # Treat as function body - use script as-is
            function_code = f"""
            function evaluateExpr({", ".join(param_names)}) {{
                {script}
            }}
            """
        else:
            # Treat as expression - wrap with return
            function_code = f"""
            function evaluateExpr({", ".join(param_names)}) {{
                return {script};
            }}
            """

        # Create QuickJS function
        fn = Function("evaluateExpr", function_code)

        # Execute function with parameters
        result = fn(*param_values)
        return result

    def evaluate(self, expr: Expr, data: dict[str, Any], ctx: dict[str, Any]) -> bool:
        """Evaluate a JavaScript expression against data and context.

        Args:
            expr: Expression to evaluate (must have engine="js")
            data: Target data (current event data)
            ctx: Context data (typically {"deps": [...], "data": {...}})

        Returns:
            bool: Result of evaluation, False if error or non-JS engine

        Example:
            >>> evaluator = JSEvaluator()
            >>> expr = Expr(engine="js", script="data.amount > 0")
            >>> evaluator.evaluate(expr, {"amount": 100}, {})
            True
        """
        # Only handle JavaScript expressions
        if expr.engine != "js":
            logger.error(
                f"Unsupported expression engine: {expr.engine}. "
                f"JSEvaluator only supports 'js'."
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
            # Provide helpful error messages for common mistakes
            error_message = str(e)

            # Check for common context access mistakes
            if "ctx" in expr.script and (
                "deps" in error_message or "data" in error_message
            ):
                num_deps = len(ctx.get("deps", []))
                logger.error(
                    f"Failed to evaluate expression '{expr.script}': {e}\n"
                    f"Hint: Context structure is ctx.deps, not ctx.data.\n"
                    f"  - Available context keys: {list(ctx.keys())}\n"
                    f"  - Number of dependencies: {num_deps}\n"
                    f"  - For single dependency: Use ctx.data.field (auto-populated)\n"
                    f"  - For multiple dependencies: Use ctx.deps[i].data.field\n"
                    f"  - Structure: ctx.deps = [{{flow: str, id: str, data: dict}}, ...]"
                )
            elif "data" in expr.script:
                logger.error(
                    f"Failed to evaluate expression '{expr.script}': {e}\n"
                    f"Available data keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}\n"
                    f"Available context keys: {list(ctx.keys())}"
                )
            else:
                logger.error(
                    f"Failed to evaluate JavaScript expression '{expr.script}': {e}\n"
                    f"Hint: Available variables are 'data' (event data) and 'ctx' (context with dependencies)",
                    exc_info=True,
                )
            return False
