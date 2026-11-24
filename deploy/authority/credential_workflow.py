"""Durable setup dispatch and authenticated credential-consumer rendezvous.

An unknown dispatch is observed, never replayed. A workflow acknowledgement or
successful run is insufficient: each retained credential requires its own proof.
"""
import copy
import json
import time
from urllib.parse import quote

import authority_release
from setup import CredentialStaging, CREDENTIAL_NAMES, _credential_binding, _credential_purpose
from dispatch_controls import locked_reference
from trusted_ci_policy import object_fields, positive, require


class CredentialWorkflow:
    def __init__(self, staging, api, journal, sleep=time.sleep, monotonic=time.monotonic):
        require(isinstance(staging, CredentialStaging) and journal.root != staging.journal.root,
                'separate owned dispatch journal and native credential staging required')
        self.staging, self.api, self.journal = staging, api, journal
        self.sleep, self.monotonic = sleep, monotonic
        self.document = None

    def run(self):
        authority_release.authorize('bootstrap')
        return self._drive()

    def _guard(self):
        current = self.staging._guard()
        require(self.journal.read() == self.document, 'credential dispatch journal changed')
        return current

    def _save(self, state):
        self._guard()
        self.document = self.journal.write(self.document, state)

    def _runs(self, root):
        self._guard()
        runs = self.api.pages(root + '/runs', 'workflow_runs')
        require(isinstance(runs, list) and len(runs) <= 10000 and
                all(isinstance(r, dict) and positive(r.get('id')) for r in runs) and
                len({r['id'] for r in runs}) == len(runs), 'bounded unique workflow inventory required')
        return runs

    def _reference(self, policy):
        return locked_reference(self.api, policy, self._guard)

    def _drive(self):
        current, staged = self.staging._prepare()
        require(all(entry['phase'] != 'unstarted' for entry in staged['entries'].values()),
                'all credential write intents required before dispatch')
        binding = _credential_binding(current)
        challenges = {_credential_purpose(name): self.staging._challenge(name) for name in CREDENTIAL_NAMES}
        policy = current['deployment']['policy']
        workflow = '/repos/' + policy['authority_repository'] + '/actions/workflows/' + quote(policy['workflow'], safe='')
        run_root = '/repos/' + policy['authority_repository'] + '/actions/runs/'
        self.document = self.journal.read()
        if self.document is None:
            baseline = sorted(r['id'] for r in self._runs(workflow))
            self._save(dict(schema_version=1, kind='credential-workflow', binding=binding,
                challenges=challenges, baseline=baseline, phase='prepared', run_id=None))
        state = copy.deepcopy(self.document['value'])
        object_fields(state, ('schema_version', 'kind', 'binding', 'challenges', 'baseline', 'phase', 'run_id'),
                      'private credential dispatch')
        require(type(state['schema_version']) is int and state['schema_version'] == 1 and
                state['kind'] == 'credential-workflow' and state['binding'] == binding and
                state['challenges'] == challenges and state['phase'] in ('prepared', 'dispatch-started', 'selected', 'verified') and
                isinstance(state['baseline'], list) and all(positive(i) for i in state['baseline']) and
                len(set(state['baseline'])) == len(state['baseline']) and
                (state['run_id'] is None if state['phase'] in ('prepared', 'dispatch-started') else positive(state['run_id'])),
                'retained credential dispatch differs')
        if state['phase'] == 'prepared':
            branch = self._reference(policy)
            # Retain intent before POST. A lost response must not launch another run.
            state['phase'] = 'dispatch-started'
            self._save(state)
            self._guard()
            self.api.post(workflow + '/dispatches', dict(ref=branch,
                inputs=dict(challenges=json.dumps(challenges, sort_keys=True, separators=(',', ':')))))
        end = self.monotonic() + 300
        for _ in range(151):
            self._guard()
            require(self.monotonic() < end, 'credential workflow observation deadline exceeded')
            if state['phase'] == 'dispatch-started':
                candidates = [r for r in self._runs(workflow) if r['id'] not in state['baseline'] and
                    r.get('head_sha') == policy['workflow_sha'] and r.get('event') == 'workflow_dispatch' and
                    r.get('repository', {}).get('id') == policy['authority_repository_id']]
                require(len(candidates) <= 1, 'ambiguous dispatch; no automatic adoption or replay')
                if candidates:
                    state.update(phase='selected', run_id=candidates[0]['id'])
                    self._save(state)
            if state['phase'] in ('selected', 'verified'):
                path = run_root + str(state['run_id'])
                run = self.api.get(path)
                require(run.get('id') == state['run_id'] and run.get('head_sha') == policy['workflow_sha'] and
                        run.get('repository', {}).get('id') == policy['authority_repository_id'] and
                        run.get('event') == 'workflow_dispatch' and positive(run.get('run_attempt')),
                        'credential workflow identity changed')
                if run.get('status') == 'completed':
                    require(run.get('conclusion') == 'success', 'credential workflow did not succeed')
                    attempt = run['run_attempt']
                    jobs = self.api.pages(path + '/attempts/' + str(attempt) + '/jobs', 'jobs')
                    artifacts = self.api.pages(path + '/artifacts', 'artifacts')
                    require(isinstance(jobs, list) and isinstance(artifacts, list) and
                            len(jobs) <= 10000 and len(artifacts) <= 10000, 'bounded consumer inventory required')
                    for name in CREDENTIAL_NAMES:
                        purpose = _credential_purpose(name)
                        matching_jobs = [j for j in jobs if j.get('name') == 'credential proof (' + purpose + ')']
                        matching_artifacts = [a for a in artifacts if a.get('name') ==
                            'credential-proof-' + purpose + '-' + str(attempt)]
                        require(len(matching_jobs) == len(matching_artifacts) == 1,
                                'missing or ambiguous credential consumer')
                        self._guard()
                        self.staging._accept(name, self.api, dict(run_id=state['run_id'], attempt=attempt,
                            job_id=matching_jobs[0]['id'], artifact_id=matching_artifacts[0]['id']))
                    state['phase'] = 'verified'
                    self._save(state)
                    return dict(state='credentials-verified', verified=list(CREDENTIAL_NAMES), enforcement_active=False)
            self.sleep(2)
        require(False, 'credential workflow not observed; retain intent without redispatch')


class TrialWorkflow:
    """One native trial dispatch and exact closed-consumer/run binding.

    Missing or ambiguous evidence leaves the retained operation pending. Neither
    an unknown POST nor an absent artifact permits another dispatch.
    """
    def __init__(self, staging, api, journal):
        from setup import TrialReadStaging
        require(isinstance(staging, TrialReadStaging), 'native scoped trial-read staging required')
        require(journal.root != staging.provision.root / 'trial-read-staging', 'separate dispatch purpose journal required')
        self.staging, self.api, self.journal = staging, api, journal

    def run(self, prompt):
        authority_release.authorize('protected-run')
        import provenance
        import trial_handoff
        from registry import TRIAL
        from trusted_ci_policy import digest
        credential = self.staging.run()
        c = self.staging.provision
        original, trial = c.session.registry, self.staging.registry
        record, origin = trial_handoff.read(original, self.staging.revision, c.clock())
        require(isinstance(prompt, str) and digest(prompt) == record['prompt_digest'], 'exact native-approved prompt required')
        p = record['trial']['deployment']['policy']
        workflow = '/repos/' + p['authority_repository'] + '/actions/workflows/' + quote(p['workflow'], safe='')
        self.document = self.journal.read()
        def guard():
            self.staging._guard()
            require(self.journal.read() == self.document and c.clock() < credential['expires'],
                    'trial dispatch journal changed or delegated capability expired')
        def save(state):
            guard()
            self.document = self.journal.write(self.document, state)
        def runs():
            guard()
            values = self.api.pages(workflow + '/runs', 'workflow_runs')
            require(isinstance(values, list) and len(values) <= 10000 and
                    all(isinstance(r, dict) and positive(r.get('id')) for r in values) and
                    len({r['id'] for r in values}) == len(values), 'bounded unique trial dispatch inventory required')
            guard()
            return values
        if self.document is None:
            baseline = sorted(r['id'] for r in runs())
            save(dict(revision=self.staging.revision, credential=credential, baseline=baseline,
                phase='prepared', execution=None, revision_bound=None))
        state = copy.deepcopy(self.document['value'])
        object_fields(state, ('revision', 'credential', 'baseline', 'phase', 'execution', 'revision_bound'), 'retained trial dispatch')
        require(state['revision'] == self.staging.revision and state['credential'] == credential and
                state['phase'] in ('prepared', 'dispatch-started', 'bind-started', 'bound') and
                isinstance(state['baseline'], list) and all(positive(v) for v in state['baseline']) and
                len(set(state['baseline'])) == len(state['baseline']), 'retained native trial dispatch differs')
        if state['phase'] == 'prepared':
            branch = locked_reference(self.api, p, guard)
            state['phase'] = 'dispatch-started'
            save(state)
            guard()
            hint = dict(origin=original.coordinates, revision=self.staging.revision)
            self.api.post(workflow + '/dispatches', dict(ref=branch, inputs=dict(mode='qualification',
                handoff=json.dumps(hint, sort_keys=True, separators=(',', ':')), prompt=prompt)))
        if state['phase'] == 'dispatch-started':
            candidates = [r for r in runs() if r['id'] not in state['baseline'] and r.get('head_sha') == p['workflow_sha'] and
                r.get('repository', {}).get('id') == p['authority_repository_id'] and r.get('event') == 'workflow_dispatch']
            require(len(candidates) <= 1, 'ambiguous trial dispatch remains pending; never redispatch')
            require(len(candidates) == 1 and candidates[0].get('run_attempt') == 1,
                    'trial dispatch remains pending; never redispatch')
            run_id = candidates[0]['id']
            root = '/repos/' + p['authority_repository'] + '/actions/runs/' + str(run_id)
            jobs = [j for j in self.api.pages(root + '/attempts/1/jobs', 'jobs') if j.get('name') == 'trial handoff']
            artifacts = [a for a in self.api.pages(root + '/artifacts', 'artifacts') if
                a.get('name') == 'trial-handoff-' + record['task_id'] + '-1']
            require(len(jobs) == len(artifacts) == 1, 'closed trial consumer remains pending; never redispatch')
            locator = dict(run_id=run_id, attempt=1, job_id=jobs[0]['id'], artifact_id=artifacts[0]['id'])
            proof = provenance.authenticated_document(self.api, record['trial']['deployment'], locator,
                'trial-handoff', record['task_id'], c.clock())
            expected = dict(schema_version=1, kind='trial-handoff-consumption', publication_revision=self.staging.revision,
                record_digest=digest(record), task_id=record['task_id'], nonce=record['nonce'],
                **{k: credential[k] for k in ('token_digest', 'repository_id', 'permissions')},
                run_id=run_id, attempt=1, job_id=locator['job_id'])
            require(proof['document'] == expected and record['created'] <= proof['job_started'] <=
                    proof['artifact_created'] <= proof['job_completed'] < credential['expires'],
                    'closed trial consumer did not consume the exact native read capability')
            state.update(phase='bind-started', execution=dict(publication_revision=self.staging.revision,
                handshake=locator, credential=credential))
            save(state)
            bound = dict(record, execution=state['execution'])
            guard()
            original._replace(origin, {TRIAL: bound}, before_effect=guard,
                              trial_branch='agentic-trial-' + record['task_id'] + '-execution')
        revision = original.ref('agentic-trial-' + record['task_id'] + '-execution')
        bound, _ = trial_handoff.read(original, revision, c.clock())
        require(bound == dict(record, execution=state['execution']) and state['revision_bound'] in (None, revision),
                'native trial execution binding differs')
        guard()
        if state['phase'] != 'bound':
            state.update(phase='bound', revision_bound=revision)
            save(state)
        location = state['execution']['handshake']
        return dict(revision=revision, task_id=record['task_id'], run_id=location['run_id'], attempt=location['attempt'],
            expires=min(record['expires'], credential['expires']), hosted_qualified=False, enforcement_active=False)
