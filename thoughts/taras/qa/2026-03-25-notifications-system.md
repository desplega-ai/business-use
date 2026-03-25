---
date: 2026-03-25
plan: thoughts/taras/plans/2026-03-25-notifications-system.md
topic: "Notifications system QA validation"
result: PASS
---

# QA Report: Notifications System

## Summary

The notifications system implementation across 6 phases has been validated. All automated checks pass, all plan specifications match the implementation, and real Slack webhook delivery confirmed.

**Verdict: PASS**

## Automated Checks

| Check | Result |
|-------|--------|
| `ruff check src/notifications/ tests/notifications/` | All checks passed |
| `ruff format --check src/notifications/ tests/notifications/` | 10 files already formatted |
| `mypy src/notifications/` | Success: no issues found in 5 source files |
| `pytest tests/notifications/ -v` | 44/44 passed (0.38s) |
| `pytest` (full suite) | 235/235 passed (0.61s) |
| `bun run e2e/run.ts` | All E2E tests passed (4/4 evals correct) |

## Code Review: Plan vs Implementation

All 6 phases verified against plan specifications:

| Requirement | File | Status |
|-------------|------|--------|
| Config constants (SLACK_WEBHOOK_URL, SENTRY_DSN, NOTIFY_THROTTLE_SECONDS) | `config.py:160-168` | MATCH |
| Notifier Protocol (matches ExprEvaluator pattern) | `notifications/protocol.py` | MATCH |
| NotificationDispatcher (throttle, error isolation, routing) | `notifications/dispatcher.py` | MATCH |
| Singleton factory (build_dispatcher/get_dispatcher) | `notifications/__init__.py` | MATCH |
| SlackNotifier (Block Kit, ASCII graph, httpx) | `notifications/slack.py` | MATCH |
| SentryNotifier (guarded import, capture_message, fingerprint) | `notifications/sentry.py` | MATCH |
| Sentry init in lifespan (guarded by SENTRY_DSN + ImportError) | `api/api.py:557-566` | MATCH |
| build_dispatcher() called in lifespan | `api/api.py:568` | MATCH |
| /v1/run-eval dispatches on "failed" | `api/api.py:248-250` | MATCH |
| /v1/reeval-running-flows queries "running" + "failed" | `api/api.py:287` | MATCH |
| /v1/reeval-running-flows dispatches "failed->passed" transition | `api/api.py:326-332` | MATCH |
| /v1/reeval-running-flows dispatches new failures | `api/api.py:333-338` | MATCH |
| handle_new_batch_event dispatches on "failed" | `handlers.py:81-83` | MATCH |
| [notifications] optional extra (sentry-sdk>=2.0.0) | `pyproject.toml:57-59` | MATCH |
| config.yaml.example notification settings | `config.yaml.example:30-39` | MATCH |
| CLAUDE.md env vars documented | `CLAUDE.md:263-265` | MATCH |

**Zero discrepancies found.**

## Test Coverage Analysis

### Dispatcher tests (14 tests)
- Empty dispatcher no-op
- Single/multiple notifier routing
- Error isolation (failing notifier doesn't block others)
- Throttle: same (flow, status) skipped within window
- Throttle: different flow/status independent
- Throttle disabled (0), throttle expiration
- Transition parameter forwarding

### Slack tests (11 tests)
- Failed flow payload (danger color, correct blocks)
- Resolved transition payload (good color, transition text)
- Running flow payload (warning color)
- Duration formatting (ms, s, m)
- ASCII graph: linear, multi-child, empty
- HTTP: success, 500, 429, network error — all caught

### Sentry tests (11 tests)
- capture_message with correct level (error/info) for failed/passed/error/timed_out
- Tags (flow, run_id, eval_status) set correctly
- Context with/without transition
- Graceful skip when sentry-sdk not installed (warns once)
- Error handling (capture_message/set_tag exceptions caught)

### Integration tests (8 tests)
- build_dispatcher with no config → empty
- build_dispatcher with Slack only → 1 notifier (SlackNotifier)
- build_dispatcher with Sentry only → 1 notifier (SentryNotifier)
- build_dispatcher with both → 2 notifiers
- throttle_seconds forwarded
- get_dispatcher before/after build
- Noop dispatcher fresh each call

## Manual E2E: Slack Webhook

Sent 2 test notifications to real Slack webhook:

1. **Failed notification**: Flow `checkout`, run `qa_test_run_001`
   - 4-node graph (cart_created ✅, payment_processed ✅, inventory_reserved ❌, order_confirmed ⏸️)
   - Red/danger color sidebar
   - Duration: 3.2s
   - Result: **Delivered successfully**

2. **Resolved notification**: Flow `checkout`, run `qa_test_run_001`, transition `failed->passed`
   - 3-node graph (all ✅)
   - Green/good color sidebar
   - Result: **Delivered successfully**

## Architecture Review

- `eval_flow_run()` remains **pure** — zero side effects added
- Notifications fire **after** result persistence at call sites (not inside eval)
- Dispatcher is a module-level singleton via `get_dispatcher()` — accessible from both HTTP endpoints and event handlers
- No-op when unconfigured (empty notifiers list)
- Each notifier wraps all errors — one failing notifier cannot block others
- `sentry-sdk` is optional (`[notifications]` extra) with guarded import

## Notes

- Sentry integration not manually tested (requires real DSN) — unit tests provide adequate coverage via mocked sentry_sdk
- E2E test suite runs with no SLACK_WEBHOOK_URL configured, confirming the no-op path works correctly
