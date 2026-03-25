---
date: 2026-03-25
planner: Claude
repository: business-use
topic: "Composable notifications system for flow evaluation outcomes"
tags: [plan, notifications, slack, sentry, adapters, eval-pipeline]
status: completed
autonomy: autopilot
research: thoughts/taras/research/2026-03-25-notifications-system.md
---

# Notifications System Implementation Plan

## Overview

Implement a composable notifications system in the Business-Use core API that sends alerts based on flow evaluation outcomes. Starting with two notifiers: **Slack** (incoming webhooks) and **Sentry** (`capture_message`). The system is opt-in, no-op if not configured, and follows the existing hexagonal architecture patterns.

## Current State Analysis

- `eval_flow_run()` at `eval/eval.py:63-149` is a pure orchestration function with **zero side effects** — it reads from the DB, builds a graph, validates, and returns `BaseEvalOutput`.
- All result persistence happens at the **call sites** (2 API endpoints + 1 event handler + 1 CLI + 1 ensure runner).
- Config uses module-level constants via `get_env_or_config()` at `config.py:73-89` with env var > YAML > default priority.
- `AppState` TypedDict at `api/api.py:51-52` currently holds only `bus: EventBus`, wired through FastAPI lifespan at `api/api.py:533-539`.
- `httpx` is already a dependency (`pyproject.toml:38`), used async in `triggers/executor.py:64-81`.
- The only Protocol in the codebase is `ExprEvaluator` at `domain/evaluation.py:19-38`.
- No existing notification, alerting, or webhook system exists.

### Key Discoveries:
- `EvalStatus` is `Literal["pending", "running", "passed", "failed", "skipped", "error", "cancelled", "timed_out", "flaky"]` at `models.py:17-27`
- The reeval endpoint at `api/api.py:250-335` compares old vs new status — but currently only queries `running` status evals, so it needs expansion to also query `failed` evals for detecting `failed → passed` transitions
- `sentry-sdk` is not currently a dependency; the `[scan]` optional extra pattern at `pyproject.toml:51-56` provides the template for `[notifications]`

## Desired End State

1. A `notifications/` adapter module under `core/src/` with `Notifier` Protocol, `NotificationDispatcher`, `SlackNotifier`, and `SentryNotifier`.
2. Config constants `SLACK_WEBHOOK_URL`, `SENTRY_DSN`, `NOTIFY_THROTTLE_SECONDS` following the existing `get_env_or_config()` pattern.
3. Dispatcher initialized as a module-level singleton in lifespan and called from 3 call sites (2 API endpoints + 1 event handler) via `get_dispatcher()` after eval result persistence.
4. Notifications fire on: (a) `"failed"` status from any eval path, (b) `"failed" → "passed"` transition from the reeval endpoint (requires expanding reeval query to include `failed` status evals).
5. `sentry-sdk` as an optional extra (`pip install business-use-core[notifications]`).
6. Full test coverage for dispatcher, notifiers, and wiring.

### Verification:
- `cd core && uv run ruff check src/ && uv run ruff format --check src/ && uv run mypy src/` passes
- `cd core && uv run pytest` passes
- `bun run e2e/run.ts` passes (no regressions)
- Slack notification received when a flow evaluation fails (manual with real webhook)
- Sentry event captured when a flow evaluation fails (manual with real DSN)

## Quick Verification Reference

Common commands:
- `cd core && uv run ruff check src/ --fix` — lint
- `cd core && uv run ruff format src/` — format
- `cd core && uv run mypy src/` — type check
- `cd core && uv run pytest` — unit tests
- `bun run e2e/run.ts` — E2E tests

Key files to check:
- `core/src/notifications/` — new module (all files)
- `core/src/config.py` — new constants
- `core/src/api/api.py` — AppState, lifespan, dispatch calls
- `core/src/events/handlers.py` — dispatch call in batch handler
- `core/pyproject.toml` — `[notifications]` extra
- `core/tests/notifications/` — new tests

## What We're NOT Doing

- Per-flow notification configuration (deferred to future version)
- Multiple Slack channels (single webhook URL for v1)
- Mermaid → image rendering for Slack (ASCII graph + UI deep link instead)
- Notifications for `"running"` or `"passed"` status (only `"failed"` and `"failed" → "passed"` transitions)
- Notifications for `"error"`, `"timed_out"`, or `"cancelled"` statuses — these exist in `EvalStatus` but `eval_flow_run()` only produces `"passed"`, `"failed"`, or `"running"` as overall flow status; the other values are per-node only
- Modifying `eval_flow_run()` itself (keep it pure; dispatch at call sites)
- Sentry SDK initialization in the notifications module (init happens at app startup)
- Threading/reply support in Slack (incoming webhooks can't thread)

## Implementation Approach

**Keep `eval_flow_run()` pure.** Rather than adding a side effect inside the function (research Point A), we dispatch notifications at the 3 call sites (2 API endpoints + 1 event handler) **after** result persistence. This is Point B from the research. Rationale:

1. The function stays pure and testable with zero side effects.
2. Notifications only fire after data is committed to the DB.
3. The reeval endpoint uniquely needs transition detection (`old_status != new_status`), which only exists at that call site.
4. CLI and ensure runner don't need notifications (they're developer-facing tools).

The dispatcher lives in `AppState` alongside the bus, following the same wiring pattern.

---

## Phase 1: Config Constants + Notifier Protocol + Dispatcher

### Overview
Create the notifications module skeleton: `Notifier` Protocol, `NotificationDispatcher` with throttling, and the config constants. No concrete notifiers yet — just the infrastructure.

### Changes Required:

#### 1. Notification Config Constants
**File**: `core/src/config.py`
**Changes**: Add 3 new constants after the existing `DEBUG` constant (around line 110), following the `get_env_or_config()` pattern:

```python
# --- Notification settings ---
SLACK_WEBHOOK_URL: Final[str | None] = get_env_or_config(
    "BUSINESS_USE_SLACK_WEBHOOK_URL", "slack_webhook_url"
)
SENTRY_DSN: Final[str | None] = get_env_or_config(
    "SENTRY_DSN", "sentry_dsn"
)
NOTIFY_THROTTLE_SECONDS: Final[int] = int(
    get_env_or_config(
        "BUSINESS_USE_NOTIFY_THROTTLE_SECONDS", "notify_throttle_seconds", "0"
    )
)
```

Note: `SENTRY_DSN` uses the standard env var name (no `BUSINESS_USE_` prefix) because `sentry_sdk.init()` auto-reads it by convention.

#### 2. Notifier Protocol
**File**: `core/src/notifications/protocol.py` (new)
**Changes**: Define the `Notifier` Protocol following the `ExprEvaluator` pattern at `domain/evaluation.py:19-38`:

```python
from typing import Protocol
from src.models import BaseEvalOutput

class Notifier(Protocol):
    async def notify(
        self,
        flow: str,
        run_id: str,
        result: BaseEvalOutput,
        transition: str | None = None,
    ) -> None:
        """Send a notification about a flow evaluation result.

        Must never raise — log and move on.
        """
        ...
```

#### 3. NotificationDispatcher
**File**: `core/src/notifications/dispatcher.py` (new)
**Changes**: Dispatcher that routes to all registered notifiers with optional throttling:

- `register(notifier)` — adds a notifier
- `dispatch(flow, run_id, result, transition)` — iterates notifiers, catches exceptions per-notifier
- Throttle: in-memory `dict[tuple[str, str], float]` mapping `(flow, status)` → `last_notified_ts`. Skip if `now - last < throttle_seconds`.
- Constructor takes `throttle_seconds: int = 0` (0 = disabled).

#### 4. Module Init with Factory
**File**: `core/src/notifications/__init__.py` (new)
**Changes**: `build_dispatcher()` factory that reads config and registers configured notifiers. For this phase, it only creates the empty dispatcher (no notifiers registered yet):

```python
from src.config import NOTIFY_THROTTLE_SECONDS
from src.notifications.dispatcher import NotificationDispatcher

def build_dispatcher() -> NotificationDispatcher:
    dispatcher = NotificationDispatcher(throttle_seconds=NOTIFY_THROTTLE_SECONDS)
    # Notifiers registered in subsequent phases
    return dispatcher
```

### Success Criteria:

#### Automated Verification:
- [x] New files exist: `ls core/src/notifications/{__init__,protocol,dispatcher}.py`
- [x] Lint passes: `cd core && uv run ruff check src/notifications/`
- [x] Format passes: `cd core && uv run ruff format --check src/notifications/`
- [x] Type check passes: `cd core && uv run mypy src/notifications/`
- [x] Config constants accessible: `cd core && uv run python -c "from src.config import SLACK_WEBHOOK_URL, SENTRY_DSN, NOTIFY_THROTTLE_SECONDS; print('OK')" `
- [x] Dispatcher instantiates: `cd core && uv run python -c "from src.notifications import build_dispatcher; d = build_dispatcher(); print(f'Notifiers: {len(d.notifiers)}')" `

#### Manual Verification:
- [ ] Review `config.py` — new constants follow the same style as existing ones
- [ ] Review `protocol.py` — Protocol is clean, matches `ExprEvaluator` style
- [ ] Review `dispatcher.py` — throttle logic is correct, exception handling wraps each notifier individually

**Implementation Note**: Pause after this phase for verification before proceeding.

---

## Phase 2: Slack Notifier

### Overview
Implement the `SlackNotifier` that sends Block Kit messages via incoming webhooks. Includes an ASCII graph renderer for inline flow visualization and a deep link to the UI.

### Changes Required:

#### 1. SlackNotifier Class
**File**: `core/src/notifications/slack.py` (new)
**Changes**:

- `SlackNotifier` class with `__init__(self, webhook_url: str)`.
- `async def notify(...)` — builds Block Kit payload, POSTs via `httpx.AsyncClient` with 10s timeout.
- Color mapping: `"failed"` → `"danger"`, resolved (`transition` is set) → `"good"`.
- Payload structure: `attachments[0].blocks` with colored sidebar per Slack convention.
- Blocks: header (emoji + status), section fields (flow, run_id, status, duration), ASCII graph code block, context with deep link.
- `_build_ascii_graph(result: BaseEvalOutput) -> str` — constructs a text-based DAG from `result.graph` and `result.exec_info` with status emoji per node (`✅`/`❌`/`⏸️`).
- All errors caught and logged — never propagates exceptions.
- Uses short-lived `httpx.AsyncClient()` context manager (consistent with `triggers/executor.py:64-81` pattern).

#### 2. Register in Factory
**File**: `core/src/notifications/__init__.py`
**Changes**: Update `build_dispatcher()` to register `SlackNotifier` when `SLACK_WEBHOOK_URL` is configured:

```python
from src.config import SLACK_WEBHOOK_URL, NOTIFY_THROTTLE_SECONDS

def build_dispatcher() -> NotificationDispatcher:
    dispatcher = NotificationDispatcher(throttle_seconds=NOTIFY_THROTTLE_SECONDS)
    if SLACK_WEBHOOK_URL:
        from src.notifications.slack import SlackNotifier
        dispatcher.register(SlackNotifier(SLACK_WEBHOOK_URL))
    return dispatcher
```

#### 3. Test Directory Init
**File**: `core/tests/notifications/__init__.py` (new, empty)

#### 4. Unit Tests
**File**: `core/tests/notifications/test_slack.py` (new)
**Changes**:
- Test payload construction for failed flow
- Test payload construction for resolved (failed → passed) transition
- Test ASCII graph rendering with multi-node flow
- Test error handling (webhook returns 500 — should log, not raise)
- Test rate limiting (429 response — should log, not raise)
- Mock `httpx.AsyncClient.post` to avoid real HTTP calls

### Success Criteria:

#### Automated Verification:
- [x] File exists: `ls core/src/notifications/slack.py`
- [x] Lint passes: `cd core && uv run ruff check src/notifications/ tests/notifications/`
- [x] Type check passes: `cd core && uv run mypy src/notifications/`
- [x] Tests pass: `cd core && uv run pytest tests/notifications/test_slack.py -v`

#### Manual Verification:
- [ ] Review Block Kit payload — correct Slack format (header, section fields, code block, context)
- [ ] Review ASCII graph — readable for a 3-4 node flow with mixed statuses
- [ ] Review error handling — no exception can escape `notify()`

**Implementation Note**: Pause after this phase for verification before proceeding.

---

## Phase 3: Sentry Notifier

### Overview
Implement the `SentryNotifier` that sends `capture_message` events with structured tags and context. Guard the `sentry-sdk` import so the notifier gracefully skips if the package isn't installed.

### Changes Required:

#### 1. SentryNotifier Class
**File**: `core/src/notifications/sentry.py` (new)
**Changes**:

- Guard import: `try: import sentry_sdk; HAS_SENTRY = True except ImportError: HAS_SENTRY = False`
- `SentryNotifier` class — no constructor args (Sentry SDK reads DSN from env or prior `init()` call).
- `async def notify(...)`:
  - If `not HAS_SENTRY`: log warning once, return.
  - `sentry_sdk.set_tag("flow", flow)`, `set_tag("run_id", run_id)`, `set_tag("eval_status", result.status)`.
  - `sentry_sdk.set_context("eval_result", {...})` with flow, run_id, status, elapsed_ms, failed_nodes.
  - `sentry_sdk.capture_message(...)` with level `"error"` for failed, `"info"` for resolved.
  - `fingerprint=["flow-eval", flow, result.status]` for issue grouping.
- All errors caught and logged — never propagates.

#### 2. Sentry SDK Initialization
**File**: `core/src/api/api.py`
**Changes**: Add optional Sentry SDK init in the FastAPI lifespan (before yield), guarded by config:

```python
from src.config import SENTRY_DSN
if SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=SENTRY_DSN)
    except ImportError:
        log.warning("SENTRY_DSN configured but sentry-sdk not installed")
```

This runs once at app startup. If `sentry-sdk` isn't installed or DSN is None, it's a no-op.

#### 3. Optional Dependency Extra
**File**: `core/pyproject.toml`
**Changes**: Add `notifications` extra to `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
scan = [
    "tree-sitter>=0.25.0",
    "tree-sitter-javascript>=0.25.0",
    "tree-sitter-typescript>=0.23.0",
]
notifications = [
    "sentry-sdk>=2.0.0",
]
```

#### 4. Register in Factory
**File**: `core/src/notifications/__init__.py`
**Changes**: Update `build_dispatcher()` to register `SentryNotifier` when `SENTRY_DSN` is configured:

```python
if SENTRY_DSN:
    from src.notifications.sentry import SentryNotifier
    dispatcher.register(SentryNotifier())
```

#### 5. Unit Tests
**File**: `core/tests/notifications/test_sentry.py` (new)
**Changes**:
- Test capture_message called with correct level and fingerprint
- Test tags and context set correctly
- Test graceful skip when sentry-sdk not installed (mock ImportError)
- Test error handling (capture_message raises — should log, not raise)
- Mock `sentry_sdk` module

### Success Criteria:

#### Automated Verification:
- [x] File exists: `ls core/src/notifications/sentry.py`
- [x] Lint passes: `cd core && uv run ruff check src/notifications/ tests/notifications/`
- [x] Type check passes: `cd core && uv run mypy src/notifications/`
- [x] Tests pass: `cd core && uv run pytest tests/notifications/ -v`
- [x] Optional dep defined: `cd core && grep -A2 'notifications' pyproject.toml`

#### Manual Verification:
- [ ] Review sentry.py — import guard is correct, capture_message has proper fingerprint
- [ ] Review api.py lifespan — Sentry init is guarded and won't crash if package missing
- [ ] Verify `uv sync` still works without the `[notifications]` extra (sentry-sdk not required)

**Implementation Note**: Pause after this phase for verification before proceeding.

---

## Phase 4: Wire Dispatcher into Eval Pipeline

### Overview
Initialize the `NotificationDispatcher` singleton at app startup and call `dispatch()` from the 3 call sites (2 API endpoints + 1 event handler) after eval result persistence. The dispatcher is accessed via `get_dispatcher()` singleton — not `AppState` — because the event handler lacks HTTP request context.

### Changes Required:

#### 1. Upgrade `build_dispatcher()` to Singleton Pattern
**File**: `core/src/notifications/__init__.py`
**Changes**: Extend the factory from Phase 1 to store a module-level singleton. All 3 call sites use `get_dispatcher()` — this is necessary because:
- The `/run-eval` endpoint doesn't accept a `request` parameter, so `request.state` is unavailable.
- The event handler (`handle_new_batch_event`) runs via the event bus, not an HTTP request context.

The singleton pattern is consistent with how `config.py` constants work — module-level, import directly:

```python
# notifications/__init__.py
_dispatcher: NotificationDispatcher | None = None

def build_dispatcher() -> NotificationDispatcher:
    global _dispatcher
    dispatcher = NotificationDispatcher(throttle_seconds=NOTIFY_THROTTLE_SECONDS)
    # ... register notifiers (already added in Phases 2-3) ...
    _dispatcher = dispatcher
    return dispatcher

def get_dispatcher() -> NotificationDispatcher:
    if _dispatcher is None:
        return NotificationDispatcher()  # empty no-op dispatcher
    return _dispatcher
```

#### 2. Initialize Dispatcher in Lifespan
**File**: `core/src/api/api.py`
**Changes**: Call `build_dispatcher()` in the lifespan to initialize the singleton (around line 533-539). `AppState` TypedDict remains unchanged — the dispatcher lives as a module-level singleton, not in app state:

```python
from src.notifications import build_dispatcher

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[AppState]:
    build_dispatcher()  # Initialize singleton — accessed via get_dispatcher()
    yield {
        "bus": new_bus(),
    }
    log.info("Ciaito!")
```

#### 3. Dispatch from POST `/v1/run-eval`
**File**: `core/src/api/api.py` (around line 245)
**Changes**: After persisting `EvalOutput` and before returning, dispatch on `"failed"`:

```python
from src.notifications import get_dispatcher

if result.status == "failed":
    dispatcher = get_dispatcher()
    await dispatcher.dispatch(flow=body.flow, run_id=body.run_id, result=result)
```

#### 4. Dispatch from `handle_new_batch_event`
**File**: `core/src/events/handlers.py` (around line 73)
**Changes**: After eval_flow_run() and persist, dispatch on failure:

```python
from src.notifications import get_dispatcher

# After eval_flow_run() and persist:
if eval_result.status == "failed":
    dispatcher = get_dispatcher()
    await dispatcher.dispatch(flow=flow, run_id=run_id, result=eval_result)
```

#### 5. Expand Reeval Query to Include `failed` Status
**File**: `core/src/api/api.py` (around line 278-284)
**Changes**: The current query only selects evals with `output["status"] == "running"`. To detect `failed → passed` transitions, expand the filter to also include `failed`:

```python
stmt = (
    select(EvalOutput)
    .where(
        EvalOutput.output["status"].astext.in_(["running", "failed"]),  # type: ignore
        EvalOutput.created_at >= cutoff_time,
    )
    .order_by(desc(EvalOutput.created_at))  # type: ignore
)
```

> **Why**: Without this change, `old_status` is always `"running"`, making the `failed → passed` transition detection dead code.

Also update the endpoint docstring to reflect the broader scope (e.g., "Re-evaluate flows in running or failed state").

#### 6. Dispatch from Reeval Endpoint
**File**: `core/src/api/api.py` (around line 305-318)
**Changes**: After updating the `EvalOutput` record, dispatch on status transitions. Note: `eval_output.output` is a `BaseEvalOutput` Pydantic model — use attribute access (`.status`), not dict access (`.get()`):

```python
old_status = eval_output.output.status  # Pydantic model attribute, not dict
# ... (existing eval_flow_run call and persist) ...

dispatcher = get_dispatcher()

if old_status == "failed" and new_result.status == "passed":
    await dispatcher.dispatch(
        flow=eval_output.flow,
        run_id=eval_output.run_id,
        result=new_result,
        transition="failed->passed",
    )
elif new_result.status == "failed" and old_status != "failed":
    await dispatcher.dispatch(
        flow=eval_output.flow,
        run_id=eval_output.run_id,
        result=new_result,
    )
```

This handles two cases:
- **Resolved**: previously failed flow now passes → send resolved notification
- **Newly failed**: status changed to failed (was running/pending) → send failure notification

### Success Criteria:

#### Automated Verification:
- [x] Lint passes: `cd core && uv run ruff check src/`
- [x] Format passes: `cd core && uv run ruff format --check src/`
- [x] Type check passes: `cd core && uv run mypy src/`
- [x] Existing tests pass: `cd core && uv run pytest`
- [x] E2E passes (no regressions): `bun run e2e/run.ts`

#### Manual Verification:
- [ ] Review lifespan — `build_dispatcher()` called to initialize singleton
- [ ] Review all 3 dispatch call sites — correct status checks, correct parameters, all use `get_dispatcher()`
- [ ] Review reeval query expansion — includes both `"running"` and `"failed"` status evals
- [ ] Verify that without `SLACK_WEBHOOK_URL` or `SENTRY_DSN` configured, the dispatcher is a no-op (empty notifiers list)

**Implementation Note**: This is the most critical phase — pause for thorough review before proceeding.

---

## Phase 5: Dispatcher and Integration Tests

### Overview
Add unit tests for the `NotificationDispatcher` (throttling, error isolation, routing) and integration tests verifying the wiring from eval call sites through to notification dispatch.

### Changes Required:

#### 1. Dispatcher Unit Tests
**File**: `core/tests/notifications/test_dispatcher.py` (new)
**Changes**:
- Test empty dispatcher (no notifiers) — `dispatch()` is no-op
- Test single notifier — `notify()` called with correct args
- Test multiple notifiers — all called, order preserved
- Test error isolation — one notifier raises, others still called
- Test throttle — same `(flow, status)` within window is skipped
- Test throttle — different `(flow, status)` not affected
- Test throttle disabled (0) — all notifications pass through
- Test transition parameter forwarded correctly

#### 2. Integration Tests
**File**: `core/tests/notifications/test_integration.py` (new)
**Changes**:
- Test `build_dispatcher()` with no config → empty dispatcher
- Test `build_dispatcher()` with `SLACK_WEBHOOK_URL` set → 1 notifier
- Test `build_dispatcher()` with both configured → 2 notifiers
- Test `get_dispatcher()` before `build_dispatcher()` → returns no-op
- Mock config values via `monkeypatch.setenv()`

### Success Criteria:

#### Automated Verification:
- [x] All notification tests pass: `cd core && uv run pytest tests/notifications/ -v`
- [x] Full test suite passes: `cd core && uv run pytest`
- [x] Lint passes: `cd core && uv run ruff check tests/notifications/`

#### Manual Verification:
- [ ] Review test coverage — all dispatcher branches covered (throttle on/off, error handling, empty list)
- [ ] Review integration tests — config mocking is clean, no side effects between tests

**Implementation Note**: Pause after this phase for verification before proceeding.

---

## Phase 6: Documentation and Config Example

### Overview
Update `config.yaml.example` with notification settings and add a brief section to the CLI help.

### Changes Required:

#### 1. Config Example
**File**: `core/config.yaml.example`
**Changes**: Add notification settings section:

```yaml
# --- Notification settings (optional) ---

# Slack incoming webhook URL for failure notifications
# slack_webhook_url: https://hooks.slack.com/services/T.../B.../xxx

# Sentry DSN for error tracking (requires: pip install business-use-core[notifications])
# sentry_dsn: https://xxx@o123.ingest.sentry.io/456

# Minimum seconds between notifications for the same (flow, status) pair (0 = disabled)
# notify_throttle_seconds: 60
```

#### 2. Update CLAUDE.md
**File**: `CLAUDE.md`
**Changes**: Add notification config fields to the Configuration section's environment variables list:

```
- `BUSINESS_USE_SLACK_WEBHOOK_URL` - Slack webhook URL for failure notifications
- `SENTRY_DSN` - Sentry DSN for error tracking (requires `[notifications]` extra)
- `BUSINESS_USE_NOTIFY_THROTTLE_SECONDS` - Throttle seconds between notifications (default: 0)
```

### Success Criteria:

#### Automated Verification:
- [x] Config example file updated: `grep -c 'slack_webhook_url' core/config.yaml.example`
- [x] CLAUDE.md updated: `grep -c 'SLACK_WEBHOOK_URL' CLAUDE.md`

#### Manual Verification:
- [ ] Review config.yaml.example — settings are commented out (opt-in pattern)
- [ ] Review CLAUDE.md — new env vars documented consistently with existing ones

**Implementation Note**: Pause after this phase for final review.

---

## Testing Strategy

### Unit Tests (Phase 2, 3, 5)
- `tests/notifications/test_dispatcher.py` — dispatcher routing, throttle, error isolation
- `tests/notifications/test_slack.py` — payload construction, ASCII graph, error handling
- `tests/notifications/test_sentry.py` — capture_message, tags, import guard
- `tests/notifications/test_integration.py` — factory wiring, config-driven registration

### Regression Tests
- Existing `tests/` suite must continue passing
- E2E suite (`bun run e2e/run.ts`) must continue passing

### Manual E2E (post-implementation)
1. Configure `BUSINESS_USE_SLACK_WEBHOOK_URL` with a real Slack incoming webhook
2. Start server: `cd core && uv run business-use serve --reload`
3. Send events that produce a failed flow evaluation (use SDK example or seed script)
4. Verify Slack notification received in the configured channel with correct Block Kit formatting
5. Trigger reeval that resolves the flow: `curl -X POST http://localhost:13370/v1/reeval-running-flows -H "X-Api-Key: <key>"`
6. Verify "resolved" Slack notification received
7. (Optional) Configure `SENTRY_DSN`, install `sentry-sdk`, repeat — verify events in Sentry dashboard

## References
- Research: `thoughts/taras/research/2026-03-25-notifications-system.md`
- Eval pipeline: `core/src/eval/eval.py:63-149`
- Config system: `core/src/config.py:73-89`
- AppState + lifespan: `core/src/api/api.py:51-52, 533-539`
- Event handler: `core/src/events/handlers.py:24-83`
- Reeval endpoint: `core/src/api/api.py:250-335`
- ExprEvaluator Protocol (pattern): `core/src/domain/evaluation.py:19-38`
- httpx async pattern: `core/src/triggers/executor.py:64-81`
