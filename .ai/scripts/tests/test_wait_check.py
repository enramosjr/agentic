"""Exercise wait_check's real CLI: detached start, blocking wait and every exit state."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "wait_check.py"


class WaitCheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.log = Path(self.directory.name) / "check.log"

    def cli(self, *args, timeout=30):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=timeout)

    def start(self, code):
        result = self.cli("start", "--log", str(self.log), "--", sys.executable, "-c", code)
        self.assertEqual(result.returncode, 0, result.stderr)
        pid = json.loads(result.stdout)["pid"]
        self.addCleanup(self.kill, pid)
        return pid

    @staticmethod
    def kill(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def record(self, result):
        lines = [line.removeprefix("wait: ") for line in result.stderr.splitlines() if line.startswith("wait: ")]
        self.assertEqual(len(lines), 1, result.stderr)
        return json.loads(lines[0])

    def test_finished_check_returns_its_exit_code_and_output_tail(self):
        self.start("import sys,time; print('step one'); time.sleep(.3); print('last line'); sys.exit(7)")
        result = self.cli("wait", "--log", str(self.log), "--max", "20")
        self.assertEqual(result.returncode, 7)
        record = self.record(result)
        self.assertEqual((record["state"], record["exit_code"]), ("finished", 7))
        self.assertEqual(result.stdout.splitlines()[-2:], ["step one", "last line"])
        self.assertEqual((self.log.parent / "check.log.exit").read_text(), "7\n")

    def test_passing_check_returns_zero(self):
        self.start("print('ok')")
        result = self.cli("wait", "--log", str(self.log), "--max", "20")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.record(result)["state"], "finished")

    def test_fail_pattern_returns_early_while_check_keeps_running(self):
        pid = self.start("import time; print('window 12 FAIL rms=3', flush=True); time.sleep(60)")
        started = time.monotonic()
        result = self.cli("wait", "--log", str(self.log), "--fail", r"\bFAIL\b", "--max", "20")
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual(result.returncode, 4)
        record = self.record(result)
        self.assertEqual((record["state"], record["line"]), ("fail-match", "window 12 FAIL rms=3"))
        os.kill(pid, 0)

    def test_done_pattern_returns_zero_before_exit(self):
        self.start("import time; print('capture ready', flush=True); time.sleep(60)")
        result = self.cli("wait", "--log", str(self.log), "--done", "capture ready", "--max", "20")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.record(result)["state"], "done-match")

    def test_timeout_reports_running_and_leaves_check_alive(self):
        pid = self.start("import time; print('progress 1', flush=True); time.sleep(60)")
        result = self.cli("wait", "--log", str(self.log), "--max", "0.5")
        self.assertEqual(result.returncode, 124)
        self.assertEqual(self.record(result)["state"], "running")
        os.kill(pid, 0)
        self.assertFalse((self.log.parent / "check.log.exit").exists())

    def test_killed_supervisor_is_reported_lost_not_passed(self):
        pid = self.start("import time; time.sleep(60)")
        self.kill(pid)
        result = self.cli("wait", "--log", str(self.log), "--max", "20")
        self.assertEqual(result.returncode, 125)
        self.assertEqual(self.record(result)["state"], "lost")

    def test_external_pid_without_exit_record_is_lost(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(.3)"])
        self.log.write_text("external\n")
        result = self.cli("wait", "--log", str(self.log), "--pid", str(child.pid), "--max", "20")
        child.wait()
        self.assertEqual(result.returncode, 125)

    def test_missing_command_and_bad_pattern_fail_closed(self):
        self.assertEqual(self.cli("start", "--log", str(self.log)).returncode, 2)
        self.log.write_text("")
        self.assertEqual(self.cli("wait", "--log", str(self.log), "--fail", "(").returncode, 2)

    def test_live_log_cannot_be_reused_but_finished_one_can(self):
        self.start("import time; time.sleep(60)")
        refused = self.cli("start", "--log", str(self.log), "--", sys.executable, "-c", "print(1)")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("still owns", refused.stderr)
        self.kill(int((self.log.parent / "check.log.pid").read_text()))
        self.cli("wait", "--log", str(self.log), "--max", "5")
        self.start("print('second run')")
        result = self.cli("wait", "--log", str(self.log), "--max", "20")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "second run"))

    def test_unstartable_command_records_127(self):
        result = self.cli("start", "--log", str(self.log), "--", "/does-not-exist/check")
        self.assertEqual(result.returncode, 0)
        waited = self.cli("wait", "--log", str(self.log), "--max", "20")
        self.assertEqual(waited.returncode, 127)
        self.assertIn("cannot start command", waited.stdout)


if __name__ == "__main__":
    unittest.main()
