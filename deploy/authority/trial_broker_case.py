"""Held native broker negatives over the shared Session; never dispatch a merge."""
import copy

import broker_proofs
import provenance
from broker_refusal import BrokerRefusal
from merge_receipts import ActionsReceipts
from trusted_ci_policy import digest, object_fields, positive, require, sha


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
    require(not expiry or not receipts._matches('control-ready'),'expired-proof refusal must precede readiness')
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
    require(not expiry or not receipts._matches('control-ready'),'expired-proof refusal must precede readiness')
    receipt=receipts.authenticate(value['receipt'])
    require(digest(receipt)==value['receipt_digest'] and observed<=receipt['issued']<=value['completed'],
            'broker receipt differs or predates refusal')
    _prerequisites(a,authority)
    return copy.deepcopy(value)


def _negative_current(binding, record, retained, authority, source, now):
    """Current prerequisites without creating an Admission or source credential."""
    import service
    from authority_github import Readers,current_snapshot
    from qualification_cases import HostCases
    from trusted_ci_github import independent_approval
    from broker_evidence import _additional_checks
    d=binding['deployment']; s=retained['request']['snapshot']; readers=Readers(source,authority,d)
    require(current_snapshot(readers,d,s['pr'],s['run_id'],s['run_attempt'])==s,'broker negative candidate changed')
    location=service._locator(authority,d,s['run_id'],s['run_attempt'],'evidence',s['pr'])
    proof=provenance.authenticated_document(authority,d,location,'evidence',s['pr'],now)
    task=dict(kind='native-trial-case-task',submitted=retained['candidate']['submitted'],worker=retained['worker'],
              certificate_digest=digest(retained['certificate']))
    coordinates=dict(configuration_revision=binding['configuration_revision'],operation=binding['fence']['pending'],
        sequence=binding['fence']['sequence'],issuer_installation_id=record['pair']['identities']['apps']['issuer']['installation_id'],
        evidence_job_id=proof['job_id'],evidence_digest=digest(proof['document']),task_digest=digest(task))
    probe=HostCases(None,source,authority,record['pair']['identities'],None,None,None,lambda:now)
    probe._success(s,location,coordinates,d)
    pr=source.get('/repos/'+d['policy']['repository']+'/pulls/'+str(s['pr']))
    require(pr.get('mergeable') is True,'unresolved broker negative candidate')
    independent_approval(source,d['policy'],pr,human=True)
    from urllib.parse import quote
    rules=source.pages('/repos/'+d['policy']['repository']+'/rules/branches/'+quote(d['policy']['target'],safe=''))
    required=[v for rule in rules if rule['type']=='required_status_checks' for v in rule['parameters']['required_status_checks']]
    require(any(v['context']==d['policy']['check_name'] and v.get('integration_id')==d['policy']['app_id'] for v in required),
            'broker negative current issuer obligation missing')
    _additional_checks(source,d,s,required)
    require(current_snapshot(readers,d,s['pr'],s['run_id'],s['run_attempt'])==s,'broker negative candidate changed during readback')


def expired_terminal(authority, record, retained, terminal, proof, now, source=None):
    """Exact fourth CLOSED broker refusal. Evidence-only; no active Admission."""
    return _negative_terminal(authority,record,retained,terminal,proof,now,source,'expired-proof')


def outage_terminal(authority, record, retained, terminal, proof, now, source=None):
    """Exact fifth CLOSED broker refusal. Evidence-only; no active Admission."""
    return _negative_terminal(authority,record,retained,terminal,proof,now,source,'authority-outage')


def _negative_terminal(authority, record, retained, terminal, proof, now, source, case):
    # Only immutable terminal/consumption authentication is shared. The original
    # refusal semantics below remain distinct: readiness is forbidden for expiry
    # and required for outage. Neither path creates an Admission or a gate.
    from merge_receipts import not_submitted
    from service import _locator,_publication_result
    from trial_host_case import _ClosedDirectAPI
    from trusted_ci_deployment import timestamp
    from trial_case import _closed,consumption
    from trial_launch import consumption as ready_consumption
    from authority_protocol import fingerprint
    object_fields(terminal,('schema_version kind request_digest certificate_digest before after completed recovery broker_receipt').split(),
                  'broker negative v2 terminal')
    require(type(terminal['schema_version']) is int and terminal['schema_version']==2 and
            retained['candidate']['name']==case and terminal['kind']=='trial-case-terminal' and
            terminal['request_digest']==digest(retained['request']) and terminal['certificate_digest']==digest(retained['certificate']),
            'exact broker negative v2 evidence required; legacy terminals remain held')
    authority=_ClosedDirectAPI(authority)
    b=terminal['before']; d=b['deployment']; request=retained['request']; s=request['snapshot']; op=b['fence']['pending']
    require(b['fence']==retained['pending'] and op==retained['certificate']['operation'] and
            s['run_attempt']==op['attempt']==1 and type(now) is int and
            now<min(record['expires'],retained['certificate']['expires'],d['expires']) and
            positive(terminal['completed']) and proof['job_started']<=terminal['completed']<=proof['artifact_created']<=proof['job_completed']<=now,
            'broker negative terminal binding or interval differs')
    # Reauthenticate the original CLOSED READY and case-consumption preimages.
    # These finite capabilities constrain original events, not today's history read.
    execution,launch=retained['execution'],retained['launch']
    require(execution is not None and launch is not None,'broker negative consumed launch required')
    object_fields(execution,('publication_revision credential handshake').split(),'broker negative consumed execution')
    object_fields(launch,('revision credential handshake').split(),'broker negative consumed launch')
    ready={k:retained[k] for k in ('schema_version','task_id','origin_revision','prompt','candidate','worker','history')}
    ready.update(kind='trial-case-ready',execution=None)
    for link,role,initial,revision in (
            (launch,'trial-case-ready',ready,launch['revision']),
            (execution,'trial-case-handoff',dict(retained,execution=None),execution['publication_revision'])):
        credential=link['credential']; locator=link['handshake']
        object_fields(credential,('revision repository_id permissions token_digest expires').split(),'broker negative retained credential')
        require(credential['revision']==launch['revision'] and positive(credential['repository_id']) and
                credential['repository_id']==launch['credential']['repository_id'] and
                credential['permissions']==dict(contents='read') and fingerprint(credential['token_digest']) and
                credential['token_digest']==launch['credential']['token_digest'] and positive(credential['expires']) and
                credential['expires']<=retained['certificate']['expires'] and
                locator['run_id']==s['run_id'] and locator['attempt']==1,
                'broker negative retained capability scope or interval differs')
        consumed=provenance.authenticated_document(authority,d,locator,role,record['task_id'],now)
        expected=(ready_consumption if role=='trial-case-ready' else consumption)(initial,revision,credential,locator)
        _closed(consumed,expected,record['created'],credential['expires'])
        require(proof['job_completed']<credential['expires'],'broker negative original producer outlived capability')
    envelope=terminal['recovery']; receipt=terminal['broker_receipt']
    object_fields(envelope,('schema_version kind operation_digest configuration_revision deployment_digest producer recovery artifacts facts').split(),
                  'broker negative recovery envelope')
    require(type(envelope['schema_version']) is int and envelope['schema_version']==2 and envelope['kind']=='broker-terminal-recovery' and
            envelope['operation_digest']==digest(op) and envelope['configuration_revision']==b['configuration_revision'] and
            envelope['deployment_digest']==b['deployment_digest'] and envelope['facts'] is None and
            terminal['after']['fence']['completed'][-1]['receipt_digest']==digest(envelope),
            'broker negative recovery digest differs')
    require(envelope['recovery']==dict(run_id=proof['run_id'],attempt=proof['attempt'],job_id=proof['job_id'],workflow_sha=d['policy']['workflow_sha']) and
            proof['run_id']==op['run_id'] and proof['attempt']==1,'broker negative recovery producer differs')
    producer=envelope['producer']; object_fields(producer,('id run_id head_sha conclusion completed_at').split(),'broker negative CLOSED broker')
    require(positive(producer['id']) and producer['conclusion']=='success','successful CLOSED broker negative required')
    reader=ActionsReceipts(authority,lambda:copy.deepcopy(b),producer['id'],lambda:now,recovery=True)
    job=reader.terminal_job(); closed=int(timestamp(job['completed_at']).timestamp())
    require(producer=={k:job[k] for k in producer} and closed<=proof['job_started'],'broker negative broker/finalizer interval differs')
    artifacts=envelope['artifacts']; object_fields(artifacts,('not-submitted dispatch outcome host-denied').split(),'broker negative recovery artifacts')
    require(artifacts['not-submitted'] is not None and all(artifacts[k] is None for k in ('dispatch','outcome','host-denied')) and
            all(not reader._matches(k) for k in ('gate','dispatch','outcome','host-denied')) and
            (case!='expired-proof' or not reader._matches('control-ready')),
            'broker negative has conflicting dispatch evidence')
    require(reader.find_for_recovery('not-submitted')==artifacts['not-submitted'] and
            reader.authenticate(artifacts['not-submitted'])==receipt and
            digest(receipt)==digest(not_submitted(b,producer['id'],receipt.get('issued'))),
            'broker negative Session receipt differs')
    matches=reader._matches('not-submitted')
    require(len(matches)==1 and matches[0]['id']==artifacts['not-submitted']['artifact_id'] and
            matches[0]['digest']==artifacts['not-submitted']['archive_digest'],'broker negative receipt archive changed')
    receipt_created=int(timestamp(matches[0]['created_at']).timestamp())
    identity=dict(schema_version=1,kind='trial-broker-denial',case=case,
                  request_digest=digest(request),certificate_digest=digest(retained['certificate']))
    def load(role):
        location=_locator(authority,d,s['run_id'],1,role,s['pr'])
        return provenance.authenticated_document(authority,d,location,role,s['pr'],now)
    denial=load('trial-broker-denial'); value=denial['document']; saved=load('trial-broker-intent'); intent=value['intent']
    extra=[] if case=='expired-proof' else ['collection','observed','before','after']
    object_fields(value,(*identity,'job_id','intent','refusal','receipt','receipt_digest','completed',*extra),'native broker outcome')
    object_fields(intent,(*identity,'job_id','issued','proofs','proofs_digest','publication_digest'),'broker negative intent')
    require(type(value['schema_version']) is int and type(intent['schema_version']) is int and
            all(value[k]==v for k,v in identity.items()) and
            all(intent[k]==v for k,v in dict(identity,kind='trial-broker-intent').items()) and
            positive(value['job_id']) and positive(intent['job_id']) and
            value['job_id']==intent['job_id']==denial['job_id']==saved['job_id']==producer['id'] and saved['document']==intent and
            value['receipt']==artifacts['not-submitted'] and value['receipt_digest']==digest(receipt),
            'broker negative intent, outcome or receipt identity differs')
    refusal=value['refusal']; object_fields(refusal,('code','observation'),'broker negative refusal')
    if case=='expired-proof':
        object_fields(refusal['observation'],('purpose artifact_id proof_digest provenance expires observed').split(),'expired-proof observation')
    observed=refusal['observation']['observed'] if case=='expired-proof' else value['observed']
    require(positive(intent['issued']) and positive(observed) and positive(value['completed']) and
            denial['job_started']<=intent['issued']<=saved['artifact_created']<=observed<=receipt['issued']<=receipt_created<=value['completed']<=
            denial['artifact_created']<=closed and saved['job_started']==denial['job_started'] and
            saved['job_completed']==denial['job_completed']==closed and
            value['completed']<min(record['expires'],retained['certificate']['expires'],op['execution_deadline'],d['expires']),
            'broker negative original event interval differs')
    if case=='expired-proof':
        original,expected=broker_proofs._expired_history(authority,b,record,retained,intent['proofs'],intent['issued'],observed)
        require(original['proofs_digest']==intent['proofs_digest'] and digest(expected)==digest(refusal),
                'exact historical proof_expired refusal differs')
    else:
        _outage_history(authority,b,record,retained,value,reader,saved['artifact_created'])
    publication=load('publication-controls')
    facts=_publication_result(publication['document'],b,s,publication,intent['issued'])
    require(digest(publication)==intent['publication_digest'] and facts['controls_digest']==retained['certificate']['controls_digest'],
            'broker negative original publication differs')
    if source is not None: _negative_current(b,record,retained,authority,source,now)
    return dict(request_sent=False,broker_refusal=refusal['code'],document=copy.deepcopy(value))


def _outage_history(authority, binding, record, retained, value, reader, intent_created):
    """Reauthenticate original collection documents, never active collection."""
    from control_rendezvous import _ready_document,_response_document
    from broker_evidence import _artifact_readback
    request,certificate=retained['request'],retained['certificate']
    d=binding['deployment']; s=request['snapshot']; intent=value['intent']; observed=value['observed']
    require(d['state']=='qualification' and d['qualification'] is None and
            certificate['record_digest']==digest(record) and certificate['candidate']==retained['candidate'] and
            certificate['worker']==retained['worker'] and certificate['operation']==binding['fence']['pending'] and
            certificate['sequence']==binding['fence']['sequence'] and certificate['configuration_revision']==binding['configuration_revision'] and
            certificate['deployment_digest']==binding['deployment_digest'] and
            request['qualification']==dict(kind='native-trial-certificate',digest=digest(certificate)) and
            certificate['issued']<=intent['issued']<=observed<certificate['expires'],
            'exact authority-outage historical binding required')
    refusal=value['refusal']; observation=refusal['observation']
    object_fields(observation,('path','status'),'historical outage observation')
    require(refusal['code']=='readback_unavailable' and type(observation['status']) is int and observation['status'] in (502,503,504) and
            observation['path']=='/repos/'+d['policy']['authority_repository']+'/actions/runs/'+str(s['run_id'])+'/artifacts' and
            value['before']==value['after']==s,'exact historical authority readback refusal required')
    collection=value['collection']
    object_fields(collection,('locators','request','controls','proofs'),'historical outage collection')
    locators=collection['locators']; ready=collection['request']
    object_fields(locators,('evidence','proofs','task','qualification'),'historical outage locators')
    require(locators['task']==request['task']==dict(task_id=retained['candidate']['submitted']['task_id'],locator=retained['worker']['locator']) and
            locators['qualification']==request['qualification'] and digest(locators['proofs'])==digest(intent['proofs']),
            'historical outage preload inputs differ')
    matches=reader._matches('control-ready')
    require(len(matches)==1,'exact original Session readiness required')
    ready_locator=reader._locator('control-ready',matches[0])
    archived,created=reader._archive(ready_locator)
    require(archived==ready,'historical Session readiness differs')
    _ready_document(ready,binding,value['job_id'],observed)
    require(intent_created<=ready['issued']<=created<=observed,'historical readiness interval differs')
    original=broker_proofs._read_bound(authority,binding,record['pair']['identities'],s,intent['proofs'],intent['issued'])
    require(original['proofs_digest']==intent['proofs_digest'],'historical original purpose proofs differ')
    broker_proofs._read_bound(authority,binding,record['pair']['identities'],s,intent['proofs'],ready['issued'])
    evidence_locator=locators['evidence']
    require(evidence_locator['run_id']==s['run_id'] and evidence_locator['attempt']==s['run_attempt'],
            'historical outage verifier belongs to another attempt')
    evidence=provenance.authenticated_document(authority,d,evidence_locator,'evidence',s['pr'],observed)
    for event in (intent['issued'],observed):
        provenance.validate_evidence(evidence['document'],d,s,binding['configuration_revision'],evidence['job_id'],event)
    controls=provenance.authenticated_document(authority,d,collection['controls'],'controls',s['pr'],observed)
    response=_response_document(controls['document'],ready,binding,controls,observed)
    require(response['result']['controls_digest']==certificate['controls_digest'],'historical outage controls differ from certificate')
    final=broker_proofs._read_bound(authority,binding,record['pair']['identities'],s,collection['proofs'],observed,request=ready)
    # This is the original worker artifact, not a task artifact fabricated for the
    # native case. Its immutable receipt/provenance must still match the record.
    worker=provenance.authenticated_document(authority,record['trial']['deployment'],retained['worker']['locator'],
                                              'trial-task',record['task_id'],observed)
    task=dict(task_id=record['task_id'],run_id=record['execution']['handshake']['run_id'],attempt=1,
              deadline=min(record['expires'],record['execution']['credential']['expires']),purpose='qualification')
    worker_request=dict(schema_version=2,task=task,prompt=retained['prompt'],source_base=record['pair']['fixture_revision'],
                        configuration_revision=record['trial']['configuration_revision'],deployment_digest=record['trial']['deployment_digest'])
    receipt=worker['document']; worker_deployment=record['trial']['deployment']
    object_fields(receipt,('schema_version kind admission_digest request_digest execution submitted protocol isolation relay '
        'controls_digest cleanup_complete completed hosted_qualified enforcement_active').split(),'historical original worker receipt')
    require(type(receipt['schema_version']) is int and receipt['schema_version']==2 and receipt['kind']=='trial-task' and
            receipt['request_digest']==digest(worker_request) and receipt['execution']=={k:worker[k] for k in ('run_id','attempt','job_id')} and
            receipt['cleanup_complete'] is True and receipt['hosted_qualified'] is False and receipt['enforcement_active'] is False and
            positive(receipt['completed']) and worker['job_started']<=receipt['completed']<=worker['artifact_created']<=worker['job_completed'],
            'historical original worker completion differs')
    submitted=receipt['submitted']
    require(submitted['task_id']==task['task_id'] and submitted['run_id']==task['run_id'] and submitted['attempt']==1 and
            submitted['configuration_revision']==worker_request['configuration_revision'] and
            submitted['deployment_digest']==worker_request['deployment_digest'] and submitted['app_id']==worker_deployment['apps']['coding'] and
            submitted['bot_id']==int(worker_deployment['resources']['coding_bot_id']) and submitted['branch']=='agentic/task-'+task['task_id'] and
            sha(submitted['head']) and sha(submitted['tree']) and
            positive(submitted['pr']), 'historical original worker submission differs')
    require(retained['worker']==dict(state='trial-complete',locator=retained['worker']['locator'],
                                    submitted=worker['document']['submitted'],hosted_qualified=False,enforcement_active=False) and
            worker['run_id']==record['execution']['handshake']['run_id'] and worker['attempt']==1,
            'historical outage worker differs')
    references=[evidence,worker,*original['provenance'].values(),*final['provenance'].values(),controls]
    _artifact_readback(authority,d,references)


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
