"""Finite native negative specimens over existing conditional source primitives."""
import base64
import copy

import submission
from trial_specimen import RECIPES, manifest, mutate, validate_mutation
from trusted_ci_policy import digest, object_fields, positive, require

INTENT = 'native-trial-mutation-intent'
RESULT = 'native-trial-mutation-result'


def selected(candidate):
    return candidate.get('transition', {}).get('intent', {}).get('phase') == 'negative'


def ownership(c, candidate):
    document = c.store(c.root / ('trial-mutation-'+candidate['name'])).read()
    require(document is not None and document['value']['phase'] == 'complete' and
            document['value']['claim'] == candidate['transition']['intent'] and
            document['value']['links'] == candidate['transition']['links'] and
            document['value']['result'] == candidate['submitted'], 'owned negative mutation changed')
    return {'trial-mutation-'+candidate['name']: document}


def guard(a):
    from trial_transition import read_native
    original = a.original if hasattr(a, 'original') else a.native.provision.session.registry
    for link in a.candidate['transition']['links'].values(): read_native(original, link, a.record)


def prepare(a, preparer, approve):
    from trial_controller import Admission
    from trial_transition import _publish_native
    from service import _source_token
    require(type(a) is Admission and a.candidate['name'] in RECIPES and a.value['phase'] == 'ready',
            'only an owned ready negative reservation may be mutated')
    if selected(a.candidate):
        ownership(a.native.provision, a.candidate)
        return
    a.guard()
    c = a.native.provision
    journal = c.store(c.root / ('trial-mutation-'+a.candidate['name']))
    document = journal.read()
    reservation = copy.deepcopy(a.candidate)
    root = '/repos/'+a.binding['deployment']['policy']['repository']
    expires = min(a.record['expires'], a.binding['deployment']['expires'],
                  a.record['origin']['binding']['fence']['pending']['execution_deadline'])
    def local():
        a.local_guard()
        require(journal.read() == document and a.clock() < expires, 'negative mutation ownership changed or expired')
    from coding_parent import _FencedSource
    def no_write():
        require(False, 'negative specimen observation is read-only')
    def read_tree(api, tree, full):
        # No effect occurs in this immutable-object scan. Authenticate the
        # complete live authority at both boundaries, and ownership/time around
        # every blocking read; no observation or authority survives the batch.
        full()
        source = _FencedSource(api, lambda force=False:local(), no_write)
        files = submission._read_tree(source, root, tree, local)
        full()
        return files
    original = read_tree(a.source, reservation['submitted']['tree'], a.guard)
    require(original == a.worker['files'], 'negative specimen original export differs from CLOSED worker')
    files = mutate(original, a.candidate['name'])
    issued = a.clock() if document is None else document['value']['claim']['issued']
    preview = dict(kind='native-negative-mutation-preview', record_digest=digest(a.record),
        worker=a.value['worker'], reservation=reservation, history=a.value['history'], baseline=a.binding,
        before=manifest(original), after=manifest(files), issued=issued,
        expires=expires)
    claim = dict(schema_version=1, kind=INTENT, task_id=a.record['task_id'], execution=None,
        name=a.candidate['name'], record_digest=digest(a.record), phase='negative', reservation=reservation,
        previous=reservation['submitted'], issued=issued, expires=preview['expires'], preview=preview,
        approval=digest(preview))
    def check():
        a.guard()
        require(journal.read() == document and a.clock() < claim['expires'], 'negative mutation ownership changed or expired')
        require(submission.existing_ref(a.source, root, a.binding['deployment']['policy']['target']) ==
                __import__('trial_transition').current_base(c.session.registry,a.record,a.value['history']),
                'negative mutation target moved')
        a.local_guard()
    check()
    fresh = document is None
    if fresh:
        require(callable(approve) and approve(copy.deepcopy(preview)) == digest(preview), 'exact negative mutation approval required')
        check()
        document = journal.write(None, dict(phase='approved', claim=claim, links={}, tree=None, result=None))
    require(document['value']['claim'] == claim, 'negative mutation approval substituted original inputs')
    state = copy.deepcopy(document['value'])
    def save():
        nonlocal document
        check(); document = journal.write(document, state)
    if fresh:
        # Intent is retained before native publication, mint or source objects.
        state['phase'] = 'publication-started'; save()
        state['links'][INTENT] = _publish_native(c,a.record,claim,check)
        state['phase'] = 'materialization-started'; save()
        with _source_token('coding',preparer.coding,a.registry.api,a.binding['deployment'],a.record['pair']['identities'],
                           a.binding['configuration_revision'],a.clock,preparer.token_factory,check) as scoped:
            entries = []
            after = manifest(files)
            before = manifest(original)
            for path, item in sorted(after.items()):
                if before.get(path) != item:
                    check()
                    blob = scoped.post(root+'/git/blobs',dict(encoding='base64',content=base64.b64encode(files[path]['content']).decode()))['sha']
                    require(blob == item['sha'], 'negative mutation blob differs')
                entries.append(dict(path=path,mode=item['mode'],type='blob',sha=item['sha']))
            check()
            state['tree'] = scoped.post(root+'/git/trees',dict(tree=entries))['sha']; save()
            validate_mutation(original,read_tree(scoped,state['tree'],check),a.candidate['name'])
            state['phase'] = 'advance-started'; save()
            def source_guard(force=False):
                if force: check()
                else: local()
            check()
            state['result'] = submission._advance(_FencedSource(scoped,source_guard,check),a.binding['deployment'],
                reservation['submitted'],state['tree'],digest(claim),issued)
            check()
            state['phase'] = 'advanced'; save()
    else:
        require(state['phase'] in ('advance-started','advanced','result-started','complete') and state['tree'] is not None,
                'negative mutation effect remains unknown; no recreation or coding remint')
        observed = submission._advance(a.source,a.binding['deployment'],reservation['submitted'],state['tree'],digest(claim),issued,recover=True)
        require(state['result'] in (None,observed), 'negative mutation result changed')
        state['result'] = observed
    result = dict(schema_version=1,kind=RESULT,task_id=a.record['task_id'],execution=None,name=a.candidate['name'],
                  record_digest=digest(a.record),intent=state['links'][INTENT],intent_digest=digest(claim),
                  submitted=state['result'],completed=a.clock())
    if RESULT not in state['links']:
        require(fresh or state['phase'] not in ('result-started','complete'), 'negative result publication remains unknown')
        state['phase'] = 'result-started'; save()
        state['links'][RESULT] = _publish_native(c,a.record,result,check)
    state['phase'] = 'complete'; save()
    candidate = dict(reservation,submitted=state['result'],transition=dict(intent=claim,links=state['links']))
    a.value.update(candidate=candidate,transition_ownership=ownership(c,candidate))
    a.candidate = copy.deepcopy(candidate)
    a._save()
    a.guard()


def authenticate(candidate, record, worker, history, original, clock, before=None):
    from trial_transition import read_native
    require(candidate['name'] in RECIPES and selected(candidate), 'fixed native negative mutation required')
    object_fields(candidate,('name','submitted','controls_digest','transition')+
                  (('eligibility',) if 'eligibility' in candidate else ()),'negative specimen candidate')
    t = candidate['transition']; object_fields(t,('intent','links'),'negative mutation provenance')
    object_fields(t['links'],(INTENT,RESULT),'negative mutation publications')
    claim = read_native(original,t['links'][INTENT],record)
    result = read_native(original,t['links'][RESULT],record)
    object_fields(claim,('schema_version kind task_id execution name record_digest phase reservation previous issued expires preview approval').split(),
                  'native negative mutation intent')
    object_fields(result,('schema_version kind task_id execution name record_digest intent intent_digest submitted completed').split(),
                  'native negative mutation result')
    require(type(claim['schema_version']) is int and claim['schema_version']==1 and
            type(result['schema_version']) is int and result['schema_version']==1 and
            claim['kind']==INTENT and result['kind']==RESULT and claim['execution'] is result['execution'] is None and
            claim['task_id']==result['task_id']==record['task_id'] and claim['name']==result['name']==candidate['name'] and
            result['record_digest']==digest(record) and all(positive(v) for v in (claim['issued'],claim['expires'],result['completed'])) and
            claim == t['intent'] and claim['phase'] == 'negative' and claim['name'] == candidate['name'] and
            claim['record_digest'] == digest(record) and claim['issued'] <= result['completed'] <= clock() < claim['expires'] and
            result['intent'] == t['links'][INTENT] and result['intent_digest'] == digest(claim) and
            result['submitted'] == candidate['submitted'], 'negative mutation immutable history differs')
    p = claim['preview']; reservation = claim['reservation']
    require(candidate.get('eligibility')==reservation.get('eligibility'),'negative specimen lost original eligibility binding')
    object_fields(p,('kind record_digest worker reservation history baseline before after issued expires').split(),'native negative mutation preview')
    baseline=p['baseline']
    end=min(record['expires'],baseline['deployment']['expires'],record['origin']['binding']['fence']['pending']['execution_deadline'])
    require(claim['expires']==end and (before is None or baseline==before), 'negative mutation baseline or original deadline differs')
    require(p['kind'] == 'native-negative-mutation-preview' and p['record_digest'] == digest(record) and
            p['worker'] == worker and p['reservation'] == reservation and p['history'] == history and
            p['issued'] == claim['issued'] and p['expires'] == claim['expires'] and claim['approval'] == digest(p) and
            reservation['name'] == candidate['name'] and reservation['controls_digest'] == candidate['controls_digest'] and
            claim['previous'] == reservation['submitted'] and
            reservation['submitted']['tree'] == worker['submitted']['tree'] and
            reservation['submitted']['export_digest'] == worker['submitted']['export_digest'], 'negative approval substituted original export')
    require(digest(p['before'])==worker['submitted']['export_digest'], 'negative original manifest differs from CLOSED export')
    after=copy.deepcopy(p['before']); after.update(manifest(RECIPES[candidate['name']]))
    require(p['after']==after and candidate['submitted']['export_digest']==digest(after) and
            all(candidate['submitted'][k]==reservation['submitted'][k] for k in ('pr','task_id','branch','bot_id','app_id','run_id','attempt')) and
            candidate['submitted']['head']!=reservation['submitted']['head'], 'negative manifest or reserved identity differs')
    return claim,result


def validate(candidate, record, worker, history, source, original, registry, clock, before=None):
    if before is None:
        from trial_case import baseline
        before=baseline(original,registry,record,history,clock)
    claim,result=authenticate(candidate,record,worker,history,original,clock,before)
    p=claim['preview']; reservation=claim['reservation']
    root = '/repos/'+record['trial']['deployment']['policy']['repository']
    before = submission._read_tree(source,root,reservation['submitted']['tree'],lambda:require(clock()<claim['expires'],'negative mutation expired'))
    after = submission._read_tree(source,root,candidate['submitted']['tree'],lambda:require(clock()<claim['expires'],'negative mutation expired'))
    before_manifest,after_manifest=manifest(before),manifest(after)
    # authenticate already binds the exact recipe delta between these manifests.
    require(before_manifest == p['before'] and after_manifest == p['after'], 'negative mutation manifest differs')
    from coding_parent import _FencedSource
    def clock_guard(force=False): require(clock()<claim['expires'],'negative mutation expired')
    def deny_write(): require(False,'negative mutation validation is read-only')
    readonly=_FencedSource(source,clock_guard,deny_write)
    head,root=submission._advance_head(readonly,record['trial']['deployment'],reservation['submitted'],candidate['submitted']['tree'],
                                      digest(claim),claim['issued'],recover=True)
    submission._advance_ref(readonly,root,reservation['submitted'],head)
    clock_guard()
    expected=dict(reservation['submitted'],head=head,tree=candidate['submitted']['tree'],export_digest=digest(after_manifest))
    require(expected == candidate['submitted'], 'negative mutation current head differs')
    return after
