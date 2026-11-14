"""R7 R8: installed local feedback remains distinct from external authorization."""
import os
import subprocess
import sys
from test_install import InstallerCase


class LocalFeedbackTests(InstallerCase):
    def test_local_gate_and_read_only_deployment_refusal(self):
        self.run_install('--no-knowledge')
        env = dict(os.environ)
        for key in ['GH_TOKEN', 'AGENTIC_READ_TOKEN', '_AGENTIC_LIFECYCLE_RUN_ROOTS']:
            env.pop(key, None)
        root = self.target / '.ai/scripts'
        declaration = subprocess.run([sys.executable, str(root / 'lifecycle.py'), 'tier', 'L2',
                                      '--reason', 'local fixture'], cwd=self.target, env=env,
                                     capture_output=True, text=True, timeout=30)
        self.assertEqual(declaration.returncode, 0, declaration.stderr)
        gate = subprocess.run([sys.executable, str(root / 'lifecycle.py'), 'gate', 'implement'],
                              cwd=self.target, env=env, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(gate.returncode, 0)
        self.assertIn('intent', gate.stdout + gate.stderr)
        before = self.snapshot()
        result = subprocess.run([sys.executable, str(root / 'trusted_ci.py'), 'verify-deployment', '--live'],
                                cwd=self.target, env=env, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unverified', result.stderr)
        self.assertEqual(self.snapshot(), before)
