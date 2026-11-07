"""Fail-closed qualification summary over the actual workflow command."""
import os
from pathlib import Path
import re
import subprocess
import unittest


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
