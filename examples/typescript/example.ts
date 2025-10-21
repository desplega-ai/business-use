/**
 * Example usage of the Business-Use JavaScript/TypeScript SDK.
 */

import { initialize, ensure, shutdown } from 'business-use';

// Initialize the SDK
console.log('Initializing SDK...');
initialize({
  apiKey: 'secret',
  url: 'http://localhost:13370',
  batchSize: 5, // Small batch for testing
  batchInterval: 2000, // Flush every 2 seconds
});

// Track some business actions
console.log('\nTracking business actions...');

ensure({
  id: 'user_signup',
  flow: 'onboarding',
  runId: 'run_001',
  data: { email: 'alice@example.com', plan: 'premium' },
  description: 'User signed up for premium plan',
});

ensure({
  id: 'email_verified',
  flow: 'onboarding',
  runId: 'run_001',
  data: { email: 'alice@example.com' },
  depIds: ['user_signup'],
  description: 'Email verified successfully',
});

// Track an assertion
console.log('\nTracking business assertions...');

// Example with fully typed assertion - data parameter is type-safe!
ensure({
  id: 'payment_valid',
  flow: 'checkout',
  runId: 'run_002',
  data: { amount: 99.99, currency: 'USD' },
  validator: (data, ctx) => {
    // data.amount and data.currency are available with autocomplete!
    return data.amount > 0 && ['USD', 'EUR', 'GBP'].includes(data.currency);
  },
  depIds: ['email_verified'],
  description: 'Payment validation check',
});

// Example with filter (this will be skipped)
ensure({
  id: 'debug_event',
  flow: 'diagnostics',
  runId: 'run_003',
  data: { debug: true },
  filter: false, // This event will be filtered out
  description: 'This should not be sent',
});

// Example with lambda filter (this will be sent) - with type safety!
ensure({
  id: 'production_event',
  flow: 'diagnostics',
  runId: 'run_003',
  data: { production: true, amount: 100 },
  filter: (data) => data.production && data.amount > 0, // data is typed!
  description: 'This should be sent',
});

// Example with lambda runId
ensure({
  id: 'dynamic_run',
  flow: 'testing',
  runId: () => `dynamic_${Date.now()}`,
  data: { test: true },
  description: 'Using dynamic run ID',
});

// Example with conditions and additional metadata
ensure({
  id: 'critical_payment',
  flow: 'checkout',
  runId: 'run_004',
  data: { amount: 500, currency: 'USD' },
  conditions: [{ timeout_ms: 3000 }],
  additional_meta: { priority: 'high', source: 'api' },
  description: 'High-priority payment with timeout',
});

console.log('\nWaiting for batches to be sent...');
console.log('(Check the logs above for batch processing)');

// Wait a bit for batches to be processed
setTimeout(async () => {
  // Gracefully shutdown
  console.log('\nShutting down SDK...');
  await shutdown(5000);

  console.log('\nDone! Check if the backend received the events.');
  process.exit(0);
}, 3000);
