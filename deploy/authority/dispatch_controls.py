"""Approved native setup of the authority's immutable dispatch branch.

No source-repository rule is changed. This control is separate from acceptance
enforcement and is only writable through the held, human-owned setup context.
"""
import copy
from urllib.parse import quote

import authority_release
from configuration import SetupConfigurationSession
from trusted_ci_policy import digest, object_fields, positive, require, sha

NAME = 'agentic-authority-dispatch'


def desired(branch):
    return dict(name=NAME, target='branch', enforcement='active', bypass_actors=[],
        conditions=dict(ref_name=dict(include=['refs/heads/' + branch], exclude=[])),
        rules=[dict(type='update', parameters=dict(update_allows_fetch_and_merge=False)), dict(type='deletion')])


def preview(api, repository, repository_id, revision):
    require(positive(repository_id) and sha(revision), 'approved authority identity required')
    root = '/repos/' + repository
    current = api.get(root)
    branch = current.get('default_branch')
    require(current.get('id') == repository_id and current.get('private') is True and
            isinstance(branch, str) and 0 < len(branch) <= 255 and
            api.get(root + '/git/ref/heads/' + quote(branch, safe='')).get('object', {}).get('sha') == revision,
            'approved authority branch identity differs')
    rules = api.pages(root + '/rulesets')
    require(isinstance(rules, list) and len(rules) <= 10000 and
            all(isinstance(r, dict) and positive(r.get('id')) for r in rules) and
            len({r['id'] for r in rules}) == len(rules), 'bounded unique authority rules inventory required')
    require(not any(r.get('name') == NAME for r in rules), 'existing dispatch lock requires owned repair')
    return dict(schema_version=1, repository=repository, repository_id=repository_id,
        branch=branch, revision=revision, baseline=sorted(r['id'] for r in rules), desired=desired(branch))


def locked_reference(api, policy, guard):
    guard()
    root = '/repos/' + policy['authority_repository']
    repository = api.get(root)
    branch = repository.get('default_branch')
    require(repository.get('id') == policy['authority_repository_id'] and repository.get('private') is True and
            isinstance(branch, str) and 0 < len(branch) <= 255 and
            api.get(root + '/git/ref/heads/' + quote(branch, safe='')).get('object', {}).get('sha') ==
            policy['workflow_sha'], 'dispatch branch differs from approved software')
    effective = api.get(root + '/rules/branches/' + quote(branch, safe=''))
    require(isinstance(effective, list) and len(effective) <= 10000 and all(isinstance(r, dict) for r in effective),
            'effective dispatch reference controls unavailable')
    identifiers = {r.get('ruleset_id') for r in effective if r.get('type') == 'update' and
        positive(r.get('ruleset_id')) and r.get('ruleset_source_type') == 'Repository' and
        r.get('ruleset_source') == policy['authority_repository']}
    locked = False
    for identity in identifiers:
        value = api.get(root + '/rulesets/' + str(identity))
        if not (value.get('id') == identity and value.get('source_type') == 'Repository' and
                value.get('source') == policy['authority_repository'] and value.get('target') == 'branch' and
                value.get('enforcement') == 'active' and value.get('bypass_actors') == [] and
                value.get('conditions') == dict(ref_name=dict(include=['refs/heads/' + branch], exclude=[]))):
            continue
        rules = value.get('rules')
        if not isinstance(rules, list) or not all(isinstance(r, dict) for r in rules): continue
        updates = [r for r in rules if r.get('type') == 'update']
        deletions = [r for r in rules if r.get('type') == 'deletion']
        if (len(updates) == len(deletions) == 1 and
                updates[0].get('parameters') == dict(update_allows_fetch_and_merge=False) and
                any(r.get('type') == 'deletion' and r.get('ruleset_id') == identity and
                    r.get('ruleset_source_type') == 'Repository' and
                    r.get('ruleset_source') == policy['authority_repository'] for r in effective)):
            locked = True
    require(locked, 'dispatch reference requires active no-update/no-deletion rules without bypass')
    guard()
    return branch


class DispatchLock:
    def __init__(self, session, api, journal):
        require(isinstance(session, SetupConfigurationSession), 'native approved dispatch-lock session required')
        self.session, self.api, self.journal = session, api, journal
        self.document = None

    def run(self):
        authority_release.authorize('bootstrap')
        return self._apply()

    def _guard(self):
        repository = self.session.preview['authority_repository']
        current = self.session.require_effect('rules', repository + ':dispatch-lock')
        require(current['deployment']['state'] == 'setup' and self.journal.read() == self.document,
                'native dispatch-lock setup or journal changed')
        actor = self.api.get('/user')
        require(actor.get('type') == 'User' and actor.get('id') == self.session.owner['setup']['operator_id'],
                'dispatch-lock writer differs from approved native operator')
        require(self.session.require_effect('rules', repository + ':dispatch-lock') == current and
                self.journal.read() == self.document, 'dispatch-lock authorization changed during identity read')
        return current

    def _save(self, state):
        self._guard()
        self.document = self.journal.write(self.document, state)

    def _apply(self):
        self.document = self.journal.read()
        current = self._guard()
        policy = current['deployment']['policy']
        plan = self.session.preview['changes']['protections'].get('authority_dispatch')
        require(isinstance(plan, dict), 'approved exact dispatch-lock preview required')
        object_fields(plan, ('schema_version', 'repository', 'repository_id', 'branch', 'revision', 'baseline', 'desired'),
                      'dispatch-lock preview')
        require(type(plan['schema_version']) is int and plan['schema_version'] == 1 and
                plan['repository'] == policy['authority_repository'] and plan['repository_id'] == policy['authority_repository_id'] and
                plan['revision'] == policy['workflow_sha'] and plan['desired'] == desired(plan['branch']),
                'approved dispatch-lock identity differs')
        binding = dict(configuration_revision=current['configuration_revision'], deployment_digest=current['deployment_digest'],
            operation_id=current['fence']['pending']['operation_id'], approval_digest=self.session.owner['setup']['approval_digest'])
        root = '/repos/' + plan['repository']
        if self.document is None:
            require(preview(self.api, plan['repository'], plan['repository_id'], plan['revision']) == plan,
                    'dispatch-lock preview changed')
            self._save(dict(schema_version=1, binding=binding, plan_digest=digest(plan), phase='prepared', ruleset_id=None))
        state = copy.deepcopy(self.document['value'])
        object_fields(state, ('schema_version', 'binding', 'plan_digest', 'phase', 'ruleset_id'), 'private dispatch-lock state')
        require(type(state['schema_version']) is int and state['schema_version'] == 1 and state['binding'] == binding and
                state['plan_digest'] == digest(plan) and state['phase'] in ('prepared', 'create-started', 'created', 'verified') and
                (state['ruleset_id'] is None if state['phase'] in ('prepared', 'create-started') else positive(state['ruleset_id'])),
                'retained dispatch-lock setup differs')
        if state['phase'] == 'prepared':
            require(preview(self.api, plan['repository'], plan['repository_id'], plan['revision']) == plan,
                    'dispatch-lock preview changed')
            state['phase'] = 'create-started'
            self._save(state)
            self._guard()
            result = self.api.post(root + '/rulesets', plan['desired'])
            require(positive(result.get('id')), 'dispatch-lock creation identity unavailable')
            state.update(phase='created', ruleset_id=result['id'])
            self._save(state)
        require(state['phase'] != 'create-started', 'dispatch-lock creation outcome unknown; do not adopt or replay')
        observed = self.api.get(root + '/rulesets/' + str(state['ruleset_id']))
        require(observed.get('id') == state['ruleset_id'] and observed.get('source') == plan['repository'] and
                observed.get('source_type') == 'Repository' and
                {k: observed.get(k) for k in plan['desired']} == plan['desired'], 'owned dispatch-lock controls differ')
        require(locked_reference(self.api, policy, self._guard) == plan['branch'], 'dispatch-lock branch changed')
        state['phase'] = 'verified'
        self._save(state)
        return dict(state='dispatch-locked', ruleset_id=state['ruleset_id'], enforcement_active=False)
