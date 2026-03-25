/**
 * Edge cases the scanner should handle gracefully.
 * Some calls are extractable, some should produce warnings.
 */
import { ensure } from 'business-use';

// 1. Normal — extractable
ensure({
  id: 'normal_node',
  flow: 'edge_cases',
  runId: 'run_1',
  data: {},
});

// 2. Dynamic id — NOT extractable, should warn
const nodeId = 'dynamic_' + Date.now();
ensure({
  id: nodeId,
  flow: 'edge_cases',
  runId: 'run_1',
  data: {},
});

// 3. Template literal id (no substitution) — extractable
ensure({
  id: `static_template`,
  flow: 'edge_cases',
  runId: 'run_1',
  data: {},
});

// 4. Template literal with substitution — NOT extractable, should warn
const stage = 'prod';
ensure({
  id: `dynamic_${stage}`,
  flow: 'edge_cases',
  runId: 'run_1',
  data: {},
});

// 5. depIds with mixed literals and variables — partial extraction, should warn
const extraDep = 'some_other_node';
ensure({
  id: 'mixed_deps',
  flow: 'edge_cases',
  runId: 'run_1',
  data: {},
  depIds: ['normal_node', extraDep, 'static_template'],
});

// 6. Spread in depIds — NOT extractable
const baseDeps = ['a', 'b'];
ensure({
  id: 'spread_deps',
  flow: 'edge_cases',
  runId: 'run_1',
  data: {},
  depIds: [...baseDeps, 'c'],
});

// 7. Conditional ensure — extractable (scanner doesn't care about control flow)
if (featureFlags.newCheckout) {
  ensure({
    id: 'conditional_node',
    flow: 'edge_cases',
    runId: 'run_1',
    data: {},
    depIds: ['normal_node'],
  });
}

// 8. No flow property — should skip (flow is required)
ensure({
  id: 'missing_flow',
  runId: 'run_1',
  data: {},
} as any);
