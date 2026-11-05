"""The suite runner's no-bytecode policy applies to fixture subprocesses too."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import disk_tmp  # noqa: F401


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
