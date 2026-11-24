"""The suite runner's no-bytecode policy applies to fixture subprocesses too."""
import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import disk_tmp  # noqa: F401
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tests


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

    def test_per_test_groups_run_each_method_once_in_its_own_process(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root, marker = Path(directory), Path(outside) / 'runs'
            self.fixture(root, marker, count=6)
            self.assertEqual(run_tests.groups(root), {'test_fixture.Cases': 6})
            self.assertEqual(run_tests.groups(root, per_test=True), {f'test_fixture.Cases.test_{i:03}': 1 for i in range(6)})
            result = subprocess.run([sys.executable, str(Path(run_tests.__file__)), '-s', str(root), '-j', '3', '--per-test'],
                                    cwd=root, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Ran 6 tests', result.stdout)
            # Concurrent appends to one marker file can interleave on Windows, so only duplicates are checked here.
            lines = marker.read_text().splitlines()
            self.assertEqual(len(lines), len(set(lines)), 'a method ran more than once')

    def test_measured_weights_balance_heavy_tests_by_duration_and_run_each_once(self):
        weights = {'m.NativeCase.test_a': 100, 'm.NativeCase.test_b': 60, 'm.NativeCase.test_c': 50,
                   'm.NativeCase.test_d': 40, 'm.NativeCase.test_e': 10}
        ids = list(weights) + ['m.NativeCase.test_unmeasured'] + [f'm.Light.test_{i}' for i in range(8)]
        parts = [run_tests.balanced(ids, (index, 2), weights) for index in (1, 2)]
        self.assertEqual(sorted(i for part in parts for i in part), sorted(ids))
        loads = [sum(weights.get(i, 50) for i in part if 'Native' in i) for part in parts]  # 50 is the median
        self.assertLessEqual(abs(loads[0] - loads[1]), 10, loads)

    def test_per_test_shards_spread_heavy_native_tests_evenly_and_run_each_once(self):
        ids = [f'm{n}.NativeCase.test_{i:02}' for n in range(3) for i in range(10)] + [f'm.Light.test_{i}' for i in range(40)]
        parts = [run_tests.balanced(ids, (index, 4)) for index in range(1, 5)]
        self.assertEqual(sorted(i for part in parts for i in part), sorted(ids))
        heavy = [sum('Native' in i for i in part) for part in parts]
        self.assertLessEqual(max(heavy) - min(heavy), 1, heavy)
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root, marker = Path(directory), Path(outside) / 'runs'
            self.fixture(root, marker, count=8)
            ran = 0
            for index in (1, 2):
                result = subprocess.run([sys.executable, str(Path(run_tests.__file__)), '-s', str(root), '-j', '2',
                                         '--per-test', '--shard', f'{index}/2'],
                                        cwd=root, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                ran += int(result.stdout.split('Ran ')[1].split(' ')[0])
            self.assertEqual(ran, 8)

    def test_skip_heavy_leaves_out_chain_classes_and_requires_per_test(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'test_mixed.py').write_text(
                'import unittest\n'
                'class NativeChain(unittest.TestCase):\n    def test_slow(self): pass\n'
                'class ClosedTerminal(unittest.TestCase):\n    def test_slow(self): pass\n'
                'class Light(unittest.TestCase):\n    def test_fast(self): pass\n', encoding='utf-8')
            self.assertEqual(run_tests.groups(root, per_test=True, skip_heavy=True), {'test_mixed.Light.test_fast': 1})
            self.assertEqual(len(run_tests.groups(root, per_test=True)), 3)
            command = [sys.executable, str(Path(run_tests.__file__)), '-s', str(root)]
            result = subprocess.run(command + ['--per-test', '--skip-heavy', '-j', '1'], cwd=root,
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Ran 1 tests', result.stdout)
            refused = subprocess.run(command + ['--skip-heavy'], cwd=root, capture_output=True, text=True, timeout=60)
            self.assertNotEqual(refused.returncode, 0)

    def test_per_test_failure_is_reported_and_nonzero(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            self.fixture(root, Path(outside) / 'runs', fail=True, count=3)
            result = subprocess.run([sys.executable, str(Path(run_tests.__file__)), '-s', str(root), '-j', '3', '--per-test'],
                                    cwd=root, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 1)
            self.assertIn('deliberate segment failure', result.stdout)
            self.assertIn('FAILED (failures=1)', result.stdout)

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
