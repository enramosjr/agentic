"""The maintainer preflight bundle contains only explicitly selected sources."""
import backend_test_support  # Establish the explicit source-only test paths.
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
import zipfile

import trusted_ci_fixtures
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'deploy' / 'authority'))
import build_bootstrap as bundle
from trusted_ci_policy import Refusal


class BundleContracts(unittest.TestCase):
    def test_extracted_bundle_runs_without_workspace_or_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / 'candidate.zip'
            bundle.build(ROOT, archive)
            with zipfile.ZipFile(archive) as source:
                source.extractall(root / 'extracted')
            executable = root / 'extracted' / 'deploy' / 'authority' / 'bootstrap_stage.py'
            env = {k: v for k, v in os.environ.items() if k in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP')}
            env.update(PATH=os.defpath, PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
            help_result = subprocess.run([sys.executable, str(executable), '--help'], cwd=folder,
                env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            refused = subprocess.run([sys.executable, str(executable), 'preview', '--repository', '../escape'],
                cwd=folder, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(refused.returncode, 1)
            self.assertEqual(json.loads(refused.stderr)['state'], 'blocked')
            self.assertFalse(json.loads(refused.stderr)['enforcement_active'])
            native = executable.with_name('operator_setup.py')
            native_help = subprocess.run([sys.executable, str(native), '--help'], cwd=folder,
                env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(native_help.returncode, 0, native_help.stderr)
            for command in ('connect', 'setup'):
                held = subprocess.run([sys.executable, str(native), command], cwd=folder,
                    env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(held.returncode, 1, held.stderr)
                self.assertEqual(json.loads(held.stderr)['state'], 'blocked')

    def test_frozen_bundle_is_deterministic_and_records_each_source_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / 'first.zip', Path(folder) / 'second.zip'
            result = bundle.build(ROOT, first)
            bundle.build(ROOT, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(result['sha256'], hashlib.sha256(first.read_bytes()).hexdigest())
            with zipfile.ZipFile(first) as archive:
                manifest = json.loads(archive.read('bundle-manifest.json'))
                self.assertEqual(set(archive.namelist()), set(manifest['files']) | {'bundle-manifest.json'})
                for name, expected in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected)
                self.assertFalse(any('.git/' in n or '.worktrees/' in n for n in archive.namelist()))

    def test_bundle_never_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'existing.zip'
            output.write_bytes(b'preserve')
            with self.assertRaises(Refusal):
                bundle.build(ROOT, output)
            self.assertEqual(output.read_bytes(), b'preserve')


if __name__ == '__main__':
    unittest.main()
