"""Installed stdlib client, local projections and non-bypassable operational holds."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import io
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch
from test_authority_protocol import deployment
import authority_setup

ROOT = Path(__file__).resolve().parents[3]


class InstalledClientContracts(unittest.TestCase):
    def test_remote_operations_cannot_fall_through_if_release_hold_is_lifted(self):
        for command in ('connect','setup','repair','upgrade','destroy','qualify','publish','activate','task-start','merge'):
            args = [command] + (['--live'] if command == 'qualify' else [])
            with self.subTest(command=command), patch.object(authority_setup.release,'authorize'), \
                 patch.object(authority_setup,'inspect_local',return_value={'state':'blocked'}) as inspect, \
                 patch.object(authority_setup,'read_document') as read, \
                 redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as errors:
                result = authority_setup.main(args)
                self.assertEqual(result,1)
                inspect.assert_not_called()
                read.assert_not_called()
                self.assertFalse(json.loads(errors.getvalue())['remote_verified'])

    def test_installed_client_needs_no_deployment_package_and_holds_live_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            # Lifecycle's disk scratch lives below .git. Reproduce that context
            # even when this test is invoked outside the lifecycle runner.
            subprocess.run(['git', 'init', '-q', folder], check=True, capture_output=True)
            target = Path(folder) / '.git' / 'adopter'
            target.mkdir()
            subprocess.run(['git', 'init', '-q', str(target)], check=True, capture_output=True)
            install = subprocess.run([sys.executable, str(ROOT / '.ai/scripts/install.py'),
                                      '--no-knowledge', str(target)], capture_output=True, text=True, timeout=60)
            self.assertEqual(install.returncode, 0, install.stderr)
            self.assertFalse((target / 'deploy').exists())
            cli = target / '.ai/scripts/authority_setup.py'
            result = subprocess.run([sys.executable, str(cli), 'status'], cwd=target,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)['enforcement_active'])
            for command in (['connect'], ['setup'], ['qualify', '--live', '--adapter', 'all'], ['activate'], ['merge']):
                env = dict(os.environ, AGENTIC_ALLOW_LIVE='1')
                result = subprocess.run([sys.executable, str(cli), *command], cwd=target, env=env,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(json.loads(result.stdout)['state'], 'blocked')
            probe = ('import sys,unittest; loader=unittest.TestLoader(); '
                     'suite=loader.discover(sys.argv[1],pattern="test_authority_*.py"); '
                     'print("\\n".join(loader.errors)); '
                     'sys.exit(1 if loader.errors or suite.countTestCases()==0 else 0)')
            discovered = subprocess.run([sys.executable, '-I', '-c', probe,
                str(target / '.ai/scripts/tests')], cwd=target, capture_output=True, text=True, timeout=15)
            self.assertEqual(discovered.returncode, 0, discovered.stdout + discovered.stderr)
            for entry, group in [('test_authority_setup.py', 'AutomatedOnboarding'),
                                 ('test_authority_adapters.py', 'AdapterOwnership')]:
                missing = subprocess.run([sys.executable, str(target / '.ai/scripts/tests' / entry), group],
                    cwd=target, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(missing.returncode, 0)
                self.assertIn('optional backend unavailable', missing.stdout + missing.stderr)

    def test_local_active_claim_and_plan_never_authorize_enforcement(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'deployment.json'
            d = deployment()
            d.update(state='active', qualification='a' * 64)
            path.write_text(json.dumps(d))
            for command in ('status', 'plan', 'verify-local'):
                result = subprocess.run([sys.executable, str(ROOT / '.ai/scripts/authority_setup.py'), command,
                                        '--deployment', str(path)], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertFalse(data['enforcement_active'])
                self.assertEqual(data['state'], 'blocked')


if __name__ == '__main__':
    unittest.main()
