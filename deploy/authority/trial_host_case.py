"""Held native host-negatives, sharing the complete-prefix host probe.

Only the selected App producer sends the host request. Its create-only intent prevents
replay after an unknown effect. The broker consumes a CLOSED successful outcome;
it does not enter merge dispatch or pretend the host denial is a broker failure.
"""
import copy
import hashlib
import time
from urllib.parse import quote

import provenance
from qualification_cases import HostCases, negative_evidence, STALE
from trusted_ci_policy import Refusal, digest, object_fields, positive, require


def selected(admission):
    from trial_controller import authenticated
    authenticated(admission)
    from trial_transition import historical
    return not historical(admission.candidate) and admission.candidate['name'] in ('direct-push','coding-update','missing-approval','bad-acceptance','replaced-checks','forged-records','spoofed-source','human-update',*STALE)


def failed_evidence(admission, document, job_id):
    b,s,d=_context(admission)
    require(admission.candidate['name'] in ('bad-acceptance','replaced-checks','forged-records'),'only the admitted verifier negative may retain failed evidence')
    return negative_evidence(document,d,s,b['configuration_revision'],job_id,d['policy']['checks'][0])


def guard(admission):
    from authority_github import Readers,current_snapshot
    b,s,d=_context(admission)
    require(current_snapshot(Readers(admission.source,admission.registry.api,d),d,s['pr'],s['run_id'],s['run_attempt'])==s and
            admission.source.get('/repos/'+d['policy']['repository']+'/git/ref/heads/'+quote(d['policy']['target'],safe=''))['object']['sha']==s['base'],
            'host target or candidate moved before terminal effect')


def _context(admission):
    require(selected(admission), 'only the prepared native host cases are implemented')
    admission.guard()
    b, s = admission.binding, admission.request['snapshot']
    return b, s, b['deployment']


def _case(admission, authority):
    import service
    b, s, d = _context(admission)
    task = admission.request['task']
    task = admission.task(b,s,task['locator'],task['task_id'])
    if admission.candidate['name'] in ('spoofed-source',*STALE):
        # The distinguishing prerequisite is a foreign source check, not a
        # verifier mutation or successful authoritative acceptance.
        from trial_transition import acceptance
        return dict(name=admission.candidate['name'],snapshot=s,evidence=None,coordinates=dict(task_digest=task['task_digest']),
                    expected_failure=None,mutations=[],prior=acceptance(admission,authority) if admission.candidate['name'] in STALE else None)
    location = service._locator(authority,d,s['run_id'],s['run_attempt'],'evidence',s['pr'])
    proof = provenance.authenticated_document(authority,d,location,'evidence',s['pr'],admission.clock())
    identities = admission.record['pair']['identities']
    coordinates = dict(configuration_revision=b['configuration_revision'],operation=b['fence']['pending'],
        sequence=b['fence']['sequence'],issuer_installation_id=identities['apps']['issuer']['installation_id'],
        evidence_job_id=proof['job_id'],evidence_digest=digest(proof['document']),task_digest=task['task_digest'])
    negative=admission.candidate['name'] in ('bad-acceptance','replaced-checks','forged-records')
    mutations=[]
    if negative:
        import submission
        failed_evidence(admission,proof['document'],proof['job_id'])
        baseline=submission._read_tree(admission.source,'/repos/'+d['policy']['repository'],
            admission.source.get('/repos/'+d['policy']['repository']+'/git/commits/'+s['base'])['tree']['sha'],admission.guard)
        mutations=[dict(path=path,sha256=hashlib.sha256(item['content']).hexdigest())
                   for path,item in sorted(admission.worker['files'].items())
                   if path not in baseline or item['content']!=baseline[path]['content']]
        require(mutations,'actual exported mutation required for bad acceptance')
    return dict(name=admission.candidate['name'],snapshot=s,evidence=location,coordinates=coordinates,
                expected_failure=d['policy']['checks'][0] if negative else None,mutations=mutations,prior=None)


def _identity(admission):
    b, s, _ = _context(admission)
    return dict(schema_version=1,kind='trial-host-denial',case=admission.candidate['name'],
        operation_id=admission.request['operation_id'],sequence=b['fence']['sequence'],
        operation_digest=digest(b['fence']['pending']),configuration_revision=b['configuration_revision'],
        deployment_digest=b['deployment_digest'],certificate_digest=digest(admission.value['certificate']),
        snapshot=s)


def _request(d, s, name):
    if name in ('missing-approval','bad-acceptance','replaced-checks','forged-records','spoofed-source',*STALE):
        return dict(path='/repos/'+d['policy']['repository']+'/pulls/'+str(s['pr'])+'/merge',
                    method='PUT',data=dict(sha=s['head'],merge_method='merge'))
    return dict(path='/repos/'+d['policy']['repository']+'/git/refs/heads/'+quote(d['policy']['target'],safe=''),
                method='PATCH',data=dict(sha=s['merge'],force=False))


def _publication_inputs(admission, authority):
    """All non-acceptance prerequisites, using the existing publication readers."""
    import service
    import broker_proofs
    b,s,d=_context(admission)
    spoof=admission.candidate['name'] in ('spoofed-source',*STALE)
    require(spoof or admission.candidate['name'] in ('bad-acceptance','replaced-checks','forged-records'),'only admitted publication cases are implemented')
    case=_case(admission,authority)
    probe=HostCases(admission.registry,admission.source,authority,admission.record['pair']['identities'],None,None,None,admission.clock)
    probe.binding,probe.d=b,d
    observation=probe._prerequisites(case)
    locators=(dict(proofs={p:service._locator(authority,d,s['run_id'],s['run_attempt'],'proof',p)
                          for p in ('admin','reader','issuer','coding','merge')},qualification=admission.request['qualification'])
              if spoof else service._publication_locators(authority,b,admission.request))
    proofs=broker_proofs._read(authority,b,admission.record['pair']['identities'],s,locators['proofs'],admission.clock(),admission=admission)
    location=service._locator(authority,d,s['run_id'],s['run_attempt'],'publication-controls',s['pr'])
    controls=provenance.authenticated_document(authority,d,location,'publication-controls',s['pr'],admission.clock())
    facts=service._bound_validate_publication_observation(controls['document'],b,s,controls,admission.clock(),admission)
    require(locators['qualification']==admission.request['qualification'],'exact trial certificate required')
    admission.qualification(b,facts['controls_digest'])
    guard(admission)
    inputs=dict(proofs=locators['proofs'],proofs_digest=proofs['proofs_digest'],
        controls=location,controls_digest=digest(controls['document']),task_digest=case['coordinates']['task_digest'])
    if spoof:
        inputs['source']=observation
    else:
        inputs.update(evidence=case['evidence'],evidence_digest=case['coordinates']['evidence_digest'])
    return inputs


def publish(admission, authority, job, uploader, source):
    """Retain a named observation or the strict issuer's actual acceptance refusal."""
    from service import _upload_document, _publish_bound
    b,s,d=_context(admission)
    inputs=_publication_inputs(admission,authority)
    root='/repos/'+d['policy']['authority_repository']+'/actions/runs/'+str(s['run_id'])
    prefix='trial-publication-intent-'+str(s['pr'])+'-'+str(s['run_attempt'])
    require(not any(v['name']==prefix for v in authority.pages(root+'/artifacts','artifacts')),
            'publication intent already exists; never replay an uncertain publication')
    intent=dict(_identity(admission),kind='trial-publication-intent',job_id=job['id'],inputs=inputs,issued=admission.clock())
    guard(admission)
    _upload_document(uploader,prefix,intent)
    require(_publication_inputs(admission,authority)==inputs,'publication inputs changed after intent')
    if admission.candidate['name'] in ('spoofed-source',*STALE):
        # This selected attack observes the foreign source check. Publishing the
        # genuine issuer success would invalidate its distinguishing prerequisite.
        observed=admission.clock()
        guard(admission)
        value=dict(_identity(admission),kind='trial-publication-observation',job_id=job['id'],intent=intent,
            observation=inputs['source'],observed=observed,completed=admission.clock())
        return _upload_document(uploader,'trial-publication-observation-'+str(s['pr'])+'-'+str(s['run_attempt']),value)
    # The unchanged success-only issuer validates evidence before any publication.
    # Only its exact acceptance diagnostic can establish this named negative.
    expected='critical acceptance failed: '+d['policy']['checks'][0]
    try:
        _publish_bound(source,authority,admission.registry,b,admission.record['pair']['identities'],
                       admission.request,admission.clock,admission.guard,admission)
    except Refusal as error:
        observed=admission.clock()
        require(str(error)==expected,'issuer did not refuse the intended failed acceptance')
    else:
        raise Refusal('bad acceptance unexpectedly published; never count or replay it')
    require(_publication_inputs(admission,authority)==inputs,'publication inputs changed during refusal')
    guard(admission)
    value=dict(_identity(admission),kind='trial-publication-denial',job_id=job['id'],intent=intent,
        refusal=expected,observed=observed,completed=admission.clock())
    return _upload_document(uploader,'trial-publication-denial-'+str(s['pr'])+'-'+str(s['run_attempt']),value)


def read_publication(admission, authority):
    import service
    b,s,d=_context(admission)
    spoof=admission.candidate['name'] in ('spoofed-source',*STALE)
    role='trial-publication-observation' if spoof else 'trial-publication-denial'
    location=service._locator(authority,d,s['run_id'],s['run_attempt'],role,s['pr'])
    proof=provenance.authenticated_document(authority,d,location,role,s['pr'],admission.clock())
    value=proof['document']
    identity=dict(_identity(admission),kind=role)
    object_fields(value,(*identity,'job_id','intent','observation' if spoof else 'refusal','observed','completed'),'publication outcome')
    require(digest({k:value[k] for k in identity})==digest(identity) and positive(value['job_id']) and value['job_id']==proof['job_id'] and
            all(positive(value[k]) for k in ('observed','completed')) and
            proof['job_started']<=value['observed']<=value['completed']<=proof['artifact_created']<=proof['job_completed'],
            'publication outcome identity or interval differs')
    inputs=_publication_inputs(admission,authority)
    require(digest(value['observation'])==digest(inputs['source']) if spoof else
            value['refusal']=='critical acceptance failed: '+d['policy']['checks'][0], 'named publication outcome differs')
    loc=service._locator(authority,d,s['run_id'],s['run_attempt'],'trial-publication-intent',s['pr'])
    intent=provenance.authenticated_document(authority,d,loc,'trial-publication-intent',s['pr'],admission.clock())
    expected=dict(_identity(admission),kind='trial-publication-intent',job_id=proof['job_id'],
        inputs=inputs,issued=value['intent'].get('issued'))
    require(digest(intent['document'])==digest(value['intent'])==digest(expected) and intent['job_id']==proof['job_id'] and
            positive(expected['issued']) and proof['job_started']<=expected['issued']<=intent['artifact_created']<=value['observed'],
            'issuer refusal intent or inputs differ')
    guard(admission)
    return dict(locator=location,digest=digest(value))


def produce(admission, authority, app, token_factory, environment, uploader, sleeper=time.sleep):
    from service import _upload_document
    b, s, d = _context(admission)
    job = provenance.admit_job(authority,d,environment,'trial host denial',admission.clock())
    if admission.candidate['name']=='human-update':
        return consume_human(admission,authority,job,uploader,sleeper)
    case = _case(admission,authority)
    identities = admission.record['pair']['identities']
    merger=admission.candidate['name'] in ('missing-approval','bad-acceptance','replaced-checks','forged-records','spoofed-source',*STALE)
    purpose='merge' if merger else 'coding'
    publication=read_publication(admission,authority) if case['name'] in ('bad-acceptance','replaced-checks','forged-records','spoofed-source',*STALE) else None
    probe = HostCases(admission.registry,admission.source,authority,identities,None if merger else app,app if merger else None,None,
                      admission.clock,token_factory,guard=admission.guard)
    probe.binding, probe.d = copy.deepcopy(b), d
    identity = _identity(admission)
    root = '/repos/'+d['policy']['authority_repository']+'/actions/runs/'+str(s['run_id'])
    prefix = 'trial-host-intent-'+admission.record['task_id']+'-'+str(s['run_attempt'])
    intent = dict(identity,kind='trial-host-intent',job_id=job['id'],request=_request(d,s,case['name']),issued=admission.clock())
    def retain(request):
        admission.guard()
        require(request==intent['request'] and not any(v['name']==prefix for v in authority.pages(root+'/artifacts','artifacts')),
                'host intent already exists; never replay an uncertain request')
        _upload_document(uploader,prefix,intent)  # Create-only acknowledgement before the host effect.
        admission.guard()
    record, observation = probe._probe(case,{purpose:identities['apps'][purpose]['actor_id']},before_send=retain)
    if publication is not None:
        observation['publication']=publication
        record['evidence_digest']=digest(observation)
    admission.guard()
    document = dict(identity,job_id=job['id'],intent=intent,record=record,observation=observation,completed=admission.clock())
    return _upload_document(uploader,'trial-host-denial-'+admission.record['task_id']+'-'+str(s['run_attempt']),document)


def native_human(admission, human):
    """The native human sends the request; Actions later consumes this claim."""
    from trial_controller import Admission, case_journal
    from trial_case import read as read_case
    from trial_transition import _publish_native
    require(type(admission) is Admission and admission.candidate['name']=='human-update', 'actual native human case owner required')
    b,s,d=_context(admission); c=admission.native.provision
    journal=c.store(c.root/'trial-native-human')
    require(journal.read() is None,'native human attempt already retained; never replay')
    publication=c.store(c.root/case_journal('trial-case-publication',admission.candidate)).read()
    require(publication is not None and publication['value']['phase']=='bound','owned exact human execution publication required')
    revision=publication['value']['revision_bound']
    value,record=read_case(c.session.registry,revision,admission.clock)
    require(record==admission.record and value['request']==admission.request and value['candidate']==admission.candidate and
            value['execution'] is not None,'native human substituted current execution')
    identity=human.get('/user')
    require(positive(identity.get('id')) and identity.get('type')=='User' and identity['id'] in d['policy']['reviewers'] and
            identity['id'] not in [v['actor_id'] for v in record['pair']['identities']['apps'].values()],
            'independently supplied human identity differs')
    job=provenance.execution_job(admission.registry.api,d,s['run_id'],s['run_attempt'],'trial host denial')
    require(job.get('status') in ('queued','in_progress'),'native human requires its exact pending consumer job')
    binding=dict(schema_version=1,task_id=record['task_id'],execution=None,record_digest=digest(record),name='human-update',
        case_revision=revision,case_digest=digest(value),request_digest=digest(admission.request),
        certificate_digest=digest(admission.value['certificate']),snapshot=s,identity=identity,consumer_job_id=job['id'],
        token_digest=value['execution']['credential']['token_digest'],expires=min(record['expires'],value['certificate']['expires'],
            value['execution']['credential']['expires']))
    document=None; intent=None
    def owner_guard():
        require(journal.read()==document,'native human intent ownership changed')
        admission.guard()
        if intent is not None:
            from trial_transition import read_native
            require(digest(read_native(c.session.registry,intent,record))==digest(document['value']['claim']),
                    'native human intent publication moved')
        current_job=provenance.execution_job(admission.registry.api,d,s['run_id'],s['run_attempt'],'trial host denial')
        require(current_job['id']==job['id'] and current_job.get('status') in ('queued','in_progress'),
                'native human consumer was replaced or cancelled')
        require(journal.read()==document,'native human ownership changed during admission')
    probe=HostCases(admission.registry,admission.source,admission.registry.api,record['pair']['identities'],None,None,human,
                    admission.clock,guard=owner_guard)
    probe.binding,probe.d=b,d
    def retain(request):
        nonlocal document,intent
        admission.guard()
        claim=dict(binding,kind='native-trial-human-intent',request=request,issued=admission.clock())
        document=journal.write(None,dict(phase='intent-started',claim=claim,intent=None,result=None,completion=None))
        intent=_publish_native(c,record,claim,owner_guard)
        document=journal.write(document,dict(document['value'],phase='intent-published',intent=intent))
        admission.guard()
    result,observation=probe._probe(_case(admission,admission.registry.api),dict(human=identity['id']),identity,before_send=retain)
    owner_guard()
    claim=dict(binding,kind='native-trial-human-result',intent=intent,record=result,observation=observation,completed=admission.clock())
    document=journal.write(document,dict(document['value'],phase='result-started',result=claim))
    completion=_publish_native(c,record,claim,owner_guard)
    journal.write(document,dict(document['value'],phase='complete',completion=completion))
    return completion


def read_human(admission, authority, job_id):
    """Authenticate native provenance; do not relabel it as a job-sent request."""
    from trial_transition import read_native
    from registry import trial_reference
    from trial_case import read as read_case
    b,s,d=_context(admission)
    require(admission.candidate['name']=='human-update','fixed native human consumer required')
    original=admission.original if hasattr(admission,'original') else admission.native.provision.session.registry
    links={kind:dict(kind=kind,revision=original.ref(trial_reference(dict(kind=kind,name='human-update',
           task_id=admission.record['task_id'],execution=None)))) for kind in ('native-trial-human-intent','native-trial-human-result')}
    intent=read_native(original,links['native-trial-human-intent'],admission.record)
    result=read_native(original,links['native-trial-human-result'],admission.record)
    fields=('schema_version task_id execution record_digest name case_revision case_digest request_digest certificate_digest '
            'snapshot identity consumer_job_id token_digest expires').split()
    object_fields(intent,fields+['kind','request','issued'],'native human intent')
    object_fields(result,fields+['kind','intent','record','observation','completed'],'native human result')
    value,record=read_case(original,result['case_revision'],admission.clock)
    identity=result['identity']; credential=value['execution']['credential']
    require(digest({k:intent[k] for k in fields})==digest({k:result[k] for k in fields}) and
            type(result['schema_version']) is int and result['schema_version']==1 and result['name']=='human-update' and
            result['intent']==links['native-trial-human-intent'] and result['case_digest']==digest(value) and
            record==admission.record and value['request']==admission.request and value['candidate']==admission.candidate and
            result['request_digest']==digest(admission.request) and result['certificate_digest']==digest(admission.value['certificate']) and
            digest(result['snapshot'])==digest(s) and positive(result['consumer_job_id']) and result['consumer_job_id']==job_id and
            result['token_digest']==credential['token_digest'] and positive(result['expires']) and
            result['expires']==min(record['expires'],value['certificate']['expires'],credential['expires']) and
            positive(intent['issued']) and positive(result['completed']) and
            b['fence']['pending']['created']<=intent['issued']<=result['completed']<=admission.clock()<result['expires'] and
            positive(identity.get('id')) and identity.get('type')=='User' and identity['id'] in d['policy']['reviewers'] and
            identity['id'] not in [v['actor_id'] for v in record['pair']['identities']['apps'].values()] and
            digest(intent['request'])==digest(_request(d,s,'human-update')), 'native human observation binding differs')
    observation=result['observation']; host=result['record']
    require(observation['actor_id']==identity['id'] and type(observation['http_status']) is int and
            observation['http_status'] in (403,422) and observation['denial_category']=='protected_update' and
            observation['denied_obligation'] is None and observation['before']==observation['after']==s['base'] and
            digest(observation['snapshot'])==digest(s) and digest(observation['request'])==digest(intent['request']) and
            host['evidence_digest']==digest(observation), 'native human did not establish exact protected denial')
    probe=HostCases(admission.registry,admission.source,authority,record['pair']['identities'],None,None,None,admission.clock)
    probe.binding,probe.d=b,d
    current=probe._prerequisites(_case(admission,authority))
    a,now=observation['acceptance'],current['acceptance']
    require(digest(a['proof'])==digest(now['proof']) and digest(a['coordinates'])==digest(now['coordinates']) and
            all(a['check'][k]==now['check'][k] for k in ('check_id','external_id','expires')) and
            all(digest(observation[k])==digest(current[k]) for k in ('checks','rules','reviews')), 'native human prerequisites changed')
    admission.local_guard()
    old=getattr(admission,'_human_links',None)
    require(old is None or digest(old)==digest(links),'authenticated native human publications changed')
    if old is None:
        admission._human_links=copy.deepcopy(links)
        if hasattr(admission,'_seal'): admission._seal=copy.deepcopy(admission._state())
    guard(admission)
    return dict(intent=links['native-trial-human-intent'],result=links['native-trial-human-result'],
                intent_document=intent,result_document=result)


def consume_human(admission, authority, job, uploader, sleeper=time.sleep):
    from service import _upload_document
    from registry import trial_reference
    b,s,d=_context(admission)
    original=admission.original if hasattr(admission,'original') else admission.native.provision.session.registry
    expires=min(admission.record['expires'],admission.value['certificate']['expires'],b['fence']['pending']['execution_deadline'])
    if hasattr(admission,'case'): expires=min(expires,admission.case['execution']['credential']['expires'])
    deadline=time.monotonic()+max(0,expires-admission.clock())
    while True:
        require(admission.clock()<expires and time.monotonic()<deadline,'native human observation deadline expired')
        admission.guard(); guard(admission)
        current=provenance.execution_job(authority,d,s['run_id'],s['run_attempt'],'trial host denial')
        require(current['id']==job['id'] and current.get('status')=='in_progress','human consumer replaced or cancelled')
        ready=True
        for kind in ('native-trial-human-intent','native-trial-human-result'):
            try: original.ref(trial_reference(dict(kind=kind,name='human-update',task_id=admission.record['task_id'],execution=None)))
            except __import__('trusted_ci_github').HostRefusal as error:
                require(error.status==404,'native human observation unavailable')
                ready=False
        admission.guard(); guard(admission)
        if ready: break
        sleeper(min(0.25,max(0,expires-admission.clock())))
    claim=read_human(admission,authority,job['id'])
    b,s,d=_context(admission); identity=_identity(admission)
    root='/repos/'+d['policy']['authority_repository']+'/actions/runs/'+str(s['run_id'])
    prefix='trial-host-intent-'+admission.record['task_id']+'-'+str(s['run_attempt'])
    require(not any(v['name']==prefix for v in authority.pages(root+'/artifacts','artifacts')),
            'native human consumer intent exists; never replay publication')
    intent=dict(identity,kind='trial-host-intent',job_id=job['id'],request=_request(d,s,'human-update'),
                issued=admission.clock(),origin='native-human-observation',native=claim)
    admission.guard(); guard(admission)
    _upload_document(uploader,prefix,intent)
    require(digest(read_human(admission,authority,job['id']))==digest(claim),'native human claim moved during consumption')
    document=dict(identity,job_id=job['id'],intent=intent,record=claim['result_document']['record'],
        observation=claim['result_document']['observation'],origin='native-human-observation',native=claim,completed=admission.clock())
    admission.guard(); guard(admission)
    return _upload_document(uploader,'trial-host-denial-'+admission.record['task_id']+'-'+str(s['run_attempt']),document)


def read(admission, authority, locator=None):
    """Authenticate closed source, job interval, intent and exact denial outcome."""
    import service
    b, s, d = _context(admission)
    key = admission.record['task_id']
    if locator is None:
        locator = service._locator(authority,d,s['run_id'],s['run_attempt'],'trial-host-denial',key)
    require(locator['run_id']==s['run_id'] and locator['attempt']==s['run_attempt'], 'host outcome belongs to another run')
    proof = provenance.authenticated_document(authority,d,locator,'trial-host-denial',key,admission.clock())
    value = proof['document']
    identity = _identity(admission)
    human=admission.candidate['name']=='human-update'
    object_fields(value,(*identity,'job_id','intent','record','observation','completed',*(('origin','native') if human else ())), 'trial host outcome')
    require(digest({k:value[k] for k in identity})==digest(identity) and positive(value['job_id']) and value['job_id']==proof['job_id'] and
            positive(value['completed']) and proof['job_started']<=value['completed']<=proof['artifact_created']<=proof['job_completed'],
            'host outcome configuration or producer interval differs')
    intent_location = service._locator(authority,d,s['run_id'],s['run_attempt'],'trial-host-intent',key)
    intent = provenance.authenticated_document(authority,d,intent_location,'trial-host-intent',key,admission.clock())
    expected = dict(identity,kind='trial-host-intent',job_id=proof['job_id'],request=_request(d,s,admission.candidate['name']),issued=value['intent'].get('issued'))
    native=read_human(admission,authority,proof['job_id']) if human else None
    if human:
        require(value['origin']=='native-human-observation' and digest(value['native'])==digest(native) and
                digest(value['record'])==digest(native['result_document']['record']) and
                digest(value['observation'])==digest(native['result_document']['observation']), 'native human consumer provenance differs')
        expected.update(origin='native-human-observation',native=native)
        require(native['result_document']['completed']<=expected['issued'],'human consumption predates native completion')
    require(digest(intent['document'])==digest(value['intent'])==digest(expected) and intent['job_id']==proof['job_id'] and
            positive(expected['issued']) and proof['job_started']<=expected['issued']<=intent['artifact_created']<=value['completed'],
            'host intent differs or postdates the attempt')
    observation, record = value['observation'], value['record']
    negative=admission.candidate['name'] in ('bad-acceptance','replaced-checks','forged-records')
    stale=admission.candidate['name'] in STALE
    spoof=admission.candidate['name'] in ('spoofed-source',*STALE)
    fields=('snapshot checks rules reviews synthetic_commit request actor_id before after '
            'http_status denial_category denied_obligation').split()
    object_fields(observation,fields+(['negative','mutations','publication'] if negative else ['publication','prior'] if stale else ['publication'] if spoof else ['acceptance']),'host observation')
    missing=admission.candidate['name']=='missing-approval'
    category='required_check' if negative or spoof else 'required_review' if missing else 'protected_update'
    obligation=d['policy']['check_name'] if negative or spoof else None
    if missing:
        require(not any(r['state']=='APPROVED' and r['commit_id']==s['head'] for r in observation['reviews']),
                'missing-approval observation has candidate approval')
    actor = (native['result_document']['identity']['id'] if human else
             admission.record['pair']['identities']['apps']['merge' if missing or negative or spoof else 'coding']['actor_id'])
    commit = observation['synthetic_commit']
    require(digest(observation['snapshot'])==digest(s) and digest(observation['request'])==digest(_request(d,s,admission.candidate['name'])) and positive(observation['actor_id']) and observation['actor_id']==actor and
            observation['before']==observation['after']==s['base'] and type(observation['http_status']) is int and
            observation['http_status'] in ((403,422) if human else (403,405,422)) and observation['denial_category']==category and
            observation['denied_obligation']==obligation and commit['sha']==s['merge'] and
            [v['sha'] for v in commit['parents']]==[s['base'],s['head']] and
            commit['tree']['sha']==admission.candidate['submitted']['tree'], 'intended host denial was not established')
    expected_record = dict(name=admission.candidate['name'],pr=s['pr'],head=s['head'],base=s['base'],merge=s['merge'],
        tree=commit['tree']['sha'],before=s['base'],after=s['base'],actor_id=actor,request_sent=True,
        http_status=observation['http_status'],denial_category=category,denied_obligation=obligation,broker_refusal=None,
        merge_commit=None,merge_parents=[],merge_tree=None,evidence_digest=digest(observation))
    require(digest(record)==digest(expected_record), 'host denial record differs')
    # Reauthenticate the selected verifier/issuer outcome, obligations, external
    # human review and unchanged candidate. No observation grants freshness.
    probe = HostCases(admission.registry,admission.source,authority,admission.record['pair']['identities'],None,None,None,admission.clock)
    probe.binding, probe.d = b,d
    current = probe._prerequisites(_case(admission,authority))
    if negative:
        require(observation['negative']==current['negative'] and observation['mutations']==current['mutations'] and
                observation['publication']==read_publication(admission,authority), 'host negative evidence differs')
    elif spoof:
        require(all(digest(observation[k])==digest(current[k]) for k in ('checks','rules','reviews')) and
                digest(observation['publication'])==digest(read_publication(admission,authority)), 'host spoof observation differs')
        if stale: require(digest(observation['prior'])==digest(current['prior']), 'historical acceptance differs')
    else:
        acceptance = observation['acceptance']
        require(acceptance['proof']==current['acceptance']['proof'] and acceptance['coordinates']==current['acceptance']['coordinates'] and
                all(acceptance['check'][k]==current['acceptance']['check'][k] for k in ('check_id','external_id','expires')),
                'host denial acceptance evidence differs')
    from authority_github import Readers,current_snapshot
    require(current_snapshot(Readers(admission.source,authority,d),d,s['pr'],s['run_id'],s['run_attempt'])==s and
            admission.source.get('/repos/'+d['policy']['repository']+'/git/ref/heads/'+quote(d['policy']['target'],safe=''))['object']['sha']==s['base'],
            'host target or candidate changed after denial')
    admission.guard()
    return dict(locator=locator,document=value,proof={k:v for k,v in proof.items() if k!='document'})


def broker(admission, authority, job_id, uploader):
    from merge_receipts import ActionsReceipts
    b, _, _ = _context(admission)
    receipts = ActionsReceipts._create(authority,admission.registry.binding,job_id,admission.clock,uploader=uploader,admission=admission)
    receipts.current_job()
    outcome = read(admission,authority)
    document = dict(schema_version=1,kind='host-denied',operation_id=admission.request['operation_id'],
        sequence=b['fence']['sequence'],job_id=job_id,issued=admission.clock(),
        host=outcome['locator'],host_digest=digest(outcome['document']))
    receipts.append('host-denied',document)
    return dict(state='host-denied',operation_id=document['operation_id'],sequence=document['sequence'],fence_pending=True)


def validate_receipt(value, admission, authority, job_id):
    _context(admission)
    object_fields(value,('schema_version kind operation_id sequence job_id issued host host_digest').split(),'host no-dispatch receipt')
    require(type(value['schema_version']) is int and value['schema_version']==1 and value['kind']=='host-denied' and
            value['operation_id']==admission.request['operation_id'] and type(value['sequence']) is int and
            value['sequence']==admission.request['sequence'] and value['job_id']==job_id and positive(value['issued']) and
            admission.binding['fence']['pending']['created']<=value['issued']<=admission.clock(), 'host receipt operation differs')
    outcome = read(admission,authority,value['host'])
    require(digest(outcome['document'])==value['host_digest'] and outcome['proof']['job_completed']<=value['issued'],
            'host receipt substituted its closed outcome')
    return value
