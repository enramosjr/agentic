"""Cross-platform parity contracts, exercised with native OS implementations."""
from __future__ import annotations

import os
import json
import hashlib
import shlex
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import review_guard
import disk_tmp


class GitEnvironmentTests(unittest.TestCase):
    def test_protected_command_preserves_requested_python_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            child = 'import os,json;print(json.dumps([os.environ.get("PYTHONUTF8"),os.environ.get("PYTHONIOENCODING")]))'
            code = ('import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
                'import review_guard as g;\n'
                'with g.producer(Path(sys.argv[2])):\n'
                ' r=g.run(Path(sys.argv[2]),[sys.executable,"-c",sys.argv[3]],capture_output=True,text=True)\n'
                ' assert r.returncode==0,r.stderr\n print(r.stdout,end="")\n')
            values = {**os.environ, 'PYTHONUTF8': '0', 'PYTHONIOENCODING': 'cp1252'}
            result = subprocess.run([sys.executable, '-c', code, str(SCRIPTS), str(root), child],
                                    env=values, capture_output=True, encoding='utf-8', timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), ['0', 'cp1252'])

    def test_unicode_input_mutation_invalidates_proof_under_legacy_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            name = '\u4f60\u597d.txt'
            (root / name).write_bytes(b'value')
            tests = root / 'tests'
            tests.mkdir()
            (tests / 'test_value.py').write_text('import unittest\nfrom pathlib import Path\n'
                f'class Check(unittest.TestCase):\n def test_value(self):\n  self.assertEqual(Path({name!r}).read_bytes(), b"value")\n',
                encoding='utf-8')
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c',
                            'user.email=test@example.com', 'commit', '-qm', 'fixture'], check=True)
            values = dict(os.environ)
            if os.name == 'nt':
                values.update(PYTHONUTF8='0', PYTHONIOENCODING='cp1252')
            inventory = subprocess.run([sys.executable, str(SCRIPTS / 'repo.py'), 'files'],
                cwd=root, env={**values, 'REPO_ROOT': str(root)}, capture_output=True, encoding='utf-8')
            self.assertEqual(inventory.returncode, 0, inventory.stderr)
            self.assertIn(name, inventory.stdout)
            for arguments in [('tier', 'L1', '--reason', 'unicode evidence'),
                ('run', 'unit', '--', sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'),
                ('reuse', 'unit')]:
                result = subprocess.run([sys.executable, str(SCRIPTS / 'lifecycle.py'), *arguments],
                    cwd=root, env=values, capture_output=True, encoding='utf-8', timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            (root / name).write_bytes(b'changed')
            result = subprocess.run([sys.executable, str(SCRIPTS / 'lifecycle.py'), 'reuse', 'unit'],
                cwd=root, env=values, capture_output=True, encoding='utf-8', timeout=30)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(name, result.stdout + result.stderr)

    def test_unicode_acceptance_command_roundtrips_under_legacy_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / '\u4f60\u597d.txt').write_bytes(b'value')
            check = "from pathlib import Path; assert Path('\u4f60\u597d.txt').read_bytes()==b'value'"
            command = f'{shlex.quote(sys.executable)} -c {shlex.quote(check)}'
            (root / 'spec.md').write_text('# Spec\n\n## Requirements\n- R1: The command MUST read the named file.\n'
                f'## Acceptance\n- R1: `{command}` passes.\n## Non-goals\nOther work.\n## Open questions\nNone.\n',
                encoding='utf-8')
            (root / 'plan.md').write_text('Implement R1.\n', encoding='utf-8')
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c',
                            'user.email=test@example.com', 'commit', '-qm', 'fixture'], check=True)
            values = dict(os.environ)
            if os.name == 'nt':
                values.update(PYTHONUTF8='0', PYTHONIOENCODING='cp1252')
            for arguments in [('tier', 'L2', '--reason', 'unicode fixture'),
                              ('stage', 'intent', '--ref', 'spec.md', '--approved-by', 'human:fixture'),
                              ('stage', 'plan', '--ref', 'plan.md'), ('converge', 'spec.md')]:
                result = subprocess.run([sys.executable, str(SCRIPTS / 'lifecycle.py'), *arguments],
                                        cwd=root, env=values, capture_output=True, encoding='utf-8', timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('R1 PASS', result.stdout)

    def test_cli_unicode_output_uses_utf8_under_legacy_windows_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'unicode.txt'
            source.write_text('\u4f60\u597d\n', encoding='utf-8')
            values = dict(os.environ)
            if os.name == 'nt':
                values.update(PYTHONUTF8='0', PYTHONIOENCODING='cp1252')
            result = subprocess.run([sys.executable, str(SCRIPTS / 'repo.py'), 'read', str(source)],
                                    env=values, capture_output=True, encoding='utf-8', timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('\u4f60\u597d', result.stdout)

    def test_native_cli_finds_installed_git_without_shell_path_setup(self):
        values = dict(os.environ)
        if os.name == 'nt':
            values['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        result = subprocess.run([sys.executable, str(SCRIPTS / 'repo.py'), 'context', '--json'],
                                cwd=SCRIPTS.parents[1], env=values, capture_output=True,
                                text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['git']['head'])

    def test_preserves_injected_trust_without_git_namespace_redirection(self):
        values = {'PATH': os.environ['PATH'], 'GIT_CONFIG_COUNT': '2',
                  'GIT_CONFIG_KEY_0': 'safe.directory', 'GIT_CONFIG_VALUE_0': 'C:/work/project',
                  'GIT_CONFIG_KEY_1': 'core.worktree', 'GIT_CONFIG_VALUE_1': 'C:/other',
                  'GIT_DIR': 'C:/other/.git', 'GIT_WORK_TREE': 'C:/other',
                  'GIT_CONFIG_PARAMETERS': "'core.worktree'='C:/other'"}
        with patch.dict(os.environ, values, clear=True):
            actual = review_guard.git_environment()
        self.assertEqual(actual, {'PATH': values['PATH'], 'GIT_CONFIG_COUNT': '1',
            'GIT_CONFIG_KEY_0': 'safe.directory', 'GIT_CONFIG_VALUE_0': 'C:/work/project'})

    def test_malformed_injected_configuration_is_not_forwarded(self):
        with patch.dict(os.environ, {'GIT_CONFIG_COUNT': 'invalid'}, clear=True):
            self.assertEqual(review_guard.git_environment(), {})


class ProcessLifetimeTests(unittest.TestCase):
    def test_liveness_probe_does_not_terminate_the_probed_process(self):
        code = ('import os,sys; sys.path.insert(0,sys.argv[1]); import wait_check; '
                'print("alive", wait_check._alive(os.getpid()), flush=True)')
        result = subprocess.run([sys.executable, '-c', code, str(SCRIPTS)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'alive True'), result.stderr)

    def test_native_identity_distinguishes_living_exited_and_reused_pid(self):
        import process_runtime
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        try:
            identity = process_runtime.identity(child.pid)
            self.assertTrue(identity['birth'])
            self.assertTrue(process_runtime.alive(child.pid, identity['birth']))
            self.assertFalse(process_runtime.alive(child.pid, 'different-birth'))
        finally:
            child.kill()
            child.wait()
        self.assertFalse(process_runtime.alive(child.pid, identity['birth']))


class FixtureCleanupTests(unittest.TestCase):
    def test_read_only_fixture_is_removed_without_deleting_temp_root(self):
        directory = Path(tempfile.mkdtemp(prefix='parity-cleanup-')).resolve()
        target = directory / 'readonly'
        target.write_text('fixture')
        target.chmod(0o444)
        try:
            disk_tmp.remove_tree(directory)
            self.assertFalse(directory.exists())
            with self.assertRaises(ValueError):
                disk_tmp.remove_tree(Path(tempfile.gettempdir()))
        finally:
            if directory.exists():
                target.chmod(0o666)
                target.unlink()
                directory.rmdir()


class BaselineRestoreTests(unittest.TestCase):
    def test_repairs_only_verified_newline_conversion_and_refuses_other_edits(self):
        import restore_baselines
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / restore_baselines.RELATIVE
            target.mkdir(parents=True)
            data = b'original\ncontent\n'
            entry = {'file': 'baseline.txt', 'sha256': hashlib.sha256(data).hexdigest(),
                     'git_blob': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()}
            manifest = json.dumps({'sources': [entry]}).encode() + b'\n'
            (target / 'manifest.json').write_bytes(manifest)
            (target / 'baseline.txt').write_bytes(data)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'core.autocrlf=false', 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c',
                            'user.email=test@example.com', 'commit', '-qm', 'baseline'], check=True)
            (target / 'baseline.txt').write_bytes(data.replace(b'\n', b'\r\n'))
            pin = hashlib.sha256(manifest).hexdigest()
            self.assertEqual(restore_baselines.restore(root, manifest_sha=pin), 1)
            self.assertEqual((target / 'baseline.txt').read_bytes(), data)
            self.assertEqual(restore_baselines.restore(root, manifest_sha=pin), 0)
            (target / 'baseline.txt').write_bytes(b'tampered\r\n')
            with self.assertRaisesRegex(ValueError, 'beyond Git newline'):
                restore_baselines.restore(root, manifest_sha=pin)
            self.assertEqual((target / 'baseline.txt').read_bytes(), b'tampered\r\n')


if __name__ == '__main__':
    unittest.main()
