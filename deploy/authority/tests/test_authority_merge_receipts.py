"""Local durable-receipt contracts; no hosted artifact qualification."""
import backend_test_support
import copy
import hashlib
import io
import json
import unittest
import zipfile

from test_authority_merge_window import binding, gate
from trusted_ci_policy import Refusal, digest
import merge_receipts
import merge_window


class ReceiptAPI:
    def __init__(self):
        self.artifacts, self.archives = [], {}
        self.job = dict(id=77, run_id=99, head_sha='a' * 40, name='broker (7)',
            status='in_progress', conclusion=None, started_at='1970-01-01T00:16:40Z', completed_at=None)
        self.run = dict(id=99, path='.github/workflows/authority.yml', workflow_id=33,
            repository={'id': 456}, head_sha='a' * 40, run_attempt=1, event='schedule', head_branch='main')

    def get(self, path):
        if path.endswith('/actions/runs/99/attempts/1'):
            return self.run
        if path.endswith('/actions/workflows/33'):
            return dict(id=33, path='.github/workflows/authority.yml')
        raise AssertionError(path)

    def pages(self, path, collection):
        if path.endswith('/attempts/1/jobs'):
            return [self.job]
        if path.endswith('/runs/99/artifacts'):
            return self.artifacts
        raise AssertionError(path)

    def fetch(self, path, **kwargs):
        return self.archives[int(path.split('/')[-2])]

    def upload(self, name, raw):
        if any(a['name'] == name for a in self.artifacts):
            raise Refusal('provider conflict')
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('receipt.json', raw)
        packed = stream.getvalue()
        identity = 500 + len(self.artifacts)
        self.archives[identity] = packed
        self.artifacts.append(dict(id=identity, name=name, expired=False,
            created_at='1970-01-01T00:16:42Z', digest='sha256:' + hashlib.sha256(packed).hexdigest(),
            workflow_run=dict(id=99, repository_id=456, head_repository_id=456, head_sha='a' * 40)))
        return identity


def dispatch_document():
    g = gate()
    return dict(schema_version=2, kind='dispatch', gate_digest=digest(g),
                operation_id=g['operation_id'], sequence=g['sequence'], gate=g)


class ReceiptContracts(unittest.TestCase):
    def test_positive_not_submitted_receipt_excludes_dispatch_and_binds_producer(self):
        store, api = self.store()
        document = merge_receipts.not_submitted(binding(), 77, 1002)
        locator = store.append('not-submitted', document)
        self.assertEqual(store.authenticate(locator), document)
        with self.assertRaises(Refusal): store.append('dispatch', dispatch_document())
        api.job.update(status='completed', conclusion='cancelled', completed_at='1970-01-01T00:16:42Z')
        recovery, _ = self.store(api, recovery=True)
        self.assertEqual(recovery.authenticate(locator), document)
        for field, value in [('job_id', 78), ('operation_digest', '0' * 64), ('issued', 1003)]:
            changed = dict(document, **{field: value})
            with self.subTest(field=field), self.assertRaises(Refusal):
                store._document('not-submitted', changed)

    def store(self, api=None, **kwargs):
        api = api or ReceiptAPI()
        return merge_receipts.ActionsReceipts(api, lambda: binding(), 77, lambda: 1002,
                                             uploader=api.upload, **kwargs), api

    def test_create_authenticate_and_duplicate_even_identical_refuses(self):
        store, api = self.store()
        value = dispatch_document()
        loc = store.append('dispatch', value)
        self.assertEqual(store.authenticate(loc), value)
        self.assertEqual(api.artifacts[0]['name'], 'agentic-merge-' + '1' * 32 + '-s1-a1-dispatch')
        with self.assertRaises(Refusal):
            store.append('dispatch', value)
        self.assertEqual(len(api.artifacts), 1)

    def test_lost_upload_ack_never_permits_merge_or_reupload(self):
        api, calls = ReceiptAPI(), []
        def lost(name, raw):
            api.upload(name, raw)
            raise Refusal('lost acknowledgement')
        store, _ = self.store(api)
        store.uploader = lost
        class Source:
            def merge(self, *args, **kwargs):
                calls.append(args)
        with self.assertRaises(Refusal):
            merge_window.dispatch(gate(), lambda: binding(), store, Source(), lambda: 1002)
        self.assertEqual(calls, [])
        with self.assertRaises(Refusal):
            store.append('dispatch', dispatch_document())
        recovery, _ = self.store(api, recovery=True)
        self.assertEqual(recovery.authenticate(recovery.find_for_recovery('dispatch')), dispatch_document())
        self.assertEqual(len(api.artifacts), 1)

    def test_exact_job_artifact_and_operation_are_required(self):
        for record, key, bad in [('job', 'id', 78), ('job', 'name', 'verify (7)'),
            ('job', 'head_sha', 'b' * 40), ('run', 'run_attempt', 2),
            ('run', 'head_sha', 'b' * 40), ('run', 'event', 'pull_request')]:
            store, api = self.store()
            getattr(api, record)[key] = bad
            with self.subTest(key=key), self.assertRaises(Refusal):
                store.append('dispatch', dispatch_document())
            self.assertEqual(api.artifacts, [])
        for key, bad in [('expired', True), ('digest', 'sha256:' + '0' * 64),
                         ('created_at', '1970-01-01T00:16:39Z')]:
            store, api = self.store()
            loc = store.append('dispatch', dispatch_document())
            api.artifacts[0][key] = bad
            with self.subTest(key=key), self.assertRaises(Refusal):
                store.authenticate(loc)

    def test_recovery_accepts_failed_producer_but_cannot_append_or_dispatch(self):
        store, api = self.store()
        loc = store.append('dispatch', dispatch_document())
        api.job.update(status='completed', conclusion='failure', completed_at='1970-01-01T00:16:42Z')
        with self.assertRaises(Refusal):
            store.authenticate(loc)
        recovery, _ = self.store(api, recovery=True)
        self.assertEqual(recovery.authenticate(loc), dispatch_document())
        with self.assertRaises(Refusal):
            recovery.append('dispatch', dispatch_document())

    def test_wrong_payload_and_replacement_artifact_are_rejected(self):
        for field, bad in [('operation_id', '2' * 32), ('sequence', 2), ('gate_digest', '0' * 64)]:
            store, api = self.store()
            doc = dispatch_document()
            doc[field] = bad
            with self.subTest(field=field), self.assertRaises(Refusal):
                store.append('dispatch', doc)
            self.assertEqual(api.artifacts, [])
        store, api = self.store()
        loc = store.append('dispatch', dispatch_document())
        api.artifacts[0]['id'] += 1
        with self.assertRaises(Refusal):
            store.authenticate(loc)

    def test_unsafe_archive_and_duplicate_name_fail_closed(self):
        for filename in ('../receipt.json', 'other.json'):
            store, api = self.store()
            loc = store.append('dispatch', dispatch_document())
            raw = io.BytesIO()
            with zipfile.ZipFile(raw, 'w') as archive:
                archive.writestr(filename, json.dumps(dispatch_document()))
            api.archives[loc['artifact_id']] = raw.getvalue()
            api.artifacts[0]['digest'] = 'sha256:' + hashlib.sha256(raw.getvalue()).hexdigest()
            with self.subTest(filename=filename), self.assertRaises(Refusal):
                store.authenticate(loc)
        store, api = self.store()
        loc = store.append('dispatch', dispatch_document())
        api.artifacts.append(copy.deepcopy(api.artifacts[0]))
        with self.assertRaises(Refusal):
            store.authenticate(loc)


if __name__ == '__main__':
    unittest.main()
