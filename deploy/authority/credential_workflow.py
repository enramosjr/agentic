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
