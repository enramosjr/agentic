"""pr_sync.py and the driver's PR guard, run against a real bare remote and a fake `gh`.

The fixture mirrors per-task PRs to main: a run branch holds the queue, and four task branches
fork from main. After a human merges task-1 into main, task-2 conflicts with it in code; the
other branches only need the base merged in (their log.md and index.md edits go through the
OKF merge driver).

Run: python3 -m unittest discover -s .ai/scripts/tests
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import okf  # noqa: E402
from test_autonomy import FAKE_AGENT  # noqa: E402

FAKE_GH = """\
import json, sys
from pathlib import Path
state, log = Path({state!r}), Path({log!r})
args = sys.argv[1:]
with log.open("a") as handle:
    handle.write(json.dumps(args) + "\\n")
prs = json.loads(state.read_text())
if args[:2] == ["pr", "list"]:
    print(json.dumps(prs))
elif args[:2] == ["pr", "ready"]:
    for pr in prs:
        if str(pr["number"]) == args[2]:
            pr["isDraft"] = "--undo" in args
    state.write_text(json.dumps(prs))
"""

QUEUE = """
### T1 — First
- State: DONE
- Owner: agent@task-1
- Evidence: https://example.test/pr/1

### T2 — Second
- State: DONE
- Owner: agent@task-2
- Evidence: https://example.test/pr/2

### T3 — Third
- State: IN_PROGRESS
- Owner: agent@task-3

### T4 — Fourth
- State: DONE
- Owner: agent@task-4
- Evidence: https://example.test/pr/4
"""

PRS = [
    {"number": 2, "headRefName": "task-2", "baseRefName": "main", "isDraft": False},
    {"number": 3, "headRefName": "task-3", "baseRefName": "main", "isDraft": True},
    {"number": 4, "headRefName": "task-4", "baseRefName": "main", "isDraft": False},
    {"number": 5, "headRefName": "run", "baseRefName": "main", "isDraft": False},
    {"number": 9, "headRefName": "human", "baseRefName": "main", "isDraft": False},
]

DAY = "2026-10-13"


@unittest.skipUnless(shutil.which("git"), "git not installed")
class PrSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, root)
        self.root, self.repo, self.remote = root, root / "work", root / "remote.git"
        self.bundle = self.repo / "knowledge"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("OKF_", "GIT_"))}
        self.env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t", PYTHONDONTWRITEBYTECODE="1")
        self.gh_state, self.gh_log = root / "prs.json", root / "gh.jsonl"
        self.gh_state.write_text(json.dumps(PRS))
        (root / "gh.py").write_text(FAKE_GH.format(state=str(self.gh_state), log=str(self.gh_log)))
        self.env["OKF_GH"] = str(root / "gh")
        (root / "gh").write_text(f"#!/bin/sh\nexec {sys.executable} {root / 'gh.py'} \"$@\"\n")
        (root / "gh").chmod(0o755)

        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True)
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        scripts = self.repo / ".ai" / "scripts"
        scripts.mkdir(parents=True)
        for name in ("okf.py", "learning.py", "pr_sync.py", "autonomy_driver.py", "timed_check.py", "autonomy_progress.py", "autonomy_validation.py", "scratch.py", "review_guard.py", "ledger.py"):
            shutil.copy(SCRIPTS / name, scripts / name)
        self.okf("init", "--autonomous")  # also registers the merge driver
        # Keep the sync fixture independent of the initialization date.
        (self.bundle / "log.md").write_text("# OKF Change Log\n")
        (self.repo / "app.txt").write_text("one\ntwo\nthree\n")
        self.commit("base")
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "-q", "origin", "main")

        self.git("checkout", "-q", "-b", "run")
        self.append(okf.QUEUE_DOC, QUEUE)
        self.set_status("In flight", "T3 claimed")
        self.commit("run state")
        self.git("push", "-q", "origin", "run")

        self.task_branch("task-1", app="one-A", doc="t1")
        self.task_branch("task-2", app="one-B", doc="t2")  # same line as task-1: a real conflict once task-1 lands
        self.task_branch("task-3", doc="t3")
        self.task_branch("task-4", doc="t4")
        self.task_branch("human", app="one-H")

        # A human merges task-1's PR on main.
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "--no-edit", "task-1")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", "run")
        self.tips = {branch: self.rev(f"origin/{branch}") for branch in ("task-2", "task-3", "task-4", "human", "run")}

    # -- helpers -----------------------------------------------------------------------------

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=self.repo, env=self.env, capture_output=True, text=True, check=check)

    def rev(self, ref: str) -> str:
        return self.git("rev-parse", ref).stdout.strip()

    def is_ancestor(self, older: str, newer: str) -> bool:
        return self.git("merge-base", "--is-ancestor", older, newer, check=False).returncode == 0

    def okf(self, *args: str) -> str:
        result = self.script("okf.py", *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.repo / ".ai/scripts" / name), *args],
            cwd=self.repo, env=self.env, capture_output=True, text=True, check=False,
        )

    def append(self, rel: str, text: str) -> None:
        path = self.bundle / rel
        path.write_text(path.read_text() + text)

    def set_status(self, heading: str, body: str) -> None:
        path = self.bundle / okf.STATUS_DOC
        text = path.read_text()
        start = text.index(f"## {heading}\n")
        end = text.index("\n## ", start + 1) + 1
        path.write_text(text[:start] + f"## {heading}\n\n{body}\n\n" + text[end:])

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def task_branch(self, name: str, *, app: str | None = None, doc: str | None = None) -> None:
        self.git("checkout", "-q", "-b", name, "main")
        if app:
            (self.repo / "app.txt").write_text(f"{app}\ntwo\nthree\n")
        if doc:
            self.okf("log", f"Delivered {doc}.", "--date", DAY)
            self.okf("new", f"history/{doc}.md", "--type", "Historical Record", "--title", doc.upper(), "--description", f"{doc}.")
        self.commit(name)
        self.git("push", "-q", "origin", name)

    def gh_calls(self) -> list[list[str]]:
        if not self.gh_log.exists():
            return []
        return [json.loads(line) for line in self.gh_log.read_text().splitlines()]

    def mutations(self) -> list[list[str]]:
        return [call for call in self.gh_calls() if call[:2] != ["pr", "list"]]

    def show(self, ref: str, path: str) -> str:
        return self.git("show", f"{ref}:{path}").stdout

    # -- tests -------------------------------------------------------------------------------

    def test_sync_keeps_agent_prs_mergeable_and_returns_conflicts_to_draft(self) -> None:
        result = self.script("pr_sync.py")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "#2 task-2 <- main: conflicts: app.txt (returned to draft)",
                "#3 task-3 <- main: skipped (task IN_PROGRESS; its owner merges the base)",
                "#4 task-4 <- main: synced",
                "#5 run <- main: synced",
            ],
        )
        self.git("fetch", "-q", "origin")
        # task-4: main merged in on top of the old tip (no force-push); log and index merged per entry.
        self.assertTrue(self.is_ancestor("origin/main", "origin/task-4"))
        self.assertTrue(self.is_ancestor(self.tips["task-4"], "origin/task-4"))
        log = self.show("origin/task-4", "knowledge/log.md")
        self.assertEqual(log.count(f"## {DAY}"), 1)
        self.assertIn(f"## {DAY}\n\n- Delivered t4.\n- Delivered t1.", log)
        index = self.show("origin/task-4", "knowledge/history/index.md")
        self.assertIn("(t1.md)", index)
        self.assertIn("(t4.md)", index)
        self.assertNotIn("<<<<<<<", log + index)
        # task-2 conflicts in code only (its log and index merge cleanly): untouched, back to draft, explained.
        self.assertEqual(self.rev("origin/task-2"), self.tips["task-2"])
        self.assertIn(["pr", "ready", "2", "--undo"], self.mutations())
        comment = next(call for call in self.mutations() if call[:3] == ["pr", "comment", "2"])
        self.assertIn("`app.txt`", comment[-1])
        self.assertNotIn("log.md", comment[-1])
        # Skipped and foreign PRs are untouched.
        self.assertEqual(self.rev("origin/task-3"), self.tips["task-3"])
        self.assertEqual(self.rev("origin/human"), self.tips["human"])
        self.assertFalse(any("9" in call for call in self.mutations()))
        # The run branch merged main in place, stays pushed, and its checkpoint is still safe.
        self.assertEqual(self.rev("HEAD"), self.rev("origin/run"))
        self.assertTrue(self.is_ancestor("origin/main", "HEAD"))
        checks = {c.name: c for c in okf.checkpoint(self.bundle)}
        self.assertTrue(all(c.ok for c in checks.values()), {n: c.detail for n, c in checks.items() if not c.ok})
        self.assertTrue(checks["git HEAD"].ok)
        self.assertEqual(len(self.git("worktree", "list").stdout.splitlines()), 1)

        # A second pass changes nothing and asks gh for nothing new: #2 is already a draft.
        calls = len(self.mutations())
        again = self.script("pr_sync.py")
        self.assertEqual(again.returncode, 1)
        self.assertIn("#2 task-2 <- main: conflicts: app.txt", again.stdout)
        self.assertIn("#4 task-4 <- main: in sync", again.stdout)
        self.assertIn("#5 run <- main: in sync", again.stdout)
        self.assertEqual(len(self.mutations()), calls)

    def test_milestone_pr_without_task_owner_is_synced(self) -> None:
        self.git("branch", "milestone/m2", self.tips["task-4"])
        self.git("push", "-q", "origin", "milestone/m2")
        prs = [{"number": 6, "headRefName": "milestone/m2", "baseRefName": "main", "isDraft": True}]
        self.gh_state.write_text(json.dumps(prs))
        result = self.script("pr_sync.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "#6 milestone/m2 <- main: synced")
        self.git("fetch", "-q", "origin")
        self.assertTrue(self.is_ancestor("origin/main", "origin/milestone/m2"))
        self.assertTrue(self.is_ancestor(self.tips["task-4"], "origin/milestone/m2"))
        self.assertEqual(self.show("origin/milestone/m2", "app.txt"), "one-A\ntwo\nthree\n")
        self.assertIn("Delivered t4.", self.show("origin/milestone/m2", "knowledge/log.md"))
        self.assertTrue(json.loads(self.gh_state.read_text())[0]["isDraft"])
        self.assertEqual(self.mutations(), [])

    def test_dry_run_changes_nothing(self) -> None:
        head = self.rev("HEAD")
        result = self.script("pr_sync.py", "--dry-run")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("#2 task-2 <- main: conflicts: app.txt", result.stdout)
        self.assertIn("#4 task-4 <- main: would sync", result.stdout)
        self.assertIn("#5 run <- main: would sync", result.stdout)
        self.assertEqual(self.rev("HEAD"), head)
        self.git("fetch", "-q", "origin")
        self.assertEqual({b: self.rev(f"origin/{b}") for b in self.tips}, self.tips)
        self.assertEqual(self.mutations(), [])
        self.assertEqual(self.git("status", "--porcelain").stdout, "")

    def test_milestone_driver_does_not_sync_or_dispatch_other_milestones(self) -> None:
        self.git("branch", "milestone/m0", self.tips["task-2"])
        self.git("checkout", "-q", "-b", "milestone/m2", "run")
        self.git("push", "-q", "origin", "milestone/m0", "milestone/m2")
        unrelated_tip = self.rev("origin/milestone/m0")
        self.gh_state.write_text(json.dumps(PRS + [
            {"number": 6, "headRefName": "milestone/m0", "baseRefName": "main", "isDraft": False},
            {"number": 7, "headRefName": "milestone/m2", "baseRefName": "main", "isDraft": True},
        ]))
        agent, log = self.root / "agent.py", self.root / "sessions.jsonl"
        agent.write_text(FAKE_AGENT.format(scripts=str(SCRIPTS)))
        result = self.script("autonomy_driver.py", "--max-idle", "1", "--headless", "--",
                             sys.executable, str(agent), str(log), "idle")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("#7 milestone/m2 <- main: synced", result.stderr)
        self.assertNotIn("PR conflicts:", result.stderr)
        prompt = json.loads(log.read_text().splitlines()[0])["prompt"]
        self.assertIn("Branch: milestone/m2", prompt)
        self.assertNotIn("make these pull requests mergeable again", prompt)
        self.assertEqual(self.rev("origin/milestone/m0"), unrelated_tip)
        self.assertTrue(self.is_ancestor("origin/main", "origin/milestone/m2"))
        self.assertEqual(self.mutations(), [])

    def test_driver_puts_conflicts_first_and_fails_closed_without_gh(self) -> None:
        agent, log = self.root / "agent.py", self.root / "sessions.jsonl"
        agent.write_text(FAKE_AGENT.format(scripts=str(SCRIPTS)))
        run = lambda *options: self.script("autonomy_driver.py", *options, "--max-idle", "1", "--headless", "--", sys.executable, str(agent), str(log), "idle")
        result = run()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("driver: pr-sync: #2 task-2 <- main: conflicts: app.txt (returned to draft)", result.stderr)
        self.assertIn("(PR conflicts: #2)", result.stderr)  # pending work even though no task is READY
        prompt = json.loads(log.read_text().splitlines()[0])["prompt"]
        self.assertIn("Before any other work, make these pull requests mergeable again.", prompt)
        self.assertIn("- #2 task-2 <- main: conflicts: app.txt", prompt)

        self.env["OKF_GH"] = str(self.root / "missing-gh")
        failed = run()
        self.assertEqual(failed.returncode, 1)
        self.assertIn("driver: stop: PR sync failed: ", failed.stderr)
        self.assertIn("pass --no-pr-sync", failed.stderr)
        self.assertEqual(len(log.read_text().splitlines()), 1)  # no second session started


if __name__ == "__main__":
    unittest.main()
