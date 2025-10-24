"""Tests for Python expression evaluator."""

import pytest

from src.execution.python_eval import PythonEvaluator
from src.models import Expr


@pytest.fixture
def evaluator():
    """Create a PythonEvaluator instance."""
    return PythonEvaluator()


class TestBasicExpressions:
    """Test basic Python expression evaluation."""

    def test_simple_comparison_greater_than(self, evaluator):
        """Test simple greater than comparison."""
        expr = Expr(engine="python", script="data['amount'] > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_simple_comparison_less_than(self, evaluator):
        """Test simple less than comparison."""
        expr = Expr(engine="python", script="data['amount'] < 1000")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_simple_comparison_equals(self, evaluator):
        """Test equality comparison."""
        expr = Expr(engine="python", script="data['amount'] == 100")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_simple_comparison_false(self, evaluator):
        """Test comparison that evaluates to false."""
        expr = Expr(engine="python", script="data['amount'] > 1000")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_string_equality(self, evaluator):
        """Test string equality comparison."""
        expr = Expr(engine="python", script="data['status'] == 'approved'")
        result = evaluator.evaluate(expr, {"status": "approved"}, {})
        assert result is True

    def test_string_inequality(self, evaluator):
        """Test string inequality."""
        expr = Expr(engine="python", script="data['status'] != 'rejected'")
        result = evaluator.evaluate(expr, {"status": "approved"}, {})
        assert result is True


class TestBooleanLogic:
    """Test boolean logic operations."""

    def test_and_operator(self, evaluator):
        """Test AND operator."""
        expr = Expr(
            engine="python", script="data['amount'] > 50 and data['amount'] < 200"
        )
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_and_operator_false(self, evaluator):
        """Test AND operator returning false."""
        expr = Expr(
            engine="python", script="data['amount'] > 50 and data['amount'] > 200"
        )
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_or_operator(self, evaluator):
        """Test OR operator."""
        expr = Expr(
            engine="python", script="data['amount'] < 50 or data['amount'] > 90"
        )
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_or_operator_false(self, evaluator):
        """Test OR operator returning false."""
        expr = Expr(
            engine="python", script="data['amount'] < 50 or data['amount'] > 200"
        )
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_not_operator(self, evaluator):
        """Test NOT operator."""
        expr = Expr(engine="python", script="not (data['amount'] > 1000)")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_complex_boolean_logic(self, evaluator):
        """Test complex boolean expression."""
        expr = Expr(
            engine="python",
            script="(data['amount'] > 50 and data['amount'] < 200) or data['status'] == 'vip'",
        )
        result = evaluator.evaluate(expr, {"amount": 100, "status": "normal"}, {})
        assert result is True


class TestContextAccess:
    """Test context access with dependencies."""

    def test_single_dependency_context(self, evaluator):
        """Test accessing context with single dependency."""
        expr = Expr(engine="python", script="ctx['data']['user_id'] == 'user_123'")
        ctx = {
            "deps": [{"flow": "test", "id": "node1", "data": {"user_id": "user_123"}}]
        }
        ctx["data"] = ctx["deps"][0]["data"]  # Convenience field
        result = evaluator.evaluate(expr, {}, ctx)
        assert result is True

    def test_multiple_dependencies_context(self, evaluator):
        """Test accessing context with multiple dependencies."""
        expr = Expr(
            engine="python",
            script="ctx['deps'][0]['data']['user_id'] == ctx['deps'][1]['data']['user_id']",
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
            engine="python",
            script="ctx['deps'][0]['data']['user_id'] != ctx['deps'][1]['data']['user_id']",
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
        expr = Expr(engine="python", script="ctx['data']['user_id'] == data['user_id']")
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
        expr = Expr(engine="python", script="data['price'] == 99.99")
        result = evaluator.evaluate(expr, {"price": 99.99}, {})
        assert result is True

    def test_boolean_value(self, evaluator):
        """Test boolean value."""
        expr = Expr(engine="python", script="data['is_active'] == True")
        result = evaluator.evaluate(expr, {"is_active": True}, {})
        assert result is True

    def test_none_value(self, evaluator):
        """Test None value handling."""
        expr = Expr(engine="python", script="data['optional'] is None")
        result = evaluator.evaluate(expr, {"optional": None}, {})
        assert result is True

    def test_list_length(self, evaluator):
        """Test list length check."""
        expr = Expr(engine="python", script="len(data['items']) > 0")
        result = evaluator.evaluate(expr, {"items": [1, 2, 3]}, {})
        assert result is True

    def test_list_access(self, evaluator):
        """Test list element access."""
        expr = Expr(engine="python", script="data['items'][0] == 1")
        result = evaluator.evaluate(expr, {"items": [1, 2, 3]}, {})
        assert result is True

    def test_dict_in_data(self, evaluator):
        """Test nested dictionary access."""
        expr = Expr(engine="python", script="data['user']['name'] == 'John'")
        result = evaluator.evaluate(expr, {"user": {"name": "John"}}, {})
        assert result is True


class TestBuiltinFunctions:
    """Test available built-in functions."""

    def test_len_function(self, evaluator):
        """Test len() function."""
        expr = Expr(engine="python", script="len(data['items']) == 3")
        result = evaluator.evaluate(expr, {"items": [1, 2, 3]}, {})
        assert result is True

    def test_min_function(self, evaluator):
        """Test min() function."""
        expr = Expr(engine="python", script="min(data['values']) == 1")
        result = evaluator.evaluate(expr, {"values": [3, 1, 2]}, {})
        assert result is True

    def test_max_function(self, evaluator):
        """Test max() function."""
        expr = Expr(engine="python", script="max(data['values']) == 3")
        result = evaluator.evaluate(expr, {"values": [3, 1, 2]}, {})
        assert result is True

    def test_sum_function(self, evaluator):
        """Test sum() function."""
        expr = Expr(engine="python", script="sum(data['values']) == 6")
        result = evaluator.evaluate(expr, {"values": [1, 2, 3]}, {})
        assert result is True

    def test_str_function(self, evaluator):
        """Test str() conversion."""
        expr = Expr(engine="python", script="str(data['number']) == '123'")
        result = evaluator.evaluate(expr, {"number": 123}, {})
        assert result is True

    def test_int_function(self, evaluator):
        """Test int() conversion."""
        expr = Expr(engine="python", script="int(data['string']) == 123")
        result = evaluator.evaluate(expr, {"string": "123"}, {})
        assert result is True

    def test_float_function(self, evaluator):
        """Test float() conversion."""
        expr = Expr(engine="python", script="float(data['string']) == 123.45")
        result = evaluator.evaluate(expr, {"string": "123.45"}, {})
        assert result is True

    def test_bool_function(self, evaluator):
        """Test bool() conversion."""
        expr = Expr(engine="python", script="bool(data['value']) == True")
        result = evaluator.evaluate(expr, {"value": 1}, {})
        assert result is True


class TestErrorHandling:
    """Test error handling behavior."""

    def test_wrong_engine(self, evaluator):
        """Test that wrong engine returns False."""
        expr = Expr(engine="js", script="data.amount > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_non_boolean_return(self, evaluator):
        """Test that non-boolean return values are caught."""
        expr = Expr(engine="python", script="data['amount']")  # Returns number
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_missing_data_field(self, evaluator):
        """Test that missing data fields are handled gracefully."""
        expr = Expr(engine="python", script="data['nonexistent'] > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_syntax_error(self, evaluator):
        """Test that syntax errors are handled gracefully."""
        expr = Expr(engine="python", script="data['amount'] > >")  # Invalid syntax
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_empty_context(self, evaluator):
        """Test expression with empty context."""
        expr = Expr(engine="python", script="data['amount'] > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_name_error(self, evaluator):
        """Test that undefined variables are handled."""
        expr = Expr(engine="python", script="undefined_var > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_type_error(self, evaluator):
        """Test that type errors are handled."""
        expr = Expr(engine="python", script="data['string'] > 0")
        result = evaluator.evaluate(expr, {"string": "not a number"}, {})
        assert result is False


class TestEvalExpr:
    """Test the eval_expr method (lower-level evaluation)."""

    def test_eval_expr_returns_string(self, evaluator):
        """Test eval_expr can return non-boolean values."""
        result = evaluator.eval_expr(
            "data['payment_id']", {"data": {"payment_id": "pmt_123"}}
        )
        assert result == "pmt_123"

    def test_eval_expr_returns_number(self, evaluator):
        """Test eval_expr returns numbers."""
        result = evaluator.eval_expr("data['amount'] * 2", {"data": {"amount": 50}})
        assert result == 100

    def test_eval_expr_returns_boolean(self, evaluator):
        """Test eval_expr returns booleans."""
        result = evaluator.eval_expr("data['amount'] > 0", {"data": {"amount": 100}})
        assert result is True

    def test_eval_expr_with_context(self, evaluator):
        """Test eval_expr with context parameter."""
        ctx = {
            "deps": [{"flow": "test", "id": "node1", "data": {"user_id": "user_123"}}]
        }
        ctx["data"] = ctx["deps"][0]["data"]
        result = evaluator.eval_expr("ctx['data']['user_id']", {"data": {}, "ctx": ctx})
        assert result == "user_123"

    def test_eval_expr_list_comprehension(self, evaluator):
        """Test eval_expr with list comprehension."""
        result = evaluator.eval_expr(
            "[x * 2 for x in data['values']]", {"data": {"values": [1, 2, 3]}}
        )
        assert result == [2, 4, 6]

    def test_eval_expr_dict_comprehension(self, evaluator):
        """Test eval_expr with dict comprehension."""
        result = evaluator.eval_expr(
            "{k: v * 2 for k, v in data['pairs'].items()}",
            {"data": {"pairs": {"a": 1, "b": 2}}},
        )
        assert result == {"a": 2, "b": 4}


class TestComplexExpressions:
    """Test more complex Python expressions."""

    def test_in_operator(self, evaluator):
        """Test 'in' operator."""
        expr = Expr(engine="python", script="'important' in data['tags']")
        result = evaluator.evaluate(expr, {"tags": ["urgent", "important"]}, {})
        assert result is True

    def test_not_in_operator(self, evaluator):
        """Test 'not in' operator."""
        expr = Expr(engine="python", script="'spam' not in data['tags']")
        result = evaluator.evaluate(expr, {"tags": ["urgent", "important"]}, {})
        assert result is True

    def test_string_methods(self, evaluator):
        """Test string method calls."""
        expr = Expr(engine="python", script="data['name'].lower() == 'john'")
        result = evaluator.evaluate(expr, {"name": "JOHN"}, {})
        assert result is True

    def test_string_startswith(self, evaluator):
        """Test string startswith method."""
        expr = Expr(engine="python", script="data['id'].startswith('user_')")
        result = evaluator.evaluate(expr, {"id": "user_123"}, {})
        assert result is True

    def test_string_endswith(self, evaluator):
        """Test string endswith method."""
        expr = Expr(engine="python", script="data['email'].endswith('@example.com')")
        result = evaluator.evaluate(expr, {"email": "test@example.com"}, {})
        assert result is True

    def test_list_comprehension_in_expression(self, evaluator):
        """Test list comprehension in boolean expression."""
        expr = Expr(
            engine="python", script="len([x for x in data['values'] if x > 5]) > 0"
        )
        result = evaluator.evaluate(expr, {"values": [1, 6, 3, 8]}, {})
        assert result is True

    def test_ternary_expression(self, evaluator):
        """Test ternary conditional expression."""
        expr = Expr(engine="python", script="True if data['amount'] > 100 else False")
        result = evaluator.evaluate(expr, {"amount": 150}, {})
        assert result is True


class TestRandomFunctions:
    """Test random number generation functions."""

    def test_randint_available(self, evaluator):
        """Test that randint is available and works."""
        expr = Expr(engine="python", script="randint(1, 10) >= 1")
        # Run multiple times to ensure it works consistently
        for _ in range(5):
            result = evaluator.evaluate(expr, {}, {})
            assert result is True

    def test_random_available(self, evaluator):
        """Test that random is available and works."""
        expr = Expr(engine="python", script="random() >= 0 and random() <= 1")
        # Run multiple times to ensure it works consistently
        for _ in range(5):
            result = evaluator.evaluate(expr, {}, {})
            assert result is True

    def test_randint_in_range(self, evaluator):
        """Test randint generates values in correct range."""
        result = evaluator.eval_expr("randint(5, 5)", {})
        assert result == 5

    def test_random_in_range(self, evaluator):
        """Test random generates values between 0 and 1."""
        result = evaluator.eval_expr("random()", {})
        assert 0 <= result <= 1
