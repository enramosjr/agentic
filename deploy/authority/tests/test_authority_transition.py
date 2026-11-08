"""Local host-transition ordering and interruption recovery, not qualification."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

from test_authority_registry import RegistryHost, coordinates, intent
from test_authority_fence import pending
from test_authority_reconcile import Host
from configuration import ConfigurationSession
from trusted_ci_policy import Refusal, digest
import registry
import reconcile
from transition import ContextTransition


class TransitionHost(Host):
    def __init__(self):
        super().__init__()
        self.rules[0].update(target='branch', conditions={'ref_name': {'include': ['refs/heads/main'], 'exclude': []}})
        self.fail_delete = False
        self.lose_delete_ack = False
        self.hide_new_effective = False
        self.substitute_repository = False
        self.effective_defect = None
        self.events = []
    def get(self, path):
        if self.substitute_repository and path == '/repos/owner/project':
            return {'id': 789, 'default_branch': 'main', 'allow_merge_commit': True}
        if '/rulesets/' in path:
            identity = int(path.rsplit('/', 1)[1].split('?')[0])
            return copy.deepcopy(next(r for r in self.rules if r['id'] == identity))
        return super().get(path)
    def post(self, path, data):
        value = super().post(path, data)
        self.events.append(('create', value['id']))
        return value
    def fetch(self, path, method='GET', **kwargs):
        if method == 'DELETE' and '/rulesets/' in path:
            if self.fail_delete:
                self.fail_delete = False
                raise OSError('synthetic interruption before owned deletion')
            identity = int(path.rsplit('/', 1)[1])
            self.events.append(('delete', identity))
            self.rules = [r for r in self.rules if r['id'] != identity]
            if self.lose_delete_ack:
                self.lose_delete_ack = False
                raise OSError('synthetic interruption after owned deletion')
            return b''
        raise AssertionError(path)
    def pages(self, path, collection=None):
        result = copy.deepcopy(super().pages(path, collection))
        if self.hide_new_effective and '/rules/branches/' in path:
            return [r for r in result if r['ruleset_id'] < 103]
        if self.effective_defect and '/rules/branches/' in path:
            if self.effective_defect == 'missing_check':
                return [r for r in result if not (r['ruleset_id'] >= 103 and r['type'] == 'required_status_checks')]
            for item in result:
                if item['ruleset_id'] >= 103 and item['type'] == 'required_status_checks':
                    key = 'context' if self.effective_defect == 'wrong_context' else 'integration_id'
                    item['parameters']['required_status_checks'][0][key] = 'other' if key == 'context' else 999
        return result


class GenerationTransition(unittest.TestCase):
    def test_repository_substitution_or_uninstalled_software_refuses_before_host_writes(self):
        for defect in ('repository', 'software'):
            target, store, session, desired = self.prepared()
            flow = ContextTransition(target, store, session)
            if defect == 'repository':
                target.substitute_repository = True
            else:
                desired['policy']['workflow_sha'] = 'f' * 40
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                flow.preview(desired)
            self.assertEqual(target.events, [])

    def prepared(self):
        host = RegistryHost()
        store = registry.Registry(host, coordinates())
        store.write(None, intent())
        scope = {'rules': ['owner/project'], 'registry': ['owner/authority:agentic-registry']}
        def acquire(identity, sequence):
            before = store.binding()
            op = pending(before, 'configuration', identity)
            op['scope_digest'] = digest(scope)
            store.acquire_operation(before['branch_head'], before['configuration_revision'], op)
            return ConfigurationSession(store, identity, sequence,
                {'workflow_sha': 'a' * 40, 'run_id': 99, 'attempt': 1}, scope, lambda: 1001)
        session = acquire('1' * 32, 1)
        target = TransitionHost()
        reconciler = reconcile.Reconciler(target, store, lambda: 1001, session=session)
        reconciler.apply(digest(reconciler.preview()))
        current = store.read()
        active = copy.deepcopy(current)
        active.update(generation=current['generation'] + 1, state='active', qualification='a' * 64)
        session.write_configuration(digest(current), active)
        bound = store.binding()
        store.finalize_operation(bound['branch_head'], {'operation_id': '1' * 32, 'sequence': 1,
            'kind': 'configuration-complete', 'receipt_digest': 'a' * 64})
        session = acquire('2' * 32, 2)
        desired = copy.deepcopy(active)
        desired.update(generation=active['generation'] + 1, state='qualification', qualification=None)
        desired['policy'].update(epoch='epoch_next', check_name='AGENTIC epoch_next')
        target.events.clear()
        return target, store, session, desired

    def test_installs_effective_new_gate_before_retiring_owned_controls_and_updating_registry(self):
        target, store, session, desired = self.prepared()
        before = store.read()
        foreign = copy.deepcopy(target.rules[0])
        flow = ContextTransition(target, store, session)
        plan = flow.preview(desired)
        result = flow.apply(plan, digest(plan))
        self.assertEqual([kind for kind, _ in target.events], ['create', 'create', 'delete', 'delete'])
        self.assertEqual(target.rules[0], foreign)
        self.assertEqual(store.read()['policy']['epoch'], 'epoch_next')
        self.assertEqual(store.read()['state'], 'qualification')
        self.assertFalse(result['enforcement_active'])
        self.assertIsNotNone(store.binding()['fence']['pending'])
        self.assertNotEqual(store.read()['resources']['acceptance_rule'], before['resources']['acceptance_rule'])

    def test_interruption_preserves_old_registry_and_resumes_without_duplicate_rules(self):
        target, store, session, desired = self.prepared()
        before = store.read()
        flow = ContextTransition(target, store, session)
        plan = flow.preview(desired)
        target.fail_delete = True
        with self.assertRaises(OSError):
            flow.apply(plan, digest(plan))
        self.assertEqual(store.read(), before)
        self.assertEqual([kind for kind, _ in target.events], ['create', 'create'])
        flow.apply(plan, digest(plan))
        self.assertEqual([kind for kind, _ in target.events], ['create', 'create', 'delete', 'delete'])

    def test_lost_create_or_delete_ack_recovers_only_exact_owned_rules(self):
        for defect in ('create', 'delete'):
            with self.subTest(defect=defect):
                target, store, session, desired = self.prepared()
                flow = ContextTransition(target, store, session)
                plan = flow.preview(desired)
                if defect == 'create':
                    target.lose_ack = True
                else:
                    target.lose_delete_ack = True
                before = store.read()
                with self.assertRaises(OSError):
                    flow.apply(plan, digest(plan))
                self.assertEqual(store.read(), before)
                flow.apply(plan, digest(plan))
                self.assertEqual(len(target.rules), 3)
                self.assertEqual(len({r['name'] for r in target.rules}), 3)
                self.assertEqual(len(target.writes), 4)  # Two initial + two new, never duplicate creates.

    def test_final_registry_lost_ack_recovers_the_exact_committed_transition(self):
        target, store, session, desired = self.prepared()
        flow = ContextTransition(target, store, session)
        plan = flow.preview(desired)
        store.api.lose_ack = True
        with self.assertRaises(OSError):
            flow.apply(plan, digest(plan))
        committed = copy.deepcopy(store.read())
        self.assertEqual(committed['policy']['epoch'], 'epoch_next')
        events = list(target.events)
        result = flow.apply(plan, digest(plan))
        self.assertEqual(result['state'], 'qualification')
        self.assertEqual(store.read(), committed)
        self.assertEqual(target.events, events)
        self.assertIsNotNone(store.binding()['fence']['pending'])

    def test_fresh_authenticated_session_can_resume_a_committed_transition(self):
        target, store, session, desired = self.prepared()
        flow = ContextTransition(target, store, session)
        plan = flow.preview(desired)
        store.api.lose_ack = True
        with self.assertRaises(OSError):
            flow.apply(plan, digest(plan))
        restarted = ConfigurationSession(store, session.operation_id, session.sequence,
            dict(session.owner), copy.deepcopy(session.scope), lambda: 1001)
        events, writes, refs = list(target.events), list(store.api.writes), dict(store.api.refs)
        ContextTransition(target, store, restarted).apply(plan, digest(plan))
        self.assertEqual(target.events, events)
        self.assertEqual(store.api.writes, writes)
        self.assertEqual(store.api.refs, refs)
        self.assertIsNotNone(store.binding()['fence']['pending'])

    def test_final_registry_readback_failure_recovers_without_replaying_mutations(self):
        target, store, session, desired = self.prepared()
        flow = ContextTransition(target, store, session)
        plan = flow.preview(desired)
        original_fetch, original_get = store.api.fetch, store.api.get
        fail_read = [False]
        def fetch(path, method='GET', **kwargs):
            result = original_fetch(path, method=method, **kwargs)
            if method == 'PATCH':
                fail_read[0] = True
            return result
        def get(path):
            if fail_read[0]:
                fail_read[0] = False
                raise OSError('synthetic final readback interruption')
            return original_get(path)
        store.api.fetch, store.api.get = fetch, get
        with self.assertRaises(OSError):
            flow.apply(plan, digest(plan))
        events, writes, refs = list(target.events), list(store.api.writes), dict(store.api.refs)
        flow.apply(plan, digest(plan))
        self.assertEqual(target.events, events)
        self.assertEqual(store.api.writes, writes)
        self.assertEqual(store.api.refs, refs)

    def test_lost_ack_recovery_rejects_unrelated_progress_and_changed_host_controls(self):
        for defect in ('record', 'parent', 'registry_data', 'foreign', 'effective', 'owner',
                       'expired', 'sibling', 'software', 'new_rule', 'pending_owner', 'pending_sequence'):
            with self.subTest(defect=defect):
                target, store, session, desired = self.prepared()
                flow = ContextTransition(target, store, session)
                plan = flow.preview(desired)
                store.api.lose_ack = True
                with self.assertRaises(OSError):
                    flow.apply(plan, digest(plan))
                bound = store.binding()
                host = store.api
                commit = host.commits[bound['branch_head']]
                tree = host.trees[commit['tree']['sha']]
                if defect == 'record':
                    import json
                    changed = copy.deepcopy(bound['deployment'])
                    changed['expires'] += 1
                    tree[registry.DOCUMENT] = ('100644', host.blob(json.dumps(changed).encode()))
                elif defect == 'parent':
                    commit['parents'] = [{'sha': 'f' * 40}]
                elif defect == 'registry_data':
                    tree['README.md'] = ('100644', host.blob(b'unrelated mutation'))
                elif defect == 'foreign':
                    target.rules[0]['rules'].append({'type': 'deletion'})
                elif defect == 'effective':
                    target.effective_defect = 'missing_check'
                elif defect == 'owner':
                    session.owner['run_id'] = 100
                elif defect == 'expired':
                    session.clock = lambda: 1300
                elif defect == 'sibling':
                    foreign = 'f' * 40
                    host.commits[foreign] = dict(sha=foreign, message='unrelated commit', tree=commit['tree'],
                                                parents=[{'sha': bound['branch_head']}])
                    host.refs['agentic-registry'] = foreign
                elif defect == 'software':
                    host.refs['main'] = 'f' * 40
                elif defect == 'new_rule':
                    target.rules[-1]['bypass_actors'][0]['bypass_mode'] = 'always'
                else:
                    import json
                    changed = copy.deepcopy(bound['fence'])
                    if defect == 'pending_owner':
                        changed['pending']['run_id'] = 100
                    else:
                        changed['sequence'] = 3
                        changed['completed'].append(dict(operation_id='3' * 32, sequence=2,
                            kind='configuration-complete', receipt_digest='a' * 64))
                    tree[registry.OPERATION] = ('100644', host.blob(json.dumps(changed).encode()))
                events = list(target.events)
                writes, refs = list(host.writes), dict(host.refs)
                with self.assertRaises(Refusal):
                    flow.apply(plan, digest(plan))
                self.assertEqual(target.events, events)
                self.assertEqual(host.writes, writes)
                self.assertEqual(host.refs, refs)
                self.assertIsNotNone(store.binding(check_software=False)['fence']['pending'])

    def test_partial_effective_rules_cannot_retire_old_gate_even_with_both_new_ids(self):
        for defect in ('missing_check', 'wrong_context', 'wrong_issuer'):
            with self.subTest(defect=defect):
                target, store, session, desired = self.prepared()
                flow = ContextTransition(target, store, session)
                plan = flow.preview(desired)
                before = store.read()
                target.effective_defect = defect
                with self.assertRaises(Refusal):
                    flow.apply(plan, digest(plan))
                self.assertEqual(store.read(), before)
                self.assertFalse(any(kind == 'delete' for kind, _ in target.events))

    def test_ineffective_new_gate_never_deletes_old_rules_or_advances_registry(self):
        target, store, session, desired = self.prepared()
        flow = ContextTransition(target, store, session)
        plan = flow.preview(desired)
        before = store.read()
        target.hide_new_effective = True
        with self.assertRaises(Refusal):
            flow.apply(plan, digest(plan))
        self.assertEqual(store.read(), before)
        self.assertFalse(any(kind == 'delete' for kind, _ in target.events))

    def test_apply_revalidates_plan_and_negative_control_detects_missing_guard(self):
        def probe(broken=False):
            target, store, session, desired = self.prepared()
            flow = ContextTransition(target, store, session)
            plan = flow.preview(desired)
            plan['desired']['policy']['target'] = 'other'
            plan['new_controls'] = reconcile.desired_rules(plan['desired'])
            def assertion():
                with self.assertRaises(Refusal):
                    flow.apply(plan, digest(plan))
                self.assertEqual(target.events, [])
            if broken:
                with patch.object(flow, 'validate_desired', return_value=None), self.assertRaises(AssertionError):
                    assertion()
            else:
                assertion()
        probe()
        probe(broken=True)

    def test_stale_approval_foreign_drift_and_reused_context_refuse_without_writes(self):
        for defect in ('approval', 'foreign', 'context'):
            target, store, session, desired = self.prepared()
            flow = ContextTransition(target, store, session)
            if defect == 'context':
                desired['policy']['check_name'] = store.read()['policy']['check_name']
                with self.assertRaises(Refusal):
                    flow.preview(desired)
            else:
                plan = flow.preview(desired)
                if defect == 'foreign':
                    target.rules[0]['rules'].append({'type': 'deletion'})
                with self.assertRaises(Refusal):
                    flow.apply(plan, '0' * 64 if defect == 'approval' else digest(plan))
            self.assertEqual(target.events, [])


if __name__ == '__main__':
    unittest.main()
