"""Local control contracts for the sole, scoped broker update exception."""
import backend_test_support
import copy
import unittest

from test_authority_protocol import deployment
from trusted_ci_policy import Refusal
import reconcile
from merge_controls import check_rules


class SoleMergePath(unittest.TestCase):
    def rules(self):
        d = deployment()
        d['resources']['operation_id'] = 'a' * 32
        return d, [dict(rule, id=i) for i, rule in enumerate(reconcile.desired_rules(d).values(), 1)]

    def test_only_merger_integration_can_update_via_pull_request(self):
        d, rules = self.rules()
        self.assertEqual(rules[1]['bypass_actors'], [
            {'actor_type': 'Integration', 'actor_id': d['apps']['merge'], 'bypass_mode': 'pull_request'}])
        check_rules(d, rules)

    def test_human_coder_issuer_admin_always_and_acceptance_bypass_are_refused(self):
        d, rules = self.rules()
        for exception in [
            {'actor_type': 'User', 'actor_id': 17, 'bypass_mode': 'pull_request'},
            *({'actor_type': 'Integration', 'actor_id': d['apps'][p], 'bypass_mode': 'pull_request'}
              for p in ('coding', 'issuer', 'admin', 'reader')),
            {'actor_type': 'Integration', 'actor_id': d['apps']['merge'], 'bypass_mode': 'always'},
        ]:
            changed = copy.deepcopy(rules)
            changed[1]['bypass_actors'] = [exception]
            with self.subTest(exception=exception), self.assertRaises(Refusal):
                check_rules(d, changed)
        changed = copy.deepcopy(rules)
        changed[0]['bypass_actors'] = rules[1]['bypass_actors']
        with self.assertRaises(Refusal):
            check_rules(d, changed)

    def test_missing_duplicate_merged_rules_or_squash_do_not_authorize(self):
        d, rules = self.rules()
        for defect in ('missing', 'duplicate', 'combined', 'squash'):
            changed = copy.deepcopy(rules)
            if defect == 'missing':
                changed[1]['bypass_actors'] = []
            elif defect == 'duplicate':
                changed[1]['bypass_actors'] *= 2
            elif defect == 'combined':
                changed[0]['rules'].append({'type': 'update'})
            else:
                changed[0]['rules'][0]['parameters']['allowed_merge_methods'] = ['merge', 'squash']
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                check_rules(d, changed)


if __name__ == '__main__':
    unittest.main()
