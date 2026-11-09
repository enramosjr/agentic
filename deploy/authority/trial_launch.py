"""Held native READY -> one queued run -> exact pending case rendezvous.

The fresh read capability is staged before queueing. Only data and authenticated
CLOSED consumption proofs cross jobs; original native ownership stays here.
"""
import copy
import json
from urllib.parse import quote

import authority_release
import provenance
from dispatch_controls import locked_reference
from registry import Registry, TRIAL, trial_reference
from setup import TrialReadStaging
from trial_controller import Admission
from trial_handoff import read as read_origin
from trusted_ci_policy import digest, object_fields, positive, require, sha


def read(original, revision, clock):
    require(isinstance(original,Registry) and sha(revision),'exact READY publication required')
    value=original.blob(revision,TRIAL)[0]
    object_fields(value,('schema_version kind task_id origin_revision prompt candidate worker execution').split(),'READY case')
    require(type(value['schema_version']) is int and value['schema_version']==1 and
            value['kind']=='trial-case-ready' and value['execution'] is None,'READY is not pending authorization')
    record,before=read_origin(original,value['origin_revision'],clock())
    require(record['execution'] is not None and value['task_id']==record['task_id'] and
            digest(value['prompt'])==record['prompt_digest'],'READY original execution differs')
    commit=original.api.get(original.root+'/git/commits/'+revision)
    require(commit.get('sha')==revision and [v['sha'] for v in commit['parents']]==[before['branch_head']] and
            commit['message']=='AGENTIC conditional registry '+digest({TRIAL:value}) and
            original.ref(trial_reference(value))==revision,'READY conditional publication differs')
    def unrelated(entries): return {k:v for k,v in entries.items() if k!=TRIAL and not TRIAL.startswith(k+'/')}
    require(unrelated(original.tree(revision)[1])==unrelated(original.tree(before['branch_head'])[1]),
            'READY publication changed unrelated data')
    original.unchanged(before)
    require(original.ref(trial_reference(value))==revision and clock()<record['expires'],'READY moved or expired')
    return value,record


def authenticate(original, api, link, clock):
    """Authenticate the pre-queue capability and CLOSED READY consumer."""
    from trial_case import _closed
    object_fields(link,('revision','credential','handshake'),'READY consumption binding')
    value,record=read(original,link['revision'],clock)
    credential=link['credential']; locator=link['handshake']
    object_fields(credential,('revision repository_id permissions token_digest expires').split(),'READY read capability')
    require(credential['revision']==link['revision'] and credential['repository_id']==original.coordinates['repository_id'] and
            credential['permissions']==dict(contents='read') and clock()<credential['expires']<=record['expires'],
            'READY capability scope or lifetime differs')
    proof=provenance.authenticated_document(api,record['trial']['deployment'],locator,'trial-case-ready',record['task_id'],clock())
    _closed(proof,consumption(value,link['revision'],credential,locator),record['created'],credential['expires'])
    require(locator['attempt']==1,'READY rerun refused')
    return value,record


def consumption(value, revision, credential, locator):
    from trial_case import consumption as pending_consumption
    return dict(pending_consumption(value,revision,credential,locator),kind='trial-case-ready-consumption')


def consume(registry, original, environment, hint, clock):
    from trial_case import CaseReadStaging
    value,record=read(original,hint['revision'],clock)
    registry.unchanged(record['trial'])
    token=environment.get(CaseReadStaging.NAME)
    require(isinstance(token,str) and original.api.token==token and
            digest(token)!=record['execution']['credential']['token_digest'] and
            [v['id'] for v in original.api.pages('/installation/repositories','repositories')]==[original.coordinates['repository_id']],
            'fresh original-only READY read capability required')
    job=provenance.admit_job(registry.api,record['trial']['deployment'],environment,'trial case ready',clock())
    require(environment.get('GITHUB_RUN_ATTEMPT')=='1','READY rerun refused')
    original.unchanged(record['origin']['binding']); registry.unchanged(record['trial'])
    require(original.ref(trial_reference(value))==hint['revision'] and clock()<record['expires'],'READY changed during consumption')
    return consumption(value,hint['revision'],dict(token_digest=digest(token),repository_id=original.coordinates['repository_id'],
        permissions=dict(contents='read')),dict(run_id=int(environment['GITHUB_RUN_ID']),attempt=1,job_id=job['id']))


class Staging(TrialReadStaging):
    from trial_case import CaseReadStaging
    NAME, JOURNAL=CaseReadStaging.NAME,CaseReadStaging.JOURNAL

    def __init__(self, native, reader, token_factory):
        self.native=native
        a=native.admission
        super().__init__(a.native.provision,a.registry,native.document['value']['revision'],reader,token_factory)

    def run(self):
        authority_release.authorize('bootstrap')
        a,c=self.native.admission,self.provision
        require(a.value['phase']=='ready','READY staging must precede pending case preparation')
        value,record=read(c.session.registry,self.revision,c.clock)
        require(value==self.native.document['value']['ready'],'retained READY differs')
        journal=c.store(c.root/self.JOURNAL)
        def check(document):
            self.native.guard()
            require(journal.read()==document and c.session.registry.ref(trial_reference(value))==self.revision,
                    'READY staging ownership changed')
        return self._stage(c,record,record['origin']['binding'],journal,check)


def revoke(provision, token_factory):
    """Reconstruct exact-token cleanup without expired native admission reads."""
    authority_release.authorize('bootstrap')
    from trial_setup import Provision
    require(type(provision) is Provision,'actual native case provisioning owner required for cleanup')
    document=provision.store(provision.root/'trial-case-launch').read()
    require(document is not None and sha(document['value']['revision']),'retained READY cleanup identity required')
    # Reuse the same credential engine with its fixed case purpose. This facade
    # can only revoke the exact retained token; it cannot mint, stage or dispatch.
    staging=TrialReadStaging(provision,None,document['value']['revision'],None,token_factory)
    staging.NAME,staging.JOURNAL=Staging.NAME,Staging.JOURNAL
    return staging.revoke()


class Native:
    def __init__(self, admission, reader=None, token_factory=None):
        self.admission,self.reader,self.token_factory=admission,reader,token_factory

    def run(self,prompt,admin=None,token_factory=None):
        authority_release.authorize('qualify-live')
        return self._run(prompt,admin,token_factory)

    def guard(self):
        self.admission.guard()
        require(self.journal.read()==self.document,'native case launch ownership changed')
        if self.document is not None and self.document['value']['credential'] is not None:
            credential=self.document['value']['credential']
            c=self.admission.native.provision
            staged=c.store(c.root/Staging.JOURNAL).read()
            require(staged is not None and staged['value']['phase'] in ('secret-started','staged') and
                    staged['value']['revision']==credential['revision'] and
                    digest(staged['value']['credential']['token'])==credential['token_digest'] and
                    self.admission.clock()<credential['expires'],'retained pre-queue case delegation changed or expired')

    def save(self,state):
        self.guard()
        self.document=self.journal.write(self.document,state)

    def _run(self,prompt,admin,token_factory):
        import service
        from trial_case import Publication
        a=self.admission
        require(type(a) is Admission,'actual native case launch owner required')
        a.guard()
        c=a.native.provision; original=c.session.registry
        p=a.record['trial']['deployment']['policy']
        require(p['workflow']=='.github/workflows/authority-v2.yml','case launch requires the fixed authority workflow')
        self.journal=c.store(c.root/'trial-case-launch'); self.document=self.journal.read()
        ready=dict(schema_version=1,kind='trial-case-ready',task_id=a.record['task_id'],
            origin_revision=a.value['workflow']['value']['revision_bound'],prompt=prompt,
            candidate=copy.deepcopy(a.candidate),worker=copy.deepcopy(a.value['worker']),execution=None)
        require(digest(prompt)==a.record['prompt_digest'],'exact approved case prompt required')
        if self.document is None:
            require(a.value['phase']=='ready','READY intent must precede case fencing')
            self.save(dict(ready=ready,phase='publication-started',revision=None,credential=None,baseline=None,link=None))
            original._replace(a.record['origin']['binding'],{TRIAL:ready},before_effect=self.guard,trial_branch=trial_reference(ready))
        state=copy.deepcopy(self.document['value'])
        object_fields(state,('ready phase revision credential baseline link').split(),'native case launch')
        require(state['ready']==ready and state['phase'] in ('publication-started','published','prepared','dispatch-started','consumed'),
                'resume only retained exact case launch')
        revision=original.ref(trial_reference(ready))
        require(read(original,revision,a.clock)[0]==ready and state['revision'] in (None,revision),'READY publication remains pending')
        if state['phase']=='publication-started':
            state.update(phase='published',revision=revision); self.save(state)
        self.staging=Staging(self,self.reader,self.token_factory)
        workflow='/repos/'+p['authority_repository']+'/actions/workflows/'+quote(p['workflow'],safe='')
        def runs():
            self.guard()
            values=a.registry.api.pages(workflow+'/runs','workflow_runs')
            require(isinstance(values,list) and len(values)<=10000 and all(isinstance(v,dict) and positive(v.get('id')) for v in values) and
                    len({v['id'] for v in values})==len(values),'bounded unique case run inventory required')
            self.guard()
            return values
        if state['phase']=='published':
            credential=self.staging.run()
            state.update(phase='prepared',credential=credential,baseline=sorted(v['id'] for v in runs())); self.save(state)
        require(state['credential'] is not None and a.clock()<state['credential']['expires'],'case launch delegation expired')
        if state['phase']=='prepared':
            branch=locked_reference(a.registry.api,p,self.guard)
            state['phase']='dispatch-started'; self.save(state)
            self.guard()
            a.registry.api.post(workflow+'/dispatches',dict(ref=branch,inputs=dict(mode='case',
                handoff=json.dumps(dict(origin=original.coordinates,revision=revision),sort_keys=True,separators=(',',':')))))
        if state['phase']=='dispatch-started':
            candidates=[v for v in runs() if v['id'] not in state['baseline'] and v.get('head_sha')==p['workflow_sha'] and
                v.get('repository',{}).get('id')==p['authority_repository_id'] and v.get('event')=='workflow_dispatch']
            require(len(candidates)==1 and candidates[0].get('run_attempt')==1,'case dispatch remains pending or ambiguous; never redispatch')
            locator=self.locator(candidates[0]['id'],'trial case ready','trial-case-ready')
            link=dict(revision=revision,credential=state['credential'],handshake=locator)
            require(authenticate(original,a.registry.api,link,a.clock)[0]==ready,'case READY consumer differs')
            state.update(phase='consumed',link=link); self.save(state)
        authenticate(original,a.registry.api,state['link'],a.clock)
        run_id=state['link']['handshake']['run_id']
        if a.value['phase']=='ready':
            environment=dict(GITHUB_REPOSITORY_ID=str(p['authority_repository_id']),GITHUB_SHA=p['workflow_sha'],
                GITHUB_RUN_ID=str(run_id),GITHUB_RUN_ATTEMPT='1',GITHUB_JOB='prepare')
            service._prepare_trial(a,environment,admin,token_factory,launch=self)
        require(a.request['snapshot']['run_id']==run_id and a.request['snapshot']['run_attempt']==1,'case fence belongs to another run')
        publication=Publication(a)
        hint=publication.publish(prompt,launch=state['link'])
        credential=dict(state['credential'],expires=min(state['credential']['expires'],a.value['certificate']['expires']))
        location=self.locator(run_id,'trial case handoff','trial-case-handoff')
        return publication.bind(credential,location)

    def locator(self,run_id,name,prefix):
        a=self.admission
        self.guard()
        root=a.registry.root+'/actions/runs/'+str(run_id)
        jobs=a.registry.api.pages(root+'/attempts/1/jobs','jobs')
        artifacts=a.registry.api.pages(root+'/artifacts','artifacts')
        require(isinstance(jobs,list) and isinstance(artifacts,list) and len(jobs)<=10000 and len(artifacts)<=10000,
                'bounded case consumer inventory required')
        jobs=[v for v in jobs if v.get('name')==name]
        artifacts=[v for v in artifacts if v.get('name')==prefix+'-'+a.record['task_id']+'-1']
        require(len(jobs)==len(artifacts)==1,'closed case consumer remains pending; never redispatch')
        self.guard()
        return dict(run_id=run_id,attempt=1,job_id=jobs[0]['id'],artifact_id=artifacts[0]['id'])
