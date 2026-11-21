"""Second-case evidence through native engines; remote boundaries remain modeled."""
import backend_test_support
import copy
import io
import json
import unittest
import zipfile
from unittest.mock import patch

import authority_release
import broker_finalize
import trial_case
import trial_controller
import trial_host_case
import trial_launch
from test_authority_broker_evidence import stamp
import test_authority_trial_host_case as host_fixture
import test_authority_trial_terminal as terminal_fixture
from trusted_ci_policy import Refusal, digest


class Holds(unittest.TestCase):
    def test_observation_hold_precedes_transport(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        with self.assertRaises(authority_release.Held):
            trial_controller.Native(NoIO()).observe_terminal('prompt', 'coding-update', {})


@unittest.skipIf(getattr(host_fixture.NativeHost, '__unittest_skip__', False), 'optional cryptography required')
class CodingTerminal(unittest.TestCase):
    fixture = host_fixture.NativeHost.fixture
    prepared = host_fixture.NativeHost.prepared
    connected = host_fixture.NativeHost.connected
    configured = host_fixture.NativeHost.configured
    exercise = host_fixture.NativeHost.exercise
    prepare = host_fixture.NativeHost.prepare
    forbidden = terminal_fixture.Terminal.forbidden
    collector = terminal_fixture.Terminal.collector

    def pending(self, args):
        f = host_fixture.Sequential(self, args)
        f.prepared_host(); f.host(); f.run('broker'); f.finalize()
        job = next(j for j in f.remote.jobs if j['name'] == 'finalize')
        job.update(status='completed', conclusion='success', completed_at=stamp(f.clock[0]))
        first = self.collector(f)._collect('prompt', f.source)
        self.assertTrue(first['intended_denial_verified'])
        f.second()
        with self.assertRaisesRegex(Refusal, 'pending'): f.coordinate()
        f.close_handoff(); f.published(); f.host(); f.run('broker')
        return f

    def closed(self, args):
        f = self.pending(args)
        f.finalize()
        job = next(j for j in f.remote.jobs if j['name'] == 'finalize')
        job.update(status='completed', conclusion='success', completed_at=stamp(f.clock[0]))
        artifact = next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
        location = dict(run_id=f.remote.run['id'], attempt=1, job_id=job['id'], artifact_id=artifact['id'])
        return f, location

    def journal(self, f):
        return f.native.provision.store(f.native.provision.root / 'trial-controller-coding-update')

    def document(self, f, prefix):
        a = next(a for a in f.remote.artifacts if a['name'].startswith(prefix))
        with zipfile.ZipFile(io.BytesIO(f.remote.raw[a['id']])) as z:
            member = z.namelist()[0]
            return a['id'], member, json.loads(z.read(member))

    def observe(self, f, location):
        return trial_controller.Native(f.preparer)._observe_terminal('prompt', 'coding-update', location, f.source)

    def test_two_case_evidence_read_only_observation_cleanup_and_progression(self):
        def check(*args):
            f, location = self.closed(args)
            original = f.origin.binding()
            before = self.journal(f).read()['value']
            _, _, document = self.document(f, 'trial-case-terminal-')
            self.assertEqual(document['schema_version'], 2)
            self.assertEqual(digest(document['recovery']), document['after']['fence']['completed'][-1]['receipt_digest'])
            with self.forbidden(f): terminal = self.observe(f, location)
            self.assertEqual(self.journal(f).read()['value']['terminal'], terminal)
            calls = []
            def tokens(token):
                self.assertEqual(token, f.case_token)
                api = f.origin_factory(token); fetch = api.fetch
                def revoke(path, **kw):
                    self.assertEqual((path, kw), ('/installation/token', dict(method='DELETE', binary=True)))
                    calls.append(token)
                    return fetch(path, **kw)
                api.fetch = revoke
                return api
            f.clock[0] += 1
            trial_launch.revoke(f.native.provision, tokens, name='coding-update')
            self.assertEqual(calls, [f.case_token])
            self.assertEqual(f.source.refs['main'], before['request']['snapshot']['base'])
            self.assertEqual(f.origin.binding(), original)
            f.second('missing-approval', 105, 'fresh-third-case')
            history = f.admission.value['history']
            self.assertEqual(len(history), 2)
            cases = [trial_case.read(f.origin, v['revision'], lambda:f.clock[0])[0] for v in history]
            self.assertEqual([v['candidate']['name'] for v in cases], ['direct-push', 'coding-update'])
            for field in ('pr', 'head', 'task_id'):
                self.assertNotEqual(cases[0]['candidate']['submitted'][field], cases[1]['candidate']['submitted'][field])
            target = f.source.refs['main']; f.source.refs['main'] = '0'*40
            with patch.object(f.source, 'pages', side_effect=AssertionError('historical live prerequisites')):
                self.assertEqual(trial_case.baseline(f.origin, f.native.registry, f.admission.record, history,
                                                    lambda:f.clock[0]), terminal['binding'])
            with self.assertRaises(Refusal):
                trial_host_case._direct_outcome(document['before'], f.admission.record, before,
                    f.api, document['host_receipt']['host'], f.clock[0], f.source)
            f.source.refs['main'] = target
            self.assertFalse(f.admission.record['trial']['deployment']['state'] == 'active')
        self.exercise(continuation=check)

    def test_legacy_coding_terminal_cannot_be_observed_or_used_as_predecessor(self):
        def check(*args):
            f, location = self.closed(args)
            journal = self.journal(f); before = journal.read()
            identity, member, terminal = self.document(f, 'trial-case-terminal-')
            terminal['schema_version'] = 1
            terminal.pop('recovery', None); terminal.pop('host_receipt', None)
            f.remote.replace(identity, terminal, member)
            with self.assertRaises(Refusal): self.observe(f, location)
            self.assertEqual(journal.read(), before)
            # Test the historical consumer independently of native observation.
            publication = f.native.provision.store(f.native.provision.root / 'trial-case-publication-coding-update').read()['value']
            history = before['value']['history'] + [dict(revision=publication['revision_bound'], terminal=location)]
            with self.assertRaises(Refusal):
                trial_case.baseline(f.origin, f.native.registry, f.admission.record, history, lambda:f.clock[0])
            with self.assertRaises(Refusal):
                trial_controller.Native(f.preparer)._open('prompt', 'missing-approval', f.source)
            self.assertNotIn(f.case_token, f.revoked)
        self.exercise(continuation=check)

    def test_coding_outcome_semantics_and_current_prerequisites_fail_closed(self):
        def check(*args):
            f, location = self.closed(args)
            before = self.journal(f).read()
            _, _, terminal = self.document(f, 'trial-case-terminal-')
            identity, member, outcome = self.document(f, 'trial-host-denial-')
            metadata = copy.deepcopy(next(a for a in f.remote.artifacts if a['id'] == identity))
            raw = f.remote.raw[identity]
            trial_host_case._direct_outcome(terminal['before'], f.admission.record, before['value'],
                f.api, terminal['host_receipt']['host'], f.clock[0])
            for fault, message in (('case', 'identity'), ('actor', 'intended'), ('request', 'intended'),
                                   ('status', 'intended'), ('target', 'intended'), ('category', 'intended'),
                                   ('record', 'record'), ('intent', 'intent'), ('coordinates', 'coordinates'),
                                   ('rules', 'obligation'), ('reviews', 'human'), ('check', 'issuer acceptance')):
                value = copy.deepcopy(outcome); observation = value['observation']
                if fault == 'case': value['case'] = 'direct-push'
                if fault == 'actor': observation['actor_id'] += 1
                if fault == 'request': observation['request']['data']['force'] = True
                if fault == 'status': observation['http_status'] = 200
                if fault == 'target': observation['after'] = '0'*40
                if fault == 'category': observation['denial_category'] = 'required_check'
                if fault == 'record': value['record']['request_sent'] = False
                if fault == 'intent': value['intent']['issued'] += 1000
                if fault == 'coordinates': observation['acceptance']['coordinates']['task_digest'] = '0'*64
                if fault == 'rules': observation['rules'] = []
                if fault == 'reviews': observation['reviews'] = []
                if fault == 'check': observation['acceptance']['check']['check_id'] += 1
                value['record']['evidence_digest'] = digest(observation)
                f.remote.replace(identity, value, member)
                with self.subTest(fault=fault), self.forbidden(f), self.assertRaisesRegex(Refusal, message):
                    trial_host_case._direct_outcome(terminal['before'], f.admission.record, before['value'],
                        f.api, terminal['host_receipt']['host'], f.clock[0])
                f.remote.raw[identity] = raw
                next(a for a in f.remote.artifacts if a['id'] == identity).update(metadata)
            pages = f.source.pages
            for part in ('check-runs', 'rules/branches', 'reviews'):
                def missing(path, *pos): return [] if part in path else pages(path, *pos)
                with self.subTest(current=part), patch.object(f.source, 'pages', side_effect=missing), self.assertRaises(Refusal):
                    self.observe(f, location)
                self.assertEqual(self.journal(f).read(), before)
        self.exercise(continuation=check)

    def test_native_ack_loss_never_adopts_completion_and_cleanup_survives_expiry(self):
        def check(*args):
            f, location = self.closed(args)
            save = trial_controller.Admission._save
            def uncertain(admission):
                save(admission)
                raise OSError('coding terminal ACK lost')
            with self.forbidden(f), patch.object(trial_controller.Admission, '_save', new=uncertain), self.assertRaisesRegex(OSError, 'ACK lost'):
                self.observe(f, location)
            f.native.provision._controller_acknowledgements.clear()
            with self.assertRaises(Refusal): self.observe(f, location)
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt', 'coding-update', f.source)
            f.clock[0] = f.admission.record['expires'] + 1
            trial_launch.revoke(f.native.provision, f.origin_factory, name='coding-update')
            self.assertIn(f.case_token, f.revoked)
        self.exercise(continuation=check)

    def test_terminal_chain_inventory_and_deadlines_refuse_without_advancement(self):
        def check(*args):
            f, location = self.closed(args)
            journal = self.journal(f); before = journal.read()
            identity, member, terminal = self.document(f, 'trial-case-terminal-')
            artifacts, raw = copy.deepcopy(f.remote.artifacts), copy.deepcopy(f.remote.raw)
            now = f.clock[0]; pages = f.api.pages
            for fault in ('request', 'certificate', 'envelope', 'host', 'broker', 'conflict', 'missing-host',
                          'duplicate-id', 'oversized', 'expiry'):
                value = copy.deepcopy(terminal)
                f.remote.artifacts[:] = copy.deepcopy(artifacts)
                f.remote.raw.clear(); f.remote.raw.update(raw)
                if fault == 'request': value['request_digest'] = '0'*64
                if fault == 'certificate': value['certificate_digest'] = '0'*64
                if fault == 'envelope': value['recovery']['operation_digest'] = '0'*64
                if fault == 'host': value['host_receipt']['host_digest'] = '0'*64
                if fault == 'broker': value['recovery']['producer']['id'] += 1
                if fault == 'conflict':
                    a = next(a for a in f.remote.artifacts if a['name'].endswith('-host-denied'))
                    f.remote.artifacts.append(dict(a, id=999999, name=a['name'].replace('-host-denied', '-dispatch')))
                if fault == 'missing-host':
                    f.remote.artifacts[:] = [a for a in f.remote.artifacts if not a['name'].startswith('trial-host-denial-')]
                if fault == 'expiry': f.clock[0] = f.admission.record['expires'] + 1
                f.remote.replace(identity, value, member)
                def inventory(path, collection=None):
                    values = pages(path, collection)
                    if fault in ('duplicate-id', 'oversized') and collection == 'artifacts' and '/actions/runs/103/' in path:
                        return values + [dict(values[0])] if fault == 'duplicate-id' else [dict(values[0], id=i+1) for i in range(10001)]
                    return values
                with self.subTest(fault=fault), patch.object(f.api, 'pages', side_effect=inventory), self.forbidden(f), self.assertRaises(Refusal):
                    self.observe(f, location)
                self.assertEqual(journal.read(), before)
                with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt', 'missing-approval', f.source)
                self.assertNotIn(f.case_token, f.revoked)
                f.clock[0] = now
        self.exercise(continuation=check)

    def test_finalizer_ack_loss_cannot_export_or_publish_coding_evidence(self):
        def check(*args):
            import registry
            f = self.pending(args)
            instances = []; finalize = broker_finalize.Finalizer._finalize
            write = registry.Registry.finalize_operation
            def track(instance, *pos, **kw):
                instances.append(instance)
                return finalize(instance, *pos, **kw)
            def uncertain(instance, *pos, **kw):
                write(instance, *pos, **kw)
                raise OSError('finalizer ACK lost')
            with patch.object(broker_finalize.Finalizer, '_finalize', new=track), patch.object(registry.Registry, 'finalize_operation', new=uncertain):
                with self.assertRaisesRegex(OSError, 'ACK lost'): f.finalize()
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
            request = f.admission.request
            with self.assertRaises(Refusal):
                instances[-1]._direct_evidence(request['operation_id'], request['sequence'], f.native.registry.binding())
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt', 'missing-approval', f.source)
        self.exercise(continuation=check)

    def test_finalizer_export_is_exact_acknowledged_and_not_stale(self):
        def check(*args):
            f = self.pending(args)
            instances = []; finalize = broker_finalize.Finalizer._finalize
            def track(instance, *pos, **kw):
                instances.append(instance)
                return finalize(instance, *pos, **kw)
            with patch.object(broker_finalize.Finalizer, '_finalize', new=track): result = f.finalize()
            instance = instances[-1]; request = f.admission.request
            evidence = instance._direct_evidence(request['operation_id'], request['sequence'], result)
            self.assertEqual(evidence['host_receipt']['operation_id'], request['operation_id'])
            for op, seq, value in (('0'*32, request['sequence'], result),
                                   (request['operation_id'], request['sequence']+1, result),
                                   (request['operation_id'], request['sequence'], {})):
                with self.assertRaises(Refusal): instance._direct_evidence(op, seq, value)
            with self.assertRaises(Refusal): instance._finalize('invalid', 1, 1)
            with self.assertRaises(Refusal): instance._direct_evidence(request['operation_id'], request['sequence'], result)
        self.exercise(continuation=check)


if __name__ == '__main__': unittest.main()
