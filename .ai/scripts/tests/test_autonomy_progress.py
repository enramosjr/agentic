"""Public progress projection, incremental reads and acknowledgement identity."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import autonomy_progress


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "events.jsonl"
        self.ack = self.path.with_suffix(".ack.json")
        self.progress = autonomy_progress.Progress(self.path, self.ack, 90)
        self.addCleanup(self.progress.output.close)

    def test_only_completed_public_messages_are_projected(self):
        for value in ([], {"item": None}, {"type": "item.completed", "item": {"type": "agent_message", "text": {"private": "PRIVATE"}}},
                      {"type": "item.completed", "item": {"type": "command_execution", "aggregated_output": "PRIVATE"}}):
            self.progress.observe(json.dumps(value))
        self.progress.observe(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Tests running"}}))
        events = autonomy_progress.read_events(self.path, after=1)
        self.assertEqual([entry["text"] for entry in events], ["Tests running"])
        self.assertNotIn("PRIVATE", self.path.read_text())

    def test_cursor_and_claude_stream_json_project_only_assistant_text(self):
        lines = [
            {"type": "system", "subtype": "init", "cwd": "PRIVATE"},
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "PRIVATE prompt"}]}},
            {"type": "tool_call", "subtype": "completed", "tool_call": {"shellToolCall": {"args": {"command": "PRIVATE"}}}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Cursor update"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "thinking", "thinking": "PRIVATE"},
                {"type": "tool_use", "name": "Bash", "input": {"command": "PRIVATE"}}]}},
            {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "PRIVATE"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Claude update"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": {"private": "PRIVATE"}}]}},
            {"type": "assistant", "message": "PRIVATE"},
            {"type": "result", "subtype": "success", "is_error": False, "result": "PRIVATE final duplicate"},
            {"type": "result", "subtype": "error_during_execution", "is_error": True, "result": "PRIVATE"},
        ]
        for value in lines:
            self.progress.observe(json.dumps(value))
        events = autonomy_progress.read_events(self.path, after=1)
        self.assertEqual([(entry["kind"], entry["text"]) for entry in events],
                         [("update", "Cursor update"), ("update", "Claude update"),
                          ("failure", "Agent reported a failure; inspect the private run log for details.")])
        self.assertNotIn("PRIVATE", self.path.read_text())

    def test_actual_read_and_ack_cli_bind_sequence_and_refuse_stale_or_other_runs(self):
        self.progress.emit("heartbeat", "Still testing")
        read = subprocess.run([sys.executable, str(SCRIPTS / "autonomy_progress.py"), "read", "--file", str(self.path), "--after", "1"],
                              capture_output=True, text=True, timeout=5)
        self.assertEqual(read.returncode, 0, read.stderr)
        value = json.loads(read.stdout)
        self.assertEqual(value["next_sequence"], 2)
        self.assertEqual([event["text"] for event in value["events"]], ["Still testing"])
        ack = subprocess.run([sys.executable, str(SCRIPTS / "autonomy_progress.py"), "ack", "--file", str(self.path), "--ack-file", str(self.ack)],
                             capture_output=True, text=True, timeout=5)
        self.assertEqual(ack.returncode, 0, ack.stderr)
        self.progress.check()
        for run, moment in (("unrelated-run", time.monotonic()), (self.progress.run_id, -1)):
            self.ack.write_text(json.dumps({"run_id": run, "sequence": 2, "acknowledged_at": moment}))
            with self.assertRaises(autonomy_progress.MonitorLost):
                self.progress.check()

    def test_existing_progress_file_cannot_be_reused_for_another_launch(self):
        with self.assertRaises(FileExistsError):
            autonomy_progress.Progress(self.path, self.ack, 90)


if __name__ == "__main__":
    unittest.main()
