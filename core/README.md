# Magic Core

A workflow automation and event-driven testing framework built with Python, FastAPI, and SQLite.

## Features

- **Event-Driven Architecture**: Define triggers, actions, and assertions based on events
- **Workflow Automation**: Create complex workflows with dependencies and conditions
- **RESTful API**: Built with FastAPI for easy integration
- **Type-Safe**: Full type hints with mypy validation
- **Async First**: Built on async/await for high performance
- **SQLite Backend**: Lightweight database with migrations via Alembic

## Installation

### From PyPI (when published)

```bash
pip install magic-core
```

### From Source

```bash
git clone https://github.com/desplega-ai/magic
cd magic/core
uv sync
```

## Quick Start

### 1. Set up environment

Create a `.env` file:

```env
API_KEY=your-secret-api-key
DATABASE_PATH=/tmp/magic-db.sqlite
LOG_LEVEL=INFO
ENV=local
```

### 2. Run migrations

```bash
make migrate
# or
cli db migrate
```

### 3. Start the server

**Development:**
```bash
make serve
# or
cli serve --reload
```

**Production:**
```bash
make prod
# or
cli prod --workers 4
```

The API will be available at `http://localhost:13370`

## CLI Commands

The `cli` command provides several utilities:

### Database Management
- `cli db migrate` - Run database migrations

### Server
- `cli serve [--port PORT] [--reload]` - Start development server
- `cli prod [--port PORT] [--workers N]` - Start production server

## Development

### Setup

```bash
# Install with dev dependencies
make dev

# Or with uv
uv sync --all-groups
```

### Code Quality

```bash
# Format code
make format

# Lint and type check
make lint

# Run all checks (CI-friendly)
make check
```

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:13370/docs`
- ReDoc: `http://localhost:13370/redoc`

### Key Endpoints

- `GET /v1/health` - Health check
- `GET /v1/check` - API key validation
- `GET /v1/definitions` - List workflow definitions
- `POST /v1/definitions` - Create workflow definition
- `GET /v1/events` - List events
- `GET /v1/outputs` - List evaluation outputs

## Architecture

### Models

- **Event**: Workflow events with typed data
- **Definition**: Workflow definitions with triggers, actions, and assertions
- **EvalOutput**: Evaluation results with execution info

### Database

- **Engine**: SQLite with async support (aiosqlite)
- **Migrations**: Alembic for schema management
- **Transactions**: Context-managed with retry logic

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | (required) | API authentication key |
| `DATABASE_PATH` | `/tmp/magic-db.sqlite` | SQLite database path |
| `LOG_LEVEL` | `WARNING` | Logging level |
| `ENV` | `local` | Environment name |
| `DEBUG` | `false` | Enable SQL echo |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting: `make check`
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details

## Requirements

- Python 3.12+
- SQLite 3.35+ (for JSON support)

## Technologies

- **FastAPI** - Modern web framework
- **SQLModel** - SQL databases with Pydantic models
- **Alembic** - Database migrations
- **Click** - CLI framework
- **Ruff** - Fast Python linter and formatter
- **mypy** - Static type checker
