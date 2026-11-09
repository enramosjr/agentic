"""The actual worker archive is deterministic, complete, and stays held."""
import backend_test_support  # Establish the explicit source-only test paths.
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import trusted_ci_fixtures
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deploy/authority'))
import build_runtime
import cloud_worker


class RuntimeBundleContracts(unittest.TestCase):
    def test_real_bundle_roundtrip_and_worker_hold(self):
        root = Path(__file__).resolve().parents[3]
        raw = build_runtime.archive(root)
        self.assertEqual(raw, build_runtime.archive(root))
        with tempfile.TemporaryDirectory() as folder:
            target = cloud_worker.unpack(raw, Path(folder) / 'runtime')
            manifest = json.loads((target / 'runtime-manifest.json').read_text())
            self.assertFalse(manifest['enforcement_active'])
            for name in ('deploy/authority/service.py', 'deploy/authority/registration.py',
                         'deploy/authority/coding_stdio.py', 'deploy/authority/artifact_upload/action.mjs',
                         'deploy/authority/cloud.py', 'deploy/authority/cloud_execution.py',
            'deploy/authority/trial_candidates.py', 'deploy/authority/trial_controller.py', 'deploy/authority/trial_case.py', 'deploy/authority/trial_launch.py',
                         '.github/workflows/authority-v2.yml', '.github/workflows/authority-v2-recovery.yml'):
                self.assertIn(name, manifest['files'])
            for name, fingerprint in manifest['files'].items():
                self.assertEqual(hashlib.sha256((target / name).read_bytes()).hexdigest(), fingerprint)
            imported = subprocess.run([sys.executable,'-I','-c',
            'import sys; sys.path.insert(0,sys.argv[1]); import coding_parent,task_controls,trial_candidates,trial_controller,trial_case,trial_launch',
                str(target / 'deploy/authority')],capture_output=True,text=True,cwd=folder,timeout=15)
            self.assertEqual(imported.returncode,0,imported.stderr)
            result = subprocess.run([sys.executable, '-I', str(target / 'deploy/authority/cloud_worker.py')],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stderr)['enforcement_active'])
            self.assertNotIn('Traceback', result.stderr)
            for entrypoint, args in [('service.py', ['credential', str(Path(sys.executable).resolve())]),
                                     ('service.py', ['prepare-task', str(Path(sys.executable).resolve())]),
                                     ('service.py', ['model-authorization', str(Path(sys.executable).resolve())]),
                                     ('service.py', ['task', str(Path(sys.executable).resolve())]),
                                     ('service.py', ['task-controls', str(Path(sys.executable).resolve())]),
                                     *[('service.py', [role, str(Path(sys.executable).resolve())]) for role in
                                       ('discover','prepare','verify','publication-controls','publish','proof','broker','controls','final-proof','finalize')],
                                     ('coding_stdio.py', ['--stdio'])]:
                held = subprocess.run([sys.executable, '-I', str(target / 'deploy/authority' / entrypoint), *args],
                    input=b'not a challenge', capture_output=True, cwd=folder, timeout=15)
                self.assertEqual(held.returncode, 1)
                self.assertIn(b'refused', held.stderr)
                self.assertNotIn(b'Traceback', held.stderr)

    def test_no_overwrite_or_unbounded_custom_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'runtime.tgz'
            build_runtime.build(Path(__file__).resolve().parents[3], output)
            from trusted_ci_policy import Refusal
            with self.assertRaises(Refusal):
                build_runtime.build(Path(__file__).resolve().parents[3], output)


if __name__ == '__main__':
    unittest.main()
