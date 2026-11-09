"""Read-only qualification handoff through the existing conditional registry.

The original native fence authorizes publication into the disposable authority.
No native capability or Python object crosses the job boundary. Neither this
record nor its consent is candidate review or active authority admission.
"""
import copy
import re
import secrets

import authority_release
from registry import Registry, DOCUMENT, OPERATION, TRIAL
from trial_admission import Admission
from trial_setup import Provision
from trusted_ci_policy import digest, object_fields, positive, require, sha


FIELDS = ('schema_version kind nonce task_id prompt_digest origin pair trial created expires execution delegation').split()


def _record(value, now):
    object_fields(value, FIELDS, 'native trial handoff')
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and
            value['kind'] == 'native-trial-handoff' and
            all(isinstance(value[k], str) and re.fullmatch('[0-9a-f]{32}', value[k]) for k in ('nonce', 'task_id')) and
            isinstance(value['prompt_digest'], str) and re.fullmatch('[0-9a-f]{64}', value['prompt_digest']) and
            positive(value['created']) and positive(value['expires']) and
            value['created'] <= now < value['expires'] <= value['created'] + 3600,
            'native trial handoff expired or malformed')
    object_fields(value['origin'], ('coordinates', 'binding', 'scope', 'owner'), 'original fenced authority')
    require(value['delegation'] == dict(name='AGENTIC_TRIAL_ORIGIN_TOKEN',
            repository_id=value['origin']['coordinates']['repository_id'], permissions=dict(contents='read'),
            expires=value['expires']), 'exact original-authority read delegation required')
    if value['execution'] is not None:
        execution = value['execution']
        object_fields(execution, ('publication_revision', 'handshake', 'credential'), 'native bound trial execution')
        require(sha(execution['publication_revision']), 'exact initial handoff revision required')
        object_fields(execution['handshake'], ('run_id', 'attempt', 'job_id', 'artifact_id'), 'trial handshake locator')
        require(all(positive(v) for v in execution['handshake'].values()) and execution['handshake']['attempt'] == 1,
                'one original trial attempt required')
    return value


def read(registry, revision, now):
    """Authenticate the exact conditional commit and unchanged configuration.

    A same-content document at an arbitrary later commit is insufficient. The
    record binds its parent, not its own commit or deployment digest.
    """
    require(isinstance(registry, Registry) and sha(revision), 'trial registry and exact revision required')
    record = _record(registry.blob(revision, TRIAL)[0], now)
    current = registry.binding()
    before = record['origin']['binding']
    require(registry.coordinates == record['origin']['coordinates'] and current == before and
            registry.ref('agentic-trial-' + record['task_id'] + ('-execution' if record['execution'] else '')) == revision and
            current['deployment']['state'] == 'qualification' and current['deployment']['qualification'] is None and
            current['fence']['pending'] is not None and current['fence']['pending']['kind'] == 'configuration',
            'current original fenced handoff required')
    require(
            registry.blob(before['branch_head'], DOCUMENT) == (before['deployment'], before['configuration_revision']) and
            registry.blob(before['branch_head'], OPERATION)[0] == before['fence'], 'handoff configuration changed')
    commit = registry.api.get(registry.root + '/git/commits/' + revision)
    require(commit.get('sha') == revision and [p['sha'] for p in commit['parents']] == [before['branch_head']] and
            commit['message'] == 'AGENTIC conditional registry ' + digest({TRIAL: record}),
            'handoff is not the exact retained conditional commit')
    def unrelated(entries):
        return {k: v for k, v in entries.items() if k != TRIAL and not TRIAL.startswith(k + '/')}
    require(unrelated(registry.tree(revision)[1]) == unrelated(registry.tree(before['branch_head'])[1]),
            'handoff publication changed unrelated registry data')
    registry.unchanged(current)
    require(registry.ref('agentic-trial-' + record['task_id'] + ('-execution' if record['execution'] else '')) == revision,
            'native handoff ref moved during authentication')
    if record['execution'] is not None:
        initial, _ = read(registry, record['execution']['publication_revision'], now)
        require(initial['execution'] is None and record == dict(initial, execution=record['execution']),
                'bound execution substituted native handoff intent')
        registry.unchanged(current)
        require(registry.ref('agentic-trial-' + record['task_id'] + '-execution') == revision,
                'bound execution ref moved during initial-record authentication')
    _record(record, now)
    return copy.deepcopy(record), current


class Hosted:
    """Authenticated read-only context; contains no native session or root keys."""
    def __init__(self, registry, origin_reader, authority, environment, hint, prompt, clock):
        import provenance
        from trusted_ci_policy import loads
        hint = loads(hint) if isinstance(hint, str) else hint
        object_fields(hint, ('origin', 'revision'), 'native handoff lookup hint')
        self.original = Registry(origin_reader, hint['origin'])
        require([v['id'] for v in origin_reader.pages('/installation/repositories', 'repositories')] ==
                [self.original.coordinates['repository_id']], 'hosted origin capability reaches another repository')
        self.registry, self.authority, self.clock = registry, authority, clock
        initial, _ = read(self.original, hint['revision'], clock())
        require(initial['execution'] is None, 'initial handoff revision required')
        self.revision = self.original.ref('agentic-trial-' + initial['task_id'] + '-execution')
        self.record, self.origin_binding = read(self.original, self.revision, clock())
        r, origin = self.record, self.origin_binding
        require(r['execution']['publication_revision'] == hint['revision'] and
                isinstance(prompt, str) and 0 < len(prompt.encode('utf-8')) <= 65536 and
                digest(prompt) == r['prompt_digest'], 'prompt differs from exact native consent')
        op = origin['fence']['pending']
        scope, owner, pair = r['origin']['scope'], r['origin']['owner'], r['pair']
        require(isinstance(owner, dict) and set(owner) in
                ({'workflow_sha', 'run_id', 'attempt'}, {'workflow_sha', 'run_id', 'attempt', 'setup'}) and
                all(op.get(k) == v for k, v in owner.items()) and op['scope_digest'] == digest(scope) and
                set((pair['fixture_repository'], pair['authority_repository'])) <= set(scope.get('qualification-fixture', [])) and
                pair['origin'] == dict(configuration_revision=origin['configuration_revision'], deployment_digest=origin['deployment_digest'],
                    branch_head=origin['branch_head'], operation_id=op['operation_id'], sequence=origin['fence']['sequence'],
                    workflow_sha=origin['deployment']['policy']['workflow_sha'], adapter=origin['deployment']['adapter'],
                    account=origin['deployment']['account']) and clock() < min(op['execution_deadline'], origin['deployment']['expires']),
                'native handoff does not own original approved fixture scope')
        require(registry.binding() == r['trial'] and r['trial']['deployment']['state'] == 'qualification' and
                r['trial']['deployment']['qualification'] is None and r['trial']['fence']['pending'] is None,
                'native-approved disposable configuration changed')
        execution = r['execution']
        location, credential = execution['handshake'], execution['credential']
        object_fields(credential, ('revision', 'repository_id', 'permissions', 'token_digest', 'expires'), 'consumed read delegation')
        require(credential['revision'] == hint['revision'] and credential['repository_id'] == self.original.coordinates['repository_id'] and
                credential['permissions'] == dict(contents='read') and positive(credential['expires']) and
                clock() < credential['expires'] <= r['expires'], 'consumed native read delegation expired or differs')
        require(isinstance(getattr(origin_reader, 'token', None), str) and
                digest(origin_reader.token) == credential['token_digest'], 'origin capability differs from exact consumed native token')
        proof = provenance.authenticated_document(authority, r['trial']['deployment'], location, 'trial-handoff', r['task_id'], clock())
        expected = dict(schema_version=1, kind='trial-handoff-consumption', publication_revision=hint['revision'],
            record_digest=digest(initial), task_id=r['task_id'], nonce=r['nonce'],
            **{k:credential[k] for k in ('token_digest', 'repository_id', 'permissions')},
            **{k:location[k] for k in ('run_id', 'attempt', 'job_id')})
        require(proof['document'] == expected and r['created'] <= proof['job_started'] <= proof['artifact_created'] <=
                proof['job_completed'] < credential['expires'], 'closed native read consumption differs')
        self.task = dict(task_id=r['task_id'], run_id=location['run_id'], attempt=location['attempt'],
                         deadline=min(r['expires'], credential['expires']), purpose='qualification')
        self.environment = {k:environment[k] for k in ('GITHUB_REPOSITORY_ID', 'GITHUB_SHA', 'GITHUB_RUN_ID',
            'GITHUB_RUN_ATTEMPT', 'GITHUB_JOB') if k in environment}
        require(self.environment.get('GITHUB_RUN_ID') == str(location['run_id']) and
                self.environment.get('GITHUB_RUN_ATTEMPT') == str(location['attempt']), 'native execution bound to another run or attempt')
        role = self.environment.get('GITHUB_JOB')
        name = {'qualification':'hosted qualification', 'trial_prepare':'trial preparation',
            'model_auth':'model authorization', 'trial_model_auth':'model authorization',
            **{prefix + k + '_proof':'proof (' + k + ')' for prefix in ('', 'trial_')
               for k in ('admin', 'reader', 'issuer', 'coding', 'merge')}}.get(role)
        if role == 'trial_task_controls':
            p = r['trial']['deployment']['policy']
            require(self.environment.get('GITHUB_REPOSITORY_ID') == str(p['authority_repository_id']) and
                    self.environment.get('GITHUB_SHA') == p['workflow_sha'], 'pinned independent trial controls required')
            self.job = provenance.execution_job(authority, r['trial']['deployment'], location['run_id'], location['attempt'],
                'trial task controls (' + r['task_id'] + ')')
        else:
            require(name is not None, 'fixed native trial producer required')
            self.job = provenance.admit_job(authority, r['trial']['deployment'], self.environment, name, clock())
        self.prompt = prompt
        self.guard()

    def guard(self):
        r, original, trial = self.record, self.original, self.registry
        self.local_guard()
        original_branch = original.unchanged(self.origin_binding)
        trial_branch = trial.unchanged(r['trial'])
        # Recheck individual origin pointers after the blocking trial observation.
        require(original.ref(original.coordinates['registry_branch']) == self.origin_binding['branch_head'] and
                original.ref(original_branch) == self.origin_binding['software_revision'] and
                original.ref('agentic-trial-' + r['task_id']) == r['execution']['publication_revision'] and
                original.ref('agentic-trial-' + r['task_id'] + '-execution') == self.revision,
                'native authority or execution binding moved during trial observation')
        require(trial.ref(trial.coordinates['registry_branch']) == r['trial']['branch_head'] and
                trial.ref(trial_branch) == r['trial']['software_revision'], 'trial pointers moved during original observation')
        require(self.clock() < self.task['deadline'], 'native trial expired during live readback')
        return original_branch, trial_branch

    def local_guard(self):
        require(self.record['created'] <= self.clock() < self.task['deadline'], 'native hosted trial expired')
        require(digest(getattr(self.original.api, 'token', None)) == self.record['execution']['credential']['token_digest'],
                'consumed native read capability changed')

    def worker_configuration(self):
        """Live pointers to immutable records already authenticated by this job."""
        self.local_guard()
        original = self.original.unchanged(self.origin_binding)
        trial = self.registry.unchanged(self.record['trial'])
        require(self.original.ref('agentic-trial-' + self.record['task_id'] + '-execution') == self.revision,
                'native execution binding moved')
        self.local_guard()
        return original, trial

    def approve(self, intent):
        self.guard()
        require(self.environment.get('GITHUB_JOB') == 'qualification' and intent['task'] == self.task and
                intent['origin'] == self.record['pair']['origin'] and intent['source_base'] == self.record['pair']['fixture_revision'] and
                intent['execution']['job_id'] == self.job['id'] and intent['configuration_revision'] == self.record['trial']['configuration_revision'] and
                intent['deployment_digest'] == self.record['trial']['deployment_digest'], 'hosted admission differs from native trial consent')
        return digest(intent)

    def approve_worker(self, preview):
        self.guard()
        request = preview['request']
        require(preview['kind'] == 'trial-worker' and request['task'] == self.task and
                digest(request['prompt']) == self.record['prompt_digest'] and
                request['source_base'] == self.record['pair']['fixture_revision'], 'worker differs from native prompt consent')
        return digest(preview)


def consume(registry, authority, environment, hint, origin_reader, clock):
    """Pinned closed handshake consumes exactly the native staged read capability."""
    import provenance
    from trusted_ci_policy import loads
    value = loads(hint) if isinstance(hint, str) else hint
    object_fields(value, ('origin', 'revision'), 'trial handoff coordinates')
    original = Registry(origin_reader, value['origin'])
    require([v['id'] for v in origin_reader.pages('/installation/repositories', 'repositories')] ==
            [original.coordinates['repository_id']], 'origin read capability reaches another repository')
    record, _ = read(original, value['revision'], clock())
    require(record['execution'] is None and registry.binding() == record['trial'], 'initial exact trial handoff required')
    job = provenance.admit_job(authority, record['trial']['deployment'], environment, 'trial handoff', clock())
    require(environment.get('GITHUB_RUN_ATTEMPT') == '1', 'native trial cannot replay another attempt')
    token = environment.get('AGENTIC_TRIAL_ORIGIN_TOKEN')
    require(isinstance(token, str) and 0 < len(token) <= 16384, 'native scoped read capability required')
    require(getattr(origin_reader, 'token', None) == token, 'consumer transport differs from exact staged capability')
    original.unchanged(record['origin']['binding'])
    registry.unchanged(record['trial'])
    require(clock() < record['expires'], 'native trial handoff expired during consumption')
    return dict(schema_version=1, kind='trial-handoff-consumption', publication_revision=value['revision'],
        record_digest=digest(record), task_id=record['task_id'], nonce=record['nonce'], token_digest=digest(token),
        repository_id=original.coordinates['repository_id'], permissions=dict(contents='read'),
        run_id=int(environment['GITHUB_RUN_ID']), attempt=1, job_id=job['id'])


class Native:
    def __init__(self, provision, registry):
        self.provision, self.registry = provision, registry

    def run(self, prompt, reader, token_factory, approve):
        authority_release.authorize('protected-run')
        from setup import TrialReadStaging
        from credential_workflow import TrialWorkflow
        published = self.publish(prompt, approve)
        staging = TrialReadStaging(self.provision, self.registry, published['revision'], reader, token_factory)
        return TrialWorkflow(staging, self.registry.api, self.provision.store(self.provision.root / 'trial-workflow')).run(prompt)

    def observe(self, prompt, source=None, token_factory=None):
        """Read-only exact completion recovery; absence is never proof of failure."""
        authority_release.authorize('protected-run')
        from trusted_ci_github import GitHub
        from setup import TrialReadStaging
        completed = self._completion(prompt, source)
        record = completed['record']
        TrialReadStaging(self.provision,self.registry,record['execution']['publication_revision'],None,token_factory or GitHub).revoke()
        return completed['result']

    def _completion(self, prompt, source=None):
        """Shared exact CLOSED worker and Git readback; no activation or effects."""
        c = self.provision
        require(isinstance(c,Provision), 'actual native trial provision required')
        retained = c.store(c.root / 'trial-workflow').read()
        require(retained is not None and retained['value']['phase'] == 'bound', 'native trial dispatch remains pending')
        record, origin = read(c.session.registry,retained['value']['revision_bound'],c.clock())
        require(record['execution'] == retained['value']['execution'] and digest(prompt) == record['prompt_digest'] and
                c.completed() == record['pair'] and c.session._check() == origin and self.registry.binding() == record['trial'],
                'native completion recovery binding differs')
        completed = self._worker_completion(record, prompt, source)
        require(read(c.session.registry,retained['value']['revision_bound'],c.clock())[0] == record and
                self.registry.binding() == record['trial'] and c.store(c.root / 'trial-workflow').read() == retained and
                c.completed() == record['pair'], 'native authorization changed during completion recovery')
        return dict(completed, record=record, retained=retained)

    def _worker_completion(self, record, prompt, source=None):
        """Immutable CLOSED worker/Git reader, bracketed by its caller's live guard.

        Native observation requires the original settled binding. A separately
        authenticated case owner may bracket this same reader with its exact
        retained fence transition instead; this reader grants no such authority.
        """
        return self.worker_completion(self.registry, source or self.provision.api, record, prompt, self.provision.clock)

    @staticmethod
    def worker_completion(registry, source, record, prompt, clock):
        """Shared immutable CLOSED worker reader; caller owns the live phase guard."""
        import provenance
        import submission
        from trusted_ci_deployment import timestamp
        task = dict(task_id=record['task_id'],run_id=record['execution']['handshake']['run_id'],attempt=1,
            deadline=min(record['expires'],record['execution']['credential']['expires']),purpose='qualification')
        d, api = record['trial']['deployment'], registry.api
        request = dict(schema_version=2,task=task,prompt=prompt,source_base=record['pair']['fixture_revision'],
            configuration_revision=record['trial']['configuration_revision'],deployment_digest=record['trial']['deployment_digest'])
        job = provenance.execution_job(api,d,task['run_id'],1,'hosted qualification',completed=True)
        root = '/repos/' + d['policy']['authority_repository'] + '/actions/runs/' + str(task['run_id'])
        artifacts = [a for a in api.pages(root + '/artifacts','artifacts') if
                     a.get('name') == 'trial-task-' + task['task_id'] + '-1']
        require(len(artifacts) == 1, 'exact completed trial artifact remains pending; never replay')
        location = dict(run_id=task['run_id'],attempt=1,job_id=job['id'],artifact_id=artifacts[0]['id'])
        proof = provenance.authenticated_document(api,d,location,'trial-task',task['task_id'],clock())
        receipt = proof['document']
        object_fields(receipt,('schema_version kind admission_digest request_digest execution submitted protocol isolation relay '
            'controls_digest cleanup_complete completed hosted_qualified enforcement_active').split(),'completed trial receipt')
        require(receipt['schema_version'] == 2 and receipt['kind'] == 'trial-task' and receipt['request_digest'] == digest(request) and
                receipt['execution'] == {k:location[k] for k in ('run_id','attempt','job_id')} and
                receipt['cleanup_complete'] is True and receipt['hosted_qualified'] is False and receipt['enforcement_active'] is False and
                proof['job_started'] <= receipt['completed'] <= proof['artifact_created'] <= proof['job_completed'],
                'closed trial receipt does not establish exact cleaned-up completion')
        submitted = receipt['submitted']
        p = d['policy']
        source_root = '/repos/' + p['repository']
        require(submitted['task_id'] == task['task_id'] and submitted['run_id'] == task['run_id'] and submitted['attempt'] == 1 and
                submitted['configuration_revision'] == record['trial']['configuration_revision'] and
                submitted['deployment_digest'] == record['trial']['deployment_digest'] and submitted['app_id'] == d['apps']['coding'] and
                submitted['bot_id'] == int(d['resources']['coding_bot_id']) and submitted['branch'] == 'agentic/task-' + task['task_id'] and
                sha(submitted['head']) and sha(submitted['tree']) and positive(submitted['pr']), 'trial submission binding differs')
        commit = source.get(source_root + '/git/commits/' + submitted['head'])
        require(commit.get('sha') == submitted['head'] and commit['tree']['sha'] == submitted['tree'] and
                [v['sha'] for v in commit['parents']] == [request['source_base']], 'actual submitted Git parents or tree differ')
        def clock_guard(): require(clock() < record['expires'], 'native completion recovery expired')
        files = submission._read_tree(source,source_root,submitted['tree'],clock_guard)
        manifest = submission.export_manifest(files)
        require(digest(manifest) == submitted['export_digest'], 'actual Git blobs or executable modes differ from exported trial')
        issued = int(timestamp(commit['author']['date']).timestamp())
        submission_request = dict(schema_version=2,task_id=task['task_id'],base=request['source_base'],issued=issued,
            configuration_revision=request['configuration_revision'],deployment_digest=request['deployment_digest'],run_id=task['run_id'],attempt=1)
        require(record['created'] <= issued <= receipt['completed'] and commit['message'] ==
                'AGENTIC task ' + task['task_id'] + '\n\n' + digest(dict(request=submission_request,files=manifest)),
                'actual submitted commit differs from exact trial request')
        pr = source.get(source_root + '/pulls/' + str(submitted['pr']))
        require(pr['number'] == submitted['pr'] and pr['state'] == 'open' and pr.get('merged') is False and pr.get('draft') is False and
                pr['head']['sha'] == submitted['head'] and pr['head']['ref'] == submitted['branch'] and
                pr['head']['repo']['id'] == p['repository_id'] and pr['base']['repo']['id'] == p['repository_id'] and
                pr['base']['ref'] == p['target'] and pr['user']['id'] == submitted['bot_id'] and pr['user'].get('type') == 'Bot' and
                '<!-- agentic-task:' + digest(submission_request) + ' -->' in pr.get('body','') and
                submission.existing_ref(source,source_root,submitted['branch']) == submitted['head'], 'exact trial PR readback differs')
        result = dict(state='trial-complete',locator=location,submitted=copy.deepcopy(submitted),hosted_qualified=False,enforcement_active=False)
        return dict(result=result, proof=proof, files=files)

    def publish(self, prompt, approve):
        authority_release.authorize('protected-run')
        c, trial = self.provision, self.registry
        require(isinstance(c, Provision) and isinstance(trial, Registry), 'completed native provisioning and trial registry required')
        reg = c.session.registry
        require(isinstance(prompt, str) and 0 < len(prompt.encode('utf-8')) <= 65536,
                'bounded separately approved trial prompt required')
        # The existing admission resource validator authenticates the actual
        # completed native pair and critical/runtime/model configuration.
        validator = Admission(c, trial, trial.api, None, c.root / 'handoff-validation', c.clock, c.store)
        pair, current, _ = validator._binding()
        origin = c.session._check()
        retained = copy.deepcopy(c.document)
        journal = c.store(c.root / 'handoff')
        document = journal.read()
        if document is None:
            require(TRIAL not in reg.tree(origin['branch_head'])[1], 'unowned handoff already exists')
            record = dict(schema_version=1, kind='native-trial-handoff', nonce=secrets.token_hex(16),
                task_id=secrets.token_hex(16), prompt_digest=digest(prompt), pair=pair, trial=current,
                origin=dict(coordinates=copy.deepcopy(c.session.registry.coordinates), binding=origin,
                    scope=copy.deepcopy(c.session.scope), owner=copy.deepcopy(c.session.owner)), created=c.clock(),
                expires=min(c.preview['expires'], current['deployment']['expires'], origin['deployment']['expires'],
                    origin['fence']['pending']['execution_deadline']), execution=None)
            record['delegation'] = dict(name='AGENTIC_TRIAL_ORIGIN_TOKEN', repository_id=reg.coordinates['repository_id'],
                permissions=dict(contents='read'), expires=record['expires'])
            _record(record, c.clock())
            approval = approve(copy.deepcopy(record))
            require(approval == digest(record), 'exact handoff and separate prompt consent required')
            state = dict(record=record, approval=approval, phase='prepared', revision=None)
        else:
            state = copy.deepcopy(document['value'])
            object_fields(state, ('record', 'approval', 'phase', 'revision'), 'retained native handoff')
            record = _record(state['record'], c.clock())
            require(state['approval'] == digest(record) and record['pair'] == pair and
                    record['prompt_digest'] == digest(prompt) and
                    state['phase'] in ('prepared', 'publication-started', 'published'), 'retained handoff consent differs')
        original_expected = tuple(origin[k] for k in ('configuration_revision', 'deployment_digest', 'branch_head'))
        def guard():
            _record(record, c.clock())
            require(c.journal.read() == retained and c.document == retained and
                    c.session.expected == original_expected and c.session.owner == record['origin']['owner'] and
                    c.session.scope == record['origin']['scope'] and c.session._check() == record['origin']['binding'],
                    'original trial fence or consent changed')
            require(c._origin(pair['fixture_repository'], pair['authority_repository']) == pair['origin'] and
                    c.session.registry.coordinates == record['origin']['coordinates'], 'original trial authority changed')
            trial_branch = trial.unchanged(record['trial'])
            reg.unchanged(origin)
            require(trial.ref(trial.coordinates['registry_branch']) == record['trial']['branch_head'] and
                    trial.ref(trial_branch) == record['trial']['software_revision'],
                    'trial pointers moved during original readback')
            require(journal.read() == document and c.journal.read() == retained, 'native handoff journal changed')
            _record(record, c.clock())
        if document is None:
            guard()
            document = journal.write(None, state)
        if state['phase'] == 'prepared':
            guard()
            state['phase'] = 'publication-started'
            document = journal.write(document, state)
            guard()
            reg._replace(origin, {TRIAL: record}, before_effect=guard,
                         trial_branch='agentic-trial-' + record['task_id'])
        # Recover only the one authenticated conditional commit. An unchanged
        # parent after an unknown write is pending, never permission to repeat.
        revision = reg.ref('agentic-trial-' + record['task_id'])
        observed, binding = read(reg, revision, c.clock())
        require(observed == record and state['revision'] in (None, revision), 'retained handoff publication differs')
        require(c.session._check() == record['origin']['binding'] and trial.binding() == record['trial'] and journal.read() == document and
                c.journal.read() == retained, 'native authorization changed during publication readback')
        if state['phase'] != 'published':
            state.update(phase='published', revision=revision)
            document = journal.write(document, state)
        require(journal.read() == document, 'retained handoff publication changed')
        _record(record, c.clock())
        return dict(revision=revision, task_id=record['task_id'], expires=record['expires'],
                    hosted_qualified=False, enforcement_active=False)
