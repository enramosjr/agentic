"""Pinned artifacts survive rebuilds and reject mutation as qualified evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_lifecycle import LifecycleCase
import process_runtime


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
        if os.name == 'nt':
            link = self.repo / 'linked-directory'
            created = subprocess.run(f'cmd.exe /d /c mklink /J "{link}" "{self.repo}"',
                                     capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(created.returncode, 0, created.stderr)
            result = self.cli('freeze', '--root', str(self.repo), '--file', 'linked-directory/app.py')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('symlink refused', result.stderr)
        else:
            (self.repo / 'link.py').symlink_to(self.repo / 'app.py')
            result = self.cli('freeze', '--root', str(self.repo), '--file', 'link.py')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('symlink refused', result.stderr)

    def test_timeout_stops_descendants_before_post_run_verification(self):
        receipt = self.freeze()
        ready, escaped = self.repo / '.git/child-ready', self.repo / '.git/escaped'
        release = self.repo / '.git/release-child'
        scripts = str(Path(__file__).resolve().parents[1])
        child = (f'import sys; sys.path.insert(0,{scripts!r}); '
                 'from pathlib import Path; import json,time,process_runtime; '
                 f'Path({str(ready)!r}).write_text(json.dumps(process_runtime.identity())); '
                 f'release=Path({str(release)!r})\n'
                 'while not release.exists(): time.sleep(.01)\n'
                 f'Path({str(escaped)!r}).write_text("escaped")')
        parent = f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",{child!r}]); time.sleep(60)'
        # Arm the real timeout after readiness, excluding interpreter startup.
        wrapper = f'''
import sys, time, json
from pathlib import Path
sys.path.insert(0, {scripts!r})
import artifacts, process_runtime
process_runtime.configure_windows_environment()
ready = Path({str(ready)!r})
start, verify = process_runtime.ProcessTree.start, artifacts.verify
def ready_start(self, *args, **kwargs):
    process = start(self, *args, **kwargs)
    try:
        deadline = time.monotonic() + 30
        while not ready.exists():
            assert process.poll() is None, 'parent exited before descendant readiness'
            assert time.monotonic() < deadline, 'descendant readiness timed out'
            time.sleep(.01)
        return process
    except BaseException:
        self.close()
        raise
def checked_verify(*args, **kwargs):
    if ready.exists():
        identity = json.loads(ready.read_text())
        assert not process_runtime.alive(**identity), 'verification preceded descendant cleanup'
    return verify(*args, **kwargs)
process_runtime.ProcessTree.start = ready_start
artifacts.verify = checked_verify
raise SystemExit(artifacts.main())
'''
        try:
            result = subprocess.run([sys.executable, '-c', wrapper, 'run', '--bundle', receipt['bundle'],
                                     '--sha256', receipt['sha256'], '--timeout', '1', '--',
                                     sys.executable, '-c', parent, '{artifact:app.py}'],
                                    cwd=self.repo, capture_output=True, text=True, timeout=45)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('timed out', result.stderr)
            self.assertTrue(ready.exists(), 'descendant was not started, so cleanup was not exercised')
            self.assertFalse(process_runtime.alive(**json.loads(ready.read_text())))
            self.assertNotIn('verification preceded descendant cleanup', result.stderr)
            self.assertFalse(escaped.exists(), 'descendant outlived the artifact timeout')
        finally:
            if ready.exists():
                process_runtime.terminate_tree(**json.loads(ready.read_text()))


if __name__ == '__main__':
    unittest.main()
