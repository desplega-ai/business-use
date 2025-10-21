/**
 * Business-Use JavaScript/TypeScript SDK
 *
 * A lightweight SDK for tracking business events and assertions.
 *
 * @example
 * ```typescript
 * import { initialize, act, assert } from 'business-use';
 *
 * // Initialize the SDK
 * initialize({ apiKey: 'your-api-key' });
 *
 * // Track an action
 * act({
 *   id: 'payment_processed',
 *   flow: 'checkout',
 *   runId: 'run_12345',
 *   data: { amount: 100, currency: 'USD' }
 * });
 *
 * // Track an assertion
 * function validateTotal(data: Record<string, any>, ctx: Record<string, any>): boolean {
 *   return data.total > 0;
 * }
 *
 * assert({
 *   id: 'order_total_valid',
 *   flow: 'checkout',
 *   runId: 'run_12345',
 *   data: { total: 150 },
 *   validator: validateTotal
 * });
 * ```
 *
 * @module business-use
 */

export { initialize, act, assert, shutdown } from './client.js';
export type { NodeType, ExprEngine, Expr, EventBatchItem, QueuedEvent } from './models.js';

export const version = '0.1.0';
