/**
 * Uses act() and assert() helpers instead of ensure().
 * Scanner should detect all 3 and infer types from function name.
 */
import { act, assert } from 'business-use';

act({
  id: 'user_signup',
  flow: 'onboarding',
  runId: 'run_001',
  data: { email: 'user@example.com' },
});

act({
  id: 'email_verified',
  flow: 'onboarding',
  runId: 'run_001',
  data: { verified: true },
  depIds: ['user_signup'],
});

assert({
  id: 'profile_complete',
  flow: 'onboarding',
  runId: 'run_001',
  data: { hasName: true, hasAvatar: true },
  depIds: ['user_signup', 'email_verified'],
  validator: (data) => data.hasName && data.hasAvatar,
  description: 'User profile is complete after onboarding',
});
