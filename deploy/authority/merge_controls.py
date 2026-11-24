"""V2 broker rules; the legacy human-merge contract stays unchanged."""
import copy

from authority_protocol import validate_deployment
from trusted_ci_deployment import check_rules as check_legacy_review_rules
from trusted_ci_policy import require


def check_rules(deployment, rulesets):
    d = validate_deployment(deployment)
    require(isinstance(rulesets, list) and rulesets, 'effective rules unavailable')
    checked = copy.deepcopy(rulesets)
    updates = 0
    for original, rule in zip(rulesets, checked):
        require(isinstance(original.get('rules'), list) and
                len({r['type'] for r in original['rules']}) == len(original['rules']),
                'ambiguous effective rule types')
        types = {r['type'] for r in original['rules']}
        if 'update' in types:
            updates += 1
            require(not types & {'pull_request', 'required_status_checks'},
                    'merge update exception must be separate from acceptance')
            require(original.get('bypass_actors') == [{'actor_type': 'Integration',
                    'actor_id': d['apps']['merge'], 'bypass_mode': 'pull_request'}],
                    'only the scoped merge App may update through a pull request')
            # Reuse v1's unchanged review/check/safety validator after validating
            # the REAL v2 update exception above. This copy never reaches GitHub.
            rule['bypass_actors'] = [{'actor_type': 'User', 'actor_id': d['policy']['merge_actors'][0],
                                      'bypass_mode': 'pull_request'}]
        for item in original['rules']:
            if item['type'] == 'pull_request':
                require(item['parameters'].get('allowed_merge_methods') == ['merge'],
                        'broker requires merge commits only')
        require('merge_queue' not in types, 'merge queues are unsupported')
    require(updates, 'broker update restriction unavailable')
    check_legacy_review_rules(d['policy'], checked)
