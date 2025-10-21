# Business-Use TypeScript SDK Example

This example demonstrates how to use the Business-Use TypeScript SDK to track business events and assertions with full type safety.

## Prerequisites

- Node.js 18 or higher
- npm, yarn, or pnpm
- Business-Use backend running on `http://localhost:13370`

## Installation

The example uses the local Business-Use SDK from `../../sdk-js`.

### Using npm:

```bash
# Install dependencies (automatically links local SDK)
npm install

# Run the example
npm start

# Run with auto-reload (watch mode)
npm run dev
```

### Using pnpm:

```bash
# Install dependencies (automatically links local SDK)
pnpm install

# Run the example
pnpm start

# Run with auto-reload (watch mode)
pnpm dev
```

### Using yarn:

```bash
# Install dependencies (automatically links local SDK)
yarn install

# Run the example
yarn start

# Run with auto-reload (watch mode)
yarn dev
```

> **Note**: If you've published the SDK to npm, you can change the dependency in `package.json` to `"business-use": "^0.1.0"`

## What This Example Does

1. **Initializes** the SDK with API key and backend URL
2. **Tracks actions** - User signup and email verification
3. **Tracks assertions** - Payment validation with a typed validator function
4. **Demonstrates filters** - Client-side and server-side filtering with type safety
5. **Shows lambdas** - Dynamic run IDs and typed filter functions
6. **Uses conditions** - Timeout constraints on events
7. **Adds metadata** - Additional context with `additional_meta`
8. **Graceful shutdown** - Ensures all events are flushed before exit

## Type Safety Features

This example showcases TypeScript's type inference:

```typescript
// The data parameter is fully typed based on the data object!
ensure({
  data: { amount: 99.99, currency: 'USD' },
  validator: (data, ctx) => {
    // TypeScript knows data.amount and data.currency exist!
    return data.amount > 0 && ['USD', 'EUR', 'GBP'].includes(data.currency);
  },
});

// Filter functions are also typed
ensure({
  data: { production: true, amount: 100 },
  filter: (data) => data.production && data.amount > 0, // Full autocomplete!
});
```

## Expected Output

You should see console logs showing:
- SDK initialization
- Events being queued
- Batches being sent to the backend
- Successful batch delivery confirmation

## Configuration

Edit the `initialize()` call in `example.ts` to customize:
- `apiKey`: Your Business-Use API key
- `url`: Backend URL (default: http://localhost:13370)
- `batchSize`: Number of events per batch
- `batchInterval`: Milliseconds between batch flushes
