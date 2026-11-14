"""R1: only strict, pinned, nonempty authority policy is executable."""
import copy
import unittest
from trusted_ci_fixtures import policy
import trusted_ci_policy as t


class PolicyTests(unittest.TestCase):
    def test_valid_and_canonical_digest(self):
        p = policy()
        t.validate_policy(p)
        self.assertEqual(t.digest(p), t.digest(dict(reversed(list(p.items())))))

    def test_substitutions_and_invalid_coverage(self):
        for key, value in [('checks', []), ('checks', ['X', 'X']), ('image', 'python:latest'),
                           ('verifier_sha', 'main'), ('repository_id', True),
                           ('reviewers', [18]), ('schema_version', 2),
                           ('unknown', 'command'), ('target', '../main'),
                           ('checks', ['not a check id'])]:
            p = copy.deepcopy(policy())
            p[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(t.Refusal):
                t.validate_policy(p)

    def test_duplicate_json_keys_are_not_silently_overridden(self):
        with self.assertRaises(t.Refusal):
            t.loads('{"epoch":"v1","epoch":"v2"}')
