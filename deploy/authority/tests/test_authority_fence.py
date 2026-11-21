"""One durable admin-owned fence serializes configuration and merge attempts."""
import backend_test_support
import copy
import unittest

from test_authority_registry import RegistryHost, coordinates, intent
from trusted_ci_policy import Refusal, digest
import registry


def pending(binding, kind='merge', identity='1' * 32):
    d = binding['deployment']
    return dict(kind=kind, operation_id=identity, scope_digest=None if kind == 'merge' else 'a' * 64,
        repository_id=d['policy']['repository_id'],
        target=d['policy']['target'], configuration_revision=binding['configuration_revision'],
        deployment_digest=digest(d), workflow_sha=d['policy']['workflow_sha'], run_id=99, attempt=1,
        created=1000, execution_deadline=1300, pr=7 if kind == 'merge' else None,
        head='2' * 40 if kind == 'merge' else None, base='5' * 40 if kind == 'merge' else None,
        merge='3' * 40 if kind == 'merge' else None)


class FenceContracts(unittest.TestCase):
    def test_inactivation_keeps_context_but_reactivation_and_requalification_require_fresh_context(self):
        host, store, before = self.prepared()
        config = pending(before, 'configuration')
        store.acquire_operation(before['branch_head'], before['configuration_revision'], config)
        active = copy.deepcopy(before['deployment'])
        active.update(generation=2, state='active', qualification='a' * 64)
        write = lambda old, new: store.write(digest(old), new, operation_id=config['operation_id'], before_effect=lambda: None)
        write(before['deployment'], active)
        blocked = copy.deepcopy(active)
        blocked.update(generation=3, state='blocked', qualification=None)
        write(active, blocked)
        for state, qualification in [('active', 'a' * 64), ('active', 'b' * 64), ('qualification', 'b' * 64)]:
            changed = copy.deepcopy(blocked)
            changed.update(generation=4, state=state, qualification=qualification)
            with self.subTest(state=state, qualification=qualification), self.assertRaises(Refusal):
                write(blocked, changed)

    def test_activated_configuration_cannot_change_without_a_never_reused_context(self):
        host, store, before = self.prepared()
        config = pending(before, 'configuration')
        store.acquire_operation(before['branch_head'], before['configuration_revision'], config)
        active = copy.deepcopy(before['deployment'])
        active.update(generation=2, state='active', qualification='a' * 64)
        store.write(digest(before['deployment']), active, operation_id=config['operation_id'], before_effect=lambda: None)
        changed = copy.deepcopy(active)
        changed.update(generation=3, state='qualification', qualification=None)
        changed['expires'] += 1
        with self.assertRaises(Refusal):
            store.write(digest(active), changed, operation_id=config['operation_id'], before_effect=lambda: None)
        changed['policy'].update(epoch='next_epoch', check_name='AGENTIC next_epoch')
        store.write(digest(active), changed, operation_id=config['operation_id'], before_effect=lambda: None)
        reused = copy.deepcopy(changed)
        reused['generation'] = 4
        reused['policy']['epoch'] = active['policy']['epoch']
        with self.assertRaises(Refusal):
            store.write(digest(changed), reused, operation_id=config['operation_id'], before_effect=lambda: None)

    def prepared(self):
        host = RegistryHost()
        store = registry.Registry(host, coordinates())
        store.write(None, intent())
        return host, store, store.binding()

    def test_fence_commits_preserve_deployment_identity_and_generation(self):
        host, store, before = self.prepared()
        operation = pending(before)
        acquired = store.acquire_operation(before['branch_head'], before['configuration_revision'], operation)
        self.assertNotEqual(before['branch_head'], acquired['branch_head'])
        for key in ('deployment', 'configuration_revision', 'deployment_digest', 'software_revision'):
            self.assertEqual(before[key], acquired[key])
        self.assertEqual(acquired['fence']['pending'], operation)
        self.assertNotIn('revision', acquired)

    def test_no_expiry_unlock_or_config_write_during_pending_merge(self):
        host, store, before = self.prepared()
        store.acquire_operation(before['branch_head'], before['configuration_revision'], pending(before))
        current = store.binding()
        with self.assertRaises(Refusal):
            store.acquire_operation(current['branch_head'], current['configuration_revision'], pending(current, 'configuration'))
        changed = copy.deepcopy(before['deployment'])
        changed.update(generation=2, state='blocked')
        with self.assertRaises(Refusal):
            store.write(digest(before['deployment']), changed)
        self.assertEqual(store.binding()['fence']['pending'], pending(before))

    def test_divergent_acquisition_and_stale_configuration_are_rejected(self):
        host, store, before = self.prepared()
        foreign = 'e' * 40
        host.commits[foreign] = dict(tree=host.commits[before['branch_head']]['tree'],
                                    parents=[{'sha': before['branch_head']}])
        host.before_patch = lambda: host.refs.update({'agentic-registry': foreign})
        with self.assertRaises(Refusal):
            store.acquire_operation(before['branch_head'], before['configuration_revision'], pending(before))
        self.assertEqual(host.refs['agentic-registry'], foreign)
        now = store.binding()
        forged = pending(now)
        forged['configuration_revision'] = before['branch_head']
        with self.assertRaises(Refusal):
            store.acquire_operation(now['branch_head'], now['configuration_revision'], forged)

    def test_config_write_requires_owned_fence_and_keeps_it_pending(self):
        host, store, before = self.prepared()
        config = pending(before, 'configuration')
        store.acquire_operation(before['branch_head'], before['configuration_revision'], config)
        changed = copy.deepcopy(before['deployment'])
        changed.update(generation=2, state='blocked')
        with self.assertRaises(Refusal):
            store.write(digest(before['deployment']), changed, operation_id='2' * 32)
        store.write(digest(before['deployment']), changed, operation_id=config['operation_id'], before_effect=lambda: None)
        after = store.binding()
        self.assertNotEqual(after['configuration_revision'], before['configuration_revision'])
        self.assertEqual(after['fence']['pending'], config)

    def test_finalization_is_cas_bound_and_never_reuses_completed_operation(self):
        host, store, before = self.prepared()
        operation = pending(before)
        current = store.acquire_operation(before['branch_head'], before['configuration_revision'], operation)
        terminal = {'operation_id': operation['operation_id'], 'sequence': 1,
                    'kind': 'not-submitted', 'receipt_digest': 'a' * 64}
        with self.assertRaises(Refusal):
            store.finalize_operation(before['branch_head'], terminal)
        after = store.finalize_operation(current['branch_head'], terminal)
        self.assertIsNone(after['fence']['pending'])
        self.assertEqual(after['configuration_revision'], before['configuration_revision'])
        with self.assertRaises(Refusal):
            store.acquire_operation(after['branch_head'], after['configuration_revision'], operation)


if __name__ == '__main__':
    unittest.main()
