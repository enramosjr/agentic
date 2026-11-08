"""Framework source hygiene and unchanged adopter routing through real entry points."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import disk_tmp
import framework_policy
import review_native
from test_install import InstallerCase, tree_state


class FrameworkPolicyTests(unittest.TestCase):
    def test_task_producers_refuse_framework_subdirectory(self):
        nested = self.root / '.ai'
        nested.mkdir()
        with self.assertRaises(framework_policy.PolicyError):
            framework_policy.adopter_task(nested)
        self.assertEqual(framework_policy.adopter_task(nested, exact_target=True), nested)
        import argparse
        import okf
        with self.assertRaises(okf.OkfError):
            okf.cmd_init(nested / 'knowledge', argparse.Namespace(autonomous=False))
        self.assertFalse((nested / 'knowledge').exists())

    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(disk_tmp.remove_tree, self.root)
        self.git('init', '-q')
        self.write('README.md', '# Product reference\n')
        self.marker(['README.md'])
        self.git('add', '-A')
        self.git('commit', '-qm', 'product source')
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ('LIFECYCLE_GUARD', 'OKF_AUTONOMOUS', 'REPO_ROOT')}
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=test',
                               '-c', 'user.email=test@test', *args], check=True,
                              capture_output=True, text=True).stdout

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def marker(self, documents):
        self.write('.agentic.json', json.dumps({'repository_kind': 'framework',
                                               'source_documents': documents}))

    def cli(self, script='framework_policy.py', *args, payload=None, env=None, cwd=None):
        return subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                              cwd=cwd or self.root, env={**self.env, **(env or {})},
                              input=json.dumps(payload) if payload is not None else None,
                              capture_output=True, text=True, timeout=30)

    def hook(self, tool, tool_input, **options):
        data = {'hook_event_name': 'PreToolUse', 'tool_name': tool,
                'tool_input': tool_input, 'cwd': str(self.root), **options}
        result = self.cli('lifecycle.py', 'hook', payload=data)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_clean_working_index_and_committed_source(self):
        for snapshot in ('working', 'index', 'head'):
            result = self.cli('framework_policy.py', '--snapshot', snapshot)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('PASS', result.stdout)

    def test_unregistered_and_ignored_task_documents_are_rejected(self):
        self.write('.gitignore', 'knowledge/\ndocs/\n.ai/plans/\n')
        for name in ('notes.md', '.ai/docs/innocent-name.md', 'docs/notes.md',
                     'knowledge/log.md', '.ai/install-manifest.json', '.ai/plans/task.json', 'history/lifecycle/task.json'):
            with self.subTest(name=name):
                path = self.write(name, '# Task paperwork\n')
                result = self.cli()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(name, result.stderr)
                path.unlink()
                # An empty knowledge directory is itself prohibited.
                if name.startswith('knowledge/'):
                    path.parent.rmdir()

    def test_reusable_source_documents_and_fixture_templates_are_allowed(self):
        names = ['README.md', '.ai/docs/runtime.md', '.ai/agents/reviewer.md',
                 '.claude/skills/spec/SKILL.md', '.ai/scripts/tests/fixtures/adopter/knowledge/spec.md']
        for name in names[1:]:
            self.write(name, '# Reusable source asset\n')
        self.marker(names)
        framework_policy.validate(self.root)

    def test_distributed_directories_cannot_hide_papers_as_operational_output(self):
        for name in ('.ai/build/task.md', '.ai/docs/nested/task.md'):
            with self.subTest(name=name):
                path = self.write(name, '# Task\n')
                if 'nested' in name:
                    (path.parent / '.git').mkdir()
                result = self.cli()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(name, result.stderr)
                path.unlink()

    def test_invalid_or_missing_identity_and_inventory_fail_closed(self):
        for data in ({'repository_kind': 'adopter'}, {'repository_kind': 'typo'},
                     {'repository_kind': 'framework'}, {'repository_kind': 'framework', 'source_documents': 'README.md'}):
            with self.subTest(data=data):
                self.write('.agentic.json', json.dumps(data))
                self.assertNotEqual(self.cli().returncode, 0)

    def test_unsafe_inventory_entries_and_duplicates_are_rejected(self):
        for names in (['../plan.md'], ['/tmp/plan.md'], ['C:/plan.md'], ['a\\plan.md'],
                      ['README.md', 'readme.md'], ['knowledge/spec.md'], ['.ai/plans/plan.md']):
            with self.subTest(names=names):
                self.marker(names)
                self.assertNotEqual(self.cli().returncode, 0)

    def test_index_uses_its_own_inventory_not_unstaged_working_inventory(self):
        self.write('renamed.md', '# Task\n')
        self.git('add', 'renamed.md')
        self.marker(['README.md', 'renamed.md'])
        self.assertEqual(self.cli().returncode, 0)
        result = self.cli('framework_policy.py', '--snapshot', 'index')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('renamed.md', result.stderr)
        self.assertEqual(self.cli('framework_policy.py', '--snapshot', 'head').returncode, 0)

    def test_case_distinct_git_document_cannot_reuse_an_inventory_entry(self):
        blob = subprocess.run(['git', '-C', str(self.root), 'hash-object', '-w', '--stdin'],
                              input='# Task\n', capture_output=True, text=True, check=True).stdout.strip()
        self.git('update-index', '--add', '--cacheinfo', '100644,' + blob + ',Readme.md')
        result = self.cli('framework_policy.py', '--snapshot', 'index')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Readme.md', result.stderr)

    def test_non_git_startup_is_silent_and_bad_identity_uses_session_context(self):
        with tempfile.TemporaryDirectory() as outside:
            result = self.cli('lifecycle.py', 'hook', cwd=outside,
                              payload={'hook_event_name': 'SessionStart', 'cwd': outside})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, '')
        self.write('.agentic.json', '{"repository_kind":"typo"}')
        result = self.cli('lifecycle.py', 'hook', payload={
            'hook_event_name': 'SessionStart', 'cwd': str(self.root)})
        self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['hookEventName'], 'SessionStart')

    def test_managed_validation_refuses_framework_before_request_or_owner_writes(self):
        plan = self.write('.git/input.json', json.dumps({'requirements': ['A'], 'commands': [
            {'label': 'check', 'argv': [sys.executable, '-c', 'print(1)'], 'coverage': ['A'], 'timeout_seconds': 5}]}))
        destination = self.root / '.git/request.json'
        result = self.cli('autonomy_validation.py', 'submit', '--plan', str(plan),
                          env={'OKF_VALIDATION_REQUEST': str(destination)})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('framework', result.stderr)
        self.assertFalse(destination.exists())
        self.assertFalse((self.root / '.git/okf-scratch').exists())

    def test_managed_validation_and_pr_sync_public_apis_refuse_before_leases(self):
        import autonomy_validation
        import pr_sync
        for operation in (
            lambda: autonomy_validation.run(self.root / '.git/missing.json', self.root,
                                            time.monotonic() + 5, .1, lambda *args: None, lambda: None),
            lambda: autonomy_validation.register(self.root / '.git/workers.json', self.root, self.root),
            lambda: pr_sync.sync(self.root / 'knowledge', dry_run=True),
        ):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'framework'):
                operation()
        self.assertFalse((self.root / '.git/okf-scratch').exists())

    def test_driver_refuses_before_progress_or_runtime_and_before_direct_drive(self):
        import autonomy_driver
        progress = self.root / '.git/progress.jsonl'
        result = self.cli('autonomy_driver.py', '--bundle', str(self.root / 'knowledge'),
                          '--headless', '--progress-file', str(progress), '--', sys.executable, '-c', 'print(1)')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(progress.exists())
        with mock.patch.object(autonomy_driver.autonomy_validation, 'git', side_effect=AssertionError('too late')):
            with self.assertRaisesRegex(ValueError, 'framework'):
                autonomy_driver.drive(self.root / 'knowledge', [sys.executable], 'solo', 1, 1, None)
        self.assertFalse((self.root / '.git/okf-autonomy').exists())

    def test_existing_framework_knowledge_cannot_receive_more_self_paperwork(self):
        self.write('knowledge/index.md', '---\nokf_version: "0.2"\n---\n')
        log = self.write('knowledge/log.md', '# Change log\n')
        before = log.read_bytes()
        for args in (('log', 'Not a framework lesson'), ('reindex',), ('onboard',)):
            with self.subTest(args=args):
                result = self.cli('okf.py', '--bundle', str(self.root / 'knowledge'), *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('framework', result.stderr)
        self.assertEqual(log.read_bytes(), before)
        self.assertFalse((self.root / 'knowledge/project').exists())
        self.assertFalse((self.root / '.git/okf-scratch').exists())

    def test_staged_artifact_still_fails_after_working_file_is_removed(self):
        path = self.write('report.md', '# Review Report\n')
        self.git('add', 'report.md')
        path.unlink()
        self.assertEqual(self.cli().returncode, 0)
        self.assertNotEqual(self.cli('framework_policy.py', '--snapshot', 'index').returncode, 0)

    def test_committed_contamination_fails_the_ci_entry_point(self):
        self.write('.ai/docs/renamed.md', '# Task\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'deliberately contaminated negative control')
        result = self.cli('framework_policy.py', '--snapshot', 'head')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('.ai/docs/renamed.md', result.stderr)

    def test_source_edits_need_no_adopter_task_and_startup_is_conversational(self):
        self.assertNotIn('deny', self.hook('Write', {'file_path': str(self.root / 'app.py')}))
        result = self.cli('lifecycle.py', 'hook', payload={'hook_event_name': 'SessionStart', 'cwd': str(self.root)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('in chat', result.stdout)
        self.assertNotIn('No tier declared', result.stdout)
        self.assertFalse((self.root / '.git/okf-scratch').exists())

    def test_markdown_write_patch_add_move_and_scratch_papers_are_denied(self):
        self.assertIn('deny', self.hook('Write', {'file_path': str(self.root / 'plan.md')}))
        for patch in ('*** Add File: plan.md\n+# Plan',
                      '*** Update File: README.md\n*** Move to: report.md\n',
                      '*** Delete File: plan.md\n*** Add File: plan.md\n+# Plan\n'):
            self.assertIn('deny', self.hook('apply_patch', {'input': patch}))
        self.assertIn('deny', self.hook('Write', {'file_path': str(self.root / '.git/okf-scratch/plan.md')}))
        self.assertNotIn('deny', self.hook('apply_patch', {'input': '*** Delete File: plan.md\n'}))
        external = self.root.parent / (self.root.name + '-self-plan.md')
        self.assertIn('deny', self.hook('Write', {'file_path': str(external)}))
        self.assertNotIn('deny', self.hook('Write', {'file_path': str(external.with_suffix('.log'))}))

    def test_absolute_common_git_scratch_outside_linked_worktree_is_denied(self):
        linked = self.root / 'linked'
        self.git('worktree', 'add', '-q', '-b', 'linked', str(linked))
        self.addCleanup(lambda: self.git('worktree', 'remove', '--force', str(linked)))
        target = self.root / '.git/okf-scratch/report.md'
        result = self.cli('lifecycle.py', 'hook', cwd=linked, payload={
            'hook_event_name': 'PreToolUse', 'tool_name': 'Write', 'cwd': str(linked),
            'tool_input': {'file_path': str(target)}})
        self.assertIn('deny', result.stdout)
        self.assertFalse(target.exists())

    def test_publication_guard_precedes_wip_and_bypass_flags_for_all_adapters(self):
        self.write('.ai/docs/task.md', '# Task\n')
        for env in ({}, {'LIFECYCLE_GUARD': 'off'}, {'OKF_AUTONOMOUS': '1'}):
            for cursor in (False, True):
                data = {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
                        'cwd': str(self.root), 'tool_input': {'command': 'git commit -m "wip: task"'}}
                if cursor:
                    data.update(cursor_version=1, hook_event_name='beforeShellExecution',
                                command='git commit -m "wip: task"')
                result = self.cli('lifecycle.py', 'hook', payload=data, env=env)
                self.assertIn('deny', result.stdout, result.stderr)
        self.assertFalse((self.root / '.git/okf-scratch').exists())

    def test_pr_checks_committed_tree_and_commit_checks_index(self):
        self.write('report.md', '# Review\n')
        self.git('add', 'report.md')
        (self.root / 'report.md').unlink()
        self.assertIn('deny', self.hook('Bash', {'command': 'git commit -m fix'}))
        self.git('commit', '-qm', 'deliberate index contamination')
        self.assertIn('deny', self.hook('Bash', {'command': 'gh pr create'}))

    def test_push_checks_committed_source_and_refuses_unchecked_refs(self):
        self.assertNotIn('deny', self.hook('Bash', {'command': 'git push origin HEAD'}))
        self.assertIn('deny', self.hook('Bash', {'command': 'git push origin some-other-branch'}))
        self.write('task.md', '# Plan\n')
        self.git('add', 'task.md')
        self.git('commit', '-qm', 'deliberate contamination')
        # An unstaged inventory edit must not bless the commit being uploaded.
        self.marker(['README.md', 'task.md'])
        output = self.hook('Bash', {'command': 'git push origin HEAD'})
        self.assertIn('deny', output)
        self.assertIn('task.md', output)

    def test_publication_refuses_an_unchecked_alternate_index_or_pr_head(self):
        alternate = self.root / '.git/alternate-index'
        output = self.hook('Bash', {'command': 'git commit -m fixture',
                                   'env': {'GIT_INDEX_FILE': str(alternate)}})
        self.assertIn('deny', output)
        self.assertIn('ordinary', output)
        self.assertIn('deny', self.hook('Bash', {'command': 'gh pr create --head other-branch'}))
        self.assertIn('deny', self.hook('Bash', {'command': 'gh pr create -Hother-branch'}))

    def test_adopter_target_from_framework_session_still_requires_its_lifecycle(self):
        adopter = self.root / 'adopter'
        adopter.mkdir()
        subprocess.run(['git', 'init', '-q', str(adopter)], check=True)
        (adopter / '.agentic.json').write_text('{"repository_kind":"adopter"}')
        output = self.hook('Write', {'file_path': str(adopter / 'app.py'), 'workdir': str(adopter)})
        self.assertIn('deny', output)
        self.assertIn('No active lifecycle tier', output)
        output = self.hook('Write', {'file_path': str(adopter / 'app.py')})
        self.assertIn('deny', output)
        self.assertIn('No active lifecycle tier', output)

    def test_native_self_review_report_refuses_without_writes(self):
        with self.assertRaisesRegex(review_native.guard.ReviewError, 'framework'):
            review_native.prepare_report(self.root, {}, '.ai/docs/review.md')
        self.assertFalse((self.root / '.ai').exists())
        self.assertFalse((self.root / '.git/okf-scratch').exists())


class InstallerSourcePolicyTests(InstallerCase):
    def mark_framework(self):
        names = sorted(path.relative_to(self.template).as_posix()
                       for path in self.template.rglob('*.md') if path.is_file())
        self.write('.agentic.json', json.dumps({'repository_kind': 'framework', 'source_documents': names}), template=True)

    def test_contaminated_framework_refuses_before_existing_or_absent_target_changes(self):
        self.mark_framework()
        self.write('.ai/docs/disguised-task.md', '# Review Report\n', template=True)
        before = tree_state(self.target)
        self.assertIn('disguised-task.md', self.run_install(code=2))
        self.assertEqual(tree_state(self.target), before)
        absent = self.target.parent / 'not created'
        result = subprocess.run([sys.executable, str(self.template / '.ai/scripts/install.py'), str(absent)],
                                capture_output=True, text=True, timeout=30,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(absent.exists())

    def test_clean_framework_installs_and_adopter_okf_still_works(self):
        self.mark_framework()
        self.run_install()
        self.assertTrue((self.target / 'knowledge/index.md').is_file())
        result = subprocess.run([sys.executable, str(self.target / '.ai/scripts/lifecycle.py'),
                                 'tier', 'L1', '--reason', 'adopter control'], cwd=self.target,
                                capture_output=True, text=True, timeout=30,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(list((self.target / 'knowledge/history/lifecycle').glob('*.json')))

    def test_install_cannot_turn_another_framework_checkout_into_its_own_adopter(self):
        self.write('.agentic.json', '{"repository_kind":"framework","source_documents":[]}')
        before = tree_state(self.target)
        result = self.run_install(code=2)
        self.assertIn('framework', result)
        self.assertEqual(tree_state(self.target), before)


if __name__ == '__main__':
    unittest.main()
