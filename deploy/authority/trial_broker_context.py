"""Finite native context handover over the existing broker/configuration engines.

Historical bindings here grant only transition evidence and pinned recovery. They
never replace the live Registry used by collection, publication or dispatch.
"""
import copy
import secrets
import time

from broker_refusal import BrokerRefusal, same
from trusted_ci_policy import digest, object_fields, positive, require

INTENT = 'native-trial-broker-context-intent'
RESULT = 'native-trial-broker-context-result'
JOURNAL = 'trial-broker-context'


def selected(a):
    return a.candidate['name'] == 'context-transition'


def changed(before, after):
    old, new = before['deployment']['policy'], after['deployment']['policy']
    require(before['configuration_revision'] != after['configuration_revision'] and
            old['epoch'] != new['epoch'] and old['check_name'] != new['check_name'],
            'actual approved context transition is required; handover alone is insufficient')
    return True


def original(a):
    return a.original if hasattr(a, 'original') else a.native.provision.session.registry


def deadline(a):
    values = [a.record['expires'], a.value['certificate']['expires'], a.binding['deployment']['expires'],
              a.binding['fence']['pending']['execution_deadline'],
              a.record['origin']['binding']['fence']['pending']['execution_deadline']]
    if hasattr(a, 'case'):
        values.append(a.case['execution']['credential']['expires'])
    elif hasattr(a,'native'):
        from trial_controller import case_journal
        c=a.native.provision
        publication=c.store(c.root/case_journal('trial-case-publication',a.candidate)).read()
        require(publication is not None and publication['value']['phase']=='bound', 'bound native context delegation required')
        values.append(publication['value']['execution']['credential']['expires'])
    return min(values)


def pending_binding(registry, baseline, pending):
    """Authenticate immutable old ownership, never project it as current state."""
    from registry import OPERATION
    current = registry.binding()
    if current['fence']['schema_version'] == 3:
        retained = current['fence']['retained']['binding']
        return registry.authenticate_setup_transition(baseline, {OPERATION:pending}, retained)
    return registry.authenticate_setup_progress(baseline, {OPERATION:pending})


def guard(a, current=None):
    """Read-only ownership/source checks that intentionally survive the handover."""
    from trial_controller import Admission
    from trial_case import Hosted
    from trial_case import history_guard
    from authority_github import Readers, current_snapshot
    from trusted_ci_github import independent_approval
    require(type(a) in (Admission,Hosted), 'actual native context admission required')
    a.local_guard()
    require(selected(a) and a.clock() < deadline(a), 'native context expired or substituted')
    source = original(a)
    source.unchanged(a.record['origin']['binding'])
    from trial_broker_case import _case_value
    _, case = _case_value(a)
    require(case['history'] == a.value['history'] and len(case['history']) == 14,
            'exact fourteen native predecessors required')
    history_guard(source, a.record, case['history'], a.clock, a.registry.api)
    live = a.registry.binding() if current is None else current
    require(live['software_revision'] == a.binding['software_revision'], 'context software moved')
    if live != a.binding:
        fence = live['fence']
        require(fence['schema_version'] == 3 and fence['retained']['binding'] == a.binding and
                fence['retained']['operation'] == a.binding['fence']['pending'] and
                fence['retained']['sequence'] == a.request['sequence'], 'context handover substituted original broker')
    if a.source is not None:
        d, s = a.binding['deployment'], a.request['snapshot']
        require(current_snapshot(Readers(a.source,a.registry.api,d),d,s['pr'],s['run_id'],s['run_attempt']) == s,
                'native broker context source snapshot changed')
        repo = a.source.get('/repos/'+d['policy']['repository'])
        require(repo.get('id') == d['policy']['repository_id'] and repo.get('private') is True and
                repo.get('owner',{}).get('id') == a.record['pair']['identities']['owner_id'] and
                repo.get('default_branch') == d['policy']['target'], 'native context source identity changed')
        pr = a.source.get('/repos/'+d['policy']['repository']+'/pulls/'+str(s['pr']))
        independent_approval(a.source,d['policy'],pr,human=True)
        if live['configuration_revision'] != a.binding['configuration_revision']:
            from controls import observe
            facts=observe(Readers(a.source,a.registry.api,live['deployment']),live['deployment'])
            require(facts['base']==s['base'], 'native context target or effective controls changed')
    if getattr(a,'_context_issuance',None) is not None: issuance_guard(a)
    from registry import trial_reference
    if hasattr(a,'revision'):
        revision=a.revision
    else:
        from trial_controller import case_journal
        c=a.native.provision
        revision=c.store(c.root/case_journal('trial-case-publication',a.candidate)).read()['value']['revision_bound']
    require(source.ref('agentic-trial-'+a.record['task_id'])==a.record['execution']['publication_revision'] and
            source.ref('agentic-trial-'+a.record['task_id']+'-execution')==case['origin_revision'] and
            source.ref(trial_reference(case))==revision and
            source.ref(trial_reference(dict(case,execution=None)))==case['execution']['publication_revision'] and
            source.ref(trial_reference(dict(case,kind='trial-case-ready',execution=None)))==case['launch']['revision'],
            'native context original/current case pointers moved')
    a.registry.unchanged(live)
    fresh_source(a)
    a.local_guard()
    end=deadline(a)
    if live['fence']['schema_version']==3: end=min(end,live['fence']['pending']['execution_deadline'])
    require(a.clock() < end, 'native context deadline consumed by readback')
    return live


def fresh_source(a):
    if a.source is not None:
        from authority_github import Readers,current_snapshot
        d,s=a.binding['deployment'],a.request['snapshot']
        require(current_snapshot(Readers(a.source,a.registry.api,d),d,s['pr'],s['run_id'],s['run_attempt'])==s,
                'native context candidate moved during administrative readback')


def validate_preloaded(a, value, job, now):
    object_fields(value, ('schema_version kind request_digest prepared_digest job_id issued').split(), 'context preload')
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and value['kind'] == 'trial-preloaded' and
            value['request_digest'] == digest(a.request) and positive(job) and value['job_id'] == job and
            isinstance(value['prepared_digest'],str) and len(value['prepared_digest']) == 64 and
            positive(value['issued']) and a.binding['fence']['pending']['created'] <= value['issued'] <= now < deadline(a),
            'exact native context preload differs')
    return value


def publications(a, job, required=True):
    from registry import trial_reference
    from trial_transition import read_native
    from trusted_ci_github import HostRefusal
    links = {}
    for kind in (INTENT, RESULT):
        try:
            revision = original(a).ref(trial_reference(dict(kind=kind, name='context-transition', task_id=a.record['task_id'], execution=None)))
        except HostRefusal as error:
            require(error.status == 404 and not required, 'native context publication unavailable')
            return None
        links[kind] = dict(kind=kind, revision=revision)
    intent, result = (read_native(original(a),links[k],a.record) for k in (INTENT,RESULT))
    from trial_broker_case import _case_value
    _, case = _case_value(a)
    authenticate_intent(a.registry,a.record,case,intent,result)
    object_fields(intent, ('schema_version kind task_id execution name record_digest case_digest request_digest before marker preloaded job_id preview approval issued expires operation').split(), 'native context intent')
    object_fields(result, ('schema_version kind task_id execution name record_digest intent intent_digest steps after effects completed').split(), 'native context result')
    require(intent['schema_version'] == result['schema_version'] == 1 and
            intent['case_digest'] == digest(case) and intent['request_digest'] == digest(a.request) and
            intent['before'] == a.binding and intent['job_id'] == job and
            intent['approval'] == digest(intent['preview']) and intent['preview']['request_digest'] == digest(a.request) and
            intent['preview']['before'] == a.binding and result['intent'] == links[INTENT] and
            result['intent_digest'] == digest(intent) and positive(intent['issued']) and positive(result['completed']) and
            intent['preloaded']['issued'] <= intent['issued'] <= result['completed'] < intent['expires'] <= deadline(a),
            'native context publication identity or original interval differs')
    validate_preloaded(a,intent['preloaded'],job,a.clock())
    transition=dict(links=links,intent=intent,result=result)
    store = (evidence_store(a,a.registry.api,job,recovery=True) if a.worker is not None else
             closed_history_store(a,a.registry.api,job,transition)[0])
    require(store.find_for_recovery('trial-preloaded') == intent['marker'] and store.authenticate(intent['marker']) == intent['preloaded'],
            'native handover did not follow the exact actual Session preload')
    authenticate_steps(a.registry, intent, result)
    if a.source is not None: effective(a.source,a.registry,intent,result)
    live = guard(a)
    require(live == result['after'], 'native context result is not the held live configuration')
    return dict(links=links, intent=intent, result=result)


def authenticate_intent(registry, record, case, intent, result):
    """Pure immutable contract checks shared by live and historical readers."""
    from operation_fence import operation
    from transition import ContextTransition
    from reconcile import desired_rules, canonical
    object_fields(intent, ('schema_version kind task_id execution name record_digest case_digest request_digest before marker preloaded job_id preview approval issued expires operation').split(), 'native context intent')
    object_fields(result, ('schema_version kind task_id execution name record_digest intent intent_digest steps after effects completed').split(), 'native context result')
    before=intent['before']; preview=intent['preview']; plan=preview['plan']; op=operation(intent['operation'])
    recovery=preview['recovery']; policy=before['deployment']['policy']
    object_fields(recovery,('run_id','attempt','job','nonce','pin'),'native approved finalizer grant')
    import re
    require(recovery['run_id']==case['request']['snapshot']['run_id'] and recovery['attempt']==1 and
            recovery['job']=='finalize' and isinstance(recovery['nonce'],str) and re.fullmatch('[0-9a-f]{32}',recovery['nonce']) and
            recovery['pin']==dict(authority_repository=policy['authority_repository'],authority_repository_id=policy['authority_repository_id'],
                workflow=policy['workflow'],workflow_sha=policy['workflow_sha']), 'native context finalizer grant changed')
    expires=min(record['expires'],record['origin']['binding']['fence']['pending']['execution_deadline'],
                case['certificate']['expires'],case['execution']['credential']['expires'],
                before['deployment']['expires'],before['fence']['pending']['execution_deadline'])
    require(type(intent['schema_version']) is int and intent['schema_version']==1 and
            type(result['schema_version']) is int and result['schema_version']==1 and
            intent['kind']==INTENT and result['kind']==RESULT and intent['name']==result['name']=='context-transition' and
            intent['record_digest']==result['record_digest']==digest(record) and
            intent['case_digest']==digest(case) and intent['request_digest']==preview['request_digest']==digest(case['request']) and
            preview['before']==before and intent['approval']==digest(preview) and intent['expires']==expires and
            positive(intent['issued']) and positive(result['completed']) and
            intent['preloaded']['issued']<=intent['issued']<=result['completed']<expires and
            result['completed']<op['execution_deadline'] and
            op['kind']=='configuration' and op['created']==intent['issued'] and op['execution_deadline']<=expires and
            op['scope_digest']==digest(preview['effects']) and op['configuration_revision']==before['configuration_revision'] and
            op['deployment_digest']==before['deployment_digest'] and
            op['setup']==dict(operator_id=preview['operator_id'],installation_id=record['pair']['identities']['apps']['admin']['installation_id'],
                              approval_digest=digest(preview)), 'native context approved intent or immutable interval differs')
    require(plan['before']==before['deployment'] and plan['fence']==before['fence'] and
            plan['branch_head']==before['branch_head'] and plan['configuration_revision']==before['configuration_revision'] and
            plan['new_controls']==desired_rules(plan['desired']) and all(
                canonical(plan['old_controls'][k])==desired_rules(before['deployment'])[k] and
                str(plan['old_controls'][k]['id'])==before['deployment']['resources'][k+'_rule'] for k in ('acceptance','updates')),
            'approved native context plan differs from its original controls')
    ContextTransition(None,registry,None).validate_desired(before,plan['desired'])


def effective(source, registry, intent, result):
    from transition import ContextTransition
    from reconcile import canonical
    engine=ContextTransition(source,registry,None)
    desired=result['after']['deployment']
    observed=engine.inventory(desired)
    expected=intent['preview']['plan']['foreign']+[dict(canonical(e['response']),id=e['response']['id']) for e in result['effects'][:2]]
    require(observed==sorted(expected,key=lambda item:item['id']), 'native context foreign or owned protections changed')
    plan=dict(intent['preview']['plan'],desired=desired)
    engine.effective(plan,{k:result['effects'][i]['response'] for i,k in enumerate(('acceptance','updates'))})


def authenticate_steps(registry, intent, result):
    from registry import OPERATION, DOCUMENT
    steps = result['steps']
    require(isinstance(steps,list) and len(steps) == 2, 'exact handover and context-write history required')
    before = intent['before']
    for index, step in enumerate(steps):
        object_fields(step, ('before','documents','after'), 'native context step')
        require(step['before'] == before and set(step['documents']) == ({OPERATION} if index == 0 else {DOCUMENT,OPERATION}),
                'native context step ordering or documents differ')
        before = registry.authenticate_setup_transition(before,step['documents'],step['after'])
        require(before['fence']['schema_version'] == 3 and before['fence']['retained']['binding'] == intent['before'] and
                before['fence']['retained']['intent_digest'] == digest(intent) and before['fence']['pending'] == intent['operation'],
                'native context retained handover or configuration owner differs')
    require(before == result['after'], 'native context final binding differs')
    changed(intent['before'], before)
    effects = result['effects']
    require(isinstance(effects,list) and [e['method'] for e in effects] == ['POST','POST','DELETE','DELETE'] and
            all(e['phase'] == 'acknowledged' for e in effects), 'every native context effect requires acknowledgement')
    plan = intent['preview']['plan']
    root = '/repos/'+intent['before']['deployment']['policy']['repository']
    from reconcile import canonical
    resources = {}
    for index,kind in enumerate(('acceptance','updates')):
        created,deleted = effects[index],effects[index+2]
        object_fields(created,('method','path','body','phase','response'),'acknowledged context creation')
        object_fields(deleted,('method','path','body','phase','response'),'acknowledged context deletion')
        require(created['path'] == root+'/rulesets' and created['body'] == plan['new_controls'][kind] and
                positive(created['response'].get('id')) and canonical(created['response']) == plan['new_controls'][kind] and
                deleted['path'] == root+'/rulesets/'+str(plan['old_controls'][kind]['id']) and
                deleted['body'] is None and deleted['response'] == dict(status=204),
                'native context effect path, preimage or acknowledged result differs')
        resources[kind+'_rule'] = str(created['response']['id'])
    expected = copy.deepcopy(plan['desired']); expected['resources'].update(resources)
    acquired = steps[0]['after']
    fence = copy.deepcopy(acquired['fence'])
    fence['contexts'].append(dict(epoch=expected['policy']['epoch'],check_name=expected['policy']['check_name'],activated=False))
    require(result['after']['deployment'] == expected and result['after']['fence'] == fence and
            acquired['deployment'] == intent['before']['deployment'], 'exact native context configuration or owner differs')
    return before


def evidence_store(a, api, job, uploader=None, recovery=False):
    from merge_receipts import ActionsReceipts
    return ActionsReceipts._context(api,a,job,a.clock,uploader=uploader,recovery=recovery)


def paused(session, prepared):
    """Fixed negative-only branch after genuine preload; never returns a gate."""
    a = session._admission
    require(not getattr(session,'_context_paused',False), 'native context Session cannot reenter')
    session._context_paused = True
    marker = dict(schema_version=1,kind='trial-preloaded',request_digest=digest(a.request),
                  prepared_digest=digest(prepared),job_id=session.job_id,issued=a.clock())
    session.receipts.append('trial-preloaded',marker)
    end = time.monotonic() + max(0, deadline(a)-a.clock())
    while True:
        require(time.monotonic() < end, 'native context remains pending')
        guard(a)
        store = evidence_store(a,session.authority,session.job_id,recovery=True)
        store._job()
        value = publications(a,session.job_id,required=False)
        if value is not None:
            require(value['intent']['preloaded'] == marker, 'native transition substituted actual prepared Session')
            # The shared comparison supplies the typed refusal. No synthetic gate
            # or replacement Registry is introduced for historical evidence.
            same(value['result']['after'],prepared['binding'],'native broker context changed after preload')
            require(False, 'native broker context did not change')
        session.sleeper(0.25)


def validate_refusal(a, value, job, transition=None):
    object_fields(value, ('schema_version kind request_digest job_id operation_id sequence prepared_digest transition refusal issued').split(), 'native context refusal')
    transition = publications(a,job) if transition is None else transition
    before, after = a.binding, transition['result']['after']
    keys = ('configuration_revision','deployment_digest','deployment','fence')
    expected = dict(code='configuration_changed',observation=dict(before=digest({k:before[k] for k in keys}),
                                                                after=digest({k:after[k] for k in keys})))
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and value['kind'] == 'trial-context-refusal' and
            value['request_digest'] == digest(a.request) and value['job_id'] == job and
            value['operation_id'] == a.request['operation_id'] and value['sequence'] == a.request['sequence'] and
            value['prepared_digest'] == transition['intent']['preloaded']['prepared_digest'] and
            value['transition'] == transition['links'] and value['refusal'] == expected and positive(value['issued']) and
            transition['result']['completed'] <= value['issued'] <= a.clock() < min(deadline(a),transition['intent']['operation']['execution_deadline']),
            'exact transition-only no-dispatch refusal differs')
    return value


def closed_history_store(a, api, job, transition):
    """Pre-mint CLOSED readback, without pretending a worker is source-bound."""
    from merge_receipts import ActionsReceipts
    import service, provenance
    s=a.request['snapshot']
    locator=service._locator(api,a.binding['deployment'],s['run_id'],s['run_attempt'],'trial-broker-denial',s['pr'])
    proof=provenance.authenticated_document(api,a.binding['deployment'],locator,'trial-broker-denial',s['pr'],a.clock())
    denial=proof['document']; receipt=dict(denial)
    receipt.pop('receipt'); receipt.pop('receipt_digest')
    validate_refusal(a,receipt,job,transition)
    require(proof['job_id']==job and denial['receipt_digest']==digest(receipt), 'CLOSED preflight refusal differs')
    store=ActionsReceipts._historical_context(api,a.binding,job,a.clock,
        {'trial-preloaded':transition['intent']['preloaded'],'trial-context-refusal':receipt})
    require(store.find_for_recovery('trial-context-refusal')==denial['receipt'] and
            store.authenticate(denial['receipt'])==receipt and
            all(not store._matches(k) for k in ('gate','dispatch','outcome','control-ready','not-submitted','host-denied')),
            'CLOSED preflight has contradictory or missing no-dispatch evidence')
    return store,dict(locator=locator,proof=proof)


def begin_recovery(a, api, environment, uploader):
    """One original-job issuance attempt, before every source/proof/admin mint."""
    from pathlib import Path
    from authority_private import Store
    from broker_finalize import Finalizer
    from trusted_ci_policy import loads
    import service, provenance
    require(selected(a) and a.worker is None and getattr(a,'_context_recovery',False), 'fresh context finalizer preflight required')
    recovery=Finalizer(None,api,None,loads(environment.get('AGENTIC_RECOVERY_PIN','')),environment,a.clock)._admit()
    s=a.request['snapshot']
    require(recovery['run_id']==s['run_id'] and recovery['attempt']==s['run_attempt']==1,
            'context recovery must use its original single finalizer job')
    job=service._case_broker_job(api,a)
    transition=publications(a,job)
    closed_history_store(a,api,job,transition)
    grant=transition['intent']['preview']['recovery']
    require(grant['run_id']==recovery['run_id'] and grant['attempt']==recovery['attempt'] and grant['job']=='finalize' and
            grant['pin']==loads(environment.get('AGENTIC_RECOVERY_PIN','')), 'native context recovery role or independent pin changed')
    temporary=Path(environment.get('RUNNER_TEMP',''))
    require(temporary.is_absolute() and temporary.is_dir(), 'trusted persistent original-job RUNNER_TEMP required')
    root=temporary/('agentic-context-recovery-'+digest(dict(repository=a.binding['deployment']['policy']['authority_repository_id'],
        operation=a.request['operation_id'],sequence=a.request['sequence'],recovery=recovery,nonce=grant['nonce'])))
    store=Store(root)
    require(store.read() is None, 'native context recovery already attempted; never remint or replay')
    name='trial-context-recovery-intent-'+a.record['task_id']+'-1'
    artifacts=api.pages('/repos/'+a.binding['deployment']['policy']['authority_repository']+'/actions/runs/'+str(s['run_id'])+'/artifacts','artifacts')
    require(not any(v['name']==name for v in artifacts), 'remote context issuance intent exists; missing local history cannot be adopted')
    claim=dict(schema_version=1,kind='trial-context-recovery-intent',request_digest=digest(a.request),
        case_digest=transition['intent']['case_digest'],held_digest=digest(transition['result']['after']),
        native=transition['links'],recovery=recovery,grant=grant,issued=a.clock(),
        expires=min(deadline(a),transition['intent']['operation']['execution_deadline']))
    guard(a); require(a.clock()<claim['expires'], 'context recovery issuance expired')
    document=store.write(None,dict(phase='attempt-started',claim=claim,marker=None))
    # A failed persistence/upload/ACK ends this attempt before any credential
    # creation. A new process sees the protected record even if artifacts vanish.
    guard(a); require(a.clock()<claim['expires'], 'context issuance expired after protected persistence')
    identity=service._upload_document(uploader,name,claim)
    locator=dict(run_id=s['run_id'],attempt=1,job_id=recovery['job_id'],artifact_id=identity)
    proof=provenance.live_context_recovery(api,a.binding['deployment'],locator,a.record['task_id'],a.clock())
    require(proof['document']==claim and a.clock()<claim['expires'], 'context issuance acknowledgement differs or expired')
    document=store.write(document,dict(phase='marker-bound',claim=claim,marker=locator))
    a._context_issuance=dict(claim=claim,marker=locator,root=str(root))
    a._context_store,a._context_store_document=store,document
    a._seal=copy.deepcopy(a._state())
    issuance_guard(a)


def issuance_guard(a):
    import provenance
    value=a._context_issuance; store=a._context_store
    require(str(store.root)==value['root'] and store.read()==a._context_store_document and
            a._context_store_document['value']['phase'] in ('marker-bound','pair-started') and
            a._context_store_document['value']['claim']==value['claim'] and
            a._context_store_document['value']['marker']==value['marker'], 'protected context issuance state changed')
    proof=provenance.live_context_recovery(a.registry.api,a.binding['deployment'],value['marker'],a.record['task_id'],a.clock())
    require(proof['document']==value['claim'] and a.clock()<value['claim']['expires'],
            'context issuance marker removed, replaced or expired')


def run(a, authority, session, uploader):
    from trial_broker_case import _prerequisites
    _prerequisites(a,authority)
    # _collect enters paused() after authentic preload. It cannot return a gate,
    # including missing-result, expiry and exception paths.
    try:
        session._run(_admission=a)
    except BrokerRefusal as error:
        require(error.code == 'configuration_changed', 'wrong native context refusal')
        transition = publications(a,session.job_id)
        value = dict(schema_version=1,kind='trial-context-refusal',request_digest=digest(a.request),job_id=session.job_id,
                     operation_id=a.request['operation_id'],sequence=a.request['sequence'],
                     prepared_digest=transition['intent']['preloaded']['prepared_digest'],transition=transition['links'],
                     refusal=dict(code=error.code,observation=error.observation),issued=a.clock())
        validate_refusal(a,value,session.job_id)
        store = evidence_store(a,authority,session.job_id,uploader=uploader)
        location = store.append('trial-context-refusal',value)
        require(store.authenticate(location) == value, 'native context refusal readback differs')
        import service
        s = a.request['snapshot']
        service._upload_document(uploader,'trial-broker-denial-'+str(s['pr'])+'-'+str(s['run_attempt']),
                                 dict(value,receipt=location,receipt_digest=digest(value)))
        return dict(state='broker-denied',refusal=error.code,operation_id=a.request['operation_id'],
                    sequence=a.request['sequence'],fence_pending=True)
    require(False, 'native context Session returned without its typed refusal')


def configuration_preview(native, document):
    from trial_handoff import Native
    from trial_setup import Provision
    require(type(native) is Native and type(native.provision) is Provision, 'actual protected native context owner required')
    c = native.provision
    require(c.store(c.root/JOURNAL).read() == document, 'native broker context journal changed')
    value = document['value']; record = value['record']
    require(c.document == value['provisioning'] and c.store(c.root/'trial').read() == value['provisioning'] and
            c.session.owner == record['origin']['owner'] and c.session.scope == record['origin']['scope'],
            'native broker context owner changed')
    c.session._owned(record['origin']['binding'])
    require(value['claim']['record_digest'] == digest(record) and value['claim']['approval'] == digest(value['preview']) and
            value['current']['fence']['schema_version'] == 3, 'native broker context approval or acquisition differs')
    return value['preview'],value['current']


def native_guard(a, journal, document, value, operator, admin):
    """Re-sample source, pointers and both deadlines after administrative reads."""
    from trial_broker_case import _revocation_identity
    from trial_transition import read_native
    import provenance
    require(journal.read()==document, 'native context journal changed')
    a.local_guard()
    require(a.registry.binding()==value['current'], 'native context current pointer moved')
    require(_revocation_identity(a,operator,admin,value['preview'])==value['operation']['setup'],
            'native context administrator changed')
    d,s=a.binding['deployment'],a.request['snapshot']
    live=provenance.execution_job(a.registry.api,d,s['run_id'],s['run_attempt'],'broker ('+str(s['pr'])+')')
    require(live['id']==value['claim']['job_id'] and live['status']=='in_progress' and live['conclusion'] is None,
            'native context broker is no longer paused')
    if value['intent'] is not None:
        require(read_native(original(a),value['intent'],a.record)==value['claim'], 'native context intent moved')
    require(guard(a)==value['current'], 'native context moved during administrative readback')
    a.registry.unchanged(value['current'])
    fresh_source(a)
    a.local_guard()
    require(a.clock()<min(deadline(a),value['operation']['execution_deadline']),
            'native broker context configuration deadline consumed by readback')


def move(controller, prompt, operator, admin, approve):
    """Retained one-shot native orchestration; engine mutations never replay."""
    from trial_controller import Native, Admission
    from trial_candidates import Prepare
    from trial_broker_case import _case_value, _prerequisites, _revocation_identity
    from merge_receipts import ActionsReceipts
    from transition import ContextTransition
    from trial_transition import _publish_native, read_native
    from registry import OPERATION, DOCUMENT
    from configuration import SetupConfigurationSession
    from trial_configuration import _Boundary
    require(type(controller) is Native and type(controller.candidates) is Prepare, 'actual native context coordinator required')
    native = controller.candidates.native; c = native.provision
    journal = c.store(c.root/JOURNAL); document = journal.read()
    if document is None:
        a = controller._open(prompt,'context-transition',operator)
        _prerequisites(a,a.registry.api)
    else:
        a = Admission(native,operator,name='context-transition')
        completed = native._worker_completion(a.record,prompt,operator)
        require(completed['result'] == a.value['worker'], 'native context retained worker changed')
        a.worker = completed
    _, case = _case_value(a)
    d,p,s = a.binding['deployment'],a.binding['deployment']['policy'],a.request['snapshot']
    job = __import__('provenance').execution_job(a.registry.api,d,s['run_id'],s['run_attempt'],'broker ('+str(s['pr'])+')')
    if document is None:
        store = ActionsReceipts._create(a.registry.api,a.registry.binding,job['id'],a.clock,recovery=True,admission=a)
        location = store.find_for_recovery('trial-preloaded')
        require(location is not None and job['status'] == 'in_progress', 'actual paused native broker preload required')
        marker = store.authenticate(location)
        desired = copy.deepcopy(d); desired['generation'] += 1
        epoch = secrets.token_hex(16)
        desired['policy'].update(epoch=epoch,check_name='AGENTIC acceptance '+epoch)
        plan = ContextTransition(operator,a.registry,None).preview(desired)
        preview = {k:p[k] for k in ('repository','repository_id','target','authority_repository','authority_repository_id')}
        preview.update(schema_version=1,kind='native-trial-broker-context-preview',
            adapter=d['adapter'],account=d['account'],operator_id=c.preview['fixture']['operator_id'],
            configuration_revision=a.binding['configuration_revision'],deployment_digest=a.binding['deployment_digest'],
            workflow_sha=a.binding['software_revision'],request_digest=digest(a.request),before=a.binding,plan=plan,
            effects=dict(rules=[p['repository']],registry=[p['authority_repository']+':'+a.registry.coordinates['registry_branch']]),
            recovery=dict(run_id=s['run_id'],attempt=1,job='finalize',nonce=secrets.token_hex(16),
                pin=dict(authority_repository=p['authority_repository'],authority_repository_id=p['authority_repository_id'],
                         workflow=p['workflow'],workflow_sha=p['workflow_sha'])))
        identity = _revocation_identity(a,operator,admin,preview)
        require(callable(approve) and approve(copy.deepcopy(preview)) == digest(preview), 'exact broker context preview approval required')
        issued = a.clock()
        claim = dict(schema_version=1,kind=INTENT,task_id=a.record['task_id'],execution=None,name='context-transition',
            record_digest=digest(a.record),case_digest=digest(case),request_digest=digest(a.request),before=a.binding,
            marker=location,preloaded=marker,job_id=job['id'],preview=preview,approval=digest(preview),issued=issued,expires=deadline(a))
        operation = dict(kind='configuration',operation_id=secrets.token_hex(16),scope_digest=digest(preview['effects']),
            repository_id=p['repository_id'],target=p['target'],configuration_revision=a.binding['configuration_revision'],
            deployment_digest=a.binding['deployment_digest'],workflow_sha=p['workflow_sha'],run_id=None,attempt=None,
            created=issued,execution_deadline=min(issued+300,claim['expires']),pr=None,head=None,base=None,merge=None,
            setup=dict(identity,approval_digest=digest(preview)))
        claim['operation'] = operation
        value = dict(record=a.record,case=case,provisioning=copy.deepcopy(c.document),preview=preview,claim=claim,
            operation=operation,intent=None,phase='intent-started',steps=[],current=a.binding,effects=[],result=None)
        document = journal.write(None,value)
    else:
        value = copy.deepcopy(document['value'])
        require(value['case'] == case and value['claim']['before'] == a.binding and
                a.value['prompt_digest'] == digest(prompt), 'resume only exact native context')
    def save():
        nonlocal document
        document = journal.write(document,value)
    def owner_guard():
        native_guard(a,journal,document,value,operator,admin)
    if value['intent'] is None:
        if value['phase'] == 'intent-writing':
            from registry import trial_reference
            link = dict(kind=INTENT,revision=original(a).ref(trial_reference(value['claim'])))
            require(read_native(original(a),link,a.record)==value['claim'], 'native context intent acknowledgement remains unknown')
            value['intent']=link; value['phase']='intent-published'; save()
        else:
            require(value['phase'] == 'intent-started', 'unknown native context intent cannot replay')
            value['phase'] = 'intent-writing'; save()
            value['intent'] = _publish_native(c,a.record,value['claim'],owner_guard); value['phase']='intent-published'; save()
    if value['phase'] == 'intent-published':
        owner_guard(); value['phase']='handover-started'; save()
        result = a.registry.handover_operation(a.binding['branch_head'],a.binding['configuration_revision'],value['operation'],
            digest(value['claim']),owner_guard,a.clock)
        value['steps'].append(dict(before=a.binding,documents={OPERATION:result['fence']},after=result))
        value['current']=result; value['phase']='acquired'; save()
    elif value['phase'] == 'handover-started':
        current = a.registry.binding()
        require(current['fence']['schema_version'] == 3 and current['fence']['retained']['binding'] == a.binding and
                current['fence']['retained']['intent_digest'] == digest(value['claim']) and
                current['fence']['pending'] == value['operation'], 'native handover outcome unknown; never replay')
        a.registry.authenticate_setup_transition(a.binding,{OPERATION:current['fence']},current)
        value['steps'].append(dict(before=a.binding,documents={OPERATION:current['fence']},after=current))
        value['current']=current; value['phase']='acquired'; save()
    if value['phase'] == 'acquired':
        owner_guard()
        plan = dict(value['preview']['plan'],branch_head=value['current']['branch_head'],fence=value['current']['fence'])
        value['plan']=plan; value['phase']='policy-started'; save()
        session = SetupConfigurationSession.broker_context(native,operator,admin,document)
        def before_request(name,args,kwargs):
            method = 'POST' if name == 'post' else kwargs.get('method','GET')
            body = args[1] if name == 'post' else kwargs.get('data')
            effect = dict(method=method,path=args[0],body=copy.deepcopy(body),phase='started',response=None)
            require(method in ('POST','DELETE') and len(value['effects']) < 4, 'unexpected native context mutation')
            value['effects'].append(effect); save(); session.native_broker_context=(native,document)
            if method == 'DELETE': kwargs['expected_status']=204
        def acknowledged(name,args,kwargs,response):
            effect = value['effects'][-1]
            effect['response'] = copy.deepcopy(response) if effect['method']=='POST' else dict(status=204)
            effect['phase']='acknowledged'; save(); session.native_broker_context=(native,document)
        boundary = _Boundary(operator,owner_guard,read_guard=owner_guard,before_effect=owner_guard,
                             before_request=before_request,after_response=acknowledged)
        before = value['current']
        # Intent is durable before the one engine invocation. An interruption
        # cannot reenter its create/delete loops, even if inventory looks right.
        ContextTransition(boundary,a.registry,session).apply(plan,digest(plan))
        after = a.registry.binding()
        a.registry.authenticate_setup_transition(before,{DOCUMENT:after['deployment'],OPERATION:after['fence']},after)
        value['steps'].append(dict(before=before,documents={DOCUMENT:after['deployment'],OPERATION:after['fence']},after=after))
        value['current']=after; value['phase']='policy-complete'; save()
    elif value['phase'] == 'policy-started':
        require(all(e['phase']=='acknowledged' for e in value['effects']) and len(value['effects'])==4,
                'native context host effect unknown; never replay or adopt inventory')
        before = value['steps'][0]['after']; after = a.registry.binding()
        changed(before,after)
        a.registry.authenticate_setup_transition(before,{DOCUMENT:after['deployment'],OPERATION:after['fence']},after)
        value['steps'].append(dict(before=before,documents={DOCUMENT:after['deployment'],OPERATION:after['fence']},after=after))
        value['current']=after; value['phase']='policy-complete'; save()
    if value['phase'] == 'policy-complete':
        owner_guard()
        value['result_preimage']=dict(schema_version=1,kind=RESULT,task_id=a.record['task_id'],execution=None,name='context-transition',
            record_digest=digest(a.record),intent=value['intent'],intent_digest=digest(value['claim']),steps=value['steps'],
            after=value['current'],effects=value['effects'],completed=a.clock())
        authenticate_steps(a.registry,value['claim'],value['result_preimage'])
        value['phase']='result-writing'; save()
        value['result']=_publish_native(c,a.record,value['result_preimage'],owner_guard); value['phase']='complete'; save()
    elif value['phase'] == 'result-writing':
        from registry import trial_reference
        revision = original(a).ref(trial_reference(value['result_preimage']))
        link = dict(kind=RESULT,revision=revision)
        require(read_native(original(a),link,a.record) == value['result_preimage'], 'native result acknowledgement remains unknown')
        value['result']=link; value['phase']='complete'; save()
    require(value['phase']=='complete' and read_native(original(a),value['result'],a.record)==value['result_preimage'],
            'native context completion remains pending')
    return copy.deepcopy(value['result'])


def read_refusal(a, api, job):
    from provenance import authenticated_document
    import service
    store = evidence_store(a,api,job,recovery=True)
    producer = store.terminal_job()
    require(producer['conclusion']=='success', 'exact completed native context producer required')
    require(all(not store._matches(k) for k in ('gate','dispatch','outcome','control-ready','not-submitted','host-denied')),
            'native context contradicts dispatch or ordinary receipts')
    receipt = store.find_for_recovery('trial-context-refusal')
    require(receipt is not None, 'positive native context no-dispatch evidence missing')
    value = store.authenticate(receipt)
    s = a.request['snapshot']
    locator = service._locator(api,a.binding['deployment'],s['run_id'],s['run_attempt'],'trial-broker-denial',s['pr'])
    proof = authenticated_document(api,a.binding['deployment'],locator,'trial-broker-denial',s['pr'],a.clock())
    require(proof['job_id']==job and proof['document']==dict(value,receipt=receipt,receipt_digest=digest(value)) and
            value['issued']<=proof['artifact_created']<=proof['job_completed']<deadline(a),
            'CLOSED native context denial differs')
    return dict(links=value['transition'],held=copy.deepcopy(a.registry.binding()),denial=locator,
                receipt=receipt,receipt_digest=digest(value))


def finalize(finalizer, a, operation_id, sequence, job, recovery):
    from trial_controller import authenticated
    authenticated(a)
    require(operation_id==a.request['operation_id'] and sequence==a.request['sequence'], 'exact retained context operation required')
    before = guard(a)
    require(before['fence']['schema_version']==3, 'unresolved native context handover required')
    observed = read_refusal(a,finalizer.authority,job)
    require(observed['held']==before, 'context moved during CLOSED recovery')
    issuance_guard(a)
    context=dict(observed,issuance={k:copy.deepcopy(a._context_issuance[k]) for k in ('claim','marker')})
    envelope = dict(schema_version=1,kind='native-broker-context-recovery',context=context,recovery=recovery,
                    old_operation_digest=digest(a.binding['fence']['pending']),configuration_digest=digest(before))
    terminal = dict(operation_id=operation_id,sequence=sequence,kind='not-submitted',receipt_digest=digest(envelope))
    configuration = dict(operation_id=before['fence']['pending']['operation_id'],sequence=sequence+1,
                         kind='configuration-complete',receipt_digest=digest(dict(envelope,old_terminal=terminal)))
    def fresh():
        require(guard(a)==before, 'context moved before paired settlement')
        require(read_refusal(a,finalizer.authority,job)==observed, 'context evidence moved before paired settlement')
        require(a.clock()<min(deadline(a),before['fence']['pending']['execution_deadline']), 'paired settlement expired')
    fresh()
    retained=a._context_store_document
    require(retained['value']['phase']=='marker-bound', 'paired terminal intent already attempted; never replay')
    a._context_store_document=a._context_store.write(retained,dict(retained['value'],phase='pair-started',
        envelope=envelope,terminals=[terminal,configuration],before=before))
    a._context_terminal_evidence=dict(copy.deepcopy(context),recovery=copy.deepcopy(recovery),pin=copy.deepcopy(finalizer.pin))
    if hasattr(a,'_seal'): a._seal=copy.deepcopy(a._state())
    return finalizer.registry.finalize_handover(before['branch_head'],terminal,configuration,fresh,a.clock)


def terminal_context(a, api, job, before):
    value = copy.deepcopy(a._context_terminal_evidence)
    require(value['held']==before and value['denial']['job_id']==job, 'retained paired terminal evidence differs')
    a.local_guard()
    issuance_guard(a)
    require(a.clock()<min(deadline(a),before['fence']['pending']['execution_deadline']), 'native terminal publication expired')
    return value


def reconstruct(original_registry, registry, record, case, document, baseline, clock, producer):
    """Read-only terminal/history authentication; never creates an admission."""
    from registry import OPERATION
    from trial_transition import read_native
    import provenance
    object_fields(document,('schema_version kind request_digest certificate_digest before after completed context').split(),
                  'native context terminal')
    require(document['schema_version']==1 and document['kind']=='trial-case-terminal' and
            document['request_digest']==digest(case['request']) and document['certificate_digest']==digest(case['certificate']),
            'native context terminal substituted original case')
    context=document['context']
    object_fields(context,('links','held','denial','receipt','receipt_digest','recovery','pin','issuance'),'native context terminal evidence')
    object_fields(context['links'],(INTENT,RESULT),'native context terminal publications')
    intent,result=(read_native(original_registry,context['links'][k],record) for k in (INTENT,RESULT))
    authenticate_intent(registry,record,case,intent,result)
    require(intent['case_digest']==digest(case) and intent['request_digest']==digest(case['request']) and
            result['intent']==context['links'][INTENT] and result['intent_digest']==digest(intent),
            'historical native context intent/result differs')
    old=registry.authenticate_setup_transition(baseline,{OPERATION:case['pending']},intent['before'])
    require(document['before']==old and result['after']==context['held'], 'historical context original ownership differs')
    authenticate_steps(registry,intent,result)
    proof=provenance.authenticated_document(registry.api,old['deployment'],context['denial'],'trial-broker-denial',case['request']['snapshot']['pr'],clock())
    denial=proof['document']
    keys=('configuration_revision','deployment_digest','deployment','fence')
    expected=dict(code='configuration_changed',observation=dict(before=digest({k:old[k] for k in keys}),
                                                              after=digest({k:result['after'][k] for k in keys})))
    receipt=dict(denial); receipt.pop('receipt'); receipt.pop('receipt_digest')
    require(denial['kind']=='trial-context-refusal' and denial['request_digest']==digest(case['request']) and
            denial['job_id']==intent['job_id']==proof['job_id'] and denial['operation_id']==case['request']['operation_id'] and
            denial['sequence']==case['request']['sequence'] and denial['prepared_digest']==intent['preloaded']['prepared_digest'] and
            denial['transition']==context['links'] and denial['refusal']==expected and
            denial['receipt']==context['receipt'] and denial['receipt_digest']==context['receipt_digest']==digest(receipt) and
            result['completed']<=denial['issued']<=proof['artifact_created']<=proof['job_completed']<=document['completed']<intent['expires'],
            'historical CLOSED context refusal differs')
    require(document['completed']<intent['operation']['execution_deadline'], 'historical paired settlement exceeded configuration deadline')
    from merge_receipts import ActionsReceipts
    store=ActionsReceipts._historical_context(registry.api,old,intent['job_id'],clock,
        {'trial-preloaded':intent['preloaded'],'trial-context-refusal':receipt})
    require(store.find_for_recovery('trial-preloaded')==intent['marker'] and
            store.authenticate(intent['marker'])==intent['preloaded'] and
            store.find_for_recovery('trial-context-refusal')==context['receipt'] and
            store.authenticate(context['receipt'])==receipt and
            all(not store._matches(k) for k in ('gate','dispatch','outcome','control-ready','not-submitted','host-denied')),
            'historical context artifacts changed or contradict no-dispatch')
    after=document['after']; held=context['held']; fence=copy.deepcopy(held['fence'])
    pair=after['fence']['completed'][-2:]
    require(len(pair)==2 and pair[0]['operation_id']==old['fence']['pending']['operation_id'] and
            pair[0]['sequence']==old['fence']['sequence'] and pair[0]['kind']=='not-submitted' and
            pair[1]['operation_id']==held['fence']['pending']['operation_id'] and pair[1]['sequence']==held['fence']['sequence'] and
            pair[1]['kind']=='configuration-complete', 'historical context paired terminal differs')
    policy=old['deployment']['policy']
    require(context['pin']==dict(authority_repository=policy['authority_repository'],authority_repository_id=policy['authority_repository_id'],
                workflow=policy['workflow'],workflow_sha=policy['workflow_sha']) and
            context['recovery']==dict(run_id=producer['run_id'],attempt=producer['attempt'],job_id=producer['job_id'],workflow_sha=policy['workflow_sha']) and
            producer['job_started']<=document['completed']<=producer['artifact_created']<=producer['job_completed'],
            'historical context recovery does not match the independently pinned CLOSED producer')
    issuance=context['issuance']
    object_fields(issuance,('claim','marker'),'historical original-job recovery attempt')
    claim=issuance['claim']
    object_fields(claim,('schema_version kind request_digest case_digest held_digest native recovery grant issued expires').split(),'historical recovery issuance claim')
    issued_proof=provenance.authenticated_document(registry.api,old['deployment'],issuance['marker'],
        'trial-context-recovery-intent',record['task_id'],clock())
    require(issued_proof['document']==claim and issued_proof['job_id']==producer['job_id'] and
            type(claim['schema_version']) is int and claim['schema_version']==1 and claim['kind']=='trial-context-recovery-intent' and
            claim['request_digest']==digest(case['request']) and claim['case_digest']==digest(case) and
            claim['held_digest']==digest(held) and claim['native']==context['links'] and claim['recovery']==context['recovery'] and
            claim['grant']==intent['preview']['recovery'] and claim['grant']['pin']==context['pin'] and
            claim['recovery']['run_id']==case['request']['snapshot']['run_id'] and claim['recovery']['attempt']==1 and
            issued_proof['job_started']<=claim['issued']<=issued_proof['artifact_created']<=document['completed']<claim['expires'] and
            claim['expires']==min(intent['expires'],intent['operation']['execution_deadline']),
            'historical finalizer issuance is not the one original-job protected attempt')
    base_context={k:v for k,v in context.items() if k not in ('recovery','pin')}
    envelope=dict(schema_version=1,kind='native-broker-context-recovery',context=base_context,recovery=context['recovery'],
                  old_operation_digest=digest(old['fence']['pending']),configuration_digest=digest(held))
    require(pair[0]['receipt_digest']==digest(envelope) and
            pair[1]['receipt_digest']==digest(dict(envelope,old_terminal=pair[0])),
            'historical paired receipts do not attest this exact authenticated context recovery')
    fence.pop('retained'); fence.update(schema_version=2,pending=None,completed=fence['completed']+pair)
    return registry.authenticate_setup_transition(held,{OPERATION:fence},after)


def observe_native(controller, prompt, locator, source=None, recovering=False):
    from trial_controller import Native
    from trial_case import read, case_baseline
    import provenance
    require(type(controller) is Native, 'actual native observation owner required')
    native=controller.candidates.native; c=native.provision
    journal=c.store(c.root/'trial-controller-context-transition'); retained=journal.read()
    require(retained is not None and retained['value']['phase']==('terminal' if recovering else 'bound') and retained['value']['prompt_digest']==digest(prompt),
            'exact native context terminal observation required')
    value=copy.deepcopy(retained['value'])
    publication=c.store(c.root/'trial-case-publication-context-transition').read()
    # The original completed interval may authenticate immutable history after
    # expiry. This read-only path never constructs live admission or writes CAS.
    clock=(lambda:value['terminal']['producer']['job_completed']) if recovering else c.clock
    case,record=read(c.session.registry,publication['value']['revision_bound'],clock)
    from trial_handoff import Native as NativeHandoff
    completed=NativeHandoff.worker_completion(native.registry,source or c.api,record,prompt,clock)
    require(completed['result']==case['worker']==value['worker'], 'native context observed worker changed')
    baseline=case_baseline(c.session.registry,native.registry,record,case,clock)
    proof=provenance.authenticated_document(native.registry.api,baseline['deployment'],locator,'trial-case-terminal',record['task_id'],clock())
    require(locator['run_id']==case['request']['snapshot']['run_id'] and locator['attempt']==case['request']['snapshot']['run_attempt'] and
            proof['job_started']<=proof['document']['completed']<=proof['artifact_created']<=proof['job_completed'],
            'native context terminal producer interval differs')
    binding=reconstruct(c.session.registry,native.registry,record,case,proof['document'],baseline,clock,proof)
    from authority_github import Readers,current_snapshot
    s=case['request']['snapshot']; reader=source or c.api
    require(current_snapshot(Readers(reader,native.registry.api,baseline['deployment']),baseline['deployment'],s['pr'],s['run_id'],s['run_attempt'])==s,
            'native context source changed before observation or recovery')
    from trial_transition import read_native
    intent,result=(read_native(c.session.registry,proof['document']['context']['links'][k],record) for k in (INTENT,RESULT))
    effective(reader,native.registry,intent,result)
    require(native.registry.binding()==binding and (recovering or c.clock()<record['expires']), 'native context terminal is no longer current')
    result=dict(binding=binding,locator=copy.deepcopy(locator),document=proof['document'],producer={k:v for k,v in proof.items() if k!='document'})
    if recovering:
        require(value['terminal']==result and journal.read()==retained, 'native context retained terminal changed')
    else:
        value.update(phase='terminal',terminal=result)
        journal.write(retained,value)
    return copy.deepcopy(result)


def recover_native(controller, prompt, source=None):
    native=controller.candidates.native; c=native.provision
    retained=c.store(c.root/'trial-controller-context-transition').read()
    require(retained is not None and retained['value']['phase']=='terminal' and retained['value']['prompt_digest']==digest(prompt),
            'native context terminal is not independently observed; preserve the fence')
    return observe_native(controller,prompt,retained['value']['terminal']['locator'],source,recovering=True)
