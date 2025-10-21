# CLI Reference

Quick reference for all CLI commands.

## Getting Started

```bash
# Show all available commands
uv run cli --help

# Show help for specific command
uv run cli eval-run --help
```

## Commands

### `eval-run` - Evaluate Flow Run

Evaluate whether a flow run executed correctly according to its graph definition.

**Syntax:**
```bash
uv run cli eval-run RUN_ID FLOW [OPTIONS]
```

**Arguments:**
- `RUN_ID` - The run identifier (e.g., user session, order ID)
- `FLOW` - The flow identifier (e.g., "checkout", "onboarding")

**Options:**
- `--start-node NODE_ID` - Start evaluation from specific node (subgraph only)
- `--json-output` - Output results as JSON (for automation)
- `--verbose`, `-v` - Show detailed execution info for each node
- `--show-graph`, `-g` - Show ASCII graph visualization with status indicators
- `--help` - Show help for this command

**Examples:**

```bash
# Basic evaluation - shows pass/fail summary
uv run cli eval-run run_123 checkout

# Show ASCII graph visualization
uv run cli eval-run run_123 checkout --show-graph

# Combine graph + verbose for complete picture
uv run cli eval-run run_123 checkout -g -v

# Verbose output - shows detailed node execution
uv run cli eval-run run_123 checkout --verbose

# JSON output - for scripts/automation
uv run cli eval-run run_123 checkout --json-output

# Subgraph evaluation - only validate from specific node onwards
uv run cli eval-run run_123 checkout --start-node payment_processed

# Combine options
uv run cli eval-run run_123 checkout --verbose --start-node order_created
```

**Output (Default):**
```
Evaluating flow run: run_id=run_123, flow=checkout

============================================================
Status: PASSED
Elapsed: 45.23ms
Events processed: 5
Graph nodes: 4
============================================================

Summary:
  ✓ Passed: 4

Use --verbose for detailed execution info
```

**Output (With Graph):**
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

**Symbols:**
- `✓` - Passed (green)
- `✗` - Failed (red)
- `⊘` - Skipped (yellow)
- `│ ↓` - Flow direction

**Output (Verbose):**
```
Evaluating flow run: run_id=run_123, flow=checkout

============================================================
Status: PASSED
Elapsed: 45.23ms
Events processed: 5
Graph nodes: 4
============================================================

Execution Details:
------------------------------------------------------------

Node: cart_created
  Status: passed
  Message: Root node, no upstream dependencies
  Events: 1
  Upstream events: 0
  Elapsed: 0.12ms

Node: payment_initiated
  Status: passed
  Dependencies: cart_created
  Message: Dependency found for payment_initiated, no conditions
  Events: 1
  Upstream events: 1
  Elapsed: 0.34ms

Node: payment_processed
  Status: passed
  Dependencies: payment_initiated
  Message: Timeout satisfied: 234.5ms <= 5000ms
  Events: 1
  Upstream events: 1
  Elapsed: 0.56ms

Node: order_completed
  Status: passed
  Dependencies: payment_processed
  Message: All conditions passed
  Events: 1
  Upstream events: 1
  Elapsed: 0.23ms
------------------------------------------------------------
```

**Output (JSON):**
```json
{
  "run_id": "run_123",
  "flow": "checkout",
  "status": "passed",
  "elapsed_ns": 45234567,
  "elapsed_ms": 45.234567,
  "graph": {
    "cart_created": ["payment_initiated"],
    "payment_initiated": ["payment_processed"],
    "payment_processed": ["order_completed"],
    "order_completed": []
  },
  "exec_info": [
    {
      "node_id": "cart_created",
      "dep_node_ids": [],
      "status": "passed",
      "message": "Root node, no upstream dependencies",
      "error": null,
      "elapsed_ns": 120000,
      "ev_ids": ["evt_1"],
      "upstream_ev_ids": []
    }
  ],
  "ev_ids": ["evt_1", "evt_2", "evt_3", "evt_4", "evt_5"]
}
```

**Exit Codes:**
- `0` - Evaluation completed successfully
- `1` - Error occurred (invalid run_id, flow not found, etc.)

---

### `show-graph` - Display Flow Graph

Show the flow graph definition without running evaluation.

**Syntax:**
```bash
uv run cli show-graph [FLOW] [OPTIONS]
```

**Arguments:**
- `FLOW` - Flow identifier (optional - prompts for selection if omitted)

**Options:**
- `--nodes-only` - Show only node names without visualization
- `--help` - Show help for this command

**Examples:**

```bash
# Interactive flow selection (shows list to choose from)
uv run cli show-graph

# Show specific flow graph
uv run cli show-graph checkout

# Just list nodes without visualization
uv run cli show-graph checkout --nodes-only
```

**Output (Interactive Selection):**
```
Available flows:
  1. checkout (4 nodes)
  2. onboarding (6 nodes)
  3. refund (3 nodes)

Select flow number (or 'q' to quit): 1

============================================================
Flow: checkout
Nodes: 4
============================================================

Flow Graph:
------------------------------------------------------------
  [○] cart_created
   │
   ↓
  [○] payment_initiated
   │
   ↓
  [○] payment_processed
   │
   ↓
  [○] order_completed
------------------------------------------------------------

Execution Layers:
  Layer 0: cart_created
  Layer 1: payment_initiated
  Layer 2: payment_processed
  Layer 3: order_completed

Node Details:

  cart_created:
    Type: act
    Source: code
    Dependencies: (none)

  payment_initiated:
    Type: act
    Source: code
    Dependencies: cart_created
    Timeout: 5000ms

  payment_processed:
    Type: act
    Source: code
    Dependencies: payment_initiated
    Timeout: 30000ms
    Filter: data["status"] == "authorized"

  order_completed:
    Type: act
    Source: code
    Dependencies: payment_processed
```

**Output (Nodes Only):**
```
============================================================
Flow: checkout
Nodes: 4
============================================================

Nodes:
  [act]        cart_created
  [act]        payment_initiated (depends on: cart_created)
  [act]        payment_processed (depends on: payment_initiated)
  [act]        order_completed (depends on: payment_processed)
```

**Use Cases:**

1. **Explore available flows** - Interactive mode shows all flows
2. **Understand graph structure** - See dependencies and layers
3. **Review node definitions** - Check filters, validators, timeouts
4. **Documentation** - Generate flow diagrams for docs
5. **Debugging** - Understand expected execution order

---

### `serve` - Development Server

Run the FastAPI server in development mode with auto-reload.

**Syntax:**
```bash
uv run cli serve [OPTIONS]
```

**Options:**
- `--host HOST` - Host to bind to (default: 0.0.0.0)
- `--port PORT` - Port to bind to (default: 13370)
- `--reload` - Enable auto-reload on file changes

**Examples:**

```bash
# Run on default port 13370
uv run cli serve

# Run on custom port with auto-reload
uv run cli serve --port 8000 --reload

# Bind to specific host
uv run cli serve --host localhost --port 3000
```

---

### `prod` - Production Server

Run the FastAPI server in production mode with multiple workers.

**Syntax:**
```bash
uv run cli prod [OPTIONS]
```

**Options:**
- `--host HOST` - Host to bind to (default: 0.0.0.0)
- `--port PORT` - Port to bind to (default: 13370)
- `--workers N` - Number of worker processes (default: 4)

**Examples:**

```bash
# Run with default settings (4 workers)
uv run cli prod

# Run with 8 workers on custom port
uv run cli prod --workers 8 --port 8000

# Production deployment
uv run cli prod --host 0.0.0.0 --port 80 --workers 16
```

---

### `db migrate` - Database Migrations

Run database migrations to upgrade schema.

**Syntax:**
```bash
uv run cli db migrate [REVISION]
```

**Arguments:**
- `REVISION` - Target revision (default: "head" for latest)

**Examples:**

```bash
# Upgrade to latest
uv run cli db migrate

# Upgrade to specific revision
uv run cli db migrate ae1027a6

# Upgrade one version
uv run cli db migrate +1

# Downgrade one version
uv run cli db migrate -1
```

---

## Common Workflows

### Exploring Flows

```bash
# 1. See all available flows interactively
uv run cli show-graph

# 2. Examine specific flow structure
uv run cli show-graph checkout

# 3. List all nodes in a flow
uv run cli show-graph checkout --nodes-only
```

### Development Workflow

```bash
# 1. Understand the flow structure first
uv run cli show-graph checkout

# 2. Start development server with auto-reload
uv run cli serve --reload

# 3. In another terminal, test evaluation
uv run cli eval-run test_run_001 checkout --verbose

# 4. Check if events are flowing correctly
uv run cli eval-run test_run_001 checkout --json-output | jq '.status'
```

### Testing Workflow

```bash
# Run evaluation and capture output
OUTPUT=$(uv run cli eval-run run_123 checkout --json-output)

# Check status in scripts
if echo "$OUTPUT" | jq -e '.status == "passed"' > /dev/null; then
  echo "✓ Flow validation passed"
else
  echo "✗ Flow validation failed"
  echo "$OUTPUT" | jq '.exec_info[] | select(.status == "failed")'
fi
```

### CI/CD Integration

```bash
#!/bin/bash
# Validate all test runs
for run_id in $(cat test_runs.txt); do
  echo "Validating run: $run_id"
  uv run cli eval-run "$run_id" checkout --json-output > "results/$run_id.json"

  status=$(jq -r '.status' "results/$run_id.json")
  if [ "$status" != "passed" ]; then
    echo "❌ Run $run_id failed!"
    exit 1
  fi
done

echo "✅ All runs validated successfully"
```

---

## Tips

1. **Explore flows first** - Use `uv run cli show-graph` to see all available flows
2. **Use `--json-output` for automation** - Easy to parse with `jq` or other tools
3. **Use `--verbose` during debugging** - See exactly which node failed and why
4. **Use `--show-graph` to visualize** - Quickly spot flow structure and failures
5. **Use `--start-node` for subgraph testing** - Test specific parts of your flow
6. **Pipe to `jq` for filtering** - `... --json-output | jq '.status'`
7. **Check exit codes in scripts** - `$?` will be 0 on success, 1 on error
8. **Interactive selection** - Omit flow name to get an interactive list

---

**Version:** 1.0
**Last Updated:** 2025-01-21
