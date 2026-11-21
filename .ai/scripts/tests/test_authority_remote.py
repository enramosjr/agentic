"""Installed routing authenticates a fixed release before executing any backend."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import sys
import os
import unittest
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import authority_release
import authority_remote
from trusted_ci_policy import Refusal


def fixture():
    output = io.BytesIO()
    files = {'deploy/authority/operator_setup.py': b'# synthetic entry',
             'deploy/authority/requirements-auth.txt': b'fixed==1.0\n'}
    with zipfile.ZipFile(output, 'w') as archive:
        for path, raw in files.items(): archive.writestr('source/' + path, raw)
    raw = output.getvalue()
    pin = dict(repository='owner/release', repository_id=71, revision='a' * 40,
               archive_sha256=hashlib.sha256(raw).hexdigest(),
               files={p: hashlib.sha256(v).hexdigest() for p, v in files.items()})
    class API:
        def __init__(self): self.calls = []
        def __call__(self, route, binary=False):
            self.calls.append(route)
            if route == '/repos/owner/release': return dict(id=71, full_name='owner/release')
            if route.endswith('/commits/' + 'a' * 40): return dict(sha='a' * 40)
            if route.endswith('/zipball/' + 'a' * 40): return raw
            raise AssertionError(route)
    return pin, API()


class RemoteRoutingContracts(unittest.TestCase):
    def temporary(self):
        return tempfile.TemporaryDirectory(dir=str(Path.home()) if os.name == 'nt' else '/tmp')
    def test_unreleased_build_refuses_without_network_or_execution(self):
        with patch.object(authority_remote, 'fetch') as fetch, patch.object(authority_remote.subprocess, 'run') as run:
            with self.assertRaises(Refusal): authority_remote.route('connect', [])
            fetch.assert_not_called()
            run.assert_not_called()

    def test_authenticates_origin_revision_archive_and_selected_files(self):
        pin, api = fixture()
        with self.temporary() as folder:
            root = Path(folder) / 'release'
            authority_remote.obtain(pin, root, api)
            self.assertEqual((root / 'deploy/authority/operator_setup.py').read_bytes(), b'# synthetic entry')
            self.assertEqual(len(api.calls), 3)

    def test_substituted_origin_revision_archive_or_file_never_extracts(self):
        for defect in ('origin', 'revision', 'archive', 'file', 'path'):
            pin, api = fixture()
            if defect == 'origin': pin['repository_id'] = 999
            elif defect == 'revision':
                old = api
                def api(route, binary=False):
                    return dict(sha='b' * 40) if '/commits/' in route else old(route, binary)
            elif defect == 'archive': pin['archive_sha256'] = 'f' * 64
            elif defect == 'file': pin['files']['deploy/authority/operator_setup.py'] = 'f' * 64
            else: pin['files']['../escape.py'] = 'f' * 64
            with self.subTest(defect=defect), self.temporary() as folder:
                root = Path(folder) / 'release'
                with self.assertRaises(Refusal): authority_remote.obtain(pin, root, api)
                self.assertFalse(root.exists())

    def test_route_passes_only_fixed_command_and_no_workspace_deployment_path(self):
        pin, api = fixture()
        with patch.object(authority_release, 'BOOTSTRAP_RELEASE', pin), \
             patch.object(authority_remote, 'fetch', api), \
             patch.object(authority_remote, 'execute', return_value=0) as execute:
            self.assertEqual(authority_remote.route('connect', []), 0)
            root, command = execute.call_args.args
            self.assertEqual(command, ['connect'])
            self.assertFalse(Path(root).is_relative_to(authority_remote.CHECKOUT))
        with self.assertRaises(Refusal): authority_remote.route('setup', ['--deployment', 'candidate.json'])
        with self.assertRaises(Refusal): authority_remote.route('destroy', [])

    def test_optional_environment_executes_acquired_entry_with_no_inherited_service_root(self):
        with self.temporary() as folder:
            root = Path(folder) / 'release'
            pin, api = fixture()
            authority_remote.obtain(pin, root, api)
            (root / authority_remote.ENTRY).write_text(
                'import os,sys\nsys.exit(23 if sys.argv[1:]==["connect"] and "GH_TOKEN" not in os.environ else 9)\n')
            (root / authority_remote.REQUIREMENTS).write_text('# local fixture: no network dependencies\n')
            with patch.dict(os.environ, {'GH_TOKEN': 'SYNTHETIC-FORBIDDEN-ROOT', 'PYTHONPATH': 'SYNTHETIC-CANDIDATE'}):
                self.assertEqual(authority_remote.execute(root, ['connect']), 23)


if __name__ == '__main__': unittest.main()
