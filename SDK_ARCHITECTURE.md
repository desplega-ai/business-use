# Business-Use SDK Architecture

**Version:** 1.0
**Status:** Draft
**Target Languages:** Python, JavaScript

This document defines the architecture for Business-Use client SDKs. It provides a language-agnostic blueprint ensuring consistent behavior across all SDK implementations.

---

## Table of Contents

1. [Overview](#overview)
2. [Core Principles](#core-principles)
3. [Architecture Components](#architecture-components)
4. [Batching & Ingestion System](#batching--ingestion-system)
5. [Threading Model](#threading-model)
6. [API Contract](#api-contract)
7. [Error Handling](#error-handling)
8. [Lambda/Function Serialization](#lambdafunction-serialization)
9. [Graceful Shutdown](#graceful-shutdown)
10. [Configuration](#configuration)

---

## Overview

The Business-Use SDK provides a lightweight, synchronous API for tracking business events via the unified `ensure()` function. The event type is automatically determined based on whether a validator is provided:
- **Actions** (`act`): Created when `validator` is not provided
- **Assertions** (`assert`): Created when `validator` is provided

Events are batched and sent to a backend API to minimize performance impact.

### Design Goals

- **Zero user-facing failures**: SDK errors never crash or block user code
- **Minimal overhead**: Asynchronous batching prevents blocking I/O
- **Simple API**: Synchronous functions, no async/await required
- **Minimal dependencies**: Only HTTP client and schema validation libraries

---

## Core Principles

### 1. Never Fail User Code

The SDK must **never** throw exceptions or errors that reach user code:
- All network errors are caught and logged internally
- Invalid configurations result in no-op behavior with warnings
- Queue overflow silently drops oldest events

### 2. Asynchronous Ingestion

Events are collected in-memory and sent in background batches:
- `act()` and `assert()` return immediately (non-blocking)
- Background worker thread handles network I/O
- Batch triggers: size threshold OR time interval

### 3. Thread Safety

All public APIs are thread-safe:
- Multiple threads can call `act()`/`assert()` concurrently
- Internal queue uses thread-safe primitives
- Initialization is idempotent and thread-safe

---

## Architecture Components

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        User Application                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ initialize(api_key, url, ...)
                              ▼
                    ┌──────────────────┐
                    │   SDK Client     │
                    │   (Singleton)    │
                    └──────────────────┘
                              │
                              │ ensure()
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Thread-Safe Event Queue (FIFO)                  │
│  Max Size: batch_size * 10 (default 1000)                   │
│  Overflow: Drop oldest events                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ (background thread)
                              ▼
                    ┌──────────────────┐
                    │  Batch Processor │
                    │  Worker Thread   │
                    │  (daemon)        │
                    └──────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         │ Every 5s           │ OR                 │ Queue ≥ 100
         ▼                    ▼                    ▼
                    ┌──────────────────┐
                    │   Flush Batch    │
                    └──────────────────┘
                              │
                              │ POST /v1/events-batch
                              ▼
                    ┌──────────────────┐
                    │  Backend API     │
                    └──────────────────┘
```

### 1. SDK Client

**Responsibilities:**
- Validates connection on `initialize()`
- Stores configuration (API key, URL, batch settings)
- Provides public API: `ensure()` (auto-determines type based on validator)
- Manages initialization state (thread-safe)

**Type Auto-Detection:**
- If `validator` parameter is provided → creates "assert" node
- If `validator` is `None`/`undefined` → creates "act" node

**State:**
- `_initialized`: Boolean flag (protected by lock)
- `_api_key`: API key for authentication
- `_base_url`: Backend API URL
- `_batch_processor`: Reference to background worker

### 2. Event Queue

**Implementation:**
- **Python**: `queue.Queue` (thread-safe, blocking)
- **JavaScript**: Array with mutex (e.g., `async-mutex`)

**Behavior:**
- **Max Size**: Configurable (default: `batch_size * 10` = 1000)
- **Overflow Strategy**: Drop oldest events (FIFO eviction)
- **Thread Safety**: Built-in queue primitives

### 3. Batch Processor

**Responsibilities:**
- Runs in background daemon thread
- Dequeues events and batches them
- Sends batches to backend API
- Handles flush requests and shutdown signals

**Worker Loop:**
```
while not shutdown_signal:
    wait_for_event(timeout=100ms)  # Responsive to shutdown

    if should_flush():
        batch = collect_batch()
        send_batch(batch)
```

---

## Batching & Ingestion System

### Batch Triggering Logic

A batch is sent when **either** condition is met:

1. **Size Trigger**: Queue contains ≥ `batch_size` events (default: 100)
2. **Time Trigger**: `batch_interval` seconds elapsed since last flush (default: 5s)

### Batch Processing Flow

```
1. Dequeue events from queue (up to batch_size)
2. For each event:
   a. Evaluate filter (if False, skip event)
   b. Evaluate lambdas (run_id, dep_ids, validator)
   c. Transform to EventBatchItem format
3. POST batch to /v1/events-batch
4. On error: Log internally, DO NOT retry
```

### Lambda Evaluation

Before sending, evaluate callable parameters:

| Parameter   | Type                      | Action                           |
|-------------|---------------------------|----------------------------------|
| `filter`    | `bool \| callable`        | If callable, invoke → bool       |
| `run_id`    | `str \| callable`         | If callable, invoke → str        |
| `dep_ids`   | `list[str] \| callable`   | If callable, invoke → list[str]  |
| `validator` | `callable \| None`        | Serialize to script string       |

**Filter Early Exit**: If filter evaluates to `False`, event is dropped **before** adding to batch.

### Batch Size Considerations

**Research Findings** (from Sentry, DataDog, OpenTelemetry):
- Sentry: No native batching (1 event per request)
- OpenTelemetry: Default batch size = 512 spans
- DataDog: Configurable buffer size

**Our Defaults**:
- `batch_size`: 100 events (balance between latency and throughput)
- `batch_interval`: 5 seconds (responsive for development)
- `max_queue_size`: 1000 events (10x batch size)

---

## Threading Model

### Background Worker Thread

**Thread Type**: Daemon thread
- Automatically terminates when main program exits
- Does not prevent program shutdown

**Thread Name**: `BusinessUseWorker` (for debugging)

**Lifecycle**:
1. **Start**: Created during `initialize()`, begins immediately
2. **Run**: Infinite loop checking for flush conditions
3. **Shutdown**: Triggered by shutdown signal or program exit

### Synchronization Primitives

**Python**:
- `threading.Lock` for initialization state
- `threading.Event` for shutdown signaling
- `queue.Queue` for event storage (built-in thread safety)

**JavaScript**:
- Mutex for initialization state (e.g., `async-mutex`)
- Promise-based shutdown coordination
- Thread-safe queue implementation

### Worker Loop Algorithm

```python
while True:
    # Check shutdown signal (non-blocking)
    if shutdown_event.is_set():
        flush_remaining()
        break

    # Wait for events or timeout (100ms for responsiveness)
    try:
        event = queue.get(timeout=0.1)
        batch.append(event)
    except QueueEmpty:
        pass

    # Check flush conditions
    if len(batch) >= batch_size or time_since_last_flush >= batch_interval:
        send_batch(batch)
        batch.clear()
        last_flush_time = now()
```

**Key Points**:
- **100ms timeout**: Balances responsiveness with CPU usage
- **Non-blocking shutdown check**: Ensures timely termination
- **Dual flush conditions**: Size OR time

---

## API Contract

### Backend Endpoints

#### 1. Connection Check

```
GET /v1/check
Headers:
  X-Api-Key: <api_key>

Response (200 OK):
{
  "status": "success",
  "message": "lgtm"
}

Response (401/403):
{
  "detail": "Invalid API key"
}
```

#### 2. Event Batch Ingestion

```
POST /v1/events-batch
Headers:
  X-Api-Key: <api_key>
  Content-Type: application/json

Body:
[
  {
    "flow": "checkout",
    "id": "payment_processed",
    "run_id": "run_12345",
    "type": "act",  // or "assert"
    "data": {"amount": 100, "currency": "USD"},
    "ts": 1703001234567890123,  // nanoseconds
    "description": "Payment processed successfully",
    "dep_ids": ["cart_created", "payment_initiated"],
    "filter": {
      "engine": "python",
      "script": "data.get('amount', 0) > 0"
    },
    "validator": {
      "engine": "python",
      "script": "def validate(data, ctx):\n    return data['amount'] > 0"
    }
  }
]

Response (200 OK):
{
  "status": "success",
  "message": "Ok"
}
```

### EventBatchItem Schema

```typescript
{
  flow: string              // Required: Flow identifier
  id: string                // Required: Node/event ID
  run_id: string            // Required: Run identifier
  type: "act" | "assert"    // Required: Event type
  data: object              // Required: Event payload
  ts: integer               // Required: Timestamp (nanoseconds)
  description?: string      // Optional: Human-readable description
  dep_ids?: string[]        // Optional: Dependency node IDs
  filter?: Expr             // Optional: Filter expression
  validator?: Expr          // Optional: Validator expression (assert only)
}

Expr:
{
  engine: "python" | "js" | "cel"
  script: string
}
```

---

## Error Handling

### Never Fail User Code

**Principle**: All SDK errors are **internal** and **logged**, never propagated.

### Error Scenarios & Handling

| Scenario                     | Behavior                                | User Impact |
|------------------------------|-----------------------------------------|-------------|
| Invalid API key              | Log warning, no-op mode                 | None        |
| Network error on `/check`    | Log error, no-op mode                   | None        |
| Network error on batch send  | Log error, drop batch                   | Events lost |
| Queue overflow               | Drop oldest events, log metrics         | Old events lost |
| Lambda evaluation error      | Log error, skip event                   | Event skipped |
| Invalid parameters           | Log warning, no-op for that call        | None        |
| Not initialized              | Silent no-op                            | None        |

### Logging Strategy

**Log Levels**:
- `ERROR`: Critical failures (network errors, API errors)
- `WARNING`: Recoverable issues (queue overflow, invalid params)
- `DEBUG`: Operational details (batch sent, events queued)

**Log Format**:
```
[business-use] [timestamp] [LEVEL] message
```

**Example Logs**:
```
[business-use] [2025-01-20 10:30:45] ERROR Failed to send batch: Connection timeout
[business-use] [2025-01-20 10:30:50] WARNING Queue overflow: Dropped 10 events
[business-use] [2025-01-20 10:30:55] DEBUG Batch sent: 100 events
```

### Retry Strategy

**No Retries**: Failed batches are dropped, not retried.

**Rationale**:
- Simplicity over complexity
- Avoid memory buildup from retry queues
- Events are telemetry (not critical transactions)
- Backend should be highly available

---

## Lambda/Function Serialization

### Supported Parameters

| Parameter   | Type                      | Serialization              |
|-------------|---------------------------|----------------------------|
| `filter`    | `bool \| callable`        | If callable → source code  |
| `run_id`    | `str \| callable`         | If callable → source code  |
| `dep_ids`   | `list[str] \| callable`   | If callable → source code  |
| `validator` | `callable \| None`        | Source code                |

### Serialization Strategy

**Python**:
```python
import inspect

def serialize_lambda(fn):
    return {
        "engine": "python",
        "script": inspect.getsource(fn)
    }
```

**JavaScript**:
```javascript
function serializeLambda(fn) {
  return {
    engine: "js",
    script: fn.toString()
  };
}
```

### Execution Context

**Backend Execution**: Lambdas are serialized as strings and executed on the backend.

**Available Context** (validator only):
- `data`: Event data dictionary
- `ctx`: Context object (upstream event data, run metadata)

**Example Validator**:
```python
def validator(data, ctx):
    # Access event data
    amount = data.get('amount', 0)

    # Access upstream context
    previous_amount = ctx.get('upstream_data', {}).get('amount', 0)

    return amount > previous_amount
```

### Lambda Evaluation Timing

| Parameter   | Evaluated When           | Evaluated Where |
|-------------|--------------------------|-----------------|
| `filter`    | Before adding to queue   | Client-side     |
| `run_id`    | During batch processing  | Client-side     |
| `dep_ids`   | During batch processing  | Client-side     |
| `validator` | Never (sent as string)   | Backend         |

**Rationale for filter evaluation**:
- Early filtering reduces queue size
- Prevents unnecessary network traffic
- Evaluated client-side for performance

---

## Graceful Shutdown

### Shutdown Triggers

1. **Program Exit**: Main thread terminates
2. **Explicit Flush**: User calls `flush()` (optional API)
3. **Manual Shutdown**: User calls `shutdown()` (optional API)

### Shutdown Sequence

```
1. Set shutdown signal (threading.Event)
2. Wait for worker thread to finish current batch (with timeout)
3. Flush remaining events in queue (best-effort)
4. Send final batch to backend
5. Terminate worker thread
6. Log shutdown completion
```

### Best-Effort Flush

**Timeout**: 5 seconds (configurable)

**Behavior**:
- Worker thread attempts to send all queued events
- If timeout expires, remaining events are dropped
- No exceptions thrown, only logged

### Sentinel Pattern (Alternative)

**Alternative Approach** (for explicit shutdown API):
```python
def shutdown(timeout=5):
    # Add sentinel value to queue
    queue.put(SHUTDOWN_SENTINEL)

    # Wait for worker to process sentinel
    worker_thread.join(timeout=timeout)
```

**Recommendation**: Use `threading.Event` for simplicity (no sentinel needed with daemon threads).

---

## Configuration

### Initialize Parameters

```python
def initialize(
    api_key: str,                      # Required: API key for authentication
    url: str = "http://localhost:13370",  # Optional: Backend API URL
    batch_size: int = 100,              # Optional: Events per batch
    batch_interval: int = 5,            # Optional: Flush interval (seconds)
    max_queue_size: int | None = None, # Optional: Max queue size (default: batch_size * 10)
) -> None
```

### Defaults

| Parameter        | Default Value            | Rationale                          |
|------------------|--------------------------|------------------------------------|
| `url`            | `http://localhost:13370` | Local development default          |
| `batch_size`     | 100                      | Balance latency/throughput         |
| `batch_interval` | 5 seconds                | Responsive for development         |
| `max_queue_size` | `batch_size * 10` (1000) | 10x buffer before overflow         |

### Environment Variables (Future)

**Optional Enhancement**:
```
BUSINESS_USE_API_KEY=your_api_key
BUSINESS_USE_URL=http://localhost:13370
BUSINESS_USE_BATCH_SIZE=100
BUSINESS_USE_BATCH_INTERVAL=5
```

---

## Implementation Checklist

### Python SDK

- [ ] `queue.Queue` for event storage
- [ ] `threading.Thread` (daemon=True) for worker
- [ ] `threading.Lock` for initialization state
- [ ] `threading.Event` for shutdown signal
- [ ] `httpx` for HTTP client (sync mode)
- [ ] `pydantic` for model validation
- [ ] `inspect.getsource()` for lambda serialization
- [ ] `time.time_ns()` for nanosecond timestamps
- [ ] Logging via `logging` module

### JavaScript SDK

- [ ] Array + mutex for event storage
- [ ] Worker thread or async loop for batching
- [ ] Mutex for initialization state
- [ ] Promise-based shutdown coordination
- [ ] `fetch` or `axios` for HTTP client
- [ ] Zod or similar for model validation
- [ ] `Function.toString()` for lambda serialization
- [ ] `process.hrtime.bigint()` for nanosecond timestamps
- [ ] Logging via `console` or Winston

---

## Performance Considerations

### Memory Usage

**Queue Size**: Max 1000 events × ~1KB/event = ~1MB maximum memory
**Batch Size**: 100 events × ~1KB/event = ~100KB per batch

### CPU Usage

**Worker Thread**: Minimal overhead
- Sleeps 100ms between checks (low CPU)
- Only active during batch processing

### Network Usage

**Batch Frequency**: Every 5 seconds (default)
**Payload Size**: ~100KB per batch (default)
**Bandwidth**: ~20KB/s sustained (at default settings)

---

## Future Enhancements

### Phase 2 (Optional)

1. **Persistent Queue**: Survive process restarts (SQLite, file-based)
2. **Retry Logic**: Exponential backoff for network errors
3. **Metrics API**: Expose dropped events, batch stats
4. **Sampling**: Sample events (e.g., 10% of traffic)
5. **Compression**: Gzip payloads for large batches
6. **Circuit Breaker**: Disable SDK after repeated failures

### Phase 3 (Advanced)

1. **Multi-Backend**: Support multiple backend URLs
2. **Custom Transports**: Pluggable HTTP clients
3. **Event Hooks**: Callbacks on batch send, errors
4. **Dynamic Configuration**: Update settings at runtime

---

## References

### Researched SDKs

- **Sentry Python SDK**: BackgroundWorker pattern, envelope format
- **DataDog dd-trace-py**: Writer/encoder buffering, periodic flush
- **OpenTelemetry Python**: BatchSpanProcessor, dual-trigger batching

### Key Learnings

1. **Daemon threads**: Standard for background workers
2. **Queue overflow**: Drop oldest events (Sentry, OTel)
3. **Dual triggers**: Size + time for batching (OTel)
4. **No retries**: Simplicity over complexity (Sentry)
5. **Graceful shutdown**: Best-effort flush with timeout

---

## Glossary

- **Act**: Business event tracking (e.g., "payment processed")
- **Assert**: Business assertion validation (e.g., "order total matches")
- **Batch**: Collection of events sent to backend in single request
- **Daemon Thread**: Background thread that doesn't prevent program exit
- **Flush**: Send pending events to backend immediately
- **Lambda**: Anonymous function (Python) or arrow function (JS)
- **No-op**: No operation (function does nothing)
- **Sentinel**: Special value signaling end-of-data
- **Thread-safe**: Safe for concurrent access from multiple threads

---

**Document Version**: 1.0
**Last Updated**: 2025-01-20
**Authors**: Business-Use Team
**Status**: Draft → Review → Approved
