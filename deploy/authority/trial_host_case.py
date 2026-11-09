"""Held first native host-negative, sharing the complete-prefix host probe.

Only the coding producer sends the host request. Its create-only intent prevents
replay after an unknown effect. The broker consumes a CLOSED successful outcome;
it does not enter merge dispatch or pretend the host denial is a broker failure.
"""
import copy
from urllib.parse import quote

import provenance
from qualification_cases import HostCases
from trusted_ci_policy import digest, object_fields, positive, require


def selected(admission):
    from trial_controller import authenticated
    authenticated(admission)
    return admission.candidate['name'] in ('direct-push','coding-update')


def _context(admission):
    require(selected(admission), 'only the prepared native protected-update cases are implemented')
    admission.guard()
    b, s = admission.binding, admission.request['snapshot']
    return b, s, b['deployment']


def _case(admission, authority):
    import service
    b, s, d = _context(admission)
    location = service._locator(authority,d,s['run_id'],s['run_attempt'],'evidence',s['pr'])
    proof = provenance.authenticated_document(authority,d,location,'evidence',s['pr'],admission.clock())
    task = admission.request['task']
    task = admission.task(b,s,task['locator'],task['task_id'])
    identities = admission.record['pair']['identities']
    coordinates = dict(configuration_revision=b['configuration_revision'],operation=b['fence']['pending'],
        sequence=b['fence']['sequence'],issuer_installation_id=identities['apps']['issuer']['installation_id'],
        evidence_job_id=proof['job_id'],evidence_digest=digest(proof['document']),task_digest=task['task_digest'])
    return dict(name=admission.candidate['name'],snapshot=s,evidence=location,coordinates=coordinates,
                expected_failure=None,mutations=[],prior=None)


def _identity(admission):
    b, s, _ = _context(admission)
    return dict(schema_version=1,kind='trial-host-denial',case=admission.candidate['name'],
        operation_id=admission.request['operation_id'],sequence=b['fence']['sequence'],
        operation_digest=digest(b['fence']['pending']),configuration_revision=b['configuration_revision'],
        deployment_digest=b['deployment_digest'],certificate_digest=digest(admission.value['certificate']),
        snapshot=s)


def _request(d, s):
    return dict(path='/repos/'+d['policy']['repository']+'/git/refs/heads/'+quote(d['policy']['target'],safe=''),
                method='PATCH',data=dict(sha=s['merge'],force=False))


def produce(admission, authority, coding, token_factory, environment, uploader):
    from service import _upload_document
    b, s, d = _context(admission)
    job = provenance.admit_job(authority,d,environment,'trial host denial',admission.clock())
    case = _case(admission,authority)
    identities = admission.record['pair']['identities']
    probe = HostCases(admission.registry,admission.source,authority,identities,coding,None,None,
                      admission.clock,token_factory,guard=admission.guard)
    probe.binding, probe.d = copy.deepcopy(b), d
    identity = _identity(admission)
    root = '/repos/'+d['policy']['authority_repository']+'/actions/runs/'+str(s['run_id'])
    prefix = 'trial-host-intent-'+admission.record['task_id']+'-'+str(s['run_attempt'])
    intent = dict(identity,kind='trial-host-intent',job_id=job['id'],request=_request(d,s),issued=admission.clock())
    def retain(request):
        admission.guard()
        require(request==intent['request'] and not any(v['name']==prefix for v in authority.pages(root+'/artifacts','artifacts')),
                'host intent already exists; never replay an uncertain request')
        _upload_document(uploader,prefix,intent)  # Create-only acknowledgement before the host effect.
        admission.guard()
    record, observation = probe._probe(case,dict(coding=identities['apps']['coding']['actor_id']),before_send=retain)
    admission.guard()
    document = dict(identity,job_id=job['id'],intent=intent,record=record,observation=observation,completed=admission.clock())
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
    object_fields(value,(*identity,'job_id','intent','record','observation','completed'),'trial host outcome')
    require(all(value[k]==v for k,v in identity.items()) and value['job_id']==proof['job_id'] and
            positive(value['completed']) and proof['job_started']<=value['completed']<=proof['artifact_created']<=proof['job_completed'],
            'host outcome configuration or producer interval differs')
    intent_location = service._locator(authority,d,s['run_id'],s['run_attempt'],'trial-host-intent',key)
    intent = provenance.authenticated_document(authority,d,intent_location,'trial-host-intent',key,admission.clock())
    expected = dict(identity,kind='trial-host-intent',job_id=proof['job_id'],request=_request(d,s),issued=value['intent'].get('issued'))
    require(intent['document']==value['intent']==expected and intent['job_id']==proof['job_id'] and
            positive(expected['issued']) and proof['job_started']<=expected['issued']<=intent['artifact_created']<=value['completed'],
            'host intent differs or postdates the attempt')
    observation, record = value['observation'], value['record']
    object_fields(observation,('snapshot checks acceptance rules reviews synthetic_commit request actor_id before after '
                              'http_status denial_category denied_obligation').split(),'host observation')
    actor = admission.record['pair']['identities']['apps']['coding']['actor_id']
    commit = observation['synthetic_commit']
    require(observation['snapshot']==s and observation['request']==_request(d,s) and observation['actor_id']==actor and
            observation['before']==observation['after']==s['base'] and type(observation['http_status']) is int and
            observation['http_status'] in (403,405,422) and observation['denial_category']=='protected_update' and
            observation['denied_obligation'] is None and commit['sha']==s['merge'] and
            [v['sha'] for v in commit['parents']]==[s['base'],s['head']] and
            commit['tree']['sha']==admission.candidate['submitted']['tree'], 'intended host denial was not established')
    expected_record = dict(name=admission.candidate['name'],pr=s['pr'],head=s['head'],base=s['base'],merge=s['merge'],
        tree=commit['tree']['sha'],before=s['base'],after=s['base'],actor_id=actor,request_sent=True,
        http_status=observation['http_status'],denial_category='protected_update',denied_obligation=None,broker_refusal=None,
        merge_commit=None,merge_parents=[],merge_tree=None,evidence_digest=digest(observation))
    require(record==expected_record, 'host denial record differs')
    # Reauthenticate actual verifier/issuer success, obligations, external human
    # review and unchanged candidate. No persisted observation grants freshness.
    probe = HostCases(admission.registry,admission.source,authority,admission.record['pair']['identities'],None,None,None,admission.clock)
    probe.binding, probe.d = b,d
    current = probe._prerequisites(_case(admission,authority))
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
