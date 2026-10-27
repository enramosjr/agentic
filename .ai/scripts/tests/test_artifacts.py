"""Pinned artifacts survive rebuilds and reject mutation as qualified evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_lifecycle import LifecycleCase


class ArtifactTests(LifecycleCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'artifacts.py'), *args],
                              cwd=self.repo, capture_output=True, text=True, timeout=15)

    def freeze(self):
        result = self.cli('freeze', '--root', str(self.repo), '--file', 'app.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.addCleanup(self.make_writable, Path(receipt['bundle']))
        return receipt

    @staticmethod
    def make_writable(root):
        if root.exists():
            for path in [root, *root.rglob('*')]:
                path.chmod(0o755 if path.is_dir() else 0o644)

    def run_bundle(self, receipt, *argv):
        return self.cli('run', '--bundle', receipt['bundle'], '--sha256', receipt['sha256'], '--', *argv)

    def test_rebuild_cannot_replace_the_qualified_artifact(self):
        receipt = self.freeze()
        (self.repo / 'app.py').write_text("print('broken rebuild')\n")
        result = self.run_bundle(receipt, sys.executable, '{artifact:app.py}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'hi')

    def test_tampering_before_or_during_acceptance_fails_closed(self):
        receipt = self.freeze()
        script = ('from pathlib import Path; import sys; p=Path(sys.argv[1]); '
                  'p.chmod(0o644); p.write_text("tampered")')
        result = self.run_bundle(receipt, sys.executable, '-c', script, '{artifact:app.py}')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('hash mismatch', result.stderr)
        result = self.run_bundle(receipt, sys.executable, '{artifact:app.py}')
        self.assertNotEqual(result.returncode, 0)

    def test_wrong_pin_and_unreferenced_bundle_are_refused(self):
        receipt = self.freeze()
        self.assertNotEqual(self.run_bundle(receipt, sys.executable, '-c', 'pass').returncode, 0)
        receipt['sha256'] = '0' * 64
        self.assertNotEqual(self.run_bundle(receipt, sys.executable, '{artifact:app.py}').returncode, 0)

    def test_variants_are_separate_and_do_not_change_qualified_bytes(self):
        receipt = self.freeze()
        result = self.cli('variant', '--bundle', receipt['bundle'], '--sha256', receipt['sha256'])
        self.assertEqual(result.returncode, 0, result.stderr)
        variant = json.loads(result.stdout)
        self.assertFalse(variant['qualified'])
        (Path(variant['variant']) / 'app.py').write_text("raise SystemExit(3)\n")
        self.assertEqual(subprocess.run([sys.executable, str(Path(variant['variant']) / 'app.py')]).returncode, 3)
        self.assertEqual(self.run_bundle(receipt, sys.executable, '{artifact:app.py}').returncode, 0)

    def test_paths_and_symlinks_cannot_escape_the_declared_root(self):
        result = self.cli('freeze', '--root', str(self.repo), '--file', '../outside')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unsafe artifact path', result.stderr)
        if hasattr(os, 'symlink'):
            (self.repo / 'link.py').symlink_to(self.repo / 'app.py')
            result = self.cli('freeze', '--root', str(self.repo), '--file', 'link.py')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('symlink refused', result.stderr)


if __name__ == '__main__':
    unittest.main()
