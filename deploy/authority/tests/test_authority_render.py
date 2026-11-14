"""Credential-free cloud template rendering; not hosted-adapter qualification."""
import backend_test_support  # Establish the explicit source-only test paths.
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from trusted_ci_fixtures import policy
from backend_test_support import config
import render_cloud
from trusted_ci_policy import Refusal

ROOT = Path(__file__).resolve().parents[3]


class CloudRenderContracts(unittest.TestCase):
    def test_both_provider_clis_render_without_credentials_or_provider_tools(self):
        for adapter in ('aws', 'azure'):
            c = config(adapter)
            with self.subTest(adapter=adapter), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'rendered'
                argv = [sys.executable, str(ROOT / 'deploy/authority/render_cloud.py')]
                for key in ('adapter', 'account', 'region', 'authority', 'branch', 'deployment'):
                    argv += ['--' + key, c[key]]
                argv += ['--output', str(destination)]
                env = {k: v for k, v in os.environ.items()
                       if k in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP')}
                env.update(PATH=os.defpath, PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
                           AWS_EC2_METADATA_DISABLED='true')
                result = subprocess.run(argv, env=env, cwd=folder, capture_output=True,
                                        text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                summary = json.loads(result.stdout)
                self.assertEqual(summary['state'], 'unqualified')
                self.assertFalse(summary['enforcement_qualified'])
                manifest = json.loads((destination / 'manifest.json').read_bytes())
                self.assertEqual(manifest['account'], c['account'])
                self.assertEqual(manifest['authority'], c['authority'])
                for name, fingerprint in manifest['files'].items():
                    self.assertEqual(hashlib.sha256((destination / name).read_bytes()).hexdigest(), fingerprint)
                template = json.loads((destination / summary['template']).read_bytes())
                if adapter == 'aws':
                    trust = template['Resources']['LauncherRole']['Properties']['AssumeRolePolicyDocument']
                    subject = trust['Statement'][0]['Condition']['StringEquals']['token.actions.githubusercontent.com:sub']
                else:
                    identity = next(r for r in template['resources']
                                    if r['type'] == 'Microsoft.ManagedIdentity/userAssignedIdentities')
                    subject = identity['resources'][0]['properties']['subject']
                self.assertEqual(subject, 'repo:owner/authority:ref:refs/heads/main')

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'existing'
            destination.mkdir()
            marker = destination / 'keep.txt'
            marker.write_text('user data')
            with self.assertRaises(Refusal):
                render_cloud.render(config(), destination)
            self.assertEqual(marker.read_text(), 'user data')
            self.assertEqual(sorted(p.name for p in destination.iterdir()), ['keep.txt'])

    def test_bad_configuration_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'rejected'
            bad = dict(config(), authority='../outside')
            with self.assertRaises(Refusal):
                render_cloud.render(bad, destination)
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
