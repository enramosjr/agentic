"""Collect the original CLOSED terminal; remote boundaries remain modeled."""
import backend_test_support
import copy
from contextlib import ExitStack
import unittest
from unittest.mock import patch

import authority_release
import trial_controller
import trial_launch
import trial_terminal
from test_authority_broker_evidence import stamp
import test_authority_trial_host_case as host_fixture
from trusted_ci_policy import Refusal


class Holds(unittest.TestCase):
    def test_hold_precedes_owner_or_transport_access(self):
        class NoIO:
            def __getattr__(self, name): raise AssertionError(name)
        collector = trial_terminal.Native(NoIO(), NoIO())
        with self.assertRaises(authority_release.Held): collector.collect('prompt')
        with self.assertRaises(authority_release.Held): collector.cleanup()
        with self.assertRaises(Refusal): collector._collect('prompt')


@unittest.skipIf(getattr(host_fixture.NativeHost, '__unittest_skip__', False), 'optional cryptography required')
class Terminal(unittest.TestCase):
    fixture = host_fixture.NativeHost.fixture
    prepared = host_fixture.NativeHost.prepared
    connected = host_fixture.NativeHost.connected
    configured = host_fixture.NativeHost.configured
    exercise = host_fixture.NativeHost.exercise
    prepare = host_fixture.NativeHost.prepare

    def closed(self, args):
        f = host_fixture.Sequential(self, args)
        f.prepared_host(); f.host(); f.run('broker'); f.finalize()
        job = next(j for j in f.remote.jobs if j['name'] == 'finalize')
        job.update(status='completed', conclusion='success', completed_at=stamp(f.clock[0]))
        return f

    def collector(self, f, tokens=None):
        return trial_terminal.Native(trial_controller.Native(f.preparer), tokens or f.origin_factory)

    def journal(self, f):
        return f.native.provision.store(f.native.provision.root / 'trial-controller')

    def forbidden(self, f):
        stack = ExitStack()
        for api in (f.api, f.source, f.origin.api):
            stack.enter_context(patch.object(api, 'post', side_effect=AssertionError('remote write')))
            fetch = api.fetch
            def read(path, _fetch=fetch, **kwargs):
                self.assertEqual(kwargs.get('method', 'GET'), 'GET')
                return _fetch(path, **kwargs)
            stack.enter_context(patch.object(api, 'fetch', side_effect=read))
        for cls, method in ((trial_controller.Native, 'open'), (trial_launch.Native, 'run')):
            stack.enter_context(patch.object(cls, method, side_effect=AssertionError('active continuation')))
        stack.enter_context(patch.object(f.preparer.coding, 'post', side_effect=AssertionError('terminal credential mint')))
        return stack

    def test_connected_collection_without_active_ack_preserves_original_and_cleans_exact_token(self):
        def check(*args):
            f = self.closed(args)
            before = copy.deepcopy(self.journal(f).read())
            remote = copy.deepcopy(f.remote.raw)
            original = f.origin.binding()
            calls = []
            def tokens(token):
                self.assertEqual(token, f.case_token)
                api = f.origin_factory(token)
                fetch = api.fetch
                def revoke(path, **kw):
                    self.assertEqual((path, kw), ('/installation/token', dict(method='DELETE', binary=True)))
                    calls.append(token)
                    return fetch(path, **kw)
                api.fetch = revoke
                return api
            # Model a restarted process by losing active ACKs. No owner-reconstruction
            # or hosted-process isolation claim is made by this fixture.
            f.native.provision._controller_acknowledgements.clear()
            with self.assertRaisesRegex(Refusal, 'acknowledgement'):
                trial_controller.Native(f.preparer)._open('prompt', 'direct-push', f.source)
            with self.forbidden(f): result = self.collector(f, tokens)._collect('prompt', f.source)
            self.assertTrue(result['terminal_collected']); self.assertTrue(result['cleanup_complete'])
            self.assertTrue(result['intended_denial_verified'])
            self.assertFalse(result['hosted_qualified']); self.assertFalse(result['enforcement_active'])
            after = self.journal(f).read()['value']
            self.assertEqual(after['phase'], 'terminal')
            for key in ('request', 'certificate', 'candidate', 'history', 'record'):
                self.assertEqual(after[key], before['value'][key])
            self.assertEqual(result['terminal'], after['terminal'])
            self.assertEqual(after['terminal']['locator']['run_id'], 101)
            self.assertEqual(f.origin.binding(), original)
            self.assertEqual(f.remote.raw, remote)
            self.assertEqual(calls, [f.case_token])
            self.assertIn(f.case_token, f.revoked)
            with self.assertRaises(Refusal): self.collector(f)._collect('prompt', f.source)
            self.assertEqual(calls, [f.case_token])
        self.exercise(continuation=check)

    def test_direct_denial_evidence_and_legacy_terminal_fail_closed(self):
        def check(*args):
            import io, json, zipfile
            f = self.closed(args)
            before = self.journal(f).read()
            artifacts, raw = copy.deepcopy(f.remote.artifacts), copy.deepcopy(f.remote.raw)
            def document(prefix):
                a = next(a for a in f.remote.artifacts if a['name'].startswith(prefix))
                with zipfile.ZipFile(io.BytesIO(f.remote.raw[a['id']])) as z:
                    member = z.namelist()[0]
                    return a['id'], member, json.loads(z.read(member))
            for fault in ('legacy', 'envelope', 'actor', 'request', 'category', 'before', 'record',
                          'intent', 'acceptance', 'rules', 'reviews', 'missing-host', 'conflict'):
                f.remote.artifacts[:] = copy.deepcopy(artifacts); f.remote.raw.clear(); f.remote.raw.update(raw)
                identity, member, terminal = document('trial-case-terminal-')
                if fault == 'legacy':
                    terminal['schema_version'] = 1; terminal.pop('recovery', None)
                elif fault == 'envelope': terminal['recovery']['operation_digest'] = '0'*64
                elif fault == 'conflict':
                    a = next(a for a in f.remote.artifacts if a['name'].endswith('-host-denied'))
                    f.remote.artifacts.append(dict(a, id=999999, name=a['name'].replace('-host-denied', '-dispatch')))
                elif fault == 'missing-host':
                    f.remote.artifacts[:] = [a for a in f.remote.artifacts if not a['name'].startswith('trial-host-denial-')]
                else:
                    identity, member, outcome = document('trial-host-denial-')
                    observation = outcome['observation']
                    if fault == 'actor': observation['actor_id'] += 1
                    if fault == 'request': observation['request']['data']['force'] = True
                    if fault == 'category': observation['denial_category'] = 'required_check'
                    if fault == 'before': observation['before'] = '0'*40
                    if fault == 'record': outcome['record']['request_sent'] = False
                    if fault == 'intent': outcome['intent']['issued'] += 1000
                    if fault == 'acceptance': observation['acceptance']['coordinates']['evidence_digest'] = '0'*64
                    if fault == 'rules': observation['rules'] = []
                    if fault == 'reviews': observation['reviews'] = []
                    f.remote.replace(identity, outcome, member)
                if fault in ('legacy', 'envelope'): f.remote.replace(identity, terminal, member)
                with self.subTest(fault=fault), self.forbidden(f), self.assertRaises(Refusal):
                    self.collector(f)._collect('prompt', f.source)
                self.assertEqual(self.journal(f).read(), before)
                self.assertNotIn(f.case_token, f.revoked)
        self.exercise(continuation=check)

    def test_verified_first_case_progresses_but_history_never_grants_current_freshness(self):
        def check(*args):
            import trial_case
            f = self.closed(args)
            retained=self.journal(f).read()['value']
            result = self.collector(f)._collect('prompt', f.source)
            self.assertTrue(result['intended_denial_verified'])
            f.second()
            self.assertEqual(f.admission.candidate['name'], 'coding-update')
            history = f.admission.value['history']
            # Historical reconstruction reads CLOSED proof, not today's target/checks/reviews.
            target=f.source.refs['main']
            f.source.refs['main'] = '0'*40
            with patch.object(f.source, 'pages', side_effect=AssertionError('historical live prerequisites')):
                settled = trial_case.baseline(f.origin, f.native.registry, f.admission.record, history, lambda:f.clock[0])
            self.assertEqual(settled, result['terminal']['binding'])
            terminal=result['terminal']['document']
            with self.assertRaises(Refusal):
                __import__('trial_host_case')._direct_outcome(terminal['before'],f.admission.record,retained,
                    f.api,terminal['host_receipt']['host'],f.clock[0],f.source)
            f.source.refs['main']=target
        self.exercise(continuation=check)

    def test_closed_outcome_semantics_are_checked_beyond_archive_and_chain_digests(self):
        def check(*args):
            import io, json, zipfile, trial_host_case
            from trusted_ci_policy import digest
            f = self.closed(args)
            retained = self.journal(f).read()['value']
            a = next(a for a in f.remote.artifacts if a['name'].startswith('trial-host-denial-'))
            identity, metadata, raw = a['id'], copy.deepcopy(a), f.remote.raw[a['id']]
            with zipfile.ZipFile(io.BytesIO(raw)) as z: original = json.loads(z.read('trial-host-denial.json'))
            terminal = next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
            with zipfile.ZipFile(io.BytesIO(f.remote.raw[terminal['id']])) as z:
                before = json.loads(z.read('trial-case-terminal.json'))['before']
            locator = dict(run_id=101,attempt=1,job_id=original['job_id'],artifact_id=identity)
            trial_host_case._direct_outcome(before,f.admission.record,retained,f.api,locator,f.clock[0])
            for fault, message in (('actor','intended'),('category','intended'),('request','intended'),
                                   ('intent','intent'),('coordinates','coordinates'),('rules','obligation'),
                                   ('reviews','human'),('check','issuer acceptance')):
                value = copy.deepcopy(original); observation = value['observation']
                if fault=='actor': observation['actor_id'] += 1
                if fault=='category': observation['denial_category'] = 'required_check'
                if fault=='request': observation['request']['data']['force'] = True
                if fault=='intent': value['intent']['issued'] += 1000
                if fault=='coordinates': observation['acceptance']['coordinates']['task_digest'] = '0'*64
                if fault=='rules': observation['rules'] = []
                if fault=='reviews': observation['reviews'] = []
                if fault=='check': observation['acceptance']['check']['check_id'] += 1
                value['record']['evidence_digest'] = digest(observation)
                f.remote.replace(identity,value,'trial-host-denial.json')
                with self.subTest(fault=fault), self.forbidden(f), self.assertRaisesRegex(Refusal,message):
                    trial_host_case._direct_outcome(before,f.admission.record,retained,f.api,locator,f.clock[0])
                f.remote.raw[identity]=raw; a.clear(); a.update(metadata)
            pages=f.source.pages
            for part in ('check-runs','rules/branches','reviews'):
                def missing(path, *pos): return [] if part in path else pages(path,*pos)
                with self.subTest(current=part), patch.object(f.source,'pages',side_effect=missing), self.assertRaises(Refusal):
                    self.collector(f)._collect('prompt',f.source)
                self.assertEqual(self.journal(f).read()['value'],retained)
        self.exercise(continuation=check)

    def test_finalizer_exports_only_acknowledged_exact_invocation_and_clears_reuse(self):
        def check(*args):
            import broker_finalize, registry
            f = host_fixture.Sequential(self,args)
            f.prepared_host(); f.host(); f.run('broker')
            instances=[]; finalize=broker_finalize.Finalizer._finalize
            def track(instance,*pos,**kw):
                instances.append(instance)
                return finalize(instance,*pos,**kw)
            with patch.object(broker_finalize.Finalizer,'_finalize',new=track): result=f.finalize()
            instance=instances[-1]; request=f.admission.request
            evidence=instance._direct_evidence(request['operation_id'],request['sequence'],result)
            self.assertEqual(evidence['recovery']['kind'],'broker-terminal-recovery')
            with self.assertRaises(Refusal): instance._direct_evidence('0'*32,request['sequence'],result)
            with self.assertRaises(Refusal): instance._finalize('invalid',1,1)
            with self.assertRaises(Refusal): instance._direct_evidence(request['operation_id'],request['sequence'],result)
        self.exercise(continuation=check)
        def lost(*args):
            import broker_finalize, registry
            f = host_fixture.Sequential(self,args)
            f.prepared_host(); f.host(); f.run('broker')
            instances=[]; finalize=broker_finalize.Finalizer._finalize; write=registry.Registry.finalize_operation
            def track(instance,*pos,**kw):
                instances.append(instance)
                return finalize(instance,*pos,**kw)
            def uncertain(instance,*pos,**kw):
                write(instance,*pos,**kw)
                raise OSError('finalizer ACK lost')
            with patch.object(broker_finalize.Finalizer,'_finalize',new=track), patch.object(registry.Registry,'finalize_operation',new=uncertain):
                with self.assertRaisesRegex(OSError,'ACK lost'): f.finalize()
            self.assertFalse(any(a['name'].startswith('trial-case-terminal-') for a in f.remote.artifacts))
            request=f.admission.request
            with self.assertRaises(Refusal): instances[-1]._direct_evidence(request['operation_id'],request['sequence'],f.native.registry.binding())
        self.exercise(continuation=lost)

    def test_inventory_and_owner_faults_never_complete_or_revoke(self):
        def check(*args):
            f = self.closed(args)
            collector = self.collector(f)
            before = self.journal(f).read()
            pages = f.api.pages
            for fault in ('missing-job', 'open', 'failed', 'duplicate-job', 'duplicate-artifact',
                          'missing-artifact', 'oversized', 'malformed', 'bad-id', 'duplicate-id', 'foreign-run'):
                def inventory(path, collection=None):
                    values = pages(path, collection)
                    if '/actions/runs/101/' not in path: return values
                    values = copy.deepcopy(values)
                    if collection == 'jobs':
                        job = next(v for v in values if v['name'] == 'finalize')
                        if fault == 'missing-job': values.remove(job)
                        if fault == 'open': job['status'] = 'in_progress'
                        if fault == 'failed': job['conclusion'] = 'failure'
                        if fault == 'foreign-run': job['run_id'] = 999
                        if fault == 'duplicate-job': values.append(dict(job, id=99999))
                        if fault == 'oversized': return [dict(job, id=i+1) for i in range(10001)]
                        if fault == 'malformed': values.append(None)
                        if fault == 'bad-id': job['id'] = True
                        if fault == 'duplicate-id': values.append(dict(job, name='unrelated'))
                    if collection == 'artifacts':
                        artifact = next(v for v in values if v['name'].startswith('trial-case-terminal-'))
                        if fault == 'missing-artifact': values.remove(artifact)
                        if fault == 'duplicate-artifact': values.append(dict(artifact, id=99999))
                    return values
                with self.subTest(fault=fault), patch.object(f.api, 'pages', side_effect=inventory):
                    with self.assertRaises(Refusal): collector._collect('prompt', f.source)
                self.assertEqual(self.journal(f).read(), before)
                self.assertNotIn(f.case_token, f.revoked)
            with self.assertRaises(Refusal): collector._collect('changed prompt', f.source)
            launch = f.native.provision.store(f.native.provision.root / 'trial-case-launch')
            saved = launch.read()
            for field, value in (('phase', 'prepared'), ('link', dict(saved['value']['link'],
                    handshake=dict(saved['value']['link']['handshake'], run_id=999)))):
                changed = copy.deepcopy(saved['value']); changed[field] = value
                written = launch.write(launch.read(), changed)
                with self.assertRaises(Refusal): collector._collect('prompt', f.source)
                launch.write(written, saved['value'])
            changed = copy.deepcopy(saved['value'])
            changed['link']['handshake']['attempt'] = 2
            launch.write(launch.read(), changed)
            with self.assertRaises(Refusal): collector._collect('prompt', f.source)
            self.assertEqual(self.journal(f).read(), before)
        self.exercise(continuation=check)

    def test_substituted_terminal_current_state_and_expiry_refuse(self):
        def check(*args):
            import io, json, zipfile
            f = self.closed(args)
            collector = self.collector(f)
            before = self.journal(f).read()
            artifact = next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
            identity = artifact['id']
            raw, metadata = f.remote.raw[identity], copy.deepcopy(artifact)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                terminal = json.loads(archive.read('trial-case-terminal.json'))
            for fault in ('archive', 'request', 'certificate', 'fence', 'candidate', 'expiry'):
                changed = copy.deepcopy(terminal)
                target, now = f.source.refs['main'], f.clock[0]
                if fault == 'archive': artifact['digest'] = 'sha256:' + '0'*64
                if fault == 'request': changed['request_digest'] = '0'*64
                if fault == 'certificate': changed['certificate_digest'] = '0'*64
                if fault == 'fence': changed['after']['fence']['sequence'] += 1
                if fault == 'candidate': f.source.refs['main'] = '0'*40
                if fault == 'expiry': f.clock[0] += 1000
                if fault in ('request', 'certificate', 'fence'):
                    f.remote.replace(identity, changed, 'trial-case-terminal.json')
                with self.subTest(fault=fault), self.assertRaises(Refusal): collector._collect('prompt', f.source)
                self.assertEqual(self.journal(f).read(), before)
                self.assertNotIn(f.case_token, f.revoked)
                f.source.refs['main'], f.clock[0] = target, now
                f.remote.raw[identity] = raw; artifact.clear(); artifact.update(metadata)
        self.exercise(continuation=check)

    def test_lost_terminal_ack_never_adopts_visible_write_or_replays(self):
        def check(*args):
            import trial_storage
            f = self.closed(args)
            collector = self.collector(f)
            write = trial_storage.write_controller
            def lost(*pos, **kw):
                write(*pos, **kw)
                raise OSError('terminal ACK lost')
            with patch.object(trial_storage, 'write_controller', side_effect=lost):
                with self.assertRaisesRegex(OSError, 'ACK lost'): collector._collect('prompt', f.source)
            self.assertEqual(self.journal(f).read()['value']['phase'], 'terminal')
            self.assertNotIn(f.case_token, f.revoked)
            with self.assertRaises(Refusal): collector._collect('prompt', f.source)
            with self.forbidden(f): collector._cleanup()
            self.assertIn(f.case_token, f.revoked)
        self.exercise(continuation=check)

    def test_cleanup_failure_is_visible_and_independent_expired_cleanup_never_recollects(self):
        def check(*args):
            f = self.closed(args)
            def lost(token):
                api = f.origin_factory(token)
                fetch = api.fetch
                def revoke(*a, **kw):
                    fetch(*a, **kw)
                    raise OSError('revocation ACK lost')
                api.fetch = revoke
                return api
            with self.assertRaisesRegex(OSError, 'revocation ACK lost'):
                self.collector(f, lost)._collect('prompt', f.source)
            terminal = self.journal(f).read()
            self.assertEqual(terminal['value']['phase'], 'terminal')
            self.assertIn(f.case_token, f.revoked)
            f.clock[0] += 1000
            with self.forbidden(f): self.collector(f)._cleanup()
            self.assertEqual(self.journal(f).read(), terminal)
            self.assertEqual(f.native.provision.store(f.native.provision.root / 'trial-case-read-staging').read()['value']['phase'], 'revoked')
        self.exercise(continuation=check)


if __name__ == '__main__': unittest.main()
