# Business-Use Python SDK

[![Format & Lint Checks](https://github.com/desplega-ai/business-use/actions/workflows/check.yaml/badge.svg)](https://github.com/desplega-ai/business-use/actions/workflows/check.yaml)

A lightweight, production-ready Python SDK for tracking business events and assertions in your applications.

## Features

- **Simple API**: Main function `ensure()` with convenience helpers `act()` and `assert_()`
- **Non-blocking**: Events are batched and sent asynchronously in the background
- **Never fails**: All errors are handled internally - your application never crashes
- **Thread-safe**: Safe to use from multiple threads concurrently
- **Minimal dependencies**: Only `httpx` and `pydantic`
- **Context-aware**: Filters and validators can access upstream dependency data

## Installation

```bash
pip install business-use
```

Or with `uv`:

```bash
uv add business-use
```

## Quick Start

```python
from business_use import initialize, ensure

# Initialize with API key
initialize(api_key="your-api-key")

# Track a business action (no validator)
ensure(
    id="user_signup",
    flow="onboarding",
    run_id="user_12345",
    data={"email": "user@example.com", "plan": "premium"}
)

# Track a business assertion (with validator)
def validate_payment(data, ctx):
    """Validate payment and check upstream dependencies."""
    # ctx["deps"] contains upstream dependency events
    # Each dep: {"flow": str, "id": str, "data": dict}
    has_cart = any(dep["id"] == "cart_created" for dep in ctx["deps"])
    return data["amount"] > 0 and has_cart

ensure(
    id="payment_valid",
    flow="checkout",
    run_id="order_67890",
    data={"amount": 99.99, "currency": "USD"},
    dep_ids=["cart_created"],
    validator=validate_payment  # Creates "assert" node
)

# Convenience wrappers (optional)
from business_use import act, assert_

# act() is ensure() without validator
act(id="user_signup", flow="onboarding", run_id="u123", data={...})

# assert_() is ensure() with validator
assert_(id="validation", flow="checkout", run_id="o123", data={...}, validator=fn)
```

## API Reference

### `initialize()`

Initialize the SDK before using `ensure()`. This validates the connection to the backend and starts the background batch processor.

**Parameters:**

- `api_key` (str, optional): API key for authentication (defaults to `BUSINESS_USE_API_KEY` env var)
- `url` (str, optional): Backend API URL (defaults to `BUSINESS_USE_URL` env var or `http://localhost:13370`)
- `batch_size` (int, optional): Number of events per batch (default: `100`)
- `batch_interval` (int, optional): Flush interval in seconds (default: `5`)
- `max_queue_size` (int, optional): Max queue size (default: `batch_size * 10`)

**Examples:**

```python
# With explicit parameters
initialize(
    api_key="your-api-key",
    url="https://api.example.com",
    batch_size=50,
    batch_interval=10
)

# With environment variables
# Set BUSINESS_USE_API_KEY and BUSINESS_USE_URL in your environment
initialize()

# Mix of both (parameters override env vars)
initialize(api_key="your-api-key")  # URL from BUSINESS_USE_URL or default
```

### `ensure()`

**Main function** to track business events. Type is auto-determined by the presence of a `validator`.

**Parameters:**

- `id` (str, required): Unique node/event identifier
- `flow` (str, required): Flow identifier
- `run_id` (str | callable, required): Run identifier (or lambda returning string)
- `data` (dict, required): Event data payload
- `filter` (callable, optional): Filter function `(data, ctx) -> bool` evaluated on backend
- `dep_ids` (list[str] | callable, optional): Dependency node IDs
- `validator` (callable, optional): Validation function `(data, ctx) -> bool` executed on backend
- `description` (str, optional): Human-readable description
- `conditions` (list[NodeCondition] | callable, optional): Optional conditions (e.g., timeout constraints)
- `additional_meta` (dict, optional): Optional additional metadata

**Type determination:**
- If `validator` is provided → creates an **"assert"** node
- If `validator` is `None` → creates an **"act"** node

**Example:**

```python
# Action node (no validator)
ensure(
    id="payment_processed",
    flow="checkout",
    run_id="run_12345",
    data={"amount": 100, "currency": "USD"},
    dep_ids=["cart_created"],
    description="Payment processed successfully"
)

# Assertion node (with validator)
def validate_total(data, ctx):
    items_total = sum(dep["data"]["price"] for dep in ctx["deps"])
    return data["total"] == items_total

ensure(
    id="order_total_valid",
    flow="checkout",
    run_id="run_12345",
    data={"total": 150},
    dep_ids=["item_added"],
    validator=validate_total,
    description="Order total validation"
)
```

### `act()`

**Convenience wrapper** around `ensure()` without a validator. Creates an "act" node.

**Parameters:**

- `id` (str, required): Unique node/event identifier
- `flow` (str, required): Flow identifier
- `run_id` (str | callable, required): Run identifier (or lambda returning string)
- `data` (dict, required): Event data payload
- `filter` (callable, optional): Filter function `(data, ctx) -> bool` evaluated on backend
- `dep_ids` (list[str] | callable, optional): Dependency node IDs
- `description` (str, optional): Human-readable description

**Filter Function Signature:**

```python
def my_filter(data: dict, ctx: dict) -> bool:
    """Filter function executed on the backend.

    Args:
        data: Current event data
        ctx: Context with upstream dependencies:
             ctx["deps"] = [{"flow": str, "id": str, "data": dict}, ...]

    Returns:
        bool: True to include event, False to filter it out
    """
    pass
```

**Example:**

```python
# Simple usage
act(
    id="payment_processed",
    flow="checkout",
    run_id="run_12345",
    data={"amount": 100, "currency": "USD"}
)

# With dependencies
act(
    id="order_completed",
    flow="checkout",
    run_id="run_12345",
    data={"order_id": "ord_123", "total": 150},
    dep_ids=["payment_processed", "inventory_reserved"],
    description="Order completed successfully"
)

# Using lambdas for dynamic values
act(
    id="api_request",
    flow="integration",
    run_id=lambda: get_current_trace_id(),
    data={"endpoint": "/users", "method": "POST"},
    dep_ids=lambda: get_upstream_dependencies()
)

# With filter based on upstream dependencies
def check_prerequisites(data, ctx):
    """Only process if all upstream tasks are approved."""
    return all(dep["data"].get("status") == "approved" for dep in ctx["deps"])

act(
    id="order_completed",
    flow="checkout",
    run_id="run_12345",
    data={"order_id": "ord_123"},
    dep_ids=["payment_processed", "inventory_reserved"],
    filter=check_prerequisites,  # Evaluated on backend with ctx
    description="Order completed after all prerequisites"
)
```

### `assert_()`

**Convenience wrapper** around `ensure()` with a validator. Creates an "assert" node.

Named `assert_` (with underscore) to avoid conflict with Python's built-in `assert` keyword.

**Parameters:**

- `id` (str, required): Unique node/event identifier
- `flow` (str, required): Flow identifier
- `run_id` (str | callable, required): Run identifier (or lambda returning string)
- `data` (dict, required): Event data payload
- `filter` (callable, optional): Filter function `(data, ctx) -> bool` evaluated on backend
- `dep_ids` (list[str] | callable, optional): Dependency node IDs
- `validator` (callable, optional): Validation function `(data, ctx) -> bool` executed on backend
- `description` (str, optional): Human-readable description

**Validator Function Signature:**

```python
def my_validator(data: dict, ctx: dict) -> bool:
    """Validator function executed on the backend.

    Args:
        data: Current event data
        ctx: Context with upstream dependencies:
             ctx["deps"] = [{"flow": str, "id": str, "data": dict}, ...]

    Returns:
        bool: True if validation passes, False if it fails
    """
    pass
```

**Example:**

```python
# Simple assertion
assert_(
    id="order_total_positive",
    flow="checkout",
    run_id="run_12345",
    data={"total": 150}
)

# With validator accessing upstream dependencies
def validate_order(data, ctx):
    """Validate order total matches sum of items from upstream events.

    Args:
        data: Current order data
        ctx: Context with upstream item events in ctx["deps"]
    """
    # Calculate total from upstream item_added events
    items_total = sum(
        dep["data"]["price"]
        for dep in ctx["deps"]
        if dep["id"] == "item_added"
    )

    # Verify order total matches
    return data["total"] == items_total

assert_(
    id="order_total_matches",
    flow="checkout",
    run_id="run_12345",
    data={"total": 150},
    dep_ids=["item_added"],  # Multiple item_added events
    validator=validate_order,
    description="Order total matches sum of item prices"
)

# Validator with complex logic
def validate_payment_and_inventory(data, ctx):
    """Validate both payment and inventory are ready."""
    payment_approved = any(
        dep["id"] == "payment_processed" and dep["data"]["status"] == "approved"
        for dep in ctx["deps"]
    )
    inventory_reserved = any(
        dep["id"] == "inventory_reserved" and dep["data"]["reserved"] == True
        for dep in ctx["deps"]
    )
    return payment_approved and inventory_reserved and data["ready_to_ship"]

assert_(
    id="order_ready",
    flow="checkout",
    run_id="run_12345",
    data={"ready_to_ship": True},
    dep_ids=["payment_processed", "inventory_reserved"],
    validator=validate_payment_and_inventory
)
```

### `shutdown()`

Gracefully shutdown the SDK and flush remaining events (optional - auto-shuts down on exit).

**Parameters:**

- `timeout` (float, optional): Max time to wait for shutdown in seconds (default: `5.0`)

**Example:**

```python
from business_use import shutdown

# At application shutdown
shutdown(timeout=10.0)
```

## How It Works

### Batching & Ingestion

The SDK uses a background worker thread to batch and send events:

1. Events are added to an in-memory queue (thread-safe)
2. Background thread collects events into batches
3. Batches are sent when:
   - Batch size reaches `batch_size` (default: 100), OR
   - `batch_interval` seconds elapse (default: 5)
4. On program exit, remaining events are flushed (best-effort)

### Error Handling

**The SDK never raises exceptions.** All errors are caught and logged internally:

- Network errors: Logged, batch dropped
- Queue overflow: Oldest events dropped, logged
- Invalid parameters: Logged, no-op
- Not initialized: Silent no-op

### Lambda Serialization

Callable parameters (`run_id`, `dep_ids`, `filter`, `validator`) are serialized as Python source code and executed on the backend.

**Important Notes:**
- **Filters are evaluated on the backend** with access to upstream dependencies via `ctx`
- **Validators are executed on the backend** with the same `ctx` structure
- Both filter and validator receive: `(data: dict, ctx: dict) -> bool`
- `ctx["deps"]` contains all upstream dependency events as a list of `{"flow": str, "id": str, "data": dict}`
- Only use simple lambdas or functions defined in the same file
- External references may fail serialization

## Requirements

- Python >= 3.11
- `httpx >= 0.27.0`
- `pydantic >= 2.0.0`

## Architecture

See [SDK_ARCHITECTURE.md](../../SDK_ARCHITECTURE.md) for detailed architecture documentation.

## Development & Local Setup

### Prerequisites

- Python >= 3.11
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/desplega-ai/business-use.git
   cd business-use/sdk-py
   ```

2. **Install dependencies:**
   ```bash
   # With uv (recommended)
   uv sync

   # Or with pip
   pip install -e ".[dev]"
   ```

3. **Run the backend locally:**

   The SDK requires the Business-Use backend API running locally:
   ```bash
   # In a separate terminal, navigate to the core directory
   cd ../core

   # Install core dependencies
   uv sync

   # Run the backend
   uv run cli serve --reload
   ```

   The API will be available at `http://localhost:13370`

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_serialization.py

# Run with coverage
uv run pytest --cov=business_use --cov-report=html
```

### Running the Example

Once the backend is running:

```bash
uv run python example.py
```

You should see:
- SDK initialization logs
- Events being tracked
- Batches being sent every 5 seconds
- Graceful shutdown

### Project Structure

```
sdk-py/
├── src/business_use/
│   ├── __init__.py          # Public API exports
│   ├── client.py            # Main SDK (initialize, act, assert_)
│   ├── batch.py             # Background batching worker
│   └── models.py            # Pydantic models
├── tests/
│   ├── test_client.py       # Client behavior tests
│   └── test_serialization.py # Lambda serialization tests
├── example.py               # Usage example
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

### Development Workflow

1. **Make changes** to the SDK code in `src/business_use/`

2. **Run tests** to ensure nothing breaks:
   ```bash
   uv run pytest
   ```

3. **Test manually** with the example:
   ```bash
   # Terminal 1: Run backend
   cd ../core && uv run uvicorn src.api.api:app --port 13370

   # Terminal 2: Run example
   uv run python example.py
   ```

4. **Check code quality** (optional):
   ```bash
   # Format code
   uv run ruff format src/ tests/

   # Lint code
   uv run ruff check src/ tests/

   # Type check
   uv run mypy src/
   ```

### Common Development Tasks

#### Add a new dependency

```bash
# Add runtime dependency
uv add package-name

# Add dev dependency
uv add --dev package-name
```

#### Debug SDK behavior

Enable debug logging in your code:

```python
import logging

# Set SDK logger to debug level
logging.getLogger("business-use").setLevel(logging.DEBUG)

# Or configure all logging
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(name)s] [%(levelname)s] %(message)s"
)
```

#### Test with different batch settings

Modify `example.py` to test different configurations:

```python
initialize(
    api_key="your-api-key",
    batch_size=5,      # Small batch for testing
    batch_interval=1,  # Flush every second
)
```

#### Simulate backend failures

Stop the backend and observe SDK behavior:
- Connection check should fail gracefully
- SDK should enter no-op mode
- No exceptions should be raised

### Environment Variables

The SDK supports configuration via environment variables. This is the **recommended approach** for production deployments:

```bash
# Required: Set API key
export BUSINESS_USE_API_KEY="your-api-key"

# Optional: Set custom backend URL (defaults to http://localhost:13370)
export BUSINESS_USE_URL="https://api.desplega.ai"
```

Then simply initialize without parameters:

```python
from business_use import initialize

# Automatically uses BUSINESS_USE_API_KEY and BUSINESS_USE_URL from environment
initialize()
```

**Benefits:**
- ✅ Keep secrets out of code
- ✅ Easy configuration per environment (dev/staging/prod)
- ✅ Works with Docker, Kubernetes, etc.
- ✅ Parameters still override env vars when needed

### Troubleshooting

**Issue: SDK not sending events**

1. Check backend is running:
   ```bash
   curl http://localhost:13370/health
   # Should return: {"status":"success","message":"API is healthy"}
   ```

2. Enable debug logging to see batch processing:
   ```python
   logging.getLogger("business-use").setLevel(logging.DEBUG)
   ```

3. Check API key is correct (default: check backend config)

**Issue: Tests failing**

1. Ensure dependencies are up-to-date:
   ```bash
   uv sync
   ```

2. Run tests with verbose output:
   ```bash
   uv run pytest -v -s
   ```

3. Check if backend is interfering (tests should work without backend)

**Issue: Import errors**

Make sure you've installed the package in editable mode:
```bash
uv sync  # Reinstalls in editable mode
```

### Backend API Endpoints

When running locally, the backend exposes:

- `GET /health` - Health check (no auth required)
- `GET /v1/check` - Verify API key
- `POST /v1/events-batch` - Batch event ingestion
- `GET /v1/events` - Query events
- `GET /v1/nodes` - Query nodes

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`uv run pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Best Practices

- **Always run tests** before committing
- **Add tests** for new features
- **Keep dependencies minimal** - avoid adding unnecessary packages
- **Use type hints** for better IDE support and maintainability
- **Log errors** instead of raising exceptions in SDK code
- **Never block** the main thread - all network I/O happens in background

## License

MIT
