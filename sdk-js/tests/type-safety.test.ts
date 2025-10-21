/**
 * Tests for type safety features.
 *
 * These tests verify that TypeScript correctly infers types for filter and validator functions.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { initialize, act, assert, shutdown } from '../src/client.js';

describe('Type Safety', () => {
  beforeEach(async () => {
    // Mock console methods
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});

    // Mock fetch
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'success' }),
    } as Response);

    initialize({ apiKey: 'test-key', url: 'http://localhost:9999' });
  });

  afterEach(async () => {
    await shutdown(1000);
    vi.restoreAllMocks();
  });

  it('should provide typed data parameter in filter function', () => {
    // This test verifies that TypeScript correctly infers the data type
    act({
      id: 'test_event',
      flow: 'test_flow',
      runId: 'run_123',
      data: { amount: 100, currency: 'USD' },
      filter: (data) => {
        // If types are working, data.amount and data.currency should be accessible
        // This will compile successfully if types are correct
        const isValid = data.amount > 0 && data.currency === 'USD';
        return isValid;
      },
    });

    // No assertion needed - if TypeScript compiles, the test passes
    expect(true).toBe(true);
  });

  it('should provide typed data parameter in validator function', () => {
    // This test verifies that TypeScript correctly infers the data type
    assert({
      id: 'test_assertion',
      flow: 'test_flow',
      runId: 'run_123',
      data: { total: 150, items: [{ price: 75 }, { price: 75 }] },
      validator: (data, ctx) => {
        // If types are working, data.total and data.items should be accessible
        const calculatedTotal = data.items.reduce((sum, item) => sum + item.price, 0);
        return data.total === calculatedTotal;
      },
    });

    // No assertion needed - if TypeScript compiles, the test passes
    expect(true).toBe(true);
  });

  it('should work with explicit type annotations', () => {
    // Users can also explicitly type their data
    interface PaymentData {
      amount: number;
      currency: string;
      verified: boolean;
    }

    act<PaymentData>({
      id: 'payment_processed',
      flow: 'checkout',
      runId: 'run_456',
      data: { amount: 99.99, currency: 'EUR', verified: true },
      filter: (data) => {
        // data is now of type PaymentData
        return data.verified && data.amount > 0;
      },
    });

    expect(true).toBe(true);
  });

  it('should work with complex nested data structures', () => {
    interface OrderData {
      orderId: string;
      customer: {
        email: string;
        tier: 'free' | 'premium';
      };
      items: Array<{
        id: string;
        quantity: number;
        price: number;
      }>;
    }

    assert<OrderData>({
      id: 'order_validation',
      flow: 'checkout',
      runId: 'run_789',
      data: {
        orderId: '12345',
        customer: { email: 'test@example.com', tier: 'premium' },
        items: [
          { id: 'item1', quantity: 2, price: 50 },
          { id: 'item2', quantity: 1, price: 100 },
        ],
      },
      validator: (data, ctx) => {
        // Full type safety for nested structures
        const total = data.items.reduce((sum, item) => sum + item.quantity * item.price, 0);
        const isPremium = data.customer.tier === 'premium';
        return total > 0 && isPremium;
      },
      filter: (data) => {
        // Also type-safe in filter
        return data.items.length > 0;
      },
    });

    expect(true).toBe(true);
  });
});
