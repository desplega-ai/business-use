/**
 * CommonJS require() pattern.
 * Scanner should handle this (V2 — may warn in V1).
 */
const { ensure, act } = require('business-use');

ensure({
  id: 'cjs_node',
  flow: 'cjs_test',
  runId: 'run_1',
  data: { format: 'commonjs' },
});

act({
  id: 'cjs_act',
  flow: 'cjs_test',
  runId: 'run_1',
  data: { format: 'commonjs' },
  depIds: ['cjs_node'],
});
