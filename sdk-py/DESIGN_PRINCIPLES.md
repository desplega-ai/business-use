# Business-Use SDK Design Principles

This document outlines the core design principles that guide the Business-Use SDK implementation, based on production-proven patterns from industry leaders.

## Inspired by the Giants

Our SDK design is based on research and best practices from:
- **Sentry** - Error tracking & performance monitoring
- **DataDog** - APM & observability
- **OpenTelemetry** - Open standard for telemetry
- **PostHog** - Product analytics

## Core Principles

### 1. Never Fail User Code

**Principle:** The SDK must never crash or block the host application.

**Implementation:**
- ✅ All exceptions caught and logged internally
- ✅ Network errors → logged, batch dropped
- ✅ Invalid parameters → logged, no-op
- ✅ Not initialized → silent no-op
- ✅ Async functions → rejected with error log

**Example:**
```python
# This will NEVER raise an exception
act(id="event", flow="test", run_id=None, data=None)  # Invalid params
# SDK logs error, returns immediately
```

### 2. Daemon Thread for Background Work

**Principle:** Don't block the main thread or prevent process exit.

**Implementation:**
- ✅ Worker thread created with `daemon=True`
- ✅ Parent process can exit immediately
- ✅ No hanging or blocking on shutdown
- ✅ Optional graceful shutdown via `shutdown()`

**Comparison:**

| SDK | Worker Type | Blocks Exit? | Graceful Shutdown |
|-----|-------------|--------------|-------------------|
| Sentry | Daemon thread | ❌ No | Optional |
| DataDog | Daemon thread | ❌ No | Optional |
| OpenTelemetry | Daemon thread | ❌ No | Optional |
| **Business-Use** | **Daemon thread** | **❌ No** | **Optional** |

### 3. Batching for Performance

**Principle:** Minimize network overhead by batching events.

**Implementation:**
- ✅ Dual trigger system: size (100) OR time (5s)
- ✅ Thread-safe queue (`queue.Queue`)
- ✅ Sequential batch processing (one at a time)
- ✅ Overflow protection (drop oldest events)

**Comparison:**

| SDK | Batch Size | Time Trigger | Queue Type |
|-----|------------|--------------|------------|
| Sentry | N/A (no batching) | N/A | Queue |
| DataDog | Configurable | Configurable | Buffer |
| OpenTelemetry | 512 spans | 5s | Deque |
| **Business-Use** | **100 events** | **5s** | **Queue** |

### 4. Environment-First Configuration

**Principle:** Support 12-factor app methodology with env vars.

**Implementation:**
- ✅ `BUSINESS_USE_API_KEY` - API key
- ✅ `BUSINESS_USE_URL` - Backend URL
- ✅ Parameters override env vars
- ✅ Sensible defaults (localhost:13370)

**Example:**
```bash
export BUSINESS_USE_API_KEY=your-key
export BUSINESS_USE_URL=https://api.desplega.ai
```

```python
# Just call initialize() - uses env vars
initialize()
```

### 5. Best-Effort Delivery

**Principle:** Telemetry is important but not critical - don't retry forever.

**Implementation:**
- ✅ No retries on network errors
- ✅ No persistent queue (in-memory only)
- ✅ Graceful degradation on failures
- ✅ Events are logged, not guaranteed

**Rationale:**
- Prevents memory leaks from retry queues
- Avoids cascading failures
- Keeps SDK lightweight
- Matches observability SDK patterns (not transactional)

### 6. Minimal Dependencies

**Principle:** Keep the dependency footprint small.

**Implementation:**
- ✅ Only 2 runtime dependencies:
  - `httpx` - HTTP client
  - `pydantic` - Data validation
- ✅ No heavy frameworks
- ✅ No database drivers
- ✅ Pure Python (no C extensions)

**Comparison:**

| SDK | Core Dependencies |
|-----|-------------------|
| Sentry | urllib3, certifi |
| DataDog | 6-8 packages |
| OpenTelemetry | 10+ packages |
| **Business-Use** | **2 packages** |

### 7. Developer Experience

**Principle:** Make it trivial to use correctly, hard to use incorrectly.

**Implementation:**
- ✅ Simple API: `initialize()`, `act()`, `assert_()`
- ✅ Type hints for IDE support
- ✅ Clear error messages
- ✅ Comprehensive documentation
- ✅ Working examples

**Example:**
```python
# Minimal setup
from business_use import initialize, act

initialize()  # Uses env vars
act(id="user_signup", flow="auth", run_id="123", data={"email": "user@example.com"})
```

### 8. Thread Safety

**Principle:** Support concurrent usage without data races.

**Implementation:**
- ✅ Thread-safe queue (`queue.Queue`)
- ✅ Initialization lock (`threading.Lock`)
- ✅ Singleton pattern for global state
- ✅ Safe from multiple threads calling `act()`/`assert_()`

### 9. Graceful Shutdown (Optional)

**Principle:** Allow graceful shutdown but don't require it.

**Implementation:**
- ✅ `shutdown(timeout=5)` - best-effort flush
- ✅ `atexit` integration recommended
- ✅ Signal handler integration supported
- ✅ Daemon thread ensures no hanging

**Example:**
```python
import atexit
from business_use import shutdown

# Recommended: Register cleanup
atexit.register(lambda: shutdown(timeout=5))
```

### 10. Lambda/Function Serialization

**Principle:** Support dynamic behavior while keeping backend execution simple.

**Implementation:**
- ✅ Extract function body only (no `def` or `return`)
- ✅ Strip docstrings and comments
- ✅ Reject async functions (client-side validation)
- ✅ Serialize to Python source code

**Example:**
```python
# Lambda
lambda data, ctx: data["amount"] > 0
# Sent to backend as: 'data["amount"] > 0'

# Function
def validate(data, ctx):
    return data["total"] > 0
# Sent to backend as: 'data["total"] > 0'
```

## Design Decisions

### Why Daemon Threads?

**Alternatives considered:**
1. ❌ **Regular threads** - Would block process exit
2. ❌ **Process pool** - Too heavy, complicated shutdown
3. ❌ **asyncio** - Requires async/await in user code
4. ✅ **Daemon threads** - Simple, proven, doesn't block

### Why No Retries?

**Alternatives considered:**
1. ❌ **Exponential backoff** - Complexity, memory buildup
2. ❌ **Persistent queue** - Disk I/O, complexity, potential corruption
3. ❌ **Dead letter queue** - Overkill for telemetry
4. ✅ **No retries** - Simple, matches observability patterns

**Rationale:**
- Telemetry != Transactions (events are not critical)
- Backend should be highly available (retries paper over real issues)
- Simplicity > Feature creep
- Matches Sentry's approach (no retries)

### Why Thread-Safe Queue?

**Alternatives considered:**
1. ❌ **Deque + Lock** - More complex, potential bugs
2. ❌ **Custom implementation** - Reinventing the wheel
3. ✅ **queue.Queue** - Built-in, tested, thread-safe

### Why Sync API Only?

**Alternatives considered:**
1. ❌ **Async/await API** - Forces user code to be async
2. ❌ **Dual API (sync + async)** - Maintenance burden, confusion
3. ✅ **Sync only** - Simple, works everywhere, background thread handles async

## Production Deployment Checklist

When deploying the SDK in production:

- [ ] Set `BUSINESS_USE_API_KEY` environment variable
- [ ] Set `BUSINESS_USE_URL` to production backend
- [ ] Register `shutdown()` in `atexit` or signal handlers
- [ ] Configure appropriate `batch_size` and `batch_interval`
- [ ] Set up monitoring for SDK error logs
- [ ] Test graceful shutdown behavior
- [ ] Verify network connectivity to backend
- [ ] Review queue size (`max_queue_size`) for traffic volume

## References

### Research Sources

1. **Sentry Python SDK**
   - BackgroundWorker pattern
   - No batching by design
   - Daemon threads
   - GitHub: `getsentry/sentry-python`

2. **DataDog dd-trace-py**
   - Writer/encoder buffering
   - Periodic flush mechanism
   - Configurable batch sizes
   - GitHub: `DataDog/dd-trace-py`

3. **OpenTelemetry Python**
   - BatchSpanProcessor design
   - Dual-trigger batching (size + time)
   - Thread-safe queue management
   - GitHub: `open-telemetry/opentelemetry-python`

### Further Reading

- [12-Factor App Methodology](https://12factor.net/)
- [Python Threading Best Practices](https://docs.python.org/3/library/threading.html)
- [Daemon Threads Explained](https://docs.python.org/3/library/threading.html#thread-objects)

---

**Document Version:** 1.0
**Last Updated:** 2025-01-20
**Status:** Final
