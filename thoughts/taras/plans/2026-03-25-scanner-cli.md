---
date: 2026-03-25
author: Claude
status: completed
autonomy: critical
based_on: thoughts/taras/research/2026-03-25-static-analysis-sdk-extraction.md
---

# Scanner CLI Implementation Plan

## Overview

Implement `business-use scan` — a CLI command that statically analyzes JS/TS codebases to extract all `ensure()`, `act()`, `assert()` SDK call sites and push the resulting flow graph to the backend API. This enables automatic node registration without runtime execution, making it ideal for CI/CD integration.

## Current State Analysis

### What exists:
- **POC scanner** (`core/e2e-tests/poc_scanner.py`): ~365 lines, uses py-tree-sitter, tested against 9 JS/TS fixtures. Handles imports (named, aliased, namespace), string extraction, type inference, and graceful degradation on non-extractable values.
- **E2E fixtures** (`core/e2e-tests/js/` and `core/e2e-tests/py/`): 9 JS/TS files + 4 Python files covering happy path, edge cases, aliased imports, namespace imports, TSX, CJS require, and no-import scenarios.
- **CLI framework**: Click-based (`core/src/cli.py`), with existing groups (`workspace`, `db`, `server`, `flow`, `nodes`). The `nodes sync` command already does YAML → DB upsert with `source="code"`.
- **Node model** (`core/src/models.py:154-228`): Supports `act`/`assert` types, `source` field (`"code"`/`"manual"`), `dep_ids`, `conditions`, `description`.
- **API**: `POST /v1/nodes` exists but only accepts `generic`/`trigger`/`hook` types (`core/src/api/models.py:55-61`). No batch upsert endpoint.

### What's missing:
- Production scanner module in `core/src/`
- `business-use scan` CLI command
- Batch upsert API endpoint accepting `act`/`assert` types from scanner
- tree-sitter dependencies in `pyproject.toml`
- Unit/integration tests for scanner

### Key Discoveries:
- `NodeCreateSchema` restricts `type` to `generic|trigger|hook` (`core/src/api/models.py:61`) — scanner-pushed nodes need a separate schema allowing `act|assert`
- `NodeYAMLCreateSchema` already allows any `NodeType` (`core/src/api/models.py:64-67`) — could be reused or adapted
- `nodes sync` uses `source="code"` for YAML-synced nodes (`core/src/cli.py:1383`) — scanner should use a distinct source like `"scan"` to differentiate
- **`NodeSource` only allows `"code"` or `"manual"`** (`core/src/models.py:68-71`) — must be extended to include `"scan"` before using it as a source value
- **POC `TARGET_MODULES` only checks `"business-use"` and `"business_use"`** (`poc_scanner.py:19`) — must also match `@desplega.ai/business-use` (the actual scoped npm package name from `sdk-js/package.json:2`)
- POC scanner output format groups nodes by flow with source location — maps well to the Node model
- The `httpx` library is already a dependency (`core/pyproject.toml:38`) — can use it for API calls from scanner

## Desired End State

A working `business-use scan` command that:

```bash
# Dry-run: scan JS/TS files, print extracted nodes (no backend needed)
business-use scan ./src --dry-run
business-use scan ./src --dry-run --format table

# Push to backend API
business-use scan ./src --url http://localhost:13370 --api-key <key>

# Validate graph integrity without pushing
business-use scan ./src --validate

# Filter by flow
business-use scan ./src --flow checkout --dry-run
```

Verified by:
1. Scanner correctly extracts nodes from all 9 existing JS/TS fixture files
2. `--dry-run` outputs valid JSON matching the research spec
3. `--validate` catches broken `depIds` references and duplicate IDs
4. API push creates/updates nodes in backend with `source="scan"`
5. CI/CD integration works: `uvx business-use-core scan ./src --url $URL --api-key $KEY`

## Quick Verification Reference

Common commands:
- `cd core && uv run pytest tests/scanner/ -v` — scanner unit tests
- `cd core && uv run ruff format src/scanner/ tests/scanner/` — format
- `cd core && uv run ruff check src/scanner/ tests/scanner/ --fix` — lint
- `cd core && uv run mypy src/scanner/` — type check
- `cd core && uv run business-use scan e2e-tests/js --dry-run` — manual smoke test

Key files:
- `core/src/scanner/` — scanner module (new)
- `core/src/cli.py` — CLI entry point (modified: add `scan` command)
- `core/src/api/api.py` — API endpoints (modified: add batch upsert)
- `core/src/api/models.py` — API schemas (modified: add scan schema)
- `core/tests/scanner/` — scanner tests (new)
- `core/e2e-tests/` — existing fixtures (unchanged)

## What We're NOT Doing

- **Python SDK scanning** — JS/TS only in V1. Python scanning uses same tree-sitter approach but is a separate effort.
- **CJS `require()` support** — only ES module `import` syntax. POC already skips these correctly.
- **Watch mode** — `--watch` for re-scanning on file changes is a V2 feature.
- **Configuration file** (`.business-use/scan.yaml`) — V2. V1 uses CLI flags only.
- **Content-hash caching** — V2 optimization. V1 does a full scan each time (sub-second for typical projects anyway).
- **Local DB sync** — scanner only talks to API or dry-runs. No direct DB writes.
- **Wrapper function detection** — only direct `ensure()`/`act()`/`assert()` calls from `business-use` imports.

## Implementation Approach

1. **Promote POC to production module** — the POC scanner is well-structured and tested. Refactor it into `core/src/scanner/` with proper typing, error handling, and modularity.
2. **CLI first, API second** — get `--dry-run` working before building the API endpoint. This lets us validate the scanner independently.
3. **New batch upsert endpoint** — `POST /v1/nodes/scan` that accepts the scanner's output format and upserts nodes with `source="scan"`.
4. **Reuse existing patterns** — follow the `nodes sync` command pattern for upsert logic, the existing Click CLI patterns for the command, and `httpx` for API calls.

---

## Phase 1: Scanner Module — Promote POC to Production

### Overview
Move the POC scanner from `core/e2e-tests/poc_scanner.py` into a proper `core/src/scanner/` module with better structure, typing, and test coverage.

### Changes Required:

#### 1. Add tree-sitter dependencies
**File**: `core/pyproject.toml`
**Changes**: Add `tree-sitter>=0.25.0`, `tree-sitter-javascript>=0.25.0`, `tree-sitter-typescript>=0.23.0` as optional dependencies under a `[scan]` extra:

```toml
[project.optional-dependencies]
scan = [
    "tree-sitter>=0.25.0",
    "tree-sitter-javascript>=0.25.0",
    "tree-sitter-typescript>=0.23.0",
]
```

The `scan` command should check for these at runtime and print a helpful install message if missing:
`pip install business-use-core[scan]` or `uvx --with 'business-use-core[scan]' business-use-core scan ...`

For dev, add them to the dev dependency group so they're always available during development.

#### 1b. Extend `NodeSource` type
**File**: `core/src/models.py`
**Changes**: Add `"scan"` to the `NodeSource` literal:

```python
NodeSource = Literal[
    "code",
    "manual",
    "scan",
]
```

No database migration needed — the column is a plain `String` type, not an enum constraint. The `Literal` type is only enforced at the Python level.

#### 1c. Expand `TARGET_MODULES` to include scoped package name
**File**: `core/src/scanner/imports.py` (when creating from POC)
**Changes**: The POC's `TARGET_MODULES = {"business-use", "business_use"}` must be expanded to also match the scoped npm package:

```python
TARGET_MODULES = {"business-use", "business_use", "@desplega.ai/business-use"}
```

This ensures the scanner works with real-world imports (`import { ensure } from '@desplega.ai/business-use'`), not just the shorthand used in test fixtures.

#### 2. Create scanner module structure
```
core/src/scanner/
├── __init__.py          # Public API: scan_files(), scan_directory()
├── parser.py            # Tree-sitter parsing: language detection, AST walking
├── extractor.py         # Property extraction from AST nodes
├── imports.py           # Import analysis: named, aliased, namespace
├── models.py            # Scanner-specific types (ExtractedNode, ScanResult, ScanWarning)
└── validator.py         # Graph validation: dep_ids refs, duplicates, unreachable nodes
```

**`models.py`**: Define scanner output types using dataclasses or TypedDict:
- `ExtractedNode`: id, flow, type, dep_ids, has_validator, has_filter, description, conditions, source (file, line, column), warnings
- `ScanResult`: version, scanned_at, files_scanned, files_skipped, flows (dict of flow → list of ExtractedNode), warnings
- `ScanWarning`: file, line, message

**`imports.py`**: Extract from POC `extract_imports()` — handles named imports, aliased imports (`import { ensure as track }`), namespace imports (`import * as bu`).

**`parser.py`**: Extract from POC `get_language()`, `get_string_value()`, `_walk()`. Add proper error handling for file read failures.

**`extractor.py`**: Extract from POC `is_target_call()`, `extract_object_props()`, `scan_file()`. Compose imports + parser functions.

**`validator.py`**: New code — graph validation:
- Check all `dep_ids` reference existing nodes within same flow → warn if not
- Check for duplicate node IDs within a flow → warn
- Check for unreachable nodes (no path from root) → warn

**`__init__.py`**: Public API functions:
- `scan_files(paths: list[Path]) -> ScanResult` — scan specific files
- `scan_directory(path: Path, include: list[str], exclude: list[str]) -> ScanResult` — scan directory with glob patterns
- `validate_graph(result: ScanResult) -> list[ScanWarning]` — run graph validation

#### 3. Create scanner tests
**Directory**: `core/tests/scanner/`
**Files**:
- `test_imports.py` — test import detection (named, aliased, namespace, non-business-use)
- `test_extractor.py` — test node extraction against each e2e fixture
- `test_validator.py` — test graph validation (broken refs, duplicates, unreachable)
- `conftest.py` — fixtures pointing to `core/e2e-tests/js/` files

Tests should assert against the known-good POC results documented in the research (e.g., `basic-flow.ts` → 3 nodes, `aliased-import.ts` → 1 node, `no-business-use.ts` → 0 nodes).

### Success Criteria:

#### Automated Verification:
- [x] Scanner tests pass: `cd core && uv run pytest tests/scanner/ -v`
- [x] All 9 JS/TS fixtures produce expected results (match POC outputs from research doc)
- [x] Linting passes: `cd core && uv run ruff check src/scanner/ tests/scanner/`
- [x] Type checking passes: `cd core && uv run mypy src/scanner/`
- [x] Dependencies install cleanly: `cd core && uv sync`

#### Manual Verification:
- [x] `uv run python -c "from src.scanner import scan_directory; print(scan_directory('e2e-tests/js'))"` produces valid output
- [x] Validator catches broken dep_ids reference (e.g., a node referencing non-existent dep)
- [x] No-import files are skipped correctly
- [x] Edge cases produce appropriate warnings (dynamic values, spreads)

**Implementation Note**: After completing this phase, pause for manual confirmation. Create commit after verification passes.

---

## Phase 2: CLI Command — `business-use scan`

### Overview
Add the `scan` command to the CLI with `--dry-run`, `--format`, `--validate`, and `--flow` flags. No backend connection yet — this phase is purely local.

### Changes Required:

#### 1. Add `scan` command to CLI
**File**: `core/src/cli.py`
**Changes**: Add a new top-level `@cli.command()` named `scan` with these options:

```python
@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Scan and print results without pushing to backend")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="json", help="Output format for dry-run")
@click.option("--validate", is_flag=True, help="Run graph validation checks")
@click.option("--flow", "flow_filter", help="Filter results to a specific flow")
@click.option("--url", envvar="BUSINESS_USE_URL", help="Backend API URL")
@click.option("--api-key", envvar="BUSINESS_USE_API_KEY", help="Backend API key")
def scan(path, dry_run, output_format, validate, flow_filter, url, api_key):
```

**Behavior**:
- If `--dry-run`: scan and print results (JSON or table), exit. No `--url`/`--api-key` needed.
- If `--validate`: run graph validation, print warnings, exit with code 0 (warnings are informational, not errors). Can combine with `--dry-run`.
- If neither `--dry-run` nor `--validate`: require `--url` and `--api-key` (or env vars), scan, then push to API (Phase 4 will implement the push).
- If `--flow`: filter results to only include the specified flow.
- `--format` only applies to `--dry-run` output. Ignored when pushing to API (API push always prints a summary line).

#### 2. Table output formatter
**File**: `core/src/scanner/formatters.py` (new)
**Changes**: Implement `format_table(result: ScanResult) -> str` that renders a human-readable table:

```
Flow: checkout (3 nodes)
┌──────────────────────┬────────┬─────────────────┬──────────────────────────┐
│ ID                   │ Type   │ Dep IDs         │ Source                   │
├──────────────────────┼────────┼─────────────────┼──────────────────────────┤
│ cart_created         │ act    │ —               │ src/cart/service.ts:42   │
│ payment_processed    │ assert │ cart_created     │ src/payment/handler.ts:1 │
│ order_total_matches  │ assert │ cart_created     │ src/cart/service.ts:58   │
└──────────────────────┴────────┴─────────────────┴──────────────────────────┘

Warnings (2):
  ⚠ src/utils/helper.ts:22 - ensure() call with non-literal 'id' argument, skipped
  ⚠ src/edge-cases.ts:15 - depIds contains variable 'extraDep'
```

Also implement `format_json(result: ScanResult) -> str` — serialize ScanResult to JSON.

#### 3. Create formatter tests
**File**: `core/tests/scanner/test_formatters.py` (new)
**Changes**: Test JSON and table output formatting:
- JSON output matches expected schema (version, scanned_at, files_scanned, flows, warnings)
- Table output contains expected columns and node data
- Empty result formatting (no flows found)
- Flow filter applied before formatting

### Success Criteria:

#### Automated Verification:
- [x] Help text works: `cd core && uv run business-use scan --help`
- [x] Dry-run JSON output: `cd core && uv run business-use scan e2e-tests/js --dry-run`
- [x] Dry-run table output: `cd core && uv run business-use scan e2e-tests/js --dry-run --format table`
- [x] Validate mode: `cd core && uv run business-use scan e2e-tests/js --validate`
- [x] Flow filter: `cd core && uv run business-use scan e2e-tests/js --dry-run --flow checkout`
- [x] Linting passes: `cd core && uv run ruff check src/scanner/ src/cli.py`
- [x] Type checking passes: `cd core && uv run mypy src/scanner/`

#### Manual Verification:
- [x] JSON output matches the spec format from the research doc (version, scanned_at, files_scanned, flows, warnings)
- [x] Table output is readable and properly aligned
- [x] `--flow` filter correctly includes only matching flow nodes
- [x] `--validate` prints warnings for broken dep_ids references
- [x] Running without `--dry-run` or `--url` shows a clear error message asking for either `--dry-run` or `--url`
- [x] Environment variables `BUSINESS_USE_URL` and `BUSINESS_USE_API_KEY` are picked up correctly

**Implementation Note**: After completing this phase, pause for manual confirmation. Create commit after verification passes.

### QA Spec (optional):

**Approach:** cli-verification
**Test Scenarios:**
- [x] TC-1: Dry-run scan of fixture directory
  - Steps: `cd core && uv run business-use scan e2e-tests/js --dry-run`
  - Expected: JSON output with 7 files producing nodes, 2 skipped (no-business-use.ts, require-pattern.js), correct node counts per flow
- [x] TC-2: Validate catches broken references
  - Steps: Create a temp fixture with `depIds: ["nonexistent"]`, run `--validate`
  - Expected: Warning about unresolved dep_id reference

---

## Phase 3: Backend Batch Upsert API Endpoint

### Overview
Create `POST /v1/nodes/scan` — a batch endpoint that accepts the scanner's output format and upserts nodes with `source="scan"`. This is distinct from the existing `POST /v1/nodes` which is for manual creation.

### Changes Required:

#### 1. Add scanner-specific API schema
**File**: `core/src/api/models.py`
**Changes**: Add new Pydantic models:

```python
class ScannedNode(BaseModel):
    """A node extracted by the scanner."""
    id: str
    flow: str
    type: Literal["act", "assert"]
    dep_ids: list[str] = []
    description: str | None = None
    conditions: list[NodeCondition] = []
    has_filter: bool = False
    has_validator: bool = False
    source_file: str | None = None
    source_line: int | None = None
    source_column: int | None = None

class ScanUploadPayload(BaseModel):
    """Payload from the scanner CLI."""
    version: str = "1.0"
    scanned_at: str
    files_scanned: int
    flows: dict[str, list[ScannedNode]]
```

#### 2. Add batch upsert endpoint
**File**: `core/src/api/api.py`
**Changes**: Add `POST /v1/nodes/scan` endpoint:

- Accepts `ScanUploadPayload`
- For each node in each flow:
  - Check if node exists (by `id`)
  - If exists: update fields, set `source="scan"`, set `updated_at=now()`, clear `deleted_at`
  - If not: create with `source="scan"`, `created_at=now()`
- Soft-delete nodes that were previously `source="scan"` in the same flow but are no longer present in the payload (stale node cleanup — required to prevent ghost nodes from deleted SDK calls)
- Return summary: `{ created: N, updated: N, deleted: N, flows: [...] }`

#### 3. Add tests for the endpoint
**File**: `core/tests/api/test_scan_endpoint.py` (new)
**Changes**: Test the batch upsert endpoint:
- Create nodes → verify created
- Update nodes (re-scan with changed properties) → verify updated
- Stale node cleanup (node in DB but not in scan payload) → verify soft-deleted
- Auth required (no API key → 401)

### Success Criteria:

#### Automated Verification:
- [x] API tests pass: `cd core && uv run pytest tests/api/test_scan_endpoint.py -v`
- [x] Existing API tests still pass: `cd core && uv run pytest tests/ -v`
- [x] Linting passes: `cd core && uv run ruff check src/api/`
- [x] Type checking passes: `cd core && uv run mypy src/api/`

#### Manual Verification:
- [ ] Start server: `cd core && uv run business-use server dev`
- [ ] POST scan payload via curl:
  ```bash
  curl -X POST http://localhost:13370/v1/nodes/scan \
    -H "X-Api-Key: <key>" \
    -H "Content-Type: application/json" \
    -d '{"version":"1.0","scanned_at":"2026-03-25T10:00:00Z","files_scanned":1,"flows":{"checkout":[{"id":"cart_created","flow":"checkout","type":"act","dep_ids":[]}]}}'
  ```
- [ ] Verify node appears in `GET /v1/nodes` with `source="scan"`
- [ ] Re-POST same payload with changed description → verify node updated
- [ ] Verify existing manual/code nodes are NOT affected by scan upsert

**Implementation Note**: After completing this phase, pause for manual confirmation. Create commit after verification passes.

---

## Phase 4: Wire Scanner CLI to API

### Overview
Connect the `scan` command to the backend API so that `business-use scan ./src --url ... --api-key ...` pushes extracted nodes to the backend.

### Changes Required:

#### 1. Add API client for scanner
**File**: `core/src/scanner/api_client.py` (new)
**Changes**: Implement `push_scan_result(result: ScanResult, url: str, api_key: str) -> dict`:
- Serialize `ScanResult` to `ScanUploadPayload` JSON
- POST to `{url}/v1/nodes/scan` with `X-Api-Key` header
- Handle errors: connection refused, auth failure (401), server error (5xx)
- Return the API response summary (created/updated/deleted counts)
- Use `httpx` (already a dependency)

#### 2. Wire CLI to API client
**File**: `core/src/cli.py` (the `scan` command from Phase 2)
**Changes**: When not `--dry-run` and not `--validate`:
- Require `--url` (or `BUSINESS_USE_URL` env var) — exit with error if missing
- Require `--api-key` (or `BUSINESS_USE_API_KEY` env var) — exit with error if missing
- Call `push_scan_result()`
- Print summary: "Pushed N nodes across M flows (created: X, updated: Y)"
- Exit with code 0 on success, 1 on API error

#### 3. Add API client tests
**File**: `core/tests/scanner/test_api_client.py` (new)
**Changes**: Test the API client with mocked httpx responses:
- Success case
- Auth failure (401)
- Connection error
- Server error (5xx)

### Success Criteria:

#### Automated Verification:
- [x] API client tests pass: `cd core && uv run pytest tests/scanner/test_api_client.py -v`
- [x] All scanner tests still pass: `cd core && uv run pytest tests/scanner/ -v`
- [x] Linting passes: `cd core && uv run ruff check src/scanner/`
- [x] Type checking passes: `cd core && uv run mypy src/scanner/`

#### Manual Verification:
- [ ] Start backend: `cd core && uv run business-use server dev`
- [ ] Run scanner against fixtures: `cd core && uv run business-use scan e2e-tests/js --url http://localhost:13370 --api-key <key>`
- [ ] Verify output shows "Pushed N nodes across M flows"
- [ ] Verify nodes appear in backend: `curl http://localhost:13370/v1/nodes -H "X-Api-Key: <key>"`
- [ ] Run again → verify "updated" count (idempotent upsert)
- [ ] Test with wrong API key → verify clear error message
- [ ] Test with wrong URL → verify clear connection error message
- [ ] Test with env vars: `BUSINESS_USE_URL=... BUSINESS_USE_API_KEY=... business-use scan e2e-tests/js`

**Implementation Note**: After completing this phase, pause for manual confirmation. Create commit after verification passes.

### QA Spec (optional):

**Approach:** cli-verification
**Test Scenarios:**
- [ ] TC-1: Full end-to-end scan and push
  - Steps: Start server, run `business-use scan e2e-tests/js --url http://localhost:13370 --api-key <key>`
  - Expected: Nodes created in backend, summary printed
- [ ] TC-2: Idempotent re-scan
  - Steps: Run same scan command twice
  - Expected: First run creates, second run updates (no duplicates)
- [ ] TC-3: CI/CD simulation
  - Steps: `uvx business-use-core scan e2e-tests/js --url http://localhost:13370 --api-key <key>`
  - Expected: Works via uvx without local install

---

## Testing Strategy

### Unit Tests (`core/tests/scanner/`)
- **`test_imports.py`**: Import detection for each import pattern (named, aliased, namespace, non-target)
- **`test_extractor.py`**: Node extraction against each of the 9 JS/TS fixture files, asserting exact outputs
- **`test_validator.py`**: Graph validation (broken refs, duplicates, unreachable nodes)
- **`test_api_client.py`**: API client with mocked HTTP responses
- **`test_formatters.py`**: JSON and table output formatting

### Integration Tests
- **`test_scan_endpoint.py`**: API endpoint with real DB (using test database)

### Manual E2E Verification
```bash
# 1. Start backend
cd core && uv run business-use server dev --reload

# 2. Dry-run scan
uv run business-use scan e2e-tests/js --dry-run
uv run business-use scan e2e-tests/js --dry-run --format table
uv run business-use scan e2e-tests/js --dry-run --flow checkout

# 3. Validate
uv run business-use scan e2e-tests/js --validate

# 4. Push to backend
uv run business-use scan e2e-tests/js --url http://localhost:13370 --api-key <key>

# 5. Verify nodes in backend
curl http://localhost:13370/v1/nodes -H "X-Api-Key: <key>" | python -m json.tool

# 6. Re-scan (idempotent)
uv run business-use scan e2e-tests/js --url http://localhost:13370 --api-key <key>

# 7. CI/CD style (via uvx)
uvx business-use-core scan e2e-tests/js --dry-run
```

## References
- Research: `thoughts/taras/research/2026-03-25-static-analysis-sdk-extraction.md`
- POC scanner: `core/e2e-tests/poc_scanner.py`
- E2E fixtures: `core/e2e-tests/js/` (9 files), `core/e2e-tests/py/` (4 files)
- Node model: `core/src/models.py:154-228`
- Nodes sync command: `core/src/cli.py:1299-1427`
- API schemas: `core/src/api/models.py`

---

## Review Errata

_Reviewed: 2026-03-25 by Claude_

### Critical
- [x] `NodeSource` type (`core/src/models.py:68-71`) only allows `"code"` | `"manual"` — must add `"scan"` before using it as a source value — **fixed: added Phase 1b**

### Important
- [x] `TARGET_MODULES` in POC (`poc_scanner.py:19`) missing `@desplega.ai/business-use` scoped package name — real user imports would be missed — **fixed: added Phase 1c**
- [x] Stale node cleanup was marked as "optional" in Phase 3 — required to prevent ghost nodes — **fixed: made required**
- [x] tree-sitter deps as runtime dependencies adds ~4MB for all users — **fixed: moved to optional `[scan]` extra with runtime check**

### Resolved (Minor)
- [x] Phase 1 manual verification used `python -c` instead of `uv run python -c` — auto-fixed
- [x] `test_formatters.py` listed in Testing Strategy but missing from Phase 2 changes — auto-fixed: added as Phase 2 step 3
- [x] `--format` behavior without `--dry-run` was undefined — auto-fixed: documented as ignored when pushing to API
