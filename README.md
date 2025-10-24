# Business-Use

**Track, validate, and visualize business flows in production applications.**

Business-Use is a lightweight framework for ensuring your critical business workflows execute correctly in production. Define expected flows, track events as they happen, and automatically validate that your business logic works as intended.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)


https://github.com/user-attachments/assets/e80ae1d0-062e-4f6a-8af7-d72798c0c486


## Why Business-Use?

Traditional monitoring tells you *what* happened. Business-Use tells you if it happened *correctly*.

```python
from business_use import initialize, ensure

# Define your business flow expectations
ensure(
    id="payment_processed",
    flow="checkout",
    run_id=order_id,
    data={"amount": 99.99, "status": "completed"}
)

ensure(
    id="inventory_updated",
    flow="checkout",
    run_id=order_id,
    data={"product_id": "abc", "quantity": -1},
    validator=lambda data, ctx: data["quantity"] < 0,  # Validate inventory decreased
    description="Inventory should decrease after order"
)
```

Business-Use automatically validates:
- ✅ Events happened in the correct order
- ✅ Dependencies between steps were satisfied
- ✅ Time constraints were met
- ✅ Business rules were validated
- ✅ No steps were skipped

## Features

- **🔍 Flow Validation**: Ensure events happen in the correct order with proper dependencies
- **⚡ Zero Overhead**: Asynchronous batching means no blocking I/O in your application
- **🛡️ Never Fails**: SDK errors are caught internally - your application never crashes
- **🎯 End-to-End Testing**: Trigger flows and validate execution with the `ensure` command
- **📊 Visualization**: Interactive UI to explore flow graphs and debug failures
- **🔧 Type-Safe**: Full TypeScript support with automatic type inference
- **🚀 Production Ready**: Used in production, handles high-throughput workloads
- **⏱️ Time-Aware Polling**: Smart timeout handling with live progress updates

## Quick Start

### 1. Start the Backend

```bash
# Using uvx (recommended - no installation needed)
uvx business-use-core init        # Interactive setup (first time only)
uvx business-use-core server dev  # Start development server

# Or install globally
pip install business-use-core
business-use init
business-use server dev
```

The backend runs at `http://localhost:13370`

### 2. Install the SDK

**Python:**
```bash
pip install business-use
```

**JavaScript/TypeScript:**
```bash
pnpm add @desplega.ai/business-use
# or: npm install @desplega.ai/business-use
```

### 3. Track Your First Flow

**Python:**
```python
from business_use import initialize, ensure

# Initialize once at app startup
initialize(api_key="your-api-key")

# Track business events
ensure(
    id="user_signup",
    flow="onboarding",
    run_id="user_12345",
    data={"email": "user@example.com", "plan": "premium"}
)

ensure(
    id="email_sent",
    flow="onboarding",
    run_id="user_12345",
    data={"type": "welcome_email"},
    dep_ids=["user_signup"],
    validator=lambda data, ctx: any(d["data"]["plan"] == "premium" for d in ctx["deps"])
)
```

**JavaScript:**
```typescript
import { initialize, ensure } from '@desplega.ai/business-use';

// Initialize once at app startup
initialize({ apiKey: 'your-api-key' });

// Track business events
ensure({
  id: 'user_signup',
  flow: 'onboarding',
  runId: 'user_12345',
  data: { email: 'user@example.com', plan: 'premium' }
});

ensure({
  id: 'email_sent',
  flow: 'onboarding',
  runId: 'user_12345',
  data: { type: 'welcome_email' },
  depIds: ['user_signup'],
  validator: (data, ctx) => ctx.deps.some(d => d.data.plan === 'premium')
});
```

### 4. Validate Flows

**Evaluate a completed flow run:**
```bash
# Evaluate a specific run
business-use flow eval user_12345 onboarding --verbose

# With graph visualization
business-use flow eval user_12345 onboarding --show-graph --verbose

# HTTP API
curl -X POST http://localhost:13370/v1/run-eval \
  -H "X-Api-Key: your-api-key" \
  -d '{"run_id": "user_12345", "flow": "onboarding"}'
```

**Trigger and validate flows end-to-end:**
```bash
# Run a single flow from trigger to completion
business-use flow ensure checkout

# Run with live progress updates
business-use flow ensure checkout --live

# Run all flows with triggers in parallel
business-use flow ensure --parallel 3

# Custom timeouts and JSON output
business-use flow ensure checkout --max-timeout 60000 --json-output
```

### 5. Visualize (Optional)

```bash
cd ui && pnpm install && pnpm dev
# Open http://localhost:5173
```

Or you can use the automatic deployed version at [business-use.com](https://business-use.com).

## Examples

See the [`examples/`](./examples/) directory for complete examples:

- **Python**: Simple order processing flow
- **JavaScript**: User onboarding flow

## Architecture

Business-Use consists of four components:

```
┌─────────────┐     ┌─────────────┐
│   Python    │────▶│             │
│     SDK     │     │   Backend   │
└─────────────┘     │  (FastAPI)  │◀────┐
                    │             │     │
┌─────────────┐     │  SQLite DB  │     │
│ JavaScript  │────▶│             │     │
│     SDK     │     └─────────────┘     │
└─────────────┘            │            │
                           │            │
                    ┌──────▼─────┐      │
                    │  React UI  │──────┘
                    │ (Optional) │
                    └────────────┘
```

- **SDKs** (Python/JS): Batch events asynchronously, never block your app
- **Backend**: Stores events, validates flows, provides evaluation API
- **UI**: Visualize flow graphs, explore run history, debug failures

## End-to-End Flow Testing

Business-Use supports **trigger nodes** for automated end-to-end testing. Define trigger nodes in YAML to execute HTTP requests or commands that start your flows:

```yaml
# .business-use/checkout.yaml
flow: checkout
nodes:
  - id: checkout_trigger
    type: trigger
    handler: http_request
    handler_input:
      params:
        url: https://api.example.com/checkout
        method: POST
        body:
          product_id: "test-123"
        run_id_extractor:
          engine: python
          script: "output['order_id']"

  - id: payment_processed
    type: act
    dep_ids: [checkout_trigger]

  - id: inventory_updated
    type: assert
    dep_ids: [payment_processed]
    validator:
      engine: python
      script: "data['quantity'] < 0"
```

Then run end-to-end tests:
```bash
# Test a single flow
business-use flow ensure checkout --live

# Test all flows in parallel
business-use flow ensure --parallel 5 --live
```

The `ensure` command will:
1. Execute the trigger (HTTP request or command)
2. Extract the run_id from the response
3. Poll the flow evaluation until it passes, fails, or times out
4. Show live progress updates with remaining time

## Use Cases

### E-commerce Checkout
Validate that orders follow the correct flow:
```
cart_created → payment_initiated → payment_processed → inventory_updated → order_confirmed
```

### User Onboarding
Ensure onboarding steps happen in order:
```
signup → email_verified → profile_completed → welcome_email_sent
```

### Payment Processing
Track payment flows with validation:
```
payment_initiated → fraud_check_passed → payment_processed → receipt_sent
```

### Data Pipelines
Validate ETL workflows:
```
data_extracted → data_transformed → data_validated → data_loaded
```

## Documentation

- **[SDK Architecture](./SDK_ARCHITECTURE.md)**: Deep dive into SDK design and batching
- **[Core Architecture](./core/ARCHITECTURE.md)**: Backend architecture and domain model
- **[CLI Reference](./core/CLI_REFERENCE.md)**: Complete CLI command documentation
- **[CLAUDE.md](./CLAUDE.md)**: Development guide for contributors

## Repository Structure

```
.
├── core/               # FastAPI backend + CLI
├── sdk-py/            # Python SDK
├── sdk-js/            # JavaScript/TypeScript SDK
├── ui/                # React visualization UI
└── examples/          # Example implementations
```

---

## Component Deep Dive

### `core/` - Backend & CLI

The FastAPI backend handles event ingestion, storage, and flow validation.

**What it does:**
- Receives events from SDKs via `/v1/events-batch` endpoint
- Validates event sequences against flow definitions
- Executes trigger nodes for end-to-end testing
- Manages secrets and configuration
- Provides CLI for flow management and evaluation

**Key Features:**
- **Trigger Execution**: Execute HTTP requests or bash commands to start flows
- **Secrets Management**: Secure storage of API keys with `${secret.KEY}` syntax
- **YAML Flows**: Declarative flow definitions in `.business-use/` directory
- **E2E Testing**: `flow ensure` command for automated testing
- **Hexagonal Architecture**: Clean separation of domain logic from infrastructure

**Installation:**
```bash
# Development (local)
cd core
uv sync
uv run business-use init        # Interactive setup
uv run business-use server dev  # Start with auto-reload

# Production (PyPI)
uvx business-use-core init      # No installation needed
uvx business-use-core server dev
```

**Main Commands:**
```bash
# Server
business-use server dev         # Development server with auto-reload
business-use server prod        # Production server (4 workers)

# Flow Management
business-use flow ensure [flow] # Execute trigger + validate (E2E testing)
business-use flow eval <run_id> <flow>  # Evaluate completed run
business-use flow graph [flow]  # Show flow structure
business-use flow runs          # List recent runs

# Node Management
business-use nodes sync         # Sync YAML flows to database
business-use nodes validate     # Validate YAML files

# Workspace
business-use workspace init     # Create .business-use/ directory

# Database
business-use db migrate         # Run migrations
```

**Configuration:**
- `config.yaml` - API key, database path, log level
- `secrets.yaml` - Sensitive values (gitignored)
- `.business-use/*.yaml` - Flow definitions

**Architecture:**
- `domain/` - Pure business logic (zero dependencies)
- `execution/` - Expression evaluation (Python/CEL/JS)
- `adapters/` - Storage implementations (SQLite)
- `eval/` - Orchestration layer
- `api/` - FastAPI HTTP endpoints
- `loaders/` - YAML flow loaders
- `triggers/` - Trigger execution
- `secrets_manager/` - Secrets management

**Example Flow with Trigger:**
```yaml
# .business-use/checkout.yaml
flow: checkout
nodes:
  - id: create_order
    type: trigger
    handler: http_request
    handler_input:
      params:
        url: "${API_BASE_URL}/orders"
        method: POST
        headers:
          Authorization: "Bearer ${secret.API_KEY}"
        body: '{"product": "test-123"}'
        run_id_extractor:
          engine: python
          script: "output['order_id']"

  - id: payment_processed
    type: act
    dep_ids: [create_order]
    conditions:
      - timeout_ms: 30000
```

**Development:**
```bash
cd core
uv sync
uv run ruff format src/        # Format
uv run ruff check src/ --fix   # Lint
uv run mypy src/               # Type check
```

---

### `sdk-py/` - Python SDK

Lightweight Python SDK for tracking business events with async batching.

**What it does:**
- Track events from Python applications
- Batch events asynchronously in background thread
- Never fails or blocks your application code
- Thread-safe for concurrent use

**Installation:**
```bash
pip install business-use
# or
uv add business-use
```

**API Reference:**

**`initialize(api_key, url, batch_size, batch_interval, max_queue_size)`**

Initialize the SDK before using `ensure()`. Must be called once at app startup.

Parameters:
- `api_key` (str, optional): API key (default: `BUSINESS_USE_API_KEY` env var)
- `url` (str, optional): Backend URL (default: `BUSINESS_USE_URL` or `http://localhost:13370`)
- `batch_size` (int): Events per batch (default: 100)
- `batch_interval` (int): Flush interval in seconds (default: 5)
- `max_queue_size` (int): Max queue size (default: `batch_size * 10`)

**`ensure(id, flow, run_id, data, filter, dep_ids, validator, description, conditions, additional_meta)`**

Track a business event. Type is auto-determined by validator presence.

Parameters:
- `id` (str, required): Unique node/event identifier
- `flow` (str, required): Flow identifier
- `run_id` (str | callable, required): Run identifier or lambda
- `data` (dict, required): Event data payload
- `filter` (callable, optional): Filter function `(data, ctx) -> bool` evaluated on backend
- `dep_ids` (list[str] | callable, optional): Dependency node IDs
- `validator` (callable, optional): Validation function `(data, ctx) -> bool` executed on backend. **If provided, creates "assert" node; if absent, creates "act" node.**
- `description` (str, optional): Human-readable description
- `conditions` (list[NodeCondition], optional): Timeout constraints
- `additional_meta` (dict, optional): Additional metadata

**Validator Context:**
Both `filter` and `validator` receive `ctx` parameter with:
- `ctx["deps"]` - List of upstream dependency events: `[{"flow": str, "id": str, "data": dict}, ...]`

**`shutdown(timeout)`**

Gracefully shutdown and flush remaining events (optional, auto-shuts down on exit).

**Example:**
```python
from business_use import initialize, ensure, NodeCondition

# Initialize
initialize(api_key="your-api-key")

# Track action (no validator)
ensure(
    id="payment_processed",
    flow="checkout",
    run_id="order_123",
    data={"amount": 100, "currency": "USD"},
    dep_ids=["cart_created"]
)

# Track assertion (with validator)
def validate_total(data, ctx):
    """Validator has access to upstream events via ctx["deps"]"""
    items = [d for d in ctx["deps"] if d["id"] == "item_added"]
    total = sum(item["data"]["price"] for item in items)
    return data["total"] == total

ensure(
    id="order_total_valid",
    flow="checkout",
    run_id="order_123",
    data={"total": 150},
    dep_ids=["item_added"],
    validator=validate_total,  # Creates "assert" node
    conditions=[NodeCondition(timeout_ms=5000)]
)

# Using filter with upstream context
def check_approved(data, ctx):
    """Filter based on upstream event data"""
    return all(d["data"].get("status") == "approved" for d in ctx["deps"])

ensure(
    id="order_completed",
    flow="checkout",
    run_id=lambda: get_current_run_id(),
    data={"order_id": "ord_123"},
    filter=check_approved,  # Evaluated on backend
    dep_ids=["payment_processed", "inventory_reserved"]
)
```

**Key Features:**
- **Non-blocking**: Events batched and sent in background
- **Never fails**: All errors caught internally, never propagated to user code
- **Thread-safe**: Safe for concurrent use
- **Context-aware**: Validators/filters access upstream deps via `ctx["deps"]`

**Development:**
```bash
cd sdk-py
uv sync
uv run pytest                  # Run tests
uv run python example.py       # Run example
uv run ruff format src/ tests/ # Format
uv run ruff check src/ --fix   # Lint
```

**Environment Variables:**
```bash
export BUSINESS_USE_API_KEY="your-api-key"
export BUSINESS_USE_URL="http://localhost:13370"
```

---

### `sdk-js/` - JavaScript/TypeScript SDK

Lightweight JavaScript/TypeScript SDK with full type safety and async batching.

**What it does:**
- Track events from JavaScript/TypeScript applications
- Batch events asynchronously in background
- Never fails or blocks your application
- Full TypeScript support with type inference

**Installation:**
```bash
pnpm add @desplega.ai/business-use
# or
npm install @desplega.ai/business-use
```

**API Reference:**

**`initialize(options)`**

Initialize the SDK before using `ensure()`.

Options:
- `apiKey` (string, optional): API key (default: `BUSINESS_USE_API_KEY` env var)
- `url` (string, optional): Backend URL (default: `BUSINESS_USE_URL` or `http://localhost:13370`)
- `batchSize` (number): Events per batch (default: 100)
- `batchInterval` (number): Flush interval in ms (default: 5000)
- `maxQueueSize` (number): Max queue size (default: `batchSize * 10`)

**`ensure(options)`**

Track a business event. Type is auto-determined by validator presence.

Options:
- `id` (string, required): Unique node/event identifier
- `flow` (string, required): Flow identifier
- `runId` (string | function, required): Run identifier or function
- `data` (object, required): Event data payload
- `filter` (function, optional): Filter function `(data, ctx) => boolean` evaluated on backend
- `depIds` (string[] | function, optional): Dependency node IDs
- `validator` (function, optional): Validation function `(data, ctx) => boolean` executed on backend. **If provided, creates "assert" node; if absent, creates "act" node.**
- `description` (string, optional): Human-readable description
- `conditions` (NodeCondition[], optional): Timeout constraints
- `additional_meta` (object, optional): Additional metadata

**Validator Context:**
Both `filter` and `validator` receive `ctx` parameter with:
- `ctx.deps` - Array of upstream dependency events: `[{flow: string, id: string, data: object}, ...]`

**`shutdown(timeout)`**

Gracefully shutdown and flush remaining events (returns Promise).

**Example:**
```typescript
import { initialize, ensure } from '@desplega.ai/business-use';

// Initialize
initialize({ apiKey: 'your-api-key' });

// Track action (no validator)
ensure({
  id: 'payment_processed',
  flow: 'checkout',
  runId: 'order_123',
  data: { amount: 100, currency: 'USD' },
  depIds: ['cart_created']
});

// Track assertion (with validator)
ensure({
  id: 'order_total_valid',
  flow: 'checkout',
  runId: 'order_123',
  data: { total: 150 },
  depIds: ['item_added'],
  validator: (data, ctx) => {
    // Validator has access to upstream events via ctx.deps
    const items = ctx.deps.filter(d => d.id === 'item_added');
    const total = items.reduce((sum, item) => sum + item.data.price, 0);
    return data.total === total;
  },  // Creates "assert" node
  conditions: [{ timeout_ms: 5000 }]
});

// Using filter with upstream context
ensure({
  id: 'order_completed',
  flow: 'checkout',
  runId: () => getCurrentRunId(),
  data: { orderId: 'ord_123' },
  filter: (data, ctx) => {
    // Filter based on upstream event data
    return ctx.deps.every(d => d.data.status === 'approved');
  },  // Evaluated on backend
  depIds: ['payment_processed', 'inventory_reserved']
});
```

**TypeScript Support:**
```typescript
// Full type inference
ensure({
  id: 'payment',
  flow: 'checkout',
  runId: 'order_123',
  data: { amount: 100, currency: 'USD' },
  validator: (data, ctx) => {
    // data and ctx are automatically typed
    return data.amount > 0 && ctx.deps.length > 0;
  }
});

// Explicit typing for better type safety
interface OrderData {
  orderId: string;
  total: number;
}

ensure<OrderData>({
  id: 'order_validation',
  flow: 'checkout',
  runId: 'order_456',
  data: { orderId: '12345', total: 200 },
  validator: (data, ctx) => {
    // Full autocomplete for data.orderId, data.total
    return data.total > 0;
  }
});
```

**Key Features:**
- **Zero failures**: SDK errors never crash your code
- **Non-blocking**: Async batching prevents blocking I/O
- **Type-safe**: Full TypeScript with type inference
- **Context-aware**: Validators/filters access upstream deps via `ctx.deps`

**Development:**
```bash
cd sdk-js
pnpm install
pnpm build                     # Build SDK
pnpm test                      # Run tests
pnpm example                   # Run example
pnpm typecheck                 # Type check
pnpm format                    # Format
pnpm lint:fix                  # Lint
```

**Environment Variables:**
```bash
export BUSINESS_USE_API_KEY="your-api-key"
export BUSINESS_USE_URL="http://localhost:13370"
```

---

### `ui/` - React Visualization

Interactive React application for visualizing flow graphs and exploring run history.

**What it does:**
- Visualize flow graphs with interactive node positioning
- Explore run history and event data
- Debug flow failures with detailed evaluation results
- Real-time updates via TanStack Query

**Tech Stack:**
- **React 18** - UI framework
- **xyflow** - Flow graph visualization
- **TanStack Query** - Data fetching and caching
- **Tailwind CSS** - Styling
- **TypeScript** - Type safety
- **Vite** - Build tool

**Quick Start:**
```bash
cd ui
pnpm install
pnpm dev          # Start dev server at http://localhost:5173
```

**Features:**
- **Interactive Flow Graphs**: Drag nodes, zoom, pan
- **Run History**: Browse all flow executions
- **Event Inspection**: View event data and metadata
- **Evaluation Results**: See passed/failed nodes with details
- **Real-time Updates**: Auto-refresh on new data

**Development:**
```bash
cd ui
pnpm install
pnpm dev                       # Development server
pnpm build                     # Production build
pnpm preview                   # Preview build
pnpm lint                      # Lint
pnpm lint:fix                  # Lint with auto-fix
pnpm format                    # Format with Prettier
pnpm format:check              # Check formatting
```

**Project Structure:**
```
ui/
├── src/
│   ├── components/           # React components
│   ├── lib/                  # API client, queries, types
│   └── App.tsx              # Main app
├── public/                   # Static assets
└── package.json
```

---

## Development

### Backend
```bash
cd core
uv sync
uv run business-use server dev  # Development with auto-reload
```

### Python SDK
```bash
cd sdk-py
uv sync
uv run pytest
```

### JavaScript SDK
```bash
cd sdk-js
pnpm install
pnpm test
```

### UI
```bash
cd ui
pnpm install
pnpm dev
```

## Releasing

See [RELEASE.md](./RELEASE.md) for detailed release instructions.

## Real-World Integration

Want to see Business-Use in action? Check out our integration examples:

- **[RealWorld App](https://github.com/gothinkster/realworld)**: Article publication and user interaction flows
- More examples coming soon!

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Run formatting and linting
5. Commit your changes
6. Push to the branch
7. Open a Pull Request

## License

MIT License - see [LICENSE](./LICENSE) for details.

## Support

- **GitHub Issues**: https://github.com/desplega-ai/business-use/issues
- **Documentation**: https://github.com/desplega-ai/business-use#readme

## Why "Business-Use"?

Because production monitoring should focus on *business outcomes*, not just technical metrics. Track what matters: your users' journeys through your application.

---

Made with ❤️ by [Desplega AI](https://desplega.ai)
