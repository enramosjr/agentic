"""Execution state machine with local provider fixtures, never cloud qualification."""
import backend_test_support  # Establish the explicit source-only test paths.
import copy
from pathlib import Path
import sys
import unittest

from test_authority_jobs import request
from test_authority_protocol import execution
import authority_jobs as jobs
from trusted_ci_policy import Refusal
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deploy/authority'))
import execution as engine


class Provider:
    def __init__(self, lease):
        self.lease = lease
        self.events = []
        self.bad = False
    def launch(self, lease):
        self.events.append('launch')
        return {'id': 'fixture-instance'}
    def observe(self, handle, lease):
        self.events.append('observe')
    def report(self, lease):
        self.events.append('report')
        value = jobs.result(lease, execution(lease['deployment'])['outcomes'])
        if self.bad:
            value['lease_digest'] = '0' * 64
        return value
    def cleanup(self, handle, lease):
        self.events.append('cleanup')


class ExecutionContracts(unittest.TestCase):
    def test_cleanup_precedes_success_and_failed_result_never_escapes(self):
        for bad in (False, True):
            lease = request()
            provider = Provider(lease)
            provider.bad = bad
            if bad:
                with self.assertRaises(Refusal):
                    engine.execute(provider, lease, now=lambda: 1001, sleep=lambda _: None)
            else:
                result = engine.execute(provider, lease, now=lambda: 1001, sleep=lambda _: None)
                self.assertTrue(result['cleanup_complete'])
                self.assertFalse(result['enforcement_active'])
            self.assertEqual(provider.events[-1], 'cleanup')

    def test_cancellation_before_launch_and_after_launch(self):
        lease = request()
        provider = Provider(lease)
        with self.assertRaises(Refusal):
            engine.execute(provider, lease, now=lambda: 1001, cancelled=lambda: True)
        self.assertFalse(provider.events)
        provider = Provider(lease)
        with self.assertRaises(Refusal):
            engine.execute(provider, lease, now=lambda: 1001,
                           cancelled=lambda: bool(provider.events), sleep=lambda _: None)
        self.assertEqual(provider.events, ['launch', 'cleanup'])

    def test_cleanup_failure_cannot_be_reported_as_success(self):
        lease = request()
        provider = Provider(lease)
        def fail(handle, lease):
            raise Refusal('cleanup failed')
        provider.cleanup = fail
        with self.assertRaisesRegex(Refusal, 'cleanup failed'):
            engine.execute(provider, lease, now=lambda: 1001, sleep=lambda _: None)


if __name__ == '__main__':
    unittest.main()
