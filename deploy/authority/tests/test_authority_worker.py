"""Worker input materialization is tested without privileged host setup."""
import backend_test_support  # Establish the explicit source-only test paths.
import hashlib
import io
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from test_authority_jobs import request
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deploy/authority'))
import cloud_worker as worker


def archive(name, data=b'fixture'):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as tar:
        item = tarfile.TarInfo(name)
        item.size = len(data)
        tar.addfile(item, io.BytesIO(data))
    return stream.getvalue()


class WorkerContracts(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'POSIX bind-mount permission contract')
    def test_candidate_root_is_readable_by_sandbox_uid(self):
        bundle, source = archive('authority/tool.py'), archive('candidate/marker')
        lease = request()
        for key, value in (('bundle', bundle), ('candidate', source)):
            lease['objects'][key]['sha256'] = hashlib.sha256(value).hexdigest()
        lease['deployment']['resources']['bundle_sha'] = hashlib.sha256(bundle).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            trusted, candidate = worker.materialize(lease, bundle, source, Path(folder) / 'job')
            self.assertEqual(trusted.stat().st_mode & 0o777, 0o700)
            self.assertEqual(candidate.stat().st_mode & 0o777, 0o755)
            self.assertTrue((candidate / 'marker').stat().st_mode & 0o004)

    def test_compressed_metadata_cannot_bypass_expanded_archive_limit(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz', format=tarfile.PAX_FORMAT) as tar:
            item = tarfile.TarInfo('root/file')
            item.pax_headers = {'comment': 'x' * 8192}
            tar.addfile(item, io.BytesIO())
        with tempfile.TemporaryDirectory() as folder, patch.object(worker, 'LIMIT', 1024):
            self.assertLess(len(stream.getvalue()), 1024)
            with self.assertRaises(ValueError):
                worker.unpack(stream.getvalue(), Path(folder) / 'out')

    def test_inputs_are_hashed_before_materialization_and_kept_separate(self):
        bundle, source = archive('authority/tool.py'), archive('candidate/marker')
        lease = request()
        for key, value in (('bundle', bundle), ('candidate', source)):
            lease['objects'][key]['sha256'] = hashlib.sha256(value).hexdigest()
        lease['deployment']['resources']['bundle_sha'] = hashlib.sha256(bundle).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            trusted, candidate = worker.materialize(lease, bundle, source, Path(folder) / 'job')
            self.assertEqual((trusted / 'tool.py').read_bytes(), b'fixture')
            self.assertEqual((candidate / 'marker').read_bytes(), b'fixture')
            self.assertFalse((candidate / 'tool.py').exists())
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'job'
            with self.assertRaises(ValueError):
                worker.materialize(lease, bundle + b'tampered', source, output)
            self.assertFalse(output.exists())

    def test_archive_traversal_and_links_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('root/../../escape', '/root/absolute', 'root/.git/config'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    worker.unpack(archive(name), Path(folder) / 'out')
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w:gz') as tar:
                item = tarfile.TarInfo('root/link')
                item.type, item.linkname = tarfile.SYMTYPE, '/etc/passwd'
                tar.addfile(item)
            with self.assertRaises(ValueError):
                worker.unpack(stream.getvalue(), Path(folder) / 'out')


if __name__ == '__main__':
    unittest.main()
