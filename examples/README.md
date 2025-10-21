# Business-Use SDK Examples

This directory contains standalone, runnable examples for the Business-Use SDKs.

## Available Examples

### 🐍 [Python Example](./python/)

Demonstrates the Python SDK with:
- Event tracking with `ensure()`
- Assertions with validator functions
- Filters and lambdas
- Conditions and metadata
- Full logging and debugging

**Quick start:**
```bash
cd python
uv sync
uv run python example.py
```

### 📘 [TypeScript Example](./typescript/)

Demonstrates the TypeScript SDK with:
- Type-safe event tracking
- Typed validator and filter functions
- Dynamic run IDs
- Full IntelliSense support
- Conditions and metadata

**Quick start:**
```bash
cd typescript
npm install
npm start
```

## Prerequisites

All examples require:
- **Business-Use backend** running on `http://localhost:13370`
- Proper API key (default: `"secret"` for local development)

To start the backend:
```bash
# From the repository root
cd core
uv run cli db upgrade  # Initialize database
uv run cli serve       # Start the server
```

## Example Features

Both examples demonstrate:

✅ **SDK Initialization** - Connect to the backend
✅ **Action Tracking** - Track business events (`ensure()` without validator)
✅ **Assertions** - Validate business rules (`ensure()` with validator)
✅ **Client Filters** - Skip events based on conditions
✅ **Server Filters** - Send filter logic to backend
✅ **Dependencies** - Link events with `dep_ids`
✅ **Dynamic Values** - Use lambdas for run IDs and filters
✅ **Conditions** - Set timeouts and constraints
✅ **Metadata** - Add custom metadata to events
✅ **Graceful Shutdown** - Flush events before exit

## Standalone Design

Each example is a **standalone project** with its own:
- Package configuration (`pyproject.toml` or `package.json`)
- Dependencies management
- README with detailed instructions
- TypeScript configuration (TS example only)

This makes it easy to:
- Copy examples to your own project
- Run examples independently
- Understand SDK usage in isolation
- Test different SDK versions

## Next Steps

After running the examples:

1. **View events** - Check the backend UI at `http://localhost:3007`
2. **Explore flows** - See how events are connected
3. **Customize** - Modify the examples for your use case
4. **Integrate** - Copy patterns into your application

## Learn More

- [Python SDK Documentation](../sdk-py/README.md)
- [TypeScript SDK Documentation](../sdk-js/README.md)
- [Core API Documentation](../core/README.md)
