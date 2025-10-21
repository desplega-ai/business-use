# Core Architecture - Flow Evaluation Engine

This document describes the refactored architecture of the flow evaluation engine, designed for production use at scale.

## Architecture Overview

The codebase follows **Hexagonal Architecture** (Ports & Adapters) with clear separation of concerns:

```
┌─────────────────────────────────────────────────────┐
│                    API Layer                        │
│              (FastAPI endpoints)                    │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│              Orchestration Layer                    │
│                (src/eval/)                          │
│   Combines domain, execution, and storage           │
└────┬───────────────┬──────────────────┬─────────────┘
     │               │                  │
┌────▼────┐   ┌─────▼─────┐   ┌────────▼─────────┐
│ Domain  │   │ Execution │   │    Adapters      │
│ Logic   │   │  Layer    │   │   (Storage)      │
│         │   │           │   │                  │
│ Pure    │   │ Pluggable │   │ SQLite-specific  │
│ Python  │   │ Evaluator │   │ queries          │
└─────────┘   └───────────┘   └──────────────────┘
```

## Directory Structure

```
core/src/
├── domain/              # Pure business logic (ZERO dependencies)
│   ├── types.py         # TypedDict definitions (lightweight!)
│   ├── graph.py         # Graph construction & traversal
│   └── evaluation.py    # Flow validation logic
│
├── execution/           # Pluggable expression evaluation
│   └── python_eval.py   # Python implementation (CEL/JS stubs)
│
├── adapters/            # Infrastructure adapters
│   └── sqlite.py        # SQLite storage adapter
│
├── eval/                # Public API & orchestration
│   ├── __init__.py      # Public exports
│   └── eval.py          # Orchestrates domain + adapters
│
├── api/                 # HTTP API layer
│   ├── api.py           # FastAPI endpoints
│   └── models.py        # Request/response schemas
│
└── models.py            # Core data models (Event, Node, etc)
```

## Design Principles

### 1. **Zero Dependencies in Domain Layer**

The `domain/` directory contains pure business logic with NO external dependencies:
- No database imports
- No HTTP imports
- No framework-specific code
- Only Python stdlib + typing

**Why?** This allows desplega.ai to:
- Reuse core logic with different storage backends
- Test business logic in isolation
- Swap out infrastructure without touching domain code

### 2. **TypedDict for Internal Types**

We use `TypedDict` instead of Pydantic for internal return values:

```python
# Lightweight, no validation overhead
class FlowGraph(TypedDict):
    graph: dict[str, list[str]]
    nodes: dict[str, Node]
```

**Why?** TypedDict is:
- Lightweight (no runtime overhead)
- Perfect for internal APIs
- Clear type hints for IDEs
- No serialization/validation needed

### 3. **Protocol-Based Evaluator**

The expression evaluator uses Python's `Protocol` for pluggability:

```python
class ExprEvaluator(Protocol):
    def evaluate(self, expr: Expr, data: dict, ctx: dict) -> bool: ...
```

**Why?** This allows:
- Swapping Python eval for CEL, JS, or custom implementations
- Testing with mock evaluators
- Gradual migration to new evaluation engines

### 4. **Adapter Pattern for Storage**

Database operations are isolated in `adapters/sqlite.py`:

```python
class SqliteEventStorage:
    async def get_events_by_run(self, run_id: str, flow: str, session): ...
    async def get_nodes_by_flow(self, flow: str, session): ...
```

**Why?** This allows:
- Easy migration to PostgreSQL, MongoDB, etc. at desplega.ai
- Testing domain logic without database
- Clear separation between business logic and data access

## Key Changes from Legacy Implementation

### 1. **Use run_id + flow Instead of Time Window**

**Old approach:**
```python
# Query events by time window + filter matching (slow!)
events = query_by_time_range(ts_start, ts_end)
filtered = [ev for ev in events if matches_filter(ev)]
```

**New approach:**
```python
# Direct query by run_id + flow (fast!)
events = await storage.get_events_by_run(run_id, flow, session)
```

### 2. **Remove Magic* Models**

**Old:** Used `MagicEvent`, `MagicDefinition` (legacy models)
**New:** Uses `Event`, `Node` from `src.models` (current models)

### 3. **Pluggable Architecture**

**Old:** Monolithic 400-line file with mixed concerns
**New:** Clean separation into domain, execution, adapters

## Usage

### CLI Commands (Recommended for Development)

#### 1. Explore Flow Definitions

View flow graph structure without running evaluation:

```bash
# Interactive flow selection
uv run cli show-graph

# Show specific flow
uv run cli show-graph checkout

# Just list nodes
uv run cli show-graph checkout --nodes-only
```

**Output:**
```
Available flows:
  1. checkout (4 nodes)
  2. onboarding (6 nodes)

Select flow number: 1

Flow Graph:
------------------------------------------------------------
  [○] cart_created
   │
   ↓
  [○] payment_initiated
   │
   ↓
  [○] payment_processed
------------------------------------------------------------
```

#### 2. Evaluate Flow Runs

Evaluate a flow run directly from the command line:

```bash
# Basic evaluation
uv run cli eval-run run_123 checkout

# Show ASCII graph visualization
uv run cli eval-run run_123 checkout --show-graph

# Combine graph + verbose for full context
uv run cli eval-run run_123 checkout -g -v

# Verbose output with execution details
uv run cli eval-run run_123 checkout --verbose

# JSON output (for automation/scripts)
uv run cli eval-run run_123 checkout --json-output

# Subgraph evaluation (start from specific node)
uv run cli eval-run run_123 checkout --start-node payment_processed
```

**Output example:**
```
Evaluating flow run: run_id=run_123, flow=checkout

============================================================
Status: PASSED
Elapsed: 45.23ms
Events processed: 5
Graph nodes: 4
============================================================

Flow Graph:
------------------------------------------------------------
  [✓] cart_created
   │
   ↓
  [✓] payment_initiated
   │
   ↓
  [✓] payment_processed
   │
   ↓
  [✓] order_completed
------------------------------------------------------------

Summary:
  ✓ Passed: 4
```

### HTTP API (Production)

#### New API (Preferred)

Evaluate an entire flow run by `run_id` + `flow`:

```bash
curl -X POST http://localhost:13370/v1/run-eval \
  -H "X-Api-Key: your-key" \
  -d '{
    "run_id": "run_12345",
    "flow": "checkout"
  }'
```

#### Legacy API (Backward Compatible)

Evaluate from a specific event:

```bash
curl -X POST http://localhost:13370/v1/run-eval \
  -H "X-Api-Key: your-key" \
  -d '{
    "ev_id": "evt_abc123",
    "whole_graph": false
  }'
```

## Module Responsibilities

### `domain/types.py`
- Defines TypedDict return types
- No logic, just type definitions
- Used by domain functions

### `domain/graph.py`
- Builds DAG from node definitions
- Topological sort into layers
- Subgraph filtering
- **Zero dependencies!**

### `domain/evaluation.py`
- Matches events to graph layers
- Validates flow execution (timeouts, conditions)
- Takes `ExprEvaluator` protocol as dependency
- **Pure business logic**

### `execution/python_eval.py`
- Implements `ExprEvaluator` protocol
- Safe Python expression evaluation
- Stubs for CEL and JS (future)

### `adapters/sqlite.py`
- Encapsulates all SQLite queries
- Fetches events by run_id + flow
- Fetches nodes by flow
- **Easy to swap for other databases**

### `eval/eval.py`
- **Orchestration layer**
- Combines domain + execution + adapters
- Two public functions:
  - `eval_flow_run()` - New API
  - `eval_event()` - Legacy API

## For desplega.ai: How to Adapt

### 1. Swap Storage Backend

Replace `SqliteEventStorage` with your custom adapter:

```python
# adapters/postgres.py
class PostgresEventStorage:
    async def get_events_by_run(self, run_id, flow, session):
        # Your Postgres query here
        ...
```

Then update `eval/eval.py`:
```python
-from src.adapters.sqlite import SqliteEventStorage
+from src.adapters.postgres import PostgresEventStorage

-storage = SqliteEventStorage()
+storage = PostgresEventStorage()
```

### 2. Swap Evaluator

Replace `PythonEvaluator` with your custom implementation:

```python
# execution/cel_eval.py
class CELEvaluator:
    def evaluate(self, expr, data, ctx):
        # CEL evaluation here
        ...
```

Then update `eval/eval.py`:
```python
-from src.execution.python_eval import PythonEvaluator
+from src.execution.cel_eval import CELEvaluator

-evaluator = PythonEvaluator()
+evaluator = CELEvaluator()
```

### 3. Reuse Domain Logic

The **entire `domain/` directory** can be copied as-is:
- No database dependencies
- No framework dependencies
- Pure Python logic

Just plug in your own adapters and evaluators!

## Testing Strategy

### Domain Layer
Test in complete isolation:
```python
def test_build_graph():
    nodes = [
        Node(id="a", dep_ids=[]),
        Node(id="b", dep_ids=["a"]),
    ]
    graph = build_flow_graph(nodes)
    assert graph["graph"]["a"] == ["b"]
```

### Execution Layer
Test with mock expressions:
```python
def test_python_evaluator():
    evaluator = PythonEvaluator()
    expr = Expr(engine="python", script="data['x'] > 0")
    assert evaluator.evaluate(expr, {"x": 1}, {}) == True
```

### Adapters Layer
Test with test database:
```python
async def test_get_events_by_run(test_db):
    storage = SqliteEventStorage()
    events = await storage.get_events_by_run("run1", "flow1", test_db)
    assert len(events) > 0
```

### Integration Tests
Test full orchestration:
```python
async def test_eval_flow_run():
    result = await eval_flow_run("run_123", "checkout")
    assert result.status == "passed"
```

## Performance Considerations

### Old Implementation Issues
- Time-window queries with large date ranges
- N² loops for event matching
- Mixed concerns in monolithic file
- Hard to optimize or cache

### New Implementation Benefits
- Direct `run_id + flow` queries (indexed!)
- Clear separation allows caching at adapter layer
- Domain logic can be profiled independently
- Easy to add batching, parallel processing

## References

**Inspired by:**
- **Temporal SDK**: Core execution logic separated from infrastructure
- **Prefect**: Clean `src/` structure, separate schemas
- **Hexagonal Architecture**: Domain at center, adapters at edges

**Resources:**
- [Architecture Patterns with Python](https://www.cosmicpython.com/)
- [Temporal Python SDK](https://github.com/temporalio/sdk-python)
- [Hexagonal Architecture in Python](https://douwevandermeij.medium.com/hexagonal-architecture-in-python-7468c2606b63)

---

**Version:** 1.0
**Last Updated:** 2025-01-21
**Status:** Production-ready
