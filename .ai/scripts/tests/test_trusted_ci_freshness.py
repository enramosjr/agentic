"""R5: no reuse across candidate, target, policy, repository or execution."""
import unittest
from trusted_ci_fixtures import policy, report, snapshot
import trusted_ci_policy as t


class FreshnessTests(unittest.TestCase):
    def test_changed_current_binding_refuses_old_success(self):
        for key in ['head', 'base', 'merge', 'policy_digest', 'epoch', 'run_id',
                    'run_attempt', 'authority_repository_id', 'workflow_sha']:
            current = snapshot()
            current[key] = 100 if isinstance(current[key], int) else '7' * 40
            with self.subTest(key=key), self.assertRaises(t.Refusal):
                t.validate_report(report(), policy(), current)

    def test_head_only_or_ambiguous_merge_ref_is_refused(self):
        for merge in [None, '', '4' * 40, '5' * 40]:
            s = snapshot()
            s['merge'] = merge
            with self.assertRaises(t.Refusal):
                t.validate_snapshot(s, policy())
