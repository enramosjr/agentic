"""The suite runner's no-bytecode policy applies to fixture subprocesses too."""
import os
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import disk_tmp  # noqa: F401
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tests


class QualificationGateTests(unittest.TestCase):
    def workflow(self):
        return (Path(__file__).resolve().parents[3] / '.github/workflows/framework-parity.yml').read_text()

    def test_summary_runs_after_unsuccessful_dependencies(self):
        summary = self.workflow().split('\n  qualification:\n', 1)[1]
        self.assertIn('if: always()', summary)
        self.assertIn('needs: [windows_preflight, regression_segments]', summary)

    @unittest.skipIf(os.name == 'nt', 'the summary executes in Bash on Ubuntu')
    def test_actual_summary_command_rejects_every_unsuccessful_state(self):
        command = re.search(r"^\s+run: '(\[\[.+\]\])'\s*$", self.workflow(), re.MULTILINE).group(1)
        def check(value):
            for preflight in ('success', 'failure', 'cancelled', 'skipped', '', 'unknown'):
                for segments in ('success', 'failure', 'cancelled', 'skipped', '', 'unknown'):
                    result = subprocess.run(['bash', '-c', value],
                        env={**os.environ, 'PREFLIGHT_RESULT': preflight, 'SEGMENTS_RESULT': segments},
                        capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode == 0, preflight == segments == 'success',
                                     (preflight, segments, result.stderr))
        check(command)
        with self.assertRaises(AssertionError):
            check('[[ "$PREFLIGHT_RESULT" == success ]]')


class ShardTests(unittest.TestCase):
    def fixture(self, root, marker, fail=False, count=128):
        body = 'import unittest\nclass Cases(unittest.TestCase):\n'
        for index in range(count):
            body += (f'    def test_{index:03}(self):\n'
                     f'        with open({str(marker)!r}, "a") as stream: stream.write(self.id()+"\\n")\n')
            if fail and index == 0:
                body += '        self.fail("deliberate segment failure")\n'
        (root / 'test_fixture.py').write_text(body)

    def invoke(self, root, shard, env=None):
        return subprocess.run([sys.executable, str(Path(run_tests.__file__)), '-s', str(root),
                               '-j', '1', '--shard', shard], cwd=root, capture_output=True,
                              text=True, timeout=30, env=env)

    def test_partition_is_complete_disjoint_and_stable(self):
        names = [f'test_fixture.Cases.test_{i:03}' for i in range(128)]
        partitions = [{name for name in names if run_tests.selected(name, (i, 8))}
                      for i in range(1, 9)]
        self.assertEqual(set.union(*partitions), set(names))
        self.assertEqual(sum(map(len, partitions)), len(names))
        self.assertTrue(all(partitions), 'a large class must be split across all segments')
        for index, expected in enumerate(partitions, 1):
            self.assertEqual({name for name in reversed(names) if run_tests.selected(name, (index, 8))}, expected)

    def test_cli_runs_every_method_exactly_once_across_eight_segments(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root, marker = Path(directory), Path(outside) / 'runs'
            self.fixture(root, marker)
            for index in range(1, 9):
                result = self.invoke(root, f'{index}/8')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            actual = marker.read_text().splitlines()
            self.assertEqual(len(actual), 128)
            self.assertEqual(set(actual), {f'test_fixture.Cases.test_{i:03}' for i in range(128)})

    def test_failed_segment_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root, marker = Path(directory), Path(outside) / 'runs'
            self.fixture(root, marker, fail=True)
            results = [self.invoke(root, f'{index}/8') for index in range(1, 9)]
            self.assertEqual(sorted(result.returncode for result in results), [0] * 7 + [1])
            self.assertTrue(any('deliberate segment failure' in result.stdout for result in results))

    def test_invalid_and_empty_segments_do_not_pass(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            self.fixture(root, Path(outside) / 'runs', count=1)
            for value in ('0/2', '3/2', '1/0', '-1/2', 'abc', '1', '1/2/3'):
                with self.subTest(value=value):
                    self.assertEqual(self.invoke(root, value).returncode, 2)
            results = [self.invoke(root, f'{index}/2') for index in (1, 2)]
            self.assertEqual(sorted(result.returncode for result in results), [0, 2])

    def test_resume_cannot_substitute_one_segment_for_another(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root, marker = Path(directory), Path(outside) / 'runs'
            self.fixture(root, marker)
            env = {**os.environ, 'AGENTIC_TEST_RESUME': str(Path(outside) / 'resume.json')}
            self.assertEqual(self.invoke(root, '1/8', env).returncode, 0)
            first = marker.read_text().splitlines()
            self.assertEqual(self.invoke(root, '2/8', env).returncode, 0)
            second = marker.read_text().splitlines()[len(first):]
            self.assertTrue(second)
            self.assertFalse(set(first) & set(second))
            self.assertEqual(self.invoke(root, '2/8', env).returncode, 0)
            self.assertEqual(marker.read_text().splitlines(), first + second)

    def test_worker_crash_and_count_mismatch_do_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            for count, code in ((0, 0), (2, 7)):
                def fake(command, **kwargs):
                    path = Path(command[command.index('--result') + 1])
                    path.write_text(json.dumps({'run': count, 'failures': [], 'errors': [],
                                                'unexpected': [], 'skipped': 0}))
                    return subprocess.CompletedProcess(command, code, '', '')
                with self.subTest(count=count, code=code), mock.patch.object(run_tests.subprocess, 'run', side_effect=fake):
                    result = run_tests.run_group(Path(directory), 'test_fixture.Cases', 2)
                    self.assertTrue(result['errors'])

    def test_resume_count_mismatch_runs_the_missing_work(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            value = {'run': 0, 'failures': [], 'errors': [], 'unexpected': [], 'skipped': 0}
            resume = SimpleNamespace(passed={'test_fixture.Cases': value}, record=lambda *args: None)
            def fake(command, **kwargs):
                path = Path(command[command.index('--result') + 1])
                path.write_text(json.dumps({**value, 'run': 2}))
                return subprocess.CompletedProcess(command, 0, '', '')
            with mock.patch.object(run_tests.subprocess, 'run', side_effect=fake) as worker:
                result = run_tests.run_group(Path(directory), 'test_fixture.Cases', 2, resume)
            self.assertEqual(worker.call_count, 1)
            self.assertEqual(result['run'], 2)


class RunnerTests(unittest.TestCase):
    def test_nested_fixture_import_does_not_create_bytecode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'fixture_helper.py').write_text('VALUE = 7\n')
            (root / 'test_fixture.py').write_text(
                'import subprocess, sys, unittest\n'
                'from pathlib import Path\n'
                'class Fixture(unittest.TestCase):\n'
                '    def test_nested_import(self):\n'
                '        subprocess.run([sys.executable, "-c", "import fixture_helper; assert fixture_helper.VALUE == 7"], check=True)\n'
                '        self.assertFalse(Path("__pycache__").exists())\n'
            )
            runner = Path(__file__).resolve().parents[1] / 'run_tests.py'
            result = subprocess.run(
                [sys.executable, str(runner), '-s', str(root), '-j', '1'],
                cwd=root, capture_output=True, text=True,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '0'},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Ran 1 tests', result.stdout)
            self.assertFalse((root / '__pycache__').exists())

    def test_resume_skips_classes_that_passed_on_this_tree(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root, runs, flaky = Path(directory), Path(outside) / 'runs', Path(outside) / 'flaky'
            (root / 'test_steady.py').write_text(
                'import unittest\n'
                'class Steady(unittest.TestCase):\n'
                '    def test_ok(self):\n'
                f'        open({str(runs)!r}, "a").write("x")\n')
            (root / 'test_flaky.py').write_text(
                'import unittest\nfrom pathlib import Path\n'
                'class Flaky(unittest.TestCase):\n'
                '    def test_second_time(self):\n'
                f'        marker = Path({str(flaky)!r})\n'
                '        first = not marker.exists()\n'
                '        marker.touch()\n'
                '        self.assertFalse(first)\n')
            runner = Path(__file__).resolve().parents[1] / 'run_tests.py'
            env = {**os.environ, 'AGENTIC_TEST_RESUME': str(Path(outside) / 'resume.json')}
            def run():
                return subprocess.run([sys.executable, str(runner), '-s', str(root), '-j', '1'],
                                      cwd=root, capture_output=True, text=True, env=env)
            first = run()
            self.assertEqual(first.returncode, 1, first.stdout + first.stderr)
            self.assertEqual(runs.read_text(), 'x')
            second = run()
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(runs.read_text(), 'x', 'the class that passed must not run again')
            (root / 'test_steady.py').write_text((root / 'test_steady.py').read_text() + '\n# edited\n')
            third = run()
            self.assertEqual(third.returncode, 0, third.stdout + third.stderr)
            self.assertEqual(runs.read_text(), 'xx', 'an edited tree must rerun everything')
