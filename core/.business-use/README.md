# Business Use Node Definitions

This directory contains YAML-based node definitions for your flows.

## File Structure

Each YAML file defines one flow with its nodes:

```yaml
flow: <flow-name>
nodes:
  - id: <node-id>
    type: trigger | hook | generic
    description: <description>
    dep_ids:
      - <dependency-node-id>
    filter:
      engine: python | js | cel
      script: <filter-expression>
    validator:
      engine: python | js | cel
      script: <validator-expression>
    conditions:
      - timeout_ms: <milliseconds>
    handler: http_request | test_run | command
    handler_input:
      params:
        url: <url>
        method: GET | POST | PUT | DELETE | PATCH
        headers: {}
        body: <body>
        timeout_ms: <milliseconds>
```

## Commands

### Sync nodes from YAML to database
```bash
uv run cli sync-nodes .business-use/                 # Sync all YAML files
uv run cli sync-nodes .business-use/checkout.yaml    # Sync single file
```

### Export nodes from database to YAML
```bash
uv run cli export-nodes checkout                      # Print to stdout
uv run cli export-nodes checkout checkout.yaml        # Save to file
```

### Validate YAML files
```bash
uv run cli validate-nodes .business-use/              # Validate all files
uv run cli validate-nodes .business-use/checkout.yaml # Validate single file
```

## Important Notes

- Nodes synced from YAML have `source='code'` and cannot be modified via the API
- Use `sync-nodes` to update existing nodes (upsert behavior)
- One flow per YAML file is recommended for clarity
- All YAML files in this directory (and subdirectories) will be processed when syncing the directory
