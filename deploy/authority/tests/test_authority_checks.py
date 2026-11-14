"""Read-only exact check selection and issuer-body binding, not publication proof."""
import backend_test_support
import copy
from datetime import datetime, timezone
import unittest

from test_authority_protocol import deployment, execution
from test_authority_fence import pending
from trusted_ci_fixtures import snapshot
from trusted_ci_policy import Refusal, digest
import checks


def prepared():
    d = deployment()
    d['resources']['actions_resource'] = 'github-actions:owner/authority:' + d['policy']['workflow']
    s = snapshot(d['policy'])
    binding = {'deployment': d, 'configuration_revision': 'b' * 40}
    op = pending(binding)
    op.update(head=s['head'], merge=s['merge'], workflow_sha=s['workflow_sha'])
    coordinates = dict(configuration_revision='b' * 40, operation=op, sequence=1,
        issuer_installation_id=142, evidence_job_id=100, evidence_digest='a' * 64, task_digest='b' * 64)
    document = evidence(d)
    coordinates['evidence_digest'] = digest(document)
    body = checks.publication_body(d, s, document, coordinates, 1001)
    run = dict(body, id=321, app={'id': d['apps']['issuer']})
    return d, s, coordinates, body, run


def evidence(d):
    report = execution(d)
    report['execution']['resource'] = d['resources']['actions_resource']
    return dict(schema_version=2, kind='actions', registry_revision='b' * 40,
        result=dict(schema_version=2, report=report, cleanup_complete=True, enforcement_active=False))


class Reader:
    def __init__(self, entries):
        self.entries, self.calls = entries, []
    def pages(self, path, collection):
        self.calls.append((path, collection))
        return copy.deepcopy(self.entries)


class CheckBindingContracts(unittest.TestCase):
    def test_bare_report_cannot_omit_parent_cleanup_evidence(self):
        d, s, c, body, own = prepared()
        with self.assertRaises(Refusal):
            checks.publication_body(d, s, execution(d), c, 1001)

    def test_body_and_readback_bind_all_exact_candidate_and_operation_coordinates(self):
        d, s, c, body, own = prepared()
        self.assertEqual(body['head_sha'], s['merge'])
        self.assertEqual(body['status'], 'completed')
        self.assertEqual(body['conclusion'], 'success')
        self.assertTrue(body['external_id'].startswith('agentic-v2:'))
        foreign = copy.deepcopy(own)
        foreign['app']['id'] = d['apps']['coding']
        api = Reader([foreign, own])
        observed = checks.current(api, d, s, c, 1002)
        self.assertEqual(observed['check_id'], 321)
        self.assertEqual(api.calls, [('/repos/owner/project/commits/' + s['merge'] + '/check-runs?filter=all', 'check_runs')])

    def test_stale_foreign_incomplete_duplicate_and_future_checks_are_refused(self):
        for key, value in [('external_id', 'agentic-v2:' + 'c' * 64), ('head_sha', 'c' * 40),
            ('status', 'in_progress'), ('conclusion', 'failure'), ('app', {'id': 43}),
            ('completed_at', '2099-01-01T00:00:00Z')]:
            d, s, c, body, own = prepared()
            own[key] = value
            with self.subTest(key=key), self.assertRaises(Refusal):
                checks.current(Reader([own]), d, s, c, 1002)
        d, s, c, body, own = prepared()
        with self.assertRaises(Refusal):
            checks.current(Reader([own, dict(own, id=322)]), d, s, c, 1002)

    def test_replayed_installation_generation_attempt_or_configuration_is_not_current(self):
        for key, value in [('configuration_revision', 'c' * 40), ('sequence', 2), ('issuer_installation_id', 143),
                           ('evidence_digest', 'c' * 64), ('task_digest', 'c' * 64)]:
            d, s, c, body, own = prepared()
            changed = copy.deepcopy(c)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(Refusal):
                checks.current(Reader([own]), d, s, changed, 1002)
        d, s, c, body, own = prepared()
        c['operation']['attempt'] = 2
        with self.assertRaises(Refusal):
            checks.current(Reader([own]), d, s, c, 1002)
        d, s, c, body, own = prepared()
        d['generation'] += 1
        with self.assertRaises(Refusal):
            checks.current(Reader([own]), d, s, c, 1002)

    def test_body_never_accepts_failed_or_incomplete_execution(self):
        d, s, c, body, own = prepared()
        for outcomes in ([], [{'id': item['id'], 'status': 'failure'} for item in execution(d)['outcomes']]):
            report = evidence(d)
            report['result']['report']['outcomes'] = outcomes
            c['evidence_digest'] = digest(report)
            with self.assertRaises(Refusal):
                checks.publication_body(d, s, report, c, 1001)

    def test_failed_cleanup_tampering_and_wrong_parent_job_cannot_create_success_body(self):
        for defect in ('cleanup', 'digest', 'job'):
            d, s, c, body, own = prepared()
            document = evidence(d)
            if defect == 'cleanup':
                document['result']['cleanup_complete'] = False
                c['evidence_digest'] = digest(document)
            elif defect == 'digest':
                document['result']['report']['execution']['job_id'] = 101
            else:
                c['evidence_job_id'] = 101
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                checks.publication_body(d, s, document, c, 1001)


if __name__ == '__main__':
    unittest.main()
