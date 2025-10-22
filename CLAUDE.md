# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Business-Use is a monorepo for tracking and validating business event flows in production applications. It consists of:

- **core**: FastAPI backend for event ingestion, storage, and flow validation
- **sdk-py**: Python SDK for tracking events via unified `ensure()` function
- **sdk-js**: JavaScript/TypeScript SDK with identical API to Python SDK
- **ui**: React visualization tool for exploring flow graphs and evaluating runs

## Repository Structure

```
.
├── core/               # FastAPI backend + CLI
│   ├── src/
│   │   ├── domain/    # Pure business logic (zero dependencies)
│   │   ├── execution/ # Expression evaluation (Python/CEL/JS)
│   │   ├── adapters/  # Storage adapters (SQLite)
│   │   ├── eval/      # Flow evaluation orchestration
│   │   ├── api/       # FastAPI endpoints
│   │   ├── loaders/   # YAML flow definition loaders
│   │   └── cli.py     # CLI commands
│   └── migrations/    # Alembic database migrations
├── sdk-py/            # Python SDK
│   └── src/business_use/
│       ├── client.py  # Main SDK (initialize, ensure)
│       ├── batch.py   # Background batching worker
│       └── models.py  # Pydantic models
├── sdk-js/            # JavaScript/TypeScript SDK
│   └── src/
│       ├── client.ts  # Main SDK
│       ├── batch.ts   # Background batching
│       └── models.ts  # Zod schemas
└── ui/                # React + xyflow visualization
    └── src/
        ├── components/
        ├── lib/       # API client, queries, types
        └── App.tsx
```

## Common Commands

### Core Backend

```bash
# Install dependencies
cd core && uv sync

# First-time setup: Interactive initialization (recommended)
uv run business-use init     # Generates API key, creates config, initializes DB

# OR manual setup:
# cp config.yaml.example config.yaml && uv run business-use db migrate

# Run development server with auto-reload
uv run business-use serve --reload

# Run production server (4 workers)
uv run business-use prod

# Evaluate a flow run
uv run business-use eval-run <run_id> <flow> [--verbose] [--show-graph] [--json-output]

# Show flow graph definition
uv run business-use show-graph [flow]

# Run database migrations
uv run business-use db migrate

# Format code
uv run ruff format src/

# Lint code
uv run ruff check src/ --fix

# Type check
uv run mypy src/
```

### Python SDK

```bash
# Install dependencies
cd sdk-py && uv sync

# Run tests
uv run pytest

# Run example
uv run python example.py

# Format/lint (same as core)
uv run ruff format src/ tests/
uv run ruff check src/ tests/ --fix
```

### JavaScript SDK

```bash
# Install dependencies
cd sdk-js && pnpm install

# Build the SDK
pnpm build

# Run tests
pnpm test

# Run example
pnpm example

# Type check
pnpm typecheck

# Format/lint
pnpm format
pnpm lint:fix
```

### UI

```bash
# Install dependencies
cd ui && pnpm install

# Run development server
pnpm dev

# Build for production
pnpm build

# Format/lint (same as sdk-js)
pnpm format
pnpm lint:fix
```

## Architecture

### Core Backend (Hexagonal Architecture)

The core follows **Hexagonal Architecture** (Ports & Adapters) with strict separation:

- **domain/**: Pure business logic with ZERO external dependencies
  - Uses `TypedDict` for internal types (not Pydantic)
  - All graph construction, traversal, and validation logic
  - Pluggable via `Protocol` (ExprEvaluator)

- **execution/**: Implements expression evaluation
  - `PythonEvaluator` (current), CEL/JS (future)
  - Evaluates filters, validators, and dynamic expressions

- **adapters/**: Infrastructure adapters
  - `SqliteEventStorage` encapsulates all SQLite queries
  - Easy to swap for PostgreSQL/MongoDB

- **eval/**: Orchestration layer
  - Combines domain + execution + adapters
  - Two public APIs: `eval_flow_run()` (new) and `eval_event()` (legacy)

- **api/**: FastAPI HTTP endpoints
  - `/v1/events-batch` - batch event ingestion
  - `/v1/run-eval` - flow evaluation
  - Authentication via `X-Api-Key` header

### SDK Architecture (Python & JavaScript)

Both SDKs follow the same design documented in `SDK_ARCHITECTURE.md`:

**Key principles:**
1. **Never fail user code**: All errors caught internally, logged, never propagated
2. **Asynchronous ingestion**: Events batched and sent in background
3. **Thread-safe**: Safe for concurrent use

**Batching:**
- Events queued in-memory (max: 1000 events)
- Batch triggers: size (100 events) OR time (5 seconds)
- Background worker flushes batches to backend

**Lambda serialization:**
- `filter`: Evaluated client-side before queuing
- `run_id`, `dep_ids`: Evaluated during batch processing
- `validator`: Serialized as source code, executed on backend

### Flow Definitions

Flows can be defined in two ways:

1. **Code** (SDK): Use `ensure()` in application code
   - Type auto-determined: `validator` present → assert node, `validator` absent → act node
2. **YAML** (Declarative): Define flows in `.business-use/*.yaml` files

YAML example:
```yaml
flow: checkout
nodes:
  - id: cart_created
    type: act
  - id: payment_processed
    type: act
    dep_ids: [cart_created]
    timeout_ms: 5000
    filter:
      engine: python
      script: data["amount"] > 0
```

## Configuration

### Core Backend Configuration

The core backend uses YAML configuration files with the following priority:

1. `./config.yaml` (development - local to project)
2. `~/.business-use/config.yaml` (production - user home directory)
3. Default values

**Configuration file format (`config.yaml`):**

```yaml
# API key for authenticating requests to the server
# Required when running: serve, prod
api_key: your_secret_key_here

# Path to SQLite database file
# Default: ./db.sqlite (dev) or ~/.business-use/db.sqlite (prod)
database_path: ./db.sqlite

# Logging level: DEBUG, INFO, WARNING, ERROR
log_level: info

# Enable debug mode (verbose SQL queries, etc.)
debug: false

# Environment name
env: local
```

**Getting started:**

```bash
# Development setup - Quick start (recommended)
cd core
uv run business-use init     # Interactive setup: generates API key, creates config, initializes DB

# Start server
uv run business-use serve --reload
```

**Manual setup (alternative):**

```bash
cd core
cp config.yaml.example config.yaml
# Edit config.yaml with your settings

# Initialize database
uv run business-use db migrate

# Start server
uv run business-use serve --reload
```

**Production/PyPI usage:**

When installed via PyPI, the configuration will be loaded from `~/.business-use/config.yaml`.

The package provides two command names (both work identically):
- `business-use` (shorter, recommended)
- `business-use-core` (full package name)

```bash
# Using uvx (no installation required)
uvx business-use-core init   # Interactive setup

# Start server
uvx business-use-core serve

# OR install globally and use shorter command
pip install business-use-core
business-use init            # Interactive setup (shorter!)
business-use serve
```

**Manual setup (alternative):**

```bash
# Create config directory
mkdir -p ~/.business-use

# Create config file
cat > ~/.business-use/config.yaml <<EOF
api_key: your_secret_key_here
database_path: ~/.business-use/db.sqlite
log_level: info
EOF

# Initialize database
business-use db migrate

# Start server
business-use serve
```

**Important notes:**

- `api_key` is **required** only for `serve` and `prod` commands
- Other commands (`eval-run`, `show-graph`, `runs`, etc.) work without API_KEY
- Database commands automatically show helpful errors if DB not initialized
- `config.yaml` is gitignored (use `config.yaml.example` as template)

## Database

- **Engine**: SQLite with WAL mode (aiosqlite for async)
- **Migrations**: Alembic (run `uv run business-use db migrate`)
  - Migrations are configured programmatically (no alembic.ini required)
  - Migration files located in `src/migrations/`
  - Packaged with the distribution for PyPI/uvx users
- **Schema**: See `core/src/models.py` for Event, Node models
- **Indexes**: `(run_id, flow)` for fast lookup
- **Location**: `./db.sqlite` (dev with local config) or `~/.business-use/db.sqlite` (prod)

## SDK Configuration

### SDKs
- `BUSINESS_USE_API_KEY`: API key for authentication
- `BUSINESS_USE_URL`: Backend URL (default: `http://localhost:13370`)

## Testing Workflow

### Core
```bash
cd core
uv run business-use serve --reload  # Terminal 1

# Terminal 2
uv run business-use show-graph checkout
uv run business-use eval-run test_run_001 checkout --verbose
```

### SDKs
```bash
# Python
cd sdk-py
uv run pytest -v

# JavaScript
cd sdk-js
pnpm test
```

## Key Design Patterns

### Domain Layer Purity
The `core/src/domain/` directory must remain dependency-free. When adding features:
- Use `TypedDict` for return types (not Pydantic)
- Accept dependencies via function parameters (dependency injection)
- Use `Protocol` for pluggable components

### Error Handling in SDKs
SDKs MUST NOT raise exceptions to user code:
- Wrap all network calls in try/except
- Log errors internally with `logging` (Python) or `console` (JS)
- Return early for invalid states (no-op mode)

### Event Ingestion
Use `run_id + flow` for querying (NOT time windows):
```python
# Good - direct query
events = await storage.get_events_by_run(run_id, flow, session)

# Bad - time window filtering
events = query_by_time_range(ts_start, ts_end)
```

### Flow Evaluation
The evaluation process:
1. Load flow graph (nodes with dependencies)
2. Topologically sort into layers
3. For each layer, match events and validate:
   - Timeouts between dependent nodes
   - Filter expressions
   - Validator assertions (for `assert` nodes)

## CLI Reference

See `core/CLI_REFERENCE.md` for detailed command documentation.

Quick reference:
- `uv run business-use serve --reload` - Development server
- `uv run business-use eval-run <run_id> <flow>` - Evaluate flow
- `uv run business-use show-graph [flow]` - Show flow structure
- Use `--json-output` for automation
- Use `--verbose` for debugging
- Use `--show-graph` for visualization

## Code Style

### Python
- Formatter: `ruff format`
- Linter: `ruff check`
- Type checker: `mypy`
- Line length: 88
- Quote style: double quotes

### JavaScript/TypeScript
- Formatter: `prettier`
- Linter: `eslint`
- Type checker: `tsc --noEmit`
- Use explicit type annotations for public APIs

## Important Notes

1. **Database connections**: Use SQLModel sessions, always async
2. **API authentication**: All endpoints (except `/health`) require `X-Api-Key` header
3. **Timestamp format**: Nanoseconds (use `time.time_ns()` in Python, `process.hrtime.bigint()` in JS)
4. **Batch API**: POST to `/v1/events-batch` with array of `EventBatchItem`
5. **YAML loader**: Lives in `core/src/loaders/yaml_loader.py`, loads flows from `.business-use/` directory
6. **Filter early exit**: If filter evaluates to False, event is dropped before queuing

## Migration Notes

When adapting for other storage backends (e.g., PostgreSQL at desplega.ai):
1. Copy entire `core/src/domain/` directory as-is
2. Create new adapter in `adapters/postgres.py`
3. Update `eval/eval.py` to use new adapter
4. Domain logic remains unchanged

## References

- **SDK Architecture**: `SDK_ARCHITECTURE.md`
- **Core Architecture**: `core/ARCHITECTURE.md`
- **CLI Reference**: `core/CLI_REFERENCE.md`
- **Graph Examples**: `core/GRAPH_EXAMPLES.md`
