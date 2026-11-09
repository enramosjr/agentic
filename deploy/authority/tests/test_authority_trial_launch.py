"""One native READY dispatch reaches the shared pending and terminal engines."""
import backend_test_support
import unittest
import copy
from unittest.mock import patch

import trial_launch
import trial_case
import trial_controller
import service
import merge_transport
import app_proofs
from test_authority_app_proofs import AppAPI
from test_authority_broker_evidence import stamp
import test_authority_trial_case as case_fixture
from trusted_ci_policy import Refusal


class Launched(case_fixture.Fresh):
    def ready(self, lost=False, absent=False, name='positive'):
        self.admission=trial_controller.Native(self.preparer)._open('prompt',name,self.source)
        candidate=self.admission.candidate['submitted']
        self.synthetic(next(v for v in self.source.prs if v['number']==candidate['pr']))
        self.reviews=[dict(id=900,user=dict(id=self.p['reviewers'][0],type='User'),state='APPROVED',commit_id=candidate['head'])]
        self.tar=self.archive(candidate)
        d=self.admission.record['origin']['binding']['deployment']
        root=AppAPI(d,app_proofs.load_identities(d),'reader')
        post=root.post
        root.post=lambda *args:dict(post(*args),token='fresh-case-ready',expires_at=stamp(self.clock[0]+500))
        self.revoked=set()
        outer=self
        class Read:
            token='fresh-case-ready'
            def get(self,path):
                if self.token in outer.revoked: raise Refusal('revoked')
                return outer.origin.api.get(path)
            def pages(self,*args): return [{'id':outer.origin.coordinates['repository_id']}]
            def fetch(self,*args,**kwargs): outer.revoked.add(self.token)
        self.origin_factory=lambda token:Read()
        self.case_token=Read.token
        self.launch=trial_launch.Native(self.admission,root,self.origin_factory)
        self.dispatched=[]
        send,pages=self.api.post,self.api.pages
        def dispatch(path,body):
            if not path.endswith('/dispatches'): return send(path,body)
            self.owner.assertIn(trial_case.CaseReadStaging.NAME,self.api.secrets)
            self.owner.assertIsNone(self.registry.binding()['fence']['pending'])
            self.dispatched.append(copy.deepcopy(body))
            self.ready_hint=__import__('json').loads(body['inputs']['handoff'])
            env=self.job('trial case ready','trial_case_ready')
            env.update(GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
                       **{trial_case.CaseReadStaging.NAME:self.case_token})
            service._case_launch(env,self.ready_hint,'fixture-node','ready',clock=lambda:self.clock[0],
                api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),uploader_factory=lambda *a:self.upload)
            self.remote.jobs[-1].update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))
            if absent: self.remote.artifacts=[]
            self.job('prepare','prepare')
            if lost: raise OSError('lost case dispatch acknowledgement')
        self.api.post=dispatch
        def inventory(path,collection=None):
            if collection=='workflow_runs': return [copy.deepcopy(self.remote.run)] if self.dispatched else []
            return pages(path,collection)
        self.api.pages=inventory
        self.admin_root=self.apps(self.d['apps']['admin'],self.api.secrets['AGENTIC_ADMIN_PRIVATE_KEY'])

    def coordinate(self):
        return self.launch._run('prompt',self.admin_root,self.tokens)

    def close_handoff(self):
        env=self.job('prepare','prepare')
        env.update(GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
                   **{trial_case.CaseReadStaging.NAME:self.case_token})
        request=service._case_launch(env,self.ready_hint,'fixture-node','prepare',clock=lambda:self.clock[0],
            api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token))
        self.remote.jobs[1].update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))
        env=self.job('trial case handoff','trial_case_handoff')
        env.update(GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
                   **{trial_case.CaseReadStaging.NAME:self.case_token})
        location=service._case_producer(env,request['handoff'],'fixture-node','handoff',clock=lambda:self.clock[0],
            api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),uploader_factory=lambda *a:self.upload)
        self.remote.jobs[-1].update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))
        self.fresh=[]
        self.coordinate()
        self.hint=request['handoff']
        return request

    def finalize(self):
        # Exercise the automatic same-run terminal job and independently staged
        # finalization pin, rather than the separate recovery-run fixture.
        env=super(case_fixture.Fresh,self).job('finalize case fixture','unused')
        job=self.remote.jobs[-1]
        job.update(name='finalize')
        env.update(GITHUB_JOB='finalize',GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
            AGENTIC_RECOVERY_PIN=self.api.variables['AGENTIC_FINALIZE_PIN'],
            AGENTIC_ADMIN_PRIVATE_KEY=self.api.secrets['AGENTIC_ADMIN_PRIVATE_KEY'],
            **{trial_case.CaseReadStaging.NAME:self.case_token})
        return service._case_producer(env,self.hint,'fixture-node','finalize',clock=lambda:self.clock[0],
            api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),
            app_factory=self.apps,token_factory=self.tokens,uploader_factory=lambda *a:self.upload)


@unittest.skipIf(getattr(case_fixture.TrialCase,'__unittest_skip__',False),'optional cryptography required')
class Launch(unittest.TestCase):
    fixture=case_fixture.TrialCase.fixture
    def prepared(self):
        import test_authority_trial_configuration as configuration_fixture
        origin=configuration_fixture.provisioning.intent()
        origin['policy']['workflow']='.github/workflows/authority-v2.yml'
        with patch.object(configuration_fixture.provisioning,'intent',return_value=origin):
            return case_fixture.TrialCase.prepared(self)
    connected=case_fixture.TrialCase.connected
    configured=case_fixture.TrialCase.configured
    exercise=case_fixture.TrialCase.exercise
    prepare=case_fixture.TrialCase.prepare

    def test_ready_dispatch_reaches_shared_merge_and_terminal(self):
        def check(*args):
            f=Launched(self,args); f.ready()
            with self.assertRaisesRegex(Refusal,'pending'): f.coordinate()
            request=f.close_handoff()
            self.assertEqual(request['snapshot']['run_id'],101)
            self.assertEqual(len(f.dispatched),1)
            self.assertEqual(f.dispatched[0]['inputs']['mode'],'case')
            f.published()
            with patch.object(merge_transport,'isolated',side_effect=f.transport): result=f.run('broker')
            self.assertEqual(result['state'],'submitted')
            terminal=f.finalize()
            self.assertIsNone(terminal['fence']['pending'])
            self.assertEqual(terminal['fence']['completed'][-1]['kind'],'merged')
            self.assertEqual(len(f.merges),1)
            f.launch.staging.revoke()
            self.assertIn(f.case_token,f.revoked)
            return f.source.refs['main']
        self.exercise(continuation=check)

    def test_unknown_dispatch_recovers_once_and_withdrawn_review_closes_denial(self):
        def check(*args):
            f=Launched(self,args); f.ready(lost=True)
            with self.assertRaises(OSError): f.coordinate()
            # A new native coordinator reuses retained intent, not an old token
            # handshake or a second workflow POST.
            f.launch=trial_launch.Native(f.admission,f.launch.reader,f.origin_factory)
            with self.assertRaisesRegex(Refusal,'pending'): f.coordinate()
            f.close_handoff(); f.published(); f.reviews=[]
            with patch.object(merge_transport,'isolated',side_effect=AssertionError('denial dispatched')),self.assertRaisesRegex(Refusal,'independent approval'):
                f.run('broker')
            next(j for j in f.remote.jobs if j['name'].startswith('broker ('))['conclusion']='failure'
            terminal=f.finalize()
            self.assertEqual(terminal['fence']['completed'][-1]['kind'],'not-submitted')
            self.assertIsNone(terminal['fence']['pending'])
            self.assertEqual(len(f.dispatched),1)
            self.assertEqual(f.merges,[])
            with self.assertRaises(Refusal): f.coordinate()
        self.exercise(continuation=check)

    def test_missing_or_substituted_ready_proof_never_fences_or_redispatches(self):
        for fault in ('missing','token','expired'):
            def check(*args):
                f=Launched(self,args); f.ready(absent=fault=='missing')
                if fault=='missing':
                    with self.assertRaisesRegex(Refusal,'pending'): f.coordinate()
                else:
                    # Stop just after the real CLOSED consumer returns, before
                    # native selection and fence acquisition.
                    send=f.api.post
                    def pause(path,body):
                        result=send(path,body)
                        if path.endswith('/dispatches'): raise OSError('fixture pause')
                        return result
                    f.api.post=pause
                    with self.assertRaises(OSError): f.coordinate()
                    if fault=='expired': f.clock[0]+=501
                    else:
                        artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-ready-'))
                        import io,json,zipfile
                        with zipfile.ZipFile(io.BytesIO(f.remote.raw[artifact['id']])) as archive:
                            value=json.loads(archive.read('trial-case-ready.json'))
                        value['token_digest']='0'*64
                        f.remote.replace(artifact['id'],value,'trial-case-ready.json')
                for _ in range(2):
                    with self.assertRaises(Refusal): f.coordinate()
                self.assertEqual(len(f.dispatched),1)
                self.assertIsNone(f.registry.binding()['fence']['pending'])
                self.assertEqual(f.merges,[])
            with self.subTest(fault=fault): self.exercise(continuation=check)

    def test_unknown_ready_publication_recovers_only_exact_committed_ref(self):
        for committed in (False,True):
            def check(*args):
                f=Launched(self,args); f.ready()
                send=f.origin.api.post; writes=[]
                def post(path,body):
                    if path.endswith('/git/refs') and body['ref'].endswith('-case-ready'):
                        writes.append(copy.deepcopy(body))
                        if committed: send(path,body)
                        raise OSError('unknown READY publication')
                    return send(path,body)
                f.origin.api.post=post
                with self.assertRaises(OSError): f.coordinate()
                f.launch=trial_launch.Native(f.admission,f.launch.reader,f.origin_factory)
                from trusted_ci_github import HostRefusal
                with self.assertRaises((Refusal,HostRefusal)): f.coordinate()
                self.assertEqual(len(writes),1)
                self.assertEqual(len(f.dispatched),int(committed))
            with self.subTest(committed=committed): self.exercise(continuation=check)

    def test_delegation_expiring_during_fence_readback_refuses_git_effects(self):
        for broken in (True,False):
            def check(*args):
                f=Launched(self,args); f.ready(lost=True)
                with self.assertRaises(OSError): f.coordinate()
                get,post=f.api.get,f.api.post
                writes=[]; moved=[]
                def read(path):
                    result=get(path)
                    if f.admission.value['phase']=='fencing' and '/git/commits/' in path and not moved:
                        f.clock[0]+=501; moved.append(path)
                    return result
                def write(path,body):
                    if '/git/' in path: writes.append(path)
                    return post(path,body)
                f.api.get,f.api.post=read,write
                prepare=service._prepare_trial
                def without_launch(*args,**kwargs):
                    kwargs.pop('launch',None)
                    return prepare(*args,**kwargs)
                with patch.object(service,'_prepare_trial',without_launch if broken else prepare),self.assertRaises(Refusal):
                    f.coordinate()
                self.assertTrue(moved)
                # The deliberately broken variant demonstrates that the native
                # lifetime alone would permit writes after delegation expiry.
                self.assertEqual(bool(writes),broken)
                self.assertEqual(f.registry.binding()['fence']['pending'] is not None,broken)
            with self.subTest(broken=broken): self.exercise(continuation=check)

    def test_late_expiry_refuses_pending_publication_and_execution_binding_writes(self):
        for phase in ('publication-started','bind-started'):
            def check(*args):
                f=Launched(self,args); f.ready()
                if phase=='bind-started':
                    with self.assertRaisesRegex(Refusal,'pending'): f.coordinate()
                    # Stop the second coordination call after the CLOSED
                    # handoff upload; the next call must guard its Git effects.
                    coordinate=f.coordinate
                    f.coordinate=lambda:None
                    f.close_handoff()
                    f.coordinate=coordinate
                get,post=f.origin.api.get,f.origin.api.post
                writes=[]; moved=[]
                def read(path):
                    value=get(path)
                    state=f.native.provision.store(f.native.provision.root/'trial-case-publication').read()
                    if state is not None and state['value']['phase']==phase and '/git/commits/' in path and not moved:
                        f.clock[0]+=501; moved.append(path)
                    return value
                def write(path,body):
                    if moved and '/git/' in path: writes.append(path)
                    return post(path,body)
                f.origin.api.get,f.origin.api.post=read,write
                with self.assertRaises(Refusal): f.coordinate()
                self.assertTrue(moved)
                self.assertEqual(writes,[])
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
                self.assertEqual(len(f.dispatched),1)
            with self.subTest(phase=phase): self.exercise(continuation=check)

    def test_retained_cleanup_after_expiry_needs_no_live_admission_or_coordinator(self):
        def check(*args):
            f=Launched(self,args); f.ready(lost=True)
            with self.assertRaises(OSError): f.coordinate()
            c=f.native.provision
            f.clock[0]+=501
            with patch.object(f.admission,'guard',side_effect=AssertionError('expired admission accessed')):
                trial_launch.revoke(c,f.origin_factory)
                trial_launch.revoke(c,f.origin_factory)
            self.assertIn(f.case_token,f.revoked)
            self.assertEqual(len(f.dispatched),1)
            self.assertEqual(c.store(c.root/trial_case.CaseReadStaging.JOURNAL).read()['value']['phase'],'revoked')
        self.exercise(continuation=check)


class Holds(unittest.TestCase):
    def test_public_launch_holds_before_access(self):
        import authority_release
        with self.assertRaises(authority_release.Held): trial_launch.Native(None).run('prompt')

    def test_fixed_case_workflow_has_ready_before_prepare_and_closed_handoff_before_verify(self):
        import test_authority_producer_workflow as workflow_fixture
        graph=workflow_fixture.ProducerWorkflowContracts()
        graph.setUp()
        self.assertIn('case',graph.workflow.split('options:',1)[1].split('\n',1)[0])
        self.assertIn('needs: [discover, trial_case_ready]',graph.jobs['prepare'])
        self.assertIn('needs: [prepare]',graph.jobs['trial_case_handoff'])
        self.assertIn('needs: [prepare, trial_case_handoff]',graph.jobs['verify'])
        for job in ('trial_case_ready','prepare','trial_case_handoff','verify','publish','broker','controls','finalize'):
            self.assertIn('AGENTIC_TRIAL_CASE_ORIGIN_TOKEN',graph.jobs[job])
            self.assertNotIn('contents: write',graph.jobs[job])
        self.assertIn("'case-prepare'",graph.jobs['prepare'])
        self.assertIn('role: case-ready',graph.jobs['trial_case_ready'])
        self.assertIn('role: case-handoff',graph.jobs['trial_case_handoff'])


if __name__ == '__main__': unittest.main()
