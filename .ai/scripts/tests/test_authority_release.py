"""The held build cannot activate through a flag, environment or claimed receipt."""
import os
import unittest
from unittest.mock import patch

import trusted_ci_fixtures
import authority_release as release
from trusted_ci_policy import Refusal


class ReleaseHold(unittest.TestCase):
    def test_broker_is_explicitly_held_before_credentials(self):
        self.assertIn('broker-merge', release.HELD_OPERATIONS)
        with self.assertRaises(release.Held):
            release.authorize('broker-merge')

    def test_all_privileged_operations_are_held(self):
        with patch.dict(os.environ, {'AGENTIC_ALLOW_LIVE': '1', 'LIFECYCLE_GUARD': 'off'}):
            for operation in ('bootstrap', 'provision', 'hosted-execute', 'qualify-live',
                              'publish', 'activate', 'protected-run'):
                with self.subTest(operation=operation), self.assertRaises(Refusal):
                    release.authorize(operation)

    def test_local_operations_are_explicitly_allowed(self):
        for operation in ('render', 'inspect-local', 'verify-local', 'export'):
            release.authorize(operation)
        with self.assertRaises(Refusal):
            release.authorize('unknown-operation')

    def test_status_never_claims_enforcement(self):
        status = release.status()
        self.assertEqual(status['state'], 'blocked')
        self.assertFalse(status['enforcement_active'])
        self.assertFalse(status['live_qualification_allowed'])


if __name__ == '__main__':
    unittest.main()
