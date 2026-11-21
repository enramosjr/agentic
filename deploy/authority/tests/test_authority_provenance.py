"""Authenticated parent-job artifacts, not candidate JSON or hosted qualification."""
import backend_test_support
import copy
import hashlib
import io
import json
import unittest
import zipfile
from unittest.mock import patch

from test_authority_protocol import deployment, execution
from trusted_ci_fixtures import snapshot
from trusted_ci_policy import Refusal
from trusted_ci_policy import digest
from test_authority_jobs import request
import authority_jobs
import provenance


class ActionsAPI:
    def __init__(self, document):
        self.run = {'path': '.github/workflows/authority.yml', 'workflow_id': 33,
            'repository': {'id': 456}, 'head_sha': '1' * 40, 'run_attempt': 1,
            'event': 'schedule', 'head_branch': 'main'}
        self.job = {'id': 100, 'run_id': 99, 'head_sha': '1' * 40, 'name': 'verify (7)',
            'status': 'completed', 'conclusion': 'success', 'started_at': '1970-01-01T00:16:00Z',
            'completed_at': '1970-01-01T00:17:00Z'}
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('evidence.json', json.dumps(document))
        self.raw = stream.getvalue()
        self.artifact = {'id': 555, 'name': 'evidence-7-1', 'expired': False,
            'created_at': '1970-01-01T00:16:30Z', 'workflow_run': {'id': 99,
                'repository_id': 456, 'head_repository_id': 456, 'head_sha': '1' * 40},
            'digest': 'sha256:' + hashlib.sha256(self.raw).hexdigest()}
    def get(self, path):
        if path.endswith('/actions/runs/99'):
            return self.run
        if path.endswith('/actions/workflows/33'):
            return {'id': 33, 'path': '.github/workflows/authority.yml'}
        raise AssertionError(path)
    def pages(self, path, collection):
        if path.endswith('/runs/99/attempts/1/jobs'):
            return [self.job]
        if path.endswith('/runs/99/artifacts'):
            return [self.artifact]
        raise AssertionError(path)
    def fetch(self, path, **kwargs):
        if path.endswith('/artifacts/555/zip'):
            return self.raw
        raise AssertionError(path)


def evidence():
    d = deployment()
    resource = 'github-actions:' + d['policy']['authority_repository'] + ':' + d['policy']['workflow']
    d['resources']['actions_resource'] = resource
    report = execution(d)
    report['execution']['resource'] = resource
    return d, {'schema_version': 2, 'kind': 'actions', 'registry_revision': 'b' * 40,
               'result': {'schema_version': 2, 'report': report, 'cleanup_complete': True, 'enforcement_active': False}}


class ProvenanceContracts(unittest.TestCase):
    def test_live_task_admission_is_exact_and_production_only(self):
        d = deployment()
        d.update(state='active', qualification='f' * 64)
        env = dict(GITHUB_REPOSITORY_ID='456', GITHUB_SHA='1' * 40, GITHUB_JOB='task',
                   GITHUB_RUN_ID='99', GITHUB_RUN_ATTEMPT='1')
        api = ActionsAPI({})
        api.job.update(name='task (' + 'a' * 32 + ')', status='in_progress', conclusion=None)
        self.assertEqual(provenance.admit_job(api, d, env, api.job['name'], 1100)['id'], 100)
        for key, value in [('GITHUB_JOB', 'verify'), ('GITHUB_SHA', '2' * 40), ('GITHUB_RUN_ATTEMPT', '2')]:
            with self.subTest(key=key), self.assertRaises(Refusal):
                provenance.admit_job(api, d, dict(env, **{key:value}), api.job['name'], 1100)
        d['state'] = 'qualification'
        with self.assertRaises(Refusal): provenance.admit_job(api, d, env, api.job['name'], 1100)

    def test_cloud_parent_requires_exact_clean_result_and_authenticated_job(self):
        lease = request()
        d = lease['deployment']
        report = authority_jobs.result(lease, execution(d)['outcomes'])['report']
        value = {'schema_version': 2, 'kind': 'cloud-parent', 'registry_revision': 'b' * 40,
                 'result': {'schema_version': 2, 'lease_digest': digest(lease), 'report': report,
                            'cleanup_complete': True, 'enforcement_active': False}}
        api = ActionsAPI(value)
        proof = provenance.artifact_document(api, d, 99, 1, 7, 'evidence')
        self.assertEqual(provenance.validate_evidence(proof['document'], d, lease['snapshot'],
                         'b' * 40, proof['job_id'], 1100), report)
        api.job['conclusion'] = 'failure'
        with self.assertRaises(Refusal):
            provenance.artifact_document(api, d, 99, 1, 7, 'evidence')
        value['result']['lease_digest'] = 'not-a-digest'
        with self.assertRaises(Refusal):
            provenance.validate_evidence(value, d, lease['snapshot'], 'b' * 40, 100, 1100)

    def test_artifact_timestamp_must_fall_inside_completed_job(self):
        d, value = evidence()
        for created in ('1970-01-01T00:15:59Z', '1970-01-01T00:17:01Z'):
            api = ActionsAPI(value)
            api.artifact['created_at'] = created
            with self.subTest(created=created), self.assertRaises(Refusal):
                provenance.artifact_document(api, d, 99, 1, 7, 'evidence')

    def test_unsafe_zip_member_and_extra_member_are_rejected(self):
        d, value = evidence()
        for variant in ('path', 'symlink', 'extra', 'corrupt'):
            api = ActionsAPI(value)
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as archive:
                info = zipfile.ZipInfo('../evidence.json' if variant == 'path' else 'evidence.json')
                if variant == 'symlink':
                    info.create_system, info.external_attr = 3, 0o120777 << 16
                archive.writestr(info, json.dumps(value))
                if variant == 'extra':
                    archive.writestr('extra.json', '{}')
            api.raw = b'not-a-zip' if variant == 'corrupt' else stream.getvalue()
            api.artifact['digest'] = 'sha256:' + hashlib.sha256(api.raw).hexdigest()
            with self.subTest(variant=variant), self.assertRaises(Refusal):
                provenance.artifact_document(api, d, 99, 1, 7, 'evidence')

    def test_timestamp_negative_control_detects_bypassed_verification(self):
        suite = unittest.TestSuite([ProvenanceContracts('test_artifact_timestamp_must_fall_inside_completed_job')])
        with patch.object(provenance, 'artifact_document', return_value={}):
            result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        self.assertGreater(len(result.failures), 0)
        self.assertEqual(len(result.errors), 0)

    def test_exact_artifact_and_execution_envelope(self):
        d, value = evidence()
        proof = provenance.artifact_document(ActionsAPI(value), d, 99, 1, 7, 'evidence')
        self.assertEqual(proof['job_id'], 100)
        self.assertEqual(provenance.validate_evidence(proof['document'], d, snapshot(), 'b' * 40,
                                                    proof['job_id'], 1100), value['result']['report'])

    def test_wrong_run_job_artifact_or_digest_is_rejected_before_use(self):
        d, value = evidence()
        for record, key, bad in [('run', 'head_sha', 'f' * 40), ('run', 'run_attempt', 2),
            ('job', 'conclusion', 'failure'), ('job', 'head_sha', 'f' * 40), ('job', 'run_id', 98),
            ('artifact', 'expired', True), ('artifact', 'name', 'evidence-7-0'), ('artifact', 'digest', 'sha256:' + '0' * 64)]:
            api = ActionsAPI(value)
            getattr(api, record)[key] = bad
            with self.subTest(record=record, key=key), self.assertRaises(Refusal):
                provenance.artifact_document(api, d, 99, 1, 7, 'evidence')

    def test_missing_cleanup_cross_registry_and_job_are_rejected(self):
        d, value = evidence()
        for target, key, bad in [('result', 'cleanup_complete', False), ('result', 'unknown', 'data'),
                                 ('outer', 'registry_revision', 'c' * 40), ('outer', 'kind', 'cloud-parent')]:
            modified = copy.deepcopy(value)
            (modified['result'] if target == 'result' else modified)[key] = bad
            with self.subTest(key=key), self.assertRaises(Refusal):
                provenance.validate_evidence(modified, d, snapshot(), 'b' * 40, 100, 1100)
        with self.assertRaises(Refusal):
            provenance.validate_evidence(value, d, snapshot(), 'b' * 40, 101, 1100)

    def test_environment_does_not_replace_authenticated_job_identity(self):
        d, value = evidence()
        api = ActionsAPI(value)
        api.job.update(status='in_progress', conclusion=None)
        env = {'GITHUB_REPOSITORY_ID': '456', 'GITHUB_SHA': '1' * 40,
               'GITHUB_RUN_ID': '99', 'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_JOB': 'verify'}
        self.assertEqual(provenance.admit_job(api, d, env, 'verify (7)', 1100)['id'], 100)
        with self.assertRaises(Refusal):
            provenance.admit_job(api, d, dict(env, GITHUB_JOB='publish'), 'verify (7)', 1100)
        api.job['head_sha'] = 'f' * 40
        with self.assertRaises(Refusal):
            provenance.admit_job(api, d, env, 'verify (7)', 1100)


if __name__ == '__main__':
    unittest.main()
