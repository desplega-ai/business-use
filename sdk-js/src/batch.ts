/**
 * Background batch processor for event ingestion.
 */

import type { EventBatchItem, Expr, QueuedEvent } from './models.js';

/**
 * Logger utility
 */
const log = {
  debug: (msg: string) =>
    console.log(`[business-use] [${new Date().toISOString()}] [DEBUG] ${msg}`),
  info: (msg: string) => console.log(`[business-use] [${new Date().toISOString()}] [INFO] ${msg}`),
  warn: (msg: string) =>
    console.warn(`[business-use] [${new Date().toISOString()}] [WARNING] ${msg}`),
  error: (msg: string) =>
    console.error(`[business-use] [${new Date().toISOString()}] [ERROR] ${msg}`),
};

/**
 * Manages background batching and sending of events to the backend API.
 *
 * Follows OpenTelemetry BatchSpanProcessor pattern:
 * - Array-based queue with FIFO eviction on overflow
 * - Timer-based flushing using recursive setTimeout
 * - Graceful shutdown with timeout protection
 */
export class BatchProcessor {
  private readonly _apiKey: string;
  private readonly _baseUrl: string;
  private readonly _batchSize: number;
  private readonly _batchInterval: number;
  private readonly _maxQueueSize: number;

  // Queue and timer state
  private _queue: QueuedEvent[] = [];
  private _timer: ReturnType<typeof setTimeout> | null = null;
  private _isShuttingDown = false;

  constructor(options: {
    apiKey: string;
    baseUrl: string;
    batchSize: number;
    batchInterval: number;
    maxQueueSize: number;
  }) {
    this._apiKey = options.apiKey;
    this._baseUrl = options.baseUrl.replace(/\/$/, ''); // Remove trailing slash
    this._batchSize = options.batchSize;
    this._batchInterval = options.batchInterval;
    this._maxQueueSize = options.maxQueueSize;

    // Start the timer
    this._maybeStartTimer();

    log.debug('Batch processor started');
  }

  /**
   * Add an event to the processing queue.
   *
   * If the queue is full, the oldest event is dropped (FIFO eviction).
   * This method never throws exceptions.
   */
  enqueue(event: QueuedEvent): void {
    try {
      // Check if queue is full
      if (this._queue.length >= this._maxQueueSize) {
        // Drop oldest event
        this._queue.shift();
        log.warn('Queue overflow: Dropped oldest event');
      }

      // Add new event
      this._queue.push(event);

      // Check if we should flush immediately (size trigger)
      if (this._queue.length >= this._batchSize) {
        this._flushBatch();
      } else {
        // Ensure timer is running for time-based flush
        this._maybeStartTimer();
      }
    } catch (error) {
      log.error(`Failed to enqueue event: ${error}`);
    }
  }

  /**
   * Gracefully shutdown the batch processor.
   *
   * Attempts to flush all remaining events before stopping.
   */
  async shutdown(timeout: number = 5000): Promise<void> {
    log.debug('Shutting down batch processor');
    this._isShuttingDown = true;

    // Clear timer
    if (this._timer) {
      clearTimeout(this._timer);
      this._timer = null;
    }

    // Flush all remaining events with timeout protection
    try {
      await this._flushAllWithTimeout(timeout);
      log.debug('Batch processor shutdown complete');
    } catch (error) {
      log.warn(`Batch processor shutdown timed out: ${error}`);
    }
  }

  /**
   * Start timer if not already running (OpenTelemetry pattern).
   *
   * Only starts timer when:
   * - Queue has events
   * - Queue is below batch size threshold
   * - Timer is not already running
   * - Not shutting down
   */
  private _maybeStartTimer(): void {
    if (
      this._timer === null &&
      this._queue.length > 0 &&
      this._queue.length < this._batchSize &&
      !this._isShuttingDown
    ) {
      // Use recursive setTimeout (not setInterval) for better control
      this._timer = setTimeout(() => {
        this._timer = null;
        this._flushBatch();
        // Reschedule if there are still events
        this._maybeStartTimer();
      }, this._batchInterval);

      // In Node.js, unref() prevents the timer from keeping the process alive
      if (typeof (this._timer as any).unref === 'function') {
        (this._timer as any).unref();
      }
    }
  }

  /**
   * Flush a single batch of events.
   *
   * Evaluates filters, lambdas, and sends to backend.
   */
  private async _flushBatch(): Promise<void> {
    // Clear timer since we're flushing now
    if (this._timer) {
      clearTimeout(this._timer);
      this._timer = null;
    }

    // Extract events from queue
    const eventsToProcess = this._queue.splice(0, this._batchSize);

    if (eventsToProcess.length === 0) {
      return;
    }

    try {
      await this._sendBatch(eventsToProcess);
    } catch (error) {
      log.error(`Failed to send batch: ${error}`);
    }
  }

  /**
   * Flush all remaining events with timeout protection.
   */
  private async _flushAllWithTimeout(timeout: number): Promise<void> {
    const startTime = Date.now();

    while (this._queue.length > 0) {
      // Check timeout
      if (Date.now() - startTime >= timeout) {
        log.warn(`Flush timeout reached, ${this._queue.length} events remaining`);
        break;
      }

      // Flush one batch
      await this._flushBatch();
    }
  }

  /**
   * Process and send a batch of events to the backend.
   */
  private async _sendBatch(batch: QueuedEvent[]): Promise<void> {
    try {
      // Transform queued events to API format
      const items: EventBatchItem[] = [];

      for (const event of batch) {
        try {
          // Evaluate lambdas
          const runId = typeof event.run_id === 'function' ? event.run_id() : event.run_id;
          const depIds =
            event.dep_ids !== undefined
              ? typeof event.dep_ids === 'function'
                ? event.dep_ids()
                : event.dep_ids
              : undefined;
          const conditions =
            event.conditions !== undefined
              ? typeof event.conditions === 'function'
                ? event.conditions()
                : event.conditions
              : undefined;

          // Serialize filter if present and callable (send to backend for evaluation)
          const filterExpr: Expr | undefined =
            event.filter !== undefined && typeof event.filter === 'function'
              ? this._serializeFunction(event.filter)
              : undefined;

          // Serialize validator if present
          const validatorExpr: Expr | undefined =
            event.validator !== undefined ? this._serializeFunction(event.validator) : undefined;

          // Create batch item
          const item: EventBatchItem = {
            flow: event.flow,
            id: event.id,
            run_id: runId,
            type: event.type,
            data: event.data,
            ts: this._getTimestampNs(),
            description: event.description,
            dep_ids: depIds,
            filter: filterExpr,
            validator: validatorExpr,
            conditions: conditions,
            additional_meta: event.additional_meta,
          };

          items.push(item);
        } catch (error) {
          log.error(`Failed to process event ${event.id}: ${error}`);
          continue;
        }
      }

      if (items.length === 0) {
        log.debug('No events to send after filtering');
        return;
      }

      // Send to backend
      await this._postBatch(items);
    } catch (error) {
      log.error(`Failed to send batch: ${error}`);
    }
  }

  /**
   * POST batch to backend API.
   */
  private async _postBatch(items: EventBatchItem[]): Promise<void> {
    try {
      // Remove undefined fields from items
      const payload = items.map((item) => {
        const cleaned: any = {};
        for (const [key, value] of Object.entries(item)) {
          if (value !== undefined) {
            cleaned[key] = value;
          }
        }
        return cleaned;
      });

      // Send request using native fetch (Node 18+)
      const response = await fetch(`${this._baseUrl}/v1/events-batch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Api-Key': this._apiKey,
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        log.debug(`Batch sent successfully: ${items.length} events`);
      } else {
        const text = await response.text();
        log.error(`Batch send failed: HTTP ${response.status} - ${text}`);
      }
    } catch (error) {
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          log.error('Batch send timed out');
        } else {
          log.error(`Network error sending batch: ${error.message}`);
        }
      } else {
        log.error(`Unexpected error sending batch: ${error}`);
      }
    }
  }

  /**
   * Serialize a function to an Expr.
   *
   * Extracts function source code using .toString()
   *
   * For arrow functions: Extracts the expression after '=>'
   * For regular functions: Returns the full function body
   */
  private _serializeFunction(fn: Function): Expr {
    try {
      const source = fn.toString().trim();

      // Handle arrow functions
      if (source.includes('=>')) {
        // Find the arrow operator, being careful to skip strings
        // e.g., "(data, ctx) => data.amount > 0" -> "data.amount > 0"
        let arrowIndex = -1;
        let inString = false;
        let stringChar: string | null = null;

        for (let i = 0; i < source.length - 1; i++) {
          const char = source[i];
          const nextChar = source[i + 1];

          // Track string literals
          if (
            (char === '"' || char === "'" || char === '`') &&
            (i === 0 || source[i - 1] !== '\\')
          ) {
            if (!inString) {
              inString = true;
              stringChar = char;
            } else if (char === stringChar) {
              inString = false;
              stringChar = null;
            }
            continue;
          }

          if (inString) {
            continue;
          }

          // Look for '=>'
          if (char === '=' && nextChar === '>') {
            arrowIndex = i;
            break;
          }
        }

        if (arrowIndex === -1) {
          return { engine: 'js', script: source };
        }

        let body = source.substring(arrowIndex + 2).trim();

        // Remove wrapping braces if present: { return x } -> return x
        if (body.startsWith('{') && body.endsWith('}')) {
          body = body.substring(1, body.length - 1).trim();
        }

        // Remove 'return' statement if present
        if (body.startsWith('return ')) {
          body = body.substring(7).trim();
        }

        // Remove trailing semicolon
        body = body.replace(/;$/, '');

        // Strip outer parentheses if they wrap the entire expression
        // This handles multi-line arrows: (data) => (expr) -> we want just "expr"
        if (body.startsWith('(') && body.endsWith(')')) {
          // Check if these parens wrap the entire expression by tracking depth
          let depth = 0;
          inString = false;
          stringChar = null;
          let wrapsEntire = true;

          for (let i = 0; i < body.length; i++) {
            const char = body[i];

            // Track string literals
            if (
              (char === '"' || char === "'" || char === '`') &&
              (i === 0 || body[i - 1] !== '\\')
            ) {
              if (!inString) {
                inString = true;
                stringChar = char;
              } else if (char === stringChar) {
                inString = false;
                stringChar = null;
              }
              continue;
            }

            if (inString) {
              continue;
            }

            // Track parentheses depth
            if (char === '(') {
              depth++;
            } else if (char === ')') {
              depth--;
              // If depth hits 0 before the last character, parens don't wrap entire expression
              if (depth === 0 && i < body.length - 1) {
                wrapsEntire = false;
                break;
              }
            }
          }

          // If parens wrap the entire expression, remove them
          if (wrapsEntire && depth === 0) {
            body = body.substring(1, body.length - 1).trim();
          }
        }

        return { engine: 'js', script: body };
      }

      // Handle regular functions - return full source
      return { engine: 'js', script: source };
    } catch (error) {
      log.error(`Failed to serialize function: ${error}`);
      // Fallback: use function string representation
      return { engine: 'js', script: fn.toString() };
    }
  }

  /**
   * Get current timestamp in nanoseconds (Unix epoch).
   *
   * Returns Unix epoch time in nanoseconds (milliseconds * 1_000_000).
   * Matches Python SDK's time.time_ns() behavior.
   */
  private _getTimestampNs(): number {
    // Use Date.now() for Unix epoch consistency across Node.js and browsers
    // Date.now() returns milliseconds since Unix epoch (Jan 1, 1970)
    // Convert to nanoseconds: ms * 1_000_000
    return Date.now() * 1_000_000;
  }
}
