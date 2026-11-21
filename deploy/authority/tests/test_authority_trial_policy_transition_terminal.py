"""Twelfth CLOSED evidence; GitHub and OCI transport boundaries are modeled."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

import authority_release
import broker_finalize
import service
import trial_case
import trial_controller
import trial_host_case
import trial_launch
import trial_transition
import test_authority_trial_context_case as context_fixture
import test_authority_trial_forged_case as forged_fixture
import test_authority_trial_outage_terminal as outage_fixture
from trusted_ci_policy import Refusal, digest

RUN = 129
NAME = 'policy-transition'


class PolicyTransitionPrerequisiteContracts(unittest.TestCase):
    def fixture(self):
        p = dict(check_name='agentic-ci', app_id=11, reviewers=[5], coding_actors=[9])
        s = dict(head='a'*40, merge='b'*40)
        binding = dict(deployment=dict(policy=p))
        candidate = dict(name=NAME, submitted=dict(bot_id=9), transition=dict(intent=dict(phase='current')))
        retained = dict(request=dict(snapshot=s), candidate=candidate)
        rules = [dict(type='required_status_checks', parameters=dict(required_status_checks=[dict(context='agentic-ci', integration_id=11)]))]
        reviews = [dict(id=1, user=dict(id=5, type='User'), state='APPROVED', commit_id=s['head'])]
        return binding, retained, dict(checks=[], rules=rules, reviews=reviews)

    def test_twelfth_has_no_foreign_success_but_every_other_host_prerequisite(self):
        binding, retained, observation = self.fixture()
        trial_host_case._source_prerequisites(observation, binding, retained)
        value = copy.deepcopy(observation)
        value['checks'].append(dict(id=1, name='agentic-ci', app=dict(id=11), status='completed', conclusion='success', head_sha='b'*40))
        with self.assertRaisesRegex(Refusal, 'authoritative success'):
            trial_host_case._source_prerequisites(value, binding, retained)
        for part, wrong in (('reviews', []), ('rules', [])):
            value = copy.deepcopy(observation); value[part] = wrong
            with self.subTest(part=part), self.assertRaises(Refusal):
                trial_host_case._source_prerequisites(value, binding, retained)
        retained['candidate'] = dict(name='spoofed-source', submitted=dict(bot_id=9))
        with self.assertRaisesRegex(Refusal, 'spoofed issuer success'):
            trial_host_case._source_prerequisites(observation, binding, retained)

    def test_current_phase_is_the_only_twelfth_terminal_candidate(self):
        binding, retained, observation = self.fixture()
        self.assertTrue(trial_host_case.policy_transition_current(retained['candidate']))
        self.assertTrue(trial_host_case.stale_current(retained['candidate']))
        for intent in (dict(phase='prior'), dict(phase='negative'), dict(phase='fixture'), {}):
            candidate = dict(retained['candidate'], transition=dict(intent=intent))
            self.assertFalse(trial_host_case.policy_transition_current(candidate))
            self.assertFalse(trial_host_case.stale_current(candidate))
            with self.subTest(intent=intent), self.assertRaises(Refusal):
                trial_host_case._policy_transition_readback(None, dict(retained, candidate=candidate), None, None, 0, None)
        self.assertFalse(trial_host_case.policy_transition_current(dict(name=NAME)))
        for name in ('new-head', 'new-base', 'human-update'):
            self.assertFalse(trial_host_case.policy_transition_current(dict(name=name, transition=dict(intent=dict(phase='current')))))
        self.assertFalse(trial_host_case.stale_current(dict(name='human-update', transition=dict(intent=dict(phase='current')))))
        for other in ('spoofed-source', 'new-head', 'new-base'):
            wrong = dict(retained, candidate=dict(retained['candidate'], name=other))
            with self.assertRaises(Refusal): trial_host_case._policy_transition_source(None, None, wrong, None, None, None)
            with self.assertRaises(Refusal): trial_host_case._policy_transition_readback(None, wrong, None, None, 0, None)
        for reader in (trial_host_case._new_head_source, trial_host_case._new_base_source):
            with self.assertRaises(Refusal): reader(None, None, retained, None, None, None)
        for reader in (trial_host_case._new_head_readback, trial_host_case._new_base_readback):
            with self.assertRaises(Refusal): reader(None, retained, None, None, 0, None)
        for reader in (trial_host_case.bad_acceptance_terminal, trial_host_case.replaced_checks_terminal,
                       trial_host_case.forged_records_terminal, trial_host_case.spoofed_source_terminal,
                       trial_host_case.new_head_terminal, trial_host_case.new_base_terminal):
            with self.assertRaises(Refusal): reader(None, None, retained, {}, {}, 0, original=None)

    def test_stale_prior_requires_the_old_policy_epoch_and_moved_base(self):
        base = dict(repository='owner/project', repository_id=1, authority_repository='owner/authority',
                    authority_repository_id=2, target='main', app_id=11)
        current = dict(base, epoch='e2', check_name='AGENTIC acceptance e2')
        s = dict(pr=1, head='h', base='b', merge='m')
        good = dict(base, epoch='e1', check_name='agentic-ci')
        cases = (('old policy', good, dict(head='h', base='old'), True),
                 ('same epoch', dict(good, epoch='e2'), dict(head='h', base='old'), False),
                 ('same check', dict(good, check_name=current['check_name']), dict(head='h', base='old'), False),
                 ('same policy', dict(current), dict(head='h', base='old'), False),
                 ('foreign repository', dict(good, repository='owner/other'), dict(head='h', base='old'), False),
                 ('foreign app', dict(good, app_id=12), dict(head='h', base='old'), False),
                 ('moved head', good, dict(head='old', base='b'), False),
                 ('unmoved base', good, dict(head='h', base='b'), False))
        for label, policy, shape, ok in cases:
            value = dict(deployment=dict(policy=policy), snapshot=dict(pr=1, merge='o', **shape), coordinates={}, evidence={})
            intent = dict(phase='current', prior={}, acceptance=value)
            retained = dict(candidate=dict(name=NAME, transition=dict(intent=intent)), request=dict(snapshot=s))
            with self.subTest(label=label), patch.object(trial_transition, 'prior_acceptance', return_value=value), \
                    self.assertRaises(Refusal) as caught:
                trial_host_case._stale_prior(None, dict(deployment=dict(policy=current)), {}, retained, {}, object(), 0, 0, 0)
            # The right shape passes the coordinate gate and fails only on the later evidence checks.
            self.assertEqual('coordinates differ' in str(caught.exception), not ok)
        # new-base still requires the identical deployment, never an epoch change.
        value = dict(deployment=dict(policy=good), snapshot=dict(pr=1, merge='o', head='h', base='old'), coordinates={}, evidence={})
        retained = dict(candidate=dict(name='new-base', transition=dict(intent=dict(phase='current', prior={}, acceptance=value))),
                        request=dict(snapshot=s))
        with patch.object(trial_transition, 'prior_acceptance', return_value=value), self.assertRaisesRegex(Refusal, 'coordinates differ'):
            trial_host_case._stale_prior(None, dict(deployment=dict(policy=current)), {}, retained, {}, object(), 0, 0, 0)


class Holds(unittest.TestCase):
    def test_observation_hold_precedes_transport(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        with self.assertRaises(authority_release.Held):
            trial_controller.Native(NoIO()).observe_terminal('prompt', NAME, {})


@unittest.skipIf(getattr(context_fixture.NativeContext, '__unittest_skip__', False), 'optional cryptography required')
class PolicyTransitionTerminal(unittest.TestCase):
    fixture = context_fixture.NativeContext.fixture
    prepared = context_fixture.NativeContext.prepared
    connected = context_fixture.NativeContext.connected
    configured = context_fixture.NativeContext.configured
    exercise = context_fixture.NativeContext.exercise
    prepare = context_fixture.NativeContext.prepare
    forbidden = outage_fixture.OutageTerminal.forbidden
    document = outage_fixture.OutageTerminal.document
    closed = outage_fixture.OutageTerminal.closed
    after_prior = None

    def pending(self, args):
        # NativeContext.exercise already forbids any broker merge dispatch.
        f = context_fixture.Context(self, args)
        hook = self.after_prior
        f.through_tenth(); f.advance_case('new-base', 123, 125)
        f.pending_case(NAME, 127, RUN, after_prior=(lambda: hook(f)) if hook else None)
        return f

    def journal(self, f):
        return f.native.provision.store(f.native.provision.root/'trial-controller-policy-transition')

    def case(self, f):
        publication = f.native.provision.store(f.native.provision.root/'trial-case-publication-policy-transition').read()['value']
        case, record = trial_case.read(f.origin, publication['revision_bound'], lambda:f.clock[0])
        self.assertEqual(record, f.admission.record)
        return case

    def history(self, f, location):
        value = self.journal(f).read()['value']
        publication = f.native.provision.store(f.native.provision.root/'trial-case-publication-policy-transition').read()['value']
        return value['history']+[dict(revision=publication['revision_bound'], terminal=location)]

    def observe(self, f, location):
        with self.forbidden(f), patch.object(service, '_source_token', side_effect=AssertionError('terminal mint')), \
                patch.object(trial_controller.Admission, 'task', side_effect=AssertionError('terminal task admission')):
            return trial_controller.Native(f.preparer)._observe_terminal('prompt', NAME, location, f.source)

    def proof(self, f, location):
        from provenance import authenticated_document
        _, _, terminal = self.document(f, 'trial-case-terminal-')
        proof = authenticated_document(f.api, terminal['before']['deployment'], location, 'trial-case-terminal',
                                       f.admission.record['task_id'], f.clock[0])
        return terminal, proof

    def validate(self, f, location, case=None, terminal=None, **kwargs):
        read, proof = self.proof(f, location)
        return trial_host_case.policy_transition_terminal(f.api, f.admission.record, case or self.case(f), terminal or read, proof,
                                                          f.clock[0], original=f.origin, **kwargs)

    def next_case(self, f):
        with self.assertRaises(Refusal):
            trial_controller.Native(f.preparer)._open('prompt', 'human-update', f.source)

    def test_connected_twelfth_cleanup_and_human_update_selection(self):
        def check(*args):
            f = self.pending(args)
            original = f.origin.binding()
            f.finalize()
            terminal_binding = f.observe()['binding']
            _, _, terminal = self.document(f, 'trial-case-terminal-')
            self.assertEqual(terminal['schema_version'], 2)
            self.assertNotIn('broker_receipt', terminal)
            self.assertEqual(digest(terminal['recovery']), terminal['after']['fence']['completed'][-1]['receipt_digest'])
            self.assertEqual(terminal['after'], terminal_binding)
            _, _, publication = self.document(f, 'trial-publication-observation-')
            self.assertIn('prior', publication['observation'])
            self.assertFalse(any(a['name'].startswith(('evidence-', 'trial-publication-denial-')) for a in f.remote.artifacts))
            token = f.case_token; revoked = set(f.revoked)
            trial_launch.revoke(f.native.provision, f.origin_factory, name=NAME)
            self.assertEqual(set(f.revoked)-revoked, {token})
            f.phase = None; f.second('human-update', 131, 'fresh-human-current')
            history = f.admission.value['history']
            self.assertEqual(len(history), 12)
            cases = [trial_case.read(f.origin, e['revision'], lambda:f.clock[0])[0] for e in history]
            self.assertEqual([c['candidate']['name'] for c in cases], list(trial_controller.CASE_CHAIN[:12]))
            self.assertEqual(f.origin.binding(), original)
            self.assertEqual(f.merges, [])
            current = cases[-1]['candidate']['transition']['intent']['acceptance']
            self.assertEqual(cases[-1]['request']['snapshot']['head'], current['snapshot']['head'])
            self.assertNotEqual(cases[-1]['request']['snapshot']['base'], current['snapshot']['base'])
            self.assertNotEqual(current['deployment']['policy']['epoch'], f.p['epoch'])
            self.assertNotEqual(current['deployment']['policy']['check_name'], f.p['check_name'])
            self.assertIsNone(f.admission.binding['deployment']['qualification'])
            self.assertEqual(f.admission.binding['deployment']['state'], 'qualification')
            return f.source.refs['main']
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def owned_completion(self, f, location):
        self.observe(f, location)
        store = self.journal(f); saved = store.read(); value = copy.deepcopy(saved['value'])
        value['terminal']['binding']['fence']['completed'][-1]['receipt_digest'] = '0'*64
        store.write(saved, value)
        writes = copy.deepcopy(f.source.writes)
        with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt', 'human-update', f.source)
        self.assertEqual(f.source.writes, writes)
        self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-controller-human-update').read())

    def v1_terminal(self, f, location, seen):
        self.assertEqual(seen, ['prior'])
        before = self.journal(f).read()
        identity, member, original = self.document(f, 'trial-case-terminal-')
        value = copy.deepcopy(original)
        value.update(schema_version=1); value.pop('recovery', None); value.pop('host_receipt', None)
        f.remote.replace(identity, value, member)
        try:
            with self.assertRaises(Refusal): self.observe(f, location)
            with self.assertRaises(Refusal):
                trial_case.baseline(f.origin, f.native.registry, f.admission.record, self.history(f, location), lambda:f.clock[0])
            self.next_case(f)
            self.assertEqual(self.journal(f).read(), before)
        finally:
            f.remote.replace(identity, original, member)

    def export(self, f, instance, result):
        r = f.admission.request
        value = instance._negative_evidence(r['operation_id'], r['sequence'], result)
        self.assertEqual(set(value), {'recovery', 'host_receipt'})
        value['host_receipt']['issued'] = 1
        self.assertNotEqual(instance._negative_evidence(r['operation_id'], r['sequence'], result), value)
        for op, seq, saved in (('0'*32, r['sequence'], result), (r['operation_id'], r['sequence']+1, result),
                               (r['operation_id'], r['sequence'], {})):
            with self.assertRaises(Refusal): instance._negative_evidence(op, seq, saved)
        with self.assertRaises(Refusal): instance._finalize('invalid', 1, 1)
        with self.assertRaises(Refusal): instance._negative_evidence(r['operation_id'], r['sequence'], result)

    def built(self, args):
        """One native chain through the closed twelfth terminal, with the facts the contracts below share."""
        seen = []
        def prior_terminal(f):
            _, _, terminal = self.document(f, 'trial-case-terminal-')
            self.assertEqual(terminal['schema_version'], 1)
            self.assertNotIn('recovery', terminal); self.assertNotIn('host_receipt', terminal)
            self.assertFalse(trial_host_case.stale_current(f.admission.candidate))
            seen.append(f.admission.candidate['transition']['intent']['phase'])
        self.after_prior = prior_terminal
        try: f = self.pending(args)
        finally: self.after_prior = None
        instances = []; finalize = broker_finalize.Finalizer._finalize
        def track(instance, *pos, **kw): instances.append(instance); return finalize(instance, *pos, **kw)
        with patch.object(broker_finalize.Finalizer, '_finalize', track): result = f.finalize()
        from test_authority_broker_evidence import stamp
        job = next(j for j in f.remote.jobs if j['name'] == 'finalize')
        job.update(status='completed', conclusion='success', completed_at=stamp(f.clock[0]))
        artifact = next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
        return f, dict(run_id=f.remote.run['id'], attempt=1, job_id=job['id'], artifact_id=artifact['id']), result, instances[-1], seen

    def test_closed_terminal_contracts_share_one_native_chain(self):
        # Every step restores what it touches, so the chain is built once instead of once per contract.
        # Only the first observation, owned completion last, since it corrupts the journal on purpose.
        def check(*args):
            f, location, result, instance, seen = self.built(args)
            steps = (('export is exact, acknowledged and not stale', lambda: self.export(f, instance, result)),
                     ('terminal inventory, case and acceptance mutations', lambda: self.inventory_mutations(f, location)),
                     ('host and publication mutations', lambda: self.host_mutations(f, location)),
                     ('v1 terminal and historical preparation', lambda: self.v1_terminal(f, location, seen)),
                     ('owned completion before human-update', lambda: self.owned_completion(f, location)))
            for label, step in steps:
                with self.subTest(step=label): step()
            return f.source.refs['main']
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)

    def inventory_mutations(self, f, location):
        from test_authority_broker_evidence import stamp
        outcome = self.validate(f, location)['document']
        before = self.journal(f).read(); case = self.case(f)
        record = outcome['record']
        self.assertTrue(record['request_sent']); self.assertIsNone(record['broker_refusal'])
        self.assertEqual((record['denial_category'], record['denied_obligation']), ('required_check', f.p['check_name']))
        self.assertIn(record['http_status'], (403, 405, 422))
        old = outcome['observation']['prior']
        accepted = case['candidate']['transition']['intent']['acceptance']
        self.assertEqual(old['coordinates']['evidence_job_id'], old['proof']['job_id'])
        self.assertEqual(accepted['coordinates'], old['coordinates'])
        self.assertEqual(accepted['snapshot']['head'], case['request']['snapshot']['head'])
        self.assertNotEqual(accepted['snapshot']['base'], case['request']['snapshot']['base'])
        # The old success belongs to the previous policy epoch and check name.
        self.assertNotEqual(accepted['deployment']['policy']['epoch'], f.p['epoch'])
        self.assertNotEqual(record['denied_obligation'], accepted['deployment']['policy']['check_name'])
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
                if collection == 'artifacts' and '/runs/%d/' % RUN in path:
                    if fault == 'duplicate': return entries+[dict(entries[0])]
                    if fault == 'oversized': return [dict(entries[0], id=i+1) for i in range(10001)]
                return entries
            with self.subTest(fault=fault), patch.object(f.api, 'pages', side_effect=inventory), self.assertRaises(Refusal):
                self.validate(f, location)
            with self.subTest(native=fault), patch.object(f.api, 'pages', side_effect=inventory), self.assertRaises(Refusal):
                self.observe(f, location)
            self.assertEqual(self.journal(f).read(), before)
        f.remote.artifacts[:] = artifacts; f.remote.raw.clear(); f.remote.raw.update(raw)
        terminal, proof = self.proof(f, location)
        for reader in (trial_host_case.bad_acceptance_terminal, trial_host_case.replaced_checks_terminal,
                       trial_host_case.forged_records_terminal, trial_host_case.spoofed_source_terminal,
                       trial_host_case.new_head_terminal, trial_host_case.new_base_terminal):
            with self.assertRaises(Refusal):
                reader(f.api, f.admission.record, case, terminal, proof, f.clock[0], original=f.origin)
        for name in ('forged-records', 'direct-push', 'spoofed-source', 'new-head', 'new-base', 'human-update'):
            relabeled = copy.deepcopy(case); relabeled['candidate']['name'] = name
            with self.subTest(name=name), self.assertRaises(Refusal):
                trial_host_case.policy_transition_terminal(f.api, f.admission.record, relabeled, terminal, proof, f.clock[0], original=f.origin)
        for phase in ('prior', 'negative', 'fixture'):
            relabeled = copy.deepcopy(case); relabeled['candidate']['transition']['intent']['phase'] = phase
            with self.subTest(phase=phase), self.assertRaises(Refusal):
                trial_host_case.policy_transition_terminal(f.api, f.admission.record, relabeled, terminal, proof, f.clock[0], original=f.origin)
        relabeled = copy.deepcopy(case); relabeled['candidate'].pop('transition')
        with self.assertRaises(Refusal):
            trial_host_case.policy_transition_terminal(f.api, f.admission.record, relabeled, terminal, proof, f.clock[0], original=f.origin)
        with self.assertRaises(Refusal):
            trial_host_case.policy_transition_terminal(f.api, f.admission.record, case, terminal, proof, f.clock[0], original=None)
        for fault in ('coordinates', 'snapshot', 'evidence', 'deployment', 'policy-epoch', 'policy-check', 'current-policy', 'registry'):
            value = copy.deepcopy(case); accepted = value['candidate']['transition']['intent']['acceptance']
            if fault == 'coordinates': accepted['coordinates']['task_digest'] = '0'*64
            if fault == 'snapshot': accepted['snapshot']['base'] = f.admission.request['snapshot']['base']
            if fault == 'evidence': accepted['evidence']['artifact_id'] += 1
            if fault == 'deployment': accepted['deployment']['policy']['repository_id'] += 1
            if fault == 'policy-epoch': accepted['deployment']['policy']['epoch'] = 'foreign'
            if fault == 'policy-check': accepted['deployment']['policy']['check_name'] = f.p['check_name']
            if fault == 'current-policy': accepted['deployment']['policy'] = copy.deepcopy(f.p)
            if fault == 'registry': accepted['registry_revision'] = '0'*40
            with self.subTest(acceptance=fault), self.assertRaises(Refusal):
                trial_host_case.policy_transition_terminal(f.api, f.admission.record, value, terminal, proof, f.clock[0], original=f.origin)
        head = case['candidate']['submitted']['head']
        commit = f.source.commits[head]; message = commit['message']; commit['message'] += 'changed'
        with self.assertRaises(Refusal): self.observe(f, location)
        commit['message'] = message
        checks = f.checks[:]
        old_merge = case['candidate']['transition']['intent']['acceptance']['snapshot']['merge']
        f.checks[:] = [c for c in f.checks if c['head_sha'] != old_merge]
        with self.assertRaises(Refusal): self.observe(f, location)
        f.checks[:] = checks
        f.checks.append(dict(checks[0], id=9999, head_sha=f.admission.request['snapshot']['merge'],
                             app=dict(id=f.p['app_id']), name=f.p['check_name'], status='completed', conclusion='success'))
        with self.assertRaises(Refusal): self.observe(f, location)
        f.checks[:] = checks
        self.assertEqual(self.journal(f).read(), before)
        self.validate(f, location)

    def host_mutations(self, f, location):
        self.validate(f, location); before = self.journal(f).read()
        for prefix, faults in (
                ('trial-host-denial-', ('actor', 'status', 'category', 'obligation', 'old-obligation', 'record', 'publication', 'rules',
                                        'reviews', 'success', 'extra-negative', 'prior-removed', 'prior-check', 'prior-external',
                                        'prior-coordinates', 'prior-proof', 'prior-observed')),
                ('trial-publication-observation-', ('observation', 'task', 'prior-removed', 'prior-coordinates', 'prior-check')),
                ('publication-controls-', ('binding',)),
                ('proof-merge-', ('expired', 'binding'))):
            identity, member, saved = self.document(f, prefix)
            metadata = copy.deepcopy(next(a for a in f.remote.artifacts if a['id'] == identity)); raw = f.remote.raw[identity]
            for fault in faults:
                value = copy.deepcopy(saved)
                if prefix == 'trial-host-denial-':
                    o = value['observation']
                    if fault == 'actor': o['actor_id'] += 1
                    if fault == 'status': o['http_status'] = 500
                    if fault == 'category': o['denial_category'] = 'required_review'
                    if fault == 'obligation': o['denied_obligation'] = 'other-check'
                    if fault == 'old-obligation':
                        o['denied_obligation'] = self.case(f)['candidate']['transition']['intent']['acceptance']['deployment']['policy']['check_name']
                    if fault == 'record': value['record']['request_sent'] = False
                    if fault == 'publication': o['publication']['digest'] = '0'*64
                    if fault == 'rules': o['rules'] = []
                    if fault == 'reviews': o['reviews'] = []
                    if fault == 'success':
                        o['checks'].append(dict(name=f.p['check_name'], app=dict(id=f.p['app_id']), status='completed', conclusion='success'))
                    if fault == 'extra-negative': o['negative'] = {}
                    if fault == 'prior-removed': o.pop('prior')
                    if fault == 'prior-check': o['prior']['check']['check_id'] = True
                    if fault == 'prior-external': o['prior']['check']['external_id'] = 'agentic-v2:'+'0'*64
                    if fault == 'prior-coordinates': o['prior']['coordinates']['task_digest'] = '0'*64
                    if fault == 'prior-proof': o['prior']['proof']['job_id'] += 1
                    if fault == 'prior-observed': o['prior']['check']['observed'] = 1
                elif prefix == 'trial-publication-observation-':
                    if fault == 'observation': value['observation']['checks'] = [dict(id=1)]
                    if fault == 'task': value['intent']['inputs']['task_digest'] = '0'*64
                    if fault == 'prior-removed':
                        value['observation'].pop('prior'); value['intent']['inputs']['source'].pop('prior')
                    if fault == 'prior-coordinates':
                        value['observation']['prior']['coordinates']['task_digest'] = '0'*64
                        value['intent']['inputs']['source']['prior']['coordinates']['task_digest'] = '0'*64
                    if fault == 'prior-check':
                        value['observation']['prior']['check']['check_id'] += 1
                        value['intent']['inputs']['source']['prior']['check']['check_id'] += 1
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

    def test_native_ack_loss_blocks_human_update_and_cleanup_survives_expiry(self):
        def check(*args):
            f, location = self.closed(args); journal = self.journal(f); write = type(journal.raw).write
            def uncertain(instance, *pos, **kw):
                result = write(instance, *pos, **kw)
                if instance.root == journal.raw.root: raise OSError('twelfth root ACK lost')
                return result
            with patch.object(type(journal.raw), 'write', uncertain), self.assertRaisesRegex(OSError, 'ACK lost'):
                self.observe(f, location)
            f.native.provision._controller_acknowledgements.clear()
            with self.assertRaises(Refusal): self.observe(f, location)
            self.next_case(f)
            f.clock[0] = f.admission.record['expires']+1
            trial_launch.revoke(f.native.provision, f.origin_factory, name=NAME)
            self.assertIn(f.case_token, f.revoked)
            return f.source.refs['main']
        self.exercise(continuation=check, export_files=forged_fixture.EXPORT)


if __name__ == '__main__': unittest.main()
