/**
 * Namespace import pattern: import * as bu from 'business-use'
 * Scanner should detect bu.ensure(), bu.act(), bu.assert()
 */
import * as bu from 'business-use';

bu.ensure({
  id: 'namespace_ensure',
  flow: 'namespace_test',
  runId: 'run_1',
  data: { method: 'ensure' },
});

bu.act({
  id: 'namespace_act',
  flow: 'namespace_test',
  runId: 'run_1',
  data: { method: 'act' },
  depIds: ['namespace_ensure'],
});

bu.assert({
  id: 'namespace_assert',
  flow: 'namespace_test',
  runId: 'run_1',
  data: { method: 'assert' },
  depIds: ['namespace_act'],
  validator: (data) => data.method === 'assert',
});
