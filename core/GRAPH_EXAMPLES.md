# Graph Visualization Examples

Examples of how different flow graphs are displayed in the CLI.

## Simple Linear Flow

```
Flow: checkout
Nodes: 4

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
```

## Parallel Branches

```
Flow: onboarding
Nodes: 6

  [✓] user_registered
   │
   ↓
  [✓] email_verification    [✓] profile_setup
   │                         │
   ↓                         ↓
  [✓] welcome_email_sent    [✓] avatar_uploaded
                             │
                             ↓
                            [✓] onboarding_completed
```

## Failed Validation

```
Flow: payment
Nodes: 5

  [✓] cart_created
   │
   ↓
  [✓] payment_initiated
   │
   ↓
  [✗] fraud_check_failed  ← Failed!
   │
   ↓
  [⊘] payment_processed   ← Skipped due to failure
   │
   ↓
  [⊘] order_completed     ← Skipped due to failure
```

## Complex DAG

```
Flow: fulfillment
Nodes: 8

  [✓] order_placed
   │
   ↓
  [✓] inventory_reserved    [✓] payment_authorized
   │                         │
   ↓                         ↓
  [✓] shipping_label        [✓] payment_captured
   │                         │
   ↓                         ↓
  [✓] item_shipped    [✓] invoice_generated
                       │
                       ↓
                      [✓] fulfillment_complete
```

## Symbols Legend

- `[✓]` - **Passed** (green) - Node executed successfully
- `[✗]` - **Failed** (red) - Node validation failed
- `[⊘]` - **Skipped** (yellow) - Node skipped due to upstream failure
- `[○]` - **Pending** (white) - Node not yet executed
- `│` - Vertical connection
- `↓` - Flow direction

## Usage Tips

### 1. Quick Visual Inspection

Use `--show-graph` to quickly see the flow structure and status:
```bash
uv run cli eval-run order_123 checkout -g
```

### 2. Combine with Verbose

Get both visual and detailed info:
```bash
uv run cli eval-run order_123 checkout -g -v
```

### 3. CI/CD Visualization

In CI/CD, you can capture the graph for reports:
```bash
uv run cli eval-run $RUN_ID $FLOW -g > flow_validation.txt
```

### 4. Debugging Failed Flows

Failed nodes are highlighted in red, making it easy to spot issues:
```bash
uv run cli eval-run failed_run_456 payment -g
```

## How the Graph is Rendered

The graph visualization uses a **breadth-first traversal** to arrange nodes in layers:

1. **Layer 0**: Root nodes (no dependencies)
2. **Layer 1**: Nodes that depend only on Layer 0
3. **Layer 2**: Nodes that depend on Layer 0 or 1
4. And so on...

### Example: Layered Rendering

Given this graph definition:
```python
{
  "a": ["b", "c"],  # a points to b and c
  "b": ["d"],       # b points to d
  "c": ["d"],       # c points to d
  "d": []           # d is a leaf
}
```

Renders as:
```
  [✓] a          ← Layer 0 (root)
   │
   ↓
  [✓] b    [✓] c  ← Layer 1 (depends on a)
   │        │
   ↓        ↓
  [✓] d          ← Layer 2 (depends on b or c)
```

## Advanced: Subgraph Visualization

When using `--start-node`, only the subgraph is shown:

**Full graph:**
```
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
```

**Subgraph from `payment_processed`:**
```bash
uv run cli eval-run run_123 checkout --start-node payment_processed -g
```

Shows:
```
  [✓] payment_processed
   │
   ↓
  [✓] order_completed
```

## Limitations

- **Horizontal spacing**: Nodes at the same level are shown side-by-side (up to 4-5 before wrapping)
- **Complex graphs**: Very wide graphs (>5 parallel branches) may wrap awkwardly
- **Cross-layer edges**: Only shows direct parent→child relationships
- **Unicode support**: Requires terminal with Unicode support for symbols

## Future Enhancements

Potential improvements for the graph visualization:

1. **Interactive mode** - Navigate through nodes with arrow keys
2. **Mermaid export** - Generate Mermaid diagram markdown
3. **DOT export** - Generate Graphviz DOT format for complex graphs
4. **Timeline view** - Show execution order with timestamps
5. **Diff mode** - Compare two flow runs side-by-side

---

**Tip**: For very complex graphs, use `--json-output` and pipe to a graph visualization tool like Graphviz or Mermaid.
