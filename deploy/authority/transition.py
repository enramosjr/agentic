"""Fenced, approved required-context transition. Never activates enforcement.

The trusted administrator retains the exact approved plan across interruptions.
Runtime artifact authentication and qualification are separate, still-held paths.
"""
import copy

from authority_protocol import validate_deployment
from configuration import require_session
from merge_controls import check_rules
from reconcile import canonical, desired_rules
from trusted_ci_policy import digest, object_fields, positive, require

FIELDS = ('schema_version configuration_revision branch_head fence before desired foreign old_controls new_controls').split()


class ContextTransition:
    def __init__(self, api, registry, session):
        self.api, self.registry, self.session = api, registry, session

    def validate_desired(self, current, desired):
        old = current['deployment']
        new = validate_deployment(desired)
        require(new['generation'] == old['generation'] + 1 and new['state'] == 'qualification' and
                new['qualification'] is None, 'transition must produce an unqualified next generation')
        for key in ('repository', 'repository_id', 'target', 'authority_repository', 'authority_repository_id'):
            require(new['policy'][key] == old['policy'][key], 'transition cannot change repository coordinates')
        require(new['resources']['operation_id'] == old['resources']['operation_id'], 'stable rule ownership nonce changed')
        require(new['policy']['workflow_sha'] == current['software_revision'],
                'next policy must pin the installed approved software')
        require(all(new['policy']['epoch'] != c['epoch'] and new['policy']['check_name'] != c['check_name']
                    for c in current['fence']['contexts']), 'transition requires a never-used epoch and check context')

    def source_identity(self, deployment):
        p = deployment['policy']
        repo = self.api.get('/repos/' + p['repository'])
        require(repo['id'] == p['repository_id'] and repo['default_branch'] == p['target'] and
                repo.get('allow_merge_commit') is True, 'transition target identity or merge capability changed')

    def guard(self, deployment):
        require_session(self.session, 'rules', deployment['policy']['repository'])
        self.source_identity(deployment)
        require_session(self.session, 'rules', deployment['policy']['repository'])

    def inventory(self, deployment):
        self.source_identity(deployment)
        root = '/repos/' + deployment['policy']['repository']
        result = []
        for item in self.api.pages(root + '/rulesets?includes_parents=true'):
            require(positive(item['id']), 'ruleset identity unavailable')
            if not all(key in item for key in ('rules', 'bypass_actors', 'target', 'conditions')):
                item = self.api.get(root + '/rulesets/' + str(item['id']) + '?includes_parents=true')
            require(all(key in item for key in ('id', 'name', 'target', 'enforcement', 'conditions', 'rules', 'bypass_actors')),
                    'complete ruleset readback required for transition')
            result.append(dict(canonical(item), id=item['id']))
        require(len(result) <= 10000 and len({r['id'] for r in result}) == len(result), 'ambiguous ruleset inventory')
        return sorted(result, key=lambda value: value['id'])

    def preview(self, desired):
        current = self.registry.binding(check_software=False)
        old = current['deployment']
        new = copy.deepcopy(validate_deployment(desired))
        self.validate_desired(current, new)
        inventory = self.inventory(old)
        expected = desired_rules(old)
        owned = {}
        for kind in ('acceptance', 'updates'):
            identity = old['resources'].get(kind + '_rule', '')
            require(isinstance(identity, str) and identity.isascii() and identity.isdigit() and int(identity) > 0,
                    'registered old control identity required')
            matches = [r for r in inventory if r['id'] == int(identity)]
            require(len(matches) == 1 and canonical(matches[0]) == expected[kind], 'old owned control drift')
            owned[kind] = matches[0]
            new['resources'].pop(kind + '_rule', None)
        require(len({r['id'] for r in owned.values()}) == 2, 'separate owned controls required')
        new_rules = desired_rules(new)
        require(not any(r['name'] in {v['name'] for v in new_rules.values()} for r in inventory),
                'new context control name already exists; use the retained approved recovery plan')
        foreign = [r for r in inventory if r['id'] not in {v['id'] for v in owned.values()}]
        return dict(schema_version=2, configuration_revision=current['configuration_revision'],
                    branch_head=current['branch_head'], fence=current['fence'], before=old,
                    desired=new, foreign=foreign, old_controls=owned, new_controls=new_rules)

    def state(self, plan):
        inventory = self.inventory(plan['before'])
        old_ids = {r['id'] for r in plan['old_controls'].values()}
        new_names = {r['name'] for r in plan['new_controls'].values()}
        foreign = [r for r in inventory if r['id'] not in old_ids and r['name'] not in new_names]
        require(foreign == plan['foreign'], 'unrelated protections changed during transition')
        old, new = {}, {}
        for kind in ('acceptance', 'updates'):
            old_matches = [r for r in inventory if r['id'] == plan['old_controls'][kind]['id']]
            require(not old_matches or old_matches == [plan['old_controls'][kind]], 'old owned control changed')
            old[kind] = old_matches[0] if old_matches else None
            matches = [r for r in inventory if r['name'] == plan['new_controls'][kind]['name']]
            require(len(matches) <= 1 and all(canonical(r) == plan['new_controls'][kind] for r in matches),
                    'new owned control drift or duplicate')
            new[kind] = matches[0] if matches else None
        require(all(old.values()) or all(new.values()), 'old gate missing before the complete new gate exists')
        return old, new

    def effective(self, plan, new):
        require(all(new.values()), 'new transition controls incomplete')
        check_rules(plan['desired'], list(new.values()))
        root = '/repos/' + plan['desired']['policy']['repository']
        effective = self.api.pages(root + '/rules/branches/' + plan['desired']['policy']['target'])
        for rule in new.values():
            def semantics(item):
                return {'type': item['type'], 'parameters': item.get('parameters', {})}
            observed = [semantics(r) for r in effective if r['ruleset_id'] == rule['id']]
            expected = [semantics(r) for r in rule['rules']]
            require(sorted(observed, key=digest) == sorted(expected, key=digest),
                    'effective new rule semantics differ from the required gate')

    def next_record(self, plan, new):
        updated = copy.deepcopy(plan['desired'])
        for kind in ('acceptance', 'updates'):
            updated['resources'][kind + '_rule'] = str(new[kind]['id'])
        return updated

    def apply(self, plan, approval):
        object_fields(plan, FIELDS, 'approved context transition')
        require(type(plan['schema_version']) is int and plan['schema_version'] == 2 and digest(plan) == approval,
                'exact context transition preview approval required')
        old, desired = validate_deployment(plan['before']), validate_deployment(plan['desired'])
        root = '/repos/' + old['policy']['repository']
        require(self.session is not None, 'owned configuration session required before mutation')
        current = self.registry.binding(check_software=False)
        self.validate_desired(dict(current, deployment=old, fence=plan['fence']), desired)
        object_fields(plan['old_controls'], ('acceptance', 'updates'), 'old transition controls')
        require({v['id'] for v in plan['old_controls'].values()} ==
                {int(old['resources'][kind + '_rule']) for kind in ('acceptance', 'updates')} and
                len({v['id'] for v in plan['old_controls'].values()}) == 2,
                'transition old control identities differ')
        # Bind the plan's control bodies back to the exact approved deployments.
        require(plan['new_controls'] == desired_rules(desired) and all(
                canonical(plan['old_controls'][kind]) == desired_rules(old)[kind]
                for kind in ('acceptance', 'updates')), 'transition plan controls differ from policy')
        if current['deployment'] != old:
            # All reads. Do not replay host mutations or infer success from state.
            previous, new = self.state(plan)
            require(not any(previous.values()), 'old controls remain after the claimed registry transition')
            self.effective(plan, new)
            updated = self.next_record(plan, new)
            expected_fence = copy.deepcopy(plan['fence'])
            expected_fence['contexts'].append(dict(epoch=desired['policy']['epoch'],
                check_name=desired['policy']['check_name'], activated=False))
            self.session.recover_transition(plan['branch_head'], plan['configuration_revision'], digest(old),
                updated, plan['fence'], expected_fence)
            self.guard(updated)
            return {'state': 'qualification', 'enforcement_active': False, 'deployment_digest': digest(updated)}
        self.guard(old)
        require(current['configuration_revision'] == plan['configuration_revision'] and
                current['branch_head'] == plan['branch_head'] and current['fence'] == plan['fence'],
                'transition configuration changed; authenticated recovery required')
        for kind in ('acceptance', 'updates'):
            _, new = self.state(plan)
            if new[kind] is None:
                self.guard(old)
                observed = self.api.post(root + '/rulesets', plan['new_controls'][kind])
                require(positive(observed['id']) and canonical(observed) == plan['new_controls'][kind],
                        'created context control differs')
        _, new = self.state(plan)
        self.effective(plan, new)  # The new non-bypass gate precedes every old-rule deletion.
        for kind in ('acceptance', 'updates'):
            previous, new = self.state(plan)
            self.effective(plan, new)
            if previous[kind] is not None:
                self.guard(old)
                self.api.fetch(root + '/rulesets/' + str(previous[kind]['id']), method='DELETE', binary=True)
        previous, new = self.state(plan)
        require(not any(previous.values()), 'superseded owned controls remain')
        self.effective(plan, new)
        updated = self.next_record(plan, new)
        # No activation and no fence finalization: qualification and authenticated
        # terminal readback still have to complete in the trusted runtime.
        self.session.write_configuration(digest(old), updated)
        return {'state': 'qualification', 'enforcement_active': False, 'deployment_digest': digest(updated)}
