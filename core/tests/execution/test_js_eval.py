"""Tests for JavaScript expression evaluator."""

import pytest

from src.execution.js_eval import JSEvaluator
from src.models import Expr


@pytest.fixture
def evaluator():
    """Create a JSEvaluator instance."""
    return JSEvaluator()


class TestBasicExpressions:
    """Test basic JavaScript expression evaluation."""

    def test_simple_comparison_greater_than(self, evaluator):
        """Test simple greater than comparison."""
        expr = Expr(engine="js", script="data.amount > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_simple_comparison_less_than(self, evaluator):
        """Test simple less than comparison."""
        expr = Expr(engine="js", script="data.amount < 1000")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_simple_comparison_equals(self, evaluator):
        """Test equality comparison."""
        expr = Expr(engine="js", script="data.amount === 100")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_simple_comparison_false(self, evaluator):
        """Test comparison that evaluates to false."""
        expr = Expr(engine="js", script="data.amount > 1000")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_string_equality(self, evaluator):
        """Test string equality comparison."""
        expr = Expr(engine="js", script='data.status === "approved"')
        result = evaluator.evaluate(expr, {"status": "approved"}, {})
        assert result is True

    def test_string_inequality(self, evaluator):
        """Test string inequality."""
        expr = Expr(engine="js", script='data.status !== "rejected"')
        result = evaluator.evaluate(expr, {"status": "approved"}, {})
        assert result is True


class TestBooleanLogic:
    """Test boolean logic operations."""

    def test_and_operator(self, evaluator):
        """Test AND operator."""
        expr = Expr(engine="js", script="data.amount > 50 && data.amount < 200")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_and_operator_false(self, evaluator):
        """Test AND operator returning false."""
        expr = Expr(engine="js", script="data.amount > 50 && data.amount > 200")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_or_operator(self, evaluator):
        """Test OR operator."""
        expr = Expr(engine="js", script="data.amount < 50 || data.amount > 90")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_or_operator_false(self, evaluator):
        """Test OR operator returning false."""
        expr = Expr(engine="js", script="data.amount < 50 || data.amount > 200")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_not_operator(self, evaluator):
        """Test NOT operator."""
        expr = Expr(engine="js", script="!(data.amount > 1000)")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_complex_boolean_logic(self, evaluator):
        """Test complex boolean expression."""
        expr = Expr(
            engine="js",
            script='(data.amount > 50 && data.amount < 200) || data.status === "vip"',
        )
        result = evaluator.evaluate(expr, {"amount": 100, "status": "normal"}, {})
        assert result is True


class TestContextAccess:
    """Test context access with dependencies."""

    def test_single_dependency_context(self, evaluator):
        """Test accessing context with single dependency."""
        expr = Expr(engine="js", script='ctx.data.user_id === "user_123"')
        ctx = {
            "deps": [{"flow": "test", "id": "node1", "data": {"user_id": "user_123"}}]
        }
        ctx["data"] = ctx["deps"][0]["data"]  # Convenience field
        result = evaluator.evaluate(expr, {}, ctx)
        assert result is True

    def test_multiple_dependencies_context(self, evaluator):
        """Test accessing context with multiple dependencies."""
        expr = Expr(
            engine="js", script="ctx.deps[0].data.user_id === ctx.deps[1].data.user_id"
        )
        ctx = {
            "deps": [
                {"flow": "test", "id": "node1", "data": {"user_id": "user_123"}},
                {"flow": "test", "id": "node2", "data": {"user_id": "user_123"}},
            ]
        }
        result = evaluator.evaluate(expr, {}, ctx)
        assert result is True

    def test_multiple_dependencies_different_values(self, evaluator):
        """Test multiple dependencies with different values."""
        expr = Expr(
            engine="js", script="ctx.deps[0].data.user_id !== ctx.deps[1].data.user_id"
        )
        ctx = {
            "deps": [
                {"flow": "test", "id": "node1", "data": {"user_id": "user_123"}},
                {"flow": "test", "id": "node2", "data": {"user_id": "user_456"}},
            ]
        }
        result = evaluator.evaluate(expr, {}, ctx)
        assert result is True

    def test_context_and_data_combined(self, evaluator):
        """Test using both context and data in expression."""
        expr = Expr(engine="js", script="ctx.data.user_id === data.user_id")
        ctx = {
            "deps": [{"flow": "test", "id": "node1", "data": {"user_id": "user_123"}}]
        }
        ctx["data"] = ctx["deps"][0]["data"]
        result = evaluator.evaluate(expr, {"user_id": "user_123"}, ctx)
        assert result is True


class TestDataTypes:
    """Test different data types."""

    def test_number_comparison(self, evaluator):
        """Test number comparison."""
        expr = Expr(engine="js", script="data.price === 99.99")
        result = evaluator.evaluate(expr, {"price": 99.99}, {})
        assert result is True

    def test_boolean_value(self, evaluator):
        """Test boolean value."""
        expr = Expr(engine="js", script="data.is_active === true")
        result = evaluator.evaluate(expr, {"is_active": True}, {})
        assert result is True

    def test_null_value(self, evaluator):
        """Test null value handling."""
        expr = Expr(engine="js", script="data.optional === null")
        result = evaluator.evaluate(expr, {"optional": None}, {})
        assert result is True

    def test_array_length(self, evaluator):
        """Test array length check."""
        expr = Expr(engine="js", script="data.items.length > 0")
        result = evaluator.evaluate(expr, {"items": [1, 2, 3]}, {})
        assert result is True

    def test_array_access(self, evaluator):
        """Test array element access."""
        expr = Expr(engine="js", script="data.items[0] === 1")
        result = evaluator.evaluate(expr, {"items": [1, 2, 3]}, {})
        assert result is True


class TestErrorHandling:
    """Test error handling behavior."""

    def test_wrong_engine(self, evaluator):
        """Test that wrong engine returns False."""
        expr = Expr(engine="python", script="data['amount'] > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_non_boolean_return(self, evaluator):
        """Test that non-boolean return values are caught."""
        expr = Expr(engine="js", script="data.amount")  # Returns number, not boolean
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_missing_data_field(self, evaluator):
        """Test that missing data fields are handled gracefully."""
        expr = Expr(engine="js", script="data.nonexistent > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_syntax_error(self, evaluator):
        """Test that syntax errors are handled gracefully."""
        expr = Expr(engine="js", script="data.amount > >")  # Invalid syntax
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_empty_context(self, evaluator):
        """Test expression with empty context."""
        expr = Expr(engine="js", script="data.amount > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True


class TestEvalExpr:
    """Test the eval_expr method (lower-level evaluation)."""

    def test_eval_expr_returns_string(self, evaluator):
        """Test eval_expr can return non-boolean values."""
        result = evaluator.eval_expr(
            "data.payment_id", {"data": {"payment_id": "pmt_123"}}
        )
        assert result == "pmt_123"

    def test_eval_expr_returns_number(self, evaluator):
        """Test eval_expr returns numbers."""
        result = evaluator.eval_expr("data.amount * 2", {"data": {"amount": 50}})
        assert result == 100

    def test_eval_expr_returns_boolean(self, evaluator):
        """Test eval_expr returns booleans."""
        result = evaluator.eval_expr("data.amount > 0", {"data": {"amount": 100}})
        assert result is True

    def test_eval_expr_with_context(self, evaluator):
        """Test eval_expr with context parameter."""
        ctx = {
            "deps": [{"flow": "test", "id": "node1", "data": {"user_id": "user_123"}}]
        }
        ctx["data"] = ctx["deps"][0]["data"]
        result = evaluator.eval_expr("ctx.data.user_id", {"data": {}, "ctx": ctx})
        assert result == "user_123"


class TestComplexExpressions:
    """Test more complex JavaScript expressions."""

    def test_ternary_operator(self, evaluator):
        """Test ternary operator returns boolean."""
        expr = Expr(engine="js", script="data.amount > 100 ? true : false")
        result = evaluator.evaluate(expr, {"amount": 150}, {})
        assert result is True

    def test_object_property_access(self, evaluator):
        """Test nested object property access."""
        expr = Expr(engine="js", script='data.user.name === "John"')
        result = evaluator.evaluate(expr, {"user": {"name": "John"}}, {})
        assert result is True

    def test_method_call(self, evaluator):
        """Test calling JavaScript methods."""
        expr = Expr(engine="js", script='data.name.toLowerCase() === "john"')
        result = evaluator.evaluate(expr, {"name": "JOHN"}, {})
        assert result is True

    def test_array_method(self, evaluator):
        """Test array method call."""
        expr = Expr(engine="js", script='data.tags.includes("important")')
        result = evaluator.evaluate(expr, {"tags": ["urgent", "important"]}, {})
        assert result is True

    def test_regex_test(self, evaluator):
        """Test regex matching."""
        expr = Expr(engine="js", script="/^user_/.test(data.id)")
        result = evaluator.evaluate(expr, {"id": "user_123"}, {})
        assert result is True


class TestReturnStatements:
    """Test scripts containing return statements (SDK serialization edge cases)."""

    def test_script_with_return_statement(self, evaluator):
        """Test script with explicit return statement."""
        expr = Expr(engine="js", script="return data.amount > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_multiline_script_with_return(self, evaluator):
        """Test multi-line script with return statement."""
        script = """
        // Business rule check
        return data.item_count > 0 && data.total > 0
        """
        expr = Expr(engine="js", script=script)
        result = evaluator.evaluate(expr, {"item_count": 5, "total": 100}, {})
        assert result is True

    def test_script_with_comment_and_return(self, evaluator):
        """Test script with single-line comment before return."""
        script = """// Business Rule: Cart cannot be empty and must have positive total
return data.item_count > 0 && data.total > 0"""
        expr = Expr(engine="js", script=script)
        result = evaluator.evaluate(expr, {"item_count": 3, "total": 50.99}, {})
        assert result is True

    def test_script_with_multiline_comment_and_return(self, evaluator):
        """Test script with multi-line comment before return."""
        script = """/**
         * Validate cart state
         * - Must have items
         * - Must have positive total
         */
        return data.item_count > 0 && data.total > 0"""
        expr = Expr(engine="js", script=script)
        result = evaluator.evaluate(expr, {"item_count": 2, "total": 25.50}, {})
        assert result is True

    def test_script_with_return_false(self, evaluator):
        """Test script with return that evaluates to false."""
        script = """
        // Check if amount exceeds limit
        return data.amount > 1000
        """
        expr = Expr(engine="js", script=script)
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_script_with_return_and_context(self, evaluator):
        """Test script with return statement using context."""
        script = """
        // Verify user_id matches
        return data.user_id === ctx.data.user_id
        """
        expr = Expr(engine="js", script=script)
        ctx = {
            "deps": [{"flow": "test", "id": "node1", "data": {"user_id": "user_123"}}]
        }
        ctx["data"] = ctx["deps"][0]["data"]
        result = evaluator.evaluate(expr, {"user_id": "user_123"}, ctx)
        assert result is True

    def test_script_with_return_and_logic(self, evaluator):
        """Test script with return and complex boolean logic."""
        script = """
        // Multi-condition validation
        return (data.status === 'active' && data.amount > 0) || data.bypass === true
        """
        expr = Expr(engine="js", script=script)
        result = evaluator.evaluate(
            expr, {"status": "active", "amount": 50, "bypass": False}, {}
        )
        assert result is True

    def test_script_without_return_still_works(self, evaluator):
        """Test that scripts without return still work (backward compatibility)."""
        expr = Expr(engine="js", script="data.amount > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_script_return_with_string_containing_return(self, evaluator):
        """Test script where 'return' appears in a string."""
        # The word 'return' in a string should NOT trigger function body mode
        # This is a known limitation of the simple check
        script = """
        // Check if message contains 'return'
        return data.message.includes('return')
        """
        expr = Expr(engine="js", script=script)
        result = evaluator.evaluate(expr, {"message": "please return the item"}, {})
        assert result is True
