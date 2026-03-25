---
date: 2026-03-25T14:00:00-04:00
researcher: Claude
git_commit: b8d6f29a011b352057ee0d62f138e6ceec9da79a
branch: main
repository: business-use
topic: "Composable notifications system for the Business-Use API based on flow evaluation outcomes"
tags: [research, notifications, slack, sentry, adapters, config, eval-pipeline]
status: complete
autonomy: autopilot
last_updated: 2026-03-25
last_updated_by: Claude (errata review — 11 line-number corrections in api.py, types.py, sqlite.py references)
---

# Research: Notifications System for Business-Use API

**Date**: 2026-03-25
**Researcher**: Claude
**Git Commit**: b8d6f29
**Branch**: main

## Research Question

How to implement a composable notifications system in the Business-Use core API that sends alerts based on flow evaluation outcomes. Starting with Slack (incoming webhooks) and Sentry (capture_message). Must be opt-in, no-op if not configured, configurable via `config.yaml` or environment variables.

## Summary

The Business-Use eval pipeline has clear insertion points for notification hooks. The most natural point is inside `eval_flow_run()` (`eval/eval.py:142`) — the single function that all three evaluation entry paths converge through — right after validation completes and before the `BaseEvalOutput` is returned. The existing codebase already follows opt-in patterns (config value is `None` → feature disabled) and has a hexagonal architecture with pluggable adapters. A `notifications/` adapter layer with a `Protocol`-based `Notifier` interface fits cleanly into the existing patterns. Slack requires zero new dependencies (just `httpx` POST), and Sentry requires `sentry-sdk` as an optional dependency.

## Detailed Findings

### 1. Flow Evaluation Pipeline — Where Notifications Fit

The eval pipeline has three entry paths that all converge through `eval_flow_run()`:

| Entry Point | File | Trigger |
|---|---|---|
| `POST /v1/run-eval` | `api/api.py:210-247` | Manual/on-demand evaluation |
| `handle_new_batch_event()` | `events/handlers.py:24-83` | Automatic after event batch ingestion |
| `POST /v1/reeval-running-flows` | `api/api.py:250-335` | Cron-driven re-evaluation of running flows |

All three call `eval_flow_run()` at `eval/eval.py:63-149`, which returns a `BaseEvalOutput`.

#### Candidate Hook Points

**Point A — Inside `eval_flow_run()`, after validation, before return** (`eval/eval.py:142`)
- **Pros**: Single point covers all three entry paths. Has access to `run_id`, `flow`, and the full `BaseEvalOutput` (status, per-node items, elapsed time, graph).
- **Cons**: Adds a side effect to what is currently a pure orchestration function.
- **Recommendation**: Best insertion point for v1.

**Point B — After persistence in each entry point** (3 locations)
- `api/api.py:245` (after run-eval commit)
- `events/handlers.py:73` (after batch eval commit)
- `api/api.py:311-318` (after reeval status change detection)
- **Pros**: Notifications only fire after data is committed. Point B3 uniquely detects status *transitions* (`old_status != new_result.status`).
- **Cons**: Three separate locations to maintain.

**Point C — Via event bus** (new event type)
- Dispatch a `NewEvalResult` event from `eval_flow_run()`, register a handler that sends notifications.
- **Pros**: Fully decoupled. Follows existing `bubus` pattern (`events/handlers.py:15-21`).
- **Cons**: Adds indirection. Event bus is currently attached to FastAPI app state (`api/api.py:533-547`), so `eval_flow_run()` would need bus access.

### 2. Current Configuration System

**File**: `core/src/config.py` (158 lines)

The config system uses a single-file YAML loader with environment variable overrides:

```
Priority: env var > YAML config > default value
```

**YAML search order**: `./.business-use/config.yaml` → `./config.yaml` (legacy) → `~/.business-use/config.yaml` → empty dict.

**Override mechanism**: `get_env_or_config(env_key, config_key, default)` at `config.py:73-89` — checks `os.environ` first, then falls back to the YAML dict.

**Current fields** (all module-level constants):

| Constant | Env Var | Default | Line |
|---|---|---|---|
| `API_KEY` | `BUSINESS_USE_API_KEY` | `None` | 110 |
| `DATABASE_PATH` | `BUSINESS_USE_DATABASE_PATH` | computed | 137-139 |
| `DATABASE_URL` | `BUSINESS_USE_DATABASE_URL` | computed | 152-156 |
| `LOG_LEVEL` | `BUSINESS_USE_LOG_LEVEL` | `WARNING` | 103-105 |
| `DEBUG` | `BUSINESS_USE_DEBUG` | `False` | 107 |
| `ENV` | `BUSINESS_USE_ENV` | `"local"` | 106 |

**Access pattern**: Module-level constants imported directly by consumers (`from src.config import API_KEY`). No dependency injection, no config object.

**Existing opt-in pattern**: `API_KEY` defaults to `None`, and `ensure_api_key_or_exit()` (`cli.py:86-107`) guards commands that need it. Same pattern applies to `DATABASE_URL` (Postgres is opt-in; SQLite is the fallback).

#### Notification Config Fields to Add

Following the existing `get_env_or_config()` pattern:

| Constant | Env Var | YAML Key | Default |
|---|---|---|---|
| `SLACK_WEBHOOK_URL` | `BUSINESS_USE_SLACK_WEBHOOK_URL` | `slack_webhook_url` | `None` |
| `SENTRY_DSN` | `SENTRY_DSN` | `sentry_dsn` | `None` |
| `NOTIFY_THROTTLE_SECONDS` | `BUSINESS_USE_NOTIFY_THROTTLE_SECONDS` | `notify_throttle_seconds` | `0` (disabled) |

Note: Sentry uses the standard `SENTRY_DSN` env var (not prefixed) because `sentry_sdk.init()` auto-reads it by convention. The `NOTIFY_ON` field was removed — v1 always notifies on `"failed"` only (hardcoded), with resolved notifications (`failed → passed`) from the reeval endpoint.

### 3. Eval Output Data Available for Notifications

After `validate_flow_execution()` returns a `ValidationResult` TypedDict, `eval_flow_run()` converts it to a `BaseEvalOutput` Pydantic model:

**`BaseEvalOutput`** (`models.py:265-270`):

| Field | Type | Description |
|---|---|---|
| `status` | `EvalStatus` | Overall: `"passed"`, `"failed"`, or `"running"` |
| `elapsed_ns` | `int` | Total evaluation time in nanoseconds |
| `graph` | `dict[str, list[str]]` | Node dependency graph |
| `exec_info` | `list[BaseEvalItemOutput]` | Per-node results |
| `ev_ids` | `list[str]` | All event IDs involved |

**`BaseEvalItemOutput`** (`models.py:250-262`):

| Field | Type | Description |
|---|---|---|
| `node_id` | `str` | Node identifier |
| `dep_node_ids` | `list[str]` | Dependencies |
| `status` | `EvalStatus` | `"passed"`, `"failed"`, `"running"`, `"skipped"` |
| `message` | `str \| None` | Info/success message |
| `error` | `str \| None` | Error description |
| `elapsed_ns` | `int` | Per-node time |
| `ev_ids` | `list[str]` | Matched event IDs |
| `upstream_ev_ids` | `list[str]` | Upstream event IDs |

**`EvalStatus`** (`models.py:17-27`): `Literal["pending", "running", "passed", "failed", "skipped", "error", "cancelled", "timed_out", "flaky"]`

In practice, the overall flow status produced by `validate_flow_execution()` is one of exactly three values: `"passed"`, `"failed"`, or `"running"`.

### 4. Notifications Abstraction Proposal

The notification system needs a composable architecture where multiple notifiers can be registered and dispatched to. Following the existing `ExprEvaluator` Protocol and `MultiEvaluator` router patterns:

#### Notifier Protocol

```python
# notifications/protocol.py
from typing import Protocol

class Notifier(Protocol):
    async def notify(
        self,
        flow: str,
        run_id: str,
        result: BaseEvalOutput,
        transition: str | None = None,  # e.g., "failed->passed" for resolved
    ) -> None:
        """Send a notification about a flow evaluation result.

        Must never raise — log and move on.
        """
        ...
```

#### NotificationDispatcher (Router)

```python
# notifications/dispatcher.py
class NotificationDispatcher:
    """Routes notifications to all configured notifiers. No-op if none configured."""

    def __init__(self) -> None:
        self.notifiers: list[Notifier] = []

    def register(self, notifier: Notifier) -> None:
        self.notifiers.append(notifier)

    async def dispatch(
        self,
        flow: str,
        run_id: str,
        result: BaseEvalOutput,
        transition: str | None = None,
    ) -> None:
        for notifier in self.notifiers:
            try:
                await notifier.notify(flow, run_id, result, transition)
            except Exception:
                logger.exception(f"Notifier {type(notifier).__name__} failed")
```

#### Initialization (follows opt-in pattern)

```python
# notifications/__init__.py
def build_dispatcher() -> NotificationDispatcher:
    dispatcher = NotificationDispatcher()

    if SLACK_WEBHOOK_URL:
        dispatcher.register(SlackNotifier(SLACK_WEBHOOK_URL))

    if SENTRY_DSN:
        dispatcher.register(SentryNotifier())

    return dispatcher
```

The dispatcher is instantiated once (e.g., at module level or in FastAPI lifespan) and called from `eval_flow_run()`. If no notifiers are configured, `dispatch()` is a no-op (empty list iteration).

#### Throttle / Dedup Config

To avoid notification fatigue, the dispatcher should support throttling:

| Config | Env Var | YAML Key | Default | Description |
|---|---|---|---|---|
| `NOTIFY_THROTTLE_SECONDS` | `BUSINESS_USE_NOTIFY_THROTTLE_SECONDS` | `notify_throttle_seconds` | `0` (disabled) | Minimum seconds between notifications for the same `(flow, status)` pair |

Implementation: in-memory dict of `(flow, status) → last_notified_ts`. If `now - last_notified_ts < throttle_seconds`, skip. Simple, no external state needed.

### 5. Slack Integration — Incoming Webhooks

#### How It Works

Slack incoming webhooks are the simplest notification path: HTTP POST a JSON payload to a unique URL. No SDK, no OAuth, no bot tokens needed.

**Webhook URL format**: `https://hooks.slack.com/services/T.../B.../xxx`

#### Payload Structure

Supports Block Kit for rich layouts. Colored sidebars require wrapping blocks inside `attachments[].blocks` with a `color` field:

```json
{
  "text": "Flow ‘checkout’ evaluation: FAILED",
  "attachments": [
    {
      "color": "danger",
      "blocks": [
        {
          "type": "header",
          "text": { "type": "plain_text", "text": "❌ Flow Evaluation Failed", "emoji": true }
        },
        {
          "type": "section",
          "fields": [
            { "type": "mrkdwn", "text": "*Flow:*\n`checkout`" },
            { "type": "mrkdwn", "text": "*Run ID:*\n`run_abc123`" },
            { "type": "mrkdwn", "text": "*Status:*\n❌ Failed" },
            { "type": "mrkdwn", "text": "*Duration:*\n1.2s" }
          ]
        }
      ]
    }
  ]
}
```

#### Visual Flow Representation in Slack

Slack does **not** render Mermaid natively. Options for showing where a flow failed visually:

1. **ASCII graph in a code block** — Use mrkdwn ` ```triple backticks``` ` with a text-based DAG showing pass/fail per node. E.g.:
   ```
   cart_created ✅ → payment_processed ❌ → order_confirmed ⏸️
                  → shipping_label ✅
   ```
   Pros: No external dependencies. Cons: Limited layout for complex graphs.

2. **Mermaid → image via external service** — Render the graph to PNG using a service like `mermaid.ink` (`https://mermaid.ink/img/<base64>`), then include as a Slack `image` block. Pros: Actual visual diagram. Cons: External dependency, adds latency, privacy concern (graph data sent to third party).

3. **Self-hosted Mermaid rendering** — Run `@mermaid-js/mermaid-cli` (`mmdc`) as a subprocess to render locally, upload to Vercel Blob, include as image URL. Pros: No third party. Cons: Requires Node.js + Puppeteer on the server, heavy for a notification.

4. **Link to UI** — Include a deep link to the Business-Use UI flow visualization page. E.g., `View graph: http://localhost:5173/flows/checkout/runs/run_abc123`. Pros: Richest visualization, zero rendering overhead. Cons: Requires UI to be deployed and accessible.

**Recommendation for v1**: Option 1 (ASCII graph) for inline context + Option 4 (deep link to UI) for full visualization. The graph data is already available in `BaseEvalOutput.graph` and `exec_info` to construct both.

**Color values**: `"good"` (green), `"warning"` (yellow), `"danger"` (red), or any hex code.

#### Python Implementation

Zero new dependencies needed — `httpx` is already in the FastAPI stack. Async POST with 10s timeout, never raises.

**Rate limits**: 1 message/second/channel. HTTP 429 with `Retry-After` header on throttle.

**Error handling**: Always wrap in try/except, log and move on. Never let Slack outage block the eval pipeline.

#### Limitations

- Incoming webhooks are tied to a **single channel**. Multiple channels require multiple webhook URLs or switching to the `chat.postMessage` API with a bot token.
- Webhooks cannot read messages, thread replies, or react. For threading, the full Web API is needed.

### 6. Sentry Integration — `capture_message`

#### How It Works

`sentry-sdk` can capture custom messages (not just exceptions) with structured context. The SDK uses a background worker thread, so `capture_message()` is non-blocking — it returns an `event_id` immediately.

#### Opt-in Behavior

`sentry_sdk.init()` without a DSN (or with `dsn=None`) is a **no-op** — the SDK instruments the app but sends nothing. This makes it perfect for opt-in:

```python
import sentry_sdk

dsn = config.SENTRY_DSN  # None if not configured
if dsn:
    sentry_sdk.init(dsn=dsn)
# If dsn is None, all capture_* calls become no-ops
```

The SDK also auto-reads the `SENTRY_DSN` environment variable if no explicit `dsn` parameter is passed.

#### Sending Eval Results

```python
import sentry_sdk

sentry_sdk.set_tag("flow", flow)
sentry_sdk.set_tag("run_id", run_id)
sentry_sdk.set_tag("eval_status", result.status)

sentry_sdk.set_context("eval_result", {
    "flow": flow,
    "run_id": run_id,
    "status": result.status,
    "elapsed_ms": result.elapsed_ns / 1_000_000,
    "node_count": len(result.exec_info),
    "failed_nodes": [item.node_id for item in result.exec_info if item.status == "failed"],
})

sentry_sdk.capture_message(
    f"Flow '{flow}' evaluation: {result.status}",
    level="error" if result.status == "failed" else "info",
    fingerprint=["flow-eval", flow, result.status],
)
```

#### Key Sentry Concepts

- **`set_tag(key, value)`**: Indexed, searchable, filterable in Sentry UI. Use for flow name, run_id, status.
- **`set_context(name, dict)`**: Structured data attached to event. Use for detailed eval results.
- **`fingerprint`**: Controls issue grouping. `["flow-eval", flow, result.status]` groups all failures for the same flow into one Sentry issue.
- **`level`**: `"info"`, `"warning"`, `"error"`, `"fatal"`. Map `"failed"` → `"error"`, `"passed"` → `"info"`.
- **`before_send` callback**: Can filter/modify events before transmission. Useful for suppressing certain flows.
- **Non-blocking**: Background worker thread handles HTTP. `capture_message()` returns immediately.

#### Dependency

Requires `sentry-sdk` as an optional dependency. If not installed, the Sentry notifier should gracefully skip.

### 7. Existing Patterns to Follow

#### Adapter Pattern (`adapters/sqlite.py`)

Current adapters are stateless classes with no base class or Protocol inheritance:

```python
class SqliteEventStorage:
    async def get_events_by_run(self, run_id, flow, session) -> list[Event]: ...
    async def get_nodes_by_flow(self, flow, session) -> list[Node]: ...
```

#### Protocol Pattern (`domain/evaluation.py:19-38`)

The `ExprEvaluator` Protocol is the only Protocol in the codebase. It defines a pluggable interface that the `MultiEvaluator` satisfies via structural typing.

#### Event Bus Pattern (`events/handlers.py:15-21`)

```python
def new_bus():
    bus = EventBus()
    bus.on(NewBatchEvent, handle_new_batch_event)
    bus.on(NewEvent, handle_new_event)
    return bus
```

Bus is attached to FastAPI app state via lifespan at `api/api.py:533-547`.

#### Opt-in Guard Pattern

```python
# config.py
API_KEY: Final[str | None] = get_env_or_config("BUSINESS_USE_API_KEY", "api_key")

# cli.py
def ensure_api_key_or_exit() -> None:
    if not API_KEY:
        click.secho("API_KEY not configured!", fg="red", bold=True)
        raise click.Abort()
```

#### MultiEvaluator Router Pattern (`eval/eval.py:30-60`)

Routes to concrete implementations based on a discriminator field:

```python
class MultiEvaluator:
    def __init__(self):
        self.python_evaluator = PythonEvaluator()
        self.js_evaluator = JSEvaluator()

    def evaluate(self, expr, data, ctx):
        if expr.engine == "python":
            return self.python_evaluator.evaluate(expr, data, ctx)
        elif expr.engine == "js":
            return self.js_evaluator.evaluate(expr, data, ctx)
```

## Code References

| File | Lines | Description |
|---|---|---|
| `core/src/eval/eval.py` | 63-149 | `eval_flow_run()` — orchestration, best hook point at line 142 |
| `core/src/eval/eval.py` | 30-60 | `MultiEvaluator` — router pattern to follow |
| `core/src/domain/evaluation.py` | 141-451 | `validate_flow_execution()` — produces `ValidationResult` |
| `core/src/domain/evaluation.py` | 19-38 | `ExprEvaluator` Protocol — only Protocol in codebase |
| `core/src/domain/types.py` | 86-102 | `ValidationResult` TypedDict |
| `core/src/domain/types.py` | 62-83 | `ValidationItem` TypedDict |
| `core/src/models.py` | 265-270 | `BaseEvalOutput` Pydantic model |
| `core/src/models.py` | 250-262 | `BaseEvalItemOutput` Pydantic model |
| `core/src/models.py` | 17-27 | `EvalStatus` Literal type |
| `core/src/config.py` | 73-89 | `get_env_or_config()` — env override mechanism |
| `core/src/config.py` | 93-158 | Module-level config constants |
| `core/src/adapters/sqlite.py` | 13-106 | `SqliteEventStorage` — adapter class pattern |
| `core/src/api/api.py` | 210-247 | `POST /v1/run-eval` endpoint |
| `core/src/api/api.py` | 250-335 | `POST /v1/reeval-running-flows` endpoint |
| `core/src/api/api.py` | 533-547 | FastAPI lifespan with event bus |
| `core/src/events/handlers.py` | 15-21 | `new_bus()` — event bus setup |
| `core/src/events/handlers.py` | 24-83 | `handle_new_batch_event()` — auto-eval after ingestion |
| `core/src/cli.py` | 86-107 | `ensure_api_key_or_exit()` — opt-in guard pattern |
| `core/src/secrets_manager/secrets.py` | 51-90 | `load_secrets_from_workspace()` — graceful empty-dict pattern |

## Decisions (from review)

1. **Notify only on `”failed”` status.** No notifications for `”running”` or `”passed”` in the normal eval path. Keep it simple — only failures are actionable.

2. **Reeval transitions: notify only on `failed → passed` (resolved).** The reeval cron endpoint should send a “resolved” notification when a previously-failed flow transitions to passed. This is the only meaningful transition. Additionally, throttling must be configurable to avoid noise (see `NOTIFY_THROTTLE_SECONDS` in section 4).

3. **v1 is global config, single channel.** One Slack webhook URL, one Sentry DSN, applied to all flows. Per-flow overrides deferred to a future version.

4. **One Slack channel for v1.** Single webhook URL. Multiple channels can be added later by expanding to a list/map in config.

5. **`sentry-sdk` as optional extra: `pip install business-use-core[notifications]`.** This keeps the base install lightweight. Guard Sentry imports with `try/except ImportError`. The `[notifications]` extra pulls in `sentry-sdk`. Slack needs no extra deps (uses `httpx` already present).
