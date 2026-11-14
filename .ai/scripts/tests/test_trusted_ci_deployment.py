"""R6 R8 R9: read-only fail-closed deployment inspection."""
import copy
import unittest
from trusted_ci_fixtures import policy
from trusted_ci_policy import Refusal
import trusted_ci_deployment as d


def rules():
    return [dict(id=1, enforcement='active', bypass_actors=[], rules=[
        dict(type='pull_request', parameters=dict(required_approving_review_count=1,
             dismiss_stale_reviews_on_push=True, require_last_push_approval=True,
             require_code_owner_review=True, required_review_thread_resolution=True)),
        dict(type='required_status_checks', parameters=dict(strict_required_status_checks_policy=True,
             required_status_checks=[dict(context='AGENTIC trusted acceptance', integration_id=42)])),
        dict(type='deletion'), dict(type='non_fast_forward')]),
        dict(id=2, enforcement='active', bypass_actors=[dict(actor_type='User', actor_id=17,
             bypass_mode='pull_request')], rules=[dict(type='update')])]


class DeploymentTests(unittest.TestCase):
    def test_effective_strict_source_approval_and_update_boundary(self):
        d.check_rules(policy(), rules())
        for mutate in [lambda r: r[0].update(bypass_actors=[{'actor_type': 'RepositoryRole', 'actor_id': 5}]),
                       lambda r: r[0]['rules'][1]['parameters']['required_status_checks'][0].update(integration_id=15368),
                       lambda r: r[0]['rules'][0]['parameters'].update(required_approving_review_count=0),
                       lambda r: r[1]['bypass_actors'][0].update(actor_id=18),
                       lambda r: r[0]['rules'][0]['parameters'].update(require_code_owner_review=False),
                       lambda r: r.pop()]:
            r = rules()
            mutate(r)
            with self.assertRaises(Refusal):
                d.check_rules(policy(), r)

    def test_codeowners_are_exact_independent_reviewers(self):
        d.check_owners('* @maintainer\n', {'maintainer': 17}, policy())
        for text in ['* @coder\n', '*.py @maintainer\n', '* @maintainer\n/unsafe/ @coder\n', '']:
            with self.assertRaises(Refusal):
                d.check_owners(text, {'maintainer': 17, 'coder': 18}, policy())

    def test_no_local_file_can_establish_credential_separation(self):
        for attestation in [{}, {'credential_separation': True}]:
            with self.assertRaises(Refusal):
                d.check_access(attestation, policy())
