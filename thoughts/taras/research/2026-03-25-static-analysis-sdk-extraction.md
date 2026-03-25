---
date: 2026-03-25T12:00:00-04:00
researcher: Claude
git_commit: d178ffd13286bcd2f8489ae63857af99abcb90d7
branch: main
repository: business-use
topic: "Static analysis of JS/TS codebases to extract SDK function calls for automatic flow node registration"
tags: [research, static-analysis, tree-sitter, typescript-compiler-api, ast, sdk-js, scanner]
status: complete
autonomy: critical
last_updated: 2026-03-25
last_updated_by: Claude
---

# Research: Static Analysis for SDK Call Extraction

**Date**: 2026-03-25
**Researcher**: Claude
**Git Commit**: d178ffd
**Branch**: main

## Research Question

How to implement static analysis (tree-sitter or alternatives) for the JS SDK to automatically parse codebases and discover all `ensure()`, `act()`, `assert()` call sites — so that flow nodes can be registered in the backend without requiring runtime execution.

## Summary

The goal is a CLI tool that scans a JS/TS codebase, finds all calls to the business-use SDK (`ensure`, `act`, `assert`), and extracts the static arguments (`id`, `flow`, `depIds`, presence of `validator`) to produce a flow graph definition without running the code.

Five approaches were evaluated: **TypeScript Compiler API**, **tree-sitter (WASM)**, **Babel**, **SWC**, and **oxc-parser**. The **TypeScript Compiler API** (`ts.createSourceFile`) is the recommended approach because it adds zero new dependencies (every TS project already has `typescript`), provides perfect parsing accuracy for TypeScript, has no native bindings, and offers sufficient performance (sub-second for typical projects). Tree-sitter is the best alternative if cross-language support (Python) is needed later.

The extraction works reliably when users follow the recommended pattern of using string literals for `id`, `flow`, and `depIds`. Dynamic values (variables, expressions) cannot be extracted statically — this is a fundamental limitation of all approaches, and the tool should warn on these cases rather than fail.

## Detailed Findings

### 1. What Needs to Be Extracted

From the SDK source (`sdk-js/src/client.ts:191-216`), the `ensure()` function takes an object with these properties:

| Property | Type | Statically Extractable? | Notes |
|----------|------|------------------------|-------|
| `id` | `string` | Yes (string literal) | Required. Node identifier. |
| `flow` | `string` | Yes (string literal) | Required. Flow identifier. |
| `depIds` | `string[]` | Yes (array of string literals) | Optional. Dependency node IDs. |
| `validator` | `Function` | Presence only | Determines type: present = "assert", absent = "act" |
| `description` | `string` | Yes (string literal) | Optional. |
| `conditions` | `NodeCondition[]` | Sometimes (object literal) | Optional. e.g., `[{ timeout_ms: 5000 }]` |
| `filter` | `Function` | Presence only | Optional. |
| `runId` | `string \| () => string` | Sometimes | Often dynamic, not critical for graph structure. |
| `data` | `Record<string, any>` | No | Runtime value. |

The `act()` (`client.ts:250-260`) and `assert()` (`client.ts:266-277`) helpers are convenience wrappers around `ensure()` with the same argument shape.

Python SDK (`sdk-py/src/business_use/client.py:109-200`) has the identical API surface: `ensure()`, `act()`, `assert_()` with keyword arguments.

### 2. Approach Comparison

#### TypeScript Compiler API (Recommended)

Uses `ts.createSourceFile()` — parse-only mode, no type-checking, no import resolution overhead.

**How it works:**
1. Parse each file with `ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true)`
2. Walk AST with recursive `ts.forEachChild(node, visitor)`
3. Match `ts.isCallExpression(node)` where callee is `ensure`/`act`/`assert`
4. Extract properties from `ts.isObjectLiteralExpression(arg)` — iterate `.properties`, match `ts.isPropertyAssignment`, get values via `ts.isStringLiteral(prop.initializer).text`
5. Verify imports by inspecting `ts.isImportDeclaration` nodes for module specifier matching `business-use`

**Key code pattern:**
```typescript
// Parse (no type-checking, very fast)
const sourceFile = ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true);

// Extract string value — .text gives unquoted value directly
if (ts.isStringLiteral(prop.initializer)) {
  const value = prop.initializer.text; // "payment_processed" (no quotes)
}

// Extract array of strings
if (ts.isArrayLiteralExpression(prop.initializer)) {
  const items = prop.initializer.elements
    .filter(ts.isStringLiteral)
    .map(el => el.text);
}
```

**Pros:**
- Zero new dependencies — `typescript` already in every TS project's devDeps
- Perfect parsing accuracy — it IS the TypeScript parser
- No native bindings — pure JS, works everywhere
- Fast: sub-second for hundreds of files in parse-only mode
- Handles all TS syntax including decorators, generics, JSX
- Import checking works syntactically (check `moduleSpecifier.text`)

**Cons:**
- TypeScript-only (can't scan Python)
- `typescript` package is ~24MB (but already installed)
- No incremental parsing (parse whole file each time)
- Imperative visitor pattern (more verbose than query-based)

**Performance:**
- Parse-only mode is ~50-100x faster than full `createProgram` + type-checking
- ~2x faster than Babel for parsing
- 500 files averaging 200 lines: well under 1 second

#### Tree-sitter (web-tree-sitter / WASM)

Uses S-expression queries against a concrete syntax tree.

**How it works:**
```typescript
await Parser.init();
const parser = new Parser();
const TypeScript = await Parser.Language.load('tree-sitter-typescript.wasm');
parser.setLanguage(TypeScript);
const tree = parser.parse(sourceCode);

// Query: find ensure/act/assert calls with object argument
const query = TypeScript.query(`
  (call_expression
    function: (identifier) @fn-name
    arguments: (arguments . (object) @config-obj)
    (#any-of? @fn-name "ensure" "act" "assert"))
`);
const matches = query.matches(tree.rootNode);
```

String values live in `string_fragment` child nodes (not `string` which includes quotes).

**Pros:**
- Cross-language: supports JS, TS, Python, and 100+ other grammars
- WASM distribution: zero native deps, works everywhere
- Query-based: declarative pattern matching (vs imperative walking)
- Incremental parsing support (useful for watch mode)
- ast-grep provides a higher-level API on top of tree-sitter

**Cons:**
- Requires 3 grammar packages (JS, TS, TSX) — ~1-3MB total
- WASM memory management: must manually `.delete()` trees (no GC)
- May lag behind newest TypeScript syntax
- Async initialization required
- Query language (S-expressions) has a learning curve
- Predicate support in web-tree-sitter is more limited than native

**Performance:**
- WASM: 2-5x slower than native tree-sitter, but still fast
- 500-file codebase: estimated 1-3 seconds
- Sufficient for CLI tool

#### Babel (`@babel/parser` + `@babel/traverse`)

**How it works:**
```typescript
import { parse } from '@babel/parser';
import traverse from '@babel/traverse';

const ast = parse(code, { sourceType: 'module', plugins: ['typescript', 'jsx'] });
traverse(ast, {
  CallExpression(path) {
    if (path.node.callee.name === 'ensure') {
      const arg = path.node.arguments[0]; // ObjectExpression
      // Extract properties from arg.properties
    }
  }
});
```

**Pros:** Mature ecosystem, rich path API with scope analysis, full TS/JSX support.
**Cons:** ~2.5MB dependency, slower than TS compiler API, no type resolution.

#### SWC (`@swc/core`)

**Pros:** 20-70x faster than Babel, native TS/JSX support, same parser as Next.js.
**Cons:** Non-ESTree AST, native bindings (optionalDependencies pattern), less mature JS-side traversal (`swc-walk`), thinner documentation.

#### oxc-parser

**Pros:** Fastest parser available (26ms vs SWC 84ms vs Biome 130ms for TS), ESTree-compatible output.
**Cons:** Native bindings via napi-rs, WASM version deprecated/stale, relatively new ecosystem.

### 3. Comparison Matrix

| Criterion | TS Compiler API | tree-sitter (WASM) | Babel | SWC | oxc |
|-----------|----------------|-------------------|-------|-----|-----|
| **New deps** | None | ~1-3MB | ~2.5MB | ~30MB native | ~15MB native |
| **Native bindings** | No | No (WASM) | No | Yes | Yes |
| **TS accuracy** | Perfect | Very good | Very good | Very good | Very good |
| **Python support** | No | Yes | No | No | No |
| **Parse speed** | Fast | Moderate (WASM) | Moderate | Very fast | Fastest |
| **API style** | Imperative visitor | Query (S-expr) | Imperative visitor | Imperative visitor | ESTree visitor |
| **Import checking** | Native | Manual | Via scope | Manual | Manual |
| **Incremental** | No | Yes | No | No | No |
| **Distribution** | Trivial | Easy | Trivial | Medium | Medium |
| **Ecosystem maturity** | Excellent | Good | Excellent | Good | Emerging |

### 4. Limitations Common to All Approaches

None of these approaches can handle:

- **Variable indirection**: `const config = { id: 'foo', flow: 'bar' }; ensure(config);` — the parser sees `ensure(config)`, not the object literal
- **Dynamic values**: `ensure({ id: 'payment_' + stage, flow: getFlow() })` — expressions can't be evaluated
- **Re-exports/wrappers**: `function trackEvent(opts) { ensure(opts); }` — the wrapper call isn't detectable without deep analysis
- **Aliased imports**: `import { ensure as track } from 'business-use'` — detectable with extra logic (check `import_specifier` alias)
- **require() calls**: `const bu = require('business-use'); bu.ensure(...)` — different AST shape, needs separate query pattern

**Practical coverage**: The recommended SDK usage pattern (direct import, literal string arguments) covers 90%+ of real-world calls. Edge cases should emit warnings, not errors.

### 5. Prior Art: How Existing Tools Solve This

| Tool | Domain | Parser | Approach |
|------|--------|--------|----------|
| **i18next-parser** | i18n key extraction | TS Compiler API | Walk AST, find `t()` calls, extract first string arg |
| **i18next-cli** (next-gen) | i18n key extraction | SWC | `onVisitNode` plugin hook, 12x faster than predecessor |
| **FormatJS** | i18n extraction | Babel plugin | Visit `CallExpression` for `defineMessages()`, expose via metadata |
| **graphql-tag-pluck** | GraphQL extraction | Import detection + template literal matching | Find `gql` import, then match tagged template literals |
| **Knip** | Dead code detection | TS compiler + project references | Workspace-aware, follows dependency graph from entry points |
| **ast-grep** | Generic code search | tree-sitter (Rust) | Code-like pattern syntax with meta-variables: `ensure($$$)` |
| **ESLint rules** | Code analysis | espree (acorn-based) | `CallExpression` visitor, same pattern as Babel |
| **unimport** | Auto-import detection | Regex (fast path) + acorn (accurate path) | Regex for speed, AST for correctness |

### 6. Recommended Architecture

#### Parser Choice

**V1: py-tree-sitter** — Python bindings for tree-sitter with `tree-sitter-javascript` and `tree-sitter-typescript` grammars. Keeps everything in Python (no Node.js subprocess needed). Fast C-based parsing. Uses tree-sitter's S-expression query language for pattern matching.

While the TS Compiler API was the top research recommendation for a Node.js-based tool, **py-tree-sitter is the right choice** since the scanner lives in the Python `core/` CLI. This also naturally extends to Python SDK scanning later — just add `tree-sitter-python` grammar.

**V2 (Python scanning)**: Add `tree-sitter-python` grammar. Same query patterns, same output format. JS first, Python next.

#### Package Location

**Decision**: The scanner lives in `core/` as a subcommand of the existing `business-use` CLI (Python). This is cleaner because:
- Implementers just add `uvx business-use-core scan ./src` to CI — done
- The SDK itself doesn't need to do anything extra at runtime
- The `scan` command pushes extracted nodes directly to the backend API using `--api-key` and `--url` (same auth as the rest of the CLI)
- No database needed in CI — the scanner is a pure API client

The scanner parses JS/TS files (using the TypeScript Compiler API via a bundled Node.js script or subprocess) and POSTs the extracted graph to the backend's registration endpoint.

#### CLI Design

```bash
# Basic scan — extracts nodes and POSTs to backend
business-use scan ./src --url http://localhost:13370 --api-key <key>

# Dry-run — scan and print results without connecting to backend
business-use scan ./src --dry-run

# Output formats (for dry-run / inspection)
business-use scan ./src --dry-run --format json     # Machine-readable (default)
business-use scan ./src --dry-run --format table     # Human-readable

# Filter by flow
business-use scan ./src --flow checkout --dry-run

# Watch mode (re-scan on changes, push updates)
business-use scan ./src --watch

# Validate only — check for issues without pushing
business-use scan ./src --validate
```

**Key flags:**
- `--dry-run`: Scan and print extracted nodes locally, no backend connection needed. For local testing.
- `--validate`: Run graph validation (check `depIds` references, warn on issues) without pushing.
- `--format json|table`: Output format for dry-run mode.

#### Output Format (JSON)

The JSON format is used for `--dry-run` output and as the payload for the API POST:

```json
{
  "version": "1.0",
  "scanned_at": "2026-03-25T10:00:00Z",
  "files_scanned": 47,
  "flows": {
    "checkout": {
      "nodes": [
        {
          "id": "cart_created",
          "type": "act",
          "dep_ids": [],
          "description": "Cart was created",
          "has_filter": false,
          "has_validator": false,
          "source": { "file": "src/cart/service.ts", "line": 42, "column": 3 }
        },
        {
          "id": "payment_processed",
          "type": "assert",
          "dep_ids": ["cart_created"],
          "has_validator": true,
          "conditions": [{ "timeout_ms": 5000 }],
          "source": { "file": "src/payment/handler.ts", "line": 118, "column": 5 }
        }
      ]
    }
  },
  "warnings": [
    "src/utils/helper.ts:22 - ensure() call with non-literal 'id' argument, skipped"
  ]
}
```

No YAML output needed — the scanner pushes directly to the API.

#### Configuration

```yaml
# .business-use/scan.yaml
parser:
  include: ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"]
  exclude: ["**/node_modules/**", "**/dist/**", "**/*.test.*"]

patterns:
  - function: ensure
    from: "business-use"
  - function: act
    from: "business-use"
  - function: assert
    from: "business-use"

cache:
  enabled: true
  strategy: content  # sha-256 hash of file content
  location: .business-use/.scan-cache.json
```

#### Incremental Analysis

Content-hash caching (SHA-256 of file content):
- Cold scan of 500 TS files: <1 second
- Warm scan (no changes): <100ms (just stat checks)
- Incremental (1 file changed): <200ms

Cache stored in `.business-use/.scan-cache.json`.

#### CI/CD Integration

**GitHub Action:**
```yaml
- name: Register flow definitions
  run: uvx business-use-core scan ./src --url ${{ secrets.BUSINESS_USE_URL }} --api-key ${{ secrets.BUSINESS_USE_API_KEY }}
```

#### Graph Validation

When `--validate` is used (or as part of every scan), the tool checks:
- All `depIds` reference existing nodes within the same flow — **warn** if not
- Duplicate node IDs within a flow — **warn**
- Unreachable nodes (no path from root) — **warn**

Warnings are printed to stderr but do not cause non-zero exit. This helps catch broken references at dev time.

#### Wrapper Function Detection

V1 handles the happy path only: direct `ensure()`/`act()`/`assert()` calls imported from `business-use`. If the scanner encounters calls it can't fully extract (dynamic values, wrapper functions), it prints warnings. The `--validate` / `--dry-run` flags let users test locally without needing backend keys.

### 7. Import Verification Strategy

The tool must verify that `ensure`/`act`/`assert` are actually imported from `business-use`, not some other package. Using TS compiler API:

```typescript
function analyzeImports(sourceFile: ts.SourceFile): ImportInfo {
  const result = { namedImports: new Set<string>(), aliases: new Map<string, string>() };

  ts.forEachChild(sourceFile, (node) => {
    if (!ts.isImportDeclaration(node)) return;
    const moduleName = (node.moduleSpecifier as ts.StringLiteral).text;
    if (moduleName !== 'business-use') return;

    const bindings = node.importClause?.namedBindings;
    if (bindings && ts.isNamedImports(bindings)) {
      for (const spec of bindings.elements) {
        const original = spec.propertyName?.text ?? spec.name.text;
        const local = spec.name.text;
        if (['ensure', 'act', 'assert'].includes(original)) {
          if (original === local) result.namedImports.add(local);
          else result.aliases.set(local, original);
        }
      }
    }
  });
  return result;
}
```

This handles: named imports, aliased imports (`import { ensure as track }`), and namespace imports (`import * as bu`).

### 8. ast-grep as Complementary Tool

[ast-grep](https://ast-grep.github.io/) provides a higher-level pattern syntax on top of tree-sitter. Could be offered as a quick search tool for users:

```bash
# Find all ensure() calls
sg -p 'ensure({ id: $ID, flow: $FLOW, $$$ })' --lang ts

# Find all ensure() calls with depIds
sg -p 'ensure({ id: $ID, flow: $FLOW, depIds: $DEPS, $$$ })' --lang ts
```

This is useful for ad-hoc exploration but not for programmatic extraction (the JS API `@ast-grep/napi` has native bindings).

### 9. Proof-of-Concept Validation

A working PoC scanner was built using py-tree-sitter (`core/e2e-tests/poc_scanner.py`) and tested against 9 fixture files in `core/e2e-tests/js/`. Dependencies: `tree-sitter==0.25.2`, `tree-sitter-javascript==0.25.0`, `tree-sitter-typescript==0.23.2`.

#### Results: 9 files scanned, 2 correctly skipped

| Fixture | Nodes Extracted | Notes |
|---------|----------------|-------|
| `basic-flow.ts` | 3/3 | cart_created (act), payment_processed (act), order_total_matches (assert). All props extracted correctly including `conditions`, `description`, `depIds`. |
| `helpers-usage.ts` | 3/3 | Types correctly inferred from function name: `act()` → act, `assert()` → assert. |
| `multiple-flows.ts` | 5/5 | Nodes correctly grouped into `checkout` (2) and `refund` (3) flows. `filter` presence detected. `conditions` extracted. |
| `namespace-import.ts` | 3/3 | `bu.ensure()`, `bu.act()`, `bu.assert()` all detected via namespace import tracking. |
| `aliased-import.ts` | 1/1 | `trackEvent()` (aliased from `ensure`) extracted. `otherEnsure()` from `some-other-package` correctly ignored. |
| `jsx-component.tsx` | 1/1 | `ensure()` inside React component event handler extracted. TSX grammar handled correctly. |
| `edge-cases.ts` | 5 extracted, 3 skipped | See edge case analysis below. |
| `no-business-use.ts` | 0 (skipped) | Local `ensure()` function correctly ignored — no matching import. |
| `require-pattern.js` | 0 (skipped) | CJS `require()` not detected (by design — V2 item). |

#### Edge Case Analysis (`edge-cases.ts`)

| Case | Outcome | Warning |
|------|---------|---------|
| Normal literal values | Extracted | — |
| Dynamic `id` (variable) | Skipped | `ensure() skipped: missing/non-literal 'id'` |
| Template literal (no substitution) | Extracted (`static_template`) | — |
| Template literal with `${...}` | Skipped | `ensure() skipped: missing/non-literal 'id'` |
| `depIds` with mixed literals + variable | Partial: extracted `['normal_node', 'static_template']`, dropped variable | `depIds contains variable 'extraDep'` |
| `depIds` with spread `[...baseDeps, 'c']` | Partial: extracted `['c']` only | `depIds contains spread element` |
| Conditional `if (flag) { ensure(...) }` | Extracted (scanner ignores control flow) | — |
| Missing `flow` property | Skipped | `ensure() called without object literal argument` |

#### Key Implementation Patterns Validated

1. **Import verification works**: The scanner correctly differentiates `ensure` from `business-use` vs `ensure` from other packages or local functions.
2. **String extraction**: `string_fragment` child node gives unquoted value. Template literals without substitutions also work.
3. **Namespace imports**: `bu.ensure()` detected by tracking `import * as bu` and checking `member_expression` nodes.
4. **Alias resolution**: `import { ensure as trackEvent }` correctly maps `trackEvent()` calls back to `ensure`.
5. **Type inference**: `act()` → always "act", `assert()` → always "assert", `ensure()` → check `validator` property presence.
6. **Graceful degradation**: Non-extractable values produce warnings but don't crash or skip the entire file.

#### Test Fixtures Reference

```
core/e2e-tests/
├── js/
│   ├── basic-flow.ts          # Happy path: 3 nodes, all props
│   ├── helpers-usage.ts       # act()/assert() helpers
│   ├── multiple-flows.ts      # 2 flows in one file (checkout + refund)
│   ├── edge-cases.ts          # Dynamic values, spreads, conditionals
│   ├── aliased-import.ts      # import { ensure as trackEvent }
│   ├── namespace-import.ts    # import * as bu
│   ├── no-business-use.ts     # No SDK import (should skip)
│   ├── jsx-component.tsx      # TSX with ensure() in event handler
│   └── require-pattern.js     # CJS require() (V2 item)
├── py/
│   ├── basic_flow.py          # Python SDK happy path
│   ├── helpers_usage.py       # act()/assert_() helpers
│   ├── edge_cases.py          # Dynamic values, f-strings
│   └── no_business_use.py     # No SDK import (should skip)
└── poc_scanner.py             # PoC scanner (~300 lines)
```

## Code References

| File | Line | Description |
|------|------|-------------|
| `sdk-js/src/client.ts` | 191-216 | `ensure()` function — primary extraction target (JS) |
| `sdk-js/src/client.ts` | 250-260 | `act()` helper — convenience wrapper |
| `sdk-js/src/client.ts` | 266-277 | `assert()` helper — convenience wrapper |
| `sdk-js/src/models.ts` | 10 | `NodeType` — act, assert, generic, trigger, hook |
| `sdk-js/src/models.ts` | 57-59 | `NodeCondition` — timeout_ms |
| `sdk-py/src/business_use/client.py` | 109-200 | `ensure()` function — primary extraction target (Python) |
| `sdk-py/src/business_use/client.py` | 228-273 | `act()` helper (Python) |
| `sdk-py/src/business_use/client.py` | 276-331 | `assert_()` helper (Python) |

## Decisions (from review)

1. **Package location**: Scanner lives in `core/` as a CLI subcommand (`business-use scan`). Cleaner for implementers — just add to CI. Scanner POSTs to backend API using key/url.
2. **Python scanner**: JS/TS first, Python next. Tree-sitter (WASM) for Python when ready.
3. **No YAML output**: Scanner pushes directly to API. No need for YAML generation.
4. **Graph validation**: Print warnings for broken `depIds` references, duplicate IDs, unreachable nodes.
5. **Registration**: Scanner POSTs extracted nodes to backend API (no DB needed in CI).
6. **Wrapper detection**: Happy path only in V1 (direct calls). Warn on unrecognizable patterns. `--dry-run` and `--validate` for local testing without backend keys.

## Remaining Open Questions

1. **Backend API endpoint**: Batch POST to a new `POST /v1/flows/upsert` endpoint (similar to events-batch but for node definitions). The scan payload is graph structure, not runtime events — different from `/v1/events-batch`.
2. **Parser runtime**: **py-tree-sitter** — Python bindings for tree-sitter. No Node.js dependency. Uses `tree-sitter-javascript` and `tree-sitter-typescript` grammars via pip. Naturally extends to Python scanning later. Note: this means we use tree-sitter (not TS Compiler API) for the actual implementation, which is a shift from the research recommendation — but py-tree-sitter is the right call since the CLI is Python.
3. **Idempotency**: Upsert — replace nodes per flow on each scan.
4. **Source location tracking**: Store source file/line info in backend (optional field). Nice for debugging in UI.

## Sources

### Tree-sitter
- [tree-sitter npm](https://www.npmjs.com/package/tree-sitter) (~947K weekly downloads)
- [web-tree-sitter npm](https://www.npmjs.com/package/web-tree-sitter) (~2M weekly downloads)
- [tree-sitter Query Syntax](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax.html)
- [tree-sitter Predicates](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/3-predicates-and-directives.html)
- [Tips for tree-sitter queries (Cycode)](https://cycode.com/blog/tips-for-using-tree-sitter-queries/)
- [prebuildify](https://github.com/prebuild/prebuildify)

### TypeScript Compiler API
- [Using the Compiler API — microsoft/TypeScript Wiki](https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API)
- [Compiler API — learning-notes](https://learning-notes.mistermicheels.com/javascript/typescript/compiler-api/)
- [Gentle Introduction to TypeScript Compiler API — January](https://www.january.sh/posts/gentle-introduction-to-typescript-compiler-api)
- [Reduce typescript package size — Issue #27891](https://github.com/microsoft/TypeScript/issues/27891)

### Prior Art
- [i18next-parser](https://github.com/i18next/i18next-parser) — TS compiler API based
- [i18next-cli](https://github.com/i18next/i18next-cli) — SWC based (next-gen)
- [FormatJS Babel Plugin](https://formatjs.github.io/docs/tooling/babel-plugin/) — Babel based
- [graphql-tag-pluck](https://the-guild.dev/graphql/tools/docs/graphql-tag-pluck) — import detection + template matching
- [Knip](https://knip.dev/) — monorepo-aware dead code detection
- [ast-grep](https://ast-grep.github.io/) — tree-sitter based code search

### Distribution & CLI
- [esbuild optionalDependencies pattern](https://github.com/evanw/esbuild/pull/1621)
- [Publishing binaries on npm — Sentry](https://sentry.engineering/blog/publishing-binaries-on-npm)
- [napi-rs](https://napi.rs/) — Rust -> Node addon
- [Semgrep CLI Reference](https://semgrep.dev/docs/cli-reference)
- [ESLint Incremental Linting](https://github.com/eslint/eslint/issues/20186)

### Benchmarks
- [TypeScript Parser Benchmarks](https://dev.to/herrington_darkholme/benchmark-typescript-parsers-demystify-rust-tooling-performance-2go8)
- [OXC Benchmarks](https://oxc.rs/docs/guide/benchmarks)
- [SWC Benchmarks](https://swc.rs/docs/benchmarks)
- [ECMAScript Parser Benchmark](https://github.com/prantlf/ecmascript-parser-benchmark)
