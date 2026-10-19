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
