# Business-Use JavaScript SDK

[![Format & Lint Checks](https://github.com/desplega-ai/business-use/actions/workflows/check.yaml/badge.svg)](https://github.com/desplega-ai/business-use/actions/workflows/check.yaml)

A lightweight JavaScript/TypeScript SDK for tracking business events and assertions in production applications.

## Features

- **Zero user-facing failures**: SDK errors never crash or block your code
- **Minimal overhead**: Asynchronous batching prevents blocking I/O
- **Simple API**: Main function `ensure()` with convenience helpers `act()` and `assert()`
- **Type-safe**: Full TypeScript support with comprehensive type definitions
- **Context-aware**: Filters and validators can access upstream dependency data
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
import { initialize, ensure } from '@desplega.ai/business-use';

// Initialize the SDK (call once at app startup)
initialize({ apiKey: 'your-api-key' });

// Track a business action (no validator)
ensure({
  id: 'payment_processed',
  flow: 'checkout',
  runId: 'run_12345',
  data: { amount: 100, currency: 'USD' },
  description: 'Payment processed successfully'
});

// Track a business assertion (with validator)
function validateOrderTotal(data: Record<string, any>, ctx: { deps: Array<{ flow: string; id: string; data: Record<string, any> }> }): boolean {
  // ctx.deps contains upstream dependency events
  const hasCart = ctx.deps.some((dep) => dep.id === 'cart_created');
  return data.total > 0 && hasCart;
}

ensure({
  id: 'order_total_valid',
  flow: 'checkout',
  runId: 'run_12345',
  data: { total: 150 },
  depIds: ['cart_created'],
  validator: validateOrderTotal, // Creates "assert" node
  description: 'Order total validation'
});

// Convenience wrappers (optional)
import { act, assert } from '@desplega.ai/business-use';

// act() is ensure() without validator
act({ id: 'user_signup', flow: 'onboarding', runId: 'u123', data: {...} });

// assert() is ensure() with validator
assert({ id: 'validation', flow: 'checkout', runId: 'o123', data: {...}, validator: fn });
```

## API Reference

### `initialize(options?)`

Initialize the Business-Use SDK. Must be called before using `ensure()`.

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

### `ensure(options)`

**Main function** to track business events. Type is auto-determined by the presence of a `validator`.

**Options:**
- `id: string` - Unique event identifier (e.g., `"payment_processed"`)
- `flow: string` - Flow identifier (e.g., `"checkout"`)
- `runId: string | (() => string)` - Run identifier (string or function)
- `data: Record<string, any>` - Event data payload
- `filter?: (data, ctx) => boolean` - Optional filter function evaluated on backend
- `depIds?: string[] | (() => string[])` - Optional dependency node IDs
- `validator?: (data, ctx) => boolean` - Optional validation function executed on backend
- `description?: string` - Optional human-readable description

**Type determination:**
- If `validator` is provided → creates an **"assert"** node
- If `validator` is `undefined` → creates an **"act"** node

**Example:**
```typescript
// Action node (no validator)
ensure({
  id: 'payment_processed',
  flow: 'checkout',
  runId: 'run_12345',
  data: { amount: 100, currency: 'USD' },
  depIds: ['cart_created'],
  description: 'Payment processed successfully',
});

// Assertion node (with validator)
function validateTotal(data: Record<string, any>, ctx: { deps: DepData[] }): boolean {
  const itemsTotal = ctx.deps.reduce((sum, dep) => sum + dep.data.price, 0);
  return data.total === itemsTotal;
}

ensure({
  id: 'order_total_valid',
  flow: 'checkout',
  runId: 'run_12345',
  data: { total: 150 },
  depIds: ['item_added'],
  validator: validateTotal,
  description: 'Order total validation',
});
```

### `act(options)`

**Convenience wrapper** around `ensure()` without a validator. Creates an "act" node.

**Options:**
- `id: string` - Unique event identifier (e.g., `"payment_processed"`)
- `flow: string` - Flow identifier (e.g., `"checkout"`)
- `runId: string | (() => string)` - Run identifier (string or function)
- `data: Record<string, any>` - Event data payload
- `filter?: (data, ctx) => boolean` - Optional filter function evaluated on backend
- `depIds?: string[] | (() => string[])` - Optional dependency node IDs
- `description?: string` - Optional human-readable description

**Filter Function Signature:**

```typescript
function myFilter(
  data: Record<string, any>,
  ctx: { deps: Array<{ flow: string; id: string; data: Record<string, any> }> }
): boolean {
  // Return true to include event, false to filter it out
  // ctx.deps contains all upstream dependency events
  return true;
}
```

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
  depIds: () => getDependencies(),
});

// With filter based on upstream dependencies
function checkPrerequisites(
  data: Record<string, any>,
  ctx: { deps: Array<{ flow: string; id: string; data: Record<string, any> }> }
): boolean {
  // Only process if all upstream tasks are approved
  return ctx.deps.every((dep) => dep.data.status === 'approved');
}

act({
  id: 'order_finalized',
  flow: 'checkout',
  runId: 'run_12345',
  data: { orderId: 'ord_123' },
  depIds: ['payment_processed', 'inventory_reserved'],
  filter: checkPrerequisites, // Evaluated on backend with ctx
  description: 'Order finalized after all prerequisites',
});
```

### `assert(options)`

**Convenience wrapper** around `ensure()` with a validator. Creates an "assert" node.

**Options:**
- `id: string` - Unique assertion identifier (e.g., `"order_total_valid"`)
- `flow: string` - Flow identifier (e.g., `"checkout"`)
- `runId: string | (() => string)` - Run identifier (string or function)
- `data: Record<string, any>` - Event data payload
- `filter?: (data, ctx) => boolean` - Optional filter function evaluated on backend
- `depIds?: string[] | (() => string[])` - Optional dependency node IDs
- `validator?: (data, ctx) => boolean` - Optional validation function executed on backend
- `description?: string` - Optional human-readable description

**Validator Function Signature:**

```typescript
function myValidator(
  data: Record<string, any>,
  ctx: { deps: Array<{ flow: string; id: string; data: Record<string, any> }> }
): boolean {
  // Return true if validation passes, false if it fails
  // ctx.deps contains all upstream dependency events
  return true;
}
```

**Example:**
```typescript
// Validator accessing upstream dependencies
function validateOrderTotal(
  data: Record<string, any>,
  ctx: { deps: Array<{ flow: string; id: string; data: Record<string, any> }> }
): boolean {
  // Calculate total from upstream item_added events
  const itemsTotal = ctx.deps
    .filter((dep) => dep.id === 'item_added')
    .reduce((sum, dep) => sum + dep.data.price, 0);

  // Verify order total matches
  return data.total === itemsTotal;
}

assert({
  id: 'order_total_matches',
  flow: 'checkout',
  runId: 'run_12345',
  data: { total: 150 },
  depIds: ['item_added'], // Multiple item_added events
  validator: validateOrderTotal,
  description: 'Order total matches sum of item prices',
});

// Validator with complex logic
function validatePaymentAndInventory(
  data: Record<string, any>,
  ctx: { deps: Array<{ flow: string; id: string; data: Record<string, any> }> }
): boolean {
  const paymentApproved = ctx.deps.some(
    (dep) => dep.id === 'payment_processed' && dep.data.status === 'approved'
  );
  const inventoryReserved = ctx.deps.some(
    (dep) => dep.id === 'inventory_reserved' && dep.data.reserved === true
  );
  return paymentApproved && inventoryReserved && data.readyToShip;
}

assert({
  id: 'order_ready',
  flow: 'checkout',
  runId: 'run_12345',
  data: { readyToShip: true },
  depIds: ['payment_processed', 'inventory_reserved'],
  validator: validatePaymentAndInventory,
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
import { initialize, act, assert, type Ctx, type DepData } from '@desplega.ai/business-use';

// Type inference - both data and ctx are automatically typed!
act({
  id: 'payment_processed',
  flow: 'checkout',
  runId: 'run_123',
  data: { amount: 100, currency: 'USD' },
  depIds: ['cart_created'],
  filter: (data, ctx) => {
    // data.amount is known to exist!
    // ctx.deps gives you access to upstream dependencies
    return data.amount > 0 && ctx.deps.length > 0;
  },
});

// Explicit types for even better type safety
interface OrderData {
  orderId: string;
  total: number;
}

interface ItemData {
  id: string;
  price: number;
}

assert<OrderData>({
  id: 'order_validation',
  flow: 'checkout',
  runId: 'run_456',
  data: { orderId: '12345', total: 200 },
  depIds: ['item_added'],
  validator: (data, ctx) => {
    // Full autocomplete and type checking for data!
    // ctx.deps contains all upstream item_added events
    const calculatedTotal = ctx.deps
      .filter((dep) => dep.id === 'item_added')
      .reduce((sum, dep) => sum + (dep.data as ItemData).price, 0);
    return data.total === calculatedTotal;
  },
});
```

### Type Safety Features

- **Automatic type inference**: Both `data` and `ctx` parameters in `filter` and `validator` functions are automatically typed
- **Explicit type parameters**: Use generic type parameters (`act<T>`, `assert<T>`) for even stricter type checking
- **Context typing**: `ctx` has type `Ctx` with `deps: DepData[]` for accessing upstream dependencies
- **Nested object support**: Full type safety for complex nested data structures
- **IDE autocomplete**: Get full IntelliSense/autocomplete in VS Code and other TypeScript-aware editors

### Context Structure

Both `filter` and `validator` functions receive a `ctx` parameter with upstream dependency data:

```typescript
interface DepData {
  flow: string;    // Flow identifier
  id: string;      // Node/event identifier
  data: Record<string, any>; // Event data payload
}

interface Ctx {
  deps: DepData[]; // All upstream dependency events
}
```

## Architecture

The SDK follows industry best practices inspired by OpenTelemetry, Sentry, and DataDog:

- **Array-based queue** with configurable size limits
- **Recursive setTimeout** (not setInterval) for reliable timer management
- **Promise-based shutdown** with timeout protection
- **Backend filter evaluation** with access to upstream dependencies via `ctx`
- **Function serialization** for backend execution of both filters and validators
- **Context-aware execution** - both filters and validators receive upstream dependency data

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
