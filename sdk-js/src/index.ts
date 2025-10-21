/**
 * Business-Use JavaScript/TypeScript SDK
 *
 * A lightweight SDK for tracking business events and assertions.
 *
 * @example
 * ```typescript
 * import { initialize, ensure } from 'business-use';
 *
 * // Initialize the SDK
 * initialize({ apiKey: 'your-api-key' });
 *
 * // Track an action (no validator)
 * ensure({
 *   id: 'payment_processed',
 *   flow: 'checkout',
 *   runId: 'run_12345',
 *   data: { amount: 100, currency: 'USD' }
 * });
 *
 * // Track an assertion (with validator)
 * function validateTotal(data: Record<string, any>, ctx: Record<string, any>): boolean {
 *   return data.total > 0;
 * }
 *
 * ensure({
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

export { initialize, ensure, shutdown, act, assert } from './client.js';
export type {
  NodeType,
  ExprEngine,
  Expr,
  EventBatchItem,
  QueuedEvent,
  NodeCondition,
} from './models.js';

// @ts-ignore - package.json is imported at build time
import packageJson from '../package.json';

export const version = packageJson.version;
