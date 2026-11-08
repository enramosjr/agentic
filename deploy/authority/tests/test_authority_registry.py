"""Independent registry branch, CAS recovery and configuration qualification pins."""
import backend_test_support
import copy
import base64
import unittest

from test_authority_protocol import deployment
from test_authority_repository import GitHost
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal, digest
import authority_protocol
import registry


class RegistryHost(GitHost):
    def __init__(self):
        super().__init__()
        self.refs = {'main': self.ref}
        self.drift = False
        self.before_patch = None
    def get(self, path):
        if '/contents/' in path:
            name, ref = path.split('/contents/')[1].split('?ref=')
            tree = self.trees[self.commits[ref]['tree']['sha']]
            if name not in tree:
                raise HostRefusal(404)
            return {'type': 'file', 'encoding': 'base64', 'content': base64.b64encode(self.blobs[tree[name][1]]).decode()}
        if '/git/ref/heads/' in path:
            name = path.split('/git/ref/heads/')[1]
            if name not in self.refs:
                raise HostRefusal(404)
            return {'object': {'sha': self.refs[name]}}
        return super().get(path)
    def post(self, path, data):
        if path.endswith('/git/refs'):
            name = data['ref'].removeprefix('refs/heads/')
            if name in self.refs:
                raise HostRefusal(422)
            self.refs[name] = data['sha']
            return {}
        return super().post(path, data)
    def fetch(self, path, method='GET', data=None, **kwargs):
        if method == 'PATCH' and '/git/refs/heads/' in path:
            name = path.split('/git/refs/heads/')[1]
            if self.before_patch:
                callback, self.before_patch = self.before_patch, None
                callback()
            require_nonforce = data.get('force') is False
            ancestors, pending = set(), [data['sha']]
            while pending:
                revision = pending.pop()
                if revision in ancestors:
                    continue
                ancestors.add(revision)
                pending.extend(p['sha'] for p in self.commits[revision]['parents'])
            if not require_nonforce or self.refs[name] not in ancestors:
                raise HostRefusal(422)
            self.refs[name] = data['sha']
            if self.lose_ack:
                self.lose_ack = False
                raise OSError('lost registry update acknowledgement')
            return {}
        return super().fetch(path, method, data=data, **kwargs)


def coordinates():
    return {'schema_version': 2, 'repository': 'owner/authority', 'repository_id': 456,
            'registry_branch': 'agentic-registry'}


def intent():
    value = deployment()
    value['policy']['workflow_sha'] = 'a' * 40
    return value


def configuration_operation(store):
    before = store.binding()
    value = before['deployment']
    operation = dict(kind='configuration', operation_id='1' * 32, scope_digest='a' * 64,
        repository_id=value['policy']['repository_id'], target=value['policy']['target'],
        configuration_revision=before['configuration_revision'], deployment_digest=digest(value),
        workflow_sha=value['policy']['workflow_sha'], run_id=99, attempt=1, created=1000,
        execution_deadline=1300, pr=None, head=None, base=None, merge=None)
    store.acquire_operation(before['branch_head'], before['configuration_revision'], operation)
    return operation['operation_id']


class RegistryContracts(unittest.TestCase):
    def test_oversized_valid_record_is_rejected_before_any_mutation(self):
        host = RegistryHost()
        store = registry.Registry(host, coordinates())
        value = intent()
        value['policy']['transitions'] = ['0' * 64] * 12000
        with self.assertRaises(Refusal):
            store.write(None, value)
        self.assertEqual(host.writes, [])
        self.assertNotIn('agentic-registry', host.refs)

    def test_symlink_and_ancestor_collision_are_refused(self):
        host = RegistryHost()
        store = registry.Registry(host, coordinates())
        store.write(None, intent())
        revision = host.refs['agentic-registry']
        entries = host.trees[host.commits[revision]['tree']['sha']]
        entries[registry.DOCUMENT] = ('120000', entries[registry.DOCUMENT][1])
        with self.assertRaises(Refusal):
            store.read()
        host = RegistryHost()
        host.trees['b' * 40]['.agentic-authority'] = ('100644', host.blob(b'adopter data'))
        with self.assertRaises(Refusal):
            registry.Registry(host, coordinates()).write(None, intent())
        self.assertEqual(host.writes, [])

    def test_last_moment_divergent_writer_is_preserved(self):
        host = RegistryHost()
        store = registry.Registry(host, coordinates())
        value = intent()
        store.write(None, value)
        operation_id = configuration_operation(store)
        before = host.refs['agentic-registry']
        foreign = 'e' * 40
        host.commits[foreign] = {'tree': host.commits[before]['tree'], 'parents': [{'sha': before}]}
        host.before_patch = lambda: host.refs.update({'agentic-registry': foreign})
        changed = copy.deepcopy(value)
        changed.update(state='blocked', generation=2)
        with self.assertRaises(Refusal):
            store.write(digest(value), changed, operation_id=operation_id, before_effect=lambda: None)
        self.assertEqual(host.refs['agentic-registry'], foreign)

    def test_registry_commit_does_not_change_approved_software_commit(self):
        host = RegistryHost()
        store = registry.Registry(host, coordinates())
        value = intent()
        store.write(None, value)
        record = store.binding()
        self.assertEqual(record['deployment'], value)
        self.assertNotEqual(record['configuration_revision'], host.refs['main'])
        self.assertEqual(record['branch_head'], host.refs['agentic-registry'])
        self.assertEqual(host.refs['main'], 'a' * 40)
        self.assertEqual(store.read(), value)

    def test_stale_writer_and_software_drift_fail_closed(self):
        host = RegistryHost()
        store = registry.Registry(host, coordinates())
        value = intent()
        store.write(None, value)
        changed = copy.deepcopy(value)
        changed['generation'] += 1
        changed['state'] = 'blocked'
        with self.assertRaises(Refusal):
            store.write('0' * 64, changed)
        host.refs['main'] = 'f' * 40
        with self.assertRaises(Refusal):
            store.read()

    def test_lost_registry_ack_is_resumable_without_duplicate_update(self):
        host = RegistryHost()
        store = registry.Registry(host, coordinates())
        value = intent()
        store.write(None, value)
        operation_id = configuration_operation(store)
        changed = copy.deepcopy(value)
        changed.update(generation=2, state='blocked')
        host.lose_ack = True
        with self.assertRaises(OSError):
            store.write(digest(value), changed, operation_id=operation_id, before_effect=lambda: None)
        store.write(digest(value), changed, operation_id=operation_id, before_effect=lambda: None)
        self.assertEqual(store.read(), changed)

    def test_configuration_digest_excludes_transition_fields_but_binds_expiry(self):
        value = intent()
        config = authority_protocol.configuration_digest(value)
        active = copy.deepcopy(value)
        active.update(generation=2, state='active', qualification='e' * 64)
        self.assertEqual(authority_protocol.configuration_digest(active), config)
        active['expires'] += 1
        self.assertNotEqual(authority_protocol.configuration_digest(active), config)


if __name__ == '__main__':
    unittest.main()
