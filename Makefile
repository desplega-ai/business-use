.PHONY: help install format lint typecheck test clean all

# Default target
help:
	@echo "Business-Use Monorepo - Available Commands"
	@echo "==========================================="
	@echo ""
	@echo "Development:"
	@echo "  make install       - Install all dependencies"
	@echo "  make format        - Format code in all projects"
	@echo "  make lint          - Lint code in all projects"
	@echo "  make typecheck     - Run type checking in all projects"
	@echo "  make test          - Run tests in all projects"
	@echo "  make all           - Run format, lint, typecheck, and test"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         - Remove build artifacts and caches"
	@echo ""
	@echo "Individual Projects:"
	@echo "  make format-core   - Format core backend"
	@echo "  make format-py     - Format Python SDK"
	@echo "  make format-js     - Format JavaScript SDK"
	@echo "  make format-ui     - Format UI"
	@echo "  make lint-core     - Lint core backend"
	@echo "  make lint-py       - Lint Python SDK"
	@echo "  make lint-js       - Lint JavaScript SDK"
	@echo "  make lint-ui       - Lint UI"

# Install all dependencies
install:
	@echo "📦 Installing dependencies..."
	@echo ""
	@echo "▶ Core backend..."
	cd core && uv sync
	@echo ""
	@echo "▶ Python SDK..."
	cd sdk-py && uv sync
	@echo ""
	@echo "▶ JavaScript SDK..."
	cd sdk-js && pnpm install
	@echo ""
	@echo "▶ UI..."
	cd ui && pnpm install
	@echo ""
	@echo "✅ All dependencies installed!"

# Format all projects
format: format-core format-py format-js format-ui
	@echo ""
	@echo "✅ All projects formatted!"

format-core:
	@echo "🎨 Formatting core backend..."
	cd core && uv run ruff format src/

format-py:
	@echo "🎨 Formatting Python SDK..."
	cd sdk-py && uv run ruff format src/ tests/

format-js:
	@echo "🎨 Formatting JavaScript SDK..."
	@if [ ! -d "sdk-js/node_modules" ]; then \
		echo "📦 Installing JavaScript SDK dependencies first..."; \
		cd sdk-js && pnpm install; \
	fi
	cd sdk-js && pnpm format

format-ui:
	@echo "🎨 Formatting UI..."
	@if [ ! -d "ui/node_modules" ]; then \
		echo "📦 Installing UI dependencies first..."; \
		cd ui && pnpm install; \
	fi
	cd ui && pnpm format

# Lint all projects
lint: lint-core lint-py lint-js lint-ui
	@echo ""
	@echo "✅ All projects linted!"

lint-core:
	@echo "🔍 Linting core backend..."
	cd core && uv run ruff check src/ --fix

lint-py:
	@echo "🔍 Linting Python SDK..."
	cd sdk-py && uv run ruff check src/ tests/ --fix

lint-js:
	@echo "🔍 Linting JavaScript SDK..."
	@if [ ! -d "sdk-js/node_modules" ]; then \
		echo "📦 Installing JavaScript SDK dependencies first..."; \
		cd sdk-js && pnpm install; \
	fi
	cd sdk-js && pnpm lint:fix

lint-ui:
	@echo "🔍 Linting UI..."
	@if [ ! -d "ui/node_modules" ]; then \
		echo "📦 Installing UI dependencies first..."; \
		cd ui && pnpm install; \
	fi
	cd ui && pnpm lint:fix

# Type checking
typecheck: typecheck-core typecheck-py typecheck-js typecheck-ui
	@echo ""
	@echo "✅ All projects type-checked!"

typecheck-core:
	@echo "🔎 Type checking core backend..."
	cd core && uv run mypy src/

typecheck-py:
	@echo "🔎 Type checking Python SDK..."
	cd sdk-py && uv run mypy src/

typecheck-js:
	@echo "🔎 Type checking JavaScript SDK..."
	@if [ ! -d "sdk-js/node_modules" ]; then \
		echo "📦 Installing JavaScript SDK dependencies first..."; \
		cd sdk-js && pnpm install; \
	fi
	cd sdk-js && pnpm typecheck

typecheck-ui:
	@echo "🔎 Type checking UI..."
	@if [ ! -d "ui/node_modules" ]; then \
		echo "📦 Installing UI dependencies first..."; \
		cd ui && pnpm install; \
	fi
	cd ui && pnpm typecheck

# Run tests
test: test-core test-py test-js
	@echo ""
	@echo "✅ All tests passed!"

test-core:
	@echo "🧪 Testing core backend..."
	cd core && uv run pytest

test-py:
	@echo "🧪 Testing Python SDK..."
	cd sdk-py && uv run pytest

test-js:
	@echo "🧪 Testing JavaScript SDK..."
	@if [ ! -d "sdk-js/node_modules" ]; then \
		echo "📦 Installing JavaScript SDK dependencies first..."; \
		cd sdk-js && pnpm install; \
	fi
	cd sdk-js && pnpm test:run

# Clean build artifacts and caches
clean:
	@echo "🧹 Cleaning build artifacts and caches..."
	@echo ""
	@echo "▶ Core backend..."
	cd core && rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ dist/ build/ *.egg-info
	find core -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo ""
	@echo "▶ Python SDK..."
	cd sdk-py && rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ dist/ build/ *.egg-info
	find sdk-py -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo ""
	@echo "▶ JavaScript SDK..."
	cd sdk-js && rm -rf dist/ node_modules/.cache
	@echo ""
	@echo "▶ UI..."
	cd ui && rm -rf dist/ node_modules/.cache
	@echo ""
	@echo "✅ Cleanup complete!"

# Run everything (format, lint, typecheck, test)
all: format lint typecheck test
	@echo ""
	@echo "✅ All checks passed! Ready to commit."

# CI target (non-fixing lint)
ci: format-check lint-check typecheck test
	@echo ""
	@echo "✅ CI checks passed!"

# Format check (without fixing)
format-check:
	@echo "🔍 Checking code formatting..."
	@echo ""
	@echo "▶ Core backend..."
	cd core && uv run ruff format --check src/
	@echo ""
	@echo "▶ Python SDK..."
	cd sdk-py && uv run ruff format --check src/ tests/
	@echo ""
	@echo "▶ JavaScript SDK..."
	cd sdk-js && pnpm format:check
	@echo ""
	@echo "▶ UI..."
	cd ui && pnpm format:check
	@echo ""
	@echo "✅ All formatting is correct!"

# Lint check (without fixing)
lint-check:
	@echo "🔍 Checking linting..."
	@echo ""
	@echo "▶ Core backend..."
	cd core && uv run ruff check src/
	@echo ""
	@echo "▶ Python SDK..."
	cd sdk-py && uv run ruff check src/ tests/
	@echo ""
	@echo "▶ JavaScript SDK..."
	cd sdk-js && pnpm lint
	@echo ""
	@echo "▶ UI..."
	cd ui && pnpm lint
	@echo ""
	@echo "✅ All linting is correct!"

# Development servers
serve-core:
	@echo "🚀 Starting core backend..."
	cd core && uv run cli serve --reload

serve-ui:
	@echo "🚀 Starting UI..."
	cd ui && pnpm dev

# Quick development setup
dev: install
	@echo ""
	@echo "🎉 Development environment ready!"
	@echo ""
	@echo "To start developing:"
	@echo "  make serve-core    # Start backend (http://localhost:13370)"
	@echo "  make serve-ui      # Start UI (http://localhost:5173)"
	@echo ""
	@echo "Before committing:"
	@echo "  make all           # Run format, lint, typecheck, and test"
