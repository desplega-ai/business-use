"""Tests for lambda and function serialization."""

from business_use.batch import BatchProcessor


class TestLambdaSerialization:
    """Test lambda and function serialization to extract just the body."""

    def test_simple_lambda(self):
        """Test simple lambda expression."""
        # Create a mock processor to access the serialization method
        processor = self._create_mock_processor()

        lambda_fn = lambda data, ctx: data["amount"] > 0
        result = processor._serialize_lambda(lambda_fn)

        assert result.engine == "python"
        assert result.script == 'data["amount"] > 0'

    def test_lambda_with_boolean_logic(self):
        """Test lambda with complex boolean expression."""
        processor = self._create_mock_processor()

        lambda_fn = lambda data, ctx: data["amount"] > 0 and data["currency"] in [
            "USD",
            "EUR",
        ]
        result = processor._serialize_lambda(lambda_fn)

        assert result.engine == "python"
        assert 'data["amount"] > 0' in result.script
        assert 'data["currency"]' in result.script
        assert "and" in result.script

    def test_lambda_no_params(self):
        """Test lambda with no parameters (filter)."""
        processor = self._create_mock_processor()

        lambda_fn = lambda: True
        result = processor._serialize_lambda(lambda_fn)

        assert result.engine == "python"
        assert result.script == "True"

    def test_multiline_lambda(self):
        """Test lambda that spans multiple lines."""
        processor = self._create_mock_processor()

        # This mimics a lambda defined across multiple lines in a function call
        lambda_fn = (
            lambda data, ctx: not data["is_first_run"] or data["allow_fix"] is True
        )
        result = processor._serialize_lambda(lambda_fn)

        assert result.engine == "python"
        # Should include both parts of the expression
        assert 'not data["is_first_run"]' in result.script
        assert 'data["allow_fix"]' in result.script
        assert " or " in result.script
        # Should not have trailing comma
        assert not result.script.endswith(",")

    def test_multiline_lambda_complex(self):
        """Test complex lambda with multiple conditions."""
        processor = self._create_mock_processor()

        lambda_fn = lambda data, ctx: (
            data["status"] == "active" and data["amount"] > 0 or data["bypass"] is True
        )
        result = processor._serialize_lambda(lambda_fn)

        assert result.engine == "python"
        assert 'data["status"]' in result.script
        assert 'data["amount"]' in result.script
        assert 'data["bypass"]' in result.script
        assert " and " in result.script
        assert " or " in result.script

    def test_simple_function_with_return(self):
        """Test function with simple return statement."""
        processor = self._create_mock_processor()

        def validate_payment(data, ctx):
            return data["amount"] > 0

        result = processor._serialize_lambda(validate_payment)

        assert result.engine == "python"
        assert result.script == 'data["amount"] > 0'

    def test_function_with_single_line_docstring(self):
        """Test function with single-line docstring."""
        processor = self._create_mock_processor()

        def validate_with_docs(data, ctx):
            """Validate payment is positive."""
            return data["amount"] > 0 and data["currency"] in ["USD", "EUR"]

        result = processor._serialize_lambda(validate_with_docs)

        assert result.engine == "python"
        # Should extract just the expression, not the docstring
        assert "Validate payment" not in result.script
        assert 'data["amount"] > 0' in result.script
        assert 'data["currency"]' in result.script

    def test_function_with_multiline_docstring(self):
        """Test function with multi-line docstring."""
        processor = self._create_mock_processor()

        def validate_complex(data, ctx):
            """
            Validate payment is positive.

            This is a longer docstring.
            """
            return data["amount"] > 0

        result = processor._serialize_lambda(validate_complex)

        assert result.engine == "python"
        assert "Validate payment" not in result.script
        assert "longer docstring" not in result.script
        assert 'data["amount"] > 0' in result.script

    def test_multiline_function(self):
        """Test function with multiple statements."""
        processor = self._create_mock_processor()

        def complex_validator(data, ctx):
            """Complex validation logic."""
            items_total = sum(item["price"] for item in data["items"])
            return data["total"] == items_total

        result = processor._serialize_lambda(complex_validator)

        assert result.engine == "python"
        # Should include both lines
        assert "items_total" in result.script
        assert 'data["total"]' in result.script
        # Should not include docstring
        assert "Complex validation" not in result.script

    def test_multiline_function_with_multiple_statements(self):
        """Test function with multiple lines and final return."""
        processor = self._create_mock_processor()

        def validate_order(data, ctx):
            """Validate order with complex logic."""
            # Calculate totals
            subtotal = sum(item["price"] * item["quantity"] for item in data["items"])
            tax = subtotal * 0.1
            shipping = 10 if subtotal < 100 else 0
            total = subtotal + tax + shipping
            # Final validation
            return abs(data["total"] - total) < 0.01

        result = processor._serialize_lambda(validate_order)

        assert result.engine == "python"
        # Should include all calculation lines
        assert "subtotal = " in result.script
        assert "tax = " in result.script
        assert "shipping = " in result.script
        assert "total = " in result.script
        # Should include the return statement
        assert "return" in result.script
        assert "abs(" in result.script
        # Should not include docstring or comments
        assert "Validate order" not in result.script
        assert "Calculate totals" not in result.script
        assert "Final validation" not in result.script

    def test_multiline_function_with_conditionals(self):
        """Test function with if/else statements."""
        processor = self._create_mock_processor()

        def validate_with_conditions(data, ctx):
            if data["type"] == "premium":
                min_amount = 100
            else:
                min_amount = 50
            return data["amount"] >= min_amount

        result = processor._serialize_lambda(validate_with_conditions)

        assert result.engine == "python"
        assert 'if data["type"]' in result.script
        assert "min_amount = 100" in result.script
        assert "else:" in result.script
        assert "min_amount = 50" in result.script
        assert "return" in result.script

    def test_function_with_comments(self):
        """Test that comments are stripped."""
        processor = self._create_mock_processor()

        def validate_with_comments(data, ctx):
            # This is a comment
            return data["amount"] > 0  # inline comment

        result = processor._serialize_lambda(validate_with_comments)

        assert result.engine == "python"
        # The return statement itself should be there
        assert 'data["amount"]' in result.script

    def test_async_function_rejected(self):
        """Test that async functions are handled (fallback)."""
        processor = self._create_mock_processor()

        async def async_validator(data, ctx):
            return data["amount"] > 0

        # Should not crash, but use fallback
        result = processor._serialize_lambda(async_validator)
        assert result.engine == "python"
        # Fallback will use string representation
        assert "async" in result.script or "<function" in result.script

    def _create_mock_processor(self):
        """Create a mock batch processor for testing serialization."""
        # We don't need a real processor, just need to instantiate it
        # Use dummy values since we're only testing the serialization method
        return BatchProcessor(
            api_key="test",
            base_url="http://localhost",
            batch_size=100,
            batch_interval=5,
            max_queue_size=1000,
        )


class TestFilterSerialization:
    """Test filter-specific serialization."""

    def test_bool_filter_not_serialized(self):
        """Test that bool filters (not callable) are not serialized."""
        # This would be handled in the batch.py logic, not serialization
        # Just documenting the behavior
        pass

    def test_callable_filter_serialized(self):
        """Test that callable filters are serialized."""
        processor = BatchProcessor(
            api_key="test",
            base_url="http://localhost",
            batch_size=100,
            batch_interval=5,
            max_queue_size=1000,
        )

        filter_fn = lambda: True
        result = processor._serialize_lambda(filter_fn)

        assert result.engine == "python"
        assert result.script == "True"


class TestValidatorSerialization:
    """Test validator-specific serialization."""

    def test_validator_with_context(self):
        """Test validator that uses both data and ctx parameters."""
        processor = BatchProcessor(
            api_key="test",
            base_url="http://localhost",
            batch_size=100,
            batch_interval=5,
            max_queue_size=1000,
        )

        def validator(data, ctx):
            upstream_data = ctx.get("upstream_data", {})
            return data["total"] >= upstream_data.get("total", 0)

        result = processor._serialize_lambda(validator)

        assert result.engine == "python"
        assert "upstream_data" in result.script
        assert "ctx.get" in result.script
        assert 'data["total"]' in result.script

    def test_validator_single_expression(self):
        """Test validator with single expression."""
        processor = BatchProcessor(
            api_key="test",
            base_url="http://localhost",
            batch_size=100,
            batch_interval=5,
            max_queue_size=1000,
        )

        validator = lambda data, ctx: data["amount"] > 0
        result = processor._serialize_lambda(validator)

        assert result.engine == "python"
        assert result.script == 'data["amount"] > 0'
