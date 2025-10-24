"""Tests for MultiEvaluator router."""

import pytest

from src.eval.eval import MultiEvaluator
from src.models import Expr


@pytest.fixture
def evaluator():
    """Create a MultiEvaluator instance."""
    return MultiEvaluator()


class TestPythonEngine:
    """Test MultiEvaluator routing to Python engine."""

    def test_python_simple_comparison(self, evaluator):
        """Test Python expression evaluation."""
        expr = Expr(engine="python", script="data['amount'] > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_python_string_comparison(self, evaluator):
        """Test Python string comparison."""
        expr = Expr(engine="python", script="data['status'] == 'approved'")
        result = evaluator.evaluate(expr, {"status": "approved"}, {})
        assert result is True

    def test_python_with_context(self, evaluator):
        """Test Python expression with context."""
        expr = Expr(engine="python", script="ctx['data']['user_id'] == 'user_123'")
        ctx = {
            "deps": [{"flow": "test", "id": "node1", "data": {"user_id": "user_123"}}]
        }
        ctx["data"] = ctx["deps"][0]["data"]
        result = evaluator.evaluate(expr, {}, ctx)
        assert result is True

    def test_python_boolean_logic(self, evaluator):
        """Test Python boolean logic."""
        expr = Expr(
            engine="python", script="data['amount'] > 50 and data['amount'] < 200"
        )
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True


class TestJavaScriptEngine:
    """Test MultiEvaluator routing to JavaScript engine."""

    def test_js_simple_comparison(self, evaluator):
        """Test JavaScript expression evaluation."""
        expr = Expr(engine="js", script="data.amount > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True

    def test_js_string_comparison(self, evaluator):
        """Test JavaScript string comparison."""
        expr = Expr(engine="js", script='data.status === "approved"')
        result = evaluator.evaluate(expr, {"status": "approved"}, {})
        assert result is True

    def test_js_with_context(self, evaluator):
        """Test JavaScript expression with context."""
        expr = Expr(engine="js", script='ctx.data.user_id === "user_123"')
        ctx = {
            "deps": [{"flow": "test", "id": "node1", "data": {"user_id": "user_123"}}]
        }
        ctx["data"] = ctx["deps"][0]["data"]
        result = evaluator.evaluate(expr, {}, ctx)
        assert result is True

    def test_js_boolean_logic(self, evaluator):
        """Test JavaScript boolean logic."""
        expr = Expr(engine="js", script="data.amount > 50 && data.amount < 200")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is True


class TestMixedEngines:
    """Test mixing Python and JavaScript in the same evaluator."""

    def test_python_and_js_same_data(self, evaluator):
        """Test that both engines evaluate the same data correctly."""
        py_expr = Expr(engine="python", script="data['amount'] > 50")
        js_expr = Expr(engine="js", script="data.amount > 50")

        data = {"amount": 100}
        py_result = evaluator.evaluate(py_expr, data, {})
        js_result = evaluator.evaluate(js_expr, data, {})

        assert py_result is True
        assert js_result is True
        assert py_result == js_result

    def test_python_and_js_negative_case(self, evaluator):
        """Test both engines return False for same failing condition."""
        py_expr = Expr(engine="python", script="data['amount'] > 1000")
        js_expr = Expr(engine="js", script="data.amount > 1000")

        data = {"amount": 100}
        py_result = evaluator.evaluate(py_expr, data, {})
        js_result = evaluator.evaluate(js_expr, data, {})

        assert py_result is False
        assert js_result is False

    def test_sequential_evaluations(self, evaluator):
        """Test evaluating multiple expressions sequentially."""
        data = {"amount": 100, "status": "approved"}

        # First evaluation - Python
        expr1 = Expr(engine="python", script="data['amount'] > 50")
        result1 = evaluator.evaluate(expr1, data, {})
        assert result1 is True

        # Second evaluation - JS
        expr2 = Expr(engine="js", script='data.status === "approved"')
        result2 = evaluator.evaluate(expr2, data, {})
        assert result2 is True

        # Third evaluation - Python
        expr3 = Expr(engine="python", script="data['amount'] < 200")
        result3 = evaluator.evaluate(expr3, data, {})
        assert result3 is True


class TestUnknownEngine:
    """Test handling of unknown engines."""

    def test_unknown_engine_cel(self, evaluator):
        """Test that CEL engine (not yet implemented) returns False."""
        expr = Expr(engine="cel", script="data.amount > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False


class TestContextHandling:
    """Test context handling across engines."""

    def test_python_multi_deps(self, evaluator):
        """Test Python with multiple dependencies."""
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

    def test_js_multi_deps(self, evaluator):
        """Test JavaScript with multiple dependencies."""
        expr = Expr(
            engine="js",
            script="ctx.deps[0].data.user_id === ctx.deps[1].data.user_id",
        )
        ctx = {
            "deps": [
                {"flow": "test", "id": "node1", "data": {"user_id": "user_123"}},
                {"flow": "test", "id": "node2", "data": {"user_id": "user_123"}},
            ]
        }
        result = evaluator.evaluate(expr, {}, ctx)
        assert result is True

    def test_python_single_dep_convenience(self, evaluator):
        """Test Python using single dep convenience field."""
        expr = Expr(engine="python", script="ctx['data']['user_id'] == 'user_123'")
        ctx = {
            "deps": [{"flow": "test", "id": "node1", "data": {"user_id": "user_123"}}]
        }
        ctx["data"] = ctx["deps"][0]["data"]  # Convenience field
        result = evaluator.evaluate(expr, {}, ctx)
        assert result is True

    def test_js_single_dep_convenience(self, evaluator):
        """Test JavaScript using single dep convenience field."""
        expr = Expr(engine="js", script='ctx.data.user_id === "user_123"')
        ctx = {
            "deps": [{"flow": "test", "id": "node1", "data": {"user_id": "user_123"}}]
        }
        ctx["data"] = ctx["deps"][0]["data"]  # Convenience field
        result = evaluator.evaluate(expr, {}, ctx)
        assert result is True


class TestDataAndContextCombined:
    """Test expressions using both data and context."""

    def test_python_data_and_context(self, evaluator):
        """Test Python expression using both data and context."""
        expr = Expr(
            engine="python",
            script="data['user_id'] == ctx['data']['user_id']",
        )
        ctx = {
            "deps": [{"flow": "test", "id": "node1", "data": {"user_id": "user_123"}}]
        }
        ctx["data"] = ctx["deps"][0]["data"]
        result = evaluator.evaluate(expr, {"user_id": "user_123"}, ctx)
        assert result is True

    def test_js_data_and_context(self, evaluator):
        """Test JavaScript expression using both data and context."""
        expr = Expr(engine="js", script="data.user_id === ctx.data.user_id")
        ctx = {
            "deps": [{"flow": "test", "id": "node1", "data": {"user_id": "user_123"}}]
        }
        ctx["data"] = ctx["deps"][0]["data"]
        result = evaluator.evaluate(expr, {"user_id": "user_123"}, ctx)
        assert result is True

    def test_python_complex_condition(self, evaluator):
        """Test complex Python condition with data and context."""
        expr = Expr(
            engine="python",
            script="data['amount'] > 0 and ctx['data']['approved'] == True",
        )
        ctx = {"deps": [{"flow": "test", "id": "node1", "data": {"approved": True}}]}
        ctx["data"] = ctx["deps"][0]["data"]
        result = evaluator.evaluate(expr, {"amount": 100}, ctx)
        assert result is True

    def test_js_complex_condition(self, evaluator):
        """Test complex JavaScript condition with data and context."""
        expr = Expr(
            engine="js",
            script="data.amount > 0 && ctx.data.approved === true",
        )
        ctx = {"deps": [{"flow": "test", "id": "node1", "data": {"approved": True}}]}
        ctx["data"] = ctx["deps"][0]["data"]
        result = evaluator.evaluate(expr, {"amount": 100}, ctx)
        assert result is True


class TestErrorPropagation:
    """Test that errors are handled correctly by both engines."""

    def test_python_missing_field(self, evaluator):
        """Test Python handles missing fields gracefully."""
        expr = Expr(engine="python", script="data['nonexistent'] > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_js_missing_field(self, evaluator):
        """Test JavaScript handles missing fields gracefully."""
        expr = Expr(engine="js", script="data.nonexistent > 0")
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_python_syntax_error(self, evaluator):
        """Test Python handles syntax errors gracefully."""
        expr = Expr(engine="python", script="data['amount' > 0")  # Missing ]
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False

    def test_js_syntax_error(self, evaluator):
        """Test JavaScript handles syntax errors gracefully."""
        expr = Expr(engine="js", script="data.amount > >")  # Invalid syntax
        result = evaluator.evaluate(expr, {"amount": 100}, {})
        assert result is False
