/**
 * Example usage of the Business-Use JavaScript/TypeScript SDK.
 *
 * This example demonstrates a complete e-commerce checkout flow with:
 * - Multiple dependent nodes
 * - Filter functions to skip events conditionally
 * - Validator functions to assert business rules
 * - CEL (Common Expression Language) for server-side validation
 * - Timeout conditions between steps
 */

import { initialize, act, assert, shutdown } from 'business-use';

// Initialize the SDK
console.log('Initializing SDK...');
initialize({
  apiKey: 'secret',
  url: 'http://localhost:13370',
  batchSize: 10,
  batchInterval: 2000, // Flush every 2 seconds
});

console.log('\n' + '='.repeat(70));
console.log('EXAMPLE: E-Commerce Checkout Flow with CEL Validation');
console.log('='.repeat(70));

// Simulate a checkout session
const sessionId = `checkout_${Date.now()}`;
console.log(`\nSession ID: ${sessionId}`);

// Define TypeScript interfaces for type safety
interface CartData {
  cart_id: string;
  items: Array<{ sku: string; price: number; quantity: number }>;
  total: number;
  currency: string;
  timestamp: string;
}

interface InventoryData {
  cart_id: string;
  reservation_id: string;
  items_reserved: number;
  total: number;
}

interface PaymentData {
  cart_id: string;
  payment_id: string;
  amount: number;
  currency: string;
  status: string;
  payment_method: string;
  last4: string;
}

interface OrderData {
  order_id: string;
  cart_id: string;
  customer_email: string;
  total: number;
  currency: string;
  status: string;
  items_count: number;
  shipping_address: {
    street: string;
    city: string;
    state: string;
    zip: string;
  };
}

// Step 1: Cart Created (action node)
// This tracks when a user creates their shopping cart
console.log('\n[1/4] Creating shopping cart...');
act<CartData>({
  id: 'cart_created',
  flow: 'checkout',
  runId: sessionId,
  data: {
    cart_id: 'cart_12345',
    items: [
      { sku: 'LAPTOP-001', price: 999.99, quantity: 1 },
      { sku: 'MOUSE-042', price: 29.99, quantity: 2 },
    ],
    total: 1059.97,
    currency: 'USD',
    timestamp: new Date().toISOString(),
  },
});

// Step 2: Inventory Reserved (action node with dependency and filter)
// Only reserve inventory if cart total is above $50
console.log('\n[2/4] Reserving inventory...');
act<InventoryData>({
  id: 'inventory_reserved',
  flow: 'checkout',
  runId: sessionId,
  data: {
    cart_id: 'cart_12345',
    reservation_id: 'res_98765',
    items_reserved: 3,
    total: 1059.97,
  },
  depIds: ['cart_created'], // Must happen after cart creation
  filter: (data) => data.total > 50, // Only process if total > $50 (client-side)
  timeoutMs: 5000, // Must happen within 5s of cart creation
});

// Step 3: Payment Processed (assertion node with CEL validation)
// This validates payment using CEL expressions on the backend
console.log('\n[3/4] Processing payment with CEL validation...');
assert<PaymentData>({
  id: 'payment_processed',
  flow: 'checkout',
  runId: sessionId,
  data: {
    cart_id: 'cart_12345',
    payment_id: 'pay_abc123',
    amount: 1059.97,
    currency: 'USD',
    status: 'success',
    payment_method: 'credit_card',
    last4: '4242',
  },
  // CEL expression for server-side validation
  // This will be evaluated on the backend
  validator: {
    engine: 'cel',
    script: `
      data.status == 'success' &&
      data.amount > 0 &&
      data.currency in ['USD', 'EUR', 'GBP'] &&
      data.payment_method in ['credit_card', 'debit_card', 'paypal']
    `,
  } as any, // Type assertion for CEL validator
  depIds: ['inventory_reserved'], // Must happen after inventory reservation
  timeoutMs: 10000, // 10s timeout from inventory
});

// Step 4: Order Confirmed (assertion node with JavaScript validation)
// Final step that validates the entire order state using a JavaScript function
console.log('\n[4/4] Confirming order with JavaScript validation...');
assert<OrderData>({
  id: 'order_confirmed',
  flow: 'checkout',
  runId: sessionId,
  data: {
    order_id: 'ord_xyz789',
    cart_id: 'cart_12345',
    customer_email: 'alice@example.com',
    total: 1059.97,
    currency: 'USD',
    status: 'confirmed',
    items_count: 3,
    shipping_address: {
      street: '123 Main St',
      city: 'San Francisco',
      state: 'CA',
      zip: '94102',
    },
  },
  // JavaScript function validator (type-safe!)
  validator: (data, ctx) => {
    console.log('  Validating order confirmation...');

    // Check all required fields exist
    const requiredFields: (keyof OrderData)[] = [
      'order_id',
      'customer_email',
      'total',
      'status',
    ];

    for (const field of requiredFields) {
      if (!(field in data)) {
        console.log(`  ❌ Missing required field: ${field}`);
        return false;
      }
    }

    // Validate email format (simple check)
    if (!data.customer_email?.includes('@')) {
      console.log(`  ❌ Invalid email: ${data.customer_email}`);
      return false;
    }

    // Validate order status
    if (data.status !== 'confirmed') {
      console.log(`  ❌ Order not confirmed: ${data.status}`);
      return false;
    }

    // Validate shipping address is complete
    const addressFields = ['street', 'city', 'state', 'zip'];
    for (const field of addressFields) {
      if (!data.shipping_address?.[field as keyof typeof data.shipping_address]) {
        console.log(`  ❌ Missing shipping address field: ${field}`);
        return false;
      }
    }

    console.log(`  ✅ Order confirmed: ${data.order_id} for ${data.customer_email}`);
    return true;
  },
  depIds: ['payment_processed'], // Must happen after payment
  timeoutMs: 3000, // 3s timeout from payment
});

console.log('\n' + '='.repeat(70));
console.log('All events tracked! Flow summary:');
console.log('  cart_created → inventory_reserved → payment_processed → order_confirmed');
console.log('='.repeat(70));

console.log('\nWaiting for batches to be sent...');
console.log('(Check the logs above for batch processing)');

// Wait a bit for batches to be processed
setTimeout(async () => {
  // Gracefully shutdown
  console.log('\nShutting down SDK...');
  await shutdown(5000);

  console.log('\n✅ Done! Check the backend to evaluate the flow.');
  console.log(`   Run: cd core && uv run cli eval-run ${sessionId} checkout --verbose`);

  process.exit(0);
}, 3000);
