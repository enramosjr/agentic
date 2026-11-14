"""Third-case evidence through native engines; remote boundaries remain modeled."""
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
from test_authority_broker_evidence import stamp
import test_authority_trial_coding_terminal as coding_fixture
from trusted_ci_policy import Refusal, digest


class Holds(unittest.TestCase):
    def test_observation_hold_precedes_transport(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        with self.assertRaises(authority_release.Held):
            trial_controller.Native(NoIO()).observe_terminal('prompt', 'missing-approval', {})


@unittest.skipIf(getattr(coding_fixture.CodingTerminal, '__unittest_skip__', False), 'optional cryptography required')
class MissingTerminal(unittest.TestCase):
    fixture = coding_fixture.CodingTerminal.fixture
    prepared = coding_fixture.CodingTerminal.prepared
    connected = coding_fixture.CodingTerminal.connected
    configured = coding_fixture.CodingTerminal.configured
    exercise = coding_fixture.CodingTerminal.exercise
    prepare = coding_fixture.CodingTerminal.prepare
    forbidden = coding_fixture.CodingTerminal.forbidden
    collector = coding_fixture.CodingTerminal.collector
    document = coding_fixture.CodingTerminal.document
    closed = coding_fixture.CodingTerminal.closed

    def pending(self, args):
        f = coding_fixture.CodingTerminal.pending(self, args)
        f.finalize()
        with self.forbidden(f), patch.object(service, '_source_token', side_effect=AssertionError('terminal mint')):
            f.observe()
        trial_launch.revoke(f.native.provision, f.origin_factory, name='coding-update')
        f.second('missing-approval', 105, 'fresh-third-case')
        with self.assertRaisesRegex(Refusal, 'pending'): f.coordinate()
        f.close_handoff(); f.published()
        self.assertTrue(f.reviews)
        f.reviews = []  # Only the modeled external reviewer withdraws approval.
        f.host(); f.run('broker')
        return f

    def journal(self, f):
        return f.native.provision.store(f.native.provision.root / 'trial-controller-missing-approval')

    def observe(self, f, location):
        with self.forbidden(f), patch.object(service, '_source_token', side_effect=AssertionError('terminal mint')):
            return trial_controller.Native(f.preparer)._observe_terminal('prompt', 'missing-approval', location, f.source)

    def history(self, f, location):
        before = self.journal(f).read()['value']
        publication = f.native.provision.store(f.native.provision.root / 'trial-case-publication-missing-approval').read()['value']
        return before['history'] + [dict(revision=publication['revision_bound'], terminal=location)]

    def test_three_case_evidence_observation_cleanup_and_fourth_selection(self):
        def check(*args):
            f, location = self.closed(args)
            original = f.origin.binding(); retained = self.journal(f).read()['value']
            _, _, document = self.document(f, 'trial-case-terminal-')
            self.assertEqual(document['schema_version'], 2)
            self.assertEqual(digest(document['recovery']), document['after']['fence']['completed'][-1]['receipt_digest'])
            terminal = self.observe(f, location)
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
            trial_launch.revoke(f.native.provision, tokens, name='missing-approval')
            self.assertEqual(calls, [f.case_token])
            f.second('expired-proof', 107, 'fresh-fourth-case')
            history = f.admission.value['history']
            self.assertEqual(len(history), 3)
            cases = [trial_case.read(f.origin, v['revision'], lambda:f.clock[0])[0] for v in history]
            self.assertEqual([v['candidate']['name'] for v in cases], ['direct-push', 'coding-update', 'missing-approval'])
            for field in ('pr', 'head', 'task_id'):
                self.assertEqual(len({v['candidate']['submitted'][field] for v in cases}), 3)
            self.assertEqual(f.origin.binding(), original)
            self.assertEqual(f.source.refs['main'], retained['request']['snapshot']['base'])
            target = f.source.refs['main']; f.source.refs['main'] = '0'*40
            with patch.object(f.source, 'pages', side_effect=AssertionError('historical live prerequisites')), \
                 patch.object(service, '_source_token', side_effect=AssertionError('historical mint')):
                self.assertEqual(trial_case.baseline(f.origin, f.native.registry, f.admission.record, history,
                                                    lambda:f.clock[0]), terminal['binding'])
            with self.assertRaises(Refusal):
                trial_host_case._missing_outcome(document['before'], f.admission.record, retained,
                    f.api, document['host_receipt']['host'], f.clock[0], f.source)
            f.source.refs['main'] = target
            self.assertEqual(terminal['binding']['deployment']['state'], 'qualification')
            self.assertIsNone(terminal['binding']['deployment']['qualification'])
        self.exercise(continuation=check)

    def test_legacy_missing_terminal_refused_by_both_consumers(self):
        def check(*args):
            f, location = self.closed(args); journal = self.journal(f); before = journal.read()
            identity, member, terminal = self.document(f, 'trial-case-terminal-')
            terminal['schema_version'] = 1
            terminal.pop('recovery', None); terminal.pop('host_receipt', None)
            f.remote.replace(identity, terminal, member)
            with self.assertRaises(Refusal): self.observe(f, location)
            self.assertEqual(journal.read(), before)
            with self.assertRaises(Refusal):
                trial_case.baseline(f.origin, f.native.registry, f.admission.record, self.history(f, location), lambda:f.clock[0])
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt', 'expired-proof', f.source)
            self.assertNotIn(f.case_token, f.revoked)
        self.exercise(continuation=check)

    def test_missing_semantics_current_prerequisites_and_review_inventories(self):
        def check(*args):
            f, location = self.closed(args); before = self.journal(f).read()
            _, _, terminal = self.document(f, 'trial-case-terminal-')
            identity, member, outcome = self.document(f, 'trial-host-denial-')
            metadata = copy.deepcopy(next(a for a in f.remote.artifacts if a['id'] == identity)); raw = f.remote.raw[identity]
            def validate():
                return trial_host_case._missing_outcome(terminal['before'], f.admission.record, before['value'],
                    f.api, terminal['host_receipt']['host'], f.clock[0])
            validate()
            review = dict(id=1, state='APPROVED', commit_id=before['value']['request']['snapshot']['head'])
            for reviews in ([dict(review, state='DISMISSED')], [dict(review, commit_id='0'*40)]):
                value = copy.deepcopy(outcome); value['observation']['reviews'] = reviews
                value['record']['evidence_digest'] = digest(value['observation'])
                f.remote.replace(identity, value, member)
                validate()
            f.remote.raw[identity] = raw
            next(a for a in f.remote.artifacts if a['id'] == identity).update(metadata)
            faults = ('case', 'actor', 'method', 'path', 'data', 'status', 'target', 'category', 'obligation',
                      'record', 'intent', 'coordinates', 'rules', 'approval', 'duplicate-review', 'oversized-review',
                      'malformed-review', 'check')
            for fault in faults:
                value = copy.deepcopy(outcome); o = value['observation']
                if fault == 'case': value['case'] = 'coding-update'
                if fault == 'actor': o['actor_id'] = f.admission.record['pair']['identities']['apps']['coding']['actor_id']
                if fault == 'method': o['request']['method'] = 'PATCH'
                if fault == 'path': o['request']['path'] += '0'
                if fault == 'data': o['request']['data']['sha'] = '0'*40
                if fault == 'status': o['http_status'] = 200
                if fault == 'target': o['after'] = '0'*40
                if fault == 'category': o['denial_category'] = 'protected_update'
                if fault == 'obligation': o['denied_obligation'] = 'foreign'
                if fault == 'record': value['record']['request_sent'] = False
                if fault == 'intent': value['intent']['issued'] += 1000
                if fault == 'coordinates': o['acceptance']['coordinates']['task_digest'] = '0'*64
                if fault == 'rules': o['rules'] = []
                if fault == 'approval': o['reviews'] = [review]
                if fault == 'duplicate-review': o['reviews'] = [dict(review, state='DISMISSED')]*2
                if fault == 'oversized-review': o['reviews'] = [dict(review, id=i+1, state='DISMISSED') for i in range(10001)]
                if fault == 'malformed-review': o['reviews'] = [dict(state='DISMISSED')]
                if fault == 'check': o['acceptance']['check']['check_id'] += 1
                value['record']['evidence_digest'] = digest(o)
                f.remote.replace(identity, value, member)
                with self.subTest(fault=fault), self.forbidden(f), self.assertRaises(Refusal): validate()
                if fault in ('actor', 'approval'):
                    with self.subTest(history=fault), patch.object(service, '_source_token', side_effect=AssertionError('historical mint')), self.assertRaises(Refusal):
                        trial_case.baseline(f.origin, f.native.registry, f.admission.record, self.history(f, location), lambda:f.clock[0])
                f.remote.raw[identity] = raw
                next(a for a in f.remote.artifacts if a['id'] == identity).update(metadata)
            pages = f.source.pages
            for fault in ('check-runs', 'rules/branches', 'reviews', 'duplicate-review', 'oversized-review', 'malformed-review'):
                def changed(path, *pos):
                    if path.endswith('/reviews'):
                        if fault == 'duplicate-review': return [dict(review, state='DISMISSED')]*2
                        if fault == 'oversized-review': return [dict(review, id=i+1, state='DISMISSED') for i in range(10001)]
                        if fault == 'malformed-review': return [dict(state='DISMISSED', commit_id=review['commit_id'])]
                    if fault in path: return [review] if fault == 'reviews' else []
                    return pages(path, *pos)
                with self.subTest(current=fault), patch.object(f.source, 'pages', side_effect=changed), self.assertRaises(Refusal):
                    self.observe(f, location)
                self.assertEqual(self.journal(f).read(), before)
        self.exercise(continuation=check)

    def test_native_ack_loss_refuses_adoption_and_cleanup_survives_expiry(self):
        def check(*args):
            f, location = self.closed(args); journal = self.journal(f)
            write = type(journal.raw).write
            def uncertain(instance, *pos, **kw):
                result = write(instance, *pos, **kw)
                if instance.root == journal.raw.root: raise OSError('missing terminal ACK lost')
                return result
            with patch.object(type(journal.raw), 'write', new=uncertain), self.assertRaisesRegex(OSError, 'ACK lost'):
                self.observe(f, location)
            f.native.provision._controller_acknowledgements.clear()
            with self.assertRaises(Refusal): self.observe(f, location)
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt', 'expired-proof', f.source)
            f.clock[0] = f.admission.record['expires'] + 1
            trial_launch.revoke(f.native.provision, f.origin_factory, name='missing-approval')
            self.assertIn(f.case_token, f.revoked)
        self.exercise(continuation=check)

    def test_chain_inventory_and_deadlines_preserve_progression(self):
        def check(*args):
            f, location = self.closed(args); journal = self.journal(f); before = journal.read()
            identity, member, terminal = self.document(f, 'trial-case-terminal-')
            artifacts, raw = copy.deepcopy(f.remote.artifacts), copy.deepcopy(f.remote.raw)
            now = f.clock[0]; pages = f.api.pages
            for fault in ('request', 'certificate', 'envelope', 'host', 'broker', 'conflict', 'missing-host', 'duplicate', 'oversized', 'expiry'):
                value = copy.deepcopy(terminal)
                f.remote.artifacts[:] = copy.deepcopy(artifacts); f.remote.raw.clear(); f.remote.raw.update(raw)
                if fault == 'request': value['request_digest'] = '0'*64
                if fault == 'certificate': value['certificate_digest'] = '0'*64
                if fault == 'envelope': value['recovery']['operation_digest'] = '0'*64
                if fault == 'host': value['host_receipt']['host_digest'] = '0'*64
                if fault == 'broker': value['recovery']['producer']['id'] += 1
                if fault == 'conflict':
                    a = next(a for a in f.remote.artifacts if a['name'].endswith('-host-denied'))
                    f.remote.artifacts.append(dict(a, id=999999, name=a['name'].replace('-host-denied', '-dispatch')))
                if fault == 'missing-host': f.remote.artifacts[:] = [a for a in f.remote.artifacts if not a['name'].startswith('trial-host-denial-')]
                if fault == 'expiry': f.clock[0] = f.admission.record['expires'] + 1
                f.remote.replace(identity, value, member)
                def inventory(path, collection=None):
                    values = pages(path, collection)
                    if collection == 'artifacts' and '/actions/runs/105/' in path:
                        if fault == 'duplicate': return values + [dict(values[0])]
                        if fault == 'oversized': return [dict(values[0], id=i+1) for i in range(10001)]
                    return values
                with self.subTest(fault=fault), patch.object(f.api, 'pages', side_effect=inventory), self.assertRaises(Refusal): self.observe(f, location)
                self.assertEqual(journal.read(), before)
                with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt', 'expired-proof', f.source)
                self.assertNotIn(f.case_token, f.revoked); f.clock[0] = now
        self.exercise(continuation=check)

    def test_finalizer_ack_loss_cannot_export_or_publish(self):
        def check(*args):
            import registry
            f = self.pending(args); instances = []; finalize = broker_finalize.Finalizer._finalize
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
            with self.assertRaises(Refusal): instances[-1]._direct_evidence(request['operation_id'], request['sequence'], f.native.registry.binding())
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt', 'expired-proof', f.source)
        self.exercise(continuation=check)

    test_finalizer_export_is_exact_acknowledged_and_not_stale = coding_fixture.CodingTerminal.test_finalizer_export_is_exact_acknowledged_and_not_stale


if __name__ == '__main__': unittest.main()
