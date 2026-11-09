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
                if path.endswith('/git/refs/heads/main') or path.endswith('/merge'):
                    self.owner.assertTrue(any(a['name'].startswith('trial-host-intent-') for a in self.remote.artifacts))
                    self.attempts.append((path,pos,kw))
                    missing=self.admission.candidate['name']=='missing-approval'
                    self.owner.assertEqual(kw,dict(method='PUT',data=dict(sha=self.admission.request['snapshot']['head'],merge_method='merge')) if missing else
                                           dict(method='PATCH',data=dict(sha=self.admission.request['snapshot']['merge'],force=False)))
                    if getattr(self,'fault',None)=='unknown': raise OSError('unknown host effect')
                    if getattr(self,'fault',None)=='changed': self.source.refs['main']='0'*40
                    raise HostRefusal(403,'required_check' if getattr(self,'fault',None)=='wrong-denial' else 'required_review' if missing else 'protected_update',None)
                return fetch(path,*pos,**kw)
            scoped.fetch=send
            return scoped
        self.tokens=factory

    def host(self, change=None, selected=None, app_factory=None):
        env=self.job('trial host denial','trial_host_denial')
        purpose='merge' if self.admission.candidate['name']=='missing-approval' else 'coding'
        env.update(GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
            **{'AGENTIC_'+purpose.upper()+'_PRIVATE_KEY':self.api.secrets['AGENTIC_'+purpose.upper()+'_PRIVATE_KEY']},
            **{__import__('trial_case').CaseReadStaging.NAME:self.case_token})
        if change: change(env)
        result=service._case_producer(env,self.hint,'fixture-node','host-denial',clock=lambda:self.clock[0],
            api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),
            app_factory=app_factory or self.apps,token_factory=self.tokens,uploader_factory=lambda *a:self.upload,
            host_case=selected or self.admission.candidate['name'])
        self.remote.jobs[-1].update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))
        return result


class Sequential(HostFixture):
    """Keep both independent remote runs and every artifact address alive."""
    def __init__(self,owner,args):
        super().__init__(owner,args)
        import re
        self.runs={101:self.remote}
        get,pages,fetch=self.api.get,self.api.pages,self.api.fetch
        def remote(path):
            match=re.search(r'/actions/runs/(\d+)',path)
            return self.runs.get(int(match[1])) if match else None
        self.api.get=lambda path:copy.deepcopy(remote(path).run) if remote(path) else get(path)
        self.api.pages=lambda path,collection=None:copy.deepcopy(remote(path).jobs if collection=='jobs' else remote(path).artifacts) if remote(path) else pages(path,collection)
        def download(path,**kw):
            if '/actions/artifacts/' in path:
                identity=int(path.split('/')[-2])
                for run in self.runs.values():
                    if identity in run.raw: return run.fetch(path,**kw)
            return fetch(path,**kw)
        self.api.fetch=download

    def job(self,name,key):
        run=self.remote.run['id']
        if not any(j['name']==name for j in self.remote.jobs):
            self.remote.jobs.append(dict(id=run*100+len(self.remote.jobs),run_id=run,head_sha=self.p['workflow_sha'],name=name,
                status='in_progress',conclusion=None,started_at=stamp(self.clock[0]),completed_at=None))
        return dict(GITHUB_REPOSITORY_ID=str(self.p['authority_repository_id']),GITHUB_SHA=self.p['workflow_sha'],
            GITHUB_RUN_ID=str(run),GITHUB_RUN_ATTEMPT='1',GITHUB_JOB=key)

    def upload(self,name,raw):
        from artifact_uploader import document_member
        import json
        if any(a['name']==name for a in self.remote.artifacts): raise Refusal('fixture artifact conflict')
        identity=self.remote.run['id']*100+50000+len(self.remote.artifacts)
        self.remote.artifacts.append(dict(id=identity,name=name,expired=False,created_at=stamp(self.clock[0]),
            workflow_run=dict(id=self.remote.run['id'],repository_id=self.p['authority_repository_id'],
                head_repository_id=self.p['authority_repository_id'],head_sha=self.p['workflow_sha'])))
        self.remote.replace(identity,json.loads(raw),document_member(name))
        return identity

    def finalize(self):
        import trial_case
        env=self.job('finalize','finalize')
        env.update(GITHUB_REPOSITORY=self.p['authority_repository'],GITHUB_TOKEN='case-actions-read',
            AGENTIC_RECOVERY_PIN=self.api.variables['AGENTIC_FINALIZE_PIN'],
            AGENTIC_ADMIN_PRIVATE_KEY=self.api.secrets['AGENTIC_ADMIN_PRIVATE_KEY'],
            **{trial_case.CaseReadStaging.NAME:self.case_token})
        return service._case_producer(env,self.hint,'fixture-node','finalize',clock=lambda:self.clock[0],
            api_factory=lambda token:self.api if token=='case-actions-read' else self.origin_factory(token),
            app_factory=self.apps,token_factory=self.tokens,uploader_factory=lambda *a:self.upload)

    def observe(self):
        import trial_controller
        job=next(j for j in self.remote.jobs if j['name']=='finalize')
        job.update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))
        artifact=next(a for a in self.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
        location=dict(run_id=self.remote.run['id'],attempt=1,job_id=job['id'],artifact_id=artifact['id'])
        return trial_controller.Native(self.preparer)._observe_terminal('prompt',self.admission.candidate['name'],location,self.source)

    def second(self, name='coding-update', run=103, token='fresh-second-case'):
        from test_authority_broker_evidence import AuthorityAPI
        previous=self.remote
        self.remote=AuthorityAPI(self.d,self.clock)
        self.remote.run=copy.deepcopy(previous.run); self.remote.run['id']=run
        def replace(identity,value,member):
            import io,json,zipfile,hashlib
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as archive: archive.writestr(zipfile.ZipInfo(member),json.dumps(value))
            raw=stream.getvalue(); self.remote.raw[identity]=raw
            next(a for a in self.remote.artifacts if a['id']==identity)['digest']='sha256:'+hashlib.sha256(raw).hexdigest()
        self.remote.replace=replace
        self.runs[run]=self.remote
        self.ready(name=name,token=token)
        next(v for v in self.source.prs if v['number']==self.admission.candidate['submitted']['pr'])['mergeable']=True

    def through_second(self):
        self.prepared_host(); self.host(); self.run('broker'); self.finalize(); self.observe()
        self.second()
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.close_handoff(); self.published(); self.host(); self.run('broker'); self.finalize(); self.observe()

    def third(self):
        self.through_second()
        self.second('missing-approval',105,'fresh-third-case')
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.close_handoff(); self.published()


@unittest.skipIf(getattr(launch_fixture.Launch,'__unittest_skip__',False),'optional cryptography required')
class NativeHost(unittest.TestCase):
    fixture=launch_fixture.Launch.fixture
    prepared=launch_fixture.Launch.prepared
    connected=launch_fixture.Launch.connected
    configured=launch_fixture.Launch.configured
    exercise=launch_fixture.Launch.exercise
    prepare=launch_fixture.Launch.prepare

    def test_three_native_cases_close_missing_approval_through_merger_host(self):
        def check(*args):
            import trial_controller,trial_case,trial_launch
            f=Sequential(self,args); f.prepared_host()
            origin=f.origin.binding(); original=copy.deepcopy(f.admission.record)
            retained=[]; tokens=[]; candidates=[]
            with patch.object(merge_transport,'isolated',side_effect=AssertionError('host negative dispatched')):
                for index,name in enumerate(('direct-push','coding-update','missing-approval')):
                    if index:
                        f.second(name,103 if index==1 else 105,'fresh-case-'+name)
                        with self.assertRaisesRegex(Refusal,'pending'): f.coordinate()
                        f.admission=trial_controller.Native(f.preparer)._open('prompt',name,f.source)
                        f.launch=trial_launch.Native(f.admission,f.launch.reader,f.origin_factory)
                        request=f.close_handoff()
                        self.assertEqual(request['host_case'],name)
                        f.published()
                    if index==2:
                        self.assertTrue(f.reviews)  # Genuine independent preparation/publication first.
                        f.reviews=[]  # External withdrawal is confined to the local host-negative fixture.
                    tokens.append(f.case_token); candidates.append(copy.deepcopy(f.admission.candidate))
                    f.host(); self.assertEqual(f.run('broker')['state'],'host-denied')
                    terminal=f.finalize(); self.assertEqual(f.observe()['binding'],terminal)
                    retained.append((f.remote.run['id'],copy.deepcopy(f.remote.raw),
                        f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',f.admission.candidate)).read()))
                self.assertEqual(len(f.attempts),3)
                self.assertEqual(f.attempts[-1][0],'/repos/'+f.p['repository']+'/pulls/'+str(candidates[-1]['submitted']['pr'])+'/merge')
                self.assertEqual(f.merges,[])
                self.assertEqual(f.admission.record,original)
                self.assertEqual(f.origin.binding(),origin)
                self.assertEqual(len(f.admission.value['history']),2)
                self.assertEqual(len(f.admission.value['candidates']['value']['candidates']),16)
                self.assertEqual(f.native.provision.store(f.native.provision.root/'trial-read-staging').read()['value']['phase'],'revoked')
                self.assertEqual(len({c['submitted']['head'] for c in candidates}),3)
                self.assertEqual(len({c['submitted']['pr'] for c in candidates}),3)
                self.assertEqual(len(set(tokens)),3)
                self.assertTrue(set(tokens[:2])<=f.revoked)
                for i,(run,raw,journal) in enumerate(retained):
                    self.assertEqual(f.runs[run].raw,raw)
                    self.assertEqual(f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',candidates[i])).read(),journal)
                    if i<2:
                        prior,record=trial_case.read(f.origin,f.admission.value['history'][i]['revision'],lambda:f.clock[0])
                        self.assertEqual(prior['candidate'],candidates[i]); self.assertEqual(record,original)
                self.assertEqual([r['kind'] for r in terminal['fence']['completed'][-3:]],['not-submitted']*3)
                self.assertEqual(terminal['deployment']['state'],'qualification')
                self.assertIsNone(terminal['deployment']['qualification'])
                f.clock[0]+=1000
                trial_launch.revoke(f.native.provision,f.origin_factory,name='missing-approval')
                self.assertTrue(set(tokens)<=f.revoked)
        self.exercise(continuation=check)

    def test_third_selection_authenticates_both_owned_terminals_and_histories(self):
        def check(*args):
            import trial_controller
            f=Sequential(self,args); f.through_second()
            for name in ('direct-push','coding-update'):
                store=f.native.provision.store(f.native.provision.root/trial_controller.case_journal('trial-controller',dict(name=name)))
                saved=store.read(); value=copy.deepcopy(saved['value']); value['terminal']['binding']['fence']['completed'][-1]['receipt_digest']='0'*64
                changed=store.write(saved,value)
                with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','missing-approval',f.source)
                self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-controller-missing-approval').read())
                store.write(changed,saved['value'])
            for index in (0,1):
                run=f.runs[101 if index==0 else 103]
                artifact=next(a for a in run.artifacts if a['name'].startswith('trial-case-terminal-'))
                import io,json,zipfile
                with zipfile.ZipFile(io.BytesIO(run.raw[artifact['id']])) as archive: saved=json.loads(archive.read('trial-case-terminal.json'))
                value=copy.deepcopy(saved); value['request_digest']='0'*64
                current=f.remote; f.remote=run; run.replace(artifact['id'],value,'trial-case-terminal.json'); f.remote=current
                with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','missing-approval',f.source)
                f.remote=run; run.replace(artifact['id'],saved,'trial-case-terminal.json'); f.remote=current
            self.assertEqual(len(f.attempts),2)
        self.exercise(continuation=check)

    def test_third_credentials_scheduling_and_current_success_fail_before_host_effect(self):
        def check(*args):
            import trial_case,trial_launch
            from registry import Registry
            f=Sequential(self,args); f.third()
            count=len(f.remote.artifacts); calls=[]
            def construct(*args): calls.append(args); return f.apps(*args)
            for selected in ('direct-push','coding-update',True,'human-update'):
                with self.subTest(selected=selected),self.assertRaises(Refusal): f.host(selected=selected,app_factory=construct)
            self.assertEqual(calls,[])
            for change in (lambda env:env.update(AGENTIC_CODING_PRIVATE_KEY=f.api.secrets['AGENTIC_CODING_PRIVATE_KEY']),
                           lambda env:env.pop('AGENTIC_MERGE_PRIVATE_KEY')):
                with self.assertRaises(Refusal): f.host(change=change,app_factory=construct)
            self.assertEqual(calls,[])
            for name in ('direct-push','coding-update'):
                from trial_controller import case_journal
                old=f.native.provision.store(f.native.provision.root/case_journal('trial-case-read-staging',dict(name=name))).read()['value']['credential']['token']
                f.revoked.discard(old)  # Even an accepting transport cannot supply authority.
                with self.assertRaises(Refusal): f.host(change=lambda env:env.update(**{trial_case.CaseReadStaging.NAME:old}),app_factory=construct)
                env=f.job('trial case ready','trial_case_ready'); env[trial_case.CaseReadStaging.NAME]=old
                with self.assertRaises(Refusal): trial_launch.consume(f.registry,Registry(f.origin_factory(old),f.origin.coordinates),env,f.ready_hint,lambda:f.clock[0])
                env=f.job('trial case handoff','trial_case_handoff'); env.update(GITHUB_REPOSITORY=f.p['authority_repository'],GITHUB_TOKEN='case-actions-read',**{trial_case.CaseReadStaging.NAME:old})
                with self.assertRaises(Refusal): service._case_producer(env,f.hint,'fixture-node','handoff',clock=lambda:f.clock[0],
                    api_factory=lambda token:f.api if token=='case-actions-read' else f.origin_factory(token),uploader_factory=lambda *a:f.upload)
            self.assertEqual(calls,[])
            with self.assertRaisesRegex(Refusal,'candidate approval'): f.host()
            f.reviews=[]
            checks=copy.deepcopy(f.checks)
            f.checks=[]
            with self.assertRaises(Refusal): f.host()
            f.checks=checks
            self.assertEqual(len(f.remote.artifacts),count)
            self.assertEqual(len(f.attempts),2)
        self.exercise(continuation=check)

    def test_third_unknown_unintended_or_missing_effect_never_replays_and_cleans_after_expiry(self):
        for fault in ('unknown','wrong-denial','changed','expired'):
            def check(*args):
                import trial_launch
                f=Sequential(self,args); f.third(); f.reviews=[]
                archives={run:copy.deepcopy(f.runs[run].raw) for run in (101,103)}
                if fault=='expired': f.clock[0]+=501
                else: f.fault=fault
                with self.assertRaises((OSError,Refusal)): f.host()
                count=len(f.attempts)
                with self.assertRaises(Refusal): f.host()
                with self.assertRaises(Refusal): f.run('broker')
                self.assertEqual(len(f.attempts),count)
                self.assertEqual(count,2 if fault=='expired' else 3)
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
                self.assertEqual(f.merges,[])
                for run,raw in archives.items(): self.assertEqual(f.runs[run].raw,raw)
                state=f.native.provision.store(f.native.provision.root/'trial-controller-missing-approval').read()
                self.assertEqual(state['value']['phase'],'bound')
                f.clock[0]+=1000
                trial_launch.revoke(f.native.provision,f.origin_factory,name='missing-approval')
                self.assertIn(f.case_token,f.revoked)
                self.assertEqual(f.native.provision.store(f.native.provision.root/'trial-controller-missing-approval').read(),state)
                return f.source.refs['main']
            with self.subTest(fault=fault): self.exercise(continuation=check)

    def test_third_late_approval_after_intent_prevents_host_effect_and_replay(self):
        def check(*args):
            f=Sequential(self,args); f.third(); reviews=copy.deepcopy(f.reviews); f.reviews=[]
            # The existing shared probe must reread missing approval after durable
            # intent, immediately before its effect, even if approval arrives late.
            upload=f.upload
            def arriving(name,raw):
                value=upload(name,raw)
                if name.startswith('trial-host-intent-'): f.reviews=reviews
                return value
            f.upload=arriving
            with self.assertRaisesRegex(Refusal,'candidate approval'): f.host()
            self.assertEqual(len(f.attempts),2)
            with self.assertRaises(Refusal): f.host()
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)

    def test_third_closed_outcome_authenticates_exact_actor_request_and_denial(self):
        def check(*args):
            import io,json,zipfile
            from trusted_ci_policy import digest
            f=Sequential(self,args); f.third(); f.reviews=[]; f.host()
            artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-host-denial-'))
            with zipfile.ZipFile(io.BytesIO(f.remote.raw[artifact['id']])) as archive: saved=json.loads(archive.read('trial-host-denial.json'))
            mutations=(lambda o:o.update(actor_id=f.admission.record['pair']['identities']['apps']['coding']['actor_id']),
                lambda o:o['request'].update(method='PATCH'),lambda o:o['request']['data'].update(sha='0'*40),
                lambda o:o.update(denial_category='protected_update'),lambda o:o.update(denied_obligation=f.p['check_name']),
                lambda o:o.update(http_status=500),lambda o:o.update(after='0'*40),
                lambda o:o.update(reviews=[dict(state='APPROVED',commit_id=f.admission.request['snapshot']['head'])]))
            for mutation in mutations:
                value=copy.deepcopy(saved); mutation(value['observation']); value['record']['evidence_digest']=digest(value['observation'])
                f.remote.replace(artifact['id'],value,'trial-host-denial.json')
                for job in f.remote.jobs:
                    if job['name'].startswith('broker ('): job.update(status='in_progress',conclusion=None,completed_at=None)
                with self.assertRaises(Refusal): f.run('broker')
                self.assertFalse(any(a['name'].endswith('-host-denied') for a in f.remote.artifacts))
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            f.remote.replace(artifact['id'],saved,'trial-host-denial.json')
            next(j for j in f.remote.jobs if j['name'].startswith('broker (')).update(status='in_progress',conclusion=None,completed_at=None)
            self.assertEqual(f.run('broker')['state'],'host-denied')
            terminal=f.finalize(); self.assertEqual(f.observe()['binding'],terminal)
            self.assertEqual(len(f.attempts),3); self.assertEqual(f.merges,[])
        self.exercise(continuation=check)

    def test_third_host_effect_rechecks_both_prior_ready_pending_and_execution_refs(self):
        def check(*args):
            import trial_case
            from registry import trial_reference
            f=Sequential(self,args); f.third(); f.reviews=[]
            tokens=f.tokens
            for entry in f.admission.value['history']:
                prior,_=trial_case.read(f.origin,entry['revision'],lambda:f.clock[0])
                refs=(trial_reference(prior),trial_reference(dict(prior,execution=None)),
                      trial_reference(dict(prior,kind='trial-case-ready',execution=None)))
                for ref in refs:
                    key=ref; revision=f.origin.api.refs[key]; moved=[]
                    def factory(token):
                        scoped=tokens(token); get=scoped.get
                        def read(path):
                            result=get(path)
                            if path.endswith('/pulls/'+str(f.admission.candidate['submitted']['pr'])):
                                f.origin.api.refs[key]=f.admission.value['workflow']['value']['revision_bound']; moved.append(path)
                            return result
                        scoped.get=read
                        return scoped
                    f.tokens=factory
                    with self.subTest(ref=ref),self.assertRaisesRegex(Refusal,'prior case reference moved'): f.host()
                    self.assertTrue(moved)
                    self.assertEqual(len(f.attempts),2)
                    self.assertFalse(any(a['name'].startswith('trial-host-intent-') for a in f.remote.artifacts))
                    f.origin.api.refs[key]=revision
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
        self.exercise(continuation=check)

    def test_third_source_move_during_late_prerequisites_prevents_host_request(self):
        def check(*args):
            from qualification_cases import HostCases
            f=Sequential(self,args); f.third(); f.reviews=[]
            prerequisite=HostCases._prerequisites; reads=[]
            def moved(probe,case):
                result=prerequisite(probe,case); reads.append(case['name'])
                if len(reads)==2: f.source.refs['main']='0'*40
                return result
            with patch.object(HostCases,'_prerequisites',moved),self.assertRaisesRegex(Refusal,'base changed|moved'):
                f.host()
            self.assertEqual(reads,['missing-approval']*2)
            self.assertEqual(len(f.attempts),2)
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            return f.source.refs['main']
        self.exercise(continuation=check)

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

    def test_second_reserved_case_requires_owned_closed_first_terminal(self):
        def check(*args):
            import trial_controller
            f=HostFixture(self,args); f.prepared_host()
            owner=trial_controller.Native(f.preparer)
            with self.assertRaises(Refusal): owner._open('prompt','coding-update',f.source)
            f.host(); f.run('broker'); terminal=f.finalize()
            job=next(j for j in f.remote.jobs if j['name']=='finalize')
            job.update(status='completed',conclusion='success',completed_at=stamp(f.clock[0]))
            artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
            location=dict(run_id=101,attempt=1,job_id=job['id'],artifact_id=artifact['id'])
            with self.assertRaises(Refusal): owner._open('prompt','coding-update',f.source)
            owner._observe_terminal('prompt','direct-push',location,f.source)
            original=f.native.provision.store(f.native.provision.root/'trial-controller').read()
            second=owner._open('prompt','coding-update',f.source)
            self.assertEqual(second.binding,terminal)
            self.assertNotEqual(second.binding,second.record['trial'])
            self.assertNotEqual(second.candidate['submitted']['head'],f.admission.candidate['submitted']['head'])
            self.assertEqual(second.value['history'],[dict(revision=
                f.native.provision.store(f.native.provision.root/'trial-case-publication').read()['value']['revision_bound'],terminal=location)])
            self.assertEqual(f.native.provision.store(f.native.provision.root/'trial-controller').read(),original)
        self.exercise(continuation=check)

    def test_two_native_host_cases_retain_distinct_runs_capabilities_and_history(self):
        def check(*args):
            import trial_launch,trial_controller,trial_case
            from trusted_ci_policy import digest
            f=Sequential(self,args); f.prepared_host()
            original=copy.deepcopy(f.admission.record['trial'])
            origin=f.origin.binding()
            worker_token=f.api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN']
            first_token=f.case_token
            f.host(); self.assertEqual(f.run('broker')['state'],'host-denied')
            first=f.finalize(); f.observe()
            first_journal=f.native.provision.store(f.native.provision.root/'trial-controller').read()
            first_refs=copy.deepcopy(f.origin.api.refs)
            first_archives=copy.deepcopy(f.remote.raw)
            first_candidate=copy.deepcopy(f.admission.candidate)
            f.second()
            with self.assertRaisesRegex(Refusal,'pending'): f.coordinate()
            reader=f.launch.reader
            self.assertEqual(len(reader.visible),1)
            f.admission=trial_controller.Native(f.preparer)._open('prompt','coding-update',f.source)
            f.launch=trial_launch.Native(f.admission,reader,f.origin_factory)
            self.assertIn(first_token,f.revoked)
            self.assertNotEqual(first_token,f.case_token)
            f.close_handoff(); f.published()
            with patch.object(merge_transport,'isolated',side_effect=AssertionError('negative progression dispatched')):
                f.host(); self.assertEqual(f.run('broker')['state'],'host-denied')
            second=f.finalize(); observed=f.observe()
            self.assertEqual(observed['binding'],second)
            self.assertEqual(second['fence']['completed'][:-1],first['fence']['completed'])
            self.assertEqual([r['kind'] for r in second['fence']['completed'][-2:]],['not-submitted']*2)
            self.assertNotEqual(f.admission.candidate['submitted']['head'],first_candidate['submitted']['head'])
            self.assertNotEqual(f.admission.candidate['submitted']['pr'],first_candidate['submitted']['pr'])
            self.assertEqual(f.admission.record['trial'],original)
            self.assertEqual(f.origin.binding(),origin)
            self.assertEqual({k:f.origin.api.refs[k] for k in first_refs},first_refs)
            self.assertEqual(f.runs[101].raw,first_archives)
            self.assertEqual(f.native.provision.store(f.native.provision.root/'trial-controller').read(),first_journal)
            previous=f.admission.value['history'][0]['revision']
            prior,record=trial_case.read(f.origin,previous,lambda:f.clock[0])
            self.assertEqual(prior['candidate'],first_candidate)
            self.assertEqual(record['trial'],original)
            self.assertEqual(len(reader.visible),1)
            self.assertLessEqual(f.admission.value['certificate']['expires'],record['expires'])
            self.assertLessEqual(f.admission.value['certificate']['expires'],record['origin']['binding']['fence']['pending']['execution_deadline'])
            self.assertEqual(len(f.attempts),2)
            self.assertEqual(f.merges,[])
            self.assertEqual(second['deployment']['state'],'qualification')
            self.assertIsNone(second['deployment']['qualification'])
            self.assertEqual(len(f.runs),2)
            self.assertEqual(f.runs[103].run['id'],103)
            self.assertNotEqual(digest(f.case_token),digest(worker_token))
            self.assertEqual(f.native.provision.store(f.native.provision.root/'trial-read-staging').read()['value']['phase'],'revoked')
            trial_launch.revoke(f.native.provision,f.origin_factory,name='coding-update')
            self.assertIn(f.case_token,f.revoked)
        self.exercise(continuation=check)

    def test_progression_reauthenticates_prior_history_before_selecting_or_writing(self):
        def check(*args):
            import io,json,zipfile,trial_controller
            f=Sequential(self,args); f.prepared_host(); f.host(); f.run('broker'); f.finalize(); f.observe()
            artifact=next(a for a in f.remote.artifacts if a['name'].startswith('trial-case-terminal-'))
            with zipfile.ZipFile(io.BytesIO(f.remote.raw[artifact['id']])) as archive:
                original=json.loads(archive.read('trial-case-terminal.json'))
            owner=trial_controller.Native(f.preparer)
            for fault in ('request','certificate','baseline','terminal','interval'):
                value=copy.deepcopy(original)
                if fault=='request': value['request_digest']='0'*64
                if fault=='certificate': value['certificate_digest']='0'*64
                if fault=='baseline': value['before']=copy.deepcopy(f.admission.record['trial'])
                if fault=='terminal': value['after']['fence']['completed'][-1]['receipt_digest']='0'*64
                if fault=='interval': value['completed']+=1
                f.remote.replace(artifact['id'],value,'trial-case-terminal.json')
                with self.subTest(fault=fault),self.assertRaises(Refusal): owner._open('prompt','coding-update',f.source)
                self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-controller-coding-update').read())
            f.remote.replace(artifact['id'],original,'trial-case-terminal.json')
            entry=f.native.provision.store(f.native.provision.root/'trial-case-publication').read()['value']['revision_bound']
            ref=next(k for k,v in f.origin.api.refs.items() if v==entry)
            f.origin.api.refs[ref]=f.admission.value['workflow']['value']['revision_bound']
            with self.assertRaises(Refusal): owner._open('prompt','coding-update',f.source)
            self.assertIsNone(f.native.provision.store(f.native.provision.root/'trial-controller-coding-update').read())
            f.origin.api.refs[ref]=entry
        self.exercise(continuation=check)

    def test_second_case_refuses_old_same_scope_capability_and_substituted_native_owner(self):
        def check(*args):
            import trial_case,trial_controller,trial_launch
            f=Sequential(self,args); f.prepared_host(); f.host(); f.run('broker'); f.finalize(); f.observe()
            old=f.case_token
            f.second()
            with self.assertRaisesRegex(Refusal,'pending'): f.coordinate()
            f.close_handoff()
            count=len(f.remote.artifacts)
            f.revoked.remove(old)  # Transport acceptance cannot turn old capability into new authority.
            for token in (old,f.api.secrets['AGENTIC_TRIAL_ORIGIN_TOKEN']):
                with self.subTest(token=token),self.assertRaises(Refusal):
                    f.run('verify',change=lambda env:env.update(**{trial_case.CaseReadStaging.NAME:token}))
                self.assertEqual(len(f.remote.artifacts),count)
                env=f.job('trial case ready','trial_case_ready')
                env[trial_case.CaseReadStaging.NAME]=token
                with self.assertRaises(Refusal): trial_launch.consume(f.registry,
                    __import__('registry').Registry(f.origin_factory(token),f.origin.coordinates),env,f.ready_hint,lambda:f.clock[0])
            prior=f.native.provision.store(f.native.provision.root/'trial-controller')
            retained=prior.read(); value=copy.deepcopy(retained['value'])
            value['terminal']['binding']['fence']['completed'][-1]['receipt_digest']='0'*64
            prior.write(retained,value)
            with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','coding-update',f.source)
            self.assertEqual(len(f.attempts),1)
        self.exercise(continuation=check)

    def test_second_case_unknown_effect_or_expiry_never_replays_and_cleanup_remains_exact(self):
        for fault in ('unknown','expired'):
            def check(*args):
                import trial_launch
                f=Sequential(self,args); f.prepared_host(); f.host(); f.run('broker'); f.finalize(); f.observe()
                archives=copy.deepcopy(f.remote.raw)
                first=f.case_token
                f.second()
                with self.assertRaisesRegex(Refusal,'pending'): f.coordinate()
                f.close_handoff(); f.published()
                if fault=='unknown': f.fault='unknown'
                else: f.clock[0]+=501
                with self.assertRaises((OSError,Refusal)): f.host()
                count=len(f.attempts)
                with self.assertRaises(Refusal): f.host()
                self.assertEqual(len(f.attempts),count)
                self.assertEqual(count,2 if fault=='unknown' else 1)
                self.assertIsNotNone(f.registry.binding()['fence']['pending'])
                self.assertEqual(f.runs[101].raw,archives)
                f.clock[0]+=501
                trial_launch.revoke(f.native.provision,f.origin_factory,name='coding-update')
                self.assertTrue({first,f.case_token}<=f.revoked)
                self.assertEqual(f.merges,[])
            with self.subTest(fault=fault): self.exercise(continuation=check)

    def test_late_prior_case_pointer_movement_blocks_second_host_effect(self):
        def check(*args):
            f=Sequential(self,args); f.prepared_host(); f.host(); f.run('broker'); f.finalize(); f.observe()
            f.second()
            with self.assertRaisesRegex(Refusal,'pending'): f.coordinate()
            f.close_handoff(); f.published()
            revision=f.admission.value['history'][0]['revision']
            ref=next(k for k,v in f.origin.api.refs.items() if v==revision)
            tokens=f.tokens
            moved=[]
            def factory(token):
                scoped=tokens(token); get=scoped.get
                def read(path):
                    result=get(path)
                    if path.endswith('/pulls/'+str(f.admission.candidate['submitted']['pr'])):
                        f.origin.api.refs[ref]=f.admission.value['workflow']['value']['revision_bound']; moved.append(path)
                    return result
                scoped.get=read
                return scoped
            f.tokens=factory
            with self.assertRaises(Refusal): f.host()
            self.assertTrue(moved)
            self.assertEqual(len(f.attempts),1)
            self.assertFalse(any(a['name'].startswith('trial-host-intent-') for a in f.remote.artifacts))
            self.assertIsNotNone(f.registry.binding()['fence']['pending'])
            f.origin.api.refs[ref]=revision
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
