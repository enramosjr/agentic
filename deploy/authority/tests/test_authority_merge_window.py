"""Local broker dispatch/deadline/recovery contracts, never hosted qualification."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch
import subprocess
import sys
import time
import json
import io

from test_authority_registry import intent
from test_authority_fence import pending
from trusted_ci_policy import Refusal, digest
import merge_window
import merge_transport
import operation_fence


def gate():
    d = intent()
    d.update(state='active', qualification='f' * 64)
    return {'schema_version': 2, 'operation_id': '1' * 32, 'sequence': 1,
        'configuration_revision': 'b' * 40, 'deployment_digest': digest(d),
        'repository_id': 123, 'authority_repository_id': 456, 'target': 'main',
        'pr': 7, 'head': '2' * 40, 'base': '5' * 40, 'merge': '3' * 40,
        'tree': '6' * 40, 'workflow_sha': 'a' * 40, 'run_id': 99, 'attempt': 1,
        'epoch': d['policy']['epoch'], 'check_name': d['policy']['check_name'],
        'issued': 1000, 'expires': 1250, 'readback_started': 1000, 'readback_completed': 1001,
        'valid_until': {'deployment': 2000, 'qualification': 1500, 'task': 1400,
                        **{purpose: 1300 for purpose in ('admin', 'reader', 'issuer', 'coding', 'merge')}},
        'evidence_digest': 'a' * 64, 'controls_digest': 'b' * 64,
        'proofs_digest': 'c' * 64, 'task_digest': 'd' * 64,
        'qualification_digest': 'f' * 64, 'check_id': 1234, 'review_ids': [789]}


def binding():
    d = intent()
    d.update(state='active', qualification='f' * 64)
    b = {'deployment': d, 'configuration_revision': 'b' * 40, 'deployment_digest': digest(d)}
    op = pending(b)
    fence = operation_fence.empty(d)
    fence.update(sequence=1, pending=op)
    return dict(b, fence=fence)


class AuthorizationWindow(unittest.TestCase):
    def test_verification_fence_is_not_itself_a_merge_authorization(self):
        g, b = gate(), binding()
        # Acquire before verification, which may take the approved 600 seconds.
        # The actual authorization starts only after fresh readback and proofs.
        b['fence']['pending']['execution_deadline'] = 2000
        g.update(issued=1600, expires=1850, readback_started=1600, readback_completed=1601)
        g['valid_until'] = {key: 1950 for key in merge_window.EXPIRING}
        g['valid_until']['deployment'] = b['deployment']['expires']
        self.assertIs(merge_window.validate(g, b, 1602), g)
        g['issued'] = 1000
        with self.assertRaises(Refusal):
            merge_window.validate(g, b, 1602)

    def test_exact_gate_binds_pending_fence_and_fresh_window(self):
        g = gate()
        self.assertIs(merge_window.validate(g, binding(), 1002), g)

    def test_stale_short_future_and_overlong_authorizations_are_rejected(self):
        for field, value in [('readback_started', 970), ('issued', 1003), ('expires', 1061), ('expires', 1301)]:
            g = gate()
            g[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(Refusal):
                merge_window.validate(g, binding(), 1002)
        for purpose in gate()['valid_until']:
            g = gate()
            g['valid_until'][purpose] = 1061
            with self.subTest(purpose=purpose), self.assertRaises(Refusal):
                merge_window.validate(g, binding(), 1002)

    def test_every_candidate_configuration_and_attempt_field_is_bound(self):
        for field, value in [('configuration_revision', 'c' * 40), ('deployment_digest', 'e' * 64),
            ('repository_id', 789), ('authority_repository_id', 789), ('pr', 8), ('head', '4' * 40),
            ('base', '4' * 40), ('merge', '4' * 40), ('workflow_sha', '4' * 40), ('run_id', 100),
            ('attempt', 2), ('operation_id', '2' * 32), ('sequence', 2), ('epoch', 'old'),
            ('check_name', 'stale'), ('qualification_digest', 'e' * 64)]:
            g = gate()
            g[field] = value
            with self.subTest(field=field), self.assertRaises(Refusal):
                merge_window.validate(g, binding(), 1002)


class DispatchContracts(unittest.TestCase):
    def test_transport_uses_one_fixed_source_put_with_expected_head_and_merge_method(self):
        calls = []
        class Response(io.BytesIO):
            status = 200
        class Opener:
            def open(self, req, timeout):
                calls.append((req, timeout))
                return Response(b'{"merged": true, "sha": "7777777777777777777777777777777777777777"}')
        document = dict(token='SYNTHETIC', repository='owner/project', pr=7, head='2' * 40, timeout=30)
        self.assertTrue(merge_transport.request_once(document, Opener())['merged'])
        self.assertEqual(len(calls), 1)
        req, timeout = calls[0]
        self.assertEqual(req.full_url, 'https://api.github.com/repos/owner/project/pulls/7/merge')
        self.assertEqual(req.method, 'PUT')
        self.assertEqual(json.loads(req.data), {'sha': '2' * 40, 'merge_method': 'merge'})
        self.assertEqual(timeout, 30)

    def test_transport_supervisor_kills_a_stalled_child_at_total_deadline(self):
        children = []
        real_popen = subprocess.Popen
        def stalled(argv, **kwargs):
            self.assertNotIn('SYNTHETIC-SECRET', ' '.join(argv))
            self.assertNotIn('GITHUB_TOKEN', kwargs['env'])
            child = real_popen([sys.executable, '-I', '-c', 'import time; time.sleep(10)'], **kwargs)
            children.append(child)
            return child
        started = time.monotonic()
        with patch.object(merge_transport.subprocess, 'Popen', side_effect=stalled), self.assertRaises(Refusal):
            merge_transport.isolated({'token': 'SYNTHETIC-SECRET'}, .15)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())

    def test_one_expected_head_request_only_after_immutable_intent_readback(self):
        events = []
        g, b = gate(), binding()
        class Receipts:
            def append(self, kind, document):
                events.append(('receipt', kind))
                return {'kind': kind, 'document': copy.deepcopy(document)}
            def authenticate(self, receipt):
                events.append(('authenticated', receipt['kind']))
                return receipt['document']
        class Source:
            def merge(self, repository, pr, head, timeout):
                events.append(('merge', repository, pr, head, timeout))
                return {'merged': True, 'sha': '7' * 40}
        result = merge_window.dispatch(g, lambda: b, Receipts(), Source(), lambda: 1002)
        self.assertEqual(events[:3], [('receipt', 'dispatch'), ('authenticated', 'dispatch'),
                                     ('merge', 'owner/project', 7, '2' * 40, 30)])
        self.assertEqual(result['state'], 'submitted')

    def test_upload_latency_and_changed_fence_prevent_dispatch(self):
        for defect in ('latency', 'fence'):
            g, b, clock = gate(), binding(), [1002]
            calls = []
            class Receipts:
                def append(self, kind, document):
                    clock[0] = 1240 if defect == 'latency' else 1002
                    if defect == 'fence':
                        b['fence']['pending']['operation_id'] = '2' * 32
                    return document
                def authenticate(self, receipt):
                    return receipt
            class Source:
                def merge(self, *args, **kwargs):
                    calls.append(args)
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                merge_window.dispatch(g, lambda: b, Receipts(), Source(), lambda: clock[0])
            self.assertEqual(calls, [])


class UncertainMergeOutcome(unittest.TestCase):
    def test_transport_exception_is_unknown_and_never_retried(self):
        g, b, calls = gate(), binding(), []
        class Receipts:
            def append(self, kind, document):
                return document
            def authenticate(self, receipt):
                return receipt
        class Source:
            def merge(self, *args, **kwargs):
                calls.append(args)
                raise TimeoutError('synthetic lost response')
        result = merge_window.dispatch(g, lambda: b, Receipts(), Source(), lambda: 1002)
        self.assertEqual(result['state'], 'unknown')
        self.assertEqual(len(calls), 1)
        self.assertIsNotNone(b['fence']['pending'])

    def test_recovery_uses_actual_parents_and_tree_not_synthetic_sha_or_open_pr(self):
        g = gate()
        pr = {'number': 7, 'merged': True, 'state': 'closed', 'head': {'sha': g['head']},
              'base': {'ref': 'main', 'repo': {'id': 123}}, 'merge_commit_sha': '7' * 40}
        commit = {'sha': '7' * 40, 'parents': [{'sha': g['base']}, {'sha': g['head']}],
                  'tree': {'sha': g['tree']}}
        merge_window.recover_merged(g, pr, commit)
        for defect in ('open', 'head', 'parent', 'tree', 'sha'):
            changed_pr, changed_commit = copy.deepcopy(pr), copy.deepcopy(commit)
            if defect == 'open':
                changed_pr.update(merged=False, state='open')
            elif defect == 'head':
                changed_pr['head']['sha'] = '4' * 40
            elif defect == 'parent':
                changed_commit['parents'].reverse()
            elif defect == 'tree':
                changed_commit['tree']['sha'] = '4' * 40
            else:
                changed_commit['sha'] = g['merge']
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                merge_window.recover_merged(g, changed_pr, changed_commit)


if __name__ == '__main__':
    unittest.main()
