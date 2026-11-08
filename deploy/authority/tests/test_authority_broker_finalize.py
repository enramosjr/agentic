"""Authenticated historical recovery over API/Git fixtures, never live merges."""
import backend_test_support
import copy
import unittest

from test_authority_registry import RegistryHost, coordinates, intent
from test_authority_merge_window import gate
from test_authority_merge_receipts import ReceiptAPI
from trusted_ci_policy import Refusal, digest
import authority_release
import broker_finalize
import merge_receipts
import registry


class RecoveryAPI(ReceiptAPI):
    def __init__(self):
        super().__init__()
        self.calls = 0
        self.recovery_job = dict(id=88, run_id=100, head_sha='c' * 40, name='finalize', status='in_progress', conclusion=None)
    def get(self, path):
        self.calls += 1
        if path.endswith('/actions/runs/100'):
            return dict(self.run, id=100, head_sha='c' * 40, event='workflow_dispatch')
        return super().get(path)
    def pages(self, path, collection):
        self.calls += 1
        if path.endswith('/runs/100/attempts/1/jobs'): return [self.recovery_job]
        return super().pages(path, collection)


def fixture(kind='not-submitted'):
    host, api = RegistryHost(), RecoveryAPI()
    store = registry.Registry(host, coordinates())
    d = intent()
    d.update(state='active', qualification='f' * 64)
    store.write(None, d)
    before = store.binding()
    g = gate()
    g.update(configuration_revision=before['configuration_revision'], deployment_digest=before['deployment_digest'])
    op = {k: g[k] for k in ('operation_id', 'repository_id', 'target', 'configuration_revision', 'deployment_digest',
                           'workflow_sha', 'run_id', 'attempt', 'pr', 'head', 'base', 'merge')}
    op.update(kind='merge', scope_digest=None, created=1000, execution_deadline=1300)
    store.acquire_operation(before['branch_head'], before['configuration_revision'], op)
    receipts = merge_receipts.ActionsReceipts(api, store.binding, 77, lambda: 1002, uploader=api.upload)
    if kind == 'not-submitted': receipts.append(kind, merge_receipts.not_submitted(store.binding(), 77, 1002))
    elif kind == 'dispatch':
        receipts.append(kind, dict(schema_version=2, kind=kind, gate_digest=digest(g), operation_id=op['operation_id'], sequence=1, gate=g))
    api.job.update(status='completed', conclusion='cancelled', completed_at='1970-01-01T00:16:43Z')
    class Source:
        def __init__(self):
            self.calls = []
            self.pr = dict(number=7, state='closed', merged=True, merge_commit_sha='8' * 40,
                head={'sha': g['head']}, base={'ref': g['target'], 'repo': {'id': g['repository_id']}})
            self.commit = dict(sha='8' * 40, parents=[{'sha': g['base']}, {'sha': g['head']}], tree={'sha': g['tree']})
        def get(self, path):
            self.calls.append(path)
            if '/pulls/' in path: return copy.deepcopy(self.pr)
            if '/git/commits/' in path: return copy.deepcopy(self.commit)
            raise AssertionError(path)
    source = Source()
    trust = dict(authority_repository='owner/authority', authority_repository_id=456,
                 workflow='.github/workflows/authority.yml', workflow_sha='c' * 40)
    env = dict(GITHUB_REPOSITORY_ID='456', GITHUB_SHA='c' * 40, GITHUB_JOB='finalize', GITHUB_RUN_ID='100', GITHUB_RUN_ATTEMPT='1')
    controller = broker_finalize.Finalizer(store, api, source, trust, env, clock=lambda: 3000)
    host.writes.clear()
    return controller, host, api, source, store


class BrokerFinalizeContracts(unittest.TestCase):
    def test_public_hold_precedes_all_reads_and_mutations(self):
        controller, host, api, source, store = fixture()
        before = api.calls
        with self.assertRaises(authority_release.Held): controller.finalize('1' * 32, 1, 77)
        self.assertEqual(api.calls, before)
        self.assertEqual(host.writes, [])
        self.assertEqual(source.calls, [])

    def test_positive_no_dispatch_from_terminal_cancelled_or_failed_job_releases_exact_fence(self):
        for conclusion in ('cancelled', 'failure', 'timed_out', 'success'):
            controller, host, api, source, store = fixture()
            api.job['conclusion'] = conclusion
            after = controller._finalize('1' * 32, 1, 77)
            self.assertIsNone(after['fence']['pending'])
            self.assertEqual(after['fence']['completed'][0]['kind'], 'not-submitted')
            self.assertEqual(source.calls, [])

    def test_exact_actual_merge_after_authorization_expiry_recovers_without_outcome(self):
        controller, host, api, source, store = fixture('dispatch')
        host.refs['main'] = 'e' * 40
        host.commits['e' * 40] = copy.deepcopy(host.commits['a' * 40])
        after = controller._finalize('1' * 32, 1, 77)
        self.assertEqual(after['fence']['completed'][0]['kind'], 'merged')
        self.assertEqual(len(source.calls), 2)
        self.assertEqual(after['deployment']['policy']['workflow_sha'], 'a' * 40)

    def test_live_producer_missing_expired_or_rerun_artifacts_never_unlock(self):
        for defect in ('live', 'missing', 'expired', 'rerun', 'other-operation', 'other-job'):
            controller, host, api, source, store = fixture()
            operation, job = '1' * 32, 77
            if defect == 'live': api.job.update(status='in_progress', conclusion=None)
            elif defect == 'missing': api.artifacts.clear()
            elif defect == 'expired': api.artifacts[0]['expired'] = True
            elif defect == 'rerun': api.run['run_attempt'] = 2
            elif defect == 'other-operation': operation = '2' * 32
            else: job = 78
            with self.subTest(defect=defect), self.assertRaises(Refusal): controller._finalize(operation, 1, job)
            self.assertIsNotNone(store.binding()['fence']['pending'])
            self.assertEqual(host.writes, [])

    def test_open_or_unmerged_pr_and_wrong_actual_parents_or_tree_stay_pending(self):
        for defect in ('open', 'unmerged', 'parents', 'tree'):
            controller, host, api, source, store = fixture('dispatch')
            if defect == 'open': source.pr['state'] = 'open'
            elif defect == 'unmerged': source.pr['merged'] = False
            elif defect == 'parents': source.commit['parents'].reverse()
            else: source.commit['tree']['sha'] = '9' * 40
            with self.subTest(defect=defect), self.assertRaises(Refusal): controller._finalize('1' * 32, 1, 77)
            self.assertEqual(host.writes, [])
            self.assertIsNotNone(store.binding()['fence']['pending'])

    def test_untrusted_recovery_job_or_environment_refuses_before_admin_write(self):
        for defect in ('sha', 'job', 'run', 'environment'):
            controller, host, api, source, store = fixture()
            if defect == 'sha': api.recovery_job['head_sha'] = 'd' * 40
            elif defect == 'job': api.recovery_job['name'] = 'broker (7)'
            elif defect == 'run': api.recovery_job['run_id'] = 101
            else: controller.environment['GITHUB_SHA'] = 'd' * 40
            with self.subTest(defect=defect), self.assertRaises(Refusal): controller._finalize('1' * 32, 1, 77)
            self.assertEqual(host.writes, [])
            self.assertEqual(source.calls, [])

    def test_contradictory_positive_no_dispatch_and_dispatch_never_unlock(self):
        controller, host, api, source, store = fixture('dispatch')
        document = merge_receipts.not_submitted(store.binding(), 77, 1002)
        # Deliberately bypass creation guards to model a contradictory host inventory.
        api.upload('agentic-merge-' + '1' * 32 + '-s1-a1-not-submitted', __import__('json').dumps(document).encode())
        with self.assertRaises(Refusal): controller._finalize('1' * 32, 1, 77)
        self.assertEqual(host.writes, [])

    def test_outcome_for_another_gate_cannot_release_even_an_exact_merged_pr(self):
        controller, host, api, source, store = fixture('dispatch')
        outcome = dict(schema_version=2, kind='outcome', operation_id='1' * 32, sequence=1,
                       gate_digest='0' * 64, state='submitted', response_digest='e' * 64)
        api.upload('agentic-merge-' + '1' * 32 + '-s1-a1-outcome', __import__('json').dumps(outcome).encode())
        with self.assertRaises(Refusal): controller._finalize('1' * 32, 1, 77)
        self.assertEqual(host.writes, [])
        self.assertIsNotNone(store.binding()['fence']['pending'])


if __name__ == '__main__': unittest.main()
