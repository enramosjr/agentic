"""Pinned parent task admission contracts; synthetic execution is not qualification."""
import backend_test_support
import hashlib
import unittest

from test_authority_submission import SubmissionHost, fixture as submission_fixture
from test_authority_app_proofs import identities as purpose_identities
from test_authority_closed_artifacts import HistoricalAPI, locator
from trusted_ci_fixtures import snapshot
from trusted_ci_policy import Refusal, digest
import submission
import task_admission


def fixture():
    d, request, files = submission_fixture()
    d['policy']['merge_actors'] = [19]
    d['resources'].update(model_auth='chatgpt-plan', model_id='approved-fixture-model',
        codex_sha='c' * 64, codex_version='0.1.0', coding_image='coding@sha256:' + 'd' * 64)
    identities = purpose_identities(d)
    d['resources']['identity_digest'] = digest(identities)
    request['deployment_digest'] = digest(d)
    host = SubmissionHost()
    submitted = submission.submit(host, d, request, files, 1001)
    b = dict(deployment=d, configuration_revision='b' * 40, deployment_digest=digest(d))
    s = snapshot(d['policy'])
    s.update(pr=submitted['pr'], head=submitted['head'])
    value = dict(schema_version=2, kind='protected-task', task_id=request['task_id'],
        configuration_revision=b['configuration_revision'], deployment_digest=digest(d),
        source_base=request['base'], coding_installation_id=identities['apps']['coding']['installation_id'],
        submitted=submitted, execution=dict(run_id=99, attempt=1, job_id=77),
        harness=dict(image=d['resources']['coding_image'], sha256=d['resources']['codex_sha'],
                     version='0.1.0', auth_profile='chatgpt-plan'),
        protocol=dict(kind='codex-protocol-result', thread_id='thread-fixture', turn_id='turn-fixture',
                      model_id='approved-fixture-model', model_execution_qualified=False),
        isolation=dict(uid=65534, root_read_only=True, cap_eff='0' * 16, no_new_privs=1, seccomp=2,
            interfaces=['lo'], memory_max=512 * 1024 * 1024, pids_max=64, cpu_quota=100000, cpu_period=100000,
            work_filesystem='ext4', work_capacity=256 * 1024 * 1024,
            writable_mounts=['/work', '/tmp', '/home/agentic'], host_mounts=['/run/agentic-model'],
            credential_probes={k: 'unavailable' for k in task_admission.CREDENTIAL_PROBES}),
        relay=dict(requests=2, completed=2, response_digests=['e' * 64, 'f' * 64]),
        cleanup_complete=True, issued=970, completed=1002, expires=1500)
    api = HistoricalAPI('task', request['task_id'])
    api.document = value
    api.raw = api.archive('task.json')
    api.artifact['created_at'] = '1970-01-01T00:16:43Z'
    api.artifact['digest'] = 'sha256:' + hashlib.sha256(api.raw).hexdigest()
    return host, api, b, identities, s, value


class TaskAdmissionContracts(unittest.TestCase):
    def test_authenticated_parent_and_exact_submitted_head_are_admitted(self):
        source, api, b, identities, s, value = fixture()
        result = task_admission.read(source, api, b, identities, s, locator(), value['task_id'], 1100)
        self.assertEqual(result['document'], value)
        self.assertEqual(result['task_digest'], digest(value))
        self.assertEqual(result['head'], s['head'])
        self.assertTrue(result['admission_established'])
        self.assertFalse(value['submitted']['admission_established'])

    def test_submission_alone_cannot_establish_admission(self):
        source, api, b, identities, s, value = fixture()
        api.document = value['submitted']
        api.raw = api.archive('task.json')
        api.artifact['digest'] = 'sha256:' + hashlib.sha256(api.raw).hexdigest()
        with self.assertRaises(Refusal):
            task_admission.read(source, api, b, identities, s, locator(), value['task_id'], 1100)

    def test_isolation_cleanup_model_and_identity_failures_are_rejected(self):
        for group, key, bad in [('outer', 'configuration_revision', 'c' * 40), ('outer', 'cleanup_complete', False),
            ('outer', 'coding_installation_id', 999), ('outer', 'expires', 1099),
            ('isolation', 'uid', 0), ('isolation', 'root_read_only', False),
            ('isolation', 'interfaces', ['lo', 'eth0']), ('isolation', 'pids_max', 10000),
            ('isolation', 'host_mounts', ['/var/run/docker.sock']), ('isolation', 'cap_eff', '1' * 16),
            ('isolation', 'memory_max', 2**40), ('isolation', 'work_capacity', 2**40),
            ('relay', 'completed', 0), ('harness', 'auth_profile', 'api-key'),
            ('protocol', 'model_id', 'foreign-model'), ('protocol', 'model_execution_qualified', True)]:
            source, api, b, identities, s, value = fixture()
            (value if group == 'outer' else value[group])[key] = bad
            api.document = value
            api.raw = api.archive('task.json')
            api.artifact['digest'] = 'sha256:' + hashlib.sha256(api.raw).hexdigest()
            with self.subTest(group=group, key=key), self.assertRaises(Refusal):
                task_admission.read(source, api, b, identities, s, locator(), value['task_id'], 1100)

    def test_current_pr_branch_commit_and_bot_are_checked(self):
        for defect in ('head', 'tree', 'branch', 'author', 'parent', 'job'):
            source, api, b, identities, s, value = fixture()
            pr = source.prs[0]
            if defect == 'head':
                pr['head']['sha'] = '0' * 40
            elif defect == 'tree':
                source.commits[s['head']]['tree']['sha'] = '0' * 40
            elif defect == 'branch':
                source.refs[value['submitted']['branch']] = '0' * 40
            elif defect == 'author':
                pr['user']['id'] = 17
            elif defect == 'parent':
                source.commits[s['head']]['parents'] = [{'sha': '0' * 40}]
            else:
                api.job['conclusion'] = 'failure'
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                task_admission.read(source, api, b, identities, s, locator(), value['task_id'], 1100)

    def test_original_task_base_may_precede_current_verification_base(self):
        source, api, b, identities, s, value = fixture()
        self.assertNotEqual(s['base'], value['source_base'])
        self.assertEqual(task_admission.read(source, api, b, identities, s, locator(),
                                            value['task_id'], 1100)['head'], s['head'])


if __name__ == '__main__':
    unittest.main()
