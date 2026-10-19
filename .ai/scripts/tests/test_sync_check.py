"""Tests for `okf.py sync-check` (AGENTS.md Gate 3 as a fail-closed command).

Every test builds a temporary bundle in a scratch git repository; none touches this repository.
Run: python3 .ai/scripts/tests/test_sync_check.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import okf  # noqa: E402
from test_lifecycle import LifecycleCase  # noqa: E402
from test_okf import BundleTestCase  # noqa: E402


@unittest.skipUnless(shutil.which("git"), "git not installed")
class SyncCheckCase(BundleTestCase):
    """A committed bundle with one doc covering scripts/build.sh."""

    def setUp(self) -> None:
        super().setUp()
        self.new_doc()
        self.git = ["git", "-C", str(self.repo), "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run([*self.git, "init", "-q"], check=True)
        self.commit("init")

    def commit(self, message: str) -> None:
        subprocess.run([*self.git, "add", "."], check=True)
        subprocess.run([*self.git, "commit", "-qm", message], check=True)

    def edit_source(self, text: str = "echo changed\n", *, age: int = 0) -> Path:
        path = self.repo / "scripts/build.sh"
        path.write_text("#!/bin/sh\n" + text)
        if age:
            stamp = time.time() - age
            os.utime(path, (stamp, stamp))
        return path

    def sync_doc(self) -> None:
        """Do what Gate 3 asks: stamp the doc verified (touches it) and log the change."""
        self.run_ok("stamp", "verified", "capabilities/build.md", "--by", "human:test")
        self.run_ok("log", "Updated build capability.")

    def violations(self, *argv: str) -> tuple[int, list[dict]]:
        code, out, _ = self.run_cli("sync-check", "--json", *argv)
        return code, json.loads(out)["violations"]

    def rules(self, *argv: str) -> set[str]:
        return {item["rule"] for item in self.violations(*argv)[1]}


class SyncCheckTests(SyncCheckCase):
    def test_exit_codes_json_and_base_revision(self) -> None:
        code, out, _ = self.run_cli("sync-check")
        self.assertEqual((code, out.strip()), (0, "sync-check: OK"))
        self.assertEqual(self.violations(), (0, []))

        self.edit_source(age=10)
        code, out, _ = self.run_cli("sync-check")
        self.assertEqual(code, 1)
        self.assertIn("a-doc-unchanged knowledge/capabilities/build.md", out)
        self.assertIn("c-no-log", out)
        code, items = self.violations()
        self.assertEqual(code, 1)
        self.assertEqual({"a-doc-unchanged", "c-no-log", "d-verified-stale"}, {item["rule"] for item in items})
        self.assertTrue(all({"rule", "path"} <= set(item) for item in items))

        self.sync_doc()
        self.assertEqual(self.violations(), (0, []))

        self.commit("sync")
        self.assertEqual(self.violations(), (0, []), "a clean tree against HEAD has nothing to check")
        first = subprocess.run(
            [*self.git, "rev-list", "--max-parents=0", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        self.assertEqual(self.violations("--base", first), (0, []), "the committed change is synced")
        self.run_ok("log", "Second entry.")
        self.edit_source("echo again\n", age=10)
        self.assertEqual(self.violations("--base", first), (0, []), "the doc changed since the first commit")
        self.assertIn("a-doc-unchanged", self.rules(), "but not since HEAD")
        code, _, err = self.run_cli("sync-check", "--base", "nonexistent-rev")
        self.assertEqual(code, 1)
        self.assertIn("unknown git revision", err)

    def test_affected_doc_not_changed_fails(self) -> None:
        self.edit_source(age=10)
        self.run_ok("log", "Touched the build script.")
        code, items = self.violations()
        self.assertEqual(code, 1)
        hit = [item for item in items if item["rule"] == "a-doc-unchanged"]
        self.assertEqual([item["path"] for item in hit], ["knowledge/capabilities/build.md"])
        self.assertIn("scripts/build.sh", hit[0]["detail"])
        self.sync_doc()
        self.assertEqual(self.violations(), (0, []))

    def test_uncovered_file_fails_unless_in_sync_ignore(self) -> None:
        self.run_ok("log", "A log entry exists.")
        (self.repo / "orphan.txt").write_text("x")
        (self.repo / "docs").mkdir()
        (self.repo / "docs/skip.txt").write_text("y")
        code, items = self.violations()
        self.assertEqual(code, 1)
        self.assertEqual(
            sorted((item["rule"], item["path"]) for item in items),
            [("b-uncovered", "docs/skip.txt"), ("b-uncovered", "orphan.txt")],
        )
        self.write("project/sync-ignore", "# generated and scratch files\n\ndocs/*.txt\norphan.txt\n")
        self.assertEqual(self.violations(), (0, []))
        # Files under knowledge/ are never reported.
        self.write("concepts/new.md", "---\ntype: Concept\n---\n")
        self.assertEqual(self.violations(), (0, []))

    def test_missing_log_entry_fails(self) -> None:
        (self.repo / "orphan.txt").write_text("x")
        self.write("project/sync-ignore", "orphan.txt\n")
        code, items = self.violations()
        self.assertEqual(code, 1)
        self.assertEqual([item["rule"] for item in items], ["c-no-log"])
        self.assertIn("no log entry", items[0]["detail"])
        self.run_ok("log", "Recorded.")
        self.assertEqual(self.violations(), (0, []))
        # Knowledge-only changes need no log entry.
        self.commit("sync")
        self.write("concepts/new.md", "---\ntype: Concept\n---\n")
        self.assertEqual(self.violations(), (0, []))

    def test_verified_at_older_than_source_mtime_fails(self) -> None:
        self.edit_source(age=0)
        self.run_ok("set", "capabilities/build.md", "verified={by: \"human:test\", at: 2020-01-01T00:00:00Z}")
        self.run_ok("log", "Changed.")
        code, items = self.violations()
        self.assertEqual(code, 1)
        self.assertEqual([item["rule"] for item in items], ["d-verified-stale"])
        self.assertEqual(items[0]["path"], "knowledge/capabilities/build.md")
        self.assertIn("scripts/build.sh", items[0]["detail"])

        self.sync_doc()
        self.assertEqual(self.violations(), (0, []))

        # A list uses its latest entry; a deleted source is skipped.
        self.edit_source(age=0)
        self.run_ok("set", "capabilities/build.md", "verified=[{by: \"human:a\", at: 2020-01-01T00:00:00Z}, {by: \"human:b\", at: 2999-01-01T00:00:00Z}]")
        self.assertEqual(self.violations(), (0, []))
        (self.repo / "scripts/build.sh").unlink()
        self.run_ok("set", "capabilities/build.md", "verified={by: \"human:test\", at: 2020-01-01T00:00:00Z}")
        self.assertEqual(self.violations(), (0, []))

    def test_no_bundle_exits_one(self) -> None:
        shutil.rmtree(self.bundle)
        code, out, err = self.run_cli("sync-check")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("no OKF bundle at", err)


class SyncCheckVerifyTests(LifecycleCase):
    def bundle(self, *ignore: str) -> None:
        shutil.copytree(SCRIPTS, self.repo / ".ai/scripts", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        subprocess.run([sys.executable, ".ai/scripts/okf.py", "init"], cwd=self.repo, check=True, capture_output=True)
        self.ignore(*ignore)

    def ignore(self, *globs: str) -> None:
        (self.repo / "knowledge/project/sync-ignore").write_text("\n".join(globs) + "\n")

    def l1_to_verify(self) -> None:
        self.ok("tier", "L1", "--reason", "x")
        self.ok("stage", "intent", "--note", "n")
        self.ok("stage", "plan", "--note", "p")

    def test_stage_verify_runs_sync_check_uses_task_head_and_skips_without_bundle(self) -> None:
        # No bundle: the check is skipped without error.
        self.l1_to_verify()
        self.ok("stage", "verify", "--note", "ran")
        self.ok("stage", "ship")

        # A bundle: an uncovered change fails verify, and sync-check runs before the records gate.
        self.bundle(".ai/*")
        (self.repo / "knowledge/capabilities/broken.md").write_text("no frontmatter\n")
        (self.repo / "app.py").write_text("print('changed')\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "bundle")
        self.l1_to_verify()
        (self.repo / "app.py").write_text("print('again')\n")
        self.fails("stage", "verify", "--note", "ran", message="sync-check failed")
        self.fails("stage", "verify", "--note", "ran", message="b-uncovered app.py")
        self.ignore(".ai/*", "app.py")
        subprocess.run([sys.executable, ".ai/scripts/okf.py", "log", "Changed app."], cwd=self.repo, check=True, capture_output=True)
        self.fails("stage", "verify", "--note", "ran", message="okf.py records failed")
        (self.repo / "knowledge/capabilities/broken.md").unlink()
        self.ok("stage", "verify", "--note", "ran")

    def test_sync_check_compares_against_the_head_the_task_started_on(self) -> None:
        self.bundle(".ai/*")
        self.git("add", "-A")
        self.git("commit", "-qm", "bundle")
        self.l1_to_verify()
        (self.repo / "app.py").write_text("print('committed')\n")
        self.git("commit", "-qam", "change")  # A clean tree against HEAD, but not against the task's head.
        self.fails("stage", "verify", "--note", "ran", message="b-uncovered app.py")


if __name__ == "__main__":
    unittest.main()
