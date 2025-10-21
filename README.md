# Business-Use

**Track, validate, and visualize business flows in production applications.**

Business-Use is a lightweight framework for ensuring your critical business workflows execute correctly in production. Define expected flows, track events as they happen, and automatically validate that your business logic works as intended.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)

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
- **📊 Visualization**: Interactive UI to explore flow graphs and debug failures
- **🔧 Type-Safe**: Full TypeScript support with automatic type inference
- **🚀 Production Ready**: Used in production, handles high-throughput workloads

## Quick Start

### 1. Install the Backend

```bash
# Using uvx (recommended - no installation needed)
uvx business-use-core serve

# Or install globally
pip install business-use-core
business-use-core serve
```

The backend API will start at `http://localhost:13370`

### 2. Install the SDK

**Python:**
```bash
pip install business-use
```

**JavaScript/TypeScript:**
```bash
pnpm add business-use
# or: npm install business-use
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
    validator=lambda data, ctx: ctx["user_signup"]["plan"] == "premium"
)
```

**JavaScript:**
```typescript
import { initialize, ensure } from 'business-use';

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
  validator: (data, ctx) => ctx.user_signup.plan === 'premium'
});
```

### 4. Validate Flows

```bash
# CLI
uvx business-use-core eval-run user_12345 onboarding --verbose

# HTTP API
curl -X POST http://localhost:13370/v1/run-eval \
  -H "X-Api-Key: your-api-key" \
  -d '{"run_id": "user_12345", "flow": "onboarding"}'
```

### 5. Visualize (Optional)

```bash
cd ui && pnpm install && pnpm dev
# Open http://localhost:5173
```

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

## Development

### Backend
```bash
cd core
uv sync
uv run cli serve --reload
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
