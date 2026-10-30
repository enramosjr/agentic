"""Local Git/Python tests only; never invoke a native agent or app-server."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import review_guard
import scratch


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PrebranchTests(unittest.TestCase):
    def setUp(self):
        scratch.require_disk(Path(tempfile.gettempdir()))
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'fixture'
        self.root.mkdir()
        self.operator = self.base / 'operator'
        self.operator.mkdir()
        launcher = self.operator / 'native-launch.py'
        shutil.copy2(ROOT / 'docs/assurance/native-launch-2-review-enforcement.py', launcher)
        self.launcher = load(launcher, 'prebranch_fixture')
        self.environment = mock.patch.dict(os.environ, {'MECHANICAL_NATIVE_PREPARED_BRANCH': 'codex/named-greeting'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.git('init', '-q')
        (self.root / 'source.txt').write_text('original\n')
        self.git('add', 'source.txt')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid',
                 '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture provenance')

    def git(self, *arguments):
        environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        return subprocess.run(['git', '-C', str(self.root), *arguments], env=environment,
                              capture_output=True, text=True, check=True).stdout.strip()

    def identity(self):
        return {name: self.git(*arguments) for name, arguments in (
            ('head', ['rev-parse', 'HEAD']), ('tree', ['rev-parse', 'HEAD^{tree}']),
            ('index', ['ls-files', '--stage']), ('commits', ['rev-list', '--count', 'HEAD']),
            ('status', ['status', '--porcelain']))}

    def refused(self, agent, reason):
        before, branch = self.identity(), self.git('symbolic-ref', '--short', 'HEAD')
        with self.assertRaisesRegex(ValueError, reason):
            self.launcher.prepare_capture_storage(self.root, agent)
        self.assertEqual(self.identity(), before)
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD'), branch)
        self.assertTrue((self.root / '.git').is_dir())

    def test_prebranch_preserves_head_tree_index_commits_and_cleanliness(self):
        before = self.identity()
        retained = self.launcher.prepare_capture_storage(self.root, 'codex')
        self.assertEqual(self.identity(), before)
        self.assertEqual(self.git('symbolic-ref', '--short', 'HEAD'), 'codex/named-greeting')
        self.assertTrue((self.root / '.git').is_file())
        record = json.loads((retained / 'relocation.json').read_text())
        self.assertEqual(record['isolation']['branch'], 'codex/named-greeting')
        self.assertTrue(record['isolation']['provided_before_session'])
        self.assertEqual(record['isolation']['head'], before['head'])
        self.assertEqual(record['isolation']['tree'], before['tree'])
        self.assertEqual(record['isolation']['commits'], before['commits'])
        self.assertEqual(set(record['temporary_environment'].values()), {str(retained / 'git-metadata/okf-scratch')})
        self.assertIn('do not create or switch branches', self.launcher.supplement('codex'))

    def test_wrong_agent_refuses(self):
        self.refused('claude', 'unsupported operator branch')

    def test_wrong_branch_refuses(self):
        os.environ['MECHANICAL_NATIVE_PREPARED_BRANCH'] = 'other'
        self.refused('codex', 'unsupported operator branch')

    def test_observed_session_refuses(self):
        with review_guard.transaction(self.root) as value:
            value['sessions']['already-observed'] = {'session': 'already-observed'}
        self.refused('codex', 'precede native sessions and task state')

    def test_existing_lifecycle_state_refuses(self):
        subprocess.run([sys.executable, str(ROOT / '.ai/scripts/lifecycle.py'), 'tier', 'L0',
                        '--reason', 'existing fixture task'], cwd=self.root,
                       capture_output=True, text=True, check=True)
        self.refused('codex', 'precede native sessions and task state')

    def test_dirty_fixture_refuses(self):
        (self.root / 'source.txt').write_text('changed\n')
        self.refused('codex', 'requires a clean fixture')

    def test_active_review_refuses(self):
        with review_guard.transaction(self.root) as value:
            value['interval'] = {'phase': 'active'}
        self.refused('codex', 'already has a producer/review')

    def test_future_runner_requires_explicit_authorization_before_any_subprocess(self):
        runner = load(ROOT / 'docs/assurance/run-native-2-mechanical-codex-v6.py', 'guarded_codex_runner')
        with mock.patch.object(sys, 'argv', ['runner']), mock.patch.object(
                runner.subprocess, 'run', side_effect=AssertionError('unexpected native process')):
            with self.assertRaisesRegex(ValueError, 'fresh explicit Codex-only allocation'):
                runner.main()


if __name__ == '__main__':
    unittest.main(verbosity=2)
