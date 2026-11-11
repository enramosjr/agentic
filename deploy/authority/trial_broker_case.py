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
    return admission.candidate['name'] in ('expired-proof','authority-outage','revoked-qualification','context-transition')


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


def _prerequisites(a, authority, live=True):
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
    if live:
        live_certificate(a,authority)
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
    if a.candidate['name']=='context-transition':
        from trial_broker_context import run
        return run(a, authority, session, uploader)
    if a.candidate['name']=='revoked-qualification':
        return run_revocation(a,authority,session,uploader)
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
    if a.candidate['name']=='revoked-qualification':
        return read_revocation_outcome(a,authority,job_id)
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


def certificate_document(initial, consumption):
    require(initial['candidate']['name']=='revoked-qualification','fixed revocable certificate case required')
    return dict(schema_version=1,kind='native-trial-certificate-observation',consumption=copy.deepcopy(consumption),
                certificate=copy.deepcopy(initial['certificate']),request_digest=digest(initial['request']),
                origin='native-trial-certificate',hosted_qualified=False,enforcement_active=False)


def _case_value(a):
    from trial_case import read
    from trial_controller import case_journal
    original=a.original if hasattr(a,'original') else a.native.provision.session.registry
    if hasattr(a,'case'):
        value=a.case
    else:
        c=a.native.provision
        publication=c.store(c.root/case_journal('trial-case-publication',a.candidate)).read()
        require(publication is not None and publication['value']['phase']=='bound','owned bound revocation execution required')
        value,record=read(original,publication['value']['revision_bound'],a.clock)
        require(record==a.record,'revocation substituted original record')
    require(value['execution'] is not None and value['request']==a.request and value['certificate']==a.value['certificate'],
            'revocation substituted case certificate')
    return original,value


def _certificate_preimage(a, proof):
    from trial_case import read,consumption
    original,value=_case_value(a)
    execution=value['execution']
    initial,record=read(original,execution['publication_revision'],a.clock)
    locator=execution['handshake']
    expected=certificate_document(initial,consumption(initial,execution['publication_revision'],execution['credential'],locator))
    require(proof['document']==expected and record==a.record and
            all(proof[k]==locator[k] for k in ('run_id','attempt','job_id')) and
            proof['job_started']<=proof['artifact_created']<=proof['job_completed']<execution['credential']['expires'],
            'native certificate preimage or CLOSED producer differs')
    a.local_guard()
    return proof


def live_certificate(a, authority):
    """An authentic retained certificate alone never grants live authorization."""
    if a.candidate['name']!='revoked-qualification': return None
    import service
    s=a.request['snapshot']; d=a.binding['deployment']
    locator=service._locator(authority,d,s['run_id'],s['run_attempt'],'trial-case-certificate',a.record['task_id'])
    proof=provenance.authenticated_document(authority,d,locator,'trial-case-certificate',a.record['task_id'],a.clock())
    _certificate_preimage(a,proof)
    a.guard()
    return proof


def validate_preloaded(a, value, job, now):
    from trial_controller import authenticated
    authenticated(a)
    if a.candidate['name']=='context-transition':
        from trial_broker_context import validate_preloaded
        return validate_preloaded(a, value, job, now)
    require(a.candidate['name']=='revoked-qualification','native revocation preload only')
    object_fields(value,('schema_version kind request_digest certificate prepared_digest job_id issued').split(),'native preload marker')
    require(type(value['schema_version']) is int and value['schema_version']==1 and value['kind']=='trial-preloaded' and
            value['request_digest']==digest(a.request) and positive(job) and value['job_id']==job and
            isinstance(value['prepared_digest'],str) and len(value['prepared_digest'])==64 and
            positive(value['issued']) and a.binding['fence']['pending']['created']<=value['issued']<=now,
            'exact broker preload marker differs')
    _certificate_preimage(a,value['certificate'])
    return value


def preloaded(session, prepared):
    """Only the actual shared collector can publish this live broker receipt."""
    import time
    from registry import trial_reference
    from trusted_ci_github import HostRefusal
    a=session._admission
    marker=dict(schema_version=1,kind='trial-preloaded',request_digest=digest(a.request),
                certificate=prepared['trial_certificate'],prepared_digest=digest(prepared),job_id=session.job_id,issued=a.clock())
    session.receipts.append('trial-preloaded',marker)
    original,_=_case_value(a)
    result=dict(kind='native-trial-revocation-result',name=a.candidate['name'],task_id=a.record['task_id'],execution=None)
    deadline=time.monotonic()+min(300,a.value['certificate']['expires']-a.clock())
    while True:
        guard(a); session.receipts.current_job()
        require(time.monotonic()<deadline,'native certificate deletion remains pending')
        try:
            original.ref(trial_reference(result))
            break
        except HostRefusal as error:
            require(error.status==404,'native revocation observation unavailable')
        session.sleeper(0.25)
    read_revocation(a,session.authority,session.job_id)
    guard(a)


def _revocation_identity(a, operator, admin, preview):
    from configuration import SetupConfigurationSession
    session=SetupConfigurationSession.__new__(SetupConfigurationSession)
    session.operator_api,session.admin_api=operator,admin
    session.identities,session.preview=a.record['pair']['identities'],preview
    return session._native_identity(a.binding['deployment'])


def native_revoke(a, operator, admin, token_factory):
    """One owned native DELETE. Unknown effects retain their intent, never retry."""
    import bootstrap
    from trial_configuration import _Boundary
    from trial_controller import Admission
    from trial_transition import _publish_native
    require(type(a) is Admission and a.candidate['name']=='revoked-qualification','actual native revocation owner required')
    c=a.native.provision; journal=c.store(c.root/'trial-native-revocation')
    require(journal.read() is None,'native revocation already retained; unknown effects never replay')
    _prerequisites(a,a.registry.api)
    original,case=_case_value(a); d=a.binding['deployment']; p=d['policy']; s=a.request['snapshot']
    job=provenance.execution_job(a.registry.api,d,s['run_id'],s['run_attempt'],'broker ('+str(s['pr'])+')')
    store=ActionsReceipts._create(a.registry.api,a.registry.binding,job['id'],a.clock,recovery=True,admission=a)
    marker=store.find_for_recovery('trial-preloaded')
    require(marker is not None and job['status']=='in_progress','actual live broker preload required')
    prepared=store.authenticate(marker)
    proof=live_certificate(a,a.registry.api)
    require(proof==prepared['certificate'],'preloaded native certificate changed')
    preview={k:p[k] for k in ('repository','repository_id','target','authority_repository','authority_repository_id')}
    preview.update(adapter=d['adapter'],account=d['account'],operator_id=c.preview['fixture']['operator_id'])
    identity=_revocation_identity(a,operator,admin,preview)
    expires=min(case['certificate']['expires'],case['execution']['credential']['expires'],a.record['expires'])
    claim=dict(schema_version=1,kind='native-trial-revocation-intent',task_id=a.record['task_id'],execution=None,
        name='revoked-qualification',record_digest=digest(a.record),case_digest=digest(case),request_digest=digest(a.request),
        certificate=proof,marker=marker,preloaded=prepared,job_id=job['id'],identity=identity,preview=preview,
        issued=a.clock(),expires=expires)
    document=journal.write(None,dict(phase='intent-started',record=a.record,binding=a.binding,case=case,claim=claim,
        provisioning=copy.deepcopy(c.document),credential=None,mint_started=False,delete_started=False,intent=None,result=None))
    value=copy.deepcopy(document['value'])
    def save():
        nonlocal document
        document=journal.write(document,value)
    def owner_guard():
        require(journal.read()==document,'native revocation ownership changed')
        _prerequisites(a,a.registry.api,live=False)
        current=provenance.execution_job(a.registry.api,d,s['run_id'],s['run_attempt'],'broker ('+str(s['pr'])+')')
        require(current['id']==job['id'] and current['status']=='in_progress','native revocation broker replaced or cancelled')
        require(_revocation_identity(a,operator,admin,preview)==identity,'native revocation identity changed')
        if value['intent'] is not None:
            from trial_transition import read_native
            require(read_native(original,value['intent'],a.record)==claim,'native deletion intent moved')
        # Identity and immutable-publication authentication perform blocking reads.
        # Re-sample source, cancellation and time after them, before every effect.
        guard(a)
        current=provenance.execution_job(a.registry.api,d,s['run_id'],s['run_attempt'],'broker ('+str(s['pr'])+')')
        require(current['id']==job['id'] and current['status']=='in_progress','native revocation broker cancelled')
        a.local_guard()
    token=None
    try:
        value['intent']=_publish_native(c,a.record,claim,owner_guard); save()
        owner_guard(); value['mint_started']=True; save()
        token=bootstrap.installation_token(_Boundary(admin,owner_guard),identity['installation_id'],
                                           [p['authority_repository_id']],dict(actions='write'))
        value['credential']=dict(token=token,revoked=False); save()
        scoped=token_factory(token)
        require([x['id'] for x in scoped.pages('/installation/repositories','repositories')]==[p['authority_repository_id']],
                'native deletion capability scope differs')
        _prerequisites(a,a.registry.api); require(live_certificate(a,a.registry.api)==proof,'native certificate changed before DELETE')
        owner_guard(); value['delete_started']=True; save(); owner_guard()
        scoped.fetch('/repos/'+p['authority_repository']+'/actions/artifacts/'+str(proof['artifact_id']),method='DELETE',expected_status=204)
        owner_guard(); _absent(a,a.registry.api,proof)
        result=dict(schema_version=1,kind='native-trial-revocation-result',task_id=a.record['task_id'],execution=None,
                    name='revoked-qualification',record_digest=digest(a.record),intent=value['intent'],
                    intent_digest=digest(claim),status=204,completed=a.clock())
        value['result_preimage']=result; value['phase']='result-started'; save()
        value['result']=_publish_native(c,a.record,result,owner_guard); value['phase']='complete'; save()
        return copy.deepcopy(value['result'])
    finally:
        if token is not None:
            # Capability removal is independent of an expired admission or lost result.
            token_factory(token).fetch('/installation/token',method='DELETE',binary=True)
            value['credential']['revoked']=True; save()


def cleanup_revocation(native, operator, admin, token_factory):
    """Expired cleanup removes only the exact retained native capability."""
    from trial_handoff import Native
    from trial_setup import Provision
    from types import SimpleNamespace
    from trial_case import history_guard
    require(type(native) is Native and type(native.provision) is Provision,'actual native cleanup owner required')
    c=native.provision; journal=c.store(c.root/'trial-native-revocation'); document=journal.read()
    require(document is not None,'retained native revocation required')
    value=copy.deepcopy(document['value']); record=value['record']
    require(c.document==value['provisioning'] and c.store(c.root/'trial').read()==value['provisioning'] and
            c.session.owner==record['origin']['owner'] and c.session.scope==record['origin']['scope'],
            'native revocation cleanup ownership changed')
    c.session.registry.unchanged(record['origin']['binding'])
    history_guard(c.session.registry,record,value['case']['history'],c.clock,native.registry.api)
    from trial_transition import read_native
    require(value['intent'] is not None and read_native(c.session.registry,value['intent'],record)==value['claim'],
            'cleanup substituted native revocation intent')
    _revocation_identity(SimpleNamespace(record=record,binding=value['binding']),operator,admin,value['claim']['preview'])
    credential=value['credential']
    if credential is not None and not credential['revoked']:
        require(journal.read()==document,'cleanup ownership changed during authentication')
        token_factory(credential['token']).fetch('/installation/token',method='DELETE',binary=True)
        credential['revoked']=True; journal.write(document,value)


def _absent(a, authority, proof):
    d=a.binding['deployment']; run=proof['run_id']
    artifacts=authority.pages('/repos/'+d['policy']['authority_repository']+'/actions/runs/'+str(run)+'/artifacts','artifacts')
    name='trial-case-certificate-'+a.record['task_id']+'-'+str(proof['attempt'])
    require(not any(x['id']==proof['artifact_id'] or x['name']==name for x in artifacts),'native certificate still present or replaced')
    a.guard()


def read_revocation(a, authority, job):
    from registry import trial_reference
    from trial_transition import read_native
    original,case=_case_value(a)
    kinds=('native-trial-revocation-intent','native-trial-revocation-result')
    links={kind:dict(kind=kind,revision=original.ref(trial_reference(dict(kind=kind,name=a.candidate['name'],
        task_id=a.record['task_id'],execution=None)))) for kind in kinds}
    intent,result=(read_native(original,links[kind],a.record) for kind in kinds)
    object_fields(intent,('schema_version kind task_id execution name record_digest case_digest request_digest certificate marker preloaded job_id identity preview issued expires').split(),'native revocation intent')
    object_fields(result,('schema_version kind task_id execution name record_digest intent intent_digest status completed').split(),'native revocation result')
    require(type(intent['schema_version']) is int and intent['schema_version']==1 and
            type(result['schema_version']) is int and result['schema_version']==1 and
            intent['case_digest']==digest(case) and intent['request_digest']==digest(a.request) and
            intent['job_id']==job and result['intent']==links[kinds[0]] and result['intent_digest']==digest(intent) and
            type(result['status']) is int and result['status']==204 and positive(intent['issued']) and positive(result['completed']) and
            a.binding['fence']['pending']['created']<=intent['issued']<=result['completed']<=a.clock()<intent['expires'] and
            intent['expires']==min(case['certificate']['expires'],case['execution']['credential']['expires'],a.record['expires']),
            'native revocation result or interval differs')
    _certificate_preimage(a,intent['certificate'])
    store=ActionsReceipts._create(authority,a.registry.binding,job,a.clock,recovery=True,admission=a)
    require(store.find_for_recovery('trial-preloaded')==intent['marker'] and
            store.authenticate(intent['marker'])==intent['preloaded'] and
            intent['preloaded']['certificate']==intent['certificate'] and intent['preloaded']['issued']<=intent['issued'],
            'native deletion did not follow exact Session preload')
    _absent(a,authority,intent['certificate'])
    old=getattr(a,'_revocation_links',None)
    require(old is None or old==links,'native revocation publications changed')
    if old is None:
        a._revocation_links=copy.deepcopy(links)
        if hasattr(a,'_seal'): a._seal=copy.deepcopy(a._state())
    guard(a)
    return dict(links=links,intent=intent,result=result)


def history_revocation(original, record, case, links):
    """Immutable terminal/history pins; no live admission or authorization."""
    from trial_transition import read_native
    kinds=('native-trial-revocation-intent','native-trial-revocation-result')
    object_fields(links,kinds,'retained revocation publications')
    intent,result=(read_native(original,links[kind],record) for kind in kinds)
    require(intent['case_digest']==digest(case) and intent['request_digest']==digest(case['request']) and
            intent['certificate']['document']['certificate']==case['certificate'] and
            result['intent']==links[kinds[0]] and result['intent_digest']==digest(intent) and
            type(result['status']) is int and result['status']==204,
            'historical revocation publication differs')


def certificate_readback(a, authority, proof):
    """Only exact native removal of a successfully preloaded certificate is typed."""
    import service
    s=a.request['snapshot']; d=a.binding['deployment']
    artifacts=authority.pages('/repos/'+d['policy']['authority_repository']+'/actions/runs/'+str(s['run_id'])+'/artifacts','artifacts')
    name='trial-case-certificate-'+a.record['task_id']+'-'+str(s['run_attempt'])
    if any(x['name']==name for x in artifacts):
        require(live_certificate(a,authority)==proof,'preloaded certificate replaced')
        return
    job=provenance.execution_job(authority,d,s['run_id'],s['run_attempt'],'broker ('+str(s['pr'])+')')
    value=read_revocation(a,authority,job['id'])
    require(value['intent']['certificate']==proof,'deleted certificate differs from preload')
    _prerequisites(a,authority,live=False)
    raise BrokerRefusal('trial_certificate_revoked','authenticated native trial certificate was removed',
                        dict(origin='native-trial-certificate',certificate_digest=digest(proof),deletion=value['links']))


def run_revocation(a, authority, session, uploader):
    import service
    identity=_identity(a); s=a.request['snapshot']; key=str(s['pr'])+'-'+str(s['run_attempt'])
    name='trial-broker-intent-'+key
    root='/repos/'+a.binding['deployment']['policy']['authority_repository']+'/actions/runs/'+str(s['run_id'])
    require(not any(x['name']==name for x in authority.pages(root+'/artifacts','artifacts')),'broker intent exists; never replay')
    _prerequisites(a,authority)
    intent=dict(identity,kind='trial-broker-intent',job_id=session.job_id,issued=a.clock(),certificate=live_certificate(a,authority))
    service._upload_document(uploader,name,intent)
    try:
        session._run(_admission=a)
    except BrokerRefusal as error:
        require(error.code=='trial_certificate_revoked','wrong native certificate refusal')
        refusal=dict(code=error.code,observation=error.observation)
    else:
        require(False,'Session did not establish certificate revocation')
    deletion=read_revocation(a,authority,session.job_id)
    _prerequisites(a,authority,live=False)
    store=ActionsReceipts._create(authority,a.registry.binding,session.job_id,a.clock,recovery=True,admission=a)
    receipt=store.find_for_recovery('not-submitted')
    require(receipt is not None and all(store.find_for_recovery(k) is None for k in ('gate','dispatch','outcome','host-denied')),
            'exact no-dispatch revocation receipt required')
    document=dict(identity,job_id=session.job_id,intent=intent,deletion=deletion,refusal=refusal,receipt=receipt,
                  receipt_digest=digest(store.authenticate(receipt)),completed=a.clock())
    guard(a); service._upload_document(uploader,'trial-broker-denial-'+key,document); guard(a)
    return dict(state='broker-denied',refusal=refusal['code'],operation_id=a.request['operation_id'],sequence=a.request['sequence'],fence_pending=True)


def read_revocation_outcome(a, authority, job):
    """Historical preimages authenticate a CLOSED terminal, never authorization."""
    import service
    s=a.request['snapshot']; d=a.binding['deployment']; identity=_identity(a)
    def load(role):
        location=service._locator(authority,d,s['run_id'],s['run_attempt'],role,s['pr'])
        return provenance.authenticated_document(authority,d,location,role,s['pr'],a.clock())
    proof=load('trial-broker-denial'); value=proof['document']; retained=load('trial-broker-intent')
    object_fields(value,(*identity,'job_id','intent','deletion','refusal','receipt','receipt_digest','completed'),'revocation outcome')
    intent=value['intent']
    object_fields(intent,(*identity,'job_id','issued','certificate'),'revocation broker intent')
    require(all(value[k]==v for k,v in identity.items()) and all(intent[k]==v for k,v in dict(identity,kind='trial-broker-intent').items()) and
            retained['document']==intent and value['job_id']==intent['job_id']==proof['job_id']==retained['job_id']==job and
            positive(intent['issued']) and positive(value['completed']) and
            proof['job_started']<=intent['issued']<=retained['artifact_created']<=value['completed']<=proof['artifact_created']<=proof['job_completed'],
            'CLOSED revocation identity or interval differs')
    deletion=read_revocation(a,authority,job)
    require(value['deletion']==deletion and intent['certificate']==deletion['intent']['certificate'] and
            retained['artifact_created']<=deletion['intent']['preloaded']['issued'] and
            deletion['result']['completed']<=value['completed'] and
            value['refusal']==dict(code='trial_certificate_revoked',observation=dict(origin='native-trial-certificate',
                certificate_digest=digest(intent['certificate']),deletion=deletion['links'])), 'exact native certificate refusal differs')
    store=ActionsReceipts._create(authority,a.registry.binding,job,a.clock,recovery=True,admission=a)
    store.terminal_job()
    require(store.find_for_recovery('not-submitted')==value['receipt'] and all(store.find_for_recovery(k) is None for k in ('gate','dispatch','outcome','host-denied')),
            'revocation has contradictory dispatch evidence')
    receipt=store.authenticate(value['receipt'])
    require(digest(receipt)==value['receipt_digest'] and deletion['result']['completed']<=receipt['issued']<=value['completed'],
            'revocation receipt preimage or interval differs')
    ready=store.find_for_recovery('control-ready')
    require(ready is not None,'revocation final collection is missing')
    request=store.authenticate(ready)
    import control_rendezvous
    controls=service._locator(authority,d,s['run_id'],s['run_attempt'],'controls',s['pr'])
    control_rendezvous._read_response(authority,a.binding,request,controls,a.clock(),a)
    final={purpose:service._locator(authority,d,s['run_id'],s['run_attempt'],'final-proof',purpose)
           for purpose in ('admin','reader','issuer','coding','merge')}
    broker_proofs._read_final(authority,a.binding,a.record['pair']['identities'],s,request,final,a.clock(),a)
    _prerequisites(a,authority,live=False)
    return copy.deepcopy(value)
