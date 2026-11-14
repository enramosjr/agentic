"""Fresh strict trial fixture; real critical execution, modeled remote transports."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import backend_test_support
import trial_broker_positive
import trial_controller
from authority_private import MAX_STATE, Store as ProtectedStore
from trial_runtime import archive,pinned_kit,verify
from trial_specimen import compose,RECIPES
from trusted_ci_policy import CHECKS,Refusal,digest,require
import test_authority_trial_broker_context_case as context_fixture
import test_authority_trial_setup as setup_fixture


def original_intent(image, factory):
    # Selected before any native consent, configuration or fence exists. The
    # strict run consumes elapsed time inside this one original finite budget.
    value=copy.deepcopy(factory())
    value['expires']=4600
    value['policy']['image']=image
    value['policy']['checks']=list(CHECKS)
    return value


class ElapsedClock:
    def __init__(self,value,start=None):
        self.value=value; self.start=time.monotonic() if start is None else start
    def __getitem__(self,index):
        require(index==0,'single strict clock required')
        return self.value+int(time.monotonic()-self.start)
    def __setitem__(self,index,value):
        current=self[index]
        self.value+=max(0,value-current)


class NativeJournal:
    """Modeled native storage; every read decodes an independent JSON snapshot."""
    def __init__(self): self.raw=None
    def read(self): return None if self.raw is None else json.loads(self.raw)
    def write(self,before,value):
        if before!=self.read(): raise Refusal('fixture CAS changed')
        document=dict(schema_version=1,generation=1 if before is None else before['generation']+1,value=value)
        raw=(json.dumps(document,sort_keys=True,allow_nan=False)+'\n').encode('utf-8')
        require(len(raw)<=MAX_STATE,'fixture private setup state exceeds limit')
        self.raw=raw
        return self.read()


class Harness(unittest.TestCase):
    prepared=context_fixture.NativeBrokerContext.prepared
    configured=context_fixture.NativeBrokerContext.configured
    exercise=context_fixture.NativeBrokerContext.exercise
    prepare=context_fixture.NativeBrokerContext.prepare

    def connected(self,*args,**kwargs):
        result=context_fixture.NativeBrokerContext.connected(self,*args,**kwargs)
        controller,c,reg,origin,clock,proof,*rest=result
        from test_authority_broker_evidence import stamp
        # The legacy fixture has fixed 1970 timestamps. Record actual modeled
        # job start/closure events when running its protocol on an advancing clock.
        post=controller.api.post
        def send(path,body):
            if not path.endswith('/dispatches'): return post(path,body)
            proof.job['started_at']=stamp(c.clock())
            try:
                return post(path,body)
            finally:
                if proof.job.get('status')=='completed' and hasattr(proof,'document'):
                    proof.job['completed_at']=stamp(c.clock())
                    proof.artifact['created_at']=stamp(c.clock())
                    proof.raw=proof.archive(proof.member)
                    import hashlib
                    proof.artifact['digest']='sha256:'+hashlib.sha256(proof.raw).hexdigest()
        controller.api.post=send
        return result

    def configure(self,root,pin,image,runtime):
        self.baseline,self.export=compose(pinned_kit(root,pin))
        # The existing trial setup installs this approved independent owner file.
        # Retain it in the original export so a positive merge preserves controls.
        self.export['.github/CODEOWNERS']=dict(content=b'* @maintainer\n',executable=False)
        self.image,self.runtime=image,runtime
        self.source_root,self.source_pin=root,pin

    def fixture(self):
        # Legacy native-host fixtures temporarily alias the shared Store name.
        # Positive job journals must retain the real implementation imported above.
        require(isinstance(ProtectedStore,type) and ProtectedStore.__module__=='authority_private' and
                trial_broker_positive.Store is ProtectedStore,'actual protected positive-role Store required')
        journal_patch=patch.object(setup_fixture,'Journal',NativeJournal)
        self.addCleanup(journal_patch.stop)
        journal_patch.start()
        initial=setup_fixture.TrialProvisionContracts.fixture
        initial_intent=setup_fixture.intent
        def intent():
            return original_intent(self.image,initial_intent)
        def seed(helper):
            result=initial(helper); c=result[0]
            # Preserve the original restricted native seed. Full KIT bytes enter
            # only through the genuine CLOSED worker export and eligibility.
            self.elapsed=ElapsedClock(result[-1][0])
            c.clock=lambda:self.elapsed[0]; c.session.clock=c.clock
            return (*result[:-1],self.elapsed)
        with patch.object(setup_fixture.TrialProvisionContracts,'fixture',seed),patch.object(setup_fixture,'intent',intent):
            return context_fixture.NativeBrokerContext.fixture(self)


class Strict(context_fixture.Context):
    def __init__(self,owner,args):
        super().__init__(owner,args)
        self.clock=owner.elapsed
        self.native.provision.clock=lambda:self.clock[0]
        self.remote.clock=self.clock
        self.temporary=tempfile.TemporaryDirectory(prefix='agentic-positive-jobs-')
        owner.addCleanup(self.temporary.cleanup)
        self.image,self.runtime=owner.image,owner.runtime
        source_get,source_pages=self.source.get,self.source.pages
        root='/repos/'+self.p['repository']
        def control_get(path):
            return self.api.get(path) if path in ('/users/maintainer',root+'/actions/permissions') else source_get(path)
        def control_pages(path,collection=None):
            return self.api.pages(path,collection) if path in (root+'/collaborators?affiliation=all',root+'/hooks') else source_pages(path,collection)
        self.source.get,self.source.pages=control_get,control_pages

    def archive(self,candidate):
        files={name:dict(content=self.source.blobs[blob],executable=mode=='100755')
               for name,(mode,blob) in self.source.trees[candidate['tree']].items()}
        return archive(files)

    def verify(self,source,d,s,job_id,guard,clock):
        return verify(source,d,s,job_id,guard,clock,self.runtime)

    def ready(self,*args,**kwargs):
        open_original=trial_controller.Native._open
        def opening(native,prompt,name,*pos,**kw):
            if name in RECIPES: kw['negative_approve']=digest
            return open_original(native,prompt,name,*pos,**kw)
        with patch.object(trial_controller.Native,'_open',opening):
            return super().ready(*args,**kwargs)

    def job(self,name,key):
        environment=super().job(name,key)
        if name=='finalize' or name.startswith('broker ('):
            environment['RUNNER_TEMP']=self.temporary.name
        return environment

    def upload(self,name,raw):
        identity=super().upload(name,raw)
        if self.admission.candidate['name']=='positive' and name.endswith('-control-ready'):
            self.run('controls')
            for purpose in ('admin','reader','issuer','coding','merge'): self.run('final-proof',purpose)
        return identity

    def run(self,role,purpose=None,change=None):
        if self.admission.candidate['name']=='positive' and role=='broker':
            self.job('broker ('+str(self.admission.request['snapshot']['pr'])+')','broker')
            from trial_broker_positive import bind_native_job
            bind_native_job(self.admission,'broker',self.temporary.name)
            supplied=change
            def environment(env):
                env['RUNNER_TEMP']=self.temporary.name
                if supplied: supplied(env)
            change=environment
        return super().run(role,purpose,change)

    def finalize(self):
        if self.admission.candidate['name']=='positive':
            self.job('finalize','finalize')
            from trial_broker_positive import bind_native_job
            bind_native_job(self.admission,'finalize',self.temporary.name)
        return super().finalize()

    def finish_positive(self):
        from trial_broker_positive import bind_native_job
        self.job('finalize','finalize')
        bind_native_job(self.admission,'finalize',self.temporary.name)
        with patch.object(self.admission,'guard',side_effect=AssertionError('native owner reached from fresh recovery job')):
            return super().finalize()

    def eligibility(self):
        from trial_eligibility import _produce
        closed=self.native._completion('prompt',self.source)
        self.synthetic(next(pr for pr in self.source.prs if pr['number']==closed['result']['submitted']['pr']))
        self.tar=archive(closed['files'])
        return _produce(self.native,'prompt',self.source,self.owner.source_root,self.owner.source_pin,self.runtime,digest)

    def observe(self,phase=None):
        result=super().observe(phase=phase)
        print('strict '+self.admission.candidate['name']+(' '+phase if phase else '')+' terminal observed',flush=True)
        return result

    def complete(self):
        original_origin=copy.deepcopy(self.origin.binding())
        original_expiry=self.registry.read()['expires']
        original_preview=copy.deepcopy(self.native.provision.preview)
        self.eligibility()
        print('strict CLOSED worker eligibility PASS; starting ordered case history',flush=True)
        previous_sleeper=self.__dict__.get('sleeper')
        had_sleeper='sleeper' in self.__dict__
        try:
            self.fifteenth()
            self.sleeper=lambda seconds:self.transition()
            require(self.run('broker')['refusal']=='configuration_changed','genuine fifteenth Session refusal required')
            self.finalize(); self.observe()
        finally:
            if had_sleeper: self.sleeper=previous_sleeper
            else: self.__dict__.pop('sleeper',None)
        print('strict ordered fifteen-case history complete; starting positive',flush=True)
        self.second('positive',137,'fresh-sixteenth-case')
        with self.owner.assertRaisesRegex(Refusal,'pending'): self.coordinate()
        self.close_handoff(); self.published()
        from trial_broker_positive import approve_native
        approve_native(self.admission,json.loads(self.api.variables['AGENTIC_FINALIZE_PIN']),digest)
        import merge_transport
        self.lose_merge_ack=self.owner.lost_merge_ack
        with patch.object(merge_transport,'isolated',side_effect=self.transport):
            result=self.run('broker')
        require(result['state']==('unknown' if self.lose_merge_ack else 'submitted') and len(self.merges)==1,
                'one positive merge request with the selected acknowledgement required')
        # New service producers must reconstruct entirely from published data.
        settled=self.finish_positive()
        observed=self.observe()
        require(observed['binding']==settled and settled['fence']['completed'][-1]['kind']=='merged','genuine positive terminal required')
        publication=self.native.provision.store(self.native.provision.root/'trial-case-publication-positive').read()
        history=self.admission.value['history']+[dict(revision=publication['value']['revision_bound'],terminal=observed['locator'])]
        from trial_case import baseline
        require(len(history)==16 and baseline(self.origin,self.registry,self.admission.record,history,lambda:self.clock[0])==settled,
                'fresh full sixteen-case reconstruction required')
        require(settled['deployment']['state']=='qualification' and settled['deployment']['qualification'] is None,
                'strict source fixture cannot activate or qualify')
        require(self.origin.binding()==original_origin and settled['deployment']['expires']==original_expiry and
                self.native.provision.preview==original_preview,
                'strict trial cannot renew original origin, configuration or provisioning lifetime')
        require(len({id(a) for a in self.fresh})==len(self.fresh) and len(self.fresh)>=15,
                'positive jobs must construct independent fresh admissions')
        for admission in self.fresh:
            require(not any(hasattr(admission,name) for name in ('native','provision','journal','session')),
                    'fresh producer retained native authority objects')
        actual=self.source.refs['main']; s=self.admission.request['snapshot']
        require(actual!=s['merge'] and [p['sha'] for p in self.source.commits[actual]['parents']]==[s['base'],s['head']] and
                self.source.commits[actual]['tree']['sha']==self.admission.candidate['submitted']['tree'],
                'actual positive merge must retain original parents and tested tree')
        self.readback_controls(observed,publication,settled)
        return self.source.refs['main']

    def readback_controls(self,observed,publication,settled):
        """Read-only negative controls against one genuinely completed trial."""
        from trial_case import read,case_baseline
        from trial_broker_positive import reconstruct,case_end
        import service
        case,record=read(self.origin,publication['value']['revision_bound'],lambda:self.clock[0])
        baseline=case_baseline(self.origin,self.registry,record,case,lambda:self.clock[0])
        document=observed['document']; producer=observed['producer']
        for fault in ('facts','tree','producer','receipt','canonical-envelope'):
            changed=copy.deepcopy(document)
            if fault=='facts': changed['positive']['facts']['merge_commit']='0'*40
            if fault=='tree': changed['positive']['commit']['tree']['sha']='0'*40
            if fault=='producer': changed['positive']['producer']['conclusion']='failure'
            if fault=='receipt': changed['after']['fence']['completed'][-1]['receipt_digest']='0'*64
            if fault=='canonical-envelope': changed['positive']['pr']['title']='tampered retained provider payload'
            with self.owner.assertRaises(Refusal):
                reconstruct(self.origin,self.registry,record,case,changed,baseline,lambda:self.clock[0],producer,self.source)
            if fault=='canonical-envelope':
                # Deliberately break only the envelope digest computation. All
                # provider identities and semantic merge checks still pass, so
                # this counterfactual proves the full payload is digest-bound.
                import trial_broker_positive
                real_digest=digest
                def stale_digest(value):
                    return real_digest(document['positive']) if value==changed['positive'] else real_digest(value)
                with patch.object(trial_broker_positive,'digest',side_effect=stale_digest):
                    require(reconstruct(self.origin,self.registry,record,case,changed,baseline,lambda:self.clock[0],producer,self.source)==settled,
                            'canonical envelope control did not isolate the digest check')
        # The next attempted original producer may not mint or dispatch again.
        with patch.object(service,'_source_token',side_effect=AssertionError('positive retry minted a token')):
            with self.owner.assertRaises(Refusal): self.run('broker')
        require(len(self.merges)==1 and self.registry.binding()==settled,'positive recovery replayed an effect')
        self.clock[0]=case_end(record,case,document['before'])+1
        def mutation(*args,**kwargs): raise AssertionError('expired positive recovery attempted a mutation')
        from contextlib import ExitStack
        import merge_transport
        with patch.object(service,'_source_token',side_effect=mutation),patch.object(service,'_admin_authority',side_effect=mutation),\
             patch.object(self.api,'post',side_effect=mutation),patch.object(self.origin.api,'post',side_effect=mutation),\
             patch.object(self.source,'post',side_effect=mutation),patch.object(service,'_upload_document',side_effect=mutation),\
             patch.object(merge_transport,'isolated',side_effect=mutation),ExitStack() as reads:
            for api in (self.api,self.origin.api,self.source):
                fetch=api.fetch
                def read(path,*args,_fetch=fetch,**kwargs):
                    method=kwargs.get('method',args[0] if args else 'GET')
                    if method!='GET': mutation()
                    return _fetch(path,*args,**kwargs)
                reads.enter_context(patch.object(api,'fetch',read))
            recovered=trial_controller.Native(self.preparer)._recover_terminal('prompt','positive',self.source)
            fetch=self.api.fetch
            def missing(path,*args,**kwargs):
                if path.endswith('/actions/artifacts/'+str(observed['locator']['artifact_id'])+'/zip'):
                    raise Refusal('positive terminal archive unavailable')
                return fetch(path,*args,**kwargs)
            with patch.object(self.api,'fetch',missing),self.owner.assertRaisesRegex(Refusal,'unavailable'):
                trial_controller.Native(self.preparer)._recover_terminal('prompt','positive',self.source)
        require(recovered==observed and self.registry.binding()==settled and len(self.merges)==1,
                'expired positive recovery must return only its exact retained completion')
        print('strict positive canonical-envelope tampering and expired read-only recovery controls PASS',flush=True)


def run(root,pin,image,runtime,diagnostic=False,lost_merge_ack=False):
    owner=Harness(); owner.configure(root,pin,image,runtime)
    owner.lost_merge_ack=lost_merge_ack
    try:
        def continuation(*args):
            if diagnostic:
                print('DIAGNOSTIC: original CLOSED worker protocol only; no eligibility or positive acceptance',flush=True)
                return None
            return Strict(owner,args).complete()
        owner.exercise(continuation=continuation,export_files=owner.export)
    finally: owner.doCleanups()
