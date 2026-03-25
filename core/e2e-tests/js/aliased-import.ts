/**
 * Aliased and namespace imports.
 * Scanner should resolve these correctly.
 */

// Aliased import
import { ensure as trackEvent } from 'business-use';

trackEvent({
  id: 'aliased_node',
  flow: 'alias_test',
  runId: 'run_1',
  data: { source: 'aliased' },
});

// This should NOT be extracted — ensure from a different package
import { ensure as otherEnsure } from 'some-other-package';

otherEnsure({
  id: 'wrong_package',
  flow: 'should_not_appear',
  runId: 'run_1',
  data: {},
});
