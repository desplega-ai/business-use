/**
 * Tests for client module.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { initialize, act, assert, shutdown } from '../src/client.js';
import { BatchProcessor } from '../src/batch.js';
import type { QueuedEvent } from '../src/models.js';

describe('Async Function Rejection', () => {
  beforeEach(async () => {
    // Mock console methods to suppress logs during tests
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});

    // Mock fetch for connection check
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'success' }),
    } as Response);

    // Initialize SDK
    initialize({ apiKey: 'test-key', url: 'http://localhost:9999' });
  });

  afterEach(async () => {
    await shutdown(1000);
    vi.restoreAllMocks();
  });

  it('should reject async runId', () => {
    const asyncRunId = async () => 'run_123';

    act({
      id: 'test_event',
      flow: 'test_flow',
      runId: asyncRunId as any, // Cast to bypass TypeScript check
      data: { test: true },
    });

    // Check that an error was logged
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining('runId cannot be an async function')
    );
  });

  it('should reject async filter', () => {
    const asyncFilter = async () => true;

    act({
      id: 'test_event',
      flow: 'test_flow',
      runId: 'run_123',
      data: { test: true },
      filter: asyncFilter as any, // Cast to bypass TypeScript check
    });

    // Check that an error was logged
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining('filter cannot be an async function')
    );
  });

  it('should reject async depIds', () => {
    const asyncDepIds = async () => ['dep1', 'dep2'];

    act({
      id: 'test_event',
      flow: 'test_flow',
      runId: 'run_123',
      data: { test: true },
      depIds: asyncDepIds as any, // Cast to bypass TypeScript check
    });

    // Check that an error was logged
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining('depIds cannot be an async function')
    );
  });

  it('should reject async validator', () => {
    const asyncValidator = async (data: any, ctx: any) => data.test === true;

    assert({
      id: 'test_event',
      flow: 'test_flow',
      runId: 'run_123',
      data: { test: true },
      validator: asyncValidator as any, // Cast to bypass TypeScript check
    });

    // Check that an error was logged
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining('validator cannot be an async function')
    );
  });

  it('should accept sync functions', () => {
    const initialErrorCount = (console.error as any).mock.calls.length;

    const syncRunId = () => 'run_123';
    const syncFilter = () => true;
    const syncDepIds = () => ['dep1'];
    const syncValidator = (data: any, ctx: any) => true;

    act({
      id: 'test_event',
      flow: 'test_flow',
      runId: syncRunId,
      data: { test: true },
      filter: syncFilter,
      depIds: syncDepIds,
    });

    assert({
      id: 'test_assertion',
      flow: 'test_flow',
      runId: 'run_123',
      data: { test: true },
      validator: syncValidator,
    });

    // No additional "async function" errors should be logged
    const asyncErrors = (console.error as any).mock.calls.filter((call: any[]) =>
      call[0]?.includes('cannot be an async function')
    );
    expect(asyncErrors.length).toBe(0);
  });
});

describe('Basic SDK Usage', () => {
  beforeEach(() => {
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(async () => {
    await shutdown(1000);
    vi.restoreAllMocks();
  });

  it('should handle act before initialize as no-op', () => {
    // This should not crash
    expect(() => {
      act({ id: 'test', flow: 'test', runId: 'test', data: {} });
    }).not.toThrow();
  });

  it('should handle assert before initialize as no-op', () => {
    // This should not crash
    expect(() => {
      assert({ id: 'test', flow: 'test', runId: 'test', data: {} });
    }).not.toThrow();
  });

  it('should handle shutdown before initialize as no-op', async () => {
    // This should not crash
    await expect(shutdown()).resolves.toBeUndefined();
  });
});

describe('Environment Variables', () => {
  beforeEach(() => {
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(async () => {
    await shutdown(1000);
    delete process.env.BUSINESS_USE_API_KEY;
    delete process.env.BUSINESS_USE_URL;
    vi.restoreAllMocks();
  });

  it('should initialize with env vars', () => {
    // Set environment variables
    process.env.BUSINESS_USE_API_KEY = 'test-env-key';
    process.env.BUSINESS_USE_URL = 'http://test-env-url:8080';

    // Initialize without parameters - should use env vars
    initialize();

    // Check that info log was called (indicating success)
    expect(console.log).toHaveBeenCalledWith(
      expect.stringContaining('initialized successfully')
    );
  });

  it('should have params override env vars', () => {
    // Set environment variables
    process.env.BUSINESS_USE_API_KEY = 'env-key';
    process.env.BUSINESS_USE_URL = 'http://env-url:8080';

    // Initialize with explicit params - should override env vars
    initialize({ apiKey: 'param-key', url: 'http://param-url:9000' });

    // Check that initialization succeeded
    expect(console.log).toHaveBeenCalledWith(
      expect.stringContaining('initialized successfully')
    );
  });

  it('should fail gracefully without API key', () => {
    // Ensure no API key in environment
    delete process.env.BUSINESS_USE_API_KEY;

    // Try to initialize without apiKey parameter
    initialize();

    // Should log error
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining('API key not provided')
    );
  });
});

describe('act()/assert() timeoutMs and conditions', () => {
  let enqueueSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'success' }),
    } as Response);

    enqueueSpy = vi.spyOn(BatchProcessor.prototype, 'enqueue');

    initialize({ apiKey: 'test-key', url: 'http://localhost:9999' });
  });

  afterEach(async () => {
    await shutdown(1000);
    vi.restoreAllMocks();
  });

  it('act() should translate timeoutMs to conditions', () => {
    act({
      id: 'test_event',
      flow: 'test_flow',
      runId: 'run_123',
      data: { test: true },
      timeoutMs: 5000,
    });

    expect(enqueueSpy).toHaveBeenCalledOnce();
    const event = enqueueSpy.mock.calls[0][0] as QueuedEvent;
    expect(event.conditions).toEqual([{ timeout_ms: 5000 }]);
  });

  it('assert() should translate timeoutMs to conditions', () => {
    assert({
      id: 'test_event',
      flow: 'test_flow',
      runId: 'run_123',
      data: { test: true },
      validator: (data) => data.test === true,
      timeoutMs: 30000,
    });

    expect(enqueueSpy).toHaveBeenCalledOnce();
    const event = enqueueSpy.mock.calls[0][0] as QueuedEvent;
    expect(event.conditions).toEqual([{ timeout_ms: 30000 }]);
  });

  it('explicit conditions should take precedence over timeoutMs', () => {
    const explicitConditions = [{ timeout_ms: 9999 }];

    act({
      id: 'test_event',
      flow: 'test_flow',
      runId: 'run_123',
      data: { test: true },
      timeoutMs: 5000,
      conditions: explicitConditions,
    });

    expect(enqueueSpy).toHaveBeenCalledOnce();
    const event = enqueueSpy.mock.calls[0][0] as QueuedEvent;
    expect(event.conditions).toEqual([{ timeout_ms: 9999 }]);
  });

  it('act() should pass through description and additional_meta', () => {
    act({
      id: 'test_event',
      flow: 'test_flow',
      runId: 'run_123',
      data: { test: true },
      description: 'A test event',
      additional_meta: { source: 'test' },
    });

    expect(enqueueSpy).toHaveBeenCalledOnce();
    const event = enqueueSpy.mock.calls[0][0] as QueuedEvent;
    expect(event.description).toBe('A test event');
    expect(event.additional_meta).toEqual({ source: 'test' });
  });

  it('act() without timeoutMs or conditions should leave conditions undefined', () => {
    act({
      id: 'test_event',
      flow: 'test_flow',
      runId: 'run_123',
      data: { test: true },
    });

    expect(enqueueSpy).toHaveBeenCalledOnce();
    const event = enqueueSpy.mock.calls[0][0] as QueuedEvent;
    expect(event.conditions).toBeUndefined();
  });
});
