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


class WorktreeHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.base)
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
                data = self.payload(f'cd {shlex.quote(str(self.target))} && gh pr {verb}')
                data['tool_name'] = tool
                self.decision(data, False, CLAUDE_PROJECT_DIR=str(self.outer))
        self.ready(self.outer)
        self.git(self.target, 'switch', '-qc', 'unready-pr-target')
        output = self.decision(self.payload(f'cd {self.target} && gh pr create'), True)
        self.assertIn(str(self.target), output)

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
        executable = self.base / 'bin' / 'gh'
        executable.parent.mkdir()
        executable.write_text('#!' + sys.executable + '\nimport os\nfrom pathlib import Path\n'
                              'Path(os.environ["PR_PROBE"]).write_text(os.getcwd())\n')
        executable.chmod(0o755)
        result_path = self.base / 'execution-directory'
        env = {**self.env, 'PATH': str(executable.parent) + os.pathsep + self.env['PATH'],
               'PR_PROBE': str(result_path)}
        for directory, workdir in [(str(spaced), None), ('../target with spaces', None),
                                   ('../target with spaces', str(self.outer)), ('.', str(spaced))]:
            with self.subTest(directory=directory, workdir=workdir):
                command = f'cd {shlex.quote(directory)} && gh pr create --title "literal ; && text"'
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
        commands += [f'cd {self.outer} {operator} gh pr create' for operator in (';', '||', '|', '&', '\n')]
        commands += [f'cd {self.outer} && gh pr create && true',
                     f'true && cd {self.outer} && gh pr ready',
                     f'cd {self.outer} && cd . && gh pr create',
                     f'cd {self.outer} && gh pr create > output']
        before = self.git(self.outer, 'status', '--porcelain')
        for command in commands:
            with self.subTest(command=command):
                self.assertIn('routing', self.decision(self.payload(command), True))
        self.assertEqual(self.git(self.outer, 'status', '--porcelain'), before)

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
        link.symlink_to(nested, target_is_directory=True)
        directory = str(link / '..')
        result = subprocess.run(f'cd {shlex.quote(directory)} && pwd -P', shell=True,
                                cwd=self.outer, env=self.env, capture_output=True,
                                text=True, check=True, timeout=10)
        self.assertEqual(result.stdout.strip(), str(self.outer))
        with self.subTest(ambiguity='symlink-parent'):
            self.assertIn('routing', self.decision(self.payload(f'cd {directory} && gh pr create'), True))

        selected = self.outer / 'selected'
        selected.symlink_to(self.target, target_is_directory=True)
        search = self.base / 'cdpath'
        alternate = search / 'selected'
        alternate.mkdir(parents=True)
        self.git(alternate, 'init', '-q')
        environment = {**self.env, 'CDPATH': str(search)}
        result = subprocess.run('cd selected && pwd -P', shell=True, cwd=self.outer,
                                env=environment, capture_output=True, text=True,
                                check=True, timeout=10)
        self.assertEqual(result.stdout.splitlines()[-1], str(alternate))
        with self.subTest(ambiguity='CDPATH'):
            self.assertIn('routing', self.decision(self.payload('cd selected && gh pr ready'),
                                                  True, CDPATH=str(search)))
        # Tool-specific environment must not escape the same routing check.
        with self.subTest(ambiguity='tool-CDPATH'):
            self.assertIn('routing', self.decision(self.payload('cd selected && gh pr ready',
                                                  env={'CDPATH': str(search)}), True))
        # A valid inherited logical PWD can also change the meaning of '..'.
        alias = nested / 'logical-outer'
        alias.symlink_to(self.outer, target_is_directory=True)
        with self.subTest(ambiguity='logical-PWD'):
            self.assertIn('routing', self.decision(self.payload('cd .. && gh pr create'),
                                                  True, PWD=str(alias)))


if __name__ == '__main__':
    unittest.main()
