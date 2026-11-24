"""Ninth CLOSED evidence; GitHub and OCI transport boundaries are modeled."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

import authority_release
import broker_finalize
import merge_transport
import service
import trial_case
import trial_controller
import trial_host_case
import trial_launch
import test_authority_trial_forged_case as forged_fixture
import test_authority_trial_negative_case as negative_fixture
import test_authority_trial_new_head_case as new_head_fixture
import test_authority_trial_outage_terminal as outage_fixture
import test_authority_trial_spoof_case as spoof_fixture
from trusted_ci_policy import Refusal, digest


class SpoofPrerequisiteContracts(unittest.TestCase):
    def fixture(self):
        p = dict(check_name='agentic-ci', app_id=11, reviewers=[5], coding_actors=[9])
        s = dict(head='a'*40, merge='b'*40)
        binding = dict(deployment=dict(policy=p))
        retained = dict(request=dict(snapshot=s), candidate=dict(submitted=dict(bot_id=9)))
        spoof = dict(id=999, name='agentic-ci', app=dict(id=99), status='completed', conclusion='success', head_sha=s['merge'])
        rules = [dict(type='required_status_checks', parameters=dict(required_status_checks=[dict(context='agentic-ci', integration_id=11)]))]
        reviews = [dict(id=1, user=dict(id=5, type='User'), state='APPROVED', commit_id=s['head'])]
        return binding, retained, dict(checks=[spoof], rules=rules, reviews=reviews)

    def test_exact_foreign_success_and_host_prerequisites_are_required(self):
        binding, retained, observation = self.fixture()
        trial_host_case._spoof_prerequisites(observation, binding, retained)
        for defect in ({'name': 'other'}, {'head_sha': '0'*40}, {'status': 'in_progress'}, {'conclusion': 'failure'},
                       {'app': dict(id=11)}, {'app': {}}, {'app': dict(id=True)}, {'app': dict(id=0)}):
            value = copy.deepcopy(observation); value['checks'][0].update(defect)
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                trial_host_case._spoof_prerequisites(value, binding, retained)
        value = copy.deepcopy(observation); value['checks'].clear()
        with self.assertRaisesRegex(Refusal, 'spoofed issuer success'):
            trial_host_case._spoof_prerequisites(value, binding, retained)
        value = copy.deepcopy(observation); value['checks'].append(dict(value['checks'][0], id=1000, app=dict(id=11)))
        with self.assertRaises(Refusal): trial_host_case._spoof_prerequisites(value, binding, retained)
        for part, wrong in (('reviews', []), ('rules', [])):
            value = copy.deepcopy(observation); value[part] = wrong
            with self.subTest(part=part), self.assertRaises(Refusal):
                trial_host_case._spoof_prerequisites(value, binding, retained)
        value = copy.deepcopy(observation); value['rules'][0]['parameters']['required_status_checks'].append(dict(context='other', integration_id=8))
        with self.assertRaises(Refusal): trial_host_case._spoof_prerequisites(value, binding, retained)

    def test_spoof_reader_is_not_the_mutation_negative_reader(self):
        binding, retained, observation = self.fixture()
        retained['candidate']['name'] = 'forged-records'
        with self.assertRaises(Refusal): trial_host_case._spoof_readback(None, retained, None, None, 0, None)
        with self.assertRaises(Refusal): trial_host_case._spoof_source(None, None, retained, None, None, None)
        for reader in (trial_host_case.bad_acceptance_terminal, trial_host_case.replaced_checks_terminal, trial_host_case.forged_records_terminal):
            retained['candidate']['name'] = 'spoofed-source'
            with self.assertRaises(Refusal): reader(None, None, retained, {}, {}, 0, original=None)


class Holds(unittest.TestCase):
    def test_observation_hold_precedes_transport(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        with self.assertRaises(authority_release.Held):
            trial_controller.Native(NoIO()).observe_terminal('prompt', 'spoofed-source', {})


@unittest.skipIf(getattr(negative_fixture.NativeNegative, '__unittest_skip__', False), 'optional cryptography required')
class SpoofedSourceTerminal(unittest.TestCase):
    fixture = negative_fixture.NativeNegative.fixture
    prepared = negative_fixture.NativeNegative.prepared
    connected = negative_fixture.NativeNegative.connected
    configured = negative_fixture.NativeNegative.configured
    exercise = negative_fixture.NativeNegative.exercise
    prepare = negative_fixture.NativeNegative.prepare
    forbidden = outage_fixture.OutageTerminal.forbidden
    document = outage_fixture.OutageTerminal.document
    closed = outage_fixture.OutageTerminal.closed

    def pending(self, args, fixture=spoof_fixture.Spoof):
        f = fixture(self, args); f.ninth()
        with patch.object(merge_transport, 'isolated', side_effect=AssertionError('spoof dispatched')), \
                patch.object(service, '_publish_bound', side_effect=AssertionError('spoof published genuine issuer')):
            f.observed(); f.host()
            self.assertEqual(f.run('broker')['state'], 'host-denied')
        return f

    def journal(self, f):
        return f.native.provision.store(f.native.provision.root/'trial-controller-spoofed-source')

    def case(self, f):
        publication = f.native.provision.store(f.native.provision.root/'trial-case-publication-spoofed-source').read()['value']
        case, record = trial_case.read(f.origin, publication['revision_bound'], lambda:f.clock[0])
        self.assertEqual(record, f.admission.record)
        return case

    def history(self, f, location):
        value = self.journal(f).read()['value']
        publication = f.native.provision.store(f.native.provision.root/'trial-case-publication-spoofed-source').read()['value']
        return value['history']+[dict(revision=publication['revision_bound'], terminal=location)]

    def observe(self, f, location):
        with self.forbidden(f), patch.object(service, '_source_token', side_effect=AssertionError('terminal mint')), \
                patch.object(trial_controller.Admission, 'task', side_effect=AssertionError('terminal task admission')):
            return trial_controller.Native(f.preparer)._observe_terminal('prompt', 'spoofed-source', location, f.source)

    def validate(self, f, location):
        from provenance import authenticated_document
        _, _, terminal = self.document(f, 'trial-case-terminal-')
        proof = authenticated_document(f.api, terminal['before']['deployment'], location, 'trial-case-terminal',
                                       f.admission.record['task_id'], f.clock[0])
        return trial_host_case.spoofed_source_terminal(f.api, f.admission.record, self.case(f), terminal, proof,
                                                       f.clock[0], original=f.origin)

    def test_connected_ninth_cleanup_and_tenth_selection(self):
        def check(*args):
            f = self.pending(args, new_head_fixture.NewHead)
            original = f.origin.binding()
            f.finalize()
            terminal_binding = f.observe()['binding']
            _, _, terminal = self.document(f, 'trial-case-terminal-')
            self.assertEqual(terminal['schema_version'], 2)
            self.assertNotIn('broker_receipt', terminal)
            self.assertEqual(digest(terminal['recovery']), terminal['after']['fence']['completed'][-1]['receipt_digest'])
            self.assertEqual(terminal['after'], terminal_binding)
            _, _, publication = self.document(f, 'trial-publication-observation-')
            self.assertIn(f.spoof, publication['observation']['checks'])
            self.assertFalse(any(a['name'].startswith(('evidence-', 'trial-publication-denial-')) for a in f.remote.artifacts))
            token = f.case_token; revoked = set(f.revoked)
            trial_launch.revoke(f.native.provision, f.origin_factory, name='spoofed-source')
            self.assertEqual(set(f.revoked)-revoked, {token})
            f.phase = 'prior'
            f.second('new-head', 119, 'fresh-tenth-prior')
            history = f.admission.value['history']
            self.assertEqual(len(history), 9)
            cases = [trial_case.read(f.origin, e['revision'], lambda:f.clock[0])[0] for e in history]
            self.assertEqual([c['candidate']['name'] for c in cases], list(trial_controller.CASE_CHAIN[:9]))
            for field in ('pr', 'head', 'task_id'):
                self.assertEqual(len({c['candidate']['submitted'][field] for c in cases}), 9)
            self.assertEqual(f.origin.binding(), original)
            self.assertEqual(f.merges, []); self.assertEqual(len(f.attempts), 7)
            self.assertIsNone(f.admission.binding['deployment']['qualification'])
            self.assertEqual(f.admission.binding['deployment']['state'], 'qualification')
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def test_validated_outcome_is_the_exact_required_check_denial(self):
        def check(*args):
            f, location = self.closed(args)
            outcome = self.validate(f, location)['document']['record']
            self.assertTrue(outcome['request_sent']); self.assertIsNone(outcome['broker_refusal'])
            self.assertEqual((outcome['denial_category'], outcome['denied_obligation']), ('required_check', f.p['check_name']))
            self.assertIn(outcome['http_status'], (403, 405, 422))
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def test_export_is_exact_acknowledged_and_not_stale(self):
        def check(*args):
            f = self.pending(args); instances = []; finalize = broker_finalize.Finalizer._finalize
            def track(instance, *pos, **kw): instances.append(instance); return finalize(instance, *pos, **kw)
            with patch.object(broker_finalize.Finalizer, '_finalize', track): result = f.finalize()
            instance = instances[-1]; r = f.admission.request
            value = instance._negative_evidence(r['operation_id'], r['sequence'], result)
            self.assertEqual(set(value), {'recovery', 'host_receipt'})
            value['host_receipt']['issued'] = 1
            self.assertNotEqual(instance._negative_evidence(r['operation_id'], r['sequence'], result), value)
            for op, seq, saved in (('0'*32, r['sequence'], result), (r['operation_id'], r['sequence']+1, result),
                                   (r['operation_id'], r['sequence'], {})):
                with self.assertRaises(Refusal): instance._negative_evidence(op, seq, saved)
            with self.assertRaises(Refusal): instance._finalize('invalid', 1, 1)
            with self.assertRaises(Refusal): instance._negative_evidence(r['operation_id'], r['sequence'], result)
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def test_legacy_terminal_refused_by_both_consumers(self):
        def check(*args):
            f, location = self.closed(args); before = self.journal(f).read()
            identity, member, value = self.document(f, 'trial-case-terminal-')
            value.update(schema_version=1); value.pop('recovery', None); value.pop('host_receipt', None)
            f.remote.replace(identity, value, member)
            with self.assertRaises(Refusal): self.observe(f, location)
            with self.assertRaises(Refusal):
                trial_case.baseline(f.origin, f.native.registry, f.admission.record, self.history(f, location), lambda:f.clock[0])
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt', 'new-head', f.source, phase='prior')
            self.assertEqual(self.journal(f).read(), before)
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def test_terminal_and_inventory_mutations_fail_closed(self):
        def check(*args):
            from test_authority_broker_evidence import stamp
            f, location = self.closed(args); self.validate(f, location); before = self.journal(f).read()
            identity, member, terminal = self.document(f, 'trial-case-terminal-')
            artifacts, raw = copy.deepcopy(f.remote.artifacts), copy.deepcopy(f.remote.raw)
            pages = f.api.pages
            for fault in ('schema', 'extra', 'request', 'certificate', 'envelope', 'receipt', 'producer', 'recovery', 'interval',
                          'gate', 'control-ready', 'not-submitted', 'dispatch', 'outcome', 'missing-host', 'receipt-late',
                          'duplicate', 'oversized'):
                f.remote.artifacts[:] = copy.deepcopy(artifacts); f.remote.raw.clear(); f.remote.raw.update(raw)
                value = copy.deepcopy(terminal)
                if fault == 'schema': value['schema_version'] = True
                if fault == 'extra': value['broker_receipt'] = {}
                if fault == 'request': value['request_digest'] = '0'*64
                if fault == 'certificate': value['certificate_digest'] = '0'*64
                if fault == 'envelope': value['recovery']['operation_digest'] = '0'*64
                if fault == 'receipt': value['host_receipt']['issued'] += 1
                if fault == 'producer': value['recovery']['producer']['id'] += 1
                if fault == 'recovery': value['recovery']['recovery']['job_id'] += 1
                if fault == 'interval': value['completed'] = 1
                if fault in ('gate', 'control-ready', 'not-submitted', 'dispatch', 'outcome'):
                    a = next(a for a in f.remote.artifacts if a['name'].endswith('-host-denied'))
                    f.remote.artifacts.append(dict(a, id=999999, name=a['name'].replace('-host-denied', '-'+fault)))
                if fault == 'missing-host':
                    f.remote.artifacts[:] = [a for a in f.remote.artifacts if not a['name'].startswith('trial-host-denial-')]
                if fault == 'receipt-late':
                    next(a for a in f.remote.artifacts if a['name'].endswith('-host-denied'))['created_at'] = stamp(f.clock[0]+1)
                f.remote.replace(identity, value, member)
                def inventory(path, collection=None):
                    entries = pages(path, collection)
                    if collection == 'artifacts' and '/runs/117/' in path:
                        if fault == 'duplicate': return entries+[dict(entries[0])]
                        if fault == 'oversized': return [dict(entries[0], id=i+1) for i in range(10001)]
                    return entries
                with self.subTest(fault=fault), patch.object(f.api, 'pages', side_effect=inventory), self.assertRaises(Refusal):
                    self.validate(f, location)
                with self.subTest(native=fault), patch.object(f.api, 'pages', side_effect=inventory), self.assertRaises(Refusal):
                    self.observe(f, location)
                self.assertEqual(self.journal(f).read(), before)
            f.remote.artifacts[:] = artifacts; f.remote.raw.clear(); f.remote.raw.update(raw)
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def test_host_and_publication_mutations_fail_closed(self):
        def check(*args):
            f, location = self.closed(args); self.validate(f, location); before = self.journal(f).read()
            for prefix, faults in (
                    ('trial-host-denial-', ('actor', 'request', 'status', 'boolean-status', 'category', 'obligation', 'parents',
                                            'tree', 'record', 'intent', 'publication', 'rules', 'reviews', 'success',
                                            'spoof-removed', 'spoof-authoritative', 'extra-negative')),
                    ('trial-publication-observation-', ('observation', 'authoritative', 'intent', 'task', 'controls', 'proofs',
                                                        'observed', 'evidence-input')),
                    ('publication-controls-', ('binding',)),
                    ('proof-merge-', ('expired', 'binding'))):
                identity, member, saved = self.document(f, prefix)
                metadata = copy.deepcopy(next(a for a in f.remote.artifacts if a['id'] == identity)); raw = f.remote.raw[identity]
                for fault in faults:
                    value = copy.deepcopy(saved)
                    if prefix == 'trial-host-denial-':
                        o = value['observation']
                        if fault == 'actor': o['actor_id'] += 1
                        if fault == 'request': o['request']['data']['sha'] = '0'*40
                        if fault == 'status': o['http_status'] = 500
                        if fault == 'boolean-status': o['http_status'] = True
                        if fault == 'category': o['denial_category'] = 'required_review'
                        if fault == 'obligation': o['denied_obligation'] = 'other-check'
                        if fault == 'parents': o['synthetic_commit']['parents'].reverse()
                        if fault == 'tree': o['synthetic_commit']['tree']['sha'] = '0'*40
                        if fault == 'record': value['record']['request_sent'] = False
                        if fault == 'intent': value['intent']['issued'] += 1000
                        if fault == 'publication': o['publication']['digest'] = '0'*64
                        if fault == 'rules': o['rules'] = []
                        if fault == 'reviews': o['reviews'] = []
                        if fault == 'success':
                            o['checks'].append(dict(name=f.p['check_name'], app=dict(id=f.p['app_id']), status='completed', conclusion='success'))
                        if fault == 'spoof-removed': o['checks'] = [c for c in o['checks'] if c.get('id') != f.spoof['id']]
                        if fault == 'spoof-authoritative':
                            for c in o['checks']:
                                if c.get('id') == f.spoof['id']: c['app'] = dict(id=f.p['app_id'])
                        if fault == 'extra-negative': o['negative'] = {}
                    elif prefix == 'trial-publication-observation-':
                        if fault == 'observation': value['observation']['checks'] = []
                        if fault == 'authoritative':
                            for c in value['observation']['checks']:
                                if c.get('id') == f.spoof['id']: c['app'] = dict(id=f.p['app_id'])
                        if fault == 'intent': value['intent']['issued'] += 1000
                        if fault == 'task': value['intent']['inputs']['task_digest'] = '0'*64
                        if fault == 'controls': value['intent']['inputs']['controls_digest'] = '0'*64
                        if fault == 'proofs': value['intent']['inputs']['proofs']['merge']['artifact_id'] += 1
                        if fault == 'observed': value['observed'] = 1
                        if fault == 'evidence-input': value['intent']['inputs']['evidence'] = {}
                    elif prefix == 'proof-merge-':
                        if fault == 'expired': value['expires'] = value['completed']
                        if fault == 'binding': value['sequence'] += 1
                    elif fault == 'binding': value['configuration_revision'] = '0'*40
                    f.remote.replace(identity, value, member)
                    with self.subTest(prefix=prefix, fault=fault), self.assertRaises(Refusal): self.validate(f, location)
                    with self.subTest(native=prefix, fault=fault), self.assertRaises(Refusal): self.observe(f, location)
                    self.assertEqual(self.journal(f).read(), before)
                    f.remote.raw[identity] = raw
                    next(a for a in f.remote.artifacts if a['id'] == identity).update(metadata)
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def test_wrong_case_and_export_semantics_fail_closed(self):
        def check(*args):
            f, location = self.closed(args); self.validate(f, location); before = self.journal(f).read()
            case = self.case(f); candidate = case['candidate']
            _, _, terminal = self.document(f, 'trial-case-terminal-')
            from provenance import authenticated_document
            proof = authenticated_document(f.api, terminal['before']['deployment'], location, 'trial-case-terminal',
                                           f.admission.record['task_id'], f.clock[0])
            for reader in (trial_host_case.bad_acceptance_terminal, trial_host_case.replaced_checks_terminal,
                           trial_host_case.forged_records_terminal):
                with self.assertRaises(Refusal):
                    reader(f.api, f.admission.record, case, terminal, proof, f.clock[0], original=f.origin)
            for name in ('forged-records', 'direct-push', 'new-head'):
                relabeled = copy.deepcopy(case); relabeled['candidate']['name'] = name
                with self.subTest(name=name), self.assertRaises(Refusal):
                    trial_host_case.spoofed_source_terminal(f.api, f.admission.record, relabeled, terminal, proof, f.clock[0],
                                                           original=f.origin)
            commit = f.source.commits[candidate['submitted']['head']]; message = commit['message']; commit['message'] += 'changed'
            with self.assertRaises(Refusal): self.observe(f, location)
            commit['message'] = message
            tree = f.source.trees[candidate['submitted']['tree']]; path = sorted(tree)[0]; item = tree[path]
            tree[path] = ('100755', item[1])
            with self.assertRaises(Refusal): self.observe(f, location)
            tree[path] = item
            self.assertEqual(self.journal(f).read(), before)
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def test_late_evidence_removal_and_broker_conflicts_fail_closed(self):
        def check(*args):
            import broker_evidence
            f, location = self.closed(args); self.validate(f, location); before = self.journal(f).read()
            artifacts = copy.deepcopy(f.remote.artifacts); readback = broker_evidence._artifact_readback
            for fault in ('host-intent', 'publication', 'dispatch'):
                for consume in (self.validate, self.observe):
                    f.remote.artifacts[:] = copy.deepcopy(artifacts); changed = []
                    def race(authority, d, references):
                        if not changed and any(r['role'] == 'trial-case-terminal' and r['run_id'] == 117 for r in references):
                            changed.append(fault)
                            if fault == 'dispatch':
                                a = next(a for a in f.remote.artifacts if a['name'].endswith('-host-denied'))
                                f.remote.artifacts.append(dict(a, id=999999, name=a['name'].replace('-host-denied', '-dispatch')))
                            else:
                                prefix = 'trial-host-intent-' if fault == 'host-intent' else 'trial-publication-observation-'
                                f.remote.artifacts[:] = [a for a in f.remote.artifacts if not a['name'].startswith(prefix)]
                        return readback(authority, d, references)
                    with patch.object(broker_evidence, '_artifact_readback', side_effect=race), self.assertRaises(Refusal):
                        consume(f, location)
                    self.assertEqual(changed, [fault]); self.assertEqual(self.journal(f).read(), before)
            f.remote.artifacts[:] = artifacts
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def test_history_expiry_and_current_native_prerequisites_are_separate(self):
        def check(*args):
            f, location = self.closed(args); case = self.case(f); before = self.journal(f).read()
            from provenance import authenticated_document
            _, _, terminal = self.document(f, 'trial-case-terminal-')
            proof = authenticated_document(f.api, terminal['before']['deployment'], location, 'trial-case-terminal',
                                           f.admission.record['task_id'], f.clock[0])
            for field in ('launch', 'execution'):
                value = copy.deepcopy(case); value[field]['credential']['expires'] = terminal['completed']-1
                with self.subTest(field=field), self.assertRaises(Refusal):
                    trial_host_case.spoofed_source_terminal(f.api, f.admission.record, value, terminal, proof, f.clock[0],
                                                           original=f.origin)
            pages = f.source.pages
            for part in ('rules/branches', 'reviews'):
                def missing(path, *pos): return [] if part in path else pages(path, *pos)
                with patch.object(f.source, 'pages', side_effect=missing), self.subTest(current=part), self.assertRaises(Refusal):
                    self.observe(f, location)
                self.assertEqual(self.journal(f).read(), before)
            checks = f.checks[:]
            f.checks.remove(f.spoof)
            with self.assertRaises(Refusal): self.observe(f, location)
            f.checks[:] = checks
            f.clock[0] = max(case[k]['credential']['expires'] for k in ('launch', 'execution'))+1
            self.assertLess(f.clock[0], case['certificate']['expires'])
            with self.assertRaises(Refusal): self.observe(f, location)
            with patch.object(f.source, 'pages', side_effect=AssertionError('historical freshness')), \
                    patch.object(service, '_source_token', side_effect=AssertionError('historical mint')):
                self.validate(f, location)
                self.assertEqual(trial_case.baseline(f.origin, f.native.registry, f.admission.record,
                                                     self.history(f, location), lambda:f.clock[0]), terminal['after'])
            f.clock[0] = case['certificate']['expires']
            with self.assertRaises(Refusal): self.validate(f, location)
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def test_historical_source_reads_cannot_hide_late_conflicts(self):
        def check(*args):
            f, location = self.closed(args); history = self.history(f, location)
            artifacts = copy.deepcopy(f.remote.artifacts); read = trial_host_case._spoof_source
            for fault in ('host-intent', 'dispatch'):
                f.remote.artifacts[:] = copy.deepcopy(artifacts); changed = []
                def race(*pos, **kw):
                    result = read(*pos, **kw); changed.append(fault)
                    if fault == 'host-intent':
                        f.remote.artifacts[:] = [a for a in f.remote.artifacts if not a['name'].startswith('trial-host-intent-')]
                    else:
                        a = next(a for a in f.remote.artifacts if a['name'].endswith('-host-denied'))
                        f.remote.artifacts.append(dict(a, id=999999, name=a['name'].replace('-host-denied', '-dispatch')))
                    return result
                with patch.object(trial_host_case, '_spoof_source', side_effect=race), self.assertRaises(Refusal):
                    trial_case.history_guard(f.origin, f.admission.record, history, lambda:f.clock[0], f.api, f.source)
                self.assertEqual(changed, [fault])
            f.remote.artifacts[:] = artifacts
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def test_finalizer_ack_loss_cannot_export_or_publish(self):
        def check(*args):
            import registry
            f = self.pending(args); instances = []; finalize = broker_finalize.Finalizer._finalize
            write = registry.Registry.finalize_operation
            def track(instance, *pos, **kw): instances.append(instance); return finalize(instance, *pos, **kw)
            def uncertain(instance, *pos, **kw): write(instance, *pos, **kw); raise OSError('finalizer ACK lost')
            with patch.object(broker_finalize.Finalizer, '_finalize', track), \
                    patch.object(registry.Registry, 'finalize_operation', uncertain):
                with self.assertRaisesRegex(OSError, 'ACK lost'): f.finalize()
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
            r = f.admission.request
            with self.assertRaises(Refusal):
                instances[-1]._negative_evidence(r['operation_id'], r['sequence'], f.native.registry.binding())
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def test_native_ack_loss_blocks_tenth_and_cleanup_survives_expiry(self):
        def check(*args):
            f, location = self.closed(args); journal = self.journal(f); write = type(journal.raw).write
            def uncertain(instance, *pos, **kw):
                result = write(instance, *pos, **kw)
                if instance.root == journal.raw.root: raise OSError('ninth root ACK lost')
                return result
            with patch.object(type(journal.raw), 'write', uncertain), self.assertRaisesRegex(OSError, 'ACK lost'):
                self.observe(f, location)
            f.native.provision._controller_acknowledgements.clear()
            with self.assertRaises(Refusal): self.observe(f, location)
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt', 'new-head', f.source, phase='prior')
            f.clock[0] = f.admission.record['expires']+1
            trial_launch.revoke(f.native.provision, f.origin_factory, name='spoofed-source')
            self.assertIn(f.case_token, f.revoked)
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)


if __name__ == '__main__': unittest.main()
