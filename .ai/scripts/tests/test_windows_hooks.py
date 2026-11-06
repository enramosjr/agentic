"""Native Windows Codex hook launch and policy regressions (R1-R4)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import disk_tmp  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / '.ai/scripts'


class HookConfigurationTests(unittest.TestCase):
    def test_every_codex_handler_has_windows_override(self):  # R1
        data = json.loads((ROOT / '.codex/hooks.json').read_text())
        for groups in data['hooks'].values():
            for group in groups:
                for hook in group['hooks']:
                    self.assertIn('commandWindows', hook, hook['command'])
                    self.assertIn('codex_hook.ps1', hook['commandWindows'])
                    self.assertTrue(hook['command'].startswith('python3 '))

    def test_windows_setup_is_documented(self):  # R4
        body = (ROOT / '.ai/docs/install-and-upgrade.md').read_text()
        for term in ('Native Windows', 'Python 3.9+', 'Git for Windows',
                     'commandWindows', 'test_windows_hooks.py', '/hooks'):
            self.assertIn(term, body)


@unittest.skipUnless(os.name == 'nt', 'native Windows shell required')
class NativeWindowsHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='codex hooks ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project with spaces'
        self.root.mkdir()
        shutil.copytree(SCRIPTS, self.root / '.ai/scripts',
                        ignore=shutil.ignore_patterns('tests', '__pycache__'))
        (self.root / '.agentic.json').write_text('{"repository_kind":"framework"}')
        (self.root / 'source.py').write_text('print("fixture")\n')
        self.env = dict(os.environ)
        for key in list(self.env):
            if key.startswith('GIT_') or key in ('CLAUDE_PROJECT_DIR', 'LIFECYCLE_GUARD',
                                               'OKF_AUTONOMOUS', 'OKF_SHELL_GUARD'):
                self.env.pop(key)
        subprocess.run(['git', 'init', '-q', str(self.root)], env=self.env, check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], env=self.env, check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.com', 'commit', '-qm', 'fixture'],
                       env=self.env, check=True)
        # Reproduce the desktop PATH: installed tools are absent, not uninstalled.
        system = Path(os.environ['SystemRoot']) / 'System32'
        self.env['PATH'] = str(system) + ';' + str(system / 'WindowsPowerShell/v1.0')
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'
        self.env['PYTHONHOME'] = sys.base_prefix
        self.command_prefix = ''

    def command(self, script):
        config = json.loads((ROOT / '.codex/hooks.json').read_text())
        for groups in config['hooks'].values():
            for group in groups:
                for hook in group['hooks']:
                    if f'/{script}' in hook['command']:
                        self.assertIn('commandWindows', hook)
                        return hook['commandWindows']
        self.fail(f'no configured hook for {script}')

    def run_hook(self, script, data, cwd=None):
        data.setdefault('cwd', str(self.root))
        command = self.command(script).replace('-Command "', '-Command "' + self.command_prefix, 1)
        return subprocess.run(command, shell=True, executable=os.environ['COMSPEC'],
                              cwd=cwd or self.root, env=self.env, input=json.dumps(data, ensure_ascii=False),
                              capture_output=True, text=True, encoding='utf-8', timeout=30)

    def test_router_and_policies_from_root_and_nested_directory(self):  # R1, R2
        nested = self.root / 'nested with spaces'
        nested.mkdir()
        for cwd in (self.root, nested):
            with self.subTest(cwd=cwd):
                result = self.run_hook('lifecycle.py', {'hook_event_name': 'SessionStart'}, cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('Lifecycle router', json.loads(result.stdout)
                              ['hookSpecificOutput']['additionalContext'])
                result = self.run_hook('shell_guard.py', {'hook_event_name': 'PreToolUse',
                    'tool_name': 'Bash', 'tool_input': {'command': 'cat source.py'}}, cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']
                                 ['permissionDecision'], 'deny')
                result = self.run_hook('lifecycle.py', {'hook_event_name': 'PreToolUse',
                    'tool_name': 'Edit', 'tool_input': {'file_path': str(self.root / 'source.py')}}, cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']
                                 ['permissionDecision'], 'deny')
                result = self.run_hook('review_native.py', {'hook_event_name': 'PostToolUse',
                    'session_id': 'windows-fixture', 'tool_name': 'Bash',
                    'tool_input': {'command': 'git status'}}, cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                for script in ('shell_guard.py', 'lifecycle.py'):
                    result = self.run_hook(script, {'hook_event_name': 'PreToolUse',
                        'tool_name': 'Bash', 'tool_input': {'command': 'git status'}}, cwd)
                    self.assertEqual((result.returncode, result.stdout), (0, ''), result.stderr)

    def test_preserves_json_arguments_and_failure_exit(self):  # R1
        probe = self.root / '.ai/scripts/review_native.py'
        probe.write_text('import json,sys\nprint(json.dumps([sys.argv[1:],json.load(sys.stdin)],ensure_ascii=False))\n'
                         'print("probe stderr \\u2603",file=sys.stderr)\nsys.exit(7)\n')
        data = {'hook_event_name': 'PostToolUse', 'value': 'quotes " and unicode \u2603'}
        result = self.run_hook('review_native.py', data)
        self.assertEqual(result.returncode, 7, result.stderr)
        arguments, received = json.loads(result.stdout)
        self.assertEqual(arguments, ['hook', '--adapter', 'codex'])
        self.assertEqual(received, data)
        self.assertIn('probe stderr \u2603', result.stderr)

    def test_missing_launcher_fails_closed(self):  # R1
        (self.root / '.ai/scripts/codex_hook.ps1').unlink()
        result = self.run_hook('lifecycle.py', {'hook_event_name': 'SessionStart'})
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn('AGENTIC Windows hook', result.stderr)

    def test_custom_python_home_runs_without_python_on_path(self):  # R1
        self.env['LOCALAPPDATA'] = str(self.root / 'missing local')
        result = self.run_hook('lifecycle.py', {'hook_event_name': 'SessionStart'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Lifecycle router', json.loads(result.stdout)['hookSpecificOutput']['additionalContext'])

    def test_missing_tools_are_actionable(self):  # R1
        self.env.pop('PYTHONHOME', None)
        self.env['LOCALAPPDATA'] = str(self.root / 'missing local')
        self.env['PROGRAMFILES'] = str(self.root / 'missing programs')
        self.env['PROGRAMFILES(X86)'] = str(self.root / 'missing x86')
        self.env['USERPROFILE'] = str(self.root / 'missing user')
        # PowerShell restores ProgramFiles at startup; hosted runners can also
        # have a system-wide py.exe. Hide that file without changing SystemRoot,
        # which .NET still needs to load assemblies while the hook runs.
        self.command_prefix = ("$env:ProgramFiles='C:\\missing programs'; "
                               "${env:ProgramFiles(x86)}='C:\\missing x86'; "
                               "function Get-Item { param($Path,$LiteralPath,$ErrorAction) "
                               "if ($Path -eq (Join-Path $env:SystemRoot 'py.exe')) { return }; "
                               "Microsoft.PowerShell.Management\\Get-Item @PSBoundParameters }; ")
        # Keep only Git available while proving that missing Python fails closed.
        system_path = self.env['PATH']
        self.env['PATH'] += ';' + str(Path(shutil.which('git')).parent)
        result = self.run_hook('lifecycle.py', {'hook_event_name': 'SessionStart'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Python 3.9+', result.stderr)
        self.env['PATH'] = system_path
        result = self.run_hook('lifecycle.py', {'hook_event_name': 'SessionStart'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Git for Windows', result.stderr)


if __name__ == '__main__':
    unittest.main()
