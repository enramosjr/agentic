"""Native trial producers share pins but keep job credential purposes separate."""
import re
import unittest
import test_authority_task_workflow as tasks


class TrialActions(unittest.TestCase):
    setUp = tasks.TaskWorkflowContracts.setUp

    def test_spoof_observation_skips_only_its_acceptance_job_and_requires_other_closed_jobs(self):
        self.assertIn("needs.prepare.outputs.host_case != 'spoofed-source' && needs.prepare.outputs.host_case != 'new-head'",self.jobs['verify'])
        publish=self.jobs['publish']
        self.assertIn("needs.verify.result == 'success' || (inputs.mode == 'case' && (needs.prepare.outputs.host_case == 'spoofed-source' || needs.prepare.outputs.host_case == 'new-head') && needs.verify.result == 'skipped')",publish)
        for job in ('prepare','publication_controls','admin_proof','reader_proof','issuer_proof','coding_proof','merge_proof'):
            self.assertIn("needs."+job+".result == 'success'",publish)
        for job in ('publication_controls','admin_proof','reader_proof','issuer_proof','coding_proof','merge_proof'):
            self.assertIn("if: always() && needs.prepare.result == 'success' && (needs.verify.result == 'success' || (inputs.mode == 'case' && (needs.prepare.outputs.host_case == 'spoofed-source' || needs.prepare.outputs.host_case == 'new-head') && needs.verify.result == 'skipped'))",self.jobs[job])

    def test_direct_host_case_is_closed_before_broker_and_skips_warm_merge_producers(self):
        block=self.jobs['trial_host_denial']
        self.assertIn('needs: [prepare, publish]',block)
        self.assertIn("contains(fromJSON('[\"direct-push\",\"coding-update\",\"missing-approval\",\"bad-acceptance\",\"replaced-checks\",\"forged-records\",\"spoofed-source\",\"new-head\"]'), needs.prepare.outputs.host_case)",block)
        self.assertIn('role: case-host-denial',block)
        self.assertEqual(set(re.findall(r'secrets\.(AGENTIC_[A-Z_]+)',block)),
                         {'AGENTIC_CODING_PRIVATE_KEY','AGENTIC_MERGE_PRIVATE_KEY','AGENTIC_TRIAL_CASE_ORIGIN_TOKEN'})
        self.assertIn("contains(fromJSON('[\"direct-push\",\"coding-update\"]'), needs.prepare.outputs.host_case) && secrets.AGENTIC_CODING_PRIVATE_KEY || ''",block)
        self.assertIn("contains(fromJSON('[\"missing-approval\",\"bad-acceptance\",\"replaced-checks\",\"forged-records\",\"spoofed-source\",\"new-head\"]'), needs.prepare.outputs.host_case) && secrets.AGENTIC_MERGE_PRIVATE_KEY || ''",block)
        self.assertRegex(block,r'(?m)^ {10}AGENTIC_MERGE_PRIVATE_KEY:')
        self.assertIn('needs: [prepare, publish, trial_host_denial]',self.jobs['broker'])
        for name in ('controls','admin_final_proof','reader_final_proof','issuer_final_proof','coding_final_proof','merge_final_proof'):
            self.assertIn("needs.prepare.outputs.host_case == 'none'",self.jobs[name])

    def test_trial_mode_has_handshake_then_native_binding_before_producers(self):
        self.assertIn('options: [credentials, task, production, qualification, case]', self.workflow)
        self.assertIn("if: inputs.mode == 'qualification'", self.jobs['trial_handoff'])
        self.assertIn('needs: [trial_handoff]', self.jobs['trial_prepare'])
        self.assertIn('name: trial preparation', self.jobs['trial_prepare'])
        for role in ('model_auth', 'admin_proof', 'reader_proof', 'issuer_proof', 'coding_proof', 'merge_proof'):
            self.assertIn('needs: [trial_prepare]', self.jobs['trial_' + role])

    def test_worker_and_controls_follow_all_closed_producers_and_run_in_parallel(self):
        expected = '[trial_prepare, trial_model_auth, trial_admin_proof, trial_reader_proof, trial_issuer_proof, trial_coding_proof, trial_merge_proof]'
        for job in ('qualification', 'trial_task_controls'):
            self.assertIn('needs: ' + expected, self.jobs[job])
            self.assertIn('task: ${{ needs.trial_prepare.outputs.request }}', self.jobs[job])
        self.assertIn('name: hosted qualification', self.jobs['qualification'])
        self.assertIn('name: trial task controls (${{ fromJSON(needs.trial_prepare.outputs.request).task.task_id }})',
                      self.jobs['trial_task_controls'])

    def test_each_trial_job_receives_only_its_purpose_and_scoped_origin_read(self):
        expected = dict(trial_handoff=set(), trial_prepare=set(), trial_model_auth={'AGENTIC_MODEL_VAULT_KEY','AGENTIC_MODEL_DELIVERY_KEY'},
            qualification={'AGENTIC_CODING_PRIVATE_KEY','AGENTIC_MODEL_DELIVERY_KEY'}, trial_task_controls={'AGENTIC_ADMIN_PRIVATE_KEY'},
            **{'trial_' + p + '_proof':{'AGENTIC_' + p.upper() + '_PRIVATE_KEY'} for p in ('admin','reader','issuer','coding','merge')})
        for name, keys in expected.items():
            block = self.jobs[name]
            self.assertEqual(set(re.findall(r'secrets\.(AGENTIC_[A-Z_]+)', block)), keys | {'AGENTIC_TRIAL_ORIGIN_TOKEN'})
            self.assertIn('ref: ${{ github.sha }}', block)
            self.assertIn('persist-credentials: false', block)
            self.assertNotIn('continue-on-error', block)
