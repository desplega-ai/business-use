/**
 * Tests for function serialization.
 */

import { describe, it, expect } from 'vitest';

/**
 * Serialize a function to extract its body (mimics BatchProcessor._serializeFunction)
 */
function serializeFunction(fn: Function): { engine: string; script: string } {
  const source = fn.toString().trim();

  // Handle arrow functions
  if (source.includes('=>')) {
    const arrowIndex = source.indexOf('=>');
    let body = source.substring(arrowIndex + 2).trim();

    // Remove wrapping braces if present
    if (body.startsWith('{') && body.endsWith('}')) {
      body = body.substring(1, body.length - 1).trim();
    }

    // Remove 'return' statement if present
    if (body.startsWith('return ')) {
      body = body.substring(7).trim();
    }

    // Remove trailing semicolon
    body = body.replace(/;$/, '');

    return { engine: 'js', script: body };
  }

  // Handle regular functions - return full source
  return { engine: 'js', script: source };
}

describe('Function Serialization', () => {
  it('should serialize simple arrow function', () => {
    const fn = () => true;
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    expect(result.script).toBe('true');
  });

  it('should serialize arrow function with parameters', () => {
    const fn = (data: any) => data.amount > 0;
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    expect(result.script).toContain('data.amount > 0');
  });

  it('should serialize arrow function with multiple parameters', () => {
    const fn = (data: any, ctx: any) => data.amount > ctx.minAmount;
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    expect(result.script).toContain('data.amount > ctx.minAmount');
  });

  it('should serialize arrow function with block body', () => {
    const fn = (data: any) => {
      return data.amount > 0;
    };
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    expect(result.script).toContain('data.amount > 0');
    expect(result.script).not.toContain('return');
  });

  it('should serialize regular function', () => {
    function validatePayment(data: any, ctx: any) {
      return data.amount > 0 && ['USD', 'EUR'].includes(data.currency);
    }
    const result = serializeFunction(validatePayment);

    expect(result.engine).toBe('js');
    expect(result.script).toContain('function validatePayment');
    expect(result.script).toContain('data.amount > 0');
  });

  it('should serialize function expression', () => {
    const validate = function (data: any, ctx: any) {
      return data.total > 0;
    };
    const result = serializeFunction(validate);

    expect(result.engine).toBe('js');
    expect(result.script).toContain('function');
    expect(result.script).toContain('data.total > 0');
  });

  it('should handle complex arrow function', () => {
    const fn = (data: any, ctx: any) => {
      const total = data.items.reduce((sum: number, item: any) => sum + item.price, 0);
      return total === data.total;
    };
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    expect(result.script).toContain('data.items.reduce');
    expect(result.script).toContain('total === data.total');
  });
});
