"""Held, finite same-PR baseline -> original-worker transition.

The baseline is a native source fixture, never a second model result. Its real
CLOSED verifier and issuer establish historical acceptance. Original reservations
and the original CLOSED worker are retained verbatim.
"""
import copy
import time
import secrets

import submission
from trusted_ci_policy import digest, object_fields, positive, require

STALE_CASES = ('new-head', 'new-base', 'policy-transition')


def historical(candidate):
    return candidate.get('transition', {}).get('intent', {}).get('phase') == 'prior'


def ownership(c, candidate):
    phase=candidate['transition']['intent']['phase']
    name = candidate['name']
    names=['trial-transition-'+name+('-fixture' if phase=='fixture' else '-prior')]
    if phase=='current':
        names+=['trial-transition-'+name+'-current','trial-controller-'+name+'-prior','trial-case-publication-'+name+'-prior']
        if 'context' in candidate: names+=['trial-context-'+name]
    documents={name:c.store(c.root/name).read() for name in names}
    require(all(value is not None for value in documents.values()), 'owned transition completion missing')
    current=documents['trial-transition-'+name+'-'+phase]
    require(digest(current['value'])==digest(dict(intent=candidate['transition']['intent'],phase='complete',result=candidate['submitted'])),
            'owned transition completion differs from admitted source')
    if phase=='current':
        previous=documents['trial-controller-'+name+'-prior']
        require(previous['value']['transition_ownership']==ownership(c,previous['value']['candidate']) and
                prior_entry(c,name)==candidate['transition']['intent']['prior'], 'owned historical transition changed')
    return documents


def guard(admission):
    original = admission.original if hasattr(admission, 'original') else admission.native.provision.session.registry
    links=getattr(admission,'_human_links',None)
    if links is not None:
        for link in links.values(): read_native(original,link,admission.record)
    links=getattr(admission,'_revocation_links',None)
    if links is not None:
        for link in links.values(): read_native(original,link,admission.record)
    if hasattr(admission,'native') and admission.candidate['name']=='human-update':
        c=admission.native.provision
        human=c.store(c.root/'trial-native-human').read()
        if human is not None:
            value=human['value']
            require(value['claim']['request_digest']==digest(admission.request), 'native human ownership substituted case')
            for key,preimage in (('intent','claim'),('completion','result')):
                if value[key] is not None:
                    require(digest(read_native(original,value[key],admission.record))==digest(value[preimage]),
                            'owned native human publication changed')
    transition = admission.candidate.get('transition')
    if transition is None: return
    from trial_case import history_guard
    i = transition['intent']
    require(positive(i['issued']) and i['issued'] <= admission.clock() < i['expires'], 'transition deadline expired')
    if i['phase'] == 'current':
        history_guard(original, admission.record, admission.value['history'] + [i['prior']],admission.clock,admission.registry.api)
        if hasattr(admission, 'native'):
            require(prior_entry(admission.native.provision,admission.candidate['name']) == i['prior'], 'owned historical terminal changed')


def acceptance(admission, authority):
    """Derive old issuer coordinates from its authenticated admission, not hints."""
    original = admission.original if hasattr(admission, 'original') else admission.native.provision.session.registry
    i = admission.candidate['transition']['intent']
    require(i['phase'] == 'current', 'only current transition consumes prior acceptance')
    value=prior_acceptance(original,authority,admission.record,i['prior'],admission.clock)
    require(digest(value)==digest(i['acceptance']), 'historical acceptance changed after transition')
    return value


def prior_acceptance(original, authority, record, entry, clock):
    from trial_case import read
    import provenance
    import service
    old, loaded = read(original, entry['revision'], clock)
    require(loaded == record and historical(old['candidate']), 'historical case differs')
    s, certificate = old['request']['snapshot'], old['certificate']
    d = record['trial']['deployment']
    location = service._locator(authority, d, s['run_id'], s['run_attempt'], 'evidence', s['pr'])
    proof = provenance.authenticated_document(authority, d, location, 'evidence', s['pr'], clock())
    task = dict(kind='native-trial-transition-task', submitted=old['candidate']['submitted'], worker=old['worker'],
                certificate_digest=digest(certificate), transition=old['candidate']['transition'])
    terminal = provenance.authenticated_document(authority, d, entry['terminal'], 'trial-case-terminal', record['task_id'], clock())
    return dict(deployment=d, snapshot=s, evidence=location, registry_revision=terminal['document']['before']['branch_head'],
        coordinates=dict(configuration_revision=certificate['configuration_revision'],operation=certificate['operation'],
            sequence=certificate['sequence'],issuer_installation_id=record['pair']['identities']['apps']['issuer']['installation_id'],
            evidence_job_id=proof['job_id'],evidence_digest=digest(proof['document']),task_digest=digest(task)))


def _intent(record, worker, reservation, history, phase, tree, previous, prior, issued, controls_digest, acceptance):
    return dict(kind='native-'+reservation['name']+'-transition', phase=phase, record_digest=digest(record),
        worker=worker, reservation=reservation, history=history, tree=tree, previous=previous,
        prior=prior, acceptance=acceptance, issued=issued, controls_digest=controls_digest, expires=min(record['expires'], record['trial']['deployment']['expires'],
            record['origin']['binding']['fence']['pending']['execution_deadline']))


def prior_entry(c, name='new-head'):
    from trial_controller import case_journal
    require(name in STALE_CASES, 'only named stale cases have prior acceptance')
    candidate = dict(name=name, transition=dict(intent=dict(phase='prior')))
    terminal = c.store(c.root / case_journal('trial-controller', candidate)).read()
    publication = c.store(c.root / case_journal('trial-case-publication', candidate)).read()
    require(terminal is not None and terminal['value']['phase'] == 'terminal' and
            historical(terminal['value']['candidate']) and publication is not None and
            publication['value']['phase'] == 'bound' and
            publication['value']['initial']['candidate'] == terminal['value']['candidate'] and
            publication['value']['initial']['request'] == terminal['value']['request'],
            'owned CLOSED historical preparation required')
    require(ownership(c,terminal['value']['candidate'])==terminal['value']['transition_ownership'],
            'owned historical mutation completion changed')
    from trial_case import read
    published,record=read(c.session.registry,publication['value']['revision_bound'],c.clock)
    require(dict(published,execution=None)==publication['value']['initial'] and
            all(published[k]==terminal['value'][k] for k in ('candidate','worker','certificate','request','pending','history')),
            'owned historical completion substituted authenticated publication')
    import provenance
    outcome=terminal['value']['terminal']
    proof=provenance.authenticated_document(c.api,record['trial']['deployment'],outcome['locator'],
                                          'trial-case-terminal',record['task_id'],c.clock())
    require(digest(outcome)==digest(dict(binding=proof['document']['after'],locator=outcome['locator'],
        document=proof['document'],producer={k:v for k,v in proof.items() if k!='document'})),
        'owned historical terminal differs from CLOSED producer')
    return dict(revision=publication['value']['revision_bound'], terminal=terminal['value']['terminal']['locator'])


def terminal_baseline(original, registry, record, history, entry, before, clock):
    from trial_case import read, _predecessor
    prior, loaded = read(original, entry['revision'], clock)
    require(loaded == record and historical(prior['candidate']) and prior['history'] == history,
            'historical preparation substituted original trial')
    return _predecessor(original, registry, record, history + [entry], len(history), before, clock)


def prepare(preparer, completed, reservation, history, before, phase, source, prompt, previous):
    """Native owner only; immutable intent precedes commit and atomic ref effects."""
    from trial_controller import owned_history, CASE_CHAIN, predecessor
    from trial_case import history_guard, read
    from coding_parent import _FencedSource
    from service import _source_token
    from controls import observe
    native, record = preparer.native, completed['record']
    c, worker = native.provision, completed['result']
    name = reservation['name']
    require((name in STALE_CASES and phase in ('prior', 'current') or name in ('human-update','revoked-qualification','context-transition') and phase=='fixture') and len(history) == CASE_CHAIN.index(name),
            'only the exact original stale transition is admitted')
    root = '/repos/' + before['deployment']['policy']['repository']
    prior = None
    accepted = None
    parent = reservation['submitted']
    context = None
    if phase == 'current':
        prior = prior_entry(c,name)
        before = terminal_baseline(c.session.registry, native.registry, record, history, prior, before, c.clock)
        parent = read(c.session.registry, prior['revision'], c.clock)[0]['candidate']['submitted']
        if name!='new-head':
            context=context_link(c,name)
            before=authenticate_context(c.session.registry,native.registry,record,
                dict(name=name,submitted=parent,context=context,transition=dict(intent=dict(prior=prior))),history,before,c.clock)
        accepted = prior_acceptance(c.session.registry,native.registry.api,record,prior,c.clock)
        from qualification_cases import HostCases
        probe=HostCases(native.registry,source,native.registry.api,record['pair']['identities'],None,None,None,c.clock)
        probe.binding,probe.d=before,before['deployment']
        probe._success(accepted['snapshot'],accepted['evidence'],accepted['coordinates'],accepted['deployment'])
    tree = (source.get(root + '/git/commits/' + record['pair']['fixture_revision'])['tree']['sha']
            if phase != 'current' else reservation['submitted']['tree'] if name=='new-head' else parent['tree'])
    journal = c.store(c.root / ('trial-transition-'+name+'-' + phase))
    document = journal.read()
    retained = copy.deepcopy(c.document)
    inventory=c.store(c.root/'trial-candidates').read()
    require(inventory==previous['value']['candidates'], 'original transition inventory changed')
    monotonic = time.monotonic()
    issued = c.clock() if document is None else document['value']['intent']['issued']
    facts=observe(c.api,before['deployment'])
    context_candidate=dict(context=context) if context is not None else None
    require(facts['base']==current_base(c.session.registry,record,history,context_candidate), 'transition control base differs')
    intent = _intent(record, worker, reservation, history, phase, tree, parent, prior, issued, digest(facts),accepted)

    def guard(force=False):
        require(positive(issued) and issued <= c.clock() < intent['expires'] and
                c.store(c.root / 'trial-workflow').read() == completed['retained'] and c.document == retained and
                c.store(c.root / 'trial').read() == retained and journal.read() == document,
                'transition ownership changed or expired')
        require(c.store(c.root/'trial-candidates').read()==inventory, 'transition candidate inventory changed')
        require(c.session.owner == record['origin']['owner'] and c.session.scope == record['origin']['scope'],
                'transition native owner changed')
        c.session._owned(record['origin']['binding'])
        c.session.registry.unchanged(record['origin']['binding']); native.registry.unchanged(before)
        require(c.store(c.root / ('trial-controller-'+predecessor(name))).read() == previous,
                'owned preceding completion changed')
        owned_history(c, previous['value'])
        history_guard(c.session.registry, record, history,c.clock,native.registry.api)
        if prior is not None:
            require(prior_entry(c,name) == prior, 'owned historical terminal changed')
            history_guard(c.session.registry, record, history + [prior],c.clock,native.registry.api)
            if force:
                require(digest(prior_acceptance(c.session.registry,native.registry.api,record,prior,c.clock))==digest(accepted),
                        'prior acceptance moved before source effect')
                probe._success(accepted['snapshot'],accepted['evidence'],accepted['coordinates'],accepted['deployment'])
        repo=source.get(root)
        require(positive(repo.get('id')) and repo['id']==before['deployment']['policy']['repository_id'] and
                repo.get('private') is True and positive(repo.get('owner',{}).get('id')) and
                repo['owner']['id']==record['pair']['identities']['owner_id'] and
                repo.get('default_branch')==before['deployment']['policy']['target'],
                'transition source identity or privacy changed')
        require(submission.existing_ref(source, root, before['deployment']['policy']['target']) == current_base(c.session.registry,record,history,context_candidate),
                'transition source base moved')

    guard()
    if document is None:
        document = journal.write(None, dict(intent=intent, phase='started', result=None))
        recovering = False
    else:
        require(digest(document['value']['intent']) == digest(intent) and
                document['value']['phase'] in ('started', 'complete'), 'exact retained transition intent required')
        recovering = True
    def authorize():
        require(issued <= c.clock() <= issued + 30 and time.monotonic() <= monotonic + 30,
                'original transition control window expired')
    with _source_token('coding', preparer.coding, native.registry.api, before['deployment'], record['pair']['identities'],
                       before['configuration_revision'], c.clock, preparer.token_factory, guard) as scoped:
        authorize(); guard()
        result = (parent if name!='new-head' and phase=='current' else
                  submission._advance(_FencedSource(scoped, guard, authorize), before['deployment'], parent,
                                      tree, digest(intent), issued, recover=recovering))
    guard()
    if document['value']['phase'] == 'complete':
        require(document['value']['result'] == result, 'completed transition result changed')
    else:
        document = journal.write(document, dict(intent=intent, phase='complete', result=result))
    guard()
    candidate=dict(reservation, submitted=result, transition=dict(intent=intent))
    if context is not None: candidate['context']=context
    return candidate, before


def validate(candidate, record, worker, history, source, original, registry, clock):
    """Fresh native/Hosted readers derive authority; caller bytes cannot choose it."""
    object_fields(candidate, ('name', 'submitted', 'controls_digest', 'transition')+
                  (('context',) if 'context' in candidate else ()), 'transition candidate')
    object_fields(candidate['transition'], ('intent',), 'transition provenance')
    i = candidate['transition']['intent']
    from registry import TRIAL
    contexts=[candidate] if 'context' in candidate else []
    for entry in history:
        old=original.blob(entry['revision'],TRIAL)[0]['candidate']
        if 'context' in old: contexts.append(old)
    for bound in contexts:
        validate_context_source(original,record,bound,source)
    object_fields(i, ('kind phase record_digest worker reservation history tree previous prior acceptance issued controls_digest expires').split(),
                  'source transition intent')
    from trial_controller import CASE_CHAIN
    name = candidate['name']
    require((name in STALE_CASES and i['phase'] in ('prior', 'current') or name in ('human-update','revoked-qualification','context-transition') and i['phase']=='fixture') and len(history) == CASE_CHAIN.index(name) and
            positive(i['issued']) and i['issued'] <= clock() < i['expires'], 'transition identity or deadline differs')
    reservation = i['reservation']
    require(reservation['name'] == name and reservation['controls_digest'] == candidate['controls_digest'] and
            reservation['submitted']['tree'] == worker['submitted']['tree'] and
            reservation['submitted']['export_digest'] == worker['submitted']['export_digest'],
            'transition original worker export differs')
    root = '/repos/' + record['trial']['deployment']['policy']['repository']
    tree = (source.get(root + '/git/commits/' + record['pair']['fixture_revision'])['tree']['sha']
            if i['phase'] != 'current' else reservation['submitted']['tree'])
    parent = reservation['submitted']
    accepted=None
    if i['phase'] != 'current':
        require(i['prior'] is None, 'historical preparation cannot inherit another acceptance')
    else:
        from trial_case import read
        prior, loaded = read(original, i['prior']['revision'], clock)
        require(loaded == record and historical(prior['candidate']) and prior['history'] == history and
                prior['candidate']['transition']['intent']['reservation'] == reservation,
                'current transition substituted historical reservation')
        parent = prior['candidate']['submitted']
        if name!='new-head':
            tree = parent['tree']
            validate(prior['candidate'],record,worker,history,source,original,registry,clock)
        accepted=prior_acceptance(original,registry.api,record,i['prior'],clock)
    require(isinstance(i['controls_digest'],str) and len(i['controls_digest'])==64 and
            digest(i) == digest(_intent(record, worker, reservation, history, i['phase'], tree, parent, i['prior'], i['issued'],i['controls_digest'],accepted)),
            'source transition substituted task, export or coordinates')
    result = (parent if name!='new-head' and i['phase']=='current' else
              submission._advance(source, record['trial']['deployment'], parent, tree, digest(i), i['issued'], recover=True))
    require(digest(result) == digest(candidate['submitted']), 'transition current submitted binding differs')
    return submission._read_tree(source, root, tree, lambda: require(clock() < i['expires'], 'transition expired'))


def current_base(original, record, history, candidate=None):
    """Only authenticated fixed context publications can change the original base."""
    if candidate is not None and 'context' in candidate:
        return original.blob(candidate['context']['revision'], __import__('registry').TRIAL)[0]['source']['base']
    for entry in reversed(history):
        prior = original.blob(entry['revision'], __import__('registry').TRIAL)[0]
        if 'context' in prior['candidate']:
            return current_base(original,record,[],prior['candidate'])
    return record['pair']['fixture_revision']


def current_deployment(original, record, history, candidate=None):
    if candidate is not None and 'context' in candidate:
        return read_native(original,candidate['context'],record)['after']['deployment']
    from registry import TRIAL
    for entry in reversed(history):
        prior=original.blob(entry['revision'],TRIAL)[0]
        if 'context' in prior['candidate']:
            return read_native(original,prior['candidate']['context'],record)['after']['deployment']
    return record['trial']['deployment']


def read_native(original, link, record):
    """Authenticate one create-only native claim against the original authority."""
    from registry import TRIAL, trial_reference
    from trusted_ci_policy import sha
    object_fields(link, ('kind','revision'), 'native publication link')
    require(link['kind'] in ('native-trial-context-intent','native-trial-context-complete',
            'native-trial-human-intent','native-trial-human-result',
            'native-trial-revocation-intent','native-trial-revocation-result',
            'native-trial-broker-context-intent','native-trial-broker-context-result') and sha(link['revision']),
            'fixed native publication required')
    value = original.blob(link['revision'],TRIAL)[0]
    require(value['kind']==link['kind'] and value['record_digest']==digest(record) and
            value['task_id']==record['task_id'] and value['execution'] is None,
            'native publication substituted original trial')
    before = record['origin']['binding']
    commit = original.api.get(original.root+'/git/commits/'+link['revision'])
    require(commit.get('sha')==link['revision'] and [v['sha'] for v in commit['parents']]==[before['branch_head']] and
            commit['message']=='AGENTIC conditional registry '+digest({TRIAL:value}) and
            original.ref(trial_reference(value))==link['revision'], 'native publication is not its exact conditional commit')
    def unrelated(entries): return {k:v for k,v in entries.items() if k!=TRIAL and not TRIAL.startswith(k+'/')}
    require(unrelated(original.tree(link['revision'])[1])==unrelated(original.tree(before['branch_head'])[1]),
            'native publication changed unrelated original data')
    original.unchanged(before)
    require(original.ref(trial_reference(value))==link['revision'], 'native publication moved during authentication')
    return value


def context_link(c, name):
    document=c.store(c.root/('trial-context-'+name)).read()
    require(document is not None and document['value']['phase']=='complete' and document['value']['completion'] is not None,
            'completed owned native context required')
    return copy.deepcopy(document['value']['completion'])


def authenticate_context(original, registry, record, candidate, history, before, clock):
    """Replay only the finite native configuration chain, never latest state."""
    from registry import OPERATION, DOCUMENT
    from operation_fence import operation, terminal
    from trusted_ci_policy import sha
    from reconcile import desired_rules
    require(registry.coordinates['repository']==record['pair']['authority_repository'] and
            registry.coordinates['repository_id']==record['pair']['authority_repository_id'] and
            registry.coordinates['registry_branch']=='agentic-registry','context substituted disposable registry')
    link=candidate['context']; value=read_native(original,link,record)
    object_fields(value,('schema_version kind task_id execution record_digest name intent before after steps source result completed').split(),
                  'native context completion')
    intent=read_native(original,value['intent'],record)
    object_fields(intent,('schema_version kind task_id execution record_digest name preview before prior history').split(), 'native context intent')
    preview=intent['preview']; name=candidate['name']
    object_fields(preview,('schema_version kind operator_id repository repository_id target authority_repository authority_repository_id '
        'adapter account configuration_revision deployment_digest workflow_sha record_digest name history prior base base_tree head '
        'rules foreign effects epoch issued expires').split(),'native context preview')
    from trial_case import read as read_case
    prior,_=read_case(original,intent['prior']['revision'],clock)
    require(type(value['schema_version']) is int and value['schema_version']==1 and type(intent['schema_version']) is int and
            intent['schema_version']==1 and name in ('new-base','policy-transition') and value['name']==intent['name']==name and
            digest(value['before'])==digest(before)==digest(intent['before']) and digest(intent['history'])==digest(history) and
            digest(intent['prior'])==digest(candidate['transition']['intent']['prior']) and
            positive(value['completed']) and positive(preview['issued']) and positive(preview['expires']) and
            preview['issued']<=value['completed']<=clock()<preview['expires']<=record['expires'],
            'finite context substituted original history, phase or deadline')
    p=before['deployment']['policy']
    require(type(preview['schema_version']) is int and preview['schema_version']==1 and
            preview['kind']=='native-trial-context-preview' and preview['name']==name and
            all(positive(preview[k]) for k in ('operator_id','repository_id','authority_repository_id')) and
            preview['record_digest']==digest(record) and digest(preview['history'])==digest(history) and
            digest(preview['prior'])==digest(intent['prior']) and preview['configuration_revision']==before['configuration_revision'] and
            preview['deployment_digest']==before['deployment_digest'] and preview['workflow_sha']==before['software_revision'] and
            all(preview[k]==p[k] for k in ('repository','repository_id','target','authority_repository','authority_repository_id')) and
            preview['adapter']==before['deployment']['adapter'] and preview['account']==before['deployment']['account'] and
            preview['head']==candidate['submitted']['head']==prior['request']['snapshot']['head'] and
            preview['base']==prior['request']['snapshot']['base'] and
            preview['expires']<=min(record['expires'],before['deployment']['expires'],
                record['origin']['binding']['fence']['pending']['execution_deadline']) and
            all(positive(preview['rules'][kind].get('id')) and
                digest({k:v for k,v in preview['rules'][kind].items() if k!='id'})==digest(desired_rules(before['deployment'])[kind]) and
                str(preview['rules'][kind]['id'])==before['deployment']['resources'][kind+'_rule'] for kind in ('acceptance','updates')),
            'native context preview differs from authenticated original coordinates or gates')
    source=value['source']
    object_fields(source,('base','tree','parents','intent_digest'),'native base append')
    require(all(sha(source[k]) for k in ('base','tree')) and source['base']!=preview['base'] and
            source['tree']==preview['base_tree'] and source['parents']==[preview['base']] and source['intent_digest']==digest(intent),
            'native context source provenance differs')
    steps=value['steps']
    require(isinstance(steps,list) and len(steps)==(3 if name=='policy-transition' else 2),'exact finite context transitions required')
    for step in steps: object_fields(step,('before','documents','after'),'native configuration step')
    op=operation(steps[0]['documents'][OPERATION]['pending'])
    require(op['kind']=='configuration' and op['scope_digest']==digest(preview['effects']) and
            op['configuration_revision']==before['configuration_revision'] and op['deployment_digest']==before['deployment_digest'] and
            op['workflow_sha']==before['software_revision'] and op['repository_id']==before['deployment']['policy']['repository_id'] and
            op['target']==before['deployment']['policy']['target'] and op['created']==preview['issued'] and
            op['execution_deadline']<=preview['expires'] and
            digest(op['setup'])==digest(dict(operator_id=preview['operator_id'],
                installation_id=record['pair']['identities']['apps']['admin']['installation_id'],approval_digest=digest(preview))),
            'native configuration acquisition differs')
    fence=copy.deepcopy(before['fence']); fence['sequence']+=1; fence['pending']=op
    expected=[{OPERATION:copy.deepcopy(fence)}]
    if name=='policy-transition':
        updated=value['after']['deployment']; desired=copy.deepcopy(before['deployment']); desired['generation']+=1
        desired['policy'].update(epoch=preview['epoch'],check_name='AGENTIC acceptance '+preview['epoch'])
        for key in ('acceptance','updates'):
            identity=updated['resources'].get(key+'_rule')
            require(isinstance(identity,str) and identity.isascii() and identity.isdigit() and int(identity)>0,
                    'new context registered rule identity unavailable')
            desired['resources'][key+'_rule']=identity
        require(digest(updated)==digest(desired) and preview['epoch']!=before['deployment']['policy']['epoch'],
                'policy context changed unapproved deployment fields')
        plan=value['result']['policy']['plan']
        require(value['result']['policy']['phase']=='complete' and digest(plan['before'])==digest(before['deployment']) and
                plan['configuration_revision']==before['configuration_revision'] and
                digest(plan['fence'])==digest(fence) and plan['branch_head']==steps[0]['after']['branch_head'] and
                digest(plan['old_controls'])==digest(preview['rules']) and digest(plan['foreign'])==digest(preview['foreign']) and
                digest(plan['new_controls'])==digest(desired_rules(plan['desired'])), 'native policy plan differs')
        fence['contexts'].append(dict(epoch=desired['policy']['epoch'],check_name=desired['policy']['check_name'],activated=False))
        expected.append({DOCUMENT:desired,OPERATION:copy.deepcopy(fence)})
    else:
        require(value['result']['policy'] is None and value['after']['deployment']==before['deployment'],
                'new-base changed deployment')
    receipt=terminal(dict(operation_id=op['operation_id'],sequence=fence['sequence'],kind='configuration-complete',
                          receipt_digest=digest(value['result'])))
    require(digest(value['result'])==digest(dict(source=source,intent=value['intent'],policy=value['result']['policy'],restored=True)),
            'context terminal result differs')
    fence['pending']=None; fence['completed'].append(receipt); expected.append({OPERATION:fence})
    current=before
    for step,documents in zip(steps,expected):
        require(digest(step['before'])==digest(current) and digest(step['documents'])==digest(documents),
                'native context substituted configuration step')
        current=registry.authenticate_setup_transition(current,documents,step['after'])
    require(digest(current)==digest(value['after']), 'native context completion differs from conditional history')
    return current


def context_guard(original, record, candidate):
    if 'context' not in candidate: return
    value=read_native(original,candidate['context'],record)
    read_native(original,value['intent'],record)


def validate_context_source(original, record, candidate, source):
    from datetime import datetime, timezone
    value=read_native(original,candidate['context'],record)
    intent=read_native(original,value['intent'],record); preview=intent['preview']
    admin=record['pair']['identities']['apps']['admin']; slug=admin['slug']; bot=str(admin['actor_id'])
    date=datetime.fromtimestamp(preview['issued'],timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    author=dict(name=slug+'[bot]',email=bot+'+'+slug+'[bot]@users.noreply.github.com',date=date)
    commit=source.get('/repos/'+preview['repository']+'/git/commits/'+value['source']['base'])
    require(commit.get('sha')==value['source']['base'] and commit['tree']['sha']==preview['base_tree'] and
            [v['sha'] for v in commit['parents']]==[preview['base']] and
            commit.get('message')=='AGENTIC disposable base transition '+digest(intent) and
            digest(commit.get('author'))==digest(author)==digest(commit.get('committer')),
            'native context base commit provenance differs')


def _publish_native(c, record, value, guard):
    from registry import TRIAL, trial_reference
    original = c.session.registry
    guard()
    original._replace(record['origin']['binding'], {TRIAL:value}, before_effect=guard, trial_branch=trial_reference(value))
    link = dict(kind=value['kind'],revision=original.ref(trial_reference(value)))
    require(digest(read_native(original,link,record))==digest(value), 'native publication completion differs')
    guard()
    return link


def cleanup_context(native, name, operator_api, admin_api, token_factory):
    """Reconstruct privilege removal without admitting expired execution."""
    from trial_handoff import Native
    from trial_setup import Provision
    from trial_case import history_guard
    from configuration import SetupConfigurationSession
    from reconcile import canonical
    from trusted_ci_github import HostRefusal
    require(type(native) is Native and type(native.provision) is Provision and name in ('new-base','policy-transition'), 'actual native cleanup owner required')
    c=native.provision; journal=c.store(c.root/('trial-context-'+name)); document=journal.read()
    require(document is not None, 'retained context cleanup required')
    v=copy.deepcopy(document['value']); r=v['record']; p=v['before']['deployment']['policy']; root='/repos/'+p['repository']
    require(native.registry.coordinates['repository']==r['pair']['authority_repository'] and
            native.registry.coordinates['repository_id']==r['pair']['authority_repository_id'] and
            native.registry.coordinates['registry_branch']=='agentic-registry','cleanup substituted disposable registry coordinates')
    def save():
        nonlocal document
        document=journal.write(document,v)
    def guard():
        require(journal.read()==document and c.document==v['provisioning'] and c.store(c.root/'trial').read()==v['provisioning'] and
                c.store(c.root/'trial-workflow').read()==v['workflow'] and c.store(c.root/'trial-candidates').read()==v['candidates'] and
                c.session.owner==r['origin']['owner'] and c.session.scope==r['origin']['scope'], 'native cleanup ownership changed')
        c.session.registry.unchanged(r['origin']['binding'])
        history_guard(c.session.registry,r,v['history']+[v['prior']],c.clock,native.registry.api)
        require(v['intent'] is not None, 'no published native allowance intent to clean')
        claim=read_native(c.session.registry,v['intent'],r)
        require(digest(claim['preview'])==digest(v['preview']) and digest(claim['before'])==digest(v['before']),
                'cleanup substituted original native intent')
        obj=SetupConfigurationSession.__new__(SetupConfigurationSession)
        obj.operator_api,obj.admin_api,obj.identities,obj.preview=operator_api,admin_api,r['pair']['identities'],v['preview']
        obj._native_identity(native.registry.read())
        repo=operator_api.get(root)
        require(positive(repo.get('id')) and repo['id']==p['repository_id'] and repo.get('private') is True and
                positive(repo.get('owner',{}).get('id')) and repo['owner']['id']==r['pair']['identities']['owner_id'] and
                repo.get('default_branch')==p['target'], 'native cleanup source identity changed')
    errors=[]
    for key in ('acceptance','updates'):
        try:
            guard()
            old=v['preview']['rules'][key]; temporary=copy.deepcopy(old)
            temporary['bypass_actors'].append(dict(actor_type='Integration',actor_id=r['pair']['identities']['apps']['admin']['id'],bypass_mode='always'))
            route=root+'/rulesets/'+str(old['id'])
            try:
                observed=dict(canonical(operator_api.get(route+'?includes_parents=true')),id=old['id'])
            except HostRefusal as error:
                require(error.status==404 and v['policy'] is not None and
                        v['effects'].get('restore-'+key,{}).get('phase')=='complete', 'owned cleanup gate unavailable')
                plan=v['policy']['plan']; deletion=v['effects'].get('policy-delete-'+key)
                require(deletion is not None and deletion['method']=='DELETE' and deletion['id']==old['id'] and
                        digest(plan['old_controls'])==digest(v['preview']['rules']) and
                        digest(plan['before'])==digest(v['before']['deployment']) and
                        plan['desired']['policy']['epoch']==v['preview']['epoch'], 'missing owned gate has no exact policy deletion intent')
                from transition import ContextTransition
                transition=ContextTransition(operator_api,native.registry,None)
                previous,new=transition.state(plan)
                require(previous[key] is None and all(new.values()),'missing owned gate precedes complete new protection')
                transition.effective(plan,new)
                continue
            if digest(observed)==digest(old): continue
            require(digest(observed)==digest(temporary) and 'allow-'+key in v['effects'] and
                    digest(v['effects']['allow-'+key]['before'])==digest(old) and
                    digest(v['effects']['allow-'+key]['after'])==digest(temporary), 'unrecognized owned rule blocks cleanup')
            restore='restore-'+key
            require(restore not in v['effects'], 'restore outcome unknown; reconcile read-only without replay')
            v['effects'][restore]=dict(before=temporary,after=old,phase='started'); save()
            guard()
            require(digest(dict(canonical(operator_api.get(route+'?includes_parents=true')),id=old['id']))==digest(temporary),
                    'owned temporary gate changed before cleanup')
            operator_api.fetch(route,method='PUT',data=canonical(old))
            require(digest(dict(canonical(operator_api.get(route+'?includes_parents=true')),id=old['id']))==digest(old),
                    'cleanup restoration outcome unknown')
            v['effects'][restore]['phase']='complete'; save()
        except Exception as error:
            errors.append(error)
    if v['credential'] is not None and not v['credential']['revoked']:
        try:
            guard(); scoped=token_factory(v['credential']['token'])
            if v['credential'].get('revoke_started'):
                try: scoped.pages('/installation/repositories','repositories')
                except HostRefusal as error: require(error.status==401,'capability cleanup observation unavailable')
                else: require(False,'capability revocation outcome unknown; never replay')
            else:
                v['credential']['revoke_started']=True; save()
                scoped.fetch('/installation/token',method='DELETE',binary=True)
            v['credential']['revoked']=True; save()
        except Exception as error:
            errors.append(error)
    if errors: raise errors[0]
    return dict(restored=True,execution_admitted=False,hosted_qualified=False,enforcement_active=False)


def configuration_preview(native, name, document):
    """No caller preview admits a configuration owner: rederive protected scope."""
    from trial_handoff import Native
    from trial_setup import Provision
    from trial_controller import owned_history
    from trial_case import history_guard
    require(type(native) is Native and type(native.provision) is Provision and name in ('new-base','policy-transition'), 'actual finite native configuration owner required')
    c = native.provision
    require(document is not None and c.store(c.root/('trial-context-'+name)).read()==document,
            'protected native transition approval changed')
    v = document['value']; r = v['record']; preview = v['preview']
    require(native.registry.coordinates['repository']==r['pair']['authority_repository'] and
            native.registry.coordinates['repository_id']==r['pair']['authority_repository_id'] and
            native.registry.coordinates['registry_branch']=='agentic-registry','native context registry coordinates differ')
    require(v['name']==name and v['approval']==digest(preview) and preview['kind']=='native-trial-context-preview' and
            preview['record_digest']==digest(r) and preview['history']==v['history'] and preview['prior']==v['prior'] and
            c.store(c.root/'trial-workflow').read()==v['workflow'] and c.store(c.root/'trial').read()==v['provisioning'] and
            c.document==v['provisioning'] and c.store(c.root/'trial-candidates').read()==v['candidates'],
            'original native configuration intent changed')
    require(c.session.owner==r['origin']['owner'] and c.session.scope==r['origin']['scope'], 'native transition owner changed')
    c.session._owned(r['origin']['binding']); c.session.registry.unchanged(r['origin']['binding'])
    require(prior_entry(c,name)==v['prior'], 'native transition historical acceptance changed')
    owned_history(c,c.store(c.root/('trial-controller-'+name+'-prior')).read()['value'])
    history_guard(c.session.registry,r,v['history']+[v['prior']],c.clock,native.registry.api)
    p = v['before']['deployment']['policy']
    require(digest(preview['effects'])==digest(dict(rules=[p['repository']],
            registry=[native.registry.coordinates['repository']+':'+native.registry.coordinates['registry_branch']],
            **{'qualification-fixture':[p['repository']]})) and
            all(preview[k]==p[k] for k in ('repository','repository_id','target','authority_repository','authority_repository_id')),
            'native transition scope differs')
    return preview, native.registry.binding(check_software=False)


def move_context(controller, prompt, name, operator_api, admin_api, approve, token_factory):
    """Native finite context movement. Every uncertain write recovers read-only.

    Rule PUTs use retained pre/postimages, not a fictitious HTTP CAS. Public live
    invocation remains held; an exclusive administrative writer is not inferred
    from the configuration fence or a caller assertion.
    """
    from configuration import SetupConfigurationSession
    from trial_controller import Native, owned_history
    from trial_handoff import Native as NativeHandoff
    from trial_candidates import Prepare
    from trial_case import baseline, history_guard
    from transition import ContextTransition
    from reconcile import canonical
    from registry import OPERATION, DOCUMENT
    from trusted_ci_policy import sha
    import bootstrap
    require(type(controller) is Native and type(controller.candidates) is Prepare and name in ('new-base','policy-transition'),
            'finite native disposable context owner required')
    native = controller.candidates.native
    require(type(native) is NativeHandoff, 'actual native context owner required')
    c, reg = native.provision, native.registry
    journal = c.store(c.root/('trial-context-'+name)); document = journal.read()
    prior = prior_entry(c,name)
    terminal = c.store(c.root/('trial-controller-'+name+'-prior')).read()['value']
    r, history = terminal['record'], terminal['history']
    require(reg.coordinates['repository']==r['pair']['authority_repository'] and
            reg.coordinates['repository_id']==r['pair']['authority_repository_id'] and
            reg.coordinates['registry_branch']=='agentic-registry','only the original disposable registry is admitted')
    require(terminal['prompt_digest']==digest(prompt) and historical(terminal['candidate']), 'exact prior context preparation required')
    before = terminal_baseline(c.session.registry,reg,r,history,prior,baseline(c.session.registry,reg,r,history,c.clock),c.clock)
    p = before['deployment']['policy']; root = '/repos/'+p['repository']
    if document is None:
        reg.unchanged(before); owned_history(c,terminal)
        accepted = prior_acceptance(c.session.registry,reg.api,r,prior,c.clock)
        from qualification_cases import HostCases
        probe = HostCases(reg,operator_api,reg.api,r['pair']['identities'],None,None,None,c.clock)
        probe.binding,probe.d = before,before['deployment']
        probe._success(accepted['snapshot'],accepted['evidence'],accepted['coordinates'],accepted['deployment'])
        identity = operator_api.get('/user')
        require(positive(identity.get('id')) and identity.get('type')=='User', 'native context human identity unavailable')
        oldbase = current_base(c.session.registry,r,history)
        commit = operator_api.get(root+'/git/commits/'+oldbase)
        require(commit.get('sha')==oldbase and sha(commit['tree']['sha']), 'native context source base differs')
        inventory = ContextTransition(operator_api,reg,None).inventory(before['deployment'])
        from reconcile import desired_rules
        owned = {k:next((v for v in inventory if str(v['id'])==before['deployment']['resources'].get(k+'_rule')),None)
                 for k in ('acceptance','updates')}
        require(all(owned.values()) and all(canonical(owned[k])==desired_rules(before['deployment'])[k] for k in owned),
                'exact original disposable gates required')
        issued = c.clock()
        preview = dict(schema_version=1,kind='native-trial-context-preview',operator_id=identity['id'],
            **{k:p[k] for k in ('repository','repository_id','target','authority_repository','authority_repository_id')},
            adapter=before['deployment']['adapter'],account=before['deployment']['account'],
            configuration_revision=before['configuration_revision'],deployment_digest=before['deployment_digest'],
            workflow_sha=before['software_revision'],record_digest=digest(r),name=name,history=history,prior=prior,
            base=oldbase,base_tree=commit['tree']['sha'],head=terminal['candidate']['submitted']['head'],
            rules=owned,foreign=[v for v in inventory if v['id'] not in {x['id'] for x in owned.values()}],
            effects=dict(rules=[p['repository']],registry=[reg.coordinates['repository']+':'+reg.coordinates['registry_branch']],
                         **{'qualification-fixture':[p['repository']]}),
            epoch=secrets.token_hex(16) if name=='policy-transition' else None,issued=issued,
            expires=min(r['expires'],before['deployment']['expires'],r['origin']['binding']['fence']['pending']['execution_deadline']))
        require(approve(copy.deepcopy(preview))==digest(preview), 'exact disposable context approval required')
        v = dict(name=name,record=r,history=history,prior=prior,before=before,preview=preview,approval=digest(preview),
            workflow=terminal['workflow'],candidates=terminal['candidates'],provisioning=terminal['provisioning'],
            phase='approved',steps=[],effects={},credential=None,intent=None,source=None,policy=None,terminal=None,completion=None)
        document = journal.write(None,v)
    else:
        v = copy.deepcopy(document['value'])
        require(v['record']==r and v['before']==before and v['history']==history and v['prior']==prior,
                'resume only the exact retained native context')
    preview = v['preview']; started = time.monotonic(); session = None
    public = dict(schema_version=1,kind='native-trial-context-intent',task_id=r['task_id'],execution=None,
                  record_digest=digest(r),name=name,preview=preview,before=before,prior=prior,history=history)
    accepted=prior_acceptance(c.session.registry,reg.api,r,prior,c.clock)
    from qualification_cases import HostCases
    probe=HostCases(reg,operator_api,reg.api,r['pair']['identities'],None,None,None,c.clock)
    probe.binding,probe.d=before,before['deployment']
    def save():
        nonlocal document
        document = journal.write(document,v)
        if session is not None: session.native_transition = (native,name,document)
    def identity():
        obj = SetupConfigurationSession.__new__(SetupConfigurationSession)
        obj.operator_api,obj.admin_api,obj.identities,obj.preview = operator_api,admin_api,r['pair']['identities'],preview
        return obj._native_identity(reg.read())
    def guard(cleanup=False):
        configuration_preview(native,name,document)
        if not cleanup:
            require(positive(preview['issued']) and preview['issued']<=c.clock()<preview['expires'], 'native context expired')
        current = v['steps'][-1]['after'] if v['steps'] else before
        reg.unchanged(current)
        identity()
        repo = operator_api.get(root)
        require(positive(repo.get('id')) and repo['id']==p['repository_id'] and repo.get('private') is True and
                positive(repo.get('owner',{}).get('id')) and repo['owner']['id']==r['pair']['identities']['owner_id'] and
                repo.get('default_branch')==p['target'], 'native transition source identity changed')
        history_guard(c.session.registry,r,history+[prior],c.clock,native.registry.api)
        if not cleanup:
            probe._success(accepted['snapshot'],accepted['evidence'],accepted['coordinates'],accepted['deployment'])
    def live_source(expected, cleanup=False):
        guard(cleanup)
        require(submission.existing_ref(operator_api,root,p['target'])==expected, 'native transition source moved')
    def append_step(old, documents, after):
        reg.authenticate_setup_transition(old,documents,after)
        v['steps'].append(dict(before=old,documents=documents,after=after)); save()
    def finish():
        if 'completion_preimage' not in v:
            v['completion_preimage']=dict(schema_version=1,kind='native-trial-context-complete',task_id=r['task_id'],execution=None,
                record_digest=digest(r),name=name,intent=v['intent'],before=before,after=v['steps'][-1]['after'],steps=copy.deepcopy(v['steps']),
                source=v['source'],result=v['terminal']['result'],completed=c.clock())
            save()
        complete=v['completion_preimage']
        if v['completion'] is None:
            from registry import trial_reference
            from trusted_ci_github import HostRefusal
            try:
                revision=c.session.registry.ref(trial_reference(complete))
            except HostRefusal as error:
                require(error.status==404,'native completion observation unavailable')
                require(not v.get('completion_attempted'),'native completion outcome unknown; never replay')
                v['completion_attempted']=True; save()
                v['completion']=_publish_native(c,r,complete,lambda:live_source(v['source']['base']))
            else:
                v['completion']=dict(kind=complete['kind'],revision=revision)
                require(digest(read_native(c.session.registry,v['completion'],r))==digest(complete),'native completion differs')
        v['phase']='complete'; save()
        return copy.deepcopy(v['completion'])
    if v['phase']=='approved':
        guard()
        setup = identity()
        issued = preview['issued']
        op = dict(kind='configuration',operation_id=secrets.token_hex(16),scope_digest=digest(preview['effects']),
            repository_id=p['repository_id'],target=p['target'],configuration_revision=before['configuration_revision'],
            deployment_digest=before['deployment_digest'],workflow_sha=before['software_revision'],run_id=None,attempt=None,
            created=issued,execution_deadline=min(preview['expires'],issued+300),pr=None,head=None,base=None,merge=None,setup=setup)
        fence = copy.deepcopy(before['fence']); fence['sequence']+=1; fence['pending']=op
        v.update(phase='acquire-started',operation=op,acquired_fence=fence); save()
        reg.acquire_operation(before['branch_head'],before['configuration_revision'],op,
                              before_effect=lambda:live_source(preview['base']))
    if v['phase']=='acquire-started':
        after = reg.authenticate_setup_progress(before,{OPERATION:v['acquired_fence']})
        append_step(before,{OPERATION:v['acquired_fence']},after)
        v['phase']='acquired'; save()
    if v['phase']=='complete':
        result = read_native(c.session.registry,v['completion'],r)
        require(result['after']==reg.binding(), 'completed native context moved')
        return copy.deepcopy(v['completion'])
    if v['terminal'] is not None and reg.binding()['fence']['pending'] is None:
        old=v['terminal']['before']; fence=copy.deepcopy(old['fence']); fence['pending']=None; fence['completed'].append(v['terminal']['receipt'])
        after=reg.authenticate_setup_progress(old,{OPERATION:fence})
        if not any(digest(step['before'])==digest(old) and digest(step['after'])==digest(after) for step in v['steps']):
            append_step(old,{OPERATION:fence},after)
        v['phase']='completion-started'; save()
        return finish()
    if v['source'] is None and v['phase']=='source-started':
        try:
            guard()
            v['source']=submission._advance_target(operator_api,before['deployment'],preview['base'],
                r['pair']['identities']['apps']['admin'],digest(public),preview['issued'],recover=True)
            save()
        finally:
            cleanup_context(native,name,operator_api,admin_api,token_factory)
            document=journal.read(); v=copy.deepcopy(document['value'])
    session = SetupConfigurationSession.trial_transition(native,name,operator_api,admin_api,document)
    if v['policy'] is not None and v['policy']['phase']=='started' and reg.read()!=before['deployment']:
        plan=v['policy']['plan']; old=v['policy']['before']
        # The existing engine takes its read-only exact-write recovery branch.
        ContextTransition(operator_api,reg,session).apply(plan,digest(plan))
        after=reg.binding(); documents={DOCUMENT:after['deployment'],OPERATION:after['fence']}
        if not any(digest(step['before'])==digest(old) and digest(step['after'])==digest(after) for step in v['steps']):
            append_step(old,documents,after)
        v['policy']['phase']='complete'; save()
    def rule_write(key, old, desired, cleanup=False):
        route = root+'/rulesets/'+str(old['id'])
        intended = dict(canonical(desired),id=old['id'])
        effect = v['effects'].get(key)
        observed = dict(canonical(operator_api.get(route+'?includes_parents=true')),id=old['id'])
        if effect is None:
            require(digest(observed)==digest(old), 'owned rule preimage changed')
            v['effects'][key]=dict(before=old,after=intended,phase='started'); save()
            if cleanup: guard(True)
            else:
                session.require_effect('rules',p['repository']); guard()
                require(c.clock()<=preview['issued']+30 and time.monotonic()<=started+30, 'native source window expired')
                inventory=ContextTransition(operator_api,reg,session).inventory(before['deployment'])
                expected=[]
                for kind,rule in preview['rules'].items():
                    previous=v['effects'].get('allow-'+kind)
                    expected.append(previous['after'] if previous is not None and previous['phase']=='complete' else rule)
                require(digest(inventory)==digest(sorted(expected+preview['foreign'],key=lambda x:x['id'])),
                        'owned or foreign rules changed before allowance')
            # All blocking ownership/inventory reads precede this final source read.
            if not cleanup:
                require(submission.existing_ref(operator_api,root,p['target'])==
                        (v['source']['base'] if v['source'] else preview['base']), 'source moved before rule effect')
            operator_api.fetch(route,method='PUT',data=canonical(desired))
        else:
            require(digest(effect['before'])==digest(old) and digest(effect['after'])==digest(intended),
                    'retained rule effect differs')
        observed = dict(canonical(operator_api.get(route+'?includes_parents=true')),id=old['id'])
        require(digest(observed)==digest(intended), 'rule outcome unknown or changed; never replay')
        if v['effects'][key]['phase']!='complete':
            v['effects'][key]['phase']='complete'; save()
    if v['intent'] is None:
        if v['phase']=='acquired':
            v['phase']='intent-started'; save()
            v['intent']=_publish_native(c,r,public,lambda:live_source(preview['base'])); save()
        else:
            from registry import trial_reference
            link=dict(kind=public['kind'],revision=c.session.registry.ref(trial_reference(public)))
            require(digest(read_native(c.session.registry,link,r))==digest(public), 'native context intent unknown')
            v['intent']=link; save()
    admin = r['pair']['identities']['apps']['admin']
    temporary = copy.deepcopy(preview['rules'])
    for rule in temporary.values():
        rule['bypass_actors'].append(dict(actor_type='Integration',actor_id=admin['id'],bypass_mode='always'))
    try:
        if v['source'] is None and v['phase']=='source-started':
            guard()
            v['source']=submission._advance_target(operator_api,before['deployment'],preview['base'],admin,
                                                   digest(public),preview['issued'],recover=True)
            save()
        if v['source'] is None:
            for key in ('acceptance','updates'):
                rule_write('allow-'+key,preview['rules'][key],temporary[key])
            if v['credential'] is None:
                require(v['phase']!='mint-started', 'native source token outcome unknown; never remint')
                v['phase']='mint-started'; save(); guard()
                token = bootstrap.installation_token(admin_api,admin['installation_id'],[p['repository_id']],dict(contents='write'))
                v['credential']=dict(token=token,revoked=False); save()
            scoped = token_factory(v['credential']['token'])
            require([x['id'] for x in scoped.pages('/installation/repositories','repositories')]==[p['repository_id']],
                    'native source capability scope differs')
            recovering = v['phase']=='source-started'
            if not recovering:
                v['phase']='source-started'; save()
            def source_guard(force=False):
                session.require_effect('qualification-fixture',p['repository']); guard()
                inventory=ContextTransition(operator_api,reg,session).inventory(before['deployment'])
                require(digest(inventory)==digest(sorted(list(temporary.values())+preview['foreign'],key=lambda x:x['id'])),
                        'temporary or foreign protections changed')
            def authorize():
                require(c.clock()<=preview['issued']+30 and time.monotonic()<=started+30,'native source window expired')
            def before_source():
                source_guard(); authorize()
            v['source']=submission._advance_target(scoped,before['deployment'],
                preview['base'],admin,digest(public),preview['issued'],recover=recovering,before_effect=before_source)
            save()
    finally:
        cleanup_context(native,name,operator_api,admin_api,token_factory)
        document=journal.read(); v=copy.deepcopy(document['value'])
        session.native_transition=(native,name,document)
    guard()
    require(v['source'] is not None, 'native source effect incomplete')
    inventory = ContextTransition(operator_api,reg,session).inventory(before['deployment'])
    if v['policy'] is None:
        require(digest(inventory)==digest(sorted(list(preview['rules'].values())+preview['foreign'],key=lambda x:x['id'])),
                'original protections were not restored')
    else:
        ContextTransition(operator_api,reg,session).state(v['policy']['plan'])
    if name=='policy-transition' and v['policy'] is None:
        desired=copy.deepcopy(before['deployment']); desired['generation']+=1
        desired['policy'].update(epoch=preview['epoch'],check_name='AGENTIC acceptance '+preview['epoch'])
        plan=ContextTransition(operator_api,reg,session).preview(desired)
        v['policy']=dict(plan=plan,phase='started',before=reg.binding()); save()
    if v['policy'] is not None and v['policy']['phase']=='started':
        old=v['policy']['before']
        plan=v['policy']['plan']
        def reconcile_policy_effect(key,effect):
            inventory=ContextTransition(operator_api,reg,session).inventory(before['deployment'])
            if effect['method']=='POST':
                matches=[x for x in inventory if x['name']==effect['body']['name']]
                require(len(matches)==1 and digest(canonical(matches[0]))==digest(effect['body']),
                        'policy create outcome unknown; never replay')
            else:
                require(not any(x['id']==effect['id'] for x in inventory),'policy deletion outcome unknown; never replay')
            v['effects'][key]['phase']='complete'; save()
        for key,effect in list(v['effects'].items()):
            if key.startswith('policy-') and effect['phase']=='started': reconcile_policy_effect(key,effect)
        pending=[]
        def before_policy(method_name,args,kwargs):
            previous,new=ContextTransition(operator_api,reg,session).state(plan)
            path=args[0]
            method='POST' if method_name=='post' else kwargs.get('method','GET')
            body=args[1] if method_name=='post' else kwargs.get('data')
            create=next((k for k in ('acceptance','updates') if method=='POST' and path==root+'/rulesets' and
                         digest(body)==digest(plan['new_controls'][k]) and new[k] is None),None)
            deleting=next((k for k in ('acceptance','updates') if method=='DELETE' and
                           path==root+'/rulesets/'+str(plan['old_controls'][k]['id']) and previous[k] is not None and
                           all(new.values())),None)
            require(create is not None or deleting is not None,'unexpected policy source mutation')
            key='policy-'+('create-'+create if create else 'delete-'+deleting)
            require(key not in v['effects'],'policy source effect already attempted; never replay')
            effect=(dict(method='POST',body=plan['new_controls'][create],phase='started') if create else
                    dict(method='DELETE',id=plan['old_controls'][deleting]['id'],phase='started'))
            v['effects'][key]=effect; save(); pending[:]=[key]
            live_source(v['source']['base'])
        def after_policy():
            guard()
            key,=pending
            reconcile_policy_effect(key,v['effects'][key]); pending.clear()
        from trial_configuration import _Boundary
        boundary=_Boundary(operator_api,after_policy,read_guard=guard,before_effect=guard,before_request=before_policy)
        write=session.write_configuration
        def write_once(expected,value):
            require(not v['policy'].get('registry_started'),'policy registry outcome unknown; never replay')
            v['policy']['registry_started']=True; save()
            write(expected,value)
        session.write_configuration=write_once
        ContextTransition(boundary,reg,session).apply(plan,digest(plan))
        after=reg.binding()
        documents={DOCUMENT:after['deployment'],OPERATION:after['fence']}
        if not any(digest(step['before'])==digest(old) and digest(step['after'])==digest(after) for step in v['steps']):
            append_step(old,documents,after)
        v['policy']['phase']='complete'; save()
    if v['terminal'] is None:
        old=reg.binding()
        public_result=dict(source=v['source'],intent=v['intent'],policy=v['policy'],restored=True)
        receipt=dict(operation_id=v['operation']['operation_id'],sequence=old['fence']['sequence'],
                     kind='configuration-complete',receipt_digest=digest(public_result))
        v['terminal']=dict(before=old,receipt=receipt,result=public_result); save()
        reg.finalize_operation(old['branch_head'],receipt,before_effect=lambda:live_source(v['source']['base']))
    if v['phase']!='completion-started':
        old=v['terminal']['before']; fence=copy.deepcopy(old['fence']); fence['pending']=None; fence['completed'].append(v['terminal']['receipt'])
        after=reg.authenticate_setup_progress(old,{OPERATION:fence}); append_step(old,{OPERATION:fence},after)
        v['phase']='completion-started'; save()
    return finish()
