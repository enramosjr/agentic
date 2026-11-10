"""Held, finite same-PR baseline -> original-worker transition.

The baseline is a native source fixture, never a second model result. Its real
CLOSED verifier and issuer establish historical acceptance. Original reservations
and the original CLOSED worker are retained verbatim.
"""
import copy
import time

import submission
from trusted_ci_policy import digest, object_fields, positive, require


def historical(candidate):
    return candidate.get('transition', {}).get('intent', {}).get('phase') == 'prior'


def ownership(c, candidate):
    phase=candidate['transition']['intent']['phase']
    names=['trial-transition-new-head-prior']
    if phase=='current':
        names+=['trial-transition-new-head-current','trial-controller-new-head-prior','trial-case-publication-new-head-prior']
    documents={name:c.store(c.root/name).read() for name in names}
    require(all(value is not None for value in documents.values()), 'owned transition completion missing')
    current=documents['trial-transition-new-head-'+phase]
    require(digest(current['value'])==digest(dict(intent=candidate['transition']['intent'],phase='complete',result=candidate['submitted'])),
            'owned transition completion differs from admitted source')
    if phase=='current':
        previous=documents['trial-controller-new-head-prior']
        require(previous['value']['transition_ownership']==ownership(c,previous['value']['candidate']) and
                prior_entry(c)==candidate['transition']['intent']['prior'], 'owned historical transition changed')
    return documents


def guard(admission):
    transition = admission.candidate.get('transition')
    if transition is None: return
    from trial_case import history_guard
    original = admission.original if hasattr(admission, 'original') else admission.native.provision.session.registry
    i = transition['intent']
    require(positive(i['issued']) and i['issued'] <= admission.clock() < i['expires'], 'transition deadline expired')
    if i['phase'] == 'current':
        history_guard(original, admission.record, admission.value['history'] + [i['prior']])
        if hasattr(admission, 'native'):
            require(prior_entry(admission.native.provision) == i['prior'], 'owned historical terminal changed')


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
    return dict(kind='native-new-head-transition', phase=phase, record_digest=digest(record),
        worker=worker, reservation=reservation, history=history, tree=tree, previous=previous,
        prior=prior, acceptance=acceptance, issued=issued, controls_digest=controls_digest, expires=min(record['expires'], record['trial']['deployment']['expires'],
            record['origin']['binding']['fence']['pending']['execution_deadline']))


def prior_entry(c):
    from trial_controller import case_journal
    candidate = dict(name='new-head', transition=dict(intent=dict(phase='prior')))
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
    from trial_controller import owned_history
    from trial_case import history_guard, read
    from coding_parent import _FencedSource
    from service import _source_token
    from controls import observe
    native, record = preparer.native, completed['record']
    c, worker = native.provision, completed['result']
    require(reservation['name'] == 'new-head' and phase in ('prior', 'current') and len(history) == 9,
            'only the tenth original transition is admitted')
    root = '/repos/' + before['deployment']['policy']['repository']
    prior = None
    accepted = None
    parent = reservation['submitted']
    if phase == 'current':
        prior = prior_entry(c)
        before = terminal_baseline(c.session.registry, native.registry, record, history, prior, before, c.clock)
        parent = read(c.session.registry, prior['revision'], c.clock)[0]['candidate']['submitted']
        accepted = prior_acceptance(c.session.registry,native.registry.api,record,prior,c.clock)
        from qualification_cases import HostCases
        probe=HostCases(native.registry,source,native.registry.api,record['pair']['identities'],None,None,None,c.clock)
        probe.binding,probe.d=before,before['deployment']
        probe._success(accepted['snapshot'],accepted['evidence'],accepted['coordinates'])
    tree = (source.get(root + '/git/commits/' + record['pair']['fixture_revision'])['tree']['sha']
            if phase == 'prior' else reservation['submitted']['tree'])
    journal = c.store(c.root / ('trial-transition-new-head-' + phase))
    document = journal.read()
    retained = copy.deepcopy(c.document)
    inventory=c.store(c.root/'trial-candidates').read()
    require(inventory==previous['value']['candidates'], 'original transition inventory changed')
    monotonic = time.monotonic()
    issued = c.clock() if document is None else document['value']['intent']['issued']
    facts=observe(c.api,before['deployment'])
    require(facts['base']==record['pair']['fixture_revision'], 'transition control base differs')
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
        require(c.store(c.root / 'trial-controller-spoofed-source').read() == previous,
                'owned ninth completion changed')
        owned_history(c, previous['value'])
        history_guard(c.session.registry, record, history)
        if prior is not None:
            require(prior_entry(c) == prior, 'owned historical terminal changed')
            history_guard(c.session.registry, record, history + [prior])
            if force:
                require(digest(prior_acceptance(c.session.registry,native.registry.api,record,prior,c.clock))==digest(accepted),
                        'prior acceptance moved before source effect')
                probe._success(accepted['snapshot'],accepted['evidence'],accepted['coordinates'])
        repo=source.get(root)
        require(positive(repo.get('id')) and repo['id']==before['deployment']['policy']['repository_id'] and
                repo.get('private') is True and positive(repo.get('owner',{}).get('id')) and
                repo['owner']['id']==record['pair']['identities']['owner_id'] and
                repo.get('default_branch')==before['deployment']['policy']['target'],
                'transition source identity or privacy changed')
        require(submission.existing_ref(source, root, before['deployment']['policy']['target']) == record['pair']['fixture_revision'],
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
        result = submission._advance(_FencedSource(scoped, guard, authorize), before['deployment'], parent,
                                     tree, digest(intent), issued, recover=recovering)
    guard()
    if document['value']['phase'] == 'complete':
        require(document['value']['result'] == result, 'completed transition result changed')
    else:
        document = journal.write(document, dict(intent=intent, phase='complete', result=result))
    guard()
    return dict(reservation, submitted=result, transition=dict(intent=intent)), before


def validate(candidate, record, worker, history, source, original, registry, clock):
    """Fresh native/Hosted readers derive authority; caller bytes cannot choose it."""
    object_fields(candidate, ('name', 'submitted', 'controls_digest', 'transition'), 'transition candidate')
    object_fields(candidate['transition'], ('intent',), 'transition provenance')
    i = candidate['transition']['intent']
    object_fields(i, ('kind phase record_digest worker reservation history tree previous prior acceptance issued controls_digest expires').split(),
                  'source transition intent')
    require(candidate['name'] == 'new-head' and i['phase'] in ('prior', 'current') and len(history) == 9 and
            positive(i['issued']) and i['issued'] <= clock() < i['expires'], 'transition identity or deadline differs')
    reservation = i['reservation']
    require(reservation['name'] == 'new-head' and reservation['controls_digest'] == candidate['controls_digest'] and
            reservation['submitted']['tree'] == worker['submitted']['tree'] and
            reservation['submitted']['export_digest'] == worker['submitted']['export_digest'],
            'transition original worker export differs')
    root = '/repos/' + record['trial']['deployment']['policy']['repository']
    tree = (source.get(root + '/git/commits/' + record['pair']['fixture_revision'])['tree']['sha']
            if i['phase'] == 'prior' else reservation['submitted']['tree'])
    parent = reservation['submitted']
    accepted=None
    if i['phase'] == 'prior':
        require(i['prior'] is None, 'historical preparation cannot inherit another acceptance')
    else:
        from trial_case import read
        prior, loaded = read(original, i['prior']['revision'], clock)
        require(loaded == record and historical(prior['candidate']) and prior['history'] == history and
                prior['candidate']['transition']['intent']['reservation'] == reservation,
                'current transition substituted historical reservation')
        parent = prior['candidate']['submitted']
        accepted=prior_acceptance(original,registry.api,record,i['prior'],clock)
    require(isinstance(i['controls_digest'],str) and len(i['controls_digest'])==64 and
            digest(i) == digest(_intent(record, worker, reservation, history, i['phase'], tree, parent, i['prior'], i['issued'],i['controls_digest'],accepted)),
            'source transition substituted task, export or coordinates')
    result = submission._advance(source, record['trial']['deployment'], parent, tree, digest(i), i['issued'], recover=True)
    require(digest(result) == digest(candidate['submitted']), 'transition current submitted binding differs')
    return submission._read_tree(source, root, tree, lambda: require(clock() < i['expires'], 'transition expired'))
