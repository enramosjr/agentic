"""Cross-platform parity contracts, exercised with native OS implementations."""
from __future__ import annotations

import os
import json
import hashlib
import shlex
import shutil
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
            root = Path(directory) / '\u4f60\u597d project'
            root.mkdir()
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


class PersistedTextEncodingTests(unittest.TestCase):
    def test_unicode_repository_git_metadata_export_and_scan_under_legacy_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / '\u4f60\u597d project'
            scripts = root / '.ai/scripts'
            shutil.copytree(SCRIPTS, scripts, ignore=shutil.ignore_patterns('tests', '__pycache__'))
            (scripts / 'tests').mkdir()
            for name in ('test_run_tests.py', 'disk_tmp.py'):
                shutil.copy2(SCRIPTS / 'tests' / name, scripts / 'tests' / name)
            (root / '.agentic.json').write_bytes(b'{"repository_kind":"framework"}')
            name = '\u4f60\u597d.py'
            (root / name).write_bytes(b'def greet():\n    return 1\n')
            document = root / '.ai/docs/notice.md'
            document.parent.mkdir()
            document.write_bytes('# Notice\n\n\u4e81 content\n'.encode('utf-8'))
            for arguments in [('init', '-q'), ('add', '.'), ('-c', 'user.name=Test', '-c',
                    'user.email=test@example.com', 'commit', '-qm', 'fixture')]:
                subprocess.run(['git', '-C', str(root), *arguments], check=True)
            values = {**os.environ, 'PYTHONUTF8': '0', 'PYTHONIOENCODING': 'cp1252'}
            code = ('import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
                'import scratch,eval_outcome,pr_sync,scan,completion;root=Path(sys.argv[2]);'
                'print(json.dumps([scratch.git_common_dir(root).as_posix(),'
                'Path(eval_outcome.git(root,"rev-parse","--show-toplevel")).as_posix(),'
                'Path(pr_sync._git(root,"rev-parse","--show-toplevel").stdout.strip()).as_posix(),'
                'scan._git(root,"ls-files","-z"),completion.okf(root,"show",".ai/docs/notice.md","--body").stdout]))')
            result = subprocess.run([sys.executable, '-c', code, str(SCRIPTS), str(root)],
                                    cwd=root, env=values, capture_output=True, encoding='utf-8', timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            common, outcome, sync, inventory, text = json.loads(result.stdout)
            self.assertEqual((common, outcome, sync), ((root / '.git').as_posix(), root.as_posix(), root.as_posix()))
            self.assertIn(name + '\0', inventory)
            self.assertIn('\u4e81', text)
            command = [sys.executable if os.name == 'nt' else 'python3',
                       '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests', '-p', 'test_run_tests.py']
            exported = subprocess.run([sys.executable, str(scripts / 'assurance_inputs.py'), '--json', '--', *command],
                cwd=root, env=values, capture_output=True, encoding='utf-8', timeout=30)
            self.assertEqual(exported.returncode, 0, exported.stdout + exported.stderr)
            self.assertTrue(json.loads(exported.stdout)['ok'])
            (root / name).write_bytes(b'def greet():\n    pass # TODO\n')  # lifecycle:allow C2-pass-todo -- Deliberately broken owned scanner fixture; its denial is asserted below.
            scanned = subprocess.run([sys.executable, str(scripts / 'lifecycle.py'), 'scan-diff'],
                cwd=root, env=values, capture_output=True, encoding='utf-8', timeout=30)
            self.assertEqual(scanned.returncode, 1, scanned.stdout + scanned.stderr)
            self.assertIn(name, scanned.stdout)
            selected = subprocess.run([sys.executable, str(scripts / 'validation_select.py'), '--base', 'HEAD'],
                cwd=root, env=values, capture_output=True, encoding='utf-8', timeout=30)
            self.assertEqual(selected.returncode, 0, selected.stdout + selected.stderr)
            self.assertIn(name, json.loads(selected.stdout)['changed_paths'])

    def test_delta_hash_and_durable_audit_use_utf8_under_legacy_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = '# \u89c4\u8303\n\n\u4f60\u597d\n'
            (root / 'spec.md').write_bytes(body.encode('utf-8'))
            state = {'task': 'fixture', 'stages': {}, 'description': '\u4e81'}
            (root / 'record.json').write_bytes(json.dumps(state, ensure_ascii=False).encode('utf-8'))
            code = (
                'import sys,json;from pathlib import Path;from unittest.mock import patch;'
                'sys.path.insert(0,sys.argv[1]);import brownfield,eval_outcome;'
                'root=Path(sys.argv[2]);state=json.loads((root/"record.json").read_text(encoding="utf-8"));\n'
                'with patch.object(eval_outcome,"audit_view",return_value=[]), '
                'patch.object(eval_outcome.lifecycle,"complete",return_value=True), '
                'patch.object(eval_outcome.lifecycle,"record_path",return_value=root/"record.json"):\n'
                ' failures,_=eval_outcome.completion(root,"unused",state,None)\n'
                'print(json.dumps([brownfield.spec_hash(root/"spec.md"),failures]))\n')
            values = {**os.environ, 'PYTHONUTF8': '0', 'PYTHONIOENCODING': 'cp1252'}
            result = subprocess.run([sys.executable, '-c', code, str(SCRIPTS), str(root)],
                                    env=values, capture_output=True, encoding='utf-8', timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), [hashlib.sha256(body.strip().encode('utf-8')).hexdigest(),
                ['missing convergence for the approved spec']])


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
