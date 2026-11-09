"""Held task producer graph contracts; not hosted execution qualification."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[3]


class TaskWorkflowContracts(unittest.TestCase):
    def setUp(self):
        self.workflow = (ROOT / '.ai/trusted-ci/authority-v2.yml').read_text()
        parts = re.split(r'^  ([a-z_]+):\n', self.workflow.split('\njobs:\n', 1)[1], flags=re.MULTILINE)
        self.jobs = dict(zip(parts[1::2], parts[2::2]))

    def test_modes_preserve_existing_credential_dispatch_and_separate_task_secrets(self):
        self.assertIn('default: credentials', self.workflow)
        self.assertIn('options: [credentials, task, production]', self.workflow)
        for purpose in ('admin', 'reader', 'issuer', 'coding', 'merge', 'model_vault', 'model_delivery'):
            block = self.jobs[purpose + '_credential_proof']
            self.assertIn("if: inputs.mode == 'credentials'", block)
            self.assertIn('role: credential', block)
            self.assertIn('fromJSON(inputs.challenges).' + purpose, block)

    def test_preparation_output_is_the_only_request_for_downstream_producers(self):
        prepare = self.jobs['prepare_task']
        self.assertIn("if: inputs.mode == 'task'", prepare)
        self.assertIn('request: ${{ steps.prepare.outputs.request }}', prepare)
        self.assertIn('id: prepare', prepare)
        self.assertIn('role: prepare-task', prepare)
        self.assertIn('prompt: ${{ inputs.prompt }}', prepare)
        for name in ('model_auth', 'task', 'task_controls'):
            self.assertIn('task: ${{ needs.prepare_task.outputs.request }}', self.jobs[name])
            self.assertNotIn('inputs.prompt', self.jobs[name])
            self.assertNotIn('inputs.challenges', self.jobs[name])

    def test_task_and_admin_rendezvous_run_concurrently_after_closed_model_producer(self):
        self.assertIn('needs: [prepare_task]', self.jobs['model_auth'])
        self.assertIn('name: model authorization', self.jobs['model_auth'])
        self.assertIn('role: model-authorization', self.jobs['model_auth'])
        for name, prefix, role in (('task', 'task', 'task'), ('task_controls', 'task controls', 'task-controls')):
            block = self.jobs[name]
            self.assertIn('needs: [prepare_task, model_auth]', block)
            self.assertIn('name: ' + prefix + ' (${{ fromJSON(needs.prepare_task.outputs.request).task.task_id }})', block)
            self.assertIn('role: ' + role, block)
            self.assertIn('timeout-minutes: 20', block)
            self.assertNotIn('always()', block)
            self.assertNotIn('continue-on-error', block)
        self.assertIn('name: prepare task', self.jobs['prepare_task'])

    def test_each_job_uses_only_pinned_authority_code_and_its_own_credentials(self):
        expected = dict(prepare_task={'AGENTIC_READER_PRIVATE_KEY'},
            model_auth={'AGENTIC_MODEL_VAULT_KEY', 'AGENTIC_MODEL_DELIVERY_KEY'},
            task={'AGENTIC_CODING_PRIVATE_KEY', 'AGENTIC_MODEL_DELIVERY_KEY'},
            task_controls={'AGENTIC_ADMIN_PRIVATE_KEY'})
        for name, names in expected.items():
            block = self.jobs[name]
            self.assertEqual(set(re.findall(r'secrets\.(AGENTIC_[A-Z_]+)', block)), names)
            self.assertIn('ref: ${{ github.sha }}', block)
            self.assertIn('persist-credentials: false', block)
            self.assertIn('runs-on: ubuntu-latest', block)
            self.assertIn('GITHUB_TOKEN: ${{ github.token }}', block)
            self.assertIn('npm ci --ignore-scripts --no-audit --no-fund', block)
            self.assertNotIn('pull_request', block)
            for action in re.findall(r'uses: ([^\s]+)', block):
                self.assertTrue(action == './deploy/authority/artifact_upload' or re.fullmatch(r'[^@]+@[0-9a-f]{40}', action))
        permissions = self.workflow.split('\npermissions:\n', 1)[1].split('\nconcurrency:', 1)[0]
        self.assertEqual(permissions, '  contents: read\n  actions: read')

    def test_only_model_authorization_can_persist_its_auth_state(self):
        self.assertIn('    permissions:\n      contents: write\n      actions: read', self.jobs['model_auth'])
        for name, block in self.jobs.items():
            if name != 'model_auth':
                self.assertNotIn('contents: write', block)


if __name__ == '__main__':
    unittest.main()
