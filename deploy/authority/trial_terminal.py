"""Held first-case terminal collection, never hosted qualification or execution.

Only the original bound run can supply the CLOSED terminal. Native observation
and exact retained-token cleanup reuse their existing guards and journals.
"""
import authority_release
from trial_candidates import Prepare
from trial_controller import Native as Controller
from trial_handoff import Native as Handoff
import trial_launch
from trial_setup import Provision
from trusted_ci_github import GitHub
from trusted_ci_policy import digest, positive, require


class Native:
    def __init__(self, controller, token_factory=GitHub):
        self.controller, self.token_factory = controller, token_factory

    def collect(self, prompt):
        authority_release.authorize('qualify-live')
        return self._collect(prompt)

    def cleanup(self):
        authority_release.authorize('bootstrap')
        return self._cleanup()

    def _owner(self):
        require(type(self.controller) is Controller and type(self.controller.candidates) is Prepare,
                'actual native first-case controller required')
        native = self.controller.candidates.native
        require(type(native) is Handoff and type(native.provision) is Provision,
                'actual original native provisioning owner required')
        return native.provision

    def _cleanup(self):
        # This separate path needs no live admission and cannot resume a trial.
        trial_launch.revoke(self._owner(), self.token_factory, name='direct-push')

    def _collect(self, prompt, source=None):
        c = self._owner()
        journal = c.store(c.root / 'trial-controller')
        document = journal.read()
        require(document is not None, 'retained first-case controller required')
        value = document['value']
        require(value.get('name') == 'direct-push' and value.get('phase') == 'bound' and
                value.get('prompt_digest') == digest(prompt),
                'exact bound first case and prompt required; never adopt terminal state')
        launch_journal = c.store(c.root / 'trial-case-launch')
        launch = launch_journal.read()
        require(launch is not None and launch['value'].get('phase') == 'consumed',
                'consumed original first-case launch required')
        state = launch['value']
        link = state['link']
        handshake = link['handshake']
        snapshot = value['request']['snapshot']
        run_id, attempt = snapshot['run_id'], snapshot['run_attempt']
        require(positive(run_id) and type(attempt) is int and attempt == 1 and
                all(positive(handshake.get(k)) for k in ('run_id', 'attempt', 'job_id', 'artifact_id')) and
                handshake['run_id'] == run_id and handshake['attempt'] == attempt and
                link['revision'] == state['revision'] and link['credential'] == state['credential'] and
                state['ready']['candidate'] == value['candidate'] and
                state['ready']['task_id'] == value['record']['task_id'] and
                digest(state['ready']['prompt']) == value['prompt_digest'],
                'original consumed launch and controller coordinates differ')
        registry = self.controller.candidates.native.registry
        root = registry.root + '/actions/runs/' + str(run_id)
        jobs = registry.api.pages(root + '/attempts/1/jobs', 'jobs')
        artifacts = registry.api.pages(root + '/artifacts', 'artifacts')
        for entries in (jobs, artifacts):
            require(isinstance(entries, list) and len(entries) <= 10000 and
                    all(isinstance(v, dict) and positive(v.get('id')) for v in entries) and
                    len({v['id'] for v in entries}) == len(entries),
                    'bounded unique first-case terminal inventory required')
        jobs = [v for v in jobs if v.get('name') == 'finalize']
        name = 'trial-case-terminal-' + value['record']['task_id'] + '-1'
        artifacts = [v for v in artifacts if v.get('name') == name]
        require(len(jobs) == len(artifacts) == 1 and jobs[0].get('run_id') == run_id and
                jobs[0].get('status') == 'completed' and jobs[0].get('conclusion') == 'success',
                'exact CLOSED first-case terminal unavailable; preserve hold')
        require(journal.read() == document and launch_journal.read() == launch,
                'native terminal ownership changed during discovery')
        locator = dict(run_id=run_id, attempt=attempt, job_id=jobs[0]['id'], artifact_id=artifacts[0]['id'])
        terminal = self.controller._observe_terminal(prompt, 'direct-push', locator, source)
        # An exception from persistence or cleanup is deliberately not converted
        # into success. Collection never retries a terminal or adopts readback.
        self._cleanup()
        return dict(terminal_collected=True, cleanup_complete=True, terminal=terminal,
                    intended_denial_verified=True, hosted_qualified=False, enforcement_active=False)
