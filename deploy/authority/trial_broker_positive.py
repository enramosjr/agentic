"""Finite native positive composition. Public release and qualification stay held."""
import copy
from pathlib import Path
import secrets
from urllib.parse import quote

import provenance
from authority_private import Store
from merge_receipts import ActionsReceipts
from merge_window import recover_merged
from trusted_ci_policy import digest, loads, object_fields, positive, require, sha

GRANT = 'native-trial-positive-grant'
JOB = 'native-trial-positive-job'
ROLES = dict(broker='trial-positive-broker-intent',finalize='trial-positive-recovery-intent')


def selected(a):
    return a.candidate['name']=='positive'


def require_broker(a):
    from trial_case import Hosted
    require(type(a) is Hosted and getattr(a,'_positive',None) is not None and a._positive['role']=='broker',
            'original positive broker issuance required')


def deadline(a):
    from trial_broker_context import deadline as original_minimum
    return original_minimum(a)


def original(a):
    return a.original if hasattr(a,'original') else a.native.provision.session.registry


def grant_link(registry, record):
    from registry import trial_reference
    return dict(kind=GRANT,revision=registry.ref(trial_reference(dict(kind=GRANT,name='positive',task_id=record['task_id'],execution=None))))


def case_end(record,case,binding):
    return min(record['expires'],record['origin']['binding']['fence']['pending']['execution_deadline'],
        binding['deployment']['expires'],case['certificate']['expires'],case['pending']['pending']['execution_deadline'],
        case['execution']['credential']['expires'])


def strict_original(registry,record,case,clock):
    """Eligibility proves the new original lineage, never current acceptance."""
    from trial_eligibility import authenticate
    link=case['candidate'].get('eligibility')
    require(link is not None,'positive requires the separate strict original eligibility')
    authenticate(registry,record,case['worker'],link,clock)


def authenticate_grant(registry,record,case,binding,link,clock):
    strict_original(registry,record,case,clock)
    from trial_transition import read_native
    from trial_controller import CASE_CHAIN
    claim=read_native(registry,link,record)
    object_fields(claim,('schema_version kind task_id execution name record_digest case_digest request_digest preview approval').split(),'native positive grant')
    p=claim['preview']
    object_fields(p,('kind record_digest case_digest request_digest worker reservation history binding snapshot tree controls pin run_id attempt roles issued expires nonce').split(),
                  'native positive approval preview')
    require(type(claim['schema_version']) is int and claim['schema_version']==1 and claim['kind']==GRANT and claim['name']=='positive' and
            claim['record_digest']==p['record_digest']==digest(record) and claim['task_id']==record['task_id'] and claim['execution'] is None and
            claim['case_digest']==p['case_digest']==digest(case) and claim['request_digest']==p['request_digest']==digest(case['request']) and
            claim['approval']==digest(p) and p['kind']=='native-positive-preview' and p['worker']==case['worker'] and
            p['reservation']==case['candidate'] and p['history']==case['history'] and len(p['history'])==15 and
            CASE_CHAIN[-1]=='positive' and p['binding']==binding and p['snapshot']==case['request']['snapshot'] and sha(p['tree']) and
            p['run_id']==case['request']['snapshot']['run_id'] and p['attempt']==case['request']['snapshot']['run_attempt']==1 and
            p['roles']==dict(broker='broker ('+str(p['snapshot']['pr'])+')',finalize='finalize') and
            positive(p['issued']) and p['issued']<=clock()<p['expires']==case_end(record,case,binding) and
            isinstance(p['nonce'],str) and len(p['nonce'])==32 and all(c in '0123456789abcdef' for c in p['nonce']),
            'positive grant substituted original case, roles, history or deadline')
    pin=p['pin']; policy=binding['deployment']['policy']
    object_fields(pin,('authority_repository','authority_repository_id','workflow','workflow_sha'),'independent positive recovery pin')
    require(pin['authority_repository']==policy['authority_repository'] and pin['authority_repository_id']==policy['authority_repository_id'] and
            pin['workflow']==policy['workflow'] and pin['workflow_sha']==policy['workflow_sha'], 'independent positive recovery pin differs')
    return claim


def approve_native(a,pin,approve):
    from trial_controller import Admission
    from trial_broker_case import _case_value,_prerequisites,_proofs,_publication
    from trial_transition import _publish_native
    import service
    require(type(a) is Admission and selected(a) and a.value['phase']=='bound' and len(a.value['history'])==15,
            'positive approval requires all fifteen genuine predecessors and a bound original case')
    a.guard(); publication,case=_case_value(a)
    strict_original(original(a),a.record,case,a.clock)
    _prerequisites(a,a.registry.api,live=False)
    _proofs(a,a.registry.api,service._publication_locators(a.registry.api,a.binding,a.request)['proofs'],a.clock())
    _publication(a,a.registry.api,a.clock())
    s=a.request['snapshot']; root='/repos/'+a.binding['deployment']['policy']['repository']
    commit=a.source.get(root+'/git/commits/'+s['merge'])
    require(commit['sha']==s['merge'] and [v['sha'] for v in commit['parents']]==[s['base'],s['head']] and sha(commit['tree']['sha']),
            'positive tested merge identity differs')
    from controls import observe
    from authority_github import Readers
    controls=observe(Readers(a.source,a.registry.api,a.binding['deployment']),a.binding['deployment'])
    require(controls['base']==s['base'] and controls['controls_digest']==a.value['certificate']['controls_digest'],
            'positive approval controls differ from the bound certificate')
    c=a.native.provision; journal=c.store(c.root/'trial-positive-approval'); document=journal.read()
    if document is not None:
        require(document['value']['phase']=='complete', 'positive approval publication remains unknown; no replay')
        link=document['value']['link']
        authenticate_grant(c.session.registry,a.record,case,a.binding,link,a.clock)
        return copy.deepcopy(link)
    preview=dict(kind='native-positive-preview',record_digest=digest(a.record),case_digest=digest(case),request_digest=digest(a.request),
        worker=a.value['worker'],reservation=a.candidate,history=a.value['history'],binding=a.binding,snapshot=s,
        tree=commit['tree']['sha'],controls=controls,pin=copy.deepcopy(pin),run_id=s['run_id'],attempt=1,
        roles=dict(broker='broker ('+str(s['pr'])+')',finalize='finalize'),issued=a.clock(),expires=deadline(a),nonce=secrets.token_hex(16))
    require(callable(approve) and approve(copy.deepcopy(preview))==digest(preview),'exact native positive approval required')
    claim=dict(schema_version=1,kind=GRANT,task_id=a.record['task_id'],execution=None,name='positive',record_digest=digest(a.record),
        case_digest=digest(case),request_digest=digest(a.request),preview=preview,approval=digest(preview))
    policy=a.binding['deployment']['policy']
    require(pin==dict(authority_repository=policy['authority_repository'],authority_repository_id=policy['authority_repository_id'],
                     workflow=policy['workflow'],workflow_sha=policy['workflow_sha']), 'independent original-run finalizer pin required')
    a.guard(); require(a.clock()<preview['expires'],'positive approval expired')
    document=journal.write(None,dict(phase='publication-started',claim=claim,link=None))
    def before():
        a.guard(); require(journal.read()==document and a.clock()<preview['expires'],'positive native approval changed or expired')
    link=_publish_native(c,a.record,claim,before)
    authenticate_grant(c.session.registry,a.record,case,a.binding,link,a.clock)
    journal.write(document,dict(phase='complete',claim=claim,link=link))
    return link


def _case(a):
    if hasattr(a,'case'): return a.case
    from trial_broker_case import _case_value
    return _case_value(a)[1]


def job_link(registry,record,role):
    from registry import trial_reference
    require(role in ROLES,'fixed positive role required')
    return dict(kind=JOB,revision=registry.ref(trial_reference(dict(kind=JOB,name='positive',task_id=record['task_id'],role=role,execution=None))))


def bind_native_job(a,role,temporary):
    """Reserve original native-owned scratch before the producer's first mint.

    Shared protected storage is source-local composition, not hosted transport.
    An erased reservation cannot be recreated by a producer or replacement job.
    """
    from trial_controller import Admission
    from trial_transition import _publish_native,read_native
    require(type(a) is Admission and selected(a) and role in ROLES,'original native positive job binding required')
    a.guard(); case=_case(a); link=grant_link(original(a),a.record)
    grant=authenticate_grant(original(a),a.record,case,a.binding,link,a.clock)
    p=grant['preview']; c=a.native.provision
    journal=c.store(c.root/('trial-positive-job-'+role)); document=journal.read()
    if document is not None:
        require(document['value']['phase']=='complete','positive job binding remains unknown; never rebind')
        return copy.deepcopy(document['value']['link'])
    job=provenance.execution_job(a.registry.api,a.binding['deployment'],p['run_id'],1,p['roles'][role])
    identity=dict(run_id=job['run_id'],attempt=1,job_id=job['id'],workflow_sha=job['head_sha'])
    scratch=Path(temporary)
    require(scratch.is_absolute() and scratch.is_dir(),'existing trusted original-job scratch required')
    scratch=scratch.resolve()
    root=scratch/('agentic-positive-'+digest(dict(grant=link,role=role,operation=a.request['operation_id'])))
    value=dict(phase='reservation-started',grant=link,job=identity,scratch=str(scratch),link=None)
    document=journal.write(None,value)
    from trial_wire import WireJournal
    store=WireJournal(Store(root),'positive-'+role,root); require(store.read() is None,'positive role storage already exists; no adoption')
    reserved=store.write(None,dict(phase='reserved',role=role,grant=link,job=identity,nonce=secrets.token_hex(16)))
    claim=dict(schema_version=1,kind=JOB,task_id=a.record['task_id'],execution=None,name='positive',role=role,
        record_digest=digest(a.record),grant=link,grant_digest=digest(grant),job=identity,scratch=str(scratch),
        reserved=reserved,issued=a.clock(),expires=p['expires'])
    value.update(phase='publication-started',claim=claim,reserved=reserved)
    document=journal.write(document,value)
    def before():
        a.guard(); require(journal.read()==document and store.read()==reserved and a.clock()<p['expires'],
                           'positive original job reservation changed or expired')
    publication=_publish_native(c,a.record,claim,before)
    require(read_native(original(a),publication,a.record)==claim,'positive original job publication differs')
    journal.write(document,dict(value,phase='complete',link=publication))
    return publication


def authenticate_job(registry,record,grant,link,role,clock):
    from trial_transition import read_native
    value=read_native(registry,job_link(registry,record,role),record)
    object_fields(value,('schema_version kind task_id execution name role record_digest grant grant_digest job scratch reserved issued expires').split(),
                  'native positive original job')
    require(type(value['schema_version']) is int and value['schema_version']==1 and value['kind']==JOB and value['name']=='positive' and
            value['role']==role and value['record_digest']==digest(record) and value['grant']==link and value['grant_digest']==digest(grant) and
            value['task_id']==record['task_id'] and value['execution'] is None and
            value['expires']==grant['preview']['expires'] and grant['preview']['issued']<=value['issued']<=clock()<value['expires'] and
            value['job']['run_id']==grant['preview']['run_id'] and value['job']['attempt']==1 and
            value['job']['workflow_sha']==grant['preview']['pin']['workflow_sha'], 'positive original job binding differs')
    return value


def begin(a,api,environment,role,uploader):
    """Seal the unique original job before its first source/proof/admin mint."""
    from broker_finalize import Finalizer
    import service
    require(selected(a) and role in ROLES and a.worker is None,'fresh native positive role admission required')
    case=_case(a); link=grant_link(original(a),a.record)
    claim=authenticate_grant(original(a),a.record,case,a.binding,link,a.clock)
    p=claim['preview']; s=a.request['snapshot']
    bound=authenticate_job(original(a),a.record,claim,link,role,a.clock)
    if role=='finalize':
        require(loads(environment.get('AGENTIC_RECOVERY_PIN',''))==p['pin'],'positive recovery pin changed')
        job=Finalizer(None,api,None,p['pin'],environment,a.clock)._admit()
    else:
        admitted=provenance.admit_job(api,a.binding['deployment'],environment,p['roles'][role],a.clock())
        job=dict(run_id=admitted['run_id'],attempt=1,job_id=admitted['id'],workflow_sha=admitted['head_sha'])
    require(job['run_id']==s['run_id'] and job['attempt']==1,'positive replacement job or rerun refused')
    require(job==bound['job'],'positive numeric job was replaced; never rebind')
    temporary=Path(environment.get('RUNNER_TEMP',''))
    require(temporary.is_absolute() and temporary.is_dir() and temporary.resolve()==Path(bound['scratch']),
            'trusted persistent original-job RUNNER_TEMP changed')
    # Exclude numeric job ID: a replacement ID must collide with the consumed role.
    from trial_wire import WireJournal
    root=temporary/('agentic-positive-'+digest(dict(grant=link,role=role,operation=a.request['operation_id'])))
    store=WireJournal(Store(root),'positive-'+role,root)
    reserved=store.read()
    require(reserved==bound['reserved'],'positive role reservation missing or consumed; no remint or replacement job')
    key=s['pr'] if role=='broker' else a.record['task_id']; name=ROLES[role]+'-'+str(key)+'-1'
    artifacts=api.pages('/repos/'+a.binding['deployment']['policy']['authority_repository']+'/actions/runs/'+str(s['run_id'])+'/artifacts','artifacts')
    require(not any(v['name']==name for v in artifacts),'positive role intent exists; missing protected history cannot be adopted')
    issued=dict(schema_version=1,kind=ROLES[role],grant=link,grant_digest=digest(claim),job_binding=job_link(original(a),a.record,role),case_digest=digest(case),
        request_digest=digest(a.request),role=role,job=job,issued=a.clock(),expires=p['expires'])
    a.guard(); require(a.clock()<p['expires'],'positive issuance expired')
    document=store.write(reserved,dict(phase='attempt-started',claim=issued,marker=None,envelope=None,before=None,terminal=None))
    a.guard(); require(a.clock()<p['expires'],'positive issuance expired after persistence')
    identity=service._upload_document(uploader,name,issued)
    locator=dict(run_id=s['run_id'],attempt=1,job_id=job['job_id'],artifact_id=identity)
    proof=provenance.live_positive_issuance(api,a.binding['deployment'],locator,ROLES[role],key,a.clock())
    require(proof['document']==issued and a.clock()<p['expires'],'positive issuance marker differs or expired')
    state=dict(document['value'],phase='marker-bound',marker=locator)
    document=store.write(document,state)
    a._positive=dict(grant=link,claim=claim,issuance=issued,marker=locator,role=role,job=job,root=str(store.root),after=None,envelope=None)
    a._positive_store,a._positive_document=store,document
    a._seal=copy.deepcopy(a._state())
    guard(a)


def guard(a,binding=None):
    """Current ownership with narrowly permitted exact post-merge readback."""
    from registry import trial_reference
    from trial_case import history_guard
    from authority_github import Readers,current_snapshot
    a.local_guard(binding)
    v=a._positive; case=_case(a); expected=v['after'] or a.binding
    require(a._positive_store.read()==a._positive_document and str(a._positive_store.root)==v['root'],
            'positive protected attempt changed')
    authenticate_grant(original(a),a.record,case,a.binding,v['grant'],a.clock)
    bound=authenticate_job(original(a),a.record,v['claim'],v['grant'],v['role'],a.clock)
    require(bound['job']==v['job'] and Path(bound['scratch'])==a._positive_store.root.parent,'positive original job or scratch changed')
    original(a).unchanged(a.record['origin']['binding'])
    require(original(a).ref(trial_reference(case))==a.revision and
            original(a).ref(trial_reference(dict(case,execution=None)))==case['execution']['publication_revision'],
            'positive case publication moved')
    require(a.registry.binding()==expected,'positive registry ownership changed')
    history_guard(original(a),a.record,case['history'],a.clock,a.registry.api,a.source)
    key=case['request']['snapshot']['pr'] if v['role']=='broker' else a.record['task_id']
    proof=provenance.live_positive_issuance(a.registry.api,a.binding['deployment'],v['marker'],ROLES[v['role']],key,a.clock())
    require(proof['document']==v['issuance'],'positive issuance marker removed or replaced')
    if a.source is not None:
        p=a.binding['deployment']['policy']; root='/repos/'+p['repository']; s=a.request['snapshot']
        repo=a.source.get(root)
        require(repo.get('id')==p['repository_id'] and repo.get('private') is True and
                repo.get('owner',{}).get('id')==a.record['pair']['identities']['owner_id'] and repo.get('default_branch')==p['target'],
                'positive disposable source identity changed')
        pr=a.source.get(root+'/pulls/'+str(s['pr']))
        if pr.get('merged') is True:
            actual=a.source.get(root+'/git/commits/'+str(pr.get('merge_commit_sha')))
            recover_merged(dict(s,repository_id=p['repository_id'],target=p['target'],tree=v['claim']['preview']['tree']),pr,actual)
            require(a.source.get(root+'/git/ref/heads/'+quote(p['target'],safe=''))['object']['sha']==actual['sha'],
                    'positive target differs from the exact merged commit')
            protections(a.source,a.registry.api,a.binding,v['claim']['preview']['controls'],actual['sha'])
        else:
            require(v['after'] is None and current_snapshot(Readers(a.source,a.registry.api,a.binding['deployment']),a.binding['deployment'],
                s['pr'],s['run_id'],s['run_attempt'])==s,'positive candidate changed')
            protections(a.source,a.registry.api,a.binding,v['claim']['preview']['controls'],s['base'])
            authorization(a)
    a.local_guard(binding)
    require(a.clock()<min(deadline(a),v['claim']['preview']['expires']),'positive original deadline consumed by blocking reads')


def protections(source,authority,binding,expected,base):
    from controls import observe
    from authority_github import Readers
    actual=observe(Readers(source,authority,binding['deployment']),binding['deployment'])
    require(actual['base']==base and {k:v for k,v in actual.items() if k!='base'}==
            {k:v for k,v in expected.items() if k!='base'}, 'positive effective protections, access, owners or automation changed')
    return actual


def authorization(a):
    """Revocation readback immediately before pre-dispatch effects."""
    import service,checks
    from trusted_ci_github import independent_approval
    from authority_github import Readers,current_snapshot
    b=a.binding; d=b['deployment']; s=a.request['snapshot']; p=d['policy']
    location=service._locator(a.registry.api,d,s['run_id'],s['run_attempt'],'evidence',s['pr'])
    proof=provenance.authenticated_document(a.registry.api,d,location,'evidence',s['pr'],a.clock())
    provenance.validate_evidence(proof['document'],d,s,b['configuration_revision'],proof['job_id'],a.clock())
    task=a.task(b,s,a.request['task']['locator'],a.request['task']['task_id'])
    coordinates=dict(configuration_revision=b['configuration_revision'],operation=b['fence']['pending'],sequence=b['fence']['sequence'],
        issuer_installation_id=a.record['pair']['identities']['apps']['issuer']['installation_id'],evidence_job_id=proof['job_id'],
        evidence_digest=digest(proof['document']),task_digest=task['task_digest'])
    checks.current(a.source,d,s,coordinates,a.clock())
    pr=a.source.get('/repos/'+p['repository']+'/pulls/'+str(s['pr']))
    independent_approval(a.source,p,pr,human=True)
    require(current_snapshot(Readers(a.source,a.registry.api,d),d,s['pr'],s['run_id'],s['run_attempt'])==s,
            'positive candidate moved during last authorization readback')


def finalize(finalizer,a,operation_id,sequence,broker_job,recovery):
    require(selected(a) and a._positive is not None and a._positive['role']=='finalize','original positive recovery issuance required')
    guard(a); v=a._positive; before=copy.deepcopy(a.binding); op=before['fence']['pending']
    require((operation_id,sequence)==(op['operation_id'],before['fence']['sequence']) and recovery==v['job'] and
            finalizer.pin==v['claim']['preview']['pin'],'positive recovery job, pin or operation differs')
    store=ActionsReceipts._create(finalizer.authority,a.registry.binding,broker_job,a.clock,recovery=True,admission=a)
    producer=store.terminal_job()
    locations={k:store.find_for_recovery(k) for k in ('dispatch','outcome')}
    require(locations['dispatch'] is not None and all(store.find_for_recovery(k) is None for k in ('not-submitted','host-denied')),
            'positive requires actual dispatch without contradictory no-dispatch evidence')
    documents={k:store.authenticate(loc) for k,loc in locations.items() if loc is not None}
    dispatch=documents['dispatch']
    require(dispatch['gate']['tree']==v['claim']['preview']['tree'],'positive dispatch tested a different tree')
    p=before['deployment']['policy']; root='/repos/'+p['repository']
    pr=finalizer.source.get(root+'/pulls/'+str(op['pr']))
    commit=finalizer.source.get(root+'/git/commits/'+str(pr.get('merge_commit_sha')))
    facts=recover_merged(dispatch['gate'],pr,commit)
    target=finalizer.source.get(root+'/git/ref/heads/'+quote(p['target'],safe=''))['object']['sha']
    require(target==facts['merge_commit'],'positive target has not reached the authenticated merge')
    broker_issue=issuance_for_history(finalizer.authority,before['deployment'],a.record,_case(a),v['claim'],
                                      v['grant'],'broker',broker_job,a.clock,original_registry=original(a))
    envelope=dict(schema_version=1,kind='native-positive-terminal-recovery',operation_digest=digest(op),
        configuration_revision=before['configuration_revision'],deployment_digest=before['deployment_digest'],
        grant=v['grant'],grant_digest=digest(v['claim']),producer=dict(id=producer['id'],run_id=producer['run_id'],head_sha=producer['head_sha'],
            conclusion=producer['conclusion'],completed_at=producer['completed_at']),recovery=recovery,pin=finalizer.pin,
        artifacts=locations,documents=documents,broker_issuance=broker_issue,
        recovery_issuance=dict(claim=v['issuance'],marker=v['marker']),facts=facts,pr=pr,commit=commit,target=target)
    terminal=dict(operation_id=operation_id,sequence=sequence,kind='merged',receipt_digest=digest(envelope))
    guard(a)
    state=dict(a._positive_document['value'],phase='settlement-started',envelope=envelope,before=before,terminal=terminal)
    a._positive_document=a._positive_store.write(a._positive_document,state)
    result=finalizer.registry.finalize_operation(before['branch_head'],terminal,before_effect=lambda:guard(a))
    expected=copy.deepcopy(before['fence']); expected['pending']=None; expected['completed'].append(terminal)
    a.registry.authenticate_setup_transition(before,{__import__('registry').OPERATION:expected},result)
    v['after']=result; v['envelope']=envelope
    a._seal=copy.deepcopy(a._state())
    guard(a)
    return result


def issuance_for_history(api,d,record,case,grant,link,role,job,clock,locator=None,original_registry=None):
    key=case['request']['snapshot']['pr'] if role=='broker' else record['task_id']
    name=ROLES[role]+'-'+str(key)+'-1'; run=case['request']['snapshot']['run_id']
    if locator is None:
        artifacts=api.pages('/repos/'+d['policy']['authority_repository']+'/actions/runs/'+str(run)+'/artifacts','artifacts')
        matches=[v for v in artifacts if v['name']==name]
        require(len(matches)==1,'exact positive issuance archive missing or ambiguous')
        locator=dict(run_id=run,attempt=1,job_id=job,artifact_id=matches[0]['id'])
    proof=provenance.authenticated_document(api,d,locator,ROLES[role],key,clock())
    claim=proof['document']
    object_fields(claim,('schema_version kind grant grant_digest job_binding case_digest request_digest role job issued expires').split(),'positive issuance claim')
    require(original_registry is not None,'original native positive job authority required')
    bound=authenticate_job(original_registry,record,grant,link,role,clock)
    require(claim['schema_version']==1 and claim['kind']==ROLES[role] and claim['grant']==link and claim['grant_digest']==digest(grant) and
            claim['job_binding']==job_link(original_registry,record,role) and bound['job']==claim['job'] and
            claim['case_digest']==digest(case) and claim['request_digest']==digest(case['request']) and claim['role']==role and
            claim['job']==dict(run_id=run,attempt=1,job_id=job,workflow_sha=(grant['preview']['pin']['workflow_sha'] if role=='finalize' else d['policy']['workflow_sha'])) and
            proof['job_id']==job and proof['job_started']<=claim['issued']<=proof['artifact_created']<=proof['job_completed']<claim['expires']==grant['preview']['expires'],
            'positive issuance original job, interval or grant differs')
    return dict(claim=claim,marker=locator)


def terminal_document(a):
    guard(a); v=a._positive
    require(v['after'] is not None and v['envelope'] is not None and a._positive_document['value']['envelope']==v['envelope'],
            'retained exact positive settlement required before publication')
    return dict(schema_version=1,kind='trial-case-terminal',request_digest=digest(a.request),certificate_digest=digest(a.value['certificate']),
        before=a.binding,after=v['after'],completed=a.clock(),positive=v['envelope'])


def reconstruct(original_registry,registry,record,case,document,baseline,clock,producer,source=None):
    from registry import OPERATION
    from types import SimpleNamespace
    from trial_controller import Admission
    object_fields(document,('schema_version kind request_digest certificate_digest before after completed positive').split(),'native positive terminal')
    require(type(document['schema_version']) is int and document['schema_version']==1 and document['kind']=='trial-case-terminal' and
            document['request_digest']==digest(case['request']) and document['certificate_digest']==digest(case['certificate']) and
            positive(document['completed']) and producer['job_started']<=document['completed']<=producer['artifact_created']<=producer['job_completed'],
            'positive terminal case or CLOSED interval differs')
    Admission._retained(SimpleNamespace(binding=baseline,record=record,value=case,candidate=case['candidate'],original=original_registry))
    before=registry.authenticate_setup_transition(baseline,{OPERATION:case['pending']},document['before'])
    e=document['positive']
    object_fields(e,('schema_version kind operation_digest configuration_revision deployment_digest grant grant_digest producer recovery pin artifacts documents '
                     'broker_issuance recovery_issuance facts pr commit target').split(),'positive recovery envelope')
    grant=authenticate_grant(original_registry,record,case,before,e['grant'],clock)
    require(e['schema_version']==1 and e['kind']=='native-positive-terminal-recovery' and e['operation_digest']==digest(before['fence']['pending']) and
            e['configuration_revision']==before['configuration_revision'] and e['deployment_digest']==before['deployment_digest'] and
            e['grant_digest']==digest(grant) and e['pin']==grant['preview']['pin'] and
            e['recovery']==dict(run_id=producer['run_id'],attempt=producer['attempt'],job_id=producer['job_id'],workflow_sha=e['pin']['workflow_sha']) and
            e['recovery']['run_id']==case['request']['snapshot']['run_id'] and e['recovery']['attempt']==1 and
            producer['job_completed']<case_end(record,case,before),'positive recovery authority or deadline differs')
    certificate=case['certificate']
    q=dict(document=certificate,qualification_digest=digest(certificate),expires=case_end(record,case,before))
    receipts=ActionsReceipts._historical_positive(registry.api,before,e['producer']['id'],clock,e['documents'],q)
    job=receipts.terminal_job()
    require(e['producer']==dict(id=job['id'],run_id=job['run_id'],head_sha=job['head_sha'],conclusion=job['conclusion'],completed_at=job['completed_at']),
            'positive CLOSED broker differs')
    for kind in ('dispatch','outcome'):
        require(receipts.find_for_recovery(kind)==e['artifacts'][kind],'positive broker artifact changed')
        if e['artifacts'][kind] is not None: require(receipts.authenticate(e['artifacts'][kind])==e['documents'][kind],'positive broker document differs')
    require(not receipts._matches('not-submitted') and not receipts._matches('host-denied'),'contradictory positive broker evidence')
    gate=e['documents']['dispatch']['gate']
    require(gate['tree']==grant['preview']['tree'] and recover_merged(gate,e['pr'],e['commit'])==e['facts'] and e['target']==e['facts']['merge_commit'],
            'positive actual merge identity, parents or tree differ')
    for role,job_id,key in (('broker',job['id'],'broker_issuance'),('finalize',producer['job_id'],'recovery_issuance')):
        require(issuance_for_history(registry.api,before['deployment'],record,case,grant,e['grant'],role,job_id,clock,e[key]['marker'],original_registry)==e[key],
                'positive retained issuance archive differs')
    receipt=dict(operation_id=case['request']['operation_id'],sequence=case['request']['sequence'],kind='merged',receipt_digest=digest(e))
    fence=copy.deepcopy(before['fence']); fence['pending']=None; fence['completed'].append(receipt)
    after=registry.authenticate_setup_transition(before,{OPERATION:fence},document['after'])
    if source is not None:
        p=before['deployment']['policy']; root='/repos/'+p['repository']
        pr=source.get(root+'/pulls/'+str(gate['pr'])); commit=source.get(root+'/git/commits/'+str(pr.get('merge_commit_sha')))
        require(recover_merged(gate,pr,commit)==e['facts'] and source.get(root+'/git/ref/heads/'+quote(p['target'],safe=''))['object']['sha']==e['target'],
                'positive current merge or target changed')
        protections(source,registry.api,before,grant['preview']['controls'],e['target'])
    return after


def observe_native(controller,prompt,locator,source=None,recovering=False):
    from trial_controller import owned_history
    from trial_case import read,case_baseline
    from trial_handoff import Native as NativeHandoff
    c=controller.candidates.native.provision; registry=controller.candidates.native.registry
    from trial_storage import install
    install(c)
    journal=c.store(c.root/'trial-controller-positive'); document=journal.read()
    require(document is not None and document['value']['phase']==('terminal' if recovering else 'bound') and
            document['value']['prompt_digest']==digest(prompt),'exact owned positive observation required')
    value=copy.deepcopy(document['value']); owned_history(c,value)
    publication=c.store(c.root/'trial-case-publication-positive').read()
    require(publication is not None and publication['value']['phase']=='bound','original positive case publication required')
    clock=(lambda:value['terminal']['producer']['job_completed']) if recovering else c.clock
    case,record=read(c.session.registry,publication['value']['revision_bound'],clock)
    require(case['worker']==value['worker'] and case['candidate']==value['candidate'] and case['request']==value['request'],
            'positive observation substituted owned original case')
    worker=NativeHandoff.worker_completion(registry,source or c.api,record,prompt,clock)
    require(worker['result']==case['worker'],'positive CLOSED worker changed')
    baseline=case_baseline(c.session.registry,registry,record,case,clock)
    proof=provenance.authenticated_document(registry.api,baseline['deployment'],locator,'trial-case-terminal',record['task_id'],clock())
    require(locator['run_id']==case['request']['snapshot']['run_id'] and locator['attempt']==1,'positive terminal run differs')
    after=reconstruct(c.session.registry,registry,record,case,proof['document'],baseline,clock,proof,source or c.api)
    require(registry.binding()==after and journal.read()==document,'positive settled binding or owner changed')
    result=dict(binding=after,locator=copy.deepcopy(locator),document=proof['document'],producer={k:v for k,v in proof.items() if k!='document'})
    if recovering:
        require(result==value['terminal'],'retained positive completion changed')
    else:
        require(c.clock()<case_end(record,case,proof['document']['before']),'positive observation expired')
        from trial_storage import write_controller
        value.update(phase='terminal',terminal=result)
        write_controller(c,'trial-controller-positive',journal,document,value)
    return copy.deepcopy(result)
