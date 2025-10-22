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
# Evaluate a flow run
uv run business-use eval-run <run_id> <flow> --verbose

# Show flow graph structure
uv run business-use show-graph [flow]

# List recent runs
uv run business-use runs

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
