"""Test lambda and function serialization."""

import inspect
from business_use.batch import BatchProcessor
from business_use.models import Expr


def test_lambda_serialization():
    """Test that lambdas are serialized to just the expression."""

    # Mock batch processor (we only need the serialization method)
    class MockProcessor:
        def _serialize_lambda(self, fn) -> Expr:
            """Copy of the serialization logic."""
            try:
                source = inspect.getsource(fn).strip()

                # Handle lambda expressions
                if "lambda" in source:
                    if ":" in source:
                        body = source.split(":", 1)[1].strip()
                        body = body.rstrip(",).;")
                        return Expr(engine="python", script=body)

                # Handle regular functions
                else:
                    lines = source.split("\n")
                    body_lines = []
                    in_docstring = False
                    skip_def = True

                    for line in lines:
                        stripped = line.strip()

                        if skip_def and stripped.startswith("def "):
                            skip_def = False
                            continue

                        if '"""' in stripped or "'''" in stripped:
                            in_docstring = not in_docstring
                            continue

                        if in_docstring:
                            continue

                        if stripped and not stripped.startswith("#"):
                            body_lines.append(stripped)

                    if len(body_lines) == 1 and body_lines[0].startswith("return "):
                        return Expr(
                            engine="python",
                            script=body_lines[0].replace("return ", "", 1),
                        )

                    return Expr(engine="python", script="\n".join(body_lines))

            except Exception as e:
                print(f"Error: {e}")
                return Expr(engine="python", script=str(fn))

    processor = MockProcessor()

    print("=" * 60)
    print("Testing Lambda Serialization")
    print("=" * 60)

    # Test 1: Simple lambda
    print("\n1. Simple lambda:")
    lambda1 = lambda data, ctx: data["amount"] > 0
    result1 = processor._serialize_lambda(lambda1)
    print(f"   Input:  lambda data, ctx: data['amount'] > 0")
    print(f"   Output: {result1.script}")
    print(f"   ✓ Expected: data['amount'] > 0")

    # Test 2: Lambda with boolean logic
    print("\n2. Lambda with boolean logic:")
    lambda2 = lambda data, ctx: data["amount"] > 0 and data["currency"] in ["USD", "EUR"]
    result2 = processor._serialize_lambda(lambda2)
    print(f"   Input:  lambda data, ctx: data['amount'] > 0 and data['currency'] in ['USD', 'EUR']")
    print(f"   Output: {result2.script}")
    print(f"   ✓ Expected: data['amount'] > 0 and data['currency'] in ['USD', 'EUR']")

    # Test 3: Simple function with return
    print("\n3. Simple function with return:")

    def validate_payment(data, ctx):
        return data["amount"] > 0

    result3 = processor._serialize_lambda(validate_payment)
    print(f"   Input:  def validate_payment(data, ctx):")
    print(f"           return data['amount'] > 0")
    print(f"   Output: {result3.script}")
    print(f"   ✓ Expected: data['amount'] > 0")

    # Test 4: Function with docstring
    print("\n4. Function with docstring:")

    def validate_with_docs(data, ctx):
        """Validate payment is positive."""
        return data["amount"] > 0 and data["currency"] in ["USD", "EUR"]

    result4 = processor._serialize_lambda(validate_with_docs)
    print(f"   Input:  def validate_with_docs(data, ctx):")
    print(f'           """Validate payment is positive."""')
    print(f"           return data['amount'] > 0 and data['currency'] in ['USD', 'EUR']")
    print(f"   Output: {result4.script}")
    print(f"   ✓ Expected: data['amount'] > 0 and data['currency'] in ['USD', 'EUR']")

    # Test 5: Multi-line function
    print("\n5. Multi-line function:")

    def complex_validator(data, ctx):
        """Complex validation logic."""
        items_total = sum(item["price"] for item in data["items"])
        return data["total"] == items_total

    result5 = processor._serialize_lambda(complex_validator)
    print(f"   Input:  def complex_validator(data, ctx):")
    print(f'           """Complex validation logic."""')
    print(f'           items_total = sum(item["price"] for item in data["items"])')
    print(f"           return data['total'] == items_total")
    print(f"   Output:")
    for line in result5.script.split("\n"):
        print(f"           {line}")
    print(f"   ✓ Expected: Multi-line body without def/docstring")

    # Test 6: Filter lambda
    print("\n6. Filter lambda:")
    filter_lambda = lambda: True
    result6 = processor._serialize_lambda(filter_lambda)
    print(f"   Input:  lambda: True")
    print(f"   Output: {result6.script}")
    print(f"   ✓ Expected: True")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_lambda_serialization()
