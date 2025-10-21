# Business-Use JavaScript SDK

[![Format & Lint Checks](https://github.com/desplega-ai/business-use/actions/workflows/check.yaml/badge.svg)](https://github.com/desplega-ai/business-use/actions/workflows/check.yaml)

A lightweight JavaScript/TypeScript SDK for tracking business events and assertions in production applications.

## Features

- **Zero user-facing failures**: SDK errors never crash or block your code
- **Minimal overhead**: Asynchronous batching prevents blocking I/O
- **Simple API**: Synchronous functions, no async/await required
- **Type-safe**: Full TypeScript support with comprehensive type definitions
- **Minimal dependencies**: Only Zod for schema validation

## Installation

```bash
# Using pnpm
pnpm add @desplega.ai/business-use

# Using npm
npm install @desplega.ai/business-use

# Using yarn
yarn add @desplega.ai/business-use
```

## Quick Start

```typescript
import { initialize, act, assert } from '@desplega.ai/business-use';

// Initialize the SDK (call once at app startup)
initialize({
  apiKey: 'your-api-key',
  url: 'http://localhost:13370', // Optional, defaults to localhost
});

// Track a business action
act({
  id: 'payment_processed',
  flow: 'checkout',
  runId: 'run_12345',
  data: { amount: 100, currency: 'USD' },
  description: 'Payment processed successfully'
});

// Track a business assertion
function validateOrderTotal(data: Record<string, any>, ctx: Record<string, any>): boolean {
  return data.total > 0;
}

assert({
  id: 'order_total_valid',
  flow: 'checkout',
  runId: 'run_12345',
  data: { total: 150 },
  validator: validateOrderTotal,
  description: 'Order total validation'
});
```

## API Reference

### `initialize(options?)`

Initialize the Business-Use SDK. Must be called before using `act()` or `assert()`.

**Options:**
- `apiKey?: string` - API key for authentication (default: from `BUSINESS_USE_API_KEY` env var)
- `url?: string` - Backend API URL (default: from `BUSINESS_USE_URL` env var or `http://localhost:13370`)
- `batchSize?: number` - Number of events per batch (default: 100)
- `batchInterval?: number` - Flush interval in milliseconds (default: 5000)
- `maxQueueSize?: number` - Maximum queue size (default: `batchSize * 10`)

**Example:**
```typescript
initialize({
  apiKey: 'your-api-key',
  url: 'https://api.example.com',
  batchSize: 50,
  batchInterval: 3000,
});
```

### `act(options)`

Track a business action event. Non-blocking and synchronous.

**Options:**
- `id: string` - Unique event identifier (e.g., `"payment_processed"`)
- `flow: string` - Flow identifier (e.g., `"checkout"`)
- `runId: string | (() => string)` - Run identifier (string or function)
- `data: Record<string, any>` - Event data payload
- `filter?: boolean | (() => boolean)` - Optional filter (if false, event is skipped)
- `depIds?: string[] | (() => string[])` - Optional dependency node IDs
- `description?: string` - Optional human-readable description

**Example:**
```typescript
act({
  id: 'user_signup',
  flow: 'onboarding',
  runId: 'run_001',
  data: { email: 'user@example.com', plan: 'premium' },
  depIds: ['landing_page_visit'],
  description: 'User signed up for premium plan'
});

// Using functions for dynamic values
act({
  id: 'order_completed',
  flow: 'checkout',
  runId: () => getCurrentRunId(),
  data: { orderId: order.id },
  filter: () => order.amount > 0,
});
```

### `assert(options)`

Track a business assertion. Non-blocking and synchronous.

**Options:**
- `id: string` - Unique assertion identifier (e.g., `"order_total_valid"`)
- `flow: string` - Flow identifier (e.g., `"checkout"`)
- `runId: string | (() => string)` - Run identifier (string or function)
- `data: Record<string, any>` - Event data payload
- `filter?: boolean | (() => boolean)` - Optional filter (if false, assertion is skipped)
- `depIds?: string[] | (() => string[])` - Optional dependency node IDs
- `validator?: (data, ctx) => boolean` - Optional validation function (executed on backend)
- `description?: string` - Optional human-readable description

**Example:**
```typescript
function validatePayment(data: Record<string, any>, ctx: Record<string, any>): boolean {
  return data.amount > 0 && ['USD', 'EUR', 'GBP'].includes(data.currency);
}

assert({
  id: 'payment_valid',
  flow: 'checkout',
  runId: 'run_002',
  data: { amount: 99.99, currency: 'USD' },
  validator: validatePayment,
  description: 'Payment validation check'
});
```

### `shutdown(timeout?)`

Gracefully shutdown the SDK. Attempts to flush all remaining events.

**Parameters:**
- `timeout?: number` - Maximum time to wait in milliseconds (default: 5000)

**Returns:** `Promise<void>`

**Example:**
```typescript
// At application shutdown
await shutdown(5000);
```

## Environment Variables

The SDK supports configuration via environment variables:

- `BUSINESS_USE_API_KEY` - API key for authentication
- `BUSINESS_USE_URL` - Backend API URL

**Example:**
```bash
export BUSINESS_USE_API_KEY="your-api-key"
export BUSINESS_USE_URL="https://api.example.com"
```

```typescript
// Will use environment variables
initialize();
```

## Configuration

### Batch Processing

Events are batched and sent to the backend when either condition is met:

1. **Size trigger**: Queue contains ≥ `batchSize` events (default: 100)
2. **Time trigger**: `batchInterval` milliseconds elapsed since last flush (default: 5000ms)

### Queue Management

- **Max queue size**: `batchSize * 10` (default: 1000 events)
- **Overflow strategy**: Drops oldest events (FIFO eviction)
- **Thread safety**: Built on JavaScript event loop (inherently single-threaded)

## Error Handling

The SDK is designed to **never fail your application**:

- All network errors are caught and logged internally
- Invalid configurations result in no-op behavior with warnings
- Queue overflow silently drops oldest events
- No exceptions are thrown to user code

## TypeScript Support

The SDK is written in TypeScript and provides full type definitions with **type-safe filter and validator functions**:

```typescript
import { initialize, act, assert, type EventBatchItem } from '@desplega.ai/business-use';

// Type inference - the data parameter in filter/validator is automatically typed!
act({
  id: 'payment_processed',
  flow: 'checkout',
  runId: 'run_123',
  data: { amount: 100, currency: 'USD' },
  filter: (data) => data.amount > 0, // data.amount is known to exist!
});

// Explicit types for even better type safety
interface OrderData {
  orderId: string;
  total: number;
  items: Array<{ id: string; price: number }>;
}

assert<OrderData>({
  id: 'order_validation',
  flow: 'checkout',
  runId: 'run_456',
  data: {
    orderId: '12345',
    total: 200,
    items: [
      { id: 'item1', price: 100 },
      { id: 'item2', price: 100 },
    ],
  },
  validator: (data, ctx) => {
    // Full autocomplete and type checking for data!
    const calculatedTotal = data.items.reduce((sum, item) => sum + item.price, 0);
    return data.total === calculatedTotal;
  },
});
```

### Type Safety Features

- **Automatic type inference**: The `data` parameter in `filter` and `validator` functions is automatically typed based on the `data` field
- **Explicit type parameters**: Use generic type parameters (`act<T>`, `assert<T>`) for even stricter type checking
- **Nested object support**: Full type safety for complex nested data structures
- **IDE autocomplete**: Get full IntelliSense/autocomplete in VS Code and other TypeScript-aware editors

## Architecture

The SDK follows industry best practices inspired by OpenTelemetry, Sentry, and DataDog:

- **Array-based queue** with configurable size limits
- **Recursive setTimeout** (not setInterval) for reliable timer management
- **Promise-based shutdown** with timeout protection
- **Client-side filter evaluation** to reduce network traffic
- **Function serialization** for backend execution of validators

## Development

```bash
# Install dependencies
pnpm install

# Build the SDK
pnpm build

# Run tests
pnpm test

# Run tests with UI
pnpm test:ui

# Run example
pnpm example

# Type check
pnpm typecheck
```

## License

MIT

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Support

For issues and questions:
- GitHub Issues: https://github.com/desplega-ai/business-use/issues
- Documentation: https://github.com/desplega-ai/business-use#readme
