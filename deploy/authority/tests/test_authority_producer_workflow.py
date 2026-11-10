"""Fixed graph contracts supplement executable local service composition."""
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]


class ProducerWorkflowContracts(unittest.TestCase):
    def setUp(self):
        self.workflow = (ROOT / '.ai/trusted-ci/authority-v2.yml').read_text()
        parts = re.split(r'^  ([a-z_]+):\n', self.workflow.split('\njobs:\n', 1)[1], flags=re.MULTILINE)
        self.jobs = dict(zip(parts[1::2], parts[2::2]))

    def test_preliminary_proofs_follow_verification_and_publication_has_own_admin_job(self):
        self.assertIn('options: [credentials, task, production, qualification, case]', self.workflow)
        self.assertIn("if: inputs.mode == 'production'", self.jobs['discover'])
        self.assertIn('needs: [discover, trial_case_ready]', self.jobs['prepare'])
        self.assertIn("inputs.mode == 'case' && 'case-prepare' || 'prepare'", self.jobs['prepare'])
        self.assertIn("inputs.mode == 'production' && needs.discover.result == 'success'",self.jobs['prepare'])
        self.assertIn('needs: [prepare, trial_case_handoff]', self.jobs['verify'])
        self.assertIn("inputs.mode == 'production' || (needs.trial_case_handoff.result == 'success' && needs.prepare.outputs.host_case != 'spoofed-source' && needs.prepare.outputs.host_case != 'new-head')",self.jobs['verify'])
        for purpose in ('admin','reader','issuer','coding','merge'):
            self.assertIn('needs: [prepare, verify]', self.jobs[purpose+'_proof'])
        publication = self.jobs['publication_controls']
        self.assertIn('needs: [prepare, verify]', publication)
        self.assertIn("inputs.mode == 'case' && 'case-publication-controls' || 'publication-controls'", publication)
        self.assertNotIn('broker', publication)
        self.assertIn('publication_controls', self.jobs['publish'].split('name:',1)[0])

    def test_trial_expiry_scheduling_preserves_production_timeout(self):
        for name in ('broker','controls',*[p+'_final_proof' for p in ('admin','reader','issuer','coding','merge')]):
            self.assertIn("timeout-minutes: ${{ inputs.mode == 'case' && 10 || 5 }}",self.jobs[name])

    def test_final_jobs_are_concurrent_with_broker_and_each_key_stays_scoped(self):
        expected = dict(discover={'READER'}, prepare={'ADMIN'}, verify={'READER'},
            publication_controls={'ADMIN'},publish={'ISSUER'},broker={'READER','MERGE'},controls={'ADMIN'})
        for purpose in ('admin','reader','issuer','coding','merge'):
            expected[purpose+'_proof'] = {purpose.upper()}
            expected[purpose+'_final_proof'] = {purpose.upper()}
        for name, keys in expected.items():
            block = self.jobs[name]
            self.assertEqual(set(re.findall(r'secrets.AGENTIC_([A-Z]+)_PRIVATE_KEY',block)),keys)
            self.assertNotIn('contents: write',block)
            self.assertIn('ref: ${{ github.sha }}',block)
            self.assertIn('npm ci --ignore-scripts --no-audit --no-fund',block)
        for name in ('broker','controls',*[p+'_final_proof' for p in ('admin','reader','issuer','coding','merge')]):
            self.assertIn('needs: [prepare, publish, trial_host_denial]' if name == 'broker' else 'needs: [prepare, publish]',self.jobs[name])
            self.assertNotIn('needs: [broker',self.jobs[name])

    def test_recovery_uses_independent_pin_and_does_not_retry_or_infer_failure(self):
        final = self.jobs['finalize']
        self.assertIn('if: always() && needs.prepare.result ==',final)
        self.assertIn('broker',final.split('name:',1)[0])
        self.assertIn('AGENTIC_RECOVERY_PIN: ${{ vars.AGENTIC_FINALIZE_PIN }}',final)
        self.assertIn("inputs.mode == 'case' && 'case-finalize' || 'finalize'",final)
        self.assertNotIn('contents: write',final)
        self.assertNotIn('AGENTIC_MERGE_PRIVATE_KEY',final)
        recovery = (ROOT / '.ai/trusted-ci/authority-v2-recovery.yml').read_text()
        self.assertIn('AGENTIC_RECOVERY_PIN: ${{ vars.AGENTIC_RECOVERY_PIN }}',recovery)
        self.assertIn('name: finalize',recovery)
        self.assertIn('role: finalize',recovery)
        self.assertNotIn('contents: write',recovery)
        self.assertNotIn('AGENTIC_MERGE_PRIVATE_KEY',recovery)

    def test_runtime_bundle_contains_the_separate_recovery_entrypoint(self):
        import backend_test_support
        import build_runtime
        import io
        import tarfile
        with tarfile.open(fileobj=io.BytesIO(build_runtime.archive(ROOT)),mode='r:gz') as archive:
            member = archive.extractfile('authority/.github/workflows/authority-v2-recovery.yml').read()
        self.assertEqual(member,(ROOT/'.ai/trusted-ci/authority-v2-recovery.yml').read_bytes())


if __name__ == '__main__': unittest.main()
