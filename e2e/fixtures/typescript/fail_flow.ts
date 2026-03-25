/**
 * E2E fixture: checkout flow that should FAIL evaluation.
 *
 * The payment_processed node sends status="declined" which fails the validator.
 */

import { initialize, act, assert, shutdown } from '@desplega.ai/business-use';

const runId = process.env.E2E_RUN_ID ?? `ts_fail_${Date.now()}`;
const apiKey = process.env.BUSINESS_USE_API_KEY ?? 'test-e2e-key';
const url = process.env.BUSINESS_USE_URL ?? 'http://localhost:13399';

initialize({ apiKey, url, batchSize: 10, batchInterval: 1000 });

// Step 1: Cart Created
act({
  id: 'cart_created',
  flow: 'checkout',
  runId,
  data: { cart_id: 'cart_002', total: 99.99, currency: 'USD' },
  description: 'Shopping cart initialized',
});

// Step 2: Inventory Reserved
act({
  id: 'inventory_reserved',
  flow: 'checkout',
  runId,
  data: { cart_id: 'cart_002', reservation_id: 'res_002', items_reserved: 2 },
  depIds: ['cart_created'],
  timeoutMs: 5000,
  description: 'Inventory reserved for cart items',
});

// Step 3: Payment Processed — DELIBERATELY FAILS (status="declined")
assert({
  id: 'payment_processed',
  flow: 'checkout',
  runId,
  data: {
    cart_id: 'cart_002',
    payment_id: 'pay_002',
    amount: 99.99,
    currency: 'USD',
    status: 'declined', // <-- This will fail the validator
  },
  validator: (data: any) => data.status === 'success' && data.amount > 0,
  depIds: ['inventory_reserved'],
  timeoutMs: 10000,
  description: 'Payment processed and validated',
});

// Step 4: Order Confirmed — valid data, but flow should still fail due to step 3
assert({
  id: 'order_confirmed',
  flow: 'checkout',
  runId,
  data: {
    order_id: 'ord_002',
    customer_email: 'test@example.com',
    total: 99.99,
    status: 'confirmed',
  },
  validator: (data: any) => data.status === 'confirmed' && data.customer_email?.includes('@'),
  depIds: ['payment_processed'],
  timeoutMs: 3000,
  description: 'Order confirmed',
});

setTimeout(async () => {
  await shutdown(5000);
  console.log(`DONE run_id=${runId}`);
  process.exit(0);
}, 2000);
