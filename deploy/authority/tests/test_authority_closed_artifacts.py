"""Closed producer roles and historical attempt authentication, not live proof."""
import backend_test_support
import hashlib
import io
import json
import unittest
import zipfile

from test_authority_protocol import deployment
from trusted_ci_policy import Refusal
import provenance


class HistoricalAPI:
    def __init__(self, role='proof', key='merge'):
        self.run = dict(id=99, path='.github/workflows/authority.yml', workflow_id=33,
            repository={'id': 456}, head_sha='1' * 40, run_attempt=1, event='schedule', head_branch='main')
        names = {'proof': ('proof (' + str(key) + ')', 'proof-' + str(key) + '-1', 'proof.json'),
                 'final-proof': ('final proof (' + str(key) + ')', 'final-proof-' + str(key) + '-1', 'final-proof.json'),
                 'task': ('task (' + str(key) + ')', 'task-' + str(key) + '-1', 'task.json'),
                 'task-ready': ('task (' + str(key) + ')', 'task-ready-' + str(key) + '-1', 'task-ready.json'),
                 'task-controls': ('task controls (' + str(key) + ')', 'task-controls-' + str(key) + '-1', 'task-controls.json'),
                 'model-lease': ('model authorization', 'model-lease-' + str(key) + '-1', 'model-lease.json'),
                 'qualification': ('hosted qualification', 'qualification-1', 'qualification.json'),
                 'controls': ('controls (' + str(key) + ')', 'controls-' + str(key) + '-1', 'controls.json'),
                 'credential-proof': ('credential proof (' + str(key) + ')', 'credential-proof-' + str(key) + '-1', 'credential-proof.json'),
                 'evidence': ('verify (' + str(key) + ')', 'evidence-' + str(key) + '-1', 'evidence.json')}
        job, artifact, self.member = names[role]
        self.job = dict(id=77, run_id=99, head_sha='1' * 40, name=job, status='completed',
            conclusion='success', started_at='1970-01-01T00:16:00Z', completed_at='1970-01-01T00:17:00Z')
        self.document = {'fixture': 'authenticated document; not a qualification claim'}
        self.raw = self.archive(self.member)
        self.artifact = dict(id=555, name=artifact, expired=False, created_at='1970-01-01T00:16:30Z',
            digest='sha256:' + hashlib.sha256(self.raw).hexdigest(),
            workflow_run=dict(id=99, repository_id=456, head_repository_id=456, head_sha='1' * 40))
        self.duplicate = False

    def archive(self, name, mode=0o100644):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as archive:
            item = zipfile.ZipInfo(name)
            item.create_system, item.external_attr = 3, mode << 16
            archive.writestr(item, json.dumps(self.document))
        return raw.getvalue()

    def get(self, path):
        if path.endswith('/actions/runs/99/attempts/1'):
            return self.run
        if path.endswith('/actions/workflows/33'):
            return dict(id=33, path='.github/workflows/authority.yml')
        raise AssertionError('unexpected endpoint ' + path)

    def pages(self, path, collection):
        if path.endswith('/runs/99/attempts/1/jobs'):
            return [self.job]
        if path.endswith('/runs/99/artifacts'):
            return [self.artifact] * (2 if self.duplicate else 1)
        raise AssertionError(path)

    def fetch(self, path, **kwargs):
        if path.endswith('/artifacts/555/zip'):
            return self.raw
        raise AssertionError(path)


def locator():
    return dict(run_id=99, attempt=1, job_id=77, artifact_id=555)


class ClosedArtifactContracts(unittest.TestCase):
    def test_all_closed_roles_use_the_historical_attempt_endpoint(self):
        for role, key in [('evidence', 7), ('controls', 7), ('task', 'a' * 32), ('task-controls', 'a' * 32), ('model-lease', 'a' * 32),
                          ('qualification', None), *[('credential-proof', p) for p in
                              ('admin', 'reader', 'issuer', 'coding', 'merge', 'model_vault', 'model_delivery')],
                          *[(role, p) for role in ('proof', 'final-proof')
                              for p in ('admin', 'reader', 'issuer', 'coding', 'merge')]]:
            api = HistoricalAPI(role, key)
            with self.subTest(role=role, key=key):
                proof = provenance.authenticated_document(api, deployment(), locator(), role, key, 1100)
                self.assertEqual(proof['document'], api.document)
                self.assertEqual(proof['job_id'], 77)
                self.assertEqual(proof['artifact_id'], 555)
                self.assertEqual(proof['artifact_digest'], api.artifact['digest'])

    def test_untrusted_role_and_locator_fields_are_rejected(self):
        for role, key in [('publish', 7), ('proof', 'owner'), ('task', '../escape'), ('qualification', 7)]:
            with self.subTest(role=role), self.assertRaises(Refusal):
                provenance.authenticated_document(HistoricalAPI(), deployment(), locator(), role, key, 1100)
        for field, bad in [('run_id', True), ('attempt', 0), ('job_id', 78), ('artifact_id', 556)]:
            loc = locator()
            loc[field] = bad
            with self.subTest(field=field), self.assertRaises(Refusal):
                provenance.authenticated_document(HistoricalAPI(), deployment(), loc, 'proof', 'merge', 1100)

    def test_substituted_or_failed_producers_cannot_supply_evidence(self):
        for record, key, bad in [('run', 'run_attempt', 2), ('run', 'id', 98),
            ('run', 'head_sha', 'f' * 40), ('run', 'event', 'pull_request'),
            ('job', 'name', 'proof (coding)'), ('job', 'conclusion', 'failure'),
            ('job', 'status', 'in_progress'), ('artifact', 'expired', True),
            ('artifact', 'digest', 'sha256:' + '0' * 64), ('artifact', 'name', 'proof-coding-1'),
            ('artifact', 'created_at', '1970-01-01T00:17:01Z')]:
            api = HistoricalAPI()
            getattr(api, record)[key] = bad
            with self.subTest(record=record, key=key), self.assertRaises(Refusal):
                provenance.authenticated_document(api, deployment(), locator(), 'proof', 'merge', 1100)

    def test_archive_and_duplicate_guards_apply_to_new_roles(self):
        for defect in ('path', 'link', 'duplicate', 'repository'):
            api = HistoricalAPI()
            if defect == 'path':
                api.raw = api.archive('../proof.json')
            elif defect == 'link':
                api.raw = api.archive('proof.json', 0o120777)
            elif defect == 'duplicate':
                api.duplicate = True
            else:
                api.artifact['workflow_run']['repository_id'] = 123
            api.artifact['digest'] = 'sha256:' + hashlib.sha256(api.raw).hexdigest()
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                provenance.authenticated_document(api, deployment(), locator(), 'proof', 'merge', 1100)


if __name__ == '__main__':
    unittest.main()
