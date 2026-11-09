"""Held native, one-candidate admission into the existing authority controllers.

The certificate is a protected native journal claim backed by the actual native
handoff, CLOSED worker, exact candidate and retained conditional fence commit.
It is not a production qualification receipt or a cross-job hosted handoff.
This source-local composition never transports native objects into Actions jobs.
"""
import copy

import authority_release
from registry import OPERATION
from trial_candidates import Prepare
from trial_handoff import Native as NativeHandoff, read
from trial_setup import Provision
from trusted_ci_policy import digest, object_fields, require


def authenticated(value, binding=None):
    require(type(value) is Admission, 'actual native trial controller admission required')
    require(value.worker is not None, 'authenticated CLOSED worker required')
    value.local_guard(binding)
    return value


class Native:
    def __init__(self, candidates):
        self.candidates = candidates

    def open(self, prompt, name):
        authority_release.authorize('qualify-live')
        return self._open(prompt, name)

    def _open(self, prompt, name, source=None):
        require(type(self.candidates) is Prepare, 'actual native candidate preparer required')
        preparer, native = self.candidates, self.candidates.native
        require(type(native) is NativeHandoff and type(native.provision) is Provision, 'actual authenticated native trial required')
        c = native.provision
        source = source or c.api
        journal = c.store(c.root / 'trial-controller')
        document = journal.read()
        if document is None:
            result = preparer._run(prompt, source)
            completed = native._completion(prompt, source)
            candidates = c.store(c.root / 'trial-candidates').read()
            matches = [v for v in result['candidates'] if v['name'] == name]
            require(len(matches) == 1 and completed['result'] == result['worker'], 'exact prepared trial case required')
            value = dict(kind='native-trial-controller', prompt_digest=digest(prompt), name=name,
                record=completed['record'], workflow=completed['retained'], candidates=candidates,
                provisioning=copy.deepcopy(c.document), candidate=matches[0], worker=completed['result'],
                phase='ready', certificate=None, request=None, pending=None, terminal=None)
            document = journal.write(None, value)
        value = document['value']
        require(value['kind'] == 'native-trial-controller' and value['prompt_digest'] == digest(prompt) and
                value['name'] == name, 'resume only the exact retained native case')
        admission = Admission(native, source)
        admission.guard()
        # A new process reauthenticates the immutable worker and candidate rather
        # than projecting the current pending trial as its original settled state.
        completed = native._worker_completion(value['record'], prompt, source)
        require(completed['result'] == value['worker'], 'retained CLOSED worker changed')
        admission.worker = completed
        admission._candidate(preparer)
        admission.guard()
        return admission


class Admission:
    def __init__(self, native, source):
        require(type(native) is NativeHandoff and type(native.provision) is Provision, 'actual authenticated native trial required')
        self.native, self.source = native, source
        c = native.provision
        self.journal = c.store(c.root / 'trial-controller')
        self.document = self.journal.read()
        require(self.document is not None, 'native case intent required')
        self.value = copy.deepcopy(self.document['value'])
        object_fields(self.value, ('kind prompt_digest name record workflow candidates provisioning candidate worker '
            'phase certificate request pending terminal').split(), 'retained native case')
        self.registry, self.clock = native.registry, native.provision.clock
        self.record = self.value['record']
        record, _ = read(c.session.registry,self.value['workflow']['value']['revision_bound'],self.clock())
        require(record == self.record and self.value['workflow']['value']['execution'] == record['execution'],
                'retained native case substituted authenticated handoff')
        self.candidate = copy.deepcopy(self.value['candidate'])
        self.request = copy.deepcopy(self.value['request'])
        self.worker = None
        self.binding = copy.deepcopy(self.record['trial'])
        if self.value['phase'] in ('fencing', 'bound'):
            self._retained()
            self.binding = self.registry.authenticate_setup_progress(self.binding, {OPERATION:self.value['pending']})
            if self.value['phase'] == 'fencing':
                self.value['phase'] = 'bound'
                self._save()
        require(self.value['phase'] in ('ready','bound'), 'native case is terminal; never replay')

    def _retained(self):
        from operation_fence import operation
        b, r, certificate, request = self.binding, self.record, self.value['certificate'], self.value['request']
        pending = self.value['pending']
        op = operation(pending['pending'])
        expected = copy.deepcopy(b['fence']); expected['sequence'] += 1; expected['pending'] = op
        require(pending == expected and op['kind'] == 'merge' and op['configuration_revision'] == b['configuration_revision'] and
                op['deployment_digest'] == b['deployment_digest'] and op['repository_id'] == r['pair']['fixture_repository_id'] and
                op['target'] == b['deployment']['policy']['target'] and op['workflow_sha'] == b['software_revision'] and
                op['pr'] == self.candidate['submitted']['pr'] and op['head'] == self.candidate['submitted']['head'] and
                op['base'] == r['pair']['fixture_revision'], 'retained trial operation substituted candidate or configuration')
        object_fields(certificate, ('schema_version kind record_digest worker candidate configuration_revision deployment_digest '
            'operation sequence controls_digest issued expires hosted_qualified enforcement_active').split(), 'native trial certificate')
        require(type(certificate['schema_version']) is int and certificate['schema_version'] == 1 and
                certificate['kind'] == 'native-trial-certificate' and certificate['record_digest'] == digest(r) and
                certificate['worker'] == self.value['worker'] and certificate['candidate'] == self.candidate and
                certificate['configuration_revision'] == b['configuration_revision'] and certificate['deployment_digest'] == b['deployment_digest'] and
                certificate['operation'] == op and certificate['sequence'] == pending['sequence'] and
                certificate['issued'] == op['created'] and certificate['expires'] == min(r['expires'],op['execution_deadline']) and
                certificate['hosted_qualified'] is False and certificate['enforcement_active'] is False,
                'retained native certificate changed')
        from trusted_ci_policy import validate_snapshot
        snapshot = validate_snapshot(request['snapshot'],b['deployment']['policy'])
        require(all(snapshot[k] == op[k] for k in ('pr','head','base','merge','run_id','workflow_sha')) and snapshot['run_attempt'] == op['attempt'],
                'retained trial snapshot differs from operation')
        task = dict(task_id=self.candidate['submitted']['task_id'],locator=self.value['worker']['locator'])
        require(request == dict(schema_version=2,configuration_revision=b['configuration_revision'],deployment_digest=b['deployment_digest'],
            operation_id=op['operation_id'],sequence=pending['sequence'],snapshot=snapshot,task=task,
            qualification=dict(kind='native-trial-certificate',digest=digest(certificate))), 'retained trial request substituted')

    def _save(self):
        self.document = self.journal.write(self.document, self.value)
        self.request = copy.deepcopy(self.value['request'])

    def local_guard(self, binding=None):
        c, r = self.native.provision, self.record
        require(self.journal.read() == self.document and self.document['value'] == self.value and
                c.store(c.root / 'trial-candidates').read() == self.value['candidates'] and
                c.store(c.root / 'trial-workflow').read() == self.value['workflow'] and
                c.store(c.root / 'trial').read() == self.value['provisioning'], 'native case ownership changed')
        require(self.value['phase'] in ('ready','fencing','bound') and
                r['created'] <= self.clock() < min(r['expires'], r['trial']['deployment']['expires'],
                    r['origin']['binding']['fence']['pending']['execution_deadline']), 'native case expired or terminal')
        require(c.session.owner == r['origin']['owner'] and c.session.scope == r['origin']['scope'],
                'native case original owner or scope changed')
        require(self.record == self.value['record'] and self.candidate == self.value['candidate'] and
                self.request == self.value['request'], 'native case object changed')
        if binding is not None: require(binding == self.binding, 'trial controller binding differs')

    def guard(self, binding=None, force=False):
        self.local_guard(binding)
        c, r = self.native.provision, self.record
        origin = r['origin']['binding']
        c.session._owned(origin)
        original = c.session.registry
        original_branch = original.unchanged(origin)
        trial_branch = self.registry.unchanged(self.binding)
        p = self.binding['deployment']['policy']
        repo = self.source.get('/repos/'+p['repository'])
        require(repo.get('id') == p['repository_id'] and repo.get('private') is True and
                repo.get('owner',{}).get('id') == r['pair']['identities']['owner_id'] and repo.get('default_branch') == p['target'],
                'native disposable source identity changed')
        require(original.ref(original.coordinates['registry_branch']) == origin['branch_head'] and
                original.ref(original_branch) == origin['software_revision'] and
                original.ref('agentic-trial-'+r['task_id']) == r['execution']['publication_revision'] and
                original.ref('agentic-trial-'+r['task_id']+'-execution') == self.value['workflow']['value']['revision_bound'],
                'original trial handoff changed')
        require(self.registry.ref(self.registry.coordinates['registry_branch']) == self.binding['branch_head'] and
                self.registry.ref(trial_branch) == self.binding['software_revision'], 'trial changed during original observation')
        d = self.binding['deployment']
        require(d == r['trial']['deployment'] and d['state'] == 'qualification' and d['qualification'] is None,
                'only the original unqualified disposable configuration is admitted')
        if self.value['phase'] == 'ready':
            require(self.value['certificate'] is None and self.value['pending'] is None and self.request is None and
                    self.binding == r['trial'], 'unowned trial preparation state')
        self.local_guard(binding)

    def _candidate(self, preparer):
        import submission
        from coding_parent import _FencedSource
        candidates = self.value['candidates']['value']
        require(candidates['pending'] is None and len(candidates['candidates']) == len(candidates['requests']) and
                self.candidate in candidates['candidates'], 'complete unchanged candidate preparation required')
        index = candidates['candidates'].index(self.candidate)
        def denied(): require(False, 'trial admission may not repair or resubmit candidates')
        from service import _source_token
        d = self.record['trial']['deployment']
        with _source_token('coding',preparer.coding,self.registry.api,d,self.record['pair']['identities'],
                          self.binding['configuration_revision'],self.clock,preparer.token_factory,self.guard) as scoped:
            submitted = self.candidate['submitted']
            root = '/repos/'+d['policy']['repository']
            pr = scoped.get(root+'/pulls/'+str(submitted['pr']))
            if pr['state'] == 'open':
                result = submission._submit(_FencedSource(scoped, self.guard, denied),d,
                    candidates['requests'][index], self.worker['files'])
                require(result == submitted, 'prepared trial candidate changed')
            else:
                # Closed/merged readback grants only access to the existing
                # terminal recovery path. It cannot pass task() or dispatch.
                require(self.value['phase'] == 'bound' and pr.get('merged') is True and
                        pr['head']['sha'] == submitted['head'] and pr['head']['ref'] == submitted['branch'] and
                        pr['head']['repo']['id'] == d['policy']['repository_id'] == pr['base']['repo']['id'] and
                        pr['base']['ref'] == d['policy']['target'] and
                        pr['user']['id'] == submitted['bot_id'] and pr['user'].get('type') == 'Bot' and
                        '<!-- agentic-task:'+digest(candidates['requests'][index])+' -->' in pr.get('body','') and
                        submission.existing_ref(scoped,root,submitted['branch']) == submitted['head'], 'closed trial candidate differs')
                commit = scoped.get(root+'/git/commits/'+submitted['head'])
                require(commit['sha'] == submitted['head'] and commit['tree']['sha'] == submitted['tree'] and
                        [v['sha'] for v in commit['parents']] == [self.record['pair']['fixture_revision']] and
                        submission._read_tree(scoped,root,submitted['tree'],self.guard) == self.worker['files'],
                        'closed trial candidate export changed')

    def task(self, binding, snapshot, locator, task_id):
        self.local_guard(binding)
        submitted = self.candidate['submitted']
        require(locator == self.value['worker']['locator'] and task_id == submitted['task_id'] and
                all(snapshot[k] == submitted[k] for k in ('pr','head')) and
                snapshot['base'] == self.record['pair']['fixture_revision'], 'trial candidate is not the admitted worker export')
        p = binding['deployment']['policy']
        root = '/repos/'+p['repository']
        pr = self.source.get(root+'/pulls/'+str(submitted['pr']))
        commit = self.source.get(root+'/git/commits/'+submitted['head'])
        from submission import existing_ref
        require(pr['state'] == 'open' and pr.get('draft') is False and pr.get('merged') is False and
                pr['head']['sha'] == submitted['head'] and pr['head']['ref'] == submitted['branch'] and
                pr['head']['repo']['id'] == p['repository_id'] == pr['base']['repo']['id'] and
                pr['base']['ref'] == p['target'] and pr['user'].get('id') == submitted['bot_id'] and pr['user'].get('type') == 'Bot' and
                existing_ref(self.source,root,submitted['branch']) == submitted['head'] and
                commit['tree']['sha'] == submitted['tree'] and [v['sha'] for v in commit['parents']] == [snapshot['base']],
                'current trial candidate changed')
        document = dict(kind='native-trial-case-task', submitted=copy.deepcopy(submitted),
            worker=self.value['worker'], certificate_digest=digest(self.value['certificate']))
        self.local_guard(binding)
        return dict(document=document, provenance={k:v for k,v in self.worker['proof'].items() if k != 'document'},
            task_digest=digest(document), expires=self.record['expires'], admission_established=False)

    def qualification(self, binding, controls_digest=None):
        self.local_guard(binding)
        certificate = self.value['certificate']
        require(self.value['phase'] == 'bound' and certificate is not None and
                certificate['operation'] == binding['fence']['pending'] and certificate['sequence'] == binding['fence']['sequence'] and
                (controls_digest is None or controls_digest == certificate['controls_digest']), 'native trial certificate differs or controls moved')
        return dict(document=copy.deepcopy(certificate), qualification_digest=digest(certificate), expires=certificate['expires'])

    def acquire(self, writer, before, op, snapshot, task, facts):
        self.guard(before)
        require(self.value['phase'] == 'ready', 'trial fence already attempted; never repeat writes')
        pending = copy.deepcopy(before['fence'])
        pending['sequence'] += 1; pending['pending'] = copy.deepcopy(op)
        certificate = dict(schema_version=1,kind='native-trial-certificate',record_digest=digest(self.record),
            worker=self.value['worker'],candidate=self.candidate,configuration_revision=before['configuration_revision'],
            deployment_digest=before['deployment_digest'],operation=op,sequence=pending['sequence'],
            controls_digest=facts['controls_digest'],issued=op['created'],expires=min(self.record['expires'],op['execution_deadline']),
            hosted_qualified=False,enforcement_active=False)
        request = dict(schema_version=2,configuration_revision=before['configuration_revision'],deployment_digest=before['deployment_digest'],
            operation_id=op['operation_id'],sequence=pending['sequence'],snapshot=snapshot,task=task,
            qualification=dict(kind='native-trial-certificate',digest=digest(certificate)))
        self.value.update(phase='fencing',pending=pending,certificate=certificate,request=request)
        self._save()  # Intent precedes every authority effect, including Git objects.
        after = writer.acquire_operation(before['branch_head'],before['configuration_revision'],op,before_effect=self.guard)
        self.binding = self.registry.authenticate_setup_progress(before,{OPERATION:pending})
        require(after == self.binding, 'retained native fence differs')
        self.value['phase']='bound'; self._save(); self.guard()
        return after

    def finalize(self, environment, broker_job_id):
        authority_release.authorize('broker-merge')
        return self._finalize(environment,broker_job_id)

    def _finalize(self, environment, broker_job_id):
        from broker_finalize import Finalizer
        from trusted_ci_policy import loads
        # The existing independently approved finalization/recovery variable is
        # supplied by the trusted caller, never inferred from a current branch.
        pin = loads(environment.get('AGENTIC_RECOVERY_PIN',''))
        Finalizer(None,self.registry.api,None,pin,environment,self.clock)._admit()
        self.guard()
        before = copy.deepcopy(self.binding)
        result = Finalizer(self.registry,self.registry.api,self.source,pin,environment,self.clock)._finalize(
            self.request['operation_id'],self.request['sequence'],broker_job_id,_admission=self)
        self.registry.authenticate_setup_progress(before,{OPERATION:result['fence']})
        self.value.update(phase='terminal',terminal=result)
        self._save()
        return result
