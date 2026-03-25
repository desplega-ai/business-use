/**
 * Basic flow — happy path. All literal values, direct imports.
 * Scanner should extract all 3 nodes perfectly.
 */
import { ensure } from 'business-use';

// Root node — no dependencies
ensure({
  id: 'cart_created',
  flow: 'checkout',
  runId: () => getRunId(),
  data: { items: cart.items },
  description: 'Shopping cart was created',
});

// Depends on cart_created
ensure({
  id: 'payment_processed',
  flow: 'checkout',
  runId: () => getRunId(),
  data: { amount: payment.amount, currency: 'USD' },
  depIds: ['cart_created'],
  description: 'Payment was processed successfully',
  conditions: [{ timeout_ms: 5000 }],
});

// Assert node — has validator
ensure({
  id: 'order_total_matches',
  flow: 'checkout',
  runId: () => getRunId(),
  data: { total: order.total },
  depIds: ['cart_created', 'payment_processed'],
  validator: (data, ctx) => {
    return data.total === ctx.deps.reduce((sum, dep) => sum + dep.data.amount, 0);
  },
  description: 'Order total matches sum of payments',
});
