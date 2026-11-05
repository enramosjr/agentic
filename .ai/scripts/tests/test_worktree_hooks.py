"""Public hook regression checks using conflicting, linked Git worktrees."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest

import disk_tmp  # noqa: F401

SCRIPTS = Path(__file__).resolve().parents[1]


def quote_directory(value: str) -> str:
    return '"' + value + '"' if os.name == 'nt' else shlex.quote(value)


class DriveRelativeSpellingTests(unittest.TestCase):
    def test_windows_drive_relative_spelling_is_rejected_before_joining(self):
        from unittest import mock
        sys.path.insert(0, str(SCRIPTS))
        import pr_hook
        with mock.patch.object(pr_hook.os, 'name', 'nt'):
            for value in ('C:', 'C:.', 'C:relative', 'd:relative\\child'):
                with self.subTest(value=value), self.assertRaisesRegex(pr_hook.RoutingError, 'drive-relative'):
                    pr_hook.check_directory_spelling(value, 'test directory')
            for value in ('.', '..', 'relative', r'C:\fully\qualified', r'\\server\share\path'):
                pr_hook.check_directory_spelling(value, 'test directory')


class WorktreeHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(disk_tmp.remove_tree, self.base)
        self.outer, self.target = self.base / 'outer', self.base / 'target'
        self.outer.mkdir()
        self.env = dict(os.environ)
        for key in ('CLAUDE_PROJECT_DIR', 'LIFECYCLE_GUARD', 'OKF_AUTONOMOUS',
                    'OKF_HANDOFF_REQUEST', 'OKF_PROGRESS_REQUEST', 'GIT_DIR', 'GIT_WORK_TREE'):
            self.env.pop(key, None)
        self.env['GIT_CEILING_DIRECTORIES'] = str(self.base)
        self.git(self.outer, 'init', '-q')
        shutil.copytree(SCRIPTS, self.outer / '.ai/scripts',
                        ignore=shutil.ignore_patterns('tests', '__pycache__'))
        (self.outer / 'app.py').write_text("print('fixture')\n")
        self.git(self.outer, 'add', '-A')
        self.git(self.outer, 'commit', '-qm', 'fixture')
        self.git(self.outer, 'worktree', 'add', '-qb', 'target', str(self.target))

    def git(self, root: Path, *args: str) -> str:
        result = subprocess.run(['git', '-C', str(root), '-c', 'user.email=test@example.com',
                                 '-c', 'user.name=Test', *args], env=self.env,
                                capture_output=True, text=True, check=True, timeout=30)
        return result.stdout.strip()

    def cli(self, root: Path, *args: str) -> None:
        result = subprocess.run([sys.executable, str(self.outer / '.ai/scripts/lifecycle.py'), *args],
                                cwd=root, env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def ready(self, root: Path) -> Path:
        self.cli(root, 'tier', 'L1', '--reason', 'disposable routing fixture')
        self.cli(root, 'stage', 'intent', '--note', 'Route operation; check hook decision; fixture only')
        self.cli(root, 'stage', 'plan', '--note', 'Exercise public hook against linked worktrees')
        self.cli(root, 'retrospect', '--no-new-lessons', 'Disposable routing fixture adds no project lesson.')
        self.cli(root, 'stage', 'verify', '--note', 'Fixture setup completed')
        record, = (root / 'knowledge/history/lifecycle').glob('*.json')
        self.git(root, 'add', str(record))
        return record

    def payload(self, command: str = 'git commit -m fixture', **tool_input: object) -> dict:
        return {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
                'cwd': str(self.outer), 'tool_input': {'command': command, **tool_input}}

    def hook(self, data: dict, **env: str) -> str:
        result = subprocess.run([sys.executable, str(self.outer / '.ai/scripts/lifecycle.py'), 'hook'],
                                input=json.dumps(data), cwd=self.outer, env={**self.env, **env},
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def decision(self, data: dict, denied: bool, **env: str) -> str:
        output = self.hook(data, **env)
        self.assertEqual('"deny"' in output, denied, output)
        return output

    def test_tool_workdir_overrides_session_project(self) -> None:  # R1
        self.ready(self.target)
        self.decision(self.payload(workdir=str(self.target)), False, CLAUDE_PROJECT_DIR=str(self.outer))
        self.decision(self.payload(workdir=str(self.outer)), True, CLAUDE_PROJECT_DIR=str(self.target))
        self.decision(self.payload(f'git -C {self.target} commit -m fixture'), False,
                      CLAUDE_PROJECT_DIR=str(self.outer))
        self.decision(self.payload('git -C ../target commit -m fixture'), False)
        self.decision(self.payload(f"git -c user.name=Fixture -C .. -C target commit -m ';'"), False)
        spaced = self.base / 'target with spaces'
        self.git(self.outer, 'worktree', 'move', str(self.target), str(spaced))
        self.decision(self.payload(f'git -C "{spaced}" commit -m fixture'), False)

    def test_cwd_precedence_and_legacy_fallbacks(self) -> None:  # R2
        self.ready(self.target)
        data = self.payload()
        data['cwd'] = str(self.target)
        data['workspace_roots'] = [str(self.outer)]
        self.decision(data, False, CLAUDE_PROJECT_DIR=str(self.outer))
        data.pop('cwd')
        self.decision(data, False, CLAUDE_PROJECT_DIR=str(self.target))
        data['workspace_roots'] = [str(self.target)]
        self.decision(data, False)
        data.pop('workspace_roots')
        self.decision(data, True)

    def test_relative_workdir_and_edit_paths(self) -> None:  # R3
        self.ready(self.target)
        self.decision(self.payload(workdir='../target'), False)
        nested = self.outer / 'nested'
        nested.mkdir()
        edit = {'hook_event_name': 'PreToolUse', 'tool_name': 'Edit', 'cwd': str(nested),
                'tool_input': {'file_path': '../app.py'}}
        self.decision(edit, True)
        edit['tool_input']['workdir'] = '../../target'
        edit['tool_input']['file_path'] = 'app.py'
        self.decision(edit, False)

    def test_commit_pr_and_edit_use_target_state(self) -> None:  # R4
        self.ready(self.target)
        for ready, unready in [(self.target, self.outer), (self.outer, self.target)]:
            if ready == self.outer:
                self.ready(self.outer)
                self.git(self.target, 'switch', '-qc', 'target-unready')
            for tool, args in [('Bash', {'command': 'git commit -m fixture'}),
                               ('Shell', {'command': 'gh pr create --title fixture'}),
                               ('Edit', {'file_path': 'app.py'})]:
                for target, denied in [(ready, False), (unready, True)]:
                    with self.subTest(tool=tool, target=target, ready=ready):
                        data = self.payload()
                        data.update(tool_name=tool, tool_input={**args, 'workdir': str(target)})
                        self.decision(data, denied, CLAUDE_PROJECT_DIR=str(unready if target == ready else ready))

    def test_invalid_explicit_workdir_denies_guarded_operation(self) -> None:  # R5
        self.ready(self.outer)
        plain = self.base / 'plain'
        plain.mkdir()
        for workdir in ['', '  ', None, 4, [], str(self.base / 'missing'), str(self.outer / 'app.py'), str(plain)]:
            for tool, args in [('Bash', {'command': 'git commit -m fixture'}),
                               ('Shell', {'command': 'gh pr create'}), ('Edit', {'file_path': 'app.py'})]:
                with self.subTest(workdir=workdir, tool=tool):
                    data = self.payload()
                    data.update(tool_name=tool, tool_input={**args, 'workdir': workdir})
                    self.assertIn('workdir', self.decision(data, True))
        self.decision(self.payload('python3 --version', workdir='missing'), False)
        for directory in (str(self.base / 'missing'), str(plain), "''"):
            self.assertIn('git -C', self.decision(self.payload(f'git -C {directory} commit -m fixture'), True))
        self.assertIn('single command', self.decision(self.payload(f'git -C {self.outer} commit -m fixture; true'), True))
        self.assertIn('unsupported', self.decision(self.payload(f'git --unknown -C {self.outer} commit -m fixture'), True))

    def test_session_start_preserves_project_context(self) -> None:  # R6
        self.ready(self.target)
        data = {'hook_event_name': 'SessionStart', 'cwd': str(self.target),
                'workspace_roots': [str(self.outer)], 'tool_input': {'workdir': str(self.target)}}
        self.assertIn('No tier declared', self.hook(data, CLAUDE_PROJECT_DIR=str(self.outer)))
        self.assertIn('Active: tier L1', self.hook(data, CLAUDE_PROJECT_DIR=str(self.target)))
        self.assertIn('No tier declared', self.hook(data))
        plain = self.base / 'plain'
        plain.mkdir()
        data.update(cwd=str(plain), workspace_roots=[])
        self.assertEqual(self.hook(data), '')

    def test_outer_hook_entrypoint_routes_to_target_worktree(self) -> None:  # R7
        record = self.ready(self.target)
        # This is the live Codex adapter shape: workdir is omitted, git -C is retained.
        data = self.payload(f'git -C {self.target} commit -m fixture')
        self.git(self.target, 'reset', '-q', 'HEAD', '--', str(record))
        self.assertIn('audit record', self.decision(data, True, CLAUDE_PROJECT_DIR=str(self.outer)))
        self.git(self.target, 'add', str(record))
        self.decision(data, False, CLAUDE_PROJECT_DIR=str(self.outer))
        self.git(self.target, 'commit', '-qm', 'verified disposable audit')
        self.assertIn(record.relative_to(self.target).as_posix(), self.git(self.target, 'show', '--format=', '--name-only', 'HEAD'))
        audit = json.loads(self.git(self.target, 'show', f'HEAD:{record.relative_to(self.target).as_posix()}'))
        self.assertIn('verify', audit['stages'])
        cursor = {'hook_event_name': 'beforeShellExecution', 'cursor_version': 'test',
                  'cwd': str(self.target), 'command': 'gh pr create'}
        self.assertEqual(json.loads(self.hook(cursor, CLAUDE_PROJECT_DIR=str(self.outer)))['permission'], 'allow')
        cursor['cwd'] = str(self.outer)
        self.assertEqual(json.loads(self.hook(cursor, CLAUDE_PROJECT_DIR=str(self.target)))['permission'], 'deny')

    def test_pr_prefix_uses_target_lifecycle(self) -> None:
        self.ready(self.target)
        for tool in ('Bash', 'Shell'):
            for verb in ('create', 'ready'):
                data = self.payload(f'cd {quote_directory(str(self.target))} && gh pr {verb}')
                data['tool_name'] = tool
                self.decision(data, False, CLAUDE_PROJECT_DIR=str(self.outer))
        self.ready(self.outer)
        self.git(self.target, 'switch', '-qc', 'unready-pr-target')
        output = self.decision(self.payload(f'cd {self.target} && gh pr create'), True)
        self.assertIn(str(self.target), json.loads(output)['hookSpecificOutput']['permissionDecisionReason'])

    def test_quoted_pr_examples_are_not_shipping_commands(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        import review_guard
        commands = [
            "python3 .ai/scripts/repo.py grep 'gh pr create' source.py",
            "printf '%s %s %s' 'gh' 'pr' 'create'",
            "printf '%s' 'cd nowhere && gh pr ready'",
            "printf '%s' 'gh pr create; gh pr ready'",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.decision(self.payload(command), False)
                self.assertFalse(review_guard.command_mutates(command))
        self.decision(self.payload("gh pr create --title 'gh pr ready'"), True)

    def test_pr_literal_paths_match_cli_execution_directory(self) -> None:
        self.ready(self.target)
        spaced = self.base / 'target with spaces'
        self.git(self.outer, 'worktree', 'move', str(self.target), str(spaced))
        executable = self.base / 'bin' / ('gh.cmd' if os.name == 'nt' else 'gh')
        executable.parent.mkdir()
        probe = 'import os\nfrom pathlib import Path\nPath(os.environ["PR_PROBE"]).write_text(os.getcwd())\n'
        if os.name == 'nt':
            script = executable.with_suffix('.py')
            script.write_text(probe)
            executable.write_text(f'@"{sys.executable}" "{script}" %*\n')
        else:
            executable.write_text('#!' + sys.executable + '\n' + probe)
        executable.chmod(0o755)
        result_path = self.base / 'execution-directory'
        env = {**self.env, 'PATH': str(executable.parent) + os.pathsep + self.env['PATH'],
               'PR_PROBE': str(result_path)}
        for directory, workdir in [(str(spaced), None), ('../target with spaces', None),
                                   ('../target with spaces', str(self.outer)), ('.', str(spaced))]:
            with self.subTest(directory=directory, workdir=workdir):
                command = f'cd {quote_directory(directory)} && gh pr create --title "literal ; && text"'
                payload = self.payload(command, **({'workdir': workdir} if workdir else {}))
                self.decision(payload, False)
                subprocess.run(command, shell=True, cwd=workdir or self.outer, env=env,
                               capture_output=True, check=True, timeout=10)
                self.assertEqual(result_path.read_text(), str(spaced))
        self.decision(self.payload('gh pr ready', workdir=str(spaced)), False)

    def test_pr_invalid_routing_denies_without_record_changes(self) -> None:
        self.ready(self.outer)
        plain = self.base / 'not-git'
        plain.mkdir()
        commands = [f'cd {directory} && gh pr create' for directory in
                    ("''", str(self.base / 'missing'), str(self.outer / 'app.py'), str(plain),
                     '"$HOME"', '$(pwd)', '`pwd`')]
        commands += [f'cd {self.outer} {operator} gh pr create' for operator in ('||', '|', '&')]
        if os.name == 'nt':
            # Literal native directory prefixes are supported. Extra commands
            # between the directory change and PR remain unsupported routing.
            commands += [f'cd {self.outer} {operator} git status {operator} gh pr create'
                         for operator in (';', '\n')]
        else:
            commands += [f'cd {self.outer} {operator} gh pr create' for operator in (';', '\n')]
        commands += [f'cd {self.outer} && gh pr create && true',
                     f'true && cd {self.outer} && gh pr ready',
                     f'cd {self.outer} && cd . && gh pr create',
                     f'cd {self.outer} && gh pr create > output']
        before = self.git(self.outer, 'status', '--porcelain')
        for command in commands:
            with self.subTest(command=command):
                self.assertIn('routing', self.decision(self.payload(command), True))
        self.assertEqual(self.git(self.outer, 'status', '--porcelain'), before)

    def test_literal_paths_keep_trailing_separator_and_apostrophe(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        import pr_hook
        self.ready(self.target)
        selected = self.base / "target's directory"
        self.git(self.outer, 'worktree', 'move', str(self.target), str(selected))
        for directory in (str(selected), str(selected) + os.sep):
            literals = [quote_directory(directory)]
            if os.name == 'nt':
                literals.append("'" + directory.replace("'", "''") + "'")
            for literal in literals:
                with self.subTest(literal=literal):
                    command = f'cd {literal} && gh pr create'
                    invocation = pr_hook.recognize(command)
                    self.assertIsNotNone(invocation)
                    self.assertEqual(invocation.directory, directory)
                    self.decision(self.payload(command), False)

    def test_git_target_dynamic_spelling_cannot_select_a_literal_dollar_path(self) -> None:
        self.ready(self.target)
        selected = self.base / '$selected'
        self.git(self.outer, 'worktree', 'move', str(self.target), str(selected))
        self.decision(self.payload(f'git -C "{selected}" commit -m fixture'), True)
        self.decision(self.payload(f"git -C '{selected}' commit -m fixture"), False)

    @unittest.skipUnless(os.name == 'nt', 'native short-name namespace contract')
    def test_native_short_name_alias_keeps_actual_worktree_shipping_gates(self) -> None:
        import ctypes
        from ctypes import wintypes
        renamed = self.base / 'my-dir long worktree'
        self.git(self.outer, 'worktree', 'move', str(self.target), str(renamed))
        self.target = renamed
        self.ready(self.target)
        alias = self.base / 'LK-DIR~1'
        disk_tmp.directory_link(alias, self.target)
        self.assertEqual(alias.resolve(), self.target.resolve())
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        kernel.GetShortPathNameW.restype = wintypes.DWORD
        size = kernel.GetShortPathNameW(str(self.target), None, 0)
        self.assertGreater(size, 0, ctypes.get_last_error())
        buffer = ctypes.create_unicode_buffer(size)
        self.assertGreater(kernel.GetShortPathNameW(str(self.target), buffer, size), 0)
        spellings = {alias, Path(buffer.value)}
        # Volumes may disable creation of new DOS aliases. The junction still
        # exercises an unquoted short-name component; retain the API's real path.
        def literal(path):
            value = str(path)
            return "'" + value.replace("'", "''") + "'" if any(c.isspace() for c in value) else value
        for selected in spellings:
            with self.subTest(selected=str(selected)):
                actual = self.git(selected, 'rev-parse', '--show-toplevel')
                self.assertEqual(Path(actual).resolve(), self.target.resolve())
                self.decision(self.payload(f'git -C {literal(selected)} commit -m fixture'), False)
                self.decision(self.payload(f'cd {literal(selected)} && gh pr create'), False)
        self.git(self.target, 'switch', '-qc', 'short-alias-unready')
        for selected in spellings:
            self.decision(self.payload(f'git -C {literal(selected)} commit -m fixture'), True)
            self.decision(self.payload(f'cd {literal(selected)} && gh pr create'), True)

    def test_native_git_executable_spelling_keeps_commit_gates(self) -> None:
        self.ready(self.target)
        executable = shutil.which('git')
        commands = ([f"& '{executable}' commit -m fixture", 'git.exe commit -m fixture']
                    if os.name == 'nt' else [f'{shlex.quote(executable)} commit -m fixture'])
        for command in commands:
            with self.subTest(command=command):
                self.decision(self.payload(command, workdir=str(self.target)), False)
                self.decision(self.payload(command, workdir=str(self.outer)), True)

    def test_native_pr_executable_spelling_keeps_shipping_gates(self) -> None:
        self.ready(self.target)
        commands = ([r'& "C:\Program Files\GitHub CLI\gh.exe" pr create', 'gh.exe pr ready']
                    if os.name == 'nt' else ['gh pr create', 'gh pr ready'])
        for command in commands:
            with self.subTest(command=command):
                self.decision(self.payload(command, workdir=str(self.target)), False)
                self.decision(self.payload(command, workdir=str(self.outer)), True)

    def test_drive_relative_selectors_cannot_authorize_pr_commit_or_edit(self) -> None:
        if os.name != 'nt':
            # A colon is a literal filename on POSIX, never a drive selector.
            self.ready(self.target)
            disk_tmp.directory_link(self.outer / 'C:relative', self.target)
            self.decision(self.payload('cd C:relative && gh pr create'), False)
            return
        self.ready(self.outer)
        relative = self.outer.drive + '.'
        for command, inputs in ((f'cd {relative} && gh pr create', {}),
                                ('gh pr ready', {'workdir': relative}),
                                (f'git -C {relative} commit -m fixture', {}),
                                ('git commit -m fixture', {'workdir': relative})):
            with self.subTest(command=command, inputs=inputs):
                self.assertIn('drive-relative', self.decision(self.payload(command, **inputs), True))
        edit = {'hook_event_name': 'PreToolUse', 'tool_name': 'Edit', 'cwd': str(self.outer),
                'tool_input': {'file_path': 'app.py', 'workdir': relative}}
        self.assertIn('drive-relative', self.decision(edit, True))

    def test_pr_review_checks_use_selected_target(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        import lifecycle
        import review_guard as guard
        self.ready(self.target)
        self.ready(self.outer)
        command = f'cd {self.target} && gh pr create'
        data = self.payload(command)
        for root in (self.outer, self.target):
            guard.observe_session(root, 'claude', {'session_id': 'parent', 'cwd': str(root),
                                                  'hook_event_name': 'SessionStart'})
            guard.enable(root, 'fixture', 'claude', 'parent', 'docs/review.md')
            guard.start(root, 'fixture', 'claude', 'parent', 'child', 'reviewer', {}, [])
            before = guard.read(root)
            output = self.decision(data, root == self.target)
            if root == self.target:
                self.assertIn('active review', output)
            self.assertEqual(guard.read(root), before)
            with guard.transaction(root) as value:
                value['interval']['phase'] = 'abandoned'
                value['request']['phase'] = 'abandoned'
        # Required-but-missing native evidence must not borrow legacy readiness.
        state = lifecycle.load(self.target)
        state['mechanical_review'] = {'required': True}
        with guard.producer(self.target):
            lifecycle.save(self.target, state)
        before = lifecycle.load(self.target)
        self.decision(data, True)
        self.assertEqual(lifecycle.load(self.target), before)
        self.decision(self.payload('gh pr create', workdir=str(self.outer)), False)

    def test_pr_directory_owns_physical_guard_namespace(self) -> None:
        from unittest import mock
        sys.path.insert(0, str(SCRIPTS))
        import review_guard as guard
        data = self.payload(f'cd {self.target} && gh pr create')
        with mock.patch.dict(os.environ, {'GIT_DIR': str(self.outer / '.git'),
                                         'GIT_WORK_TREE': str(self.outer)}):
            self.assertEqual(guard.operation_roots(data), [self.target])

    def test_pr_ambiguous_shell_directories_deny(self) -> None:
        self.ready(self.target)
        nested = self.target / 'nested'
        nested.mkdir()
        link = self.outer / 'link'
        disk_tmp.directory_link(link, nested)
        directory = str(link / '..')
        pwd = 'cd' if os.name == 'nt' else 'pwd -P'
        result = subprocess.run(f'cd {quote_directory(directory)} && {pwd}', shell=True,
                                cwd=self.outer, env=self.env, capture_output=True,
                                text=True, check=True, timeout=10)
        self.assertEqual(result.stdout.strip(), str(self.outer))
        with self.subTest(ambiguity='symlink-parent'):
            self.assertIn('routing', self.decision(self.payload(f'cd {directory} && gh pr create'), True))

        selected = self.outer / 'selected'
        disk_tmp.directory_link(selected, self.target)
        search = self.base / 'cdpath'
        alternate = search / 'selected'
        alternate.mkdir(parents=True)
        self.git(alternate, 'init', '-q')
        environment = {**self.env, 'CDPATH': str(search)}
        result = subprocess.run(f'cd selected && {pwd}', shell=True, cwd=self.outer,
                                env=environment, capture_output=True, text=True,
                                check=True, timeout=10)
        # cmd does not implement CDPATH; its native relative cd uses the local
        # directory alias. The hook still refuses inherited ambiguous selectors.
        self.assertEqual(result.stdout.splitlines()[-1], str(selected if os.name == 'nt' else alternate))
        with self.subTest(ambiguity='CDPATH'):
            self.assertIn('routing', self.decision(self.payload('cd selected && gh pr ready'),
                                                  True, CDPATH=str(search)))
        # Tool-specific environment must not escape the same routing check.
        with self.subTest(ambiguity='tool-CDPATH'):
            self.assertIn('routing', self.decision(self.payload('cd selected && gh pr ready',
                                                  env={'CDPATH': str(search)}), True))
        # A valid inherited logical PWD can also change the meaning of '..'.
        alias = nested / 'logical-outer'
        disk_tmp.directory_link(alias, self.outer)
        with self.subTest(ambiguity='logical-PWD'):
            self.assertIn('routing', self.decision(self.payload('cd .. && gh pr create'),
                                                  True, PWD=str(alias)))


if __name__ == '__main__':
    unittest.main()
