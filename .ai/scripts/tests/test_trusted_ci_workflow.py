"""R4 R6: authority matrix publication remains per-PR and separately privileged."""
from pathlib import Path
import unittest
from trusted_ci_fixtures import policy
import trusted_ci_github as g
from trusted_ci_policy import Refusal


class WorkflowTests(unittest.TestCase):
    def test_one_failed_pr_does_not_skip_all_publishers(self):
        path = Path(__file__).resolve().parents[2] / 'trusted-ci/authority.yml'
        publisher = path.read_text().split('\n  publish:\n', 1)[1].split('\n  qualification:', 1)[0]
        self.assertIn("if: always() && needs.discover.result == 'success' && needs.discover.outputs.prs != '[]'", publisher)
        self.assertIn('AGENTIC_ISSUER_PRIVATE_KEY', publisher)
        verifier = path.read_text().split('\n  verify:\n', 1)[1].split('\n  publish:', 1)[0]
        self.assertNotIn('AGENTIC_ISSUER_PRIVATE_KEY', verifier)

    def test_failed_individual_job_cannot_supply_publisher_artifact(self):
        class Host:
            def get(self, path):
                if '/actions/workflows/' in path:
                    return dict(id=22, path=policy()['workflow'])
                return dict(repository={'id': 456}, head_sha='1' * 40,
                            path=policy()['workflow'], workflow_id=22, run_attempt=1, event='schedule')
            def pages(self, path, collection):
                return [dict(name='verify (7)', conclusion='failure')]
        with self.assertRaises(Refusal):
            g.artifact_report(Host(), policy(), 99, 1, 7)
