.PHONY: format lint check test install dev migrate serve prod help

help:
	@echo "Available commands:"
	@echo "  make format    - Format code with ruff"
	@echo "  make lint      - Lint code with ruff"
	@echo "  make check     - Run format check and lint (CI-friendly)"
	@echo "  make test      - Run tests with pytest"
	@echo "  make install   - Install dependencies"
	@echo "  make dev       - Install dependencies including dev tools"
	@echo "  make migrate   - Run database migrations"
	@echo "  make serve     - Run development server"
	@echo "  make prod      - Run production server"

format:
	@echo "Formatting code with ruff..."
	uv run ruff format .
	uv run ruff check --fix .

lint:
	@echo "Linting code with ruff..."
	uv run ruff check .
	@echo "Type checking with mypy..."
	uv run mypy .

check:
	@echo "Running format check..."
	uv run ruff format --check .
	@echo "Running lint check..."
	uv run ruff check .
	@echo "Running type check..."
	uv run mypy .

test:
	@echo "Running tests with pytest..."
	uv run pytest tests/ -v

install:
	@echo "Installing dependencies..."
	uv sync

dev:
	@echo "Installing dependencies with dev tools..."
	uv sync --all-groups

migrate:
	@echo "Running database migrations..."
	uv run cli db migrate

serve:
	@echo "Starting development server..."
	uv run cli serve --reload

prod:
	@echo "Starting production server..."
	uv run cli prod
