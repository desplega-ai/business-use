# business-use-core

FastAPI backend for tracking and validating business event flows in production applications.

## Quick Start

```bash
# Install dependencies
uv sync

# Initialize (creates config, generates API key, sets up database)
uv run business-use init

# Start development server
uv run business-use serve --reload

# Start production server (4 workers)
uv run business-use prod
```

## What It Does

- **Event Ingestion**: Receives events from SDKs via `/v1/events-batch`
- **Flow Evaluation**: Validates event sequences against flow definitions
- **Storage**: SQLite database with async queries
- **CLI**: Commands for evaluation, inspection, and management

## Key Commands

```bash
# Execute flows with triggers (NEW!)
uv run business-use flow ensure                     # Run all flows with triggers
uv run business-use flow ensure payment_approval    # Run specific flow
uv run business-use flow ensure --parallel 3        # Run 3 flows concurrently
uv run business-use flow ensure --live              # Interactive display

# Evaluate a flow run
uv run business-use flow eval <run_id> <flow> --verbose

# Show flow graph structure
uv run business-use flow graph [flow]

# List recent runs
uv run business-use flow runs

# Manage flow definitions
uv run business-use nodes sync                      # Sync YAML flows to DB
uv run business-use nodes validate                  # Validate YAML files

# Workspace management
uv run business-use workspace init                  # Create .business-use/

# Database migrations
uv run business-use db migrate

# Format/lint
uv run ruff format src/
uv run ruff check src/ --fix
```

## Architecture

Follows **Hexagonal Architecture** (Ports & Adapters):

- `domain/` - Pure business logic (zero dependencies)
- `execution/` - Expression evaluation (Python/CEL/JS)
- `adapters/` - Storage implementations (SQLite)
- `eval/` - Orchestration layer
- `api/` - FastAPI HTTP endpoints
- `loaders/` - YAML flow definitions

## Configuration

Configuration loaded from:
1. `./config.yaml` (development)
2. `~/.business-use/config.yaml` (production)

```yaml
api_key: your_secret_key_here
database_path: ./db.sqlite
log_level: info
```

## Installation from PyPI

```bash
# Run without installing
uvx business-use-core init
uvx business-use-core serve

# Or install globally
pip install business-use-core
business-use init
business-use serve
```

## Flow Ensure Command

The `flow ensure` command executes trigger nodes and polls evaluations until completion. Perfect for E2E testing and CI/CD pipelines.

### How It Works

1. **Execute Trigger**: Runs HTTP request or bash command defined in trigger node
2. **Extract Run ID**: Uses Python expression to extract run_id from response
3. **Poll Evaluation**: Continuously evaluates flow until passed/failed/timeout
4. **Report Results**: Shows summary with passed/failed status

### Example Flow with Trigger

`.business-use/payment_approval.yaml`:
```yaml
flow: payment_approval
nodes:
  - id: create_payment
    type: trigger
    handler: http_request
    handler_input:
      params:
        url: "${API_BASE_URL}/payments"
        method: POST
        headers:
          Authorization: "Bearer ${secret.PAYMENT_API_KEY}"
        body: '{"amount": 100, "currency": "USD"}'
        run_id_extractor:
          engine: python
          script: "output['data']['payment_id']"

  - id: payment_confirmed
    type: act
    dep_ids: [create_payment]
    conditions:
      - timeout_ms: 30000
```

### Secrets Management

Create `.business-use/secrets.yaml` (gitignored):
```yaml
PAYMENT_API_KEY: "sk_test_your_key"
API_BASE_URL: "https://api.example.com"
```

Use in YAML with `${secret.KEY}` or `${ENV_VAR}` syntax.

### Testing Locally

```bash
# 1. Sync flow definition to database
uv run business-use nodes sync

# 2. Start server
uv run business-use server dev --reload

# 3. Run ensure command (executes trigger + polls evaluation)
uv run business-use flow ensure payment_approval --live

# For dummy testing without real API:
# Send test events with the seed script
uv run python scripts/seed_test.py payment_12345
# Then evaluate manually
uv run business-use flow eval payment_12345 payment_approval --verbose
```

## Documentation

- Full project overview: `../CLAUDE.md`
- Architecture details: `ARCHITECTURE.md`
- CLI reference: `CLI_REFERENCE.md`
- Graph examples: `GRAPH_EXAMPLES.md`

## API

All endpoints require `X-Api-Key` header:

- `POST /v1/events-batch` - Ingest events
- `POST /v1/run-eval` - Evaluate flow run
- `GET /health` - Health check (no auth)
