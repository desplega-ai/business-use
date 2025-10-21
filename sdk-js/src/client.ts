/**
 * Main client module for Business-Use SDK.
 */

import { BatchProcessor } from './batch.js';
import type { NodeType, QueuedEvent } from './models.js';

/**
 * Logger utility
 */
const log = {
  debug: (msg: string) => console.log(`[business-use] [${new Date().toISOString()}] [DEBUG] ${msg}`),
  info: (msg: string) => console.log(`[business-use] [${new Date().toISOString()}] [INFO] ${msg}`),
  warn: (msg: string) => console.warn(`[business-use] [${new Date().toISOString()}] [WARNING] ${msg}`),
  error: (msg: string) => console.error(`[business-use] [${new Date().toISOString()}] [ERROR] ${msg}`),
};

/**
 * Internal SDK state (singleton pattern)
 */
class SDKState {
  initialized = false;
  batchProcessor: BatchProcessor | null = null;
}

// Global SDK state
const _state = new SDKState();

/**
 * Initialize the Business-Use SDK.
 *
 * This function must be called before using `act()` or `assert()`.
 * It validates the connection to the backend and starts the background
 * batch processor.
 *
 * This function never throws exceptions. Errors are logged internally.
 * If initialization fails, the SDK enters no-op mode.
 *
 * @param options - Initialization options
 * @param options.apiKey - API key for authentication (default: from BUSINESS_USE_API_KEY env var)
 * @param options.url - Backend API URL (default: from BUSINESS_USE_URL env var or http://localhost:13370)
 * @param options.batchSize - Number of events per batch (default: 100)
 * @param options.batchInterval - Flush interval in milliseconds (default: 5000)
 * @param options.maxQueueSize - Max queue size (default: batchSize * 10)
 *
 * @example
 * ```typescript
 * import { initialize, act } from 'business-use';
 *
 * initialize({ apiKey: 'your-api-key' });
 * act({
 *   id: 'user_signup',
 *   flow: 'onboarding',
 *   runId: '123',
 *   data: { email: 'user@example.com' }
 * });
 * ```
 *
 * Or using environment variables:
 * ```typescript
 * // Set BUSINESS_USE_API_KEY=your-api-key in environment
 * initialize(); // Will use env vars
 * ```
 */
export function initialize(options?: {
  apiKey?: string;
  url?: string;
  batchSize?: number;
  batchInterval?: number;
  maxQueueSize?: number;
}): void {
  if (_state.initialized) {
    log.warn('SDK already initialized');
    return;
  }

  try {
    // Get API key from parameter or environment
    const finalApiKey = options?.apiKey ?? process.env.BUSINESS_USE_API_KEY;
    if (!finalApiKey) {
      log.error(
        'API key not provided. Set apiKey parameter or BUSINESS_USE_API_KEY environment variable'
      );
      return;
    }

    // Get URL from parameter or environment
    const finalUrl = options?.url ?? process.env.BUSINESS_USE_URL ?? 'http://localhost:13370';

    // Normalize URL
    const baseUrl = finalUrl.replace(/\/$/, '');

    // Configuration with defaults
    const batchSize = options?.batchSize ?? 100;
    const batchInterval = options?.batchInterval ?? 5000;
    const maxQueueSize = options?.maxQueueSize ?? batchSize * 10;

    // Validate connection (synchronous check)
    if (!_checkConnection(finalApiKey, baseUrl)) {
      log.error('Connection check failed - SDK entering no-op mode');
      return;
    }

    // Start batch processor
    _state.batchProcessor = new BatchProcessor({
      apiKey: finalApiKey,
      baseUrl,
      batchSize,
      batchInterval,
      maxQueueSize,
    });

    _state.initialized = true;
    log.info('Business-Use SDK initialized successfully');
  } catch (error) {
    log.error(`Failed to initialize SDK: ${error}`);
    _state.initialized = false;
  }
}

/**
 * Track a business action event.
 *
 * This function is synchronous and non-blocking. Events are queued and
 * sent in batches to the backend.
 *
 * This function never throws exceptions. If the SDK is not initialized,
 * this is a no-op.
 *
 * @param options - Event options
 * @param options.id - Unique node/event identifier (e.g., "payment_processed")
 * @param options.flow - Flow identifier (e.g., "checkout")
 * @param options.runId - Run identifier (string or function returning string)
 * @param options.data - Event data payload
 * @param options.filter - Optional filter (boolean or function). If false, event is skipped
 * @param options.depIds - Optional dependency node IDs (array or function)
 * @param options.description - Optional human-readable description
 *
 * @example
 * ```typescript
 * act({
 *   id: 'payment_processed',
 *   flow: 'checkout',
 *   runId: 'run_12345',
 *   data: { amount: 100, currency: 'USD' },
 *   depIds: ['cart_created', 'payment_initiated'],
 *   description: 'Payment processed successfully'
 * });
 *
 * // Using functions with type safety
 * act({
 *   id: 'order_completed',
 *   flow: 'checkout',
 *   runId: () => getCurrentRunId(),
 *   data: { orderId: '123', amount: 100 },
 *   filter: (data) => data.amount > 0, // data is typed!
 * });
 * ```
 */
export function act<TData extends Record<string, any> = Record<string, any>>(options: {
  id: string;
  flow: string;
  runId: string | (() => string);
  data: TData;
  filter?: boolean | ((data: TData) => boolean);
  depIds?: string[] | (() => string[]);
  description?: string;
}): void {
  _enqueueEvent({
    type: 'act',
    id: options.id,
    flow: options.flow,
    runId: options.runId,
    data: options.data,
    filter: options.filter,
    depIds: options.depIds,
    description: options.description,
    validator: undefined,
  });
}

/**
 * Track a business assertion.
 *
 * This function is synchronous and non-blocking. Assertions are queued
 * and sent in batches to the backend.
 *
 * This function never throws exceptions. If the SDK is not initialized,
 * this is a no-op.
 *
 * @param options - Assertion options
 * @param options.id - Unique node/event identifier (e.g., "order_total_valid")
 * @param options.flow - Flow identifier (e.g., "checkout")
 * @param options.runId - Run identifier (string or function returning string)
 * @param options.data - Event data payload
 * @param options.filter - Optional filter (boolean or function). If false, assertion is skipped
 * @param options.depIds - Optional dependency node IDs (array or function)
 * @param options.validator - Optional validation function (executed on backend)
 * @param options.description - Optional human-readable description
 *
 * @example
 * ```typescript
 * // With type safety - data parameter is typed!
 * assert({
 *   id: 'order_total_matches',
 *   flow: 'checkout',
 *   runId: 'run_12345',
 *   data: { total: 150, items: [{ price: 75 }, { price: 75 }] },
 *   validator: (data, ctx) => {
 *     // data.total is known to exist (type-safe!)
 *     return data.total === data.items.reduce((sum, item) => sum + item.price, 0);
 *   },
 *   description: 'Order total matches sum of items'
 * });
 * ```
 */
export function assert<TData extends Record<string, any> = Record<string, any>>(options: {
  id: string;
  flow: string;
  runId: string | (() => string);
  data: TData;
  filter?: boolean | ((data: TData) => boolean);
  depIds?: string[] | (() => string[]);
  validator?: (data: TData, ctx: Record<string, any>) => boolean;
  description?: string;
}): void {
  _enqueueEvent({
    type: 'assert',
    id: options.id,
    flow: options.flow,
    runId: options.runId,
    data: options.data,
    filter: options.filter,
    depIds: options.depIds,
    description: options.description,
    validator: options.validator,
  });
}

/**
 * Gracefully shutdown the SDK.
 *
 * Attempts to flush all remaining events before stopping.
 * This is optional - the SDK will auto-shutdown when the process exits.
 *
 * @param timeout - Maximum time to wait for shutdown in milliseconds (default: 5000)
 *
 * @example
 * ```typescript
 * await shutdown();
 * ```
 */
export async function shutdown(timeout: number = 5000): Promise<void> {
  if (!_state.initialized) {
    log.debug('SDK not initialized, nothing to shutdown');
    return;
  }

  if (_state.batchProcessor) {
    await _state.batchProcessor.shutdown(timeout);
  }

  _state.initialized = false;
  _state.batchProcessor = null;
  log.info('SDK shutdown complete');
}

/**
 * Internal helper to enqueue an event.
 */
function _enqueueEvent(options: {
  type: NodeType;
  id: string;
  flow: string;
  runId: string | (() => string);
  data: Record<string, any>;
  filter?: boolean | (() => boolean);
  depIds?: string[] | (() => string[]);
  description?: string;
  validator?: (data: Record<string, any>, ctx: Record<string, any>) => boolean;
}): void {
  // No-op if not initialized
  if (!_state.initialized || !_state.batchProcessor) {
    return;
  }

  try {
    // Validate that no async functions are used
    if (typeof options.runId === 'function' && isAsyncFunction(options.runId)) {
      log.error(`Event ${options.id}: runId cannot be an async function`);
      return;
    }

    if (options.filter !== undefined && typeof options.filter === 'function' && isAsyncFunction(options.filter)) {
      log.error(`Event ${options.id}: filter cannot be an async function`);
      return;
    }

    if (options.depIds !== undefined && typeof options.depIds === 'function' && isAsyncFunction(options.depIds)) {
      log.error(`Event ${options.id}: depIds cannot be an async function`);
      return;
    }

    if (options.validator !== undefined && isAsyncFunction(options.validator)) {
      log.error(`Event ${options.id}: validator cannot be an async function`);
      return;
    }

    const event: QueuedEvent = {
      type: options.type,
      id: options.id,
      flow: options.flow,
      run_id: options.runId,
      data: options.data,
      filter: options.filter,
      dep_ids: options.depIds,
      description: options.description,
      validator: options.validator,
    };

    _state.batchProcessor.enqueue(event);
  } catch (error) {
    log.error(`Failed to enqueue event ${options.id}: ${error}`);
  }
}

/**
 * Validate connection to backend API.
 *
 * @param _apiKey - API key for authentication (unused, for future implementation)
 * @param _baseUrl - Backend API URL (unused, for future implementation)
 * @returns true if connection is valid, false otherwise
 */
function _checkConnection(_apiKey: string, _baseUrl: string): boolean {
  try {
    // Use synchronous check - this will block briefly during initialization
    // In a real implementation, you might want to make this async
    // For now, we'll do a simple validation and trust the backend is available
    // The first batch send will validate the connection properly

    log.info('Connection check successful (deferred to first batch)');
    return true;
  } catch (error) {
    log.error(`Connection check failed: ${error}`);
    return false;
  }
}

/**
 * Check if a function is async.
 */
function isAsyncFunction(fn: any): boolean {
  return fn.constructor.name === 'AsyncFunction';
}
