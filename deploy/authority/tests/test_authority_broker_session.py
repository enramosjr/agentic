"""Held session sequencing; collector acceptance has separate API-fixture tests."""
import backend_test_support
import copy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from test_authority_merge_window import binding, gate
from test_authority_merge_receipts import ReceiptAPI
from trusted_ci_policy import Refusal
import authority_release
import broker_session


class SessionAPI(ReceiptAPI):
    def __init__(self):
        super().__init__()
        self.warm = True
        self.producers = [dict(id=80 + i, run_id=99, head_sha='a' * 40,
            name=name, status='in_progress', conclusion=None) for i, name in enumerate(
                ['controls (7)', *['final proof (' + p + ')' for p in ('admin', 'reader', 'issuer', 'coding', 'merge')]])]
        self.events = []

    def pages(self, path, collection):
        if path.endswith('/attempts/1/jobs'):
            return [self.job, *(self.producers if self.warm else [])]
        return super().pages(path, collection)

    def upload(self, name, raw):
        self.events.append('not-submitted' if name.endswith('-not-submitted') else name.rsplit('-', 1)[-1])
        identity = super().upload(name, raw)
        self.artifacts[-1]['created_at'] = datetime.fromtimestamp(self.clock(), timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        if name.endswith('-control-ready'):
            for job in self.producers:
                job.update(status='completed', conclusion='success')
                prefix = ('controls-7' if job['name'].startswith('controls') else
                          'final-proof-' + job['name'].split('(')[1][:-1])
                self.artifacts.append(dict(id=3000 + job['id'], name=prefix + '-1'))
        return identity


class SessionContracts(unittest.TestCase):
    def configured(self):
        b, api, now = binding(), SessionAPI(), [1002]
        class Registry:
            def __init__(self): self.reads = 0
            def binding(self):
                self.reads += 1
                return copy.deepcopy(b)
        class Merger:
            def __init__(self): self.calls = []
            def merge(self, repository, pr, head, timeout):
                self.calls.append((repository, pr, head, timeout))
                return {'merged': True, 'sha': '8' * 40}
        registry, merger = Registry(), Merger()
        api.clock = lambda: now[0]
        session = broker_session.Session(registry, object(), api, {}, 77, {}, merger, api.upload,
            clock=lambda: now[0], sleeper=lambda seconds: now.__setitem__(0, now[0] + seconds))
        return session, registry, merger, api

    def test_public_session_hold_precedes_registry_or_network_access(self):
        session, registry, merger, api = self.configured()
        with self.assertRaises(authority_release.Held): session.run()
        self.assertEqual(registry.reads, 0)
        self.assertEqual(api.events, [])
        self.assertEqual(merger.calls, [])

    def test_warm_producers_then_ready_then_fresh_finish_then_one_dispatch(self):
        session, registry, merger, api = self.configured()
        events = []
        def preload(*args):
            events.append('preload')
            return {'binding': binding(), 'proofs': {'valid_until': {p: 1300 for p in ('admin', 'reader', 'issuer', 'coding', 'merge')}}}
        def finish(*args):
            events.append('finish')
            self.assertTrue(any(a['name'].endswith('-control-ready') for a in api.artifacts))
            self.assertEqual(set(args[-2]), {'admin', 'reader', 'issuer', 'coding', 'merge'})
            return gate()
        with patch.object(broker_session.broker_evidence, 'preload', side_effect=preload), \
             patch.object(broker_session.broker_evidence, 'finish', side_effect=finish):
            result = session._run()
        self.assertEqual(result['state'], 'submitted')
        self.assertEqual(events, ['preload', 'finish'])
        self.assertEqual(len(merger.calls), 1)
        self.assertEqual(api.events, ['ready', 'dispatch', 'outcome'])

    def test_missing_warm_producer_times_out_before_readiness_or_merge(self):
        session, registry, merger, api = self.configured()
        api.warm = False
        with patch.object(broker_session.broker_evidence, 'preload', return_value={}) as preload:
            with self.assertRaises(Refusal): session._run()
            preload.assert_not_called()
        self.assertEqual(api.events, ['not-submitted'])
        self.assertEqual(merger.calls, [])

    def test_failed_preload_has_positive_no_dispatch_evidence(self):
        session, registry, merger, api = self.configured()
        with patch.object(broker_session.broker_evidence, 'preload', side_effect=Refusal('synthetic refusal')):
            with self.assertRaises(Refusal): session._run()
        self.assertEqual(api.events, ['not-submitted'])
        self.assertEqual(merger.calls, [])
        self.assertEqual(session.receipts.authenticate(session.receipts._locator('not-submitted', api.artifacts[0]))['job_id'], 77)

    def test_failure_after_dispatch_begins_is_unknown_and_never_retried(self):
        session, registry, merger, api = self.configured()
        with patch.object(broker_session.broker_evidence, 'preload', return_value={'binding': binding()}), \
             patch.object(broker_session.broker_evidence, 'finish', return_value=gate()), \
             patch.object(broker_session.merge_window, 'dispatch', side_effect=OSError('synthetic lost acknowledgement')) as dispatch:
            result = session._run()
        self.assertEqual(result['state'], 'unknown')
        self.assertTrue(result['fence_pending'])
        self.assertEqual(dispatch.call_count, 1)


if __name__ == '__main__':
    unittest.main()
