"""Connected broker suffix over local host/OCI boundaries; no hosted claim."""
import backend_test_support
import copy
from contextlib import ExitStack
import io
import json
import unittest
import zipfile
from unittest.mock import patch

import broker_session
import controls
import merge_window
import merge_transport
import qualification_broker
import service
from registry import DOCUMENT, OPERATION
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal, digest
from test_authority_qualification_cases import ConnectedHost


class ConnectedBroker(ConnectedHost):
    def __init__(self):
        # Reuse actual Git object, registry and closed publication composition,
        # without executing the already delivered host-negative probes again.
        from test_authority_registry import RegistryHost
        self.stack = ExitStack()
        self.fixtures = {}
        self.sessions = []
        self.prefix = [dict(name=name, pr=i, head=format(i, '040x'))
                       for i, name in enumerate(__import__('qualification_cases').HOST_CASES, 1)]
        for index, name in enumerate(qualification_broker.CASES, 12):
            self.registry_host = RegistryHost()
            f = self.fixture(index, name)
            if name == 'expired-proof':
                fence = copy.deepcopy(f.binding['fence'])
                fence['pending']['execution_deadline'] = 1800
                self.replace(f, fence=fence)
                f.binding = f.registry.binding()
            self.acceptance(f, {})
            f.clock[0] = 1095
            f.job('controls (' + str(index) + ')', 'controls', 800)
            for i, purpose in enumerate(broker_session.PURPOSES):
                f.job('final proof (' + purpose + ')', purpose + '_final_proof', 801+i)
            f.job('broker (' + str(index) + ')', 'broker', 900)
            upload = f.upload
            def schedule(artifact, raw, f=f, name=name, upload=upload):
                identity = upload(artifact, raw)
                if artifact.endswith('-control-ready'):
                    f.clock[0] = 1096
                    with patch.object(controls, 'observe', return_value=f.facts): f.run('controls')
                    for purpose in broker_session.PURPOSES: f.run('final-proof', purpose)
                    self.fault(f, name)
                return identity
            source_get = f.source.get
            def get(path, f=f, source_get=source_get):
                if path.endswith('/git/ref/heads/main'): return dict(object=dict(sha=f.source.current_base))
                return source_get(path)
            f.source.get = get
            d = f.binding['deployment']
            merger = self.stack.enter_context(service._source_token('merge', f.roots['merge'], f.api, d,
                f.identities, f.binding['configuration_revision'], lambda f=f:f.clock[0], f.token_api))
            f.merger = merge_window.MergeSource(merger.token, d['policy']['repository'], d['policy']['repository_id'])
            locators = lambda f=f: __import__('service')._publication_locators(f.api, f.binding, f.request)
            session = broker_session.Session(f.registry, f.source, f.api, f.identities, 900, locators,
                f.merger, schedule, clock=lambda f=f:f.clock[0], sleeper=lambda seconds:None)
            self.fixtures[name] = f
            self.sessions.append((name, session))
            if name == 'expired-proof': f.clock[0] = 1390

    @staticmethod
    def replace(f, fence=None, deployment=None):
        host = f.registry.api
        tree = copy.deepcopy(host.trees[host.commits[host.refs['agentic-registry']]['tree']['sha']])
        if fence is not None: tree[OPERATION] = ('100644', host.blob(json.dumps(fence).encode()))
        if deployment is not None: tree[DOCUMENT] = ('100644', host.blob(json.dumps(deployment).encode()))
        key = digest(tree)[:40]
        host.trees[key] = tree
        commit = host.post('/repos/owner/authority/git/commits', dict(message='local transition fixture',
            tree=key, parents=[host.refs['agentic-registry']]))['sha']
        host.refs['agentic-registry'] = commit

    def transport(self, document, seconds):
        f = next(v for v in self.fixtures.values() if v.snapshot['pr'] == document['pr'])
        class Opener:
            def open(self, request, timeout):
                body = json.loads(request.data)
                if request.method != 'PUT' or body != dict(sha=f.snapshot['head'], merge_method='merge'):
                    raise AssertionError('unexpected merge request')
                f.source.merges.append((document['repository'], document['pr'], body['sha'], timeout))
                original = f.source.commits[body['sha']]
                actual = f.source.post('/repos/owner/project/git/commits', dict(message='actual hosted merge fixture',
                    tree=f.source.merge_tree, parents=[f.snapshot['base'], body['sha']],
                    author=original['author'], committer=original['committer']))['sha']
                f.source.current_base = actual
                f.source.prs[0].update(merged=True, state='closed', merge_commit_sha=actual)
                response = io.BytesIO(json.dumps(dict(merged=True, sha=actual)).encode())
                response.status = 200
                return response
        return merge_transport.request_once(document, Opener())

    def execute(self, runner=None):
        with patch.object(merge_transport, 'isolated', side_effect=self.transport):
            return (runner or self.runner())._run(self.prefix)

    def fault(self, f, name):
        if name == 'revoked-qualification':
            f.api.artifacts[:] = [a for a in f.api.artifacts if a['id'] != f.locators['qualification']['artifact_id']]
        elif name == 'authority-outage':
            pages = f.api.pages
            source_pages = f.source.pages
            pending = [False]
            def reviewed(path, collection=None):
                result = source_pages(path, collection)
                if path.endswith('/reviews'): pending[0] = True
                return result
            f.source.pages = reviewed
            def outage(path, collection=None):
                if path.endswith('/runs/99/artifacts') and pending[0]:
                    pending[0] = False
                    raise HostRefusal(503)
                return pages(path, collection)
            f.api.pages = outage
        elif name == 'context-transition':
            deployment = copy.deepcopy(f.binding['deployment'])
            deployment['policy']['epoch'] = 'changed-context'
            deployment['policy']['check_name'] = 'changed-context-check'
            deployment.update(state='qualification', qualification=None, generation=deployment['generation']+1)
            fence = copy.deepcopy(f.binding['fence'])
            fence['contexts'].append(dict(epoch='changed-context', check_name='changed-context-check', activated=False))
            self.replace(f, fence=fence, deployment=deployment)

    def runner(self):
        f = self.fixtures['positive']
        return qualification_broker.BrokerCases(self.sessions, f.roots['merge'], f.token_api)


class BrokerCaseContracts(unittest.TestCase):
    def connected(self, cls=ConnectedBroker):
        f = cls()
        self.addCleanup(f.stack.close)
        return f

    def test_ordered_suffix_uses_actual_session_receipts_and_actual_merge_commit(self):
        host = ConnectedHost()
        prefix = host.runner()._run(host.manifest)['cases']
        f = self.connected()
        f.prefix = prefix
        runner = f.runner()
        produced = f.execute(runner)
        result = produced['cases']
        self.assertFalse(produced['hosted_qualified'])
        self.assertFalse(produced['enforcement_active'])
        for record, observation in zip(result, produced['observations']):
            self.assertEqual(record['evidence_digest'], digest(observation))
        self.assertNotIn('SYNTHETIC-TOKEN', json.dumps(produced))
        self.assertEqual([v['name'] for v in result], list(qualification_broker.CASES))
        for value in result[:-1]:
            self.assertFalse(value['request_sent'])
            self.assertEqual(value['before'], value['after'])
            self.assertEqual(value['broker_refusal'], qualification_broker.BROKER_DENIALS[value['name']])
            self.assertEqual(f.fixtures[value['name']].source.merges, [])
        positive = result[-1]
        self.assertTrue(positive['request_sent'])
        self.assertNotEqual(positive['merge_commit'], positive['merge'])
        self.assertEqual(positive['merge_parents'], [positive['base'], positive['head']])
        self.assertEqual(positive['merge_tree'], positive['tree'])
        self.assertEqual(len(f.fixtures['positive'].source.merges), 1)
        for value in result:
            self.assertEqual(set(value), set(__import__('qualification_record').CASE_FIELDS))
        with self.assertRaisesRegex(Refusal, 'never replay'): f.execute(runner)
        with self.assertRaises(Refusal): f.execute()  # Changed context still blocks the whole inventory.

    def test_retained_receipt_prevents_fresh_instance_replay_before_later_cases(self):
        f = self.connected()
        name, session = f.sessions[0]
        runner = f.runner()
        record, _ = runner._case(name, session, session.registry.binding())
        self.assertEqual(record['broker_refusal'], 'proof_expired')
        with self.assertRaisesRegex(Refusal, 'receipt already exists'): f.execute()
        self.assertTrue(all(not value.source.merges for value in f.fixtures.values()))

    def test_inventory_substitution_refuses_before_any_merge(self):
        for defect in ('order', 'head', 'pr', 'prefix'):
            with self.subTest(defect=defect):
                f = self.connected()
                if defect == 'order': f.sessions.reverse()
                elif defect == 'prefix': f.prefix.reverse()
                else:
                    op = f.fixtures['positive'].binding['fence']['pending']
                    f.prefix[0][defect] = op[defect]
                with self.assertRaises(Refusal): f.execute()
                self.assertTrue(all(not v.source.merges for v in f.fixtures.values()))

    def test_unrelated_errors_or_wrong_missing_artifact_cannot_count_as_denials(self):
        for defect in ('wrong-artifact', 'credential', 'archive', 'malformed-expiry', 'wrong-outage'):
            with self.subTest(defect=defect):
                class Changed(ConnectedBroker):
                    def fault(self, f, name):
                        if defect == 'wrong-artifact' and name == 'revoked-qualification':
                            f.api.artifacts[:] = [a for a in f.api.artifacts if not a['name'].startswith('evidence-')]
                        else:
                            super().fault(f, name)
                            if defect == 'wrong-outage' and name == 'authority-outage':
                                pages = f.api.pages
                                def forbidden(path, collection=None):
                                    try: return pages(path, collection)
                                    except HostRefusal as error:
                                        if error.status != 503: raise
                                        raise HostRefusal(403) from error
                                f.api.pages = forbidden
                f = self.connected(Changed)
                if defect == 'credential': f.fixtures['positive'].roots['merge'].generic_denial = True
                if defect in ('archive', 'malformed-expiry'):
                    first = f.fixtures['expired-proof']
                    identity = service._locator(first.api, first.binding['deployment'], 99, 1, 'proof', 'admin')['artifact_id']
                    if defect == 'archive': first.api.raw[identity] = b'not a closed ZIP'
                    else:
                        with zipfile.ZipFile(io.BytesIO(first.api.raw[identity])) as archive:
                            document = json.loads(archive.read('proof.json'))
                        document['expires'] = document['issued']-1
                        first.api.replace(identity, document, 'proof.json')
                with self.assertRaises(Refusal): f.execute()
                self.assertTrue(all(not v.source.merges for v in f.fixtures.values()))

    def test_fence_change_alone_is_not_a_configuration_transition(self):
        class Changed(ConnectedBroker):
            def fault(self, f, name):
                if name == 'context-transition':
                    fence = copy.deepcopy(f.binding['fence'])
                    fence['pending']['execution_deadline'] += 1
                    self.replace(f, fence=fence)
                else: super().fault(f, name)
        f = self.connected(Changed)
        with self.assertRaisesRegex(Refusal, 'actual configuration transition missing'): f.execute()
        self.assertFalse(f.fixtures['context-transition'].source.merges)

    def test_positive_unknown_or_wrong_actual_commit_never_qualifies_or_replays(self):
        for defect in ('lost-ack', 'parents', 'tree', 'sha', 'status'):
            with self.subTest(defect=defect):
                f = self.connected()
                transport = f.transport
                def changed(document, seconds):
                    result = transport(document, seconds)
                    target = f.fixtures['positive']
                    if defect == 'lost-ack': raise OSError('lost local response')
                    commit = target.source.commits[result['sha']]
                    if defect == 'parents': commit['parents'].reverse()
                    if defect == 'tree': commit['tree']['sha'] = 'f'*40
                    if defect == 'sha': commit['sha'] = 'a'*40
                    if defect == 'status': return dict(merged=False, sha=result['sha'])
                    return result
                f.transport = changed
                runner = f.runner()
                with self.assertRaises(Refusal): f.execute(runner)
                self.assertEqual(len(f.fixtures['positive'].source.merges), 1)
                with self.assertRaises(Refusal): f.execute(runner)
                self.assertEqual(len(f.fixtures['positive'].source.merges), 1)

    def test_late_synthetic_tree_or_identity_substitution_cannot_qualify(self):
        for defect in ('tree', 'sha'):
            with self.subTest(defect=defect):
                f = self.connected()
                positive = f.fixtures['positive']
                pages, get = positive.source.pages, positive.source.get
                changed = [False]
                def reviews(path, collection=None):
                    result = pages(path, collection)
                    if path.endswith('/reviews'):
                        changed[0] = True
                        if defect == 'tree': positive.source.merge_tree = 'f'*40
                    return result
                def commit(path):
                    result = get(path)
                    if changed[0] and defect == 'sha' and path.endswith('/git/commits/' + positive.snapshot['merge']):
                        return dict(result, sha='a'*40)
                    return result
                positive.source.pages, positive.source.get = reviews, commit
                with self.assertRaises(Refusal): f.execute()
                self.assertEqual(len(positive.source.merges), 1 if defect == 'tree' else 0)

    def test_public_hold_precedes_all_transport_access(self):
        with self.assertRaises(Refusal): qualification_broker.BrokerCases(None).run(None)


if __name__ == '__main__': unittest.main()
