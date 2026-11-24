"""Native-only retained merge handover and atomic paired storage contracts."""
import backend_test_support
import copy
import unittest

import operation_fence
import registry
from test_authority_fence import pending
from test_authority_registry import RegistryHost, coordinates, intent
from trusted_ci_policy import Refusal, digest


class NativeHandover(unittest.TestCase):
    def prepared(self):
        host = RegistryHost()
        store = registry.Registry(host, coordinates())
        store.write(None, intent())
        before = store.binding()
        merge = pending(before)
        bound = store.acquire_operation(before['branch_head'], before['configuration_revision'], merge)
        config = pending(bound, 'configuration', '2' * 32)
        config.update(run_id=None, attempt=None,
                      setup=dict(operator_id=7, installation_id=8, approval_digest='b' * 64))
        return host, store, bound, config

    def handover(self):
        host, store, before, config = self.prepared()
        after = store.handover_operation(before['branch_head'], before['configuration_revision'], config,
                                         'c' * 64, lambda: None, lambda: 1001)
        return host, store, before, config, after

    def transitioned(self):
        host, store, before, config, acquired = self.handover()
        changed = copy.deepcopy(before['deployment'])
        changed['generation'] += 1
        changed['policy'].update(epoch='next-context', check_name='next-context-check')
        changed['resources'].update(acceptance_rule='81', updates_rule='82')
        store.write(digest(before['deployment']), changed, operation_id=config['operation_id'], before_effect=lambda: None)
        return host, store, before, config, acquired, store.binding()

    @staticmethod
    def terminals(before, config):
        return (dict(operation_id=before['fence']['pending']['operation_id'], sequence=before['fence']['sequence'],
                     kind='not-submitted', receipt_digest='d' * 64),
                dict(operation_id=config['operation_id'], sequence=before['fence']['sequence'] + 1,
                     kind='configuration-complete', receipt_digest='e' * 64))

    def test_handover_retains_exact_original_merge_and_no_completion(self):
        host, store, before, config, after = self.handover()
        fence = after['fence']
        self.assertEqual(fence['schema_version'], 3)
        self.assertEqual(fence['sequence'], before['fence']['sequence'] + 1)
        self.assertEqual(fence['pending'], config)
        self.assertEqual(fence['completed'], before['fence']['completed'])
        self.assertEqual(fence['retained'], dict(sequence=before['fence']['sequence'],
            operation=before['fence']['pending'], binding=before, intent_digest='c' * 64))
        self.assertEqual(after['deployment'], before['deployment'])
        self.assertEqual(store.authenticate_setup_transition(before, {registry.OPERATION: fence}, after), after)
        for key, bad in [('sequence', 3), ('operation', config), ('intent_digest', 'bad')]:
            forged = copy.deepcopy(fence); forged['retained'][key] = bad
            with self.subTest(key=key), self.assertRaises(Refusal): operation_fence.validate(forged)

    def test_ordinary_acquire_and_single_terminal_refuse_handover(self):
        host, store, before, config, after = self.handover()
        writes = copy.deepcopy(host.writes)
        with self.assertRaises(Refusal):
            store.acquire_operation(after['branch_head'], after['configuration_revision'], config)
        terminal = self.terminals(before, config)[1]
        with self.assertRaises(Refusal): store.finalize_operation(after['branch_head'], terminal)
        forged = copy.deepcopy(after['fence']); forged['completed'].append(terminal); forged['pending'] = None
        with self.assertRaises(Refusal):
            store._replace(after, {registry.OPERATION: forged}, terminal_only=True)
        self.assertEqual(host.writes, writes)

    def test_pair_settlement_is_one_ordered_transition_back_to_v2(self):
        host, store, before, config, acquired, current = self.transitioned()
        old, new = self.terminals(before, config)
        after = store.finalize_handover(current['branch_head'], old, new, lambda: None, lambda: 1002)
        self.assertEqual(after['fence']['schema_version'], 2)
        self.assertNotIn('retained', after['fence'])
        self.assertIsNone(after['fence']['pending'])
        self.assertEqual(after['fence']['completed'], [old, new])
        self.assertEqual(after['deployment'], current['deployment'])
        self.assertEqual(store.authenticate_setup_transition(current, {registry.OPERATION: after['fence']}, after), after)
        writes = copy.deepcopy(host.writes)
        with self.assertRaises(Refusal):
            store.finalize_handover(current['branch_head'], old, new, lambda: None, lambda: 1002)
        self.assertEqual(host.writes, writes)

    def test_lost_pair_ack_recovers_exact_commit_without_second_write(self):
        host, store, before, config, acquired, current = self.transitioned()
        old, new = self.terminals(before, config)
        host.lose_ack = True
        after = store.finalize_handover(current['branch_head'], old, new, lambda: None, lambda: 1002)
        self.assertIsNone(after['fence']['pending'])
        self.assertEqual(len(after['fence']['completed']), 2)

    def test_unknown_handover_ack_recovers_read_only_and_replay_refuses(self):
        host, store, before, config = self.prepared()
        host.lose_ack = True
        with self.assertRaisesRegex(OSError, 'lost registry'):
            store.handover_operation(before['branch_head'], before['configuration_revision'], config,
                                     'c' * 64, lambda: None, lambda: 1001)
        after = store.binding()
        writes = copy.deepcopy(host.writes)
        self.assertEqual(store.authenticate_setup_progress(before, {registry.OPERATION: after['fence']}), after)
        with self.assertRaises(Refusal):
            store.handover_operation(before['branch_head'], before['configuration_revision'], config,
                                     'c' * 64, lambda: None, lambda: 1001)
        self.assertEqual(host.writes, writes)

    def test_divergent_cas_cannot_install_handover_or_claim_pair_completion(self):
        for pair in (False, True):
            if pair:
                host, store, before, config, acquired, current = self.transitioned()
            else:
                host, store, current, config = self.prepared(); before = current
            foreign = 'e' * 40
            host.commits[foreign] = dict(tree=host.commits[current['branch_head']]['tree'],
                                        parents=[dict(sha=current['branch_head'])])
            host.before_patch = lambda: host.refs.update({'agentic-registry': foreign})
            with self.subTest(pair=pair), self.assertRaises(Refusal):
                if pair:
                    old, new = self.terminals(before, config)
                    store.finalize_handover(current['branch_head'], old, new, lambda: None, lambda: 1002)
                else:
                    store.handover_operation(current['branch_head'], current['configuration_revision'], config,
                                             'c' * 64, lambda: None, lambda: 1001)
            self.assertEqual(host.refs['agentic-registry'], foreign)

    def test_retained_binding_and_prefix_cannot_be_rewritten_or_nested(self):
        host, store, before, config, after = self.handover()
        for fault in ('nested', 'binding-digest', 'config-digest', 'sequence', 'operation-id', 'contexts', 'extra'):
            value = copy.deepcopy(after['fence'])
            if fault == 'nested': value['retained']['binding']['fence'] = copy.deepcopy(value)
            elif fault == 'binding-digest': value['retained']['binding']['deployment_digest'] = '0' * 64
            elif fault == 'config-digest': value['pending']['deployment_digest'] = '0' * 64
            elif fault == 'sequence': value['sequence'] += 1
            elif fault == 'operation-id': value['pending']['operation_id'] = value['retained']['operation']['operation_id']
            elif fault == 'contexts': value['contexts'][0]['epoch'] = 'substituted'
            else: value['retained']['extra'] = True
            with self.subTest(fault=fault), self.assertRaises(Refusal): operation_fence.validate(value)

    def test_retained_policy_requires_its_exact_nonempty_context_history(self):
        host, store, before, config, after = self.handover()
        for empty in (False, True):
            value = copy.deepcopy(after['fence'])
            contexts = [] if empty else [dict(epoch='substituted', check_name='substituted', activated=False)]
            value['retained']['binding']['fence']['contexts'] = contexts
            value['contexts'] = copy.deepcopy(contexts)
            with self.subTest(empty=empty), self.assertRaises(Refusal): operation_fence.validate(value)

    def test_v3_state_cannot_be_created_for_active_deployment(self):
        host, store, before, config, after = self.handover()
        value = copy.deepcopy(after['fence'])
        d = value['retained']['binding']['deployment']
        d.update(state='active', qualification='a' * 64)
        value['retained']['binding']['deployment_digest'] = digest(d)
        value['retained']['operation']['deployment_digest'] = digest(d)
        value['retained']['binding']['fence']['pending']['deployment_digest'] = digest(d)
        value['pending']['deployment_digest'] = digest(d)
        with self.assertRaises(Refusal): operation_fence.validate(value)

    def test_invalid_or_expired_handover_cannot_write(self):
        for fault in ('owner', 'intent', 'deadline', 'expired', 'late', 'same-id', 'future', 'boolean-clock', 'float-created'):
            host, store, before, config = self.prepared()
            now = [1001]
            marker = 'c' * 64
            if fault == 'owner': config.pop('setup'); config.update(run_id=99, attempt=1)
            if fault == 'intent': marker = 'bad'
            if fault == 'deadline': config['execution_deadline'] += 1
            if fault == 'expired': now[0] = config['execution_deadline']
            if fault == 'same-id':
                config['operation_id'] = before['fence']['pending']['operation_id']
            if fault == 'future': config['created'] = 1100
            if fault == 'boolean-clock': now[0] = True
            if fault == 'float-created': config['created'] = 1000.0
            writes = copy.deepcopy(host.writes)
            def guard():
                if fault == 'late': now[0] = config['execution_deadline']
            with self.subTest(fault=fault), self.assertRaises(Refusal):
                store.handover_operation(before['branch_head'], before['configuration_revision'], config,
                                         marker, guard, lambda: now[0])
            self.assertEqual(host.writes, writes)

    def test_pair_refuses_unchanged_context_wrong_terminals_and_expiry(self):
        host, store, before, config, acquired = self.handover()
        old, new = self.terminals(before, config)
        with self.assertRaises(Refusal):
            store.finalize_handover(acquired['branch_head'], old, new, lambda: None, lambda: 1002)
        for fault in ('order', 'kind', 'sequence', 'expired', 'late'):
            host, store, before, config, acquired, current = self.transitioned()
            old, new = self.terminals(before, config)
            now = [1002]
            if fault == 'order': old, new = new, old
            if fault == 'kind': old['kind'] = 'merged'
            if fault == 'sequence': new['sequence'] += 1
            if fault == 'expired': now[0] = config['execution_deadline']
            writes = copy.deepcopy(host.writes)
            def guard():
                if fault == 'late': now[0] = config['execution_deadline']
            with self.subTest(fault=fault), self.assertRaises(Refusal):
                store.finalize_handover(current['branch_head'], old, new, guard, lambda: now[0])
            self.assertEqual(host.writes, writes)

    def test_v3_configuration_write_cannot_change_other_fields_or_repeat_context(self):
        for field in ('expires', 'state', 'account', 'epoch', 'check_name'):
            host, store, before, config, after = self.handover()
            changed = copy.deepcopy(before['deployment']); changed['generation'] += 1
            changed['policy'].update(epoch='next-context', check_name='next-context-check')
            if field == 'expires': changed['expires'] += 1
            elif field == 'state': changed['state'] = 'blocked'
            elif field == 'account': changed['account'] = 'another-owner'
            else: changed['policy'][field] = before['deployment']['policy'][field]
            writes = copy.deepcopy(host.writes)
            with self.subTest(field=field), self.assertRaises(Refusal):
                store.write(digest(before['deployment']), changed, operation_id=config['operation_id'], before_effect=lambda: None)
            self.assertEqual(host.writes, writes)


if __name__ == '__main__':
    unittest.main()
