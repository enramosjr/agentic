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


def case_journal(base, candidate):
    return base + ('-'+candidate['name'] if candidate['name'] in ('coding-update','missing-approval') else '')


def authenticated(value, binding=None):
    from trial_case import Hosted
    require(type(value) in (Admission, Hosted), 'actual authenticated trial controller admission required')
    require(value.worker is not None, 'authenticated CLOSED worker required')
    value.local_guard(binding)
    return value


class Native:
    def __init__(self, candidates):
        self.candidates = candidates

    def open(self, prompt, name):
        authority_release.authorize('qualify-live')
        return self._open(prompt, name)

    def recover_terminal(self, prompt, name):
        authority_release.authorize('qualify-live')
        return self._recover_terminal(prompt,name)

    def _recover_terminal(self, prompt, name, source=None):
        require(type(self.candidates) is Prepare, 'actual native candidate preparer required')
        native=self.candidates.native
        retained=native.provision.store(native.provision.root/case_journal('trial-controller',dict(name=name))).read()
        require(retained is not None and retained['value']['prompt_digest']==digest(prompt) and retained['value']['name']==name,
                'resume only the exact retained native terminal case')
        result=Admission(native,source or native.provision.api,recover_terminal=True,name=name)
        return copy.deepcopy(result.value['terminal'])

    def observe_terminal(self, prompt, name, locator):
        authority_release.authorize('qualify-live')
        return self._observe_terminal(prompt,name,locator)

    def _observe_terminal(self, prompt, name, locator, source=None):
        require(type(self.candidates) is Prepare, 'actual native candidate preparer required')
        native=self.candidates.native
        retained=native.provision.store(native.provision.root/case_journal('trial-controller',dict(name=name))).read()
        require(retained is not None and retained['value']['prompt_digest']==digest(prompt) and retained['value']['name']==name and
                name in ('direct-push','coding-update','missing-approval'),
                'exact native host case terminal observation required')
        admission=Admission(native,source or native.provision.api,terminal_locator=locator,name=name)
        completed=native._worker_completion(admission.record,prompt,admission.source)
        require(completed['result']==admission.value['worker'], 'retained CLOSED worker changed')
        admission.worker=completed
        admission._candidate(self.candidates)
        from authority_github import Readers,current_snapshot
        s=admission.request['snapshot']; d=admission.binding['deployment']
        require(current_snapshot(Readers(admission.source,admission.registry.api,d),d,s['pr'],s['run_id'],s['run_attempt'])==s,
                'host candidate or target changed before native terminal observation')
        admission.guard()
        result=dict(binding=copy.deepcopy(admission.binding),**admission.terminal_proof)
        admission.value.update(phase='terminal',terminal=result); admission._save()
        return copy.deepcopy(result)

    def _open(self, prompt, name, source=None):
        require(type(self.candidates) is Prepare, 'actual native candidate preparer required')
        preparer, native = self.candidates, self.candidates.native
        require(type(native) is NativeHandoff and type(native.provision) is Provision, 'actual authenticated native trial required')
        c = native.provision
        source = source or c.api
        journal = c.store(c.root / case_journal('trial-controller',dict(name=name)))
        document = journal.read()
        if document is None:
            history=[]
            if name in ('coding-update','missing-approval'):
                predecessor='direct-push' if name=='coding-update' else 'coding-update'
                previous=c.store(c.root/case_journal('trial-controller',dict(name=predecessor))).read()
                require(previous is not None and previous['value']['phase']=='terminal' and
                        previous['value']['name']==predecessor and previous['value']['prompt_digest']==digest(prompt) and
                        'locator' in previous['value']['terminal'], 'owned independently observed first terminal required')
                prior=previous['value']
                publication=c.store(c.root/case_journal('trial-case-publication',dict(name=predecessor))).read()
                require(publication is not None and publication['value']['phase']=='bound' and
                        publication['value']['initial']['request']==prior['request'] and
                        publication['value']['initial']['certificate']==prior['certificate'], 'owned first execution publication required')
                history=copy.deepcopy(prior['history'])+[dict(revision=publication['value']['revision_bound'],terminal=prior['terminal']['locator'])]
                from trial_case import baseline
                settled=baseline(c.session.registry,native.registry,prior['record'],history,c.clock)
                require(settled==prior['terminal']['binding'], 'owned first native completion differs')
                if predecessor=='coding-update':
                    first=c.store(c.root/'trial-controller').read()
                    require(first==prior['previous'] and first['value']['phase']=='terminal', 'owned first native completion changed')
                    require(baseline(c.session.registry,native.registry,prior['record'],history[:1],c.clock)==first['value']['terminal']['binding'],
                            'owned first native terminal differs')
                native.registry.unchanged(settled)
                candidates=c.store(c.root/'trial-candidates').read()
                require(candidates==prior['candidates'] and c.store(c.root/'trial-workflow').read()==prior['workflow'] and
                        c.store(c.root/'trial').read()==prior['provisioning'], 'original native trial ownership changed')
                completed=native._worker_completion(prior['record'],prompt,source)
                require(completed['result']==prior['worker'], 'original CLOSED worker differs')
                result=dict(candidates=candidates['value']['candidates'],worker=prior['worker'])
                completed=dict(completed,record=prior['record'],retained=prior['workflow'])
            else:
                result = preparer._run(prompt, source)
                completed = native._completion(prompt, source)
                candidates = c.store(c.root / 'trial-candidates').read()
            matches = [v for v in result['candidates'] if v['name'] == name]
            require(len(matches) == 1 and completed['result'] == result['worker'], 'exact prepared trial case required')
            value = dict(kind='native-trial-controller', prompt_digest=digest(prompt), name=name,
                record=completed['record'], workflow=completed['retained'], candidates=candidates,
                provisioning=copy.deepcopy(c.document), candidate=matches[0], worker=completed['result'],
                phase='ready', certificate=None, request=None, pending=None, terminal=None,history=history)
            if history:
                value['previous']=previous
            document = journal.write(None, value)
        value = document['value']
        require(value['kind'] == 'native-trial-controller' and value['prompt_digest'] == digest(prompt) and
                value['name'] == name, 'resume only the exact retained native case')
        admission = Admission(native, source,name=name)
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
    def __init__(self, native, source, recover_terminal=False, terminal_locator=None,name=None):
        require(type(native) is NativeHandoff and type(native.provision) is Provision, 'actual authenticated native trial required')
        self.native, self.source = native, source
        c = native.provision
        self.journal = c.store(c.root / case_journal('trial-controller',dict(name=name)))
        self.document = self.journal.read()
        require(self.document is not None, 'native case intent required')
        self.value = copy.deepcopy(self.document['value'])
        object_fields(self.value, ('kind prompt_digest name record workflow candidates provisioning candidate worker '
            'phase certificate request pending terminal history').split()+(['previous'] if self.value.get('history') else []), 'retained native case')
        self.registry, self.clock = native.registry, native.provision.clock
        self.record = self.value['record']
        record, _ = read(c.session.registry,self.value['workflow']['value']['revision_bound'],self.clock())
        require(record == self.record and self.value['workflow']['value']['execution'] == record['execution'],
                'retained native case substituted authenticated handoff')
        self.candidate = copy.deepcopy(self.value['candidate'])
        self.request = copy.deepcopy(self.value['request'])
        self.worker = None
        from trial_case import case_baseline
        self.baseline=case_baseline(c.session.registry,self.registry,self.record,self.value,self.clock)
        self.binding = copy.deepcopy(self.baseline)
        if terminal_locator is not None:
            require(not recover_terminal and self.value['phase']=='bound' and self.candidate['name'] in ('direct-push','coding-update','missing-approval'),
                    'only an owned bound host case can observe a terminal producer')
            self._retained()
            from provenance import authenticated_document
            s=self.request['snapshot']
            require(terminal_locator['run_id']==s['run_id'] and terminal_locator['attempt']==s['run_attempt'],
                    'terminal producer belongs to another case run')
            proof=authenticated_document(self.registry.api,self.binding['deployment'],terminal_locator,
                                         'trial-case-terminal',self.record['task_id'],self.clock())
            value=proof['document']
            object_fields(value,('schema_version kind request_digest certificate_digest before after completed').split(),'closed case terminal')
            require(type(value['schema_version']) is int and value['schema_version']==1 and value['kind']=='trial-case-terminal' and
                    value['request_digest']==digest(self.request) and value['certificate_digest']==digest(self.value['certificate']) and
                    type(value['completed']) is int and proof['job_started']<=value['completed']<=proof['artifact_created']<=proof['job_completed'],
                    'closed terminal substituted case or producer interval')
            before=value['before']
            require(before['fence']==self.value['pending'] and
                    {k:v for k,v in before.items() if k not in ('branch_head','fence')}==
                    {k:v for k,v in self.binding.items() if k not in ('branch_head','fence')}, 'closed terminal parent differs')
            fence=copy.deepcopy(before['fence']); fence['pending']=None
            receipt=value['after']['fence']['completed'][-1]
            require(receipt['operation_id']==self.request['operation_id'] and receipt['sequence']==self.request['sequence'] and
                    receipt['kind']=='not-submitted', 'closed host terminal operation differs')
            fence['completed'].append(receipt)
            self.binding=self.registry.authenticate_setup_progress(before,{OPERATION:fence})
            require(self.binding==value['after'], 'closed host terminal commit differs')
            self.terminal_proof=dict(locator=copy.deepcopy(terminal_locator),document=value,
                                     producer={k:v for k,v in proof.items() if k!='document'})
            self.guard()
            return
        if recover_terminal:
            require(self.value['phase']=='closing', 'exact retained terminal intent required; never repeat finalization')
            self._retained()
            retained=self.value['terminal']
            object_fields(retained,('before','receipt'),'native terminal intent')
            before=retained['before']
            require(before['fence']==self.value['pending'] and
                    {k:v for k,v in before.items() if k not in ('branch_head','fence')}==
                    {k:v for k,v in self.binding.items() if k not in ('branch_head','fence')}, 'native terminal parent differs')
            from operation_fence import terminal
            receipt=terminal(retained['receipt'])
            op=self.value['pending']['pending']
            require(receipt['operation_id']==op['operation_id'] and receipt['sequence']==before['fence']['sequence'],
                    'native terminal receipt substituted operation')
            fence=copy.deepcopy(before['fence']); fence['pending']=None; fence['completed'].append(receipt)
            self.binding=self.registry.authenticate_setup_progress(before,{OPERATION:fence})
            self.guard()
            self.value.update(phase='terminal',terminal=copy.deepcopy(self.binding)); self._save()
            return
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
        require(self.value['phase'] in ('ready','fencing','bound','closing') and
                r['created'] <= self.clock() < min(r['expires'], r['trial']['deployment']['expires'],
                    r['origin']['binding']['fence']['pending']['execution_deadline']), 'native case expired or terminal')
        require(c.session.owner == r['origin']['owner'] and c.session.scope == r['origin']['scope'],
                'native case original owner or scope changed')
        require(self.record == self.value['record'] and self.candidate == self.value['candidate'] and
                self.request == self.value['request'], 'native case object changed')
        if self.value['history']:
            predecessor='direct-push' if self.candidate['name']=='coding-update' else 'coding-update'
            require(c.store(c.root/case_journal('trial-controller',dict(name=predecessor))).read()==self.value['previous'] and
                    self.value['previous']['value']['phase']=='terminal' and
                    self.value['previous']['value']['terminal']['binding']==self.baseline,
                    'owned prior native completion changed')
            if predecessor=='coding-update':
                require(c.store(c.root/'trial-controller').read()==self.value['previous']['value']['previous'],
                        'owned first native completion changed')
        launch=c.store(c.root/case_journal('trial-case-launch',self.candidate)).read()
        if launch is not None and self.value['phase'] in ('bound','closing'):
            from trial_case import CaseReadStaging
            staging=c.store(c.root/case_journal(CaseReadStaging.JOURNAL,self.candidate)).read()
            link=launch['value']['link']
            require(launch['value']['phase']=='consumed' and launch['value']['ready']['candidate']==self.candidate and
                    staging is not None and staging['value']['phase'] in ('secret-started','staged') and
                    staging['value']['revision']==link['revision'] and
                    digest(staging['value']['credential']['token'])==link['credential']['token_digest'] and
                    self.clock()<min(link['credential']['expires'],staging['value']['credential']['expires'],self.value['certificate']['expires']),
                    'native case launch delegation changed or expired')
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
        from trial_case import history_guard
        history_guard(original,r,self.value['history'])
        d = self.binding['deployment']
        require(d == r['trial']['deployment'] and d['state'] == 'qualification' and d['qualification'] is None,
                'only the original unqualified disposable configuration is admitted')
        if self.value['phase'] == 'ready':
            require(self.value['certificate'] is None and self.value['pending'] is None and self.request is None and
                    self.binding == self.baseline, 'unowned trial preparation state')
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

    def acquire(self, writer, before, op, snapshot, task, facts, before_effect=None):
        self.guard(before)
        def guard():
            self.guard()
            if before_effect is not None: before_effect()
        guard()
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
        after = writer.acquire_operation(before['branch_head'],before['configuration_revision'],op,before_effect=guard)
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
        require(self.value['phase']=='bound', 'terminal intent already retained; recover read-only without replay')
        before = copy.deepcopy(self.binding)
        result = Finalizer(self.registry,self.registry.api,self.source,pin,environment,self.clock)._finalize(
            self.request['operation_id'],self.request['sequence'],broker_job_id,_admission=self)
        self.registry.authenticate_setup_progress(before,{OPERATION:result['fence']})
        self.value.update(phase='terminal',terminal=result)
        self._save()
        return result

    def _retain_terminal(self, before, terminal):
        self.guard(before)
        require(self.value['phase']=='bound', 'native terminal intent already exists')
        self.value.update(phase='closing',terminal=dict(before=copy.deepcopy(before),receipt=copy.deepcopy(terminal)))
        self._save()
