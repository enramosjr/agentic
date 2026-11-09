"""Actual native trial into shared controllers; all remote/OCI effects are fixtures."""
import backend_test_support
import copy
import hashlib
import io
import json
import sys
import tarfile
import unittest
import zipfile
from unittest.mock import patch

import service
import merge_transport
from trusted_ci_policy import Refusal, digest
import test_authority_trial_candidates as candidates_fixture
from test_authority_producer_composition import Composition
from test_authority_broker_evidence import AuthorityAPI, stamp


class Connected:
    verify = Composition.verify

    def __init__(self, owner, args):
        self.owner = owner
        self.native, self.source, self.origin, self.apps, tokens, self.admin, self.old_artifacts = args
        self.preparer = owner.prepare(*args)
        self.clock, self.events, self.merges = [self.native.provision.clock()], [], []
        self.native.provision.clock = lambda:self.clock[0]
        self.registry = self.native.registry
        self.d = self.registry.read()
        self.p = self.d['policy']
        self.api = self.registry.api
        self.remote = AuthorityAPI(self.d, self.clock)
        def replace(identity,value,member):
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as archive: archive.writestr(zipfile.ZipInfo(member),json.dumps(value))
            raw=stream.getvalue(); self.remote.raw[identity]=raw
            next(a for a in self.remote.artifacts if a['id']==identity)['digest']='sha256:'+hashlib.sha256(raw).hexdigest()
        self.remote.replace=replace
        self.remote.run.update(id=101, repository={'id':self.p['authority_repository_id']}, event='workflow_dispatch')
        self.final_pin=json.loads(self.api.variables['AGENTIC_FINALIZE_PIN'])
        self.final_run=dict(self.remote.run,id=102,path=self.final_pin['workflow'],head_sha=self.final_pin['workflow_sha'],workflow_id=34)
        self.final_jobs=[]
        get, pages, fetch = self.api.get, self.api.pages, self.api.fetch
        def authority_get(path):
            if '/actions/runs/102' in path: return copy.deepcopy(self.final_run)
            if '/actions/runs/101' in path: return copy.deepcopy(self.remote.run)
            if path.endswith('/actions/workflows/34'): return dict(id=34,path=self.final_pin['workflow'])
            if path.endswith('/actions/workflows/33'): return dict(id=33, path=self.p['workflow'])
            return get(path)
        self.api.get = authority_get
        self.api.pages = lambda path, collection=None: copy.deepcopy(self.final_jobs) if '/runs/102/' in path and collection=='jobs' else copy.deepcopy(self.remote.jobs if collection == 'jobs' else self.remote.artifacts) if '/runs/101/' in path else pages(path,collection)
        self.api.fetch = lambda path, **kw:self.remote.fetch(path,**kw) if '/actions/artifacts/' in path and int(path.split('/')[-2]) in self.remote.raw else fetch(path,**kw)
        source_get, source_pages, source_post, source_fetch = self.source.get, self.source.pages, self.source.post, self.source.fetch
        self.checks, self.reviews = [], []
        directories = {}
        def read(path):
            if path in directories: return copy.deepcopy(directories[path])
            if '/git/trees/' in path and '?' not in path:
                value = source_get(path)
                nested, entries = {}, []
                for entry in value['tree']:
                    if '/' in entry['path']:
                        folder, rest = entry['path'].split('/',1)
                        nested.setdefault(folder,[]).append(dict(entry,path=rest))
                    else: entries.append(entry)
                for folder, children in nested.items():
                    key=digest(children)[:40]
                    directories['/repos/'+self.p['repository']+'/git/trees/'+key]=dict(sha=key,truncated=False,tree=children)
                    entries.append(dict(path=folder,mode='040000',type='tree',sha=key))
                return dict(value,tree=entries)
            if '/branches/' in path: return dict(commit=dict(sha=self.source.refs['main']))
            if '/git/ref/pull/' in path:
                pr = next(v for v in self.source.prs if str(v['number']) == path.split('/pull/')[1].split('/')[0])
                return dict(object=dict(sha=self.synthetic(pr)))
            return source_get(path)
        self.source.get = read
        self.source.pages = lambda path, collection=None: copy.deepcopy(self.reviews) if path.endswith('/reviews') else copy.deepcopy(self.checks) if '/check-runs' in path else source_pages(path,collection)
        def write(path, body):
            if path.endswith('/check-runs'):
                value = dict(body,id=300,app=dict(id=self.d['apps']['issuer']))
                self.checks.append(value); self.events.append('published'); return value
            return source_post(path,body)
        self.source.post = write
        self.source.fetch = lambda path, **kw:self.tar if '/tarball/' in path else source_fetch(path,**kw)
        def token_factory(token):
            scoped = tokens(token)
            original_get, original_pages, original_post, original_fetch = scoped.get, scoped.pages, scoped.post, scoped.fetch
            class Scoped:
                def __init__(self): self.token = token
                def get(self,path):
                    if path.startswith('/repos/' + self.p['authority_repository']): return self.api.get(path)
                    if '/pulls/' in path or '/git/' in path or '/branches/' in path: return read(path)
                    return original_get(path)
                def pages(self,path,collection=None):
                    if path.endswith('/reviews') or '/check-runs' in path: return self.source.pages(path,collection)
                    return original_pages(path,collection)
                def post(self,path,body):
                    if '/git/' in path and self.p['authority_repository'] in path: return self.api.post(path,body)
                    if path.endswith('/check-runs'): return write(path,body)
                    return original_post(path,body)
                def fetch(self,path,**kw):
                    if self.p['authority_repository'] in path: return self.api.fetch(path,**kw)
                    if '/tarball/' in path: return self.tar
                    return original_fetch(path,**kw)
            # These are fixture transport closures, never credentials in a worker.
            Scoped.p, Scoped.api, Scoped.source, Scoped.tar = self.p, self.api, self.source, getattr(self,'tar',b'')
            return Scoped()
        self.tokens = token_factory

    def synthetic(self, pr):
        base, head = self.source.refs['main'], pr['head']['sha']
        pr['base']['sha'] = base
        tree = self.source.commits[head]['tree']['sha']
        key = digest(dict(base=base,head=head,tree=tree))[:40]
        self.source.commits[key] = dict(sha=key,tree=dict(sha=tree),parents=[dict(sha=base),dict(sha=head)])
        return key

    def job(self, name, key):
        if key=='finalize':
            self.final_jobs=[dict(id=6000,run_id=102,head_sha=self.final_pin['workflow_sha'],name='finalize',
                status='in_progress',conclusion=None,started_at=stamp(self.clock[0]),completed_at=None)]
            return dict(GITHUB_REPOSITORY_ID=str(self.final_pin['authority_repository_id']),GITHUB_SHA=self.final_pin['workflow_sha'],
                GITHUB_RUN_ID='102',GITHUB_RUN_ATTEMPT='1',GITHUB_JOB='finalize',AGENTIC_RECOVERY_PIN=self.api.variables['AGENTIC_FINALIZE_PIN'])
        if not any(j['name']==name for j in self.remote.jobs):
            identity = 3000 + len(self.remote.jobs)
            self.remote.jobs.append(dict(id=identity,run_id=101,head_sha=self.p['workflow_sha'],name=name,
                status='in_progress',conclusion=None,started_at=stamp(self.clock[0]),completed_at=None))
        environment = dict(GITHUB_REPOSITORY_ID=str(self.p['authority_repository_id']),GITHUB_SHA=self.p['workflow_sha'],
            GITHUB_RUN_ID='101',GITHUB_RUN_ATTEMPT='1',GITHUB_JOB=key)
        return environment

    def upload(self,name,raw):
        from artifact_uploader import document_member
        if any(a['name'] == name for a in self.remote.artifacts): raise Refusal('fixture artifact conflict')
        identity = 5000 + len(self.remote.artifacts)
        self.remote.artifacts.append(dict(id=identity,name=name,expired=False,created_at=stamp(self.clock[0]),
            workflow_run=dict(id=101,repository_id=self.p['authority_repository_id'],head_repository_id=self.p['authority_repository_id'],head_sha=self.p['workflow_sha'])))
        self.remote.replace(identity,json.loads(raw),document_member(name))
        if name.endswith('-control-ready'):
            self.run('controls')
            for purpose in ('admin','reader','issuer','coding','merge'): self.run('final-proof',purpose)
            if getattr(self,'after_final',None) is not None: self.after_final()
        return identity

    def run(self,role,purpose=None):
        key = purpose+'_'+role.replace('-','_') if purpose else role.replace('-','_')
        name = ('publication controls' if role == 'publication-controls' else 'final proof' if role == 'final-proof' else role)
        name += ' ('+(purpose or str(self.admission.candidate['submitted']['pr']))+')'
        env = self.job(name,key)
        purposes = [purpose] if purpose else ['merge','reader'] if role == 'broker' else ['admin'] if role in ('controls','publication-controls') else ['issuer'] if role == 'publish' else ['reader']
        env.update({'AGENTIC_'+p.upper()+'_PRIVATE_KEY':self.api.secrets['AGENTIC_'+p.upper()+'_PRIVATE_KEY'] for p in purposes})
        try:
            return service._trial_producer(self.admission,env,self.admission.request,'fixture-node',role,
                clock=lambda:self.clock[0],app_factory=self.apps,token_factory=self.tokens,
                uploader_factory=lambda *a:self.upload,verifier=self.verify,sleeper=lambda s:None)
        finally:
            next(j for j in self.remote.jobs if j['name']==name).update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))

    def prepare(self, before_fence=None):
        import trial_controller
        self.admission = trial_controller.Native(self.preparer)._open('prompt','positive',self.source)
        self.binding = self.registry.binding()
        candidate = self.admission.candidate['submitted']
        pr = next(v for v in self.source.prs if v['number'] == candidate['pr'])
        pr['base']['sha'] = self.source.refs['main']
        self.synthetic(pr)
        self.reviews = [dict(id=900,user=dict(id=self.p['reviewers'][0],type='User'),state='APPROVED',commit_id=candidate['head'])]
        self.tar = self.archive(candidate)
        env = self.job('prepare','prepare')
        if before_fence is not None: before_fence()
        service._prepare_trial(self.admission,env,self.apps(self.d['apps']['admin'],self.api.secrets['AGENTIC_ADMIN_PRIVATE_KEY']),self.tokens)
        self.remote.jobs[-1].update(status='completed',conclusion='success',completed_at=stamp(self.clock[0]))

    def archive(self,candidate):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as archive:
            for path,(mode,blob) in self.source.trees[candidate['tree']].items():
                raw = self.source.blobs[blob]
                member = tarfile.TarInfo('candidate/'+path); member.size=len(raw)
                archive.addfile(member,io.BytesIO(raw))
        return stream.getvalue()

    def published(self):
        self.run('verify')
        for purpose in ('admin','reader','issuer','coding','merge'): self.run('proof',purpose)
        self.run('publication-controls'); self.run('publish')
        self.job('controls ('+str(self.admission.candidate['submitted']['pr'])+')','controls')
        for purpose in ('admin','reader','issuer','coding','merge'): self.job('final proof ('+purpose+')',purpose+'_final_proof')

    def transport(self, document, seconds):
        outer=self
        class Opener:
            def open(self,request,timeout):
                body=json.loads(request.data)
                outer.owner.assertEqual((request.method,body,timeout),('PUT',dict(sha=outer.admission.candidate['submitted']['head'],merge_method='merge'),30))
                outer.merges.append((request.method,body,timeout))
                candidate=outer.admission.candidate['submitted']; base=outer.admission.request['snapshot']['base']
                actual=outer.source.post('/repos/'+outer.p['repository']+'/git/commits',dict(message='actual fixture merge',
                    tree=candidate['tree'],parents=[base,candidate['head']],author=dict(name='fixture',email='fixture@example.test',date=stamp(outer.clock[0])),committer=dict(name='fixture',email='fixture@example.test',date=stamp(outer.clock[0]))))['sha']
                pr=next(v for v in outer.source.prs if v['number']==candidate['pr'])
                pr.update(state='closed',merged=True,merge_commit_sha=actual); outer.source.refs['main']=actual
                if getattr(outer,'lose_merge_ack',False): raise OSError('fixture lost actual merge acknowledgement')
                response=io.BytesIO(json.dumps(dict(merged=True,sha=actual)).encode()); response.status=200
                return response
        return merge_transport.request_once(document,opener=Opener())


@unittest.skipIf(candidates_fixture.service_fixture.hosted.workflow.staging.handoff.preparation.jwt is None, 'optional cryptography required')
class TrialController(unittest.TestCase):
    fixture = candidates_fixture.Candidates.fixture
    prepared = candidates_fixture.Candidates.prepared
    connected = candidates_fixture.Candidates.connected
    configured = candidates_fixture.Candidates.configured
    exercise = candidates_fixture.Candidates.exercise
    prepare = candidates_fixture.Candidates.prepare
    def test_native_trial_consumes_shared_graph_and_recovers_actual_merge(self):
        def check(*args):
            f = Connected(self,args)
            origin = f.origin.binding()
            f.prepare()
            before = f.registry.binding()
            self.assertEqual(before['deployment']['state'],'qualification')
            self.assertIsNone(before['deployment']['qualification'])
            f.published()
            with patch.object(merge_transport,'isolated',side_effect=f.transport): outcome=f.run('broker')
            self.assertEqual(outcome['state'],'submitted')
            self.assertEqual(len(f.merges),1)
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
            broker.update(status='completed',conclusion='success',completed_at=stamp(f.clock[0]))
            env=f.job('finalize','finalize')
            result=f.admission.finalize(env,broker['id'])
            self.assertIsNone(result['fence']['pending'])
            self.assertEqual(result['fence']['completed'][-1]['kind'],'merged')
            self.assertEqual(result['deployment'],before['deployment'])
            self.assertEqual(f.origin.binding(),origin)
            with self.assertRaises(Refusal): f.run('broker')
            actual=f.source.refs['main']
            self.assertEqual(f.source.commits[actual]['tree']['sha'],f.admission.candidate['submitted']['tree'])
            self.assertNotEqual(actual,f.admission.request['snapshot']['merge'])
            return actual
        self.exercise(continuation=check)

    def test_lost_merge_ack_recovers_in_fresh_native_instance_without_dispatch_replay(self):
        def check(*args):
            import trial_controller
            f=Connected(self,args); f.prepare(); f.published(); f.lose_merge_ack=True
            with patch.object(merge_transport,'isolated',side_effect=f.transport): result=f.run('broker')
            self.assertEqual(result['state'],'unknown'); self.assertEqual(len(f.merges),1)
            f.admission=trial_controller.Native(f.preparer)._open('prompt','positive',f.source)
            with self.assertRaises(Refusal): f.run('broker')
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
            after=f.admission.finalize(f.job('finalize','finalize'),broker['id'])
            self.assertEqual(after['fence']['completed'][-1]['kind'],'merged')
            self.assertIsNone(after['fence']['pending']); self.assertEqual(len(f.merges),1)
            return f.source.refs['main']
        self.exercise(continuation=check)

    def test_withdrawn_review_records_genuine_no_dispatch_and_finalizes(self):
        def check(*args):
            f=Connected(self,args); f.prepare(); f.published(); f.reviews=[]
            with patch.object(merge_transport,'isolated',side_effect=AssertionError('must not dispatch')),self.assertRaises(Refusal): f.run('broker')
            self.assertEqual(f.merges,[])
            names=[a['name'] for a in f.remote.artifacts]
            self.assertTrue(any(n.endswith('-not-submitted') for n in names))
            self.assertFalse(any(n.endswith('-dispatch') for n in names))
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
            environment=f.job('finalize','finalize')
            pending=f.registry.binding()
            for fault in ('missing','wrong-runtime'):
                bad=copy.deepcopy(environment)
                if fault=='missing': bad.pop('AGENTIC_RECOVERY_PIN')
                else:
                    pin=json.loads(bad['AGENTIC_RECOVERY_PIN']); pin['workflow_sha']='0'*40
                    bad['AGENTIC_RECOVERY_PIN']=json.dumps(pin)
                with self.assertRaises(Refusal): f.admission.finalize(bad,broker['id'])
                self.assertEqual(f.registry.binding(),pending)
            after=f.admission.finalize(environment,broker['id'])
            self.assertIsNone(after['fence']['pending'])
            self.assertEqual(after['fence']['completed'][-1]['kind'],'not-submitted')
        self.exercise(continuation=check)

    def test_exact_lost_fence_ack_is_read_only_recovery_and_absence_never_replays(self):
        for acknowledged in (True,False):
            def check(*args):
                import trial_controller
                f=Connected(self,args)
                effects=[]; fetch=f.api.fetch
                def lost(path,method='GET',**kw):
                    if method=='PATCH' and path.endswith('/agentic-registry'):
                        effects.append(path)
                        if acknowledged: fetch(path,method=method,**kw)
                        raise OSError('fixture lost fence acknowledgement')
                    return fetch(path,method=method,**kw)
                with self.assertRaises(OSError): f.prepare(lambda:setattr(f.api,'fetch',lost))
                if acknowledged:
                    resumed=trial_controller.Native(f.preparer)._open('prompt','positive',f.source)
                    self.assertEqual(resumed.value['phase'],'bound')
                    with self.assertRaises(Refusal): service._prepare_trial(resumed,f.job('prepare','prepare'),None)
                else:
                    with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','positive',f.source)
                self.assertEqual(len(effects),1)
            with self.subTest(committed=acknowledged): self.exercise(continuation=check)

    def test_production_rejects_trial_and_plain_json_never_admits(self):
        def check(*args):
            import broker_evidence, broker_proofs, control_rendezvous, merge_window, qualification_record, trial_controller
            f=Connected(self,args); f.prepare()
            b,s=f.registry.binding(),f.admission.request['snapshot']
            with self.assertRaises(Refusal): broker_proofs.current_operation(b,s)
            with self.assertRaises(Refusal): control_rendezvous.ready(b,99,'1'*32,f.clock[0])
            with self.assertRaises(Refusal): broker_evidence.preload(f.registry,f.source,f.api,f.admission.record['pair']['identities'],99,{},lambda:f.clock[0])
            with self.assertRaises(Refusal): service._trial_producer(copy.deepcopy(f.admission.value['certificate']),{}, {},None,'verify')
            with self.assertRaises(Refusal): trial_controller.Admission(None,None)
            with patch.object(service,'context',return_value=(f.api,f.registry,b,f.admission.record['pair']['identities'])):
                with self.assertRaises(Refusal): service._prepare({},dict(pr=s['pr']),clock=lambda:f.clock[0])
            f.published()
            with patch.object(merge_transport,'isolated',side_effect=f.transport): f.run('broker')
            broker=next(j for j in f.remote.jobs if j['name'].startswith('broker ('))
            from merge_receipts import ActionsReceipts
            receipts=ActionsReceipts._create(f.api,f.registry.binding,broker['id'],lambda:f.clock[0],recovery=True,admission=f.admission)
            gate=receipts.authenticate(receipts.find_for_recovery('dispatch'))['gate']
            with self.assertRaises(Refusal): merge_window.validate(gate,b,f.clock[0])
            with self.assertRaises(Refusal): qualification_record.validate(f.admission.value['certificate'],b,f.admission.record['pair']['identities'],{},'0'*64,f.clock[0])
            return f.source.refs['main']
        self.exercise(continuation=check)

    def test_retained_request_substitution_and_late_stale_controls_cannot_dispatch(self):
        for fault in ('retained-request','stale-controls','origin-moved'):
            def check(*args):
                import trial_controller
                f=Connected(self,args); f.prepare()
                if fault=='retained-request':
                    saved=f.admission.journal.read(); changed=copy.deepcopy(saved['value'])
                    changed['request']['snapshot']['run_id']=102
                    f.admission.journal.write(saved,changed)
                    with self.assertRaises(Refusal): trial_controller.Native(f.preparer)._open('prompt','positive',f.source)
                else:
                    f.published()
                    def late():
                        if fault=='stale-controls': f.clock[0]+=31
                        else: f.origin.api.refs['main']='9'*40
                    f.after_final=late
                    with patch.object(merge_transport,'isolated',side_effect=AssertionError('must not dispatch')),self.assertRaises(Refusal): f.run('broker')
                self.assertEqual(f.merges,[])
            with self.subTest(fault=fault): self.exercise(continuation=check)

    def test_final_native_authentication_latency_cannot_use_a_stale_dispatch_clock(self):
        def check(*args):
            f=Connected(self,args); f.prepare(); f.published()
            guard=f.admission.guard; validations=[0]
            def late(*a,**kw):
                result=guard(*a,**kw)
                frame=sys._getframe(1)
                if frame.f_code.co_name=='_validate' and frame.f_back.f_code.co_name=='_dispatch':
                    validations[0]+=1
                    if validations[0]==2: f.clock[0]+=31
                return result
            f.admission.guard=late
            with patch.object(merge_transport,'isolated',side_effect=f.transport): result=f.run('broker')
            self.assertEqual(validations[0],2,'final authentication latency was not injected')
            self.assertEqual(len(f.merges),0)
            self.assertEqual(result['state'],'unknown')
        self.exercise(continuation=check)


class Holds(unittest.TestCase):
    def test_hold_and_authentication_precede_native_access(self):
        import authority_release, trial_controller
        with self.assertRaises(authority_release.Held): trial_controller.Native(None).open('prompt','positive')
        with self.assertRaises(Refusal): service._prepare_trial({}, {}, None)
