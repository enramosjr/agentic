"""Held native broker negatives over the shared Session; never dispatch a merge."""
import copy

import broker_proofs
import provenance
from broker_refusal import BrokerRefusal
from merge_receipts import ActionsReceipts
from trusted_ci_policy import digest, object_fields, positive, require


def selected(admission):
    from trial_controller import authenticated
    authenticated(admission)
    return admission.candidate['name'] in ('expired-proof','authority-outage')


def _identity(a):
    require(selected(a),'exact native broker negative required')
    return dict(schema_version=1,kind='trial-broker-denial',case=a.candidate['name'],
        request_digest=digest(a.request),certificate_digest=digest(a.value['certificate']))


def guard(a):
    """Observe the candidate after blocking registry/history authentication."""
    from authority_github import Readers,current_snapshot
    a.guard()
    s=a.request['snapshot']; d=a.binding['deployment']
    current=current_snapshot(Readers(a.source,a.registry.api,d),d,s['pr'],s['run_id'],s['run_attempt'])
    require(current==s,
            'broker negative candidate changed during admission readback')
    a.local_guard()
    return current


def _prerequisites(a, authority):
    """Current success and human approval remain prerequisites of this negative."""
    import service
    from authority_github import Readers,current_snapshot
    from controls import observe
    from qualification_cases import HostCases
    from trusted_ci_github import independent_approval
    b,s=a.binding,a.request['snapshot']; d=b['deployment']
    readers=Readers(a.source,authority,d)
    require(current_snapshot(readers,d,s['pr'],s['run_id'],s['run_attempt'])==s,'broker negative candidate changed')
    location=service._locator(authority,d,s['run_id'],s['run_attempt'],'evidence',s['pr'])
    proof=provenance.authenticated_document(authority,d,location,'evidence',s['pr'],a.clock())
    task=a.task(b,s,a.request['task']['locator'],a.request['task']['task_id'])
    coordinates=dict(configuration_revision=b['configuration_revision'],operation=b['fence']['pending'],sequence=b['fence']['sequence'],
        issuer_installation_id=a.record['pair']['identities']['apps']['issuer']['installation_id'],
        evidence_job_id=proof['job_id'],evidence_digest=digest(proof['document']),task_digest=task['task_digest'])
    probe=HostCases(a.registry,a.source,authority,a.record['pair']['identities'],None,None,None,a.clock)
    probe._success(s,location,coordinates,d)
    pr=a.source.get('/repos/'+d['policy']['repository']+'/pulls/'+str(s['pr']))
    require(pr.get('mergeable') is True,'unresolved broker candidate')
    independent_approval(a.source,d['policy'],pr,human=True)
    facts=observe(readers,d)
    a.qualification(b,facts['controls_digest'])
    from broker_evidence import _additional_checks
    _additional_checks(a.source,d,s,facts['required_checks'])
    guard(a)


def _proofs(a, authority, locators, now):
    return broker_proofs._read(authority,a.binding,a.record['pair']['identities'],a.request['snapshot'],locators,now,admission=a)


def _publication(a, authority, now):
    import service
    s=a.request['snapshot']; d=a.binding['deployment']
    location=service._locator(authority,d,s['run_id'],s['run_attempt'],'publication-controls',s['pr'])
    proof=provenance.authenticated_document(authority,d,location,'publication-controls',s['pr'],now)
    service._bound_validate_publication_observation(proof['document'],a.binding,s,proof,now,a)
    return digest(proof)


def _expiry(a, authority, locators, now):
    # Reuse the existing semantic validator, including original capability validity.
    try:
        _proofs(a,authority,locators,now)
    except BrokerRefusal as error:
        require(error.code=='proof_expired','wrong native broker refusal')
        return dict(code=error.code,observation=error.observation)
    require(False,'retained proof has not expired')


def _outage(a, authority, intent, collection, refusal, observed, job, terminal=None):
    """Revalidate the real collection after readback recovers, without dispatch.

    The CLOSED broker attests the transient HTTP failure. Historical validation
    authenticates its exact inputs and original windows, never extends authority.
    """
    import broker_evidence
    object_fields(refusal,('code','observation'),'native outage refusal')
    observation=refusal['observation']
    object_fields(observation,('path','status'),'native outage observation')
    s=a.request['snapshot']; d=a.binding['deployment']
    require(refusal['code']=='readback_unavailable' and type(observation['status']) is int and
            observation['status'] in (502,503,504) and
            observation['path']=='/repos/'+d['policy']['authority_repository']+'/actions/runs/'+str(s['run_id'])+'/artifacts',
            'wrong native authority readback refusal')
    object_fields(collection,('locators','request','controls','proofs'),'native broker collection')
    locators=collection['locators']; request=collection['request']
    require(positive(observed) and intent['issued']<=request['issued']<=observed and
            digest(locators['proofs'])==digest(intent['proofs']), 'native outage collection differs')
    receipts=ActionsReceipts._create(authority,a.registry.binding,job,a.clock,recovery=True,admission=a)
    ready=receipts.find_for_recovery('control-ready')
    require(ready is not None and digest(receipts.authenticate(ready))==digest(request), 'exact Session readiness required')
    prepared=broker_evidence._preload(a.registry,a.source,authority,a.record['pair']['identities'],job,
                                    locators,lambda:intent['issued'],admission=a,terminal=terminal)
    return broker_evidence._finish(a.registry,a.source,authority,a.record['pair']['identities'],prepared,request,
        collection['controls'],collection['proofs'],lambda:observed,admission=a,terminal=terminal)


def run(a, authority, session, uploader, sleeper):
    """Only admission differs from the ordinary broker Session implementation."""
    import service
    identity=_identity(a); a.guard()
    job=session.job_id; s=a.request['snapshot']; key=str(s['pr'])
    receipts=ActionsReceipts._create(authority,a.registry.binding,job,a.clock,uploader=uploader,admission=a)
    receipts.current_job()
    name='trial-broker-intent-'+key+'-'+str(s['run_attempt'])
    root='/repos/'+a.binding['deployment']['policy']['authority_repository']+'/actions/runs/'+str(s['run_id'])
    require(not any(v['name']==name for v in authority.pages(root+'/artifacts','artifacts')),
            'broker intent exists; never replay an uncertain attempt')
    _prerequisites(a,authority)
    locators=service._publication_locators(authority,a.binding,a.request)['proofs']
    issued=a.clock(); proofs=_proofs(a,authority,locators,issued)
    intent=dict(identity,kind='trial-broker-intent',job_id=job,issued=issued,proofs=locators,proofs_digest=proofs['proofs_digest'],
                publication_digest=_publication(a,authority,issued))
    before=guard(a)
    service._upload_document(uploader,name,intent)
    a.guard()
    expiry=a.candidate['name']=='expired-proof'
    if expiry:
        # Authentic initially valid envelopes age without changing their bytes.
        deadline=min(proofs['valid_until'].values())
        while a.clock()<deadline:
            a.guard(); sleeper(min(2,deadline-a.clock()))
        _prerequisites(a,authority)
        _expiry(a,authority,locators,a.clock())
    a.guard()
    try:
        session._run(_admission=a)
    except BrokerRefusal as error:
        refusal=dict(code=error.code,observation=error.observation)
        if expiry:
            require(error.code=='proof_expired' and _expiry(a,authority,locators,error.observation['observed'])==refusal,
                    'Session did not establish exact retained-proof expiry')
        else:
            observed=session._refused_at
            collection=session._collection
            _outage(a,authority,intent,collection,refusal,observed,job)
    else:
        require(False,'Session did not establish native broker refusal')
    _prerequisites(a,authority)
    after=guard(a)
    receipts=ActionsReceipts._create(authority,a.registry.binding,job,a.clock,recovery=True,admission=a)
    location=receipts.find_for_recovery('not-submitted')
    require(location is not None and all(receipts.find_for_recovery(k) is None for k in ('gate','dispatch','outcome','host-denied')),
            'genuine no-dispatch Session evidence required')
    terminal=receipts.authenticate(location)
    document=dict(identity,job_id=job,intent=intent,refusal=refusal,receipt=location,receipt_digest=digest(terminal),completed=a.clock())
    if not expiry:
        document.update(collection=collection,observed=observed,before=before,after=after)
    guard(a)
    service._upload_document(uploader,'trial-broker-denial-'+key+'-'+str(s['run_attempt']),document)
    a.guard()
    return dict(state='broker-denied',refusal=refusal['code'],operation_id=a.request['operation_id'],sequence=a.request['sequence'],fence_pending=True)


def read(a, authority, job_id):
    """Authenticate the exact named CLOSED outcome before terminal effects."""
    import service
    identity=_identity(a); s=a.request['snapshot']; d=a.binding['deployment']; key=s['pr']
    def load(role):
        locator=service._locator(authority,d,s['run_id'],s['run_attempt'],role,key)
        return provenance.authenticated_document(authority,d,locator,role,key,a.clock())
    proof=load('trial-broker-denial'); value=proof['document']
    expiry=a.candidate['name']=='expired-proof'
    extra=[] if expiry else ['collection','observed','before','after']
    object_fields(value,(*identity,'job_id','intent','refusal','receipt','receipt_digest','completed',*extra),'native broker outcome')
    require(type(value['schema_version']) is int and positive(value['job_id']) and
            all(value[k]==v for k,v in identity.items()) and value['job_id']==proof['job_id']==job_id and
            positive(value['completed']) and proof['job_started']<=value['completed']<=proof['artifact_created']<=proof['job_completed'],
            'broker outcome identity or interval differs')
    retained=load('trial-broker-intent'); intent=value['intent']
    object_fields(intent,(*identity,'job_id','issued','proofs','proofs_digest','publication_digest'),'native broker intent')
    require(type(intent['schema_version']) is int and positive(intent['job_id']) and
            digest(intent)==digest(retained['document']) and retained['job_id']==job_id and
            all(intent[k]==v for k,v in dict(identity,kind='trial-broker-intent').items()) and intent['job_id']==job_id and
            positive(intent['issued']) and proof['job_started']<=intent['issued']<=retained['artifact_created']<=value['completed'],
            'broker intent differs or postdates attempt')
    require(_proofs(a,authority,intent['proofs'],intent['issued'])['proofs_digest']==intent['proofs_digest'],
            'original valid proofs differ')
    require(_publication(a,authority,intent['issued'])==intent['publication_digest'],'original publication observation differs')
    refusal=value['refusal']; object_fields(refusal,('code','observation'),'native broker refusal')
    observed=refusal['observation'].get('observed') if expiry else value['observed']
    require(positive(observed) and retained['artifact_created']<=observed<=value['completed'] and
            (not expiry or _expiry(a,authority,intent['proofs'],observed)==refusal),'exact proof expiry observation differs')
    if not expiry:
        require(digest(value['before'])==digest(value['after'])==digest(s),'native outage before/after differs')
        _outage(a,authority,intent,value['collection'],refusal,observed,job_id,terminal=value['receipt'])
    receipts=ActionsReceipts._create(authority,a.registry.binding,job_id,a.clock,recovery=True,admission=a)
    receipts.terminal_job()
    require(receipts.find_for_recovery('not-submitted')==value['receipt'] and
            all(receipts.find_for_recovery(k) is None for k in ('gate','dispatch','outcome','host-denied')),
            'broker outcome has no exact no-dispatch receipt')
    receipt=receipts.authenticate(value['receipt'])
    require(digest(receipt)==value['receipt_digest'] and observed<=receipt['issued']<=value['completed'],
            'broker receipt differs or predates refusal')
    _prerequisites(a,authority)
    return copy.deepcopy(value)
