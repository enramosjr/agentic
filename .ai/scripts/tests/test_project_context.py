"""Read-only startup discovery and explicit source/adopter identity."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_lifecycle import LifecycleCase


class ContextTests(LifecycleCase):
    def context(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[1] / 'repo.py'), 'context', '--json'],
            cwd=self.repo, env={**os.environ, 'REPO_ROOT': str(self.repo)},
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_framework_is_explicit_and_context_is_read_only(self):
        (self.repo / '.agentic.json').write_text('{"repository_kind":"framework"}')
        before = self.git_status()
        data = self.context()
        self.assertEqual(data['repository_kind'], 'framework')
        self.assertTrue(data['git']['head'])
        self.assertEqual(data['git']['freshness'], 'no-upstream')
        self.assertEqual(self.git_status(), before)
        self.assertFalse((self.repo / 'knowledge').exists())

    def git_status(self):
        return subprocess.check_output(['git', '-C', str(self.repo), 'status', '--porcelain'])

    def test_unknown_and_installed_adopter_are_distinct(self):
        self.assertEqual(self.context()['repository_kind'], 'unknown')
        path = self.repo / '.ai/install-manifest.json'
        path.parent.mkdir()
        path.write_text('{"format":1,"files":{},"hooks":{}}')
        self.assertEqual(self.context()['repository_kind'], 'adopter')

    def test_source_audit_stays_out_of_adopter_knowledge(self):
        (self.repo / '.agentic.json').write_text('{"repository_kind":"framework"}')
        self.ok('tier', 'L1', '--reason', 'framework source')
        self.assertFalse((self.repo / 'knowledge').exists())
        import lifecycle
        state = lifecycle.load(self.repo)
        self.assertTrue(lifecycle.record_path(self.repo, state).is_file())
        self.ok('learn', 'Source lessons stay available', '--evidence', 'fixture')
        self.assertIn('Source lessons stay available', self.ok('observations', '--query', 'Source lessons'))
        self.assertFalse((self.repo / 'knowledge').exists())

    def test_bad_role_fails_instead_of_initializing_anything(self):
        (self.repo / '.agentic.json').write_text('{"repository_kind":"typo"}')
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[1] / 'repo.py'), 'context', '--json'],
            env={**os.environ, 'REPO_ROOT': str(self.repo)}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('repository_kind', result.stderr)
        self.assertFalse((self.repo / 'knowledge').exists())

    def test_init_refuses_a_framework_source_bundle(self):
        scripts = Path(__file__).resolve().parents[1]
        shutil.copytree(scripts, self.repo / '.ai/scripts', ignore=shutil.ignore_patterns('tests', '__pycache__'))
        (self.repo / '.agentic.json').write_text('{"repository_kind":"framework"}')
        result = subprocess.run([sys.executable, str(self.repo / '.ai/scripts/okf.py'), 'init'],
                                cwd=self.repo, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('framework', result.stderr)
        self.assertFalse((self.repo / 'knowledge').exists())

    def test_headings_and_real_command_help_need_no_bundle(self):
        script = str(Path(__file__).resolve().parents[1] / 'repo.py')
        result = subprocess.run([sys.executable, script, 'headings', 'spec.md'], cwd=self.repo,
                                env={**os.environ, 'REPO_ROOT': str(self.repo)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Requirements', result.stdout)
        result = subprocess.run([sys.executable, script, 'commands', 'repo', 'files'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--under', result.stdout)


if __name__ == '__main__':
    unittest.main()
