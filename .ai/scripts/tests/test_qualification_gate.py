"""Fail-closed qualification summary over the actual workflow command."""
import os
import itertools
from pathlib import Path
import re
import subprocess
import unittest


class QualificationGateTests(unittest.TestCase):
    def workflow(self):
        return (Path(__file__).resolve().parents[3] / '.github/workflows/framework-parity.yml').read_text()

    def test_summary_runs_after_unsuccessful_dependencies(self):
        summary = self.workflow().split('\n  qualification:\n', 1)[1]
        self.assertIn('if: always()', summary)
        self.assertIn('needs: [source_hygiene, windows_preflight, regression_segments, authority_backend]', summary)

    def test_backend_contracts_are_required_without_optional_skip_or_resume(self):
        backend = self.workflow().split('\n  authority_backend:\n', 1)[1].split('\n  qualification:\n', 1)[0]
        self.assertIn('python -m unittest discover -s deploy/authority/tests', backend)
        self.assertIn("python: ['3.9', '3.15']", backend)
        self.assertIn('os: [ubuntu-latest, windows-latest]', backend)
        self.assertNotIn('continue-on-error', backend)
        self.assertNotIn('run_tests.py', backend)
        self.assertIn('deploy/authority/requirements-auth.txt', backend)
        self.assertIn('python deploy/authority/test_bootstrap_signing.py', backend)
        self.assertIn('python deploy/authority/test_model_vault.py', backend)
        self.assertIn('python deploy/authority/test_model_oidc.py', backend)
        self.assertIn('python deploy/authority/test_model_auth.py', backend)
        self.assertIn('python deploy/authority/test_model_consent.py', backend)
        self.assertIn('python deploy/authority/test_setup_credentials.py', backend)
        self.assertIn('node deploy/authority/artifact_upload/test_action.mjs', backend)
        self.assertIn('node deploy/authority/artifact_upload/test_upload.mjs', backend)
        self.assertIn('node deploy/authority/artifact_upload/test_sdk.mjs', backend)
        self.assertIn('npm ci --ignore-scripts', backend)

    @unittest.skipIf(os.name == 'nt', 'the summary executes in Bash on Ubuntu')
    def test_actual_summary_command_rejects_every_unsuccessful_state(self):
        command = re.search(r"^\s+run: '(\[\[.+\]\])'\s*$", self.workflow(), re.MULTILINE).group(1)
        def check(value):
            states = ('success', 'failure', 'cancelled', 'skipped', '', 'unknown')
            for hygiene, preflight, segments, backend in itertools.product(states, repeat=4):
                result = subprocess.run(['bash', '-c', value],
                    env={**os.environ, 'HYGIENE_RESULT': hygiene,
                         'PREFLIGHT_RESULT': preflight, 'SEGMENTS_RESULT': segments,
                         'BACKEND_RESULT': backend},
                    capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode == 0, hygiene == preflight == segments == backend == 'success',
                                 (hygiene, preflight, segments, backend, result.stderr))
        check(command)
        for omitted in ('HYGIENE_RESULT', 'PREFLIGHT_RESULT', 'SEGMENTS_RESULT', 'BACKEND_RESULT'):
            remaining = [name for name in ('HYGIENE_RESULT', 'PREFLIGHT_RESULT', 'SEGMENTS_RESULT', 'BACKEND_RESULT')
                         if name != omitted]
            with self.subTest(omitted=omitted), self.assertRaises(AssertionError):
                check('[[ ' + ' && '.join('"$' + name + '" == success' for name in remaining) + ' ]]')
