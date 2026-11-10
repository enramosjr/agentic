"""Held read-only case handoff into fresh, pinned producer contexts.

Only authenticated registry records and CLOSED consumption artifacts cross the
boundary. Native sessions, journals and keys stay in the native coordinator.
This is a source/local-fixture composition, not hosted qualification.
"""
import copy

import authority_release
import provenance
from registry import Registry, OPERATION, TRIAL, trial_reference
from setup import TrialReadStaging
from trial_controller import Admission, CASE_CHAIN
from trial_handoff import Native as NativeHandoff, read as read_origin
from trusted_ci_policy import digest, object_fields, require, sha


def baseline(original, registry, record, history, clock):
    """Compose the exact native host predecessors, never latest state."""
    require(isinstance(history,list) and len(history)<len(CASE_CHAIN), 'bounded native progression history required')
    before=copy.deepcopy(record['trial'])
    for index in range(len(history)):
        before=_predecessor(original,registry,record,history,index,before,clock)
    return before


def _predecessor(original,registry,record,history,index,before,clock):
    entry=history[index]
    object_fields(entry,('revision','terminal'),'prior native case')
    prior,loaded=read(original,entry['revision'],clock)
    require(loaded==record and prior['history']==history[:index] and prior['candidate']['name']==CASE_CHAIN[index] and
            prior['execution'] is not None and prior['launch'] is not None, 'exact first executed host case required')
    from types import SimpleNamespace
    Admission._retained(SimpleNamespace(binding=before,record=record,value=prior,candidate=prior['candidate']))
    location=entry['terminal']; s=prior['request']['snapshot']
    require(location['run_id']==s['run_id'] and location['attempt']==s['run_attempt'], 'prior terminal run differs')
    proof=provenance.authenticated_document(registry.api,before['deployment'],location,
                                          'trial-case-terminal',record['task_id'],clock())
    value=proof['document']
    object_fields(value,('schema_version kind request_digest certificate_digest before after completed').split(),'prior closed terminal')
    require(type(value['schema_version']) is int and value['schema_version']==1 and value['kind']=='trial-case-terminal' and
            value['request_digest']==digest(prior['request']) and value['certificate_digest']==digest(prior['certificate']) and
            type(value['completed']) is int and proof['job_started']<=value['completed']<=proof['artifact_created']<=proof['job_completed'],
            'prior terminal substituted case or interval')
    pending=registry.authenticate_setup_transition(before,{OPERATION:prior['pending']},value['before'])
    from operation_fence import terminal
    receipt=terminal(value['after']['fence']['completed'][-1])
    require(receipt['kind']=='not-submitted' and receipt['operation_id']==prior['request']['operation_id'] and
            receipt['sequence']==prior['request']['sequence'], 'prior host terminal operation differs')
    fence=copy.deepcopy(pending['fence']); fence['pending']=None; fence['completed'].append(receipt)
    return registry.authenticate_setup_transition(pending,{OPERATION:fence},value['after'])


def case_baseline(original,registry,record,value,clock):
    history=value['history']
    require(isinstance(history,list) and len(history)==(CASE_CHAIN.index(value['candidate']['name']) if value['candidate']['name'] in CASE_CHAIN else 0),
            'case progression identity differs')
    for entry in history:
        prior,_=read(original,entry['revision'],clock)
        require(value['worker']==prior['worker'] and all(value['candidate']['submitted'][k]!=prior['candidate']['submitted'][k]
                for k in ('pr','head','task_id')), 'distinct reserved case from the same worker required')
    return baseline(original,registry,record,history,clock)


def fresh_capability(original,value,record,token,clock):
    require(digest(token)!=record['execution']['credential']['token_digest'], 'original worker capability is revoked')
    for entry in value['history']:
        prior,_=read(original,entry['revision'],clock)
        require(digest(token)!=prior['execution']['credential']['token_digest'], 'prior case capability cannot authorize progression')


def history_guard(original,record,history):
    require(isinstance(history,list) and len(history)<len(CASE_CHAIN),'bounded native progression history required')
    for index,entry in enumerate(history):
        # The immutable execution document was authenticated at admission. Keep
        # all its exact publication pointers fixed across later blocking reads.
        prior=original.blob(entry['revision'],TRIAL)[0]
        require(prior['task_id']==record['task_id'] and prior['candidate']['name']==CASE_CHAIN[index] and
                prior['history']==history[:index] and prior['execution'] is not None and prior['launch'] is not None,
                'authenticated prior case identity changed')
        require(original.ref(trial_reference(prior))==entry['revision'] and
                original.ref(trial_reference(dict(prior,execution=None)))==prior['execution']['publication_revision'] and
                original.ref(trial_reference(dict(prior,kind='trial-case-ready',execution=None)))==prior['launch']['revision'],
                'authenticated prior case reference moved')


def read(original, revision, clock, _initial=False):
    require(isinstance(original, Registry) and sha(revision), 'exact case publication required')
    value = original.blob(revision, TRIAL)[0]
    object_fields(value, ('schema_version kind task_id origin_revision prompt candidate worker certificate request pending execution launch history').split(),
                  'case handoff')
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and
            value['kind'] == 'trial-case-handoff', 'authenticated case handoff required')
    require(not _initial or value['execution'] is None, 'case execution must bind an initial publication')
    record, before = read_origin(original, value['origin_revision'], clock())
    require(record['execution'] is not None and value['task_id'] == record['task_id'] and
            digest(value['prompt']) == record['prompt_digest'], 'case substituted original execution or prompt')
    if value['launch'] is not None:
        from trial_launch import read as read_ready
        object_fields(value['launch'],('revision','credential','handshake'),'READY consumption binding')
        ready, launched=read_ready(original,value['launch']['revision'],clock)
        require(launched==record and all(ready[k]==value[k] for k in ('task_id','origin_revision','prompt','candidate','worker','history')) and
                value['launch']['handshake']['run_id']==value['request']['snapshot']['run_id'], 'case substituted READY launch')
    commit = original.api.get(original.root + '/git/commits/' + revision)
    require(commit.get('sha') == revision and [v['sha'] for v in commit['parents']] == [before['branch_head']] and
            commit['message'] == 'AGENTIC conditional registry ' + digest({TRIAL:value}) and
            original.ref(trial_reference(value)) == revision, 'case is not the exact conditional publication')
    def unrelated(entries): return {k:v for k,v in entries.items() if k != TRIAL and not TRIAL.startswith(k + '/')}
    require(unrelated(original.tree(revision)[1]) == unrelated(original.tree(before['branch_head'])[1]),
            'case publication changed unrelated registry data')
    if value['execution'] is not None:
        execution = value['execution']
        object_fields(execution, ('publication_revision', 'credential', 'handshake'), 'case consumption binding')
        initial, initial_record = read(original, execution['publication_revision'], clock, _initial=True)
        require(initial['execution'] is None and initial_record == record and value == dict(initial, execution=execution),
                'case consumption substituted initial case')
    original.unchanged(before)
    require(original.ref(trial_reference(value)) == revision, 'case reference moved during authentication')
    require(clock() < min(record['expires'], value['certificate']['expires']), 'case publication expired')
    return copy.deepcopy(value), record


class Publication:
    """Native exact-case publication; uncertain Git writes are never repeated."""
    def __init__(self, admission):
        require(type(admission) is Admission, 'actual native case owner required')
        admission.guard()
        require(admission.value['phase'] == 'bound', 'case must own its exact pending fence')
        self.admission = admission
        c = admission.native.provision
        from trial_controller import case_journal
        self.journal = c.store(c.root / case_journal('trial-case-publication',admission.candidate))

    def publish(self, prompt, launch=None):
        authority_release.authorize('qualify-live')
        a = self.admission
        a.guard()
        value = dict(schema_version=1, kind='trial-case-handoff', task_id=a.record['task_id'],
            origin_revision=a.value['workflow']['value']['revision_bound'], prompt=prompt,
            **{k:copy.deepcopy(a.value[k]) for k in ('candidate','worker','certificate','request','pending','history')}, execution=None,launch=copy.deepcopy(launch))
        require(digest(prompt) == a.record['prompt_digest'], 'exact separately approved worker prompt required')
        document = self.journal.read()
        if document is None:
            document = self.journal.write(None, dict(phase='publication-started', initial=value, execution=None,
                                                   revision=None, revision_bound=None))
            self._guard(document)
            a.native.provision.session.registry._replace(a.record['origin']['binding'], {TRIAL:value},
                before_effect=lambda:self._guard(document), trial_branch=trial_reference(value))
        state = document['value']
        require(state['initial'] == value and state['phase'] in ('publication-started','published','bind-started','bound'),
                'resume only the retained exact case publication')
        original = a.native.provision.session.registry
        revision = original.ref(trial_reference(value))
        require(read(original, revision, a.clock)[0] == value and state['revision'] in (None,revision),
                'case publication remains pending; never repeat writes')
        self._guard(document)
        if state['phase'] == 'publication-started':
            state = dict(state, phase='published', revision=revision)
            self.journal.write(document, state)
        return dict(origin=original.coordinates, revision=revision)

    def _guard(self, document):
        self.admission.guard()
        require(self.journal.read() == document, 'native case publication ownership changed')
        initial=document['value']['initial']
        link=initial['launch']
        if link is not None:
            # Native authorization can outlive the fresh capability. Every
            # pending/bound Git effect must retain both, including after a
            # blocking artifact or immutable-object read.
            c=self.admission.native.provision
            from trial_controller import case_journal
            launch=c.store(c.root/case_journal('trial-case-launch',self.admission.candidate)).read()
            staging=c.store(c.root/case_journal(CaseReadStaging.JOURNAL,self.admission.candidate)).read()
            require(launch is not None and launch['value']['phase']=='consumed' and launch['value']['link']==link and
                    all(launch['value']['ready'][k]==initial[k] for k in ('task_id','origin_revision','prompt','candidate','worker','history')) and
                    staging is not None and staging['value']['revision']==link['revision'] and
                    staging['value']['phase'] in ('secret-started','staged') and
                    digest(staging['value']['credential']['token'])==link['credential']['token_digest'] and
                    min(staging['value']['credential']['expires'],self.admission.record['expires'])==link['credential']['expires'],
                    'retained READY publication delegation changed')
            require(c.session.registry.ref(trial_reference(launch['value']['ready']))==link['revision'],
                    'READY publication moved during case effect')
            require(self.journal.read()==document and c.store(c.root/case_journal('trial-case-launch',self.admission.candidate)).read()==launch and
                    c.store(c.root/case_journal(CaseReadStaging.JOURNAL,self.admission.candidate)).read()==staging and
                    self.admission.clock()<min(link['credential']['expires'],initial['certificate']['expires']),
                    'case publication delegation changed or expired')

    def bind(self, credential, locator):
        """Bind a CLOSED consumer from the prepared run, never dispatch a job."""
        authority_release.authorize('qualify-live')
        a, original = self.admission, self.admission.native.provision.session.registry
        document = self.journal.read()
        require(document is not None and document['value']['phase'] in ('published','bind-started','bound'),
                'published case intent required')
        state = copy.deepcopy(document['value'])
        initial = state['initial']
        require(credential == CaseReadStaging(self, None, None).metadata(), 'exact retained case delegation required')
        proof = provenance.authenticated_document(a.registry.api, a.binding['deployment'], locator,
                                                  'trial-case-handoff', a.record['task_id'], a.clock())
        expected = consumption(initial, state['revision'], credential, locator)
        _closed(proof, expected, a.record['created'], credential['expires'])
        require(locator['run_id'] == a.request['snapshot']['run_id'] and locator['attempt'] == 1,
                'case consumer belongs to another prepared run')
        execution = dict(publication_revision=state['revision'], credential=credential, handshake=locator)
        value = dict(initial, execution=execution)
        self._guard(document)
        if state['phase'] == 'published':
            state.update(phase='bind-started', execution=execution)
            document = self.journal.write(document, state)
            self._guard(document)
            original._replace(a.record['origin']['binding'], {TRIAL:value}, before_effect=lambda:self._guard(document),
                              trial_branch=trial_reference(value))
        require(state['execution'] == execution, 'case consumer substitution refused')
        revision = original.ref(trial_reference(value))
        require(read(original, revision, a.clock)[0] == value and state['revision_bound'] in (None,revision),
                'case consumption publication remains pending')
        self._guard(document)
        if state['phase'] != 'bound':
            state.update(phase='bound', revision_bound=revision)
            self.journal.write(document, state)
        return dict(origin=original.coordinates, revision=revision)


class CaseReadStaging(TrialReadStaging):
    NAME = 'AGENTIC_TRIAL_CASE_ORIGIN_TOKEN'
    JOURNAL = 'trial-case-read-staging'

    def __init__(self, publication, reader, token_factory):
        require(type(publication) is Publication, 'actual native case publication required')
        a = publication.admission
        from trial_controller import case_journal
        self.JOURNAL=case_journal(self.JOURNAL,a.candidate)
        document = publication.journal.read()
        require(document is not None and document['value']['revision'] is not None, 'retained published case required')
        super().__init__(a.native.provision, a.registry, document['value']['revision'], reader, token_factory)
        self.publication = publication

    def run(self):
        authority_release.authorize('bootstrap')
        a, c = self.publication.admission, self.provision
        publication = self.publication.journal.read()
        require(publication['value']['initial']['launch'] is None,'READY capability was already staged before queueing')
        require(publication['value']['phase'] in ('published','bind-started','bound'), 'case publication remains pending')
        require(read(c.session.registry, self.revision, c.clock)[0] == publication['value']['initial'],
                'retained case publication changed')
        journal = c.store(c.root / self.JOURNAL)
        def check(document):
            self.publication._guard(publication)
            require(journal.read() == document and c.session.registry.ref(trial_reference(publication['value']['initial'])) == self.revision,
                    'case delegation ownership changed')
        return self._stage(c, dict(a.record, expires=a.value['certificate']['expires']), a.record['origin']['binding'], journal, check)

    def metadata(self):
        state = self.provision.store(self.provision.root / self.JOURNAL).read()
        initial=self.publication.journal.read()['value']['initial']
        revision=initial['launch']['revision'] if initial['launch'] is not None else self.revision
        require(state is not None and state['value']['revision'] == revision and
                state['value']['phase'] in ('secret-started','staged'), 'exact staged case delegation required')
        credential = state['value']['credential']
        require(credential is not None and self.provision.clock() < min(credential['expires'], self.publication.admission.value['certificate']['expires']),
                'case read delegation expired')
        return dict(revision=revision, repository_id=self.provision.session.registry.coordinates['repository_id'],
            permissions=dict(contents='read'), token_digest=digest(credential['token']),
            expires=min(credential['expires'],self.publication.admission.value['certificate']['expires']))


def consumption(value, revision, credential, locator):
    return dict(schema_version=1, kind='trial-case-consumption', publication_revision=revision,
        case_digest=digest(value), task_id=value['task_id'],
        **{k:credential[k] for k in ('token_digest','repository_id','permissions')},
        **{k:locator[k] for k in ('run_id','attempt','job_id')})


def _closed(proof, expected, created, expires):
    require(proof['document'] == expected and created <= proof['job_started'] <= proof['artifact_created'] <=
            proof['job_completed'] < expires, 'closed case consumer did not consume the exact fresh read delegation')


def consume(registry, origin_reader, environment, hint, clock):
    object_fields(hint, ('origin','revision'), 'case lookup hint')
    original = Registry(origin_reader, hint['origin'])
    value, record = read(original, hint['revision'], clock)
    if value['launch'] is not None:
        from trial_launch import authenticate
        authenticate(original,registry.api,value['launch'],clock)
    require(value['execution'] is None, 'initial case publication required')
    binding = registry.authenticate_setup_progress(case_baseline(original,registry,record,value,clock), {OPERATION:value['pending']})
    token = environment.get(CaseReadStaging.NAME)
    fresh_capability(original,value,record,token,clock)
    require(isinstance(token,str) and 0 < len(token) <= 16384 and origin_reader.token == token and
            digest(token) != record['execution']['credential']['token_digest'] and
            [v['id'] for v in origin_reader.pages('/installation/repositories','repositories')] == [original.coordinates['repository_id']],
            'fresh purpose-only case read capability required')
    job = provenance.admit_job(registry.api,binding['deployment'],environment,'trial case handoff',clock())
    require(environment.get('GITHUB_RUN_ID') == str(value['request']['snapshot']['run_id']) and
            environment.get('GITHUB_RUN_ATTEMPT') == '1', 'case consumer differs from prepared execution')
    original.unchanged(record['origin']['binding']); registry.unchanged(binding)
    history_guard(original,record,value['history'])
    require(original.ref(trial_reference(value)) == hint['revision'] and clock() < value['certificate']['expires'],
            'case changed during consumption')
    return consumption(value,hint['revision'],dict(token_digest=digest(token),repository_id=original.coordinates['repository_id'],
        permissions=dict(contents='read')),dict(run_id=int(environment['GITHUB_RUN_ID']),attempt=1,job_id=job['id']))


class Hosted:
    """Fresh read-only admission with no native capabilities or protected journal."""
    _retained = Admission._retained
    task = Admission.task

    def qualification(self, binding, controls_digest=None):
        value = Admission.qualification(self,binding,controls_digest)
        value['expires'] = min(value['expires'], self.case['execution']['credential']['expires'])
        return value

    def __init__(self, registry, origin_reader, source, environment, hint, role, clock):
        object_fields(hint, ('origin','revision'), 'case lookup hint')
        self.original = Registry(origin_reader,hint['origin'])
        self.registry, self.source, self.clock = registry, None, clock
        self.revision = hint['revision']
        self.case, self.record = read(self.original,self.revision,clock)
        value, r = self.case, self.record
        if value['launch'] is not None:
            from trial_launch import authenticate
            authenticate(self.original,registry.api,value['launch'],clock)
        execution = value['execution']
        require(execution is not None, 'closed case consumption binding required')
        credential, locator = execution['credential'], execution['handshake']
        fresh_capability(self.original,value,r,getattr(origin_reader,'token',None),clock)
        object_fields(credential, ('revision repository_id permissions token_digest expires').split(), 'fresh consumed case delegation')
        staged_revision=value['launch']['revision'] if value['launch'] is not None else execution['publication_revision']
        require(credential['revision'] == staged_revision and
                credential['repository_id'] == self.original.coordinates['repository_id'] and credential['permissions'] == dict(contents='read') and
                digest(getattr(origin_reader,'token',None)) == credential['token_digest'] != r['execution']['credential']['token_digest'] and
                clock() < credential['expires'] <= value['certificate']['expires'] and
                [v['id'] for v in origin_reader.pages('/installation/repositories','repositories')] == [credential['repository_id']],
                'exact fresh consumed case read delegation required')
        initial = dict(value,execution=None)
        proof = provenance.authenticated_document(registry.api,r['trial']['deployment'],locator,'trial-case-handoff',r['task_id'],clock())
        _closed(proof,consumption(initial,execution['publication_revision'],credential,locator),r['created'],credential['expires'])
        self.value = dict(value,phase='bound')
        self.candidate, self.request = copy.deepcopy(value['candidate']), copy.deepcopy(value['request'])
        self.binding = case_baseline(self.original,registry,r,value,clock)
        self._retained()
        self.binding = registry.authenticate_setup_progress(self.binding, {OPERATION:value['pending']})
        require(locator['run_id'] == self.request['snapshot']['run_id'] and locator['attempt'] == 1,
                'case consumed execution differs')
        self.worker = None
        self._seal = copy.deepcopy(self._state())
        if role == 'finalize':
            from broker_finalize import Finalizer
            from trusted_ci_policy import loads
            Finalizer(None,registry.api,None,loads(environment.get('AGENTIC_RECOVERY_PIN','')),environment,clock)._admit()
        else:
            purpose = environment.get('GITHUB_JOB','').split('_',1)[0]
            require(role in ('verify','proof','publication-controls','publish','host-denial','broker','controls','final-proof'), 'fixed case producer required')
            name = ('publication controls' if role == 'publication-controls' else 'final proof' if role == 'final-proof' else role)
            name = 'trial host denial' if role == 'host-denial' else name + ' (' + (purpose if role in ('proof','final-proof') else str(self.candidate['submitted']['pr'])) + ')'
            require(environment.get('GITHUB_RUN_ID') == str(locator['run_id']) and environment.get('GITHUB_RUN_ATTEMPT') == '1',
                    'case producer belongs to another execution')
            provenance.admit_job(registry.api,self.binding['deployment'],environment,name,clock())
        self.guard()
        if source is not None: self.bind_source(source)

    def bind_source(self, source):
        """Borrow role-scoped source reads only after data/job authentication."""
        self.guard()
        require(self.worker is None and self.source is None, 'case source already bound')
        worker = NativeHandoff.worker_completion(self.registry,source,self.record,self.case['prompt'],self.clock)
        self.guard()
        require(worker['result'] == self.case['worker'], 'case CLOSED worker differs')
        self.source, self.worker = source, worker
        self._seal = copy.deepcopy(self._state())
        self.guard()

    def _state(self):
        return dict(case=self.case,record=self.record,value=self.value,candidate=self.candidate,request=self.request,binding=self.binding,worker=self.worker)

    def local_guard(self, binding=None):
        require(self._state() == self._seal and (binding is None or binding == self.binding), 'case admission object changed')
        credential = self.case['execution']['credential']
        require(self.record['created'] <= self.clock() < min(self.record['expires'],credential['expires'],self.case['certificate']['expires']) and
                digest(getattr(self.original.api,'token',None)) == credential['token_digest'], 'case delegation expired or changed')

    def guard(self, binding=None, force=False):
        self.local_guard(binding)
        r = self.record
        origin = r['origin']['binding']
        original_branch = self.original.unchanged(origin)
        trial_branch = self.registry.unchanged(self.binding)
        p = self.binding['deployment']['policy']
        if self.source is not None:
            repo = self.source.get('/repos/'+p['repository'])
            require(repo.get('id') == p['repository_id'] and repo.get('private') is True and
                    repo.get('owner',{}).get('id') == r['pair']['identities']['owner_id'] and repo.get('default_branch') == p['target'],
                    'case source identity changed')
        require(self.original.ref(self.original.coordinates['registry_branch']) == origin['branch_head'] and
                self.original.ref(original_branch) == origin['software_revision'] and
                self.original.ref('agentic-trial-'+r['task_id']) == r['execution']['publication_revision'] and
                self.original.ref('agentic-trial-'+r['task_id']+'-execution') == self.case['origin_revision'] and
                self.original.ref(trial_reference(dict(self.case,execution=None))) == self.case['execution']['publication_revision'] and
                self.original.ref(trial_reference(self.case)) == self.revision and
                self.registry.ref(self.registry.coordinates['registry_branch']) == self.binding['branch_head'] and
                self.registry.ref(trial_branch) == self.binding['software_revision'], 'case pointers moved during live observation')
        history_guard(self.original,r,self.case['history'])
        self.local_guard(binding)
