"""Exercise the timing CLI's actual output, side effects and exit status."""
import json
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "timed_check.py"
sys.path.insert(0, str(SCRIPT.parent))
import timed_check


class TimedCheckTests(unittest.TestCase):
    def invoke(self, *command, cwd=None):
        return subprocess.run([sys.executable, str(SCRIPT), "--label", "qualification", "--", *command],
                              capture_output=True, text=True, cwd=cwd)

    def timing(self, result):
        lines = [line.removeprefix("timing: ") for line in result.stderr.splitlines()
                 if line.startswith("timing: ")]
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["label"], "qualification")
        self.assertGreaterEqual(record["elapsed_seconds"], 0)
        self.assertIn("started_at", record)
        self.assertIn("finished_at", record)
        return record

    def test_success_preserves_output_and_real_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "result"
            result = self.invoke(sys.executable, "-c",
                                 "import pathlib,sys; pathlib.Path(sys.argv[1]).write_text('verified'); print('exact output')",
                                 str(target))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "exact output\n")
            self.assertEqual(target.read_text(), "verified")
            self.assertEqual(self.timing(result)["outcome"], "PASS")
            self.assertNotIn(str(target), result.stderr)

    def test_failed_check_preserves_exit_and_stderr(self):
        result = self.invoke(sys.executable, "-c", "import sys; print('refused',file=sys.stderr); sys.exit(7)")
        self.assertEqual(result.returncode, 7)
        self.assertIn("refused", result.stderr)
        record = self.timing(result)
        self.assertEqual(record["exit_code"], 7)
        self.assertEqual(record["outcome"], "FAIL")

    def test_missing_command_fails_closed(self):
        result = self.invoke("/does-not-exist/qualification")
        self.assertEqual(result.returncode, 127)
        self.assertEqual(self.timing(result)["outcome"], "FAIL")

    def test_missing_arguments_do_not_claim_a_check_ran(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("timing: ", result.stderr)

    def test_non_repository_command_keeps_cwd_and_uses_toolkit_disk_scratch(self):
        import scratch
        with tempfile.TemporaryDirectory() as directory:
            result = self.invoke(sys.executable, "-c",
                                 "import pathlib,tempfile; print(pathlib.Path.cwd()); print(tempfile.gettempdir())",
                                 cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [str(Path(directory).resolve()),
                             str(scratch.directory(SCRIPT.parents[2]))])

    def test_invalid_utf8_output_is_retained_as_explicit_byte_escapes(self):
        lines, output, timing = [], io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(timing):
            result = timed_check.run([sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes([255,10]))"],
                                     label="binary-output", timeout_seconds=2, on_output=lines.append)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(lines, ["\\xff\n"])
        self.assertIn('"outcome": "PASS"', timing.getvalue())

    def test_reader_write_failure_cannot_produce_pass_timing(self):
        def disk_full(line):
            raise OSError("simulated evidence disk full")
        output, timing = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(timing):
            with self.assertRaises(timed_check.CaptureError):
                timed_check.run([sys.executable, "-c", "print('actual command output')"], label="write-failure",
                                timeout_seconds=2, on_output=disk_full)
        self.assertIn('"outcome": "FAIL"', timing.getvalue())
        self.assertNotIn('"outcome": "PASS"', timing.getvalue())


if __name__ == "__main__":
    unittest.main()
