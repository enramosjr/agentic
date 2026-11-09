"""Real native launch and shared host denial, with only remote boundaries faked."""
import backend_test_support
import copy
import unittest
from unittest.mock import patch

import merge_transport
import service
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal
import test_authority_trial_launch as launch_fixture
from test_authority_broker_evidence import stamp


class HostFixture(launch_fixture.Launched):
    def prepared_host(self):
        self.ready(name='direct-push')
        next(v for v in self.source.prs if v['number']==self.admission.candidate['submitted']['pr'])['mergeable']=True
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.close_handoff(); self.published()
        self.attempts=[]
        tokens=self.tokens
        def factory(token):
            scoped=tokens(token); fetch=scoped.fetch
            def send(path,*pos,**kw):
                if path.endswith('/git/refs/heads/main'):
                    self.owner.assertTrue(any(a['name'].startswith('trial-host-intent-') for a in self.remote.artifacts))
                    self.attempts.append((path,pos,kw))
                    self.owner.assertEqual(kw,dict(method='PATCH',data=dict(sha=self.admission.request['snapshot']['merge'],force=False)))
                    if getattr(self,'fault',None)=='unknown': raise OSError('unknown host effect')
                    if getattr(self,'fault',None)=='changed': self.source.refs['main']='0'*40
                    raise HostRefusal(403,'required_check' if getattr(self,'fault',None)=='wrong-denial' else 'protected_update',None)
                return fetch(path,*pos,**kw)
            scoped.fetch=send
            return scoped
        self.tokens=factory

    def host(self):
        env=self.job('trial host denial','trial_host_denial')
        env.update(GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
            AGENTIC_CODING_PRIVATE_KEY=self.api.secrets['AGENTIC_CODING_PRIVATE_KEY'],
            **{__import__('trial_case').CaseReadStaging.NAME:self.case_token})
        result=service._case_producer(env,self.hint,'fixture-node','host-denial',clock=lambda:self.clock[0],
            api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),
            app_factory=self.apps,token_factory=self.tokens,uploader_factory=lambda *a:self.upload)
        self.remote.jobs[-1].update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))
        return result


@unittest.skipIf(getattr(launch_fixture.Launch,'__unittest_skip__',False),'optional cryptography required')
class NativeHost(unittest.TestCase):
    fixture=launch_fixture.Launch.fixture
    prepared=launch_fixture.Launch.prepared
    connected=launch_fixture.Launch.connected
    configured=launch_fixture.Launch.configured
    exercise=launch_fixture.Launch.exercise
    prepare=launch_fixture.Launch.prepare

    def test_native_direct_push_denial_closes_without_broker_dispatch(self):
        def check(*args):
            f=HostFixture(self,args); f.prepared_host()
            with patch.object(merge_transport,'isolated',side_effect=AssertionError('negative case dispatched')):
                f.host()
                result=f.run('broker')
            self.assertEqual(result['state'],'host-denied')
            self.assertEqual(len(f.attempts),1)
            self.assertEqual(f.merges,[])
            terminal=f.finalize()
            self.assertIsNone(terminal['fence']['pending'])
            self.assertEqual(terminal['fence']['completed'][-1]['kind'],'not-submitted')
            self.assertEqual(len(f.dispatched),1)
            # The actual automatic finalizer, not a second native finalization,
            # supplies the CLOSED observation consumed into native ownership.
            job=next(j for j in f.remote.jobs if j['name']=='finalize')
            job.update(status='completed',conclusion='success',completed_at=stamp(f.clock[0]))
            artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
            location=dict(run_id=101,attempt=1,job_id=job['id'],artifact_id=artifact['id'])
            import trial_controller
            owner=trial_controller.Native(f.preparer)
            observed=owner._observe_terminal('prompt','direct-push',location,f.source)
            self.assertEqual(observed['binding'],terminal)
            retained=f.native.provision.store(f.native.provision.root/'trial-controller').read()['value']
            self.assertEqual(retained['phase'],'terminal')
            self.assertEqual(retained['terminal']['locator'],location)
            with self.assertRaises(Refusal): f.coordinate()
            self.assertEqual(len(f.attempts),1)
        self.exercise(continuation=check)

    def test_unknown_effect_and_unintended_denial_keep_fence_and_never_replay(self):
        for fault in ('unknown','wrong-denial','changed'):
            def check(*args):
                f=HostFixture(self,args); f.prepared_host(); f.fault=fault
                with self.assertRaises((OSError,Refusal)): f.host()
                self.assertEqual(len(f.attempts),1)
                with self.assertRaises(Refusal): f.host()
                self.assertEqual(len(f.attempts),1)
                with self.assertRaises(Refusal): f.run('broker')
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
                self.assertFalse(any(a['name'].endswith(('-host-denied','-not-submitted','-dispatch')) for a in f.remote.artifacts))
                self.assertEqual(f.merges,[])
                return f.source.refs['main']
            with self.subTest(fault=fault): self.exercise(continuation=check)

    def test_closed_outcome_substitution_blocks_broker_and_terminal(self):
        def check(*args):
            f=HostFixture(self,args); f.prepared_host(); f.host()
            artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-host-denial-'))
            import io,json,zipfile
            with zipfile.ZipFile(io.BytesIO(f.remote.raw[artifact['id']])) as archive:
                original=json.loads(archive.read('trial-host-denial.json'))
            for fault in ('certificate','intent','snapshot','category','record','job'):
                value=copy.deepcopy(original)
                if fault=='certificate': value['certificate_digest']='0'*64
                if fault=='intent': value['intent']['request']['data']['force']=True
                if fault=='snapshot': value['snapshot']['head']='0'*40
                if fault=='category': value['observation']['denial_category']='permission_scope'
                if fault=='record': value['record']['request_sent']=False
                if fault=='job': value['job_id']+=1
                f.remote.replace(artifact['id'],value,'trial-host-denial.json')
                with self.assertRaises(Refusal): f.run('broker')
            f.remote.replace(artifact['id'],original,'trial-host-denial.json')
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
            broker.update(status='in_progress',conclusion=None,completed_at=None)
            self.assertEqual(f.run('broker')['state'],'host-denied')
            original['record']['before']='0'*40
            f.remote.replace(artifact['id'],original,'trial-host-denial.json')
            with self.assertRaises(Refusal): f.finalize()
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            self.assertEqual(len(f.attempts),1)
        self.exercise(continuation=check)

    def test_native_terminal_owner_consumes_denial_and_forbids_replay(self):
        def check(*args):
            f=HostFixture(self,args); f.prepared_host(); f.host(); f.run('broker')
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
            terminal=f.admission.finalize(f.job('finalize','finalize'),broker['id'])
            self.assertEqual(f.admission.value['phase'],'terminal')
            self.assertEqual(f.admission.value['terminal'],terminal)
            self.assertEqual(terminal['fence']['completed'][-1]['kind'],'not-submitted')
            with self.assertRaises(Refusal): f.coordinate()
            self.assertEqual(len(f.attempts),1)
        self.exercise(continuation=check)

    def test_missing_success_or_human_review_never_retains_intent_or_sends(self):
        for missing in ('check','review'):
            def check(*args):
                f=HostFixture(self,args); f.prepared_host()
                if missing=='check': f.checks=[]
                else: f.reviews=[]
                with self.assertRaises(Refusal): f.host()
                self.assertEqual(f.attempts,[])
                self.assertFalse(any(a['name'].startswith('trial-host-intent-') for a in f.remote.artifacts))
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            with self.subTest(missing=missing): self.exercise(continuation=check)

    def test_lost_intent_ack_never_sends_or_retries_host_effect(self):
        def check(*args):
            f=HostFixture(self,args); f.prepared_host(); upload=f.upload
            def store(name,raw):
                identity=upload(name,raw)
                if name.startswith('trial-host-intent-'): raise OSError('lost intent acknowledgement')
                return identity
            f.upload=store
            with self.assertRaises(OSError): f.host()
            with self.assertRaisesRegex(Refusal,'never replay'): f.host()
            self.assertEqual(f.attempts,[])
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)

    def test_unknown_terminal_upload_never_replays_finalization_or_completes_native(self):
        for committed in (False,True):
            def check(*args):
                f=HostFixture(self,args); f.prepared_host(); f.host(); f.run('broker')
                upload=f.upload
                def store(name,raw):
                    if name.startswith('trial-case-terminal-'):
                        if committed: upload(name,raw)
                        raise OSError('unknown terminal artifact upload')
                    return upload(name,raw)
                f.upload=store
                with self.assertRaises(OSError): f.finalize()
                job=next(j for j in f.remote.jobs if j['name']=='finalize')
                job.update(status='completed',conclusion='failure',completed_at=stamp(f.clock[0]))
                self.assertIsNone(f.registry.binding()['fence']['pending'])
                with self.assertRaises(Refusal): f.finalize()
                with self.assertRaises(Refusal): f.coordinate()
                if committed:
                    artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
                    import trial_controller
                    with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._observe_terminal('prompt','direct-push',
                        dict(run_id=101,attempt=1,job_id=job['id'],artifact_id=artifact['id']),f.source)
                self.assertEqual(f.native.provision.store(f.native.provision.root/'trial-controller').read()['value']['phase'],'bound')
                self.assertEqual(len(f.attempts),1)
            with self.subTest(committed=committed): self.exercise(continuation=check)

    def test_terminal_observer_authenticates_exact_closed_result(self):
        def check(*args):
            f=HostFixture(self,args); f.prepared_host(); f.host(); f.run('broker'); f.finalize()
            job=next(j for j in f.remote.jobs if j['name']=='finalize')
            job.update(status='completed',conclusion='success',completed_at=stamp(f.clock[0]))
            artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
            import io,json,zipfile,trial_controller
            with zipfile.ZipFile(io.BytesIO(f.remote.raw[artifact['id']])) as archive:
                original=json.loads(archive.read('trial-case-terminal.json'))
            location=dict(run_id=101,attempt=1,job_id=job['id'],artifact_id=artifact['id'])
            owner=trial_controller.Native(f.preparer)
            for fault in ('request','certificate','parent','result','interval'):
                value=copy.deepcopy(original)
                if fault=='request': value['request_digest']='0'*64
                if fault=='certificate': value['certificate_digest']='0'*64
                if fault=='parent': value['before']['branch_head']=f.admission.record['trial']['branch_head']
                if fault=='result': value['after']['fence']['completed'][-1]['receipt_digest']='0'*64
                if fault=='interval': value['completed']+=1
                f.remote.replace(artifact['id'],value,'trial-case-terminal.json')
                with self.assertRaises(Refusal): owner._observe_terminal('prompt','direct-push',location,f.source)
                self.assertEqual(f.native.provision.store(f.native.provision.root/'trial-controller').read()['value']['phase'],'bound')
            f.remote.replace(artifact['id'],original,'trial-case-terminal.json')
            f.clock[0]+=501
            with self.assertRaises(Refusal): owner._observe_terminal('prompt','direct-push',location,f.source)
        self.exercise(continuation=check)

    def test_terminal_rechecks_fresh_capability_after_blocking_artifact_read(self):
        def check(*args):
            f=HostFixture(self,args); f.prepared_host(); f.host(); f.run('broker')
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
            fetch=f.api.fetch; writes=[]
            def read(path,*pos,**kw):
                value=fetch(path,*pos,**kw)
                if '/actions/artifacts/' in path: f.clock[0]+=501
                return value
            post=f.api.post
            def write(path,*args):
                if '/git/' in path: writes.append(path)
                return post(path,*args)
            f.api.fetch=read; f.api.post=write
            with self.assertRaises(Refusal): f.admission.finalize(f.job('finalize','finalize'),broker['id'])
            self.assertEqual(writes,[])
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)

    def test_lost_terminal_ack_recovers_only_retained_commit_without_writes(self):
        for committed in (True,False):
            def check(*args):
                f=HostFixture(self,args); f.prepared_host(); f.host(); f.run('broker')
                broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
                api=f.registry.api; fetch=api.fetch; writes=[]
                def send(path,*pos,**kw):
                    if path.endswith('/git/refs/heads/agentic-registry') and kw.get('method')=='PATCH':
                        writes.append(path)
                        if committed: fetch(path,*pos,**kw)
                        raise OSError('unknown terminal registry acknowledgement')
                    return fetch(path,*pos,**kw)
                api.fetch=send
                # Crash after the committed terminal readback but before the
                # native completion journal, or lose an uncommitted PATCH.
                progress=f.registry.authenticate_setup_progress
                if committed:
                    f.registry.authenticate_setup_progress=lambda *a,**kw:(_ for _ in ()).throw(OSError('native completion interrupted'))
                with self.assertRaises((OSError,Refusal)): f.admission.finalize(f.job('finalize','finalize'),broker['id'])
                f.registry.authenticate_setup_progress=progress
                import trial_controller
                owner=trial_controller.Native(f.preparer)
                if committed:
                    result=owner._recover_terminal('prompt','direct-push',f.source)
                    self.assertIsNone(result['fence']['pending'])
                else:
                    with self.assertRaises(Refusal): owner._recover_terminal('prompt','direct-push',f.source)
                self.assertEqual(len(writes),1)
                self.assertEqual(len(f.attempts),1)
            with self.subTest(committed=committed): self.exercise(continuation=check)
