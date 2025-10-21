# Design Principles - Business-Use JavaScript SDK

This document outlines the design principles and architectural decisions for the JavaScript/TypeScript SDK.

## Core Design Philosophy

The JavaScript SDK follows the same principles as the Python SDK, adapted for the JavaScript ecosystem:

1. **Never Fail User Code** - All errors are caught and logged internally
2. **Asynchronous Ingestion** - Events are batched and sent in the background
3. **Thread Safety** - Leverages JavaScript's single-threaded event loop
4. **Minimal Dependencies** - Only Zod for schema validation

## Key Architectural Decisions

### 1. Timer Management (Following OpenTelemetry Pattern)

**Decision**: Use recursive `setTimeout` instead of `setInterval`

**Rationale**:
- Better control over execution timing
- Prevents queue buildup
- Can be cancelled cleanly on shutdown
- Allows calling `.unref()` in Node.js to prevent process hanging

**Implementation**:
```typescript
private _maybeStartTimer(): void {
  this._timer = setTimeout(() => {
    this._timer = null;
    this._flushBatch();
    this._maybeStartTimer(); // Recursive rescheduling
  }, this._batchInterval);

  // Prevent timer from keeping process alive
  if (typeof (this._timer as any).unref === 'function') {
    (this._timer as any).unref();
  }
}
```

### 2. No Mutex Required

**Decision**: Simple array-based queue without locking mechanisms

**Rationale**:
- JavaScript is single-threaded by design
- Event loop handles concurrency automatically
- No race conditions in synchronous code
- Simpler implementation than Python's threading model

### 3. Function Serialization

**Decision**: Use `Function.toString()` with smart body extraction

**Rationale**:
- Equivalent to Python's `inspect.getsource()`
- Works for arrow functions and regular functions
- Extracts just the expression for lambdas: `(data) => data.x > 0` → `data.x > 0`
- Simpler for backend to evaluate

**Implementation**:
```typescript
private _serializeFunction(fn: Function): Expr {
  const source = fn.toString().trim();

  if (source.includes('=>')) {
    // Extract arrow function body
    const body = source.substring(source.indexOf('=>') + 2).trim();
    // Remove braces, return statements, semicolons
    return { engine: 'js', script: cleanedBody };
  }

  return { engine: 'js', script: source };
}
```

### 4. Native Fetch API

**Decision**: Use native `fetch` (Node.js 18+) instead of external HTTP libraries

**Rationale**:
- Reduces dependencies
- Standard API across browsers and Node.js
- Simpler async/await pattern
- Matches modern JavaScript practices

### 5. Promise-Based Shutdown

**Decision**: `shutdown()` returns a Promise

**Rationale**:
- Idiomatic JavaScript for async operations
- Allows users to `await shutdown()` for clean exit
- Timeout protection built-in
- Matches Sentry's approach

## Configuration Defaults

Matching Python SDK for consistency:

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `batchSize` | 100 | Balance between latency and throughput |
| `batchInterval` | 5000ms | Responsive for development (5 seconds) |
| `maxQueueSize` | 1000 | 10x batch size buffer |
| `shutdownTimeout` | 5000ms | Reasonable time for graceful shutdown |

## Industry Best Practices Applied

### From OpenTelemetry
- **Intelligent timer scheduling** - Only start timer when queue < batch size
- **FIFO queue overflow** - Drop oldest events when full
- **Timeout protection** - Shutdown with configurable timeout

### From Sentry
- **Promise-based coordination** - Async shutdown handling
- **No retries** - Failed batches are dropped for simplicity
- **Rate limiting awareness** - Designed to respect backend limits

### From DataDog/Optimizely
- **Batch triggering** - Size OR time (dual conditions)
- **Max payload limits** - Respect 3.5MB typical limits
- **Environment variable support** - Standard configuration approach

## TypeScript-Specific Features

### Type Safety
- Full TypeScript types for all public APIs
- Zod schemas for runtime validation
- Type inference for function parameters

### Module Formats
- ESM (modern `import`)
- CommonJS (legacy `require`)
- TypeScript definitions (.d.ts files)

### Build System
- tsup for fast, zero-config bundling
- Dual CJS/ESM output
- Source maps for debugging

## Testing Strategy

### Unit Tests (Vitest)
- Client behavior (async rejection, initialization, env vars)
- Function serialization
- Mock fetch for HTTP operations
- Fast execution (<1 second)

### Example File
- Real-world usage patterns
- Demonstrates all API features
- Can be run against actual backend

## Error Handling Philosophy

**Never throw to user code**:

```typescript
export function act(options) {
  // No-op if not initialized
  if (!_state.initialized) {
    return; // Silent no-op
  }

  try {
    // ... implementation
  } catch (error) {
    log.error(`Failed: ${error}`);
    // Never re-throw
  }
}
```

## Future Enhancements

### Phase 2
- Browser support (LocalStorage queue persistence)
- Compression for large batches
- Metrics API (dropped events, batch stats)
- Circuit breaker pattern

### Phase 3
- Web Workers for true parallel processing
- IndexedDB for offline queue
- Service Worker integration
- Custom transport plugins

## Comparison with Python SDK

| Aspect | Python | JavaScript |
|--------|--------|------------|
| Threading | `threading.Thread` (daemon) | Recursive `setTimeout` |
| Queue | `queue.Queue` (thread-safe) | Simple array |
| HTTP | `httpx.Client` | Native `fetch` |
| Timestamps | `time.time_ns()` | `process.hrtime.bigint()` |
| Serialization | `inspect.getsource()` | `Function.toString()` |
| Async Detection | `inspect.iscoroutinefunction()` | `fn.constructor.name === 'AsyncFunction'` |

## Lessons from Research

1. **Sentry** - Showed importance of keepalive and rate limiting
2. **DataDog** - Demonstrated value of batching in browser SDKs
3. **OpenTelemetry** - Provided best pattern for timer management and queue handling
4. **Optimizely** - Confirmed our defaults (batch size, interval) are industry-standard

## Conclusion

This SDK provides a production-ready implementation that:
- Matches Python SDK behavior exactly
- Follows JavaScript/TypeScript best practices
- Incorporates learnings from industry leaders
- Maintains simplicity and reliability
