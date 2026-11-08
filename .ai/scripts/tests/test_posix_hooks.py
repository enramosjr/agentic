"""POSIX hook discovery, protocol, routing, and installed upgrade contracts R1-R6."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import disk_tmp  # noqa: F401
import install
from test_install import InstallerCase

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / '.ai/scripts'
POSIX = os.name == 'posix' and shutil.which('sh') is not None


def entries(data, flat=False):
    for event, groups in data['hooks'].items():
        for group in groups:
            for hook in [group] if flat else group['hooks']:
                yield event, group.get('matcher'), hook


def config(adapter):
    name = { 'codex': '.codex/hooks.json', 'claude': '.claude/settings.json',
             'cursor': '.cursor/hooks.json'}[adapter]
    return json.loads((ROOT / name).read_text())


@unittest.skipUnless(POSIX, 'POSIX shell required')
class PosixCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='posix hooks ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project with spaces'
        self.root.mkdir()
        self.bin = self.root / 'bin with spaces'
        self.bin.mkdir()
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(('GIT_', 'OKF_', 'CLAUDE_'))
                    and k not in ('LIFECYCLE_GUARD', 'PYTHONHOME', 'PYTHONPATH')}
        self.env.update(PATH=str(self.bin), HOME=str(self.root / 'home'),
                        PYTHONDONTWRITEBYTECODE='1')
        self.sh = shutil.which('sh')
        self.launcher = self.root / 'posix_hook.sh'
        if (SCRIPTS / 'posix_hook.sh').exists():
            shutil.copy2(SCRIPTS / 'posix_hook.sh', self.launcher)
        self.handler = self.root / 'lifecycle.py'
        self.handler.write_text('import json,sys\nprint(json.dumps(sys.argv[1:]))\n')

    def executable(self, directory, name, body=None):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        if body is None:
            path.symlink_to(sys.executable)
        else:
            path.write_text('#!/bin/sh\n' + body)
            path.chmod(0o755)
        return path

    def run_launcher(self, *args, data='', cwd=None):
        return subprocess.run([self.sh, str(self.launcher), str(self.handler), *args],
                              cwd=cwd or self.root, env=self.env, input=data,
                              capture_output=True, text=True, timeout=30)

    def isolate_fallbacks(self):
        """Redirect only fixed fallback paths; never modify system installations."""
        body = self.launcher.read_text()
        for original, local in [('/usr/local/bin/python3', self.root / 'fallback-local'),
                                ('/usr/bin/python3', self.root / 'fallback-system')]:
            self.assertIn(original, body)
            body = body.replace(original, shlex.quote(str(local)))
        self.launcher.write_text(body)


class InterpreterDiscoveryTests(PosixCase):
    def test_configured_hook_with_only_python(self):  # R1: original bug regression
        self.executable(self.bin, 'python')
        self.executable(self.bin, 'sh', 'exec ' + shlex.quote(self.sh) + ' "$@"\n')
        scripts = self.root / '.ai/scripts'
        scripts.mkdir(parents=True)
        shutil.copy2(self.handler, scripts / 'lifecycle.py')
        if self.launcher.exists():
            shutil.copy2(self.launcher, scripts / 'posix_hook.sh')
        self.env['CLAUDE_PROJECT_DIR'] = str(self.root)
        command = next(h['command'] for e, _, h in entries(config('claude'))
                       if e == 'SessionStart' and 'lifecycle.py' in h['command'])
        result = subprocess.run([self.sh, '-c', command], env=self.env, cwd=self.root,
                                input='{}', capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['hook', '--skip-in-cursor'])

    def test_python3_control(self):  # R1
        self.executable(self.bin, 'python3')
        result = self.run_launcher('control')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['control'])

    def test_search_order_and_broken_candidates(self):  # R1
        self.executable(self.bin, 'python3',
            'if [ "$1" = -c ]; then\n  exec ' + shlex.quote(sys.executable)
            + ' -c ' + shlex.quote('import sys; sys.version_info=(3,8); exec(sys.argv[1])')
            + ' "$2"\nfi\nexit 99\n')
        self.executable(self.bin, 'python', 'exit 99\n')
        second = self.root / 'second [literal]'
        self.executable(second, 'python3')
        self.env['PATH'] += ':' + str(second)
        result = self.run_launcher('selected')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['selected'])
        # A non-executable candidate and a broken shebang must also fall through.
        (self.bin / 'python3').write_text('#!/missing/interpreter\n')
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.bin / 'python3').chmod(0o644)
        self.assertEqual(self.run_launcher().returncode, 0)

    def test_python_follows_all_python3_candidates(self):  # R1
        self.executable(self.bin, 'python3', 'exit 1\n')
        self.executable(self.bin, 'python')
        self.assertEqual(self.run_launcher().returncode, 0)

    def test_empty_path_entries(self):  # R1
        self.executable(self.root, 'python3')
        for value in ('', ':' + str(self.bin), str(self.bin) + ':'):
            with self.subTest(PATH=value):
                self.env['PATH'] = value
                self.assertEqual(self.run_launcher().returncode, 0)

    def test_standard_fallback_order_and_home(self):  # R1
        self.isolate_fallbacks()
        local = self.executable(self.root, 'fallback-local')
        system = self.executable(self.root, 'fallback-system', 'exit 99\n')
        self.assertEqual(self.run_launcher().returncode, 0)
        local.unlink()
        system.unlink()
        self.executable(self.root, 'fallback-system')
        self.assertEqual(self.run_launcher().returncode, 0)
        system.unlink()
        self.executable(Path(self.env['HOME']) / '.local/bin', 'python3')
        self.assertEqual(self.run_launcher().returncode, 0)
        del self.env['HOME']
        # An unset HOME must not accidentally search a relative .local directory.
        self.executable(self.root / '.local/bin', 'python3')
        self.assertNotEqual(self.run_launcher().returncode, 0)

    def test_production_standard_fallback(self):  # R1
        result = self.run_launcher('fallback')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['fallback'])


class StreamAndExitTests(PosixCase):
    def test_probe_input_and_output_are_isolated(self):  # R2
        self.executable(self.bin, 'python3',
            'if [ "$1" = -c ]; then\n  IFS= read -r ignored || :\n'
            '  printf "probe noise\\n"\n  printf "probe error\\n" >&2\nfi\nexec '
            + shlex.quote(sys.executable) + ' "$@"\n')
        self.handler.write_text('import json,sys\nprint(json.dumps(json.load(sys.stdin)))\n')
        result = self.run_launcher(data='{"untouched": true}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'untouched': True})
        self.assertEqual(result.stderr, '')

    def test_exact_protocol_and_single_failed_dispatch(self):  # R2
        self.executable(self.bin, 'python3')
        self.handler.write_text('import json,sys\nfrom pathlib import Path\n'
                                'p=Path("invocations"); p.write_text(p.read_text()+"x" if p.exists() else "x")\n'
                                'print(json.dumps([sys.argv[1:],json.load(sys.stdin)],ensure_ascii=False))\n'
                                'print("handler stderr ☃",file=sys.stderr)\nsys.exit(7)\n')
        data = {'text': 'quotes " and unicode ☃', 'nested': [1, True]}
        result = self.run_launcher('two words', '', '*', 'quote"', data=json.dumps(data))
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(json.loads(result.stdout), [['two words', '', '*', 'quote"'], data])
        self.assertEqual(result.stderr, 'handler stderr ☃\n')
        self.assertEqual((self.root / 'invocations').read_text(), 'x')


class BootstrapFailureTests(PosixCase):
    def test_missing_python_is_actionable(self):  # R4
        self.isolate_fallbacks()
        self.handler.write_text('raise RuntimeError("HANDLER RAN")\n')
        result = self.run_launcher(data='{}')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('Python 3.9+', result.stderr)
        self.assertIn('PATH', result.stderr)
        self.assertNotIn('HANDLER RAN', result.stderr)

    def test_missing_handler_is_actionable(self):  # R4
        self.executable(self.bin, 'python3')
        self.handler.unlink()
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('reinstall', result.stderr.lower())


@unittest.skipUnless(POSIX, 'POSIX shell required')
class ConfiguredHookTests(PosixCase):
    def setUp(self):
        super().setUp()
        shutil.copytree(SCRIPTS, self.root / '.ai/scripts',
                        ignore=shutil.ignore_patterns('tests', '__pycache__'))
        (self.root / '.agentic.json').write_text('{"repository_kind":"framework"}')
        (self.root / 'source.py').write_text('print("fixture")\n')
        self.env['PATH'] = os.environ['PATH']
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'fixture')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], env=self.env,
                              capture_output=True, text=True, check=True, timeout=30)

    def invoke(self, adapter, handler, data, cwd=None):
        command = next(h['command'] for _, _, h in entries(config(adapter), adapter == 'cursor')
                       if handler in h['command'])
        env = dict(self.env)
        if adapter == 'claude':
            env['CLAUDE_PROJECT_DIR'] = str(self.root)
        data.setdefault('cwd', str(cwd or self.root))
        return subprocess.run([self.sh, '-c', command], cwd=cwd or self.root, env=env,
                              input=json.dumps(data), capture_output=True, text=True, timeout=30)

    def test_router_and_real_policy_decisions(self):  # R3
        nested = self.root / 'nested with spaces'
        nested.mkdir()
        for adapter in ('codex', 'claude', 'cursor'):
            for cwd in (self.root, nested) if adapter == 'codex' else (self.root,):
                with self.subTest(adapter=adapter, cwd=cwd):
                    event = 'sessionStart' if adapter == 'cursor' else 'SessionStart'
                    result = self.invoke(adapter, 'lifecycle.py', {'hook_event_name': event}, cwd)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('Lifecycle router', result.stdout)
                    for command, denied in [('cat source.py', True), ('git status', False)]:
                        data = {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
                                'tool_input': {'command': command}}
                        if adapter == 'cursor':
                            data = {'hook_event_name': 'beforeShellExecution', 'command': command,
                                    'cursor_version': 'test'}
                        result = self.invoke(adapter, 'shell_guard.py', data, cwd)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual('deny' in result.stdout, denied, result.stdout)

    def test_codex_linked_worktree_routes_locally(self):  # R3
        linked = self.root.parent / 'linked worktree with spaces'
        self.git('worktree', 'add', '-qb', 'linked', str(linked))
        declared = subprocess.run([sys.executable, str(linked / '.ai/scripts/lifecycle.py'),
                                   'tier', 'L1', '--reason', 'distinct linked fixture state'],
                                  cwd=linked, env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(declared.returncode, 0, declared.stderr)
        result = self.invoke('codex', 'lifecycle.py', {'hook_event_name': 'SessionStart'}, linked)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Active: tier L1', result.stdout)
        outer = self.invoke('codex', 'lifecycle.py', {'hook_event_name': 'SessionStart'})
        self.assertEqual(outer.returncode, 0, outer.stderr)
        self.assertIn('No tier declared', outer.stdout)

    def test_all_adapter_arguments_and_streams(self):  # R2, R3
        probe = ('import json,sys\nprint(json.dumps([sys.argv[1:],json.load(sys.stdin)]))\n'
                 'print("probe stderr",file=sys.stderr)\nsys.exit(7)\n')
        for handler in ('lifecycle.py', 'shell_guard.py', 'review_native.py', 'autonomy_hook.py'):
            (self.root / '.ai/scripts' / handler).write_text(probe)
        for adapter in ('codex', 'claude', 'cursor'):
            for _, _, hook in entries(config(adapter), adapter == 'cursor'):
                command = hook['command']
                handler = next(n for n in ('lifecycle.py', 'shell_guard.py', 'review_native.py',
                                          'autonomy_hook.py') if n in command)
                expected = [] if handler in ('shell_guard.py', 'autonomy_hook.py') else ['hook']
                if adapter == 'claude' and handler in ('shell_guard.py', 'lifecycle.py'):
                    expected += ['--skip-in-cursor']
                if handler == 'review_native.py':
                    expected += ['--adapter', adapter]
                result = subprocess.run([self.sh, '-c', command], cwd=self.root,
                    env={**self.env, 'CLAUDE_PROJECT_DIR': str(self.root)}, input='{"value": 1}',
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 7, result.stderr)
                self.assertEqual(json.loads(result.stdout), [expected, {'value': 1}])
                self.assertEqual(result.stderr, 'probe stderr\n')

    def test_missing_root_and_bootstrap(self):  # R4
        plain = self.root.parent / 'plain'
        plain.mkdir()
        result = self.invoke('codex', 'lifecycle.py', {}, plain)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Git', result.stderr)
        normal_path = self.env['PATH']
        self.env['PATH'] = str(self.bin)
        result = self.invoke('codex', 'lifecycle.py', {})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Git', result.stderr)
        self.env['PATH'] = normal_path
        (self.root / '.ai/scripts/posix_hook.sh').unlink()
        for adapter in ('codex', 'claude', 'cursor'):
            result = self.invoke(adapter, 'lifecycle.py', {})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('reinstall', result.stderr.lower())


class InstallationTests(InstallerCase):
    def setUp(self):
        if os.name != 'posix':
            return super().setUp()
        # DrvFS without metadata cannot retain the installer's POSIX modes.
        # Keep real CLI fixtures on a disk filesystem that can represent them.
        for directory in (Path(tempfile.gettempdir()), Path.home() / '.cache/okf-tests'):
            directory.mkdir(parents=True, exist_ok=True)
            disk_tmp.scratch.require_disk(directory)
            with tempfile.NamedTemporaryFile(dir=directory) as probe:
                try:
                    os.fchmod(probe.fileno(), 0o600)
                    supported = os.fstat(probe.fileno()).st_mode & 0o777 == 0o600
                except OSError:
                    supported = False
            if supported:
                with mock.patch.object(tempfile, 'tempdir', str(directory)):
                    super().setUp()
                return
        self.fail('Installer fixtures require a native disk filesystem supporting POSIX modes.')

    def test_coexisting_old_and_new_commands_dispatch_once(self):  # R5
        for adapter in ('codex', 'claude', 'cursor'):
            flat = adapter == 'cursor'
            desired = config(adapter)
            event, matcher, new = next(entries(desired, flat))
            suffix = new['command'].split('exec sh "$b" ', 1)[1]
            old_command = 'python3 ' + suffix.replace('$r/', '$(git rev-parse --show-toplevel)/')
            if flat:
                old_command = old_command.replace('"', '')
            old = {**new, 'command': old_command, 'timeout': 71, 'custom': 'keep'}
            existing = {**new, 'replacement-only': 'also keep'}
            groups = [old, existing] if flat else [{
                **({'matcher': matcher} if matcher else {}), 'hooks': [old, existing]}]
            merged = install.merge_hooks({'hooks': {event: groups}}, desired, [old_command], flat)
            found = [h for e, m, h in entries(merged, flat)
                     if e == event and m == matcher and h['command'] == new['command']]
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]['timeout'], 71)
            self.assertEqual(found[0]['custom'], 'keep')
            self.assertEqual(found[0]['replacement-only'], 'also keep')

    def test_clean_install_and_owned_upgrade_preserve_metadata(self):  # R5
        self.installed()
        self.assertTrue((self.target / '.ai/scripts/posix_hook.sh').is_file())
        manifest = self.manifest()
        for name in install.HOOK_FILES:
            flat = name == '.cursor/hooks.json'
            data = json.loads((self.target / name).read_text())
            old_commands = []
            for _, _, hook in entries(data, flat):
                new = hook['command']
                # Reconstruct the exact pre-launcher commands for a legacy install.
                suffix = new.split('exec sh "$b" ', 1)[1]
                old = 'python3 ' + suffix
                if name == '.codex/hooks.json':
                    old = old.replace('$r/', '$(git rev-parse --show-toplevel)/')
                if flat:
                    old = old.replace('"', '')
                hook['command'] = old
                hook['timeout'] = 71
                hook['custom'] = 'keep'
                if name == '.codex/hooks.json':
                    hook['commandWindows'] = 'custom-windows'
                old_commands.append(old)
            manifest['hooks'][name] = sorted(set(old_commands))
            self.write(name, json.dumps(data))
        self.write(install.MANIFEST, json.dumps(manifest))
        self.commit()
        self.run_install()
        for name in install.HOOK_FILES:
            actual = json.loads((self.target / name).read_text())
            wanted = json.loads((self.template / name).read_text())
            self.assertEqual([(e, m, h['command']) for e, m, h in entries(actual, name == '.cursor/hooks.json')],
                             [(e, m, h['command']) for e, m, h in entries(wanted, name == '.cursor/hooks.json')])
            for _, _, hook in entries(actual, name == '.cursor/hooks.json'):
                self.assertEqual(hook['timeout'], 71)
                self.assertEqual(hook['custom'], 'keep')
                if name == '.codex/hooks.json':
                    self.assertEqual(hook['commandWindows'], 'custom-windows')
        self.commit()
        before = self.snapshot()
        self.run_install('--check')
        self.assertEqual(self.snapshot(), before)
        self.assertIn('up to date', self.run_install())

    def test_migration_requires_ownership_and_matching_registration(self):  # R5
        for name in install.HOOK_FILES:
            flat = name == '.cursor/hooks.json'
            desired = config('cursor' if flat else 'codex' if 'codex' in name else 'claude')
            event, matcher, new = next(entries(desired, flat))
            suffix = new['command'].split('exec sh "$b" ', 1)[1]
            old_command = 'python3 ' + suffix.replace('$r/', '$(git rev-parse --show-toplevel)/')
            if flat:
                old_command = old_command.replace('"', '')
            old = {'command': old_command, 'timeout': 71, 'custom': 'keep'}
            group = {**old, **({'matcher': matcher} if matcher else {})} if flat else {
                **({'matcher': matcher} if matcher else {}), 'hooks': [old]}
            adopter = {'hooks': {event: [group]}}
            unowned = install.merge_hooks(adopter, desired, [], flat)
            self.assertTrue(any(h['command'] == old_command for _, _, h in entries(unowned, flat)))
            migrated = install.merge_hooks(adopter, desired, [old_command], flat)
            replacement = next(h for e, m, h in entries(migrated, flat)
                               if e == event and m == matcher and h['command'] == new['command'])
            self.assertEqual(replacement['custom'], 'keep')
            if 'commandWindows' in new:
                self.assertEqual(replacement['commandWindows'], new['commandWindows'])
            other = {'hooks': {'adopter-event': [group]}}
            merged = install.merge_hooks(other, desired, [old_command], flat)
            self.assertFalse(any(h.get('custom') == 'keep' for e, _, h in entries(merged, flat)
                                 if e == event))
            self.assertIsNone(install.posix_hook_replacement(old_command + ' # custom'))

    @unittest.skipUnless(POSIX, 'native POSIX runtime required')
    def test_installed_configured_hook_executes(self):  # R5
        self.installed()
        data = json.loads((self.target / '.codex/hooks.json').read_text())
        command = next(h['command'] for e, _, h in entries(data)
                       if e == 'SessionStart' and 'lifecycle.py' in h['command'])
        env = {k: v for k, v in os.environ.items() if not k.startswith(('GIT_', 'OKF_', 'CLAUDE_'))}
        result = subprocess.run([shutil.which('sh'), '-c', command], cwd=self.target, env=env,
                                input=json.dumps({'hook_event_name': 'SessionStart', 'cwd': str(self.target)}),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Lifecycle router', result.stdout)


class DocumentationTests(unittest.TestCase):
    def test_linux_setup_contract(self):  # R6
        body = (ROOT / '.ai/docs/install-and-upgrade.md').read_text()
        for text in ('POSIX', 'Python 3.9+', '/usr/local/bin/python3', '/usr/bin/python3',
                     '$HOME/.local/bin/python3', 'test_posix_hooks.py', 'restart', 'Git'):
            self.assertIn(text, body)


if __name__ == '__main__':
    if not POSIX:
        sys.exit('Native POSIX runtime required; run this acceptance suite on Linux.')
    unittest.main()
