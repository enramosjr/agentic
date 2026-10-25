"""Public hook regression checks using conflicting, linked Git worktrees."""
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


if __name__ == '__main__':
    unittest.main()
