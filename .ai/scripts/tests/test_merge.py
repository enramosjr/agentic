"""Real `git merge` runs through the OKF merge driver that `okf.py git-setup` registers.

Run: python3 -m unittest discover -s .ai/scripts/tests
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import okf  # noqa: E402

TASKS = """
### T1 — First
- State: READY
- Priority: 10

### T2 — Second
- State: READY
- Priority: 20
"""


@unittest.skipUnless(shutil.which("git"), "git not installed")
class MergeDriverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.repo)
        self.bundle = self.repo / "knowledge"
        # The toolkit lives inside the repository, as in real use, so git-setup registers a repo-relative driver.
        scripts = self.repo / ".ai" / "scripts"
        scripts.mkdir(parents=True)
        shutil.copy(SCRIPTS / "okf.py", scripts / "okf.py")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("OKF_", "GIT_"))}
        self.env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t", PYTHONDONTWRITEBYTECODE="1")
        self.git("init", "-q", "-b", "main")
        self.okf("init", "--autonomous")
        # Keep the merge fixture independent of the initialization date.
        self.path("log.md").write_text("# OKF Change Log\n")
        self.append(okf.QUEUE_DOC, TASKS)
        self.okf("log", "Base entry.", "--date", "2026-10-12")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")

    def git(self, *args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=cwd or self.repo, env=self.env, capture_output=True, text=True, check=check)

    def okf(self, *args: str) -> str:
        result = subprocess.run(
            [sys.executable, str(self.repo / ".ai/scripts/okf.py"), *args],
            cwd=self.repo, env=self.env, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def path(self, rel: str) -> Path:
        return self.bundle / rel

    def append(self, rel: str, text: str) -> None:
        self.path(rel).write_text(self.path(rel).read_text() + text)

    def replace(self, rel: str, old: str, new: str) -> None:
        text = self.path(rel).read_text()
        self.assertIn(old, text)
        self.path(rel).write_text(text.replace(old, new, 1))

    def branch(self, name: str, edit: object) -> None:
        self.git("checkout", "-q", "-b", name, "main")
        edit()  # type: ignore[operator]
        self.git("add", "-A")
        self.git("commit", "-qm", name)

    def assert_valid(self) -> None:
        """No validation errors, and every index listing equals what reindex would write."""
        self.assertIn("OK: 0 errors", self.okf("validate"))
        self.assertEqual(okf.reindex(self.bundle, check=True), [])

    def merge(self, branch: str, *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return self.git("merge", "--no-edit", branch, cwd=cwd, check=False)

    def test_git_setup_registers_the_driver_once(self) -> None:
        attributes = (self.repo / ".gitattributes").read_text()
        self.assertIn("knowledge/**/log.md merge=okf", attributes)
        self.assertIn("knowledge/project/status.md merge=okf", attributes)
        self.assertEqual(self.git("config", "merge.okf.driver").stdout.strip(), "python3 .ai/scripts/okf.py merge-driver %O %A %B %P")
        self.assertEqual(self.okf("git-setup").strip(), "merge driver already configured")
        self.assertEqual((self.repo / ".gitattributes").read_text(), attributes)

    def test_without_the_driver_the_same_branches_conflict(self) -> None:
        # A fresh clone: .gitattributes names the driver, but git config has none, so git line-merges.
        self.git("config", "--remove-section", "merge.okf")
        self.make_parallel_branches()
        self.assertNotEqual(self.merge("b").returncode, 0)
        conflicted = set(self.git("diff", "--name-only", "--diff-filter=U").stdout.split())
        self.assertTrue({"knowledge/log.md", "knowledge/history/index.md", f"knowledge/{okf.STATUS_DOC}"} <= conflicted, conflicted)

    def test_parallel_branches_merge_without_conflicts(self) -> None:
        self.make_parallel_branches()
        result = self.merge("b", cwd=self.bundle / "project")  # from a subdirectory: the driver path is repo-relative
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git("diff", "--name-only", "--diff-filter=U").stdout, "")
        self.check_parallel_merge()

    def make_parallel_branches(self) -> None:
        def branch_a() -> None:
            self.okf("log", "Entry from A.", "--date", "2026-10-13")
            self.okf("new", "history/a.md", "--type", "Historical Record", "--title", "A delivery", "--description", "A.")
            self.replace(okf.QUEUE_DOC, "### T1 — First\n- State: READY", "### T1 — First\n- State: IN_PROGRESS\n- Owner: a@a")
            self.replace(okf.STATUS_DOC, "## In flight\n\nnothing", "## In flight\n\nA's work")

        def branch_b() -> None:
            self.okf("log", "Entry from B.", "--date", "2026-10-13")
            self.okf("new", "history/b.md", "--type", "Historical Record", "--title", "B delivery", "--description", "B.")
            self.replace(okf.QUEUE_DOC, "### T2 — Second\n- State: READY", "### T2 — Second\n- State: BLOCKED\n- Blocker: x\n- Unblock: y")
            self.append(okf.QUEUE_DOC, "\n### T3 — Discovered\n- State: READY\n")
            self.replace(okf.STATUS_DOC, "## In flight\n\nnothing", "## In flight\n\nB's work")
            self.replace(okf.STATUS_DOC, "## Blockers\n\nnone", "## Blockers\n\nT2 needs y")

        self.branch("b", branch_b)
        self.branch("a", branch_a)

    def check_parallel_merge(self) -> None:
        log = self.path("log.md").read_text()
        self.assertEqual(log.count("## 2026-10-13"), 1)
        self.assertIn("## 2026-10-13\n\n- Entry from A.\n- Entry from B.\n\n## 2026-10-12\n\n", log)
        self.assertTrue(log.endswith("- Base entry.\n"))
        index = self.path("history/index.md").read_text()
        self.assertLess(index.index("(a.md)"), index.index("(b.md)"))
        queue = self.path(okf.QUEUE_DOC).read_text()
        self.assertIn("### T1 — First\n- State: IN_PROGRESS\n- Owner: a@a", queue)
        self.assertIn("### T2 — Second\n- State: BLOCKED", queue)
        self.assertIn("### T3 — Discovered", queue)
        self.assertIn("### ID — Short title", queue)  # the fenced example survives untouched
        status = self.path(okf.STATUS_DOC).read_text()
        self.assertIn("## In flight\n\nA's work", status)  # both changed it: the current branch's checkpoint wins
        self.assertIn("## Blockers\n\nT2 needs y", status)
        self.assertNotIn("<<<<<<<", log + index + queue + status)
        self.assert_valid()

    def test_the_same_task_changed_both_ways_is_a_real_conflict(self) -> None:
        self.branch("b", lambda: self.replace(okf.QUEUE_DOC, "- State: READY\n- Priority: 10", "- State: DEFERRED\n- Reason: later\n- Priority: 10"))
        self.branch("a", lambda: self.replace(okf.QUEUE_DOC, "- State: READY\n- Priority: 10", "- State: CANCELLED\n- Reason: gone\n- Priority: 10"))
        result = self.merge("b")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("diff", "--name-only", "--diff-filter=U").stdout.strip(), f"knowledge/{okf.QUEUE_DOC}")
        self.assertIn("<<<<<<< ours", self.path(okf.QUEUE_DOC).read_text())

    def test_archiving_on_one_side_and_editing_another_task_on_the_other(self) -> None:
        def close_and_archive() -> None:
            self.replace(okf.QUEUE_DOC, "- State: READY\n- Priority: 10", "- State: DONE\n- Evidence: https://example.test/pr/1\n- Priority: 10")
            self.okf("queue", "--archive")

        self.branch("b", close_and_archive)
        self.branch("a", lambda: self.replace(okf.QUEUE_DOC, "- State: READY\n- Priority: 20", "- State: READY\n- Priority: 5"))
        result = self.merge("b")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        queue = self.path(okf.QUEUE_DOC).read_text()
        self.assertNotIn("### T1 — First", queue)
        self.assertIn("### T2 — Second\n- State: READY\n- Priority: 5", queue)
        self.assertIn("### T1 — First\n- State: DONE", self.path(okf.ARCHIVE_DOC).read_text())
        self.assert_valid()

    def test_checkpoint_fails_until_the_driver_is_registered(self) -> None:
        self.git("config", "--remove-section", "merge.okf")
        checks = {c.name: c for c in okf.checkpoint(self.bundle)}
        self.assertFalse(checks["merge driver"].ok)
        self.assertIn("run `okf.py git-setup`", checks["merge driver"].detail)
        self.okf("git-setup")
        self.assertTrue({c.name: c for c in okf.checkpoint(self.bundle)}["merge driver"].ok)


if __name__ == "__main__":
    unittest.main()
