"""Exact local source-transition contracts; no live GitHub effects."""
import backend_test_support
import copy
import unittest

import submission
from test_authority_submission import SubmissionHost, fixture
from trusted_ci_policy import Refusal


class TransitionHost(SubmissionHost):
    def fetch(self, path, **kwargs):
        if '/git/blobs/' in path: return self.get(path)
        return super().fetch(path, **kwargs)

    def get(self, path):
        value = super().get(path)
        if path == '/repos/owner/project': value['node_id'] = 'fixture-source-node'
        return value

    def post(self, path, data):
        if path != '/graphql': return super().post(path, data)
        self.writes.append((path, copy.deepcopy(data)))
        value = data['variables']['input']
        if value['repositoryId'] != 'fixture-source-node': raise Refusal('foreign node')
        update, = value['refUpdates']
        branch = update['name'].removeprefix('refs/heads/')
        if self.refs[branch] != update['beforeOid'] or update['force'] is not False:
            return dict(errors=[dict(message='source moved')])
        self.refs[branch] = update['afterOid']
        next(p for p in self.prs if p['head']['ref'] == branch)['head']['sha'] = update['afterOid']
        if self.fail_after == '/graphql': raise OSError('unknown ref acknowledgement')
        return dict(data=dict(updateRefs=dict(clientMutationId=value['clientMutationId'])))


class Advance(unittest.TestCase):
    def test_all_native_transition_entrypoints_preserve_release_hold(self):
        from trial_controller import Native
        native=Native(None)
        for call in (lambda:native.open_prior('prompt'),
                     lambda:native.observe_terminal('prompt','new-head',{},phase='prior'),
                     lambda:native.recover_terminal('prompt','new-head',phase='prior')):
            with self.assertRaisesRegex(Refusal,'qualify-live blocked'): call()

    def test_exact_append_preserves_modes_and_recovers_unknown_ref_without_replay(self):
        d, request, files = fixture(); host = TransitionHost()
        original = submission._submit(host, d, request, files)
        tree = host.commits[request['base']]['tree']['sha']
        host.fail_after = '/graphql'
        with self.assertRaisesRegex(OSError, 'unknown ref'):
            submission._advance(host, d, original, tree, 'a'*64, 1001)
        writes = copy.deepcopy(host.writes)
        old = submission._advance(host, d, original, tree, 'a'*64, 1001, recover=True)
        self.assertNotEqual(old['head'], original['head'])
        self.assertEqual(host.commits[old['head']]['parents'], [dict(sha=original['head'])])
        self.assertEqual(host.writes, writes)
        host.fail_after = None
        current = submission._advance(host, d, old, original['tree'], 'b'*64, 1002)
        self.assertEqual(current['tree'], original['tree'])
        self.assertEqual(current['export_digest'], original['export_digest'])
        self.assertEqual(current['pr'], original['pr'])
        self.assertNotEqual(current['head'], original['head'])

    def test_unknown_commit_does_not_repeat_and_foreign_source_cannot_be_adopted(self):
        d, request, files = fixture(); host = TransitionHost()
        original = submission._submit(host, d, request, files)
        tree = host.commits[request['base']]['tree']['sha']
        host.fail_after = '/git/commits'
        with self.assertRaises(OSError): submission._advance(host, d, original, tree, 'a'*64, 1001)
        writes = copy.deepcopy(host.writes)
        with self.assertRaises(Refusal): submission._advance(host, d, original, tree, 'a'*64, 1001, recover=True)
        self.assertEqual(host.writes, writes)
        for issued in (True, 1001.0):
            with self.assertRaises(Refusal): submission._advance(host, d, original, tree, 'a'*64, issued)
