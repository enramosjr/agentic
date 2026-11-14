"""Version-2 contracts; these tests do not claim hosted qualification."""
import copy
import tempfile
import unittest
from pathlib import Path

from trusted_ci_fixtures import policy, snapshot
import authority_protocol as a
from trusted_ci_policy import Refusal, digest


def deployment(adapter='github-actions'):
    p = policy()
    return dict(schema_version=2, policy=p, adapter=adapter, account='owner',
                resources={'authority': 'owner/authority', 'operation_id': 'a' * 32}, generation=1,
                apps={'admin': 41, 'issuer': 42, 'coding': 43, 'reader': 44, 'merge': 45},
                state='qualification', expires=2000, qualification=None)


def execution(d=None):
    d = d or deployment()
    return dict(schema_version=2, deployment_digest=digest(d), generation=1,
                snapshot=snapshot(d['policy']), adapter=d['adapter'],
                execution={'run_id': 99, 'attempt': 1, 'job_id': 100,
                           'account': 'owner', 'resource': 'owner/authority'},
                outcomes=[{'id': c, 'status': 'success'} for c in d['policy']['checks']])


class Protocol(unittest.TestCase):
    def test_merge_app_cannot_be_missing_or_share_another_domain(self):
        for value in (None, 41, 42, 43, 44):
            d = deployment()
            if value is None:
                d['apps'].pop('merge')
            else:
                d['apps']['merge'] = value
            with self.subTest(value=value), self.assertRaises(Refusal):
                a.validate_deployment(d)

    def test_repository_path_segments_cannot_escape_scope(self):
        d = deployment()
        d['policy']['repository'] = '../project'
        with self.assertRaises(Refusal):
            a.validate_deployment(d)

    def test_verification_requires_distinct_read_only_domain(self):
        d = deployment()
        d['apps'].pop('reader')
        with self.assertRaises(Refusal):
            a.validate_deployment(d)

    def test_valid_contract(self):
        d = deployment()
        self.assertEqual(a.validate_deployment(d), d)
        self.assertEqual(a.validate_execution(execution(d), d, snapshot(), 1000), execution(d))

    def test_substituted_and_legacy_reports(self):
        d = deployment()
        for key, value in [('schema_version', 1), ('generation', 2),
                           ('deployment_digest', '0' * 64), ('adapter', 'aws'),
                           ('outcomes', []), ('extra', 'command')]:
            r = execution(d)
            r[key] = value
            with self.subTest(key=key), self.assertRaises(Refusal):
                a.validate_execution(r, d, snapshot(), 1000)

    def test_no_empty_policy_or_shared_app_identity(self):
        for change in ('checks', 'apps', 'unknown'):
            d = deployment()
            if change == 'checks':
                d['policy']['checks'] = []
            elif change == 'apps':
                d['apps']['coding'] = 42
            else:
                d['extra'] = True
            with self.subTest(change=change), self.assertRaises(Refusal):
                a.validate_deployment(d)

    def test_deadline_and_bindings_fail_closed(self):
        d = deployment()
        for now, current in [(2000, snapshot()), (1000, dict(snapshot(), head='a' * 40))]:
            with self.assertRaises(Refusal):
                a.validate_execution(execution(d), d, current, now)

    def test_failed_or_duplicate_outcomes(self):
        d = deployment()
        for outcomes in [[{'id': c, 'status': 'failure'} for c in d['policy']['checks']],
                         [execution(d)['outcomes'][0]] * 4]:
            with self.assertRaises(Refusal):
                a.validate_execution(dict(execution(d), outcomes=outcomes), d, snapshot(), 1000)

    def test_journal_compare_and_swap_and_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'operation.json'
            first = a.Journal(path)
            self.assertIsNone(first.read())
            first.write(None, deployment())
            second = a.Journal(path)
            previous = second.read()
            changed = copy.deepcopy(previous)
            changed['generation'] = 2
            changed['state'] = 'blocked'
            second.write(digest(previous), changed)
            with self.assertRaises(Refusal):
                first.write(digest(previous), deployment())
            self.assertEqual(a.Journal(path).read(), changed)
            self.assertFalse(path.with_suffix('.json.lock').exists())

    def test_journal_excludes_concurrent_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'operation.json'
            path.with_suffix('.json.lock').write_text('another live operation')
            with self.assertRaises(Refusal):
                a.Journal(path).write(None, deployment())
            self.assertFalse(path.exists())

    def test_active_requires_remote_qualification(self):
        d = deployment()
        d['state'] = 'active'
        with self.assertRaises(Refusal):
            a.validate_deployment(d)


if __name__ == '__main__':
    unittest.main()
