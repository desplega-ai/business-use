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
    // Find the arrow operator, being careful to skip strings
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
        if ((char === '"' || char === "'" || char === '`') && (i === 0 || body[i - 1] !== '\\')) {
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

  it('should serialize multi-line arrow function with logical OR', () => {
    const fn = (data: any, ctx: any) =>
      !data.isFirstRun || data.allowFix === true;
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    expect(result.script).toContain('!data.isFirstRun');
    expect(result.script).toContain('data.allowFix');
    expect(result.script).toContain('||');
    expect(result.script).not.toMatch(/,\s*$/); // Should not end with comma
  });

  it('should serialize complex multi-line arrow function', () => {
    const fn = (data: any, ctx: any) =>
      data.status === 'active' &&
      data.amount > 0 ||
      data.bypass === true;
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    expect(result.script).toContain('data.status');
    expect(result.script).toContain('data.amount');
    expect(result.script).toContain('data.bypass');
    expect(result.script).toContain('&&');
    expect(result.script).toContain('||');
  });

  it('should serialize multi-line arrow function with parentheses', () => {
    const fn = (data: any, ctx: any) => (
      data.status === 'active' &&
      data.amount > 0 ||
      data.bypass === true
    );
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    expect(result.script).toContain('data.status');
    expect(result.script).toContain('data.amount');
    expect(result.script).toContain('data.bypass');
  });

  it('should serialize multi-line arrow function with .get() and ctx.data access', () => {
    // Regression test for issue where multi-line arrows with string literals
    // in method calls weren't being parsed correctly
    const fn = (data: any, ctx: any) =>
      !data.get('rerun_required', false) && data.run_id === ctx.data.run_id;
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    // Should capture the full expression
    expect(result.script).toContain('!data.get(');
    expect(result.script).toContain('rerun_required');
    expect(result.script).toContain('data.run_id');
    expect(result.script).toContain('ctx.data.run_id');
    expect(result.script).toContain('&&');
    // Should not have trailing comma or parenthesis
    expect(result.script.trim()).not.toMatch(/[,)]$/);
  });

  it('should serialize arrow function with string literals containing special chars', () => {
    // Ensures that => operators inside strings don't break parsing
    const fn = (data: any) =>
      data['key=>with=>arrows'] === 'value=>also=>arrows' &&
      data.status === 'active';
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    expect(result.script).toContain('key=>with=>arrows');
    expect(result.script).toContain('value=>also=>arrows');
    expect(result.script).toContain('data.status');
  });

  it('should serialize arrow function with nested bracket access', () => {
    // CRITICAL TEST: This is the exact pattern that was failing in Python SDK
    // Accessing nested array indices with bracket notation
    // Pattern: ctx.deps[0].data.run_id
    const fn = (data: any, ctx: any) =>
      data.run_id === ctx.deps[0].data.run_id;
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    // Must capture the ENTIRE expression including nested bracket access
    expect(result.script).toBe('data.run_id === ctx.deps[0].data.run_id');
    // Verify we didn't cut off early
    expect(result.script).toContain('ctx.deps[0].data.run_id');
    // Verify balanced brackets
    const openBrackets = (result.script.match(/\[/g) || []).length;
    const closeBrackets = (result.script.match(/\]/g) || []).length;
    expect(openBrackets).toBe(closeBrackets);
  });

  it('should serialize multi-line arrow function with nested bracket access', () => {
    // Test the multi-line version with parentheses wrapping the expression
    const fn = (data: any, ctx: any) => (
      data.run_id === ctx.deps[0].data.run_id
    );
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    // Should capture complete expression
    expect(result.script).toBe('data.run_id === ctx.deps[0].data.run_id');
    // Verify we got the full nested access
    expect(result.script).toContain('ctx.deps[0].data.run_id');
  });

  it('should serialize arrow function with multiple nested bracket accesses', () => {
    // Complex case with multiple nested accesses
    const fn = (data: any, ctx: any) =>
      data.items[0].price === ctx.deps[0].data.items[1].price;
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    expect(result.script).toContain('data.items[0].price');
    expect(result.script).toContain('ctx.deps[0].data.items[1].price');
    // Verify balanced brackets
    const openBrackets = (result.script.match(/\[/g) || []).length;
    const closeBrackets = (result.script.match(/\]/g) || []).length;
    expect(openBrackets).toBe(closeBrackets);
  });

  it('should serialize arrow function with nested bracket access and method call', () => {
    // Test combining bracket access with method calls
    const fn = (data: any, ctx: any) =>
      data.run_id === ctx.deps[0].data.get('run_id', '');
    const result = serializeFunction(fn);

    expect(result.engine).toBe('js');
    expect(result.script).toContain('ctx.deps[0].data.get(');
    // Note: .toString() may convert quotes, so check for either single or double
    expect(result.script).toMatch(/["']run_id["']/);
    expect(result.script).toMatch(/["']run_id["'],\s*["']["']/);  // Empty string arg
    // Verify balanced delimiters
    const openParen = (result.script.match(/\(/g) || []).length;
    const closeParen = (result.script.match(/\)/g) || []).length;
    expect(openParen).toBe(closeParen);
  });
});
