"""Cloud job fencing and storage scope; no hosted qualification claims."""
import copy
import unittest
from test_authority_protocol import deployment, execution
from trusted_ci_fixtures import snapshot
from trusted_ci_policy import Refusal
import authority_jobs as jobs

HOST = 'agentic-123456789012-test.s3.us-east-2.amazonaws.com'


def request():
    d = deployment()
    d.update(adapter='aws', account='123456789012')
    d['resources'].update(artifact_host=HOST, bucket='agentic-123456789012-test',
                          region='us-east-2', bundle_sha='b' * 64,
                          compute_scope='arn:aws:cloudformation:us-east-2:123456789012:stack/test/id')
    return jobs.new_lease(d, snapshot(), 100, 'a' * 32, 1000,
        {'bundle': {'url': 'https://' + HOST + '/jobs/' + 'a' * 32 + '/bundle.tgz', 'sha256': 'b' * 64},
         'candidate': {'url': 'https://' + HOST + '/jobs/' + 'a' * 32 + '/candidate.tgz', 'sha256': 'c' * 64},
         'report': {'url': 'https://' + HOST + '/jobs/' + 'a' * 32 + '/report.json'}})


class JobContracts(unittest.TestCase):
    def test_trusted_bundle_must_match_approved_deployment(self):
        lease = request()
        lease['objects']['bundle']['sha256'] = 'e' * 64
        with self.assertRaises(Refusal):
            jobs.validate_lease(lease, 1001)

    def test_compute_scope_cannot_substitute_another_account(self):
        lease = request()
        lease['deployment']['resources']['compute_scope'] = 'arn:aws:cloudformation:us-east-2:999999999999:stack/test/id'
        with self.assertRaises(Refusal):
            jobs.validate_lease(lease, 1001)

    def test_lease_round_trip_and_exact_report(self):
        lease = request()
        jobs.validate_lease(lease, 1001)
        result = jobs.result(lease, execution(lease['deployment'])['outcomes'])
        self.assertEqual(jobs.check_result(result, lease, 1001), result['report'])

    def test_signed_url_does_not_allow_namespace_or_host_substitution(self):
        for url in ('https://evil.invalid/jobs/' + 'a' * 32 + '/bundle.tgz',
                    'https://' + HOST + '/jobs/' + 'd' * 32 + '/bundle.tgz',
                    'https://user@' + HOST + '/jobs/' + 'a' * 32 + '/bundle.tgz',
                    'https://' + HOST + '/jobs/' + 'a' * 32 + '/../bundle.tgz'):
            lease = request()
            lease['objects']['bundle']['url'] = url
            with self.subTest(url=url), self.assertRaises(Refusal):
                jobs.validate_lease(lease, 1001)

    def test_stale_lease_and_failed_or_replayed_result_are_rejected(self):
        lease = request()
        with self.assertRaises(Refusal):
            jobs.validate_lease(lease, lease['expires'])
        bad = jobs.result(lease, [{'id': c, 'status': 'failure'} for c in lease['deployment']['policy']['checks']])
        with self.assertRaises(Refusal):
            jobs.check_result(bad, lease, 1001)
        good = jobs.result(lease, execution(lease['deployment'])['outcomes'])
        different = copy.deepcopy(lease)
        different['job_id'] += 1
        with self.assertRaises(Refusal):
            jobs.check_result(good, different, 1001)


if __name__ == '__main__':
    unittest.main()
