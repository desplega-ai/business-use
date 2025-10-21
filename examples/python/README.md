# Business-Use Python SDK Example

This example demonstrates how to use the Business-Use Python SDK to track business events and assertions.

## Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Business-Use backend running on `http://localhost:13370`

## Installation

The example uses the local Business-Use SDK from `../../sdk-py`.

### Using uv (recommended):

```bash
# Install dependencies (automatically installs local SDK)
uv sync

# Run the example
uv run python example.py
```

### Using pip:

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the local SDK
pip install -e ../../sdk-py

# Run the example
python example.py
```

> **Note**: If you've published the SDK to PyPI, you can also install it with `pip install business-use`

## What This Example Does

1. **Initializes** the SDK with API key and backend URL
2. **Tracks actions** - User signup and email verification
3. **Tracks assertions** - Payment validation with a validator function
4. **Demonstrates filters** - Client-side and server-side filtering
5. **Shows lambdas** - Dynamic run IDs and filters
6. **Uses conditions** - Timeout constraints on events
7. **Adds metadata** - Additional context with `additional_meta`
8. **Graceful shutdown** - Ensures all events are flushed before exit

## Expected Output

You should see debug logs showing:
- SDK initialization
- Events being queued
- Batches being sent to the backend
- Successful batch delivery confirmation

## Configuration

Edit the `initialize()` call in `example.py` to customize:
- `api_key`: Your Business-Use API key
- `url`: Backend URL (default: http://localhost:13370)
- `batch_size`: Number of events per batch
- `batch_interval`: Seconds between batch flushes
