/**
 * Multiple flows in one file.
 * Scanner should group nodes by flow.
 */
import { ensure } from 'business-use';

// --- Checkout flow ---

ensure({
  id: 'item_added',
  flow: 'checkout',
  runId: () => sessionId,
  data: { productId: product.id },
});

ensure({
  id: 'checkout_started',
  flow: 'checkout',
  runId: () => sessionId,
  data: { cartSize: cart.items.length },
  depIds: ['item_added'],
});

// --- Refund flow ---

ensure({
  id: 'refund_requested',
  flow: 'refund',
  runId: () => orderId,
  data: { reason: refundReason },
});

ensure({
  id: 'refund_approved',
  flow: 'refund',
  runId: () => orderId,
  data: { amount: refundAmount },
  depIds: ['refund_requested'],
  filter: (data) => data.amount > 0,
});

ensure({
  id: 'refund_processed',
  flow: 'refund',
  runId: () => orderId,
  data: { txId: transaction.id },
  depIds: ['refund_approved'],
  validator: (data, ctx) => data.txId !== null,
  conditions: [{ timeout_ms: 30000 }],
});
