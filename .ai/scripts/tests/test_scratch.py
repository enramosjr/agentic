"""Scratch stays on the repository disk despite inherited/manifest temp settings."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest import mock

from test_autonomy import AutonomyTestCase
import autonomy_validation
import scratch


class ScratchTests(AutonomyTestCase):
    def setUp(self):
        super().setUp()
        self.init_git()
        self.commit_all("initial")

    def test_real_children_allocate_on_disk_and_do_not_dirty_candidate(self):
        environment = scratch.environment(self.repo, {**os.environ, "TMPDIR": "/tmp", "TMP": "/tmp", "TEMP": "/tmp"})
        root = scratch.directory(self.repo)
        code = ("import json,os,tempfile,subprocess,sys; "
                "d=tempfile.TemporaryDirectory(); "
                "print(json.dumps([d.name,*[os.environ[k] for k in ('TMPDIR','TMP','TEMP')]])); "
                "subprocess.run([sys.executable,'-c',\"import tempfile; print(tempfile.gettempdir())\"],check=True)")
        result = subprocess.run([sys.executable, "-c", code], env=environment, capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        values = json.loads(next(line for line in lines if line.startswith("[")))
        self.assertEqual(Path(values[0]).parent, root)
        self.assertEqual(values[1:], [str(root)] * 3)
        self.assertIn(str(root), lines)
        self.assertEqual(autonomy_validation.git(self.repo, "status", "--porcelain"), "")

    def test_system_temp_symlink_is_rejected_without_fallback(self):
        (self.repo / ".git" / "okf-scratch").symlink_to("/tmp", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "outside system temporary"):
            scratch.directory(self.repo)

    def test_system_temp_logs_and_aliases_are_rejected(self):
        for path in ("/tmp/run.jsonl", "/var/tmp/run.jsonl", "/dev/shm/run.jsonl"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "outside system temporary"):
                scratch.require_disk(Path(path))

    def test_unwritable_scratch_fails_before_launch(self):
        with mock.patch("scratch.tempfile.TemporaryFile", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                scratch.environment(self.repo)

    def test_validation_overrides_manifest_tmp_and_retains_effective_path(self):
        root = scratch.directory(self.repo)
        runtime = self.repo / ".git" / "validation"
        runtime.mkdir()
        request = runtime / "request.json"
        code = ("import os,tempfile; from pathlib import Path; "
                f"expected={str(root)!r}; "
                "assert all(os.environ[k]==expected for k in ('TMPDIR','TMP','TEMP')); "
                "d=tempfile.TemporaryDirectory(); assert Path(d.name).parent==Path(expected); print(d.name)")
        request.write_text(json.dumps({"candidate": autonomy_validation.git(self.repo, "rev-parse", "HEAD"), "requirements": ["A"], "commands": [
            {"label": "temp-allocation", "argv": [sys.executable, "-c", code], "timeout_seconds": 2,
             "coverage": ["A"], "env": {"TMPDIR": "/tmp", "TMP": "/tmp", "TEMP": "/tmp"}}]}))
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        value = json.loads(result.read_text())
        self.assertEqual(value["state"], "PASS")
        self.assertEqual(value["commands"][0]["scratch_directory"], str(root))
        self.assertEqual(autonomy_validation.git(self.repo, "status", "--porcelain"), "")
