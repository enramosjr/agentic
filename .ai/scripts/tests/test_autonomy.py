"""Behavioral tests for the work queue, checkpoint, handoff and autonomy hook.

Run: python3 -m unittest discover -s .ai/scripts/tests
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import okf  # noqa: E402
import autonomy_driver  # noqa: E402
import pr_sync  # noqa: E402

HAS_GIT = shutil.which("git") is not None

TASKS = """
## Tasks

```markdown
### EXAMPLE — Fenced examples are not tasks
- State: READY
```

### A — Foundation
- State: DONE
- Evidence: history/a.md

### B — Second
- State: NOT_READY
- Priority: 20
- Depends: A

### C — Third
- State: READY
- Priority: 10
- Depends: B

### D — Parent
- State: READY
- Depends: A

### D.1 — Child
- State: READY
- Parent: D
- Priority: 5
- Depends: A
"""


class AutonomyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.repo)
        self.bundle = self.repo / "knowledge"
        (self.repo / "AGENTS.md").write_text("# Agents\n")
        self.run_ok("init", "--autonomous")

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = okf.main(["--bundle", str(self.bundle), *argv])
        return code, out.getvalue(), err.getvalue()

    def run_ok(self, *argv: str) -> str:
        code, out, err = self.run_cli(*argv)
        self.assertEqual(code, 0, f"{argv} failed: {out}{err}")
        return out

    def append_tasks(self, text: str = TASKS) -> None:
        path = self.bundle / okf.QUEUE_DOC
        path.write_text(path.read_text() + text)

    def set_section(self, heading: str, body: str) -> None:
        path = self.bundle / okf.STATUS_DOC
        text = path.read_text()
        start = text.index(f"## {heading}\n")
        end = text.find("\n## ", start + 1)
        end = len(text) if end == -1 else end + 1
        path.write_text(text[:start] + f"## {heading}\n\n{body}\n\n" + text[end:])

    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
            check=True, capture_output=True,
        )

    def init_git(self) -> None:
        """A repository set up as `okf.py git-setup` leaves it, as a safe checkpoint requires."""
        self.git("init", "-q")
        self.run_ok("git-setup")

    def commit_all(self, message: str = "checkpoint", *, touch_status: bool = True) -> None:
        """Commit everything; a checkpoint commit also rewrites the status doc, as the protocol requires."""
        if touch_status:
            self.checkpoints = getattr(self, "checkpoints", 0) + 1
            self.set_section("In flight", f"{message} #{self.checkpoints}")
        self.git("add", "-A")
        self.git("commit", "-qm", message)


class QueueTests(AutonomyTestCase):
    def test_init_autonomous_creates_valid_templates_idempotently(self) -> None:
        for rel in (okf.QUEUE_DOC, okf.STATUS_DOC):
            self.assertTrue((self.bundle / rel).is_file())
        status_before = (self.bundle / okf.STATUS_DOC).read_text()
        self.run_ok("init", "--autonomous")
        self.assertEqual((self.bundle / okf.STATUS_DOC).read_text(), status_before)
        self.assertIn("requirement IDs, dependency waves and file/fixture owners", status_before)
        self.assertIn("integrated commit evidence shared by batch members", status_before)
        code, out, _ = self.run_cli("validate")
        self.assertEqual(code, 0, out)
        self.assertEqual(okf._status_sections(self.bundle).keys(), set(okf.STATUS_SECTIONS))
        self.assertNotIn("status body is", out)

    def test_oversized_status_warns_without_failing_validate(self) -> None:
        self.set_section("In flight", "Custody narrative. " * 400)
        code, out, _ = self.run_cli("validate")
        self.assertEqual(code, 0, out)
        self.assertIn(f"(budget {okf.STATUS_BUDGET_CHARS})", out)
        self.assertEqual(self.run_cli("validate", "--strict")[0], 1)

    def test_states_are_derived_from_dependencies_and_children(self) -> None:
        self.append_tasks()
        rows = {row["id"]: row["state"] for row in json.loads(self.run_ok("queue", "--json"))}
        self.assertNotIn("EXAMPLE", rows)
        # B's stored NOT_READY is recomputed: A is DONE. C waits on B even though it says READY.
        # D waits on its open child.
        self.assertEqual(rows, {"A": "DONE", "B": "READY", "C": "NOT_READY", "D": "NOT_READY", "D.1": "READY"})

    def test_next_orders_by_priority_and_skips_owned_tasks(self) -> None:
        self.append_tasks()
        self.assertEqual([r["id"] for r in json.loads(self.run_ok("queue", "--next", "--json"))], ["D.1", "B"])
        self.append_tasks("\n### E — Owned but not started\n- State: READY\n- Priority: 1\n- Owner: agent@branch\n")
        self.assertEqual([r["id"] for r in json.loads(self.run_ok("queue", "--next", "--json"))], ["D.1", "B"])

    def test_execution_hold_filters_dispatch_without_marking_work_done(self) -> None:
        self.append_tasks(TASKS.replace("### B — Second\n", "### B — Second\n- Hold: waiting for authorized model-backed case\n- Unblock: new case authorization\n"))
        self.assertEqual([row["id"] for row in json.loads(self.run_ok("queue", "--next", "--json"))], ["D.1"])
        rows = {row["id"]: row["state"] for row in json.loads(self.run_ok("queue", "--json"))}
        self.assertEqual(rows["B"], "READY")
        self.assertEqual(rows["C"], "NOT_READY")
        self.assertEqual(self.run_cli("validate")[0], 0)
        self.assertIn("Held: B", self.run_ok("handoff"))

    def test_execution_hold_needs_a_resume_condition_and_cannot_close_work(self) -> None:
        self.append_tasks("\n### HELD — Waiting\n- State: IN_PROGRESS\n- Owner: worker@held\n- Hold: qualification limit\n")
        code, out, _ = self.run_cli("validate")
        self.assertEqual(code, 1)
        self.assertIn("Hold requires Unblock", out)
        path = self.bundle / okf.QUEUE_DOC
        path.write_text(path.read_text().replace("- State: IN_PROGRESS", "- State: DONE\n- Evidence: log.md\n- Unblock: authorization"))
        self.assertIn("Hold applies only to unfinished", self.run_cli("validate")[1])

    def test_closing_children_makes_parent_ready(self) -> None:
        self.append_tasks()
        path = self.bundle / okf.QUEUE_DOC
        path.write_text(path.read_text().replace("- State: READY\n- Parent: D", "- State: DONE\n- Evidence: log.md\n- Parent: D"))
        self.assertIn("D", [r["id"] for r in json.loads(self.run_ok("queue", "--next", "--json"))])

    def test_validate_rejects_malformed_queue(self) -> None:
        self.append_tasks(
            "\n### X — Bad\n- State: WORKING\n"
            "\n### Y — Unknown dep\n- State: READY\n- Depends: NOPE\n- Priority: high\n"
            "\n### Z — Done without evidence\n- State: DONE\n"
            "\n### W — Blocked without detail\n- State: BLOCKED\n- Blocker: credentials\n"
            "\n### P — Cycle one\n- State: READY\n- Depends: Q\n"
            "\n### Q — Cycle two\n- State: READY\n- Depends: P\n"
            "\n### Y — Duplicate\n- State: READY\n"
        )
        code, out, _ = self.run_cli("validate")
        self.assertEqual(code, 1)
        for expected in (
            "X: State must be one of",
            "Y: unknown dependency NOPE",
            "Y: Priority must be an integer",
            "Z: DONE requires Evidence",
            "W: BLOCKED requires Unblock",
            "dependency cycle: P -> Q -> P",
            "duplicate task id Y",
        ):
            self.assertIn(expected, out)

    def test_missing_queue_names_the_fix(self) -> None:
        (self.bundle / okf.QUEUE_DOC).unlink()
        code, _, err = self.run_cli("queue")
        self.assertEqual(code, 1)
        self.assertIn("run `okf.py init --autonomous`", err)


class ArchiveTests(AutonomyTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.append_tasks(TASKS + "\n### E — Dropped\n- State: CANCELLED\n- Reason: superseded\n- Depends: B\n")

    def queue_text(self) -> str:
        return (self.bundle / okf.QUEUE_DOC).read_text()

    def archive_text(self) -> str:
        return (self.bundle / okf.ARCHIVE_DOC).read_text()

    def test_archive_moves_closed_tasks_and_keeps_references_resolvable(self) -> None:
        self.assertEqual(self.run_ok("queue", "--archive").strip(), "archived 2 task(s) to knowledge/project/work-queue-archive.md: A, E")
        self.assertNotIn("### A — Foundation", self.queue_text())
        self.assertNotIn("### E — Dropped", self.queue_text())
        self.assertIn("### EXAMPLE — Fenced examples are not tasks", self.queue_text())  # fenced, not a task
        self.assertIn("### B — Second\n- State: NOT_READY", self.queue_text())
        self.assertTrue(self.queue_text().endswith("- Depends: A\n"))
        self.assertIn("### A — Foundation\n- State: DONE\n- Evidence: history/a.md\n\n### E — Dropped", self.archive_text())
        self.assertTrue(self.archive_text().startswith("---\ntype: Work Queue Archive\n"))

        # A still satisfies B's dependency from the archive; the default listing omits archived tasks.
        rows = {row["id"]: row for row in json.loads(self.run_ok("queue", "--json"))}
        self.assertEqual(sorted(rows), ["B", "C", "D", "D.1"])
        self.assertEqual(rows["B"]["state"], "READY")
        done = json.loads(self.run_ok("queue", "--state", "DONE", "--json"))
        self.assertEqual([(row["id"], row["archived"]) for row in done], [("A", True)])
        code, out, _ = self.run_cli("validate")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.run_ok("queue", "--archive").strip(), "no DONE or CANCELLED tasks to archive")

    def test_archive_appends_in_closing_order(self) -> None:
        self.run_ok("queue", "--archive")
        path = self.bundle / okf.QUEUE_DOC
        path.write_text(path.read_text().replace("- State: READY\n- Parent: D", "- State: DONE\n- Evidence: log.md\n- Parent: D"))
        self.assertIn("D.1", self.run_ok("queue", "--archive"))
        archive = self.archive_text()
        self.assertLess(archive.index("### E — Dropped"), archive.index("### D.1 — Child"))
        # D's only child is archived and DONE, so the parent is READY.
        self.assertIn("D", [row["id"] for row in json.loads(self.run_ok("queue", "--next", "--json"))])
        self.assertEqual(self.run_cli("validate")[0], 0)

    def test_validate_rejects_open_archived_tasks_and_cross_file_duplicates(self) -> None:
        self.run_ok("queue", "--archive")
        archive = self.bundle / okf.ARCHIVE_DOC
        archive.write_text(archive.read_text() + "\n### R — Reopened\n- State: READY\n")
        self.append_tasks("\n### A — Reused ID\n- State: READY\n")
        code, out, _ = self.run_cli("validate")
        self.assertEqual(code, 1)
        self.assertIn("R: archived tasks must be DONE or CANCELLED, got 'READY'", out)
        self.assertIn("duplicate task id A (first at project/work-queue-archive.md line", out)

    def test_archive_refuses_a_queue_with_errors(self) -> None:
        self.append_tasks("\n### Z — Done without evidence\n- State: DONE\n")
        code, _, err = self.run_cli("queue", "--archive")
        self.assertEqual(code, 1)
        self.assertIn("queue has 1 error(s), first: Z: DONE requires Evidence", err)
        self.assertFalse((self.bundle / okf.ARCHIVE_DOC).exists())


@unittest.skipUnless(HAS_GIT, "git not installed")
class CheckpointAndHandoffTests(AutonomyTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.append_tasks()
        self.init_git()
        self.commit_all("init")

    def checks(self) -> dict[str, bool]:
        code, out, _ = self.run_cli("checkpoint", "--json")
        payload = json.loads(out)
        self.assertEqual(code, 0 if payload["safe"] else 1)
        return {c["name"]: c["ok"] for c in payload["checks"]}

    def test_committed_checkpoint_is_safe(self) -> None:
        self.assertTrue(all(self.checks().values()), self.run_cli("checkpoint")[1])

    def test_dirty_tree_is_unsafe_but_commit_age_does_not_require_status_churn(self) -> None:
        (self.repo / "AGENTS.md").write_text("# Agents\n\nEdited.\n")
        self.assertFalse(self.checks()["clean tree"])
        self.assertIn("1 uncommitted path(s), e.g. AGENTS.md", self.run_cli("checkpoint")[1])
        (self.repo / "work.txt").write_text("uncommitted\n")
        self.commit_all("work without updating status", touch_status=False)
        checks = self.checks()
        self.assertTrue(checks["clean tree"])
        self.assertTrue(all(checks.values()), self.run_cli("checkpoint")[1])
        self.assertIn("current HEAD available to handoff", self.run_cli("checkpoint")[1])
        self.assertIn("work without updating status", self.run_ok("handoff"))

    def test_missing_next_action_and_uncommitted_work_remain_unsafe(self) -> None:
        self.set_section("Next step", "")
        self.commit_all(touch_status=False)
        self.assertFalse(self.checks()["status"])
        self.assertIn("empty or missing sections: Next step", self.run_cli("checkpoint")[1])

    def test_oversized_status_is_not_a_safe_checkpoint(self) -> None:
        self.set_section("In flight", "Custody narrative. " * 400)
        self.commit_all(touch_status=False)
        self.assertFalse(self.checks()["status size"])
        self.assertIn(f"budget {okf.STATUS_BUDGET_CHARS}", self.run_cli("checkpoint")[1])
        self.set_section("In flight", "Compact current facts.")
        self.commit_all(touch_status=False)
        self.assertNotIn("status size", self.checks())

    def claim_d1(self) -> None:
        queue = self.bundle / okf.QUEUE_DOC
        queue.write_text(queue.read_text().replace("- State: READY\n- Parent: D", "- State: IN_PROGRESS\n- Owner: solo@work\n- Parent: D"))
        self.set_section("Active task", "D.1 — Child (solo@work)")
        self.commit_all(touch_status=False)

    def test_session_count_persists_in_the_queue_and_caps_at_three(self) -> None:
        self.claim_d1()
        for number in range(1, okf.SESSION_CAP + 1):
            self.assertIn(f"D.1: session {number} of {okf.SESSION_CAP}", self.run_ok("queue", "--record-session"))
        self.assertEqual((self.bundle / okf.QUEUE_DOC).read_text().count("- Sessions:"), 1)
        code, _, err = self.run_cli("queue", "--record-session")
        self.assertEqual(code, 1)
        self.assertIn("split it into separately gated tasks", err)
        self.commit_all(touch_status=False)
        self.assertNotIn("sessions", self.checks())
        queue = self.bundle / okf.QUEUE_DOC
        queue.write_text(queue.read_text().replace("- Sessions: 3", "- Sessions: 4"))
        self.commit_all(touch_status=False)
        self.assertFalse(self.checks()["sessions"])

    def test_acceptance_command_cap_fails_the_checkpoint(self) -> None:
        self.claim_d1()
        queue = self.bundle / okf.QUEUE_DOC
        commands = " ".join(f"`cargo test lane{i}`" for i in range(okf.ACCEPTANCE_COMMAND_CAP + 1))
        queue.write_text(queue.read_text().replace("- Owner: solo@work\n", f"- Owner: solo@work\n- Acceptance: {commands}\n"))
        self.commit_all(touch_status=False)
        self.assertFalse(self.checks()["acceptance commands"])

    def test_oversized_in_progress_task_is_not_a_safe_checkpoint(self) -> None:
        queue = self.bundle / okf.QUEUE_DOC
        text = queue.read_text()
        self.assertIn("- State: READY\n- Parent: D", text)
        queue.write_text(text.replace("- State: READY\n- Parent: D",
                                      "- State: IN_PROGRESS\n- Owner: solo@work\n- Parent: D\n- Notes: " + "acceptance lane. " * 250))
        self.commit_all(touch_status=False)
        self.assertFalse(self.checks()["task size"])
        self.assertIn("split it into separately gated tasks", self.run_cli("checkpoint")[1])

    def test_checkpoint_without_initial_commit_is_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            self.assertFalse(all(check.ok for check in okf.checkpoint(repo / "knowledge")))

    def test_active_task_must_be_in_progress(self) -> None:
        self.set_section("Active task", "B — Second")
        self.commit_all()
        self.assertFalse(self.checks()["active task"])
        path = self.bundle / okf.QUEUE_DOC
        path.write_text(path.read_text().replace("- State: NOT_READY\n- Priority: 20", "- State: IN_PROGRESS\n- Owner: agent@b\n- Priority: 20"))
        self.commit_all()
        self.assertTrue(all(self.checks().values()))

    def test_handoff_digest_prompt_and_task_brief(self) -> None:
        self.set_section("Next step", "Write the parser for B.")
        self.set_section("Key decisions", "Batch B,C; dependency B before C; owner parser.py: worker-b.")
        self.set_section("Last validation", "Focused parser checks PASS; full package suite deferred to integrated batch.")
        self.commit_all()
        digest = self.run_ok("handoff")
        self.assertIn("Startup: READY", digest)
        self.assertIn("Checkpoint: NOT AUDITED", digest)
        self.assertIn("Next READY: D.1 — Child [P5]; B — Second [P20]", digest)
        self.assertIn("Next step: Write the parser for B.", digest)

        prompt = self.run_ok("handoff", "--prompt")
        self.assertIn("Next step: Write the parser for B.", prompt)
        self.assertIn("This prompt is the startup handoff", prompt)
        self.assertIn("Session scope: one bounded integrated batch", prompt)
        self.assertIn(f"A batch has at most {okf.SESSION_CAP} sessions", prompt)
        self.assertIn("do not run a full gate merely to end a session", prompt)
        self.assertIn("A session boundary alone does not close a batch", prompt)
        self.assertIn("closed as DONE with scoped Evidence now", prompt)
        self.assertNotIn("evaluation feeding generation and correction", prompt)
        self.assertIn("this repository's objective, current roadmap, acceptance and queue", prompt)
        self.assertIn("Next READY: D.1 — Child; B — Second", prompt)
        self.assertIn("Do not start unrelated work or another batch in this session", prompt)
        self.assertIn("External prerequisites must be DONE", prompt)
        self.assertIn("unfinished prerequisites must be earlier members of this same batch", prompt)
        self.assertIn("Keep a task IN_PROGRESS until the gate covering its own acceptance passes", prompt)
        self.assertIn("Computed READY semantics stay unchanged", prompt)
        self.assertIn("full required commands once per integrated batch, deduplicated", prompt)
        self.assertIn("integrated commit as shared evidence for every batch member", prompt)
        self.assertIn("checkbox per requirement/task", prompt)
        self.assertNotIn("Role: orchestrator", prompt)
        orchestrator = self.run_ok("handoff", "--prompt", "--role", "orchestrator")
        self.assertIn("Role: orchestrator (.ai/agents/orchestrator.md). Session scope: one batch round.", orchestrator)
        self.assertIn("parallel only with disjoint files/fixtures and no dependency edge", orchestrator)
        self.assertIn("focused checks during implementation", orchestrator)

    def test_portable_prompt_uses_local_objective_and_bootstraps_without_an_extra_session(self) -> None:
        queue = self.bundle / okf.QUEUE_DOC
        queue.write_text(queue.read_text().removesuffix(TASKS))
        self.set_section("Objective", "M1 desktop: controller setup, scan, launch and return.")
        for role in ("solo", "orchestrator"):
            with self.subTest(role=role):
                prompt = self.run_ok("handoff", "--prompt", "--role", role)
                self.assertIn("Objective: M1 desktop: controller setup, scan, launch and return.", prompt)
                self.assertIn("Queue empty: bootstrap the first eligible flow", prompt)
                self.assertIn("then start implementation in this session", prompt)
                self.assertIn("do not end a records-only bootstrap session", prompt)
                self.assertNotIn("evaluation feeding", prompt)
                self.assertNotIn("delivery-batches.md", prompt)
                self.assertNotIn("Start with: python3 .ai/scripts/okf.py handoff", prompt)

    def test_task_brief_includes_scoped_batch_context(self) -> None:
        self.set_section("Key decisions", "Batch B,C; dependency B before C; owner parser.py: worker-b.")
        self.set_section("Last validation", "Focused parser checks PASS; full package suite deferred to integrated batch.")
        self.set_section("Next step", "Write the parser for B.")

        brief = self.run_ok("handoff", "--task", "C")
        self.assertIn("This brief replaces `okf.py context` and the autonomy protocol: skip both.", brief)
        self.assertIn("Do not open a task PR.", brief)
        self.assertIn("same milestone PR, titled M<N>: <Title>", brief)
        self.assertIn("It stays draft until the entire milestone passes review, validation", brief)
        self.assertIn("merge the assigned milestone branch into your branch (never rebase or force-push)", brief)
        self.assertIn("report their exact commands/outcomes and deferred full Validation commands", brief)
        self.assertIn("Do not mark tasks DONE or check completed PR requirements before the integrated gate passes", brief)
        self.assertIn("required full commands once at the integrated commit", brief)
        self.assertIn("Parallel work requires disjoint files/fixtures and no dependency edge", brief)
        self.assertIn("Batch context from the checkpoint (read-only)", brief)
        self.assertIn("Batch B,C; dependency B before C; owner parser.py: worker-b.", brief)
        self.assertIn("full package suite deferred to integrated batch", brief)
        self.assertIn("Next step: Write the parser for B.", brief)
        self.assertNotIn("Open your", brief)
        self.assertNotIn("task is DONE", brief)
        self.assertIn("assigned exactly one task: C — Third (state NOT_READY)", brief)
        self.assertIn("- Depends: B", brief)
        self.assertNotIn("### D", brief)
        code, _, err = self.run_cli("handoff", "--task", "NOPE")
        self.assertEqual(code, 1)
        self.assertIn("no task 'NOPE'", err)

    def test_handoff_reports_owned_dirty_work_without_demanding_startup_checkpoint(self) -> None:
        (self.repo / "work.txt").write_text("uncommitted\n")
        digest = self.run_ok("handoff")
        self.assertIn("Startup: READY", digest)
        self.assertIn("Uncommitted work: 1 uncommitted path(s)", digest)
        self.assertIn("inspect `git status` and `git diff`", digest)

    def test_handoff_does_not_run_document_audit_but_full_checkpoint_still_rejects_bad_docs(self) -> None:
        (self.bundle / "concepts" / "broken.md").write_text("# Missing required frontmatter\n")
        self.commit_all(touch_status=False)
        with mock.patch.object(okf, "validate", side_effect=AssertionError("startup must not audit documents")):
            self.assertIn("Startup: READY", self.run_ok("handoff"))
            self.assertIn("Startup: READY", self.run_ok("handoff", "--prompt"))
            self.assertIn("assigned exactly one task", self.run_ok("handoff", "--task", "B"))
        self.assertFalse(self.checks()["okf validate"])
        self.assertEqual(self.run_cli("checkpoint")[0], 1)


@unittest.skipUnless(HAS_GIT, "git not installed")
class HookTests(AutonomyTestCase):
    """Runs the hook as the harness does: a subprocess fed the event JSON on stdin."""

    def setUp(self) -> None:
        super().setUp()
        self.init_git()
        self.commit_all("init")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def hook(self, event: dict[str, object], **env: str) -> tuple[int, dict[str, object] | None]:
        environment = {k: v for k, v in os.environ.items() if not k.startswith("OKF_AUTONOMOUS")}
        environment.update(OKF_BUNDLE=str(self.bundle), TMPDIR=str(self.tmp), **env)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "autonomy_hook.py")],
            input=json.dumps(event), capture_output=True, text=True, env=environment, check=False,
        )
        return result.returncode, json.loads(result.stdout) if result.stdout.strip() else None

    def test_session_start_after_compaction_injects_checkpoint(self) -> None:
        self.append_tasks()
        self.commit_all("tasks")
        code, out = self.hook({"hook_event_name": "SessionStart", "source": "compact", "session_id": "s"})
        self.assertEqual(code, 0)
        context = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("Autonomous handoff", context)
        self.assertIn("Next READY: D.1 — Child", context)
        self.assertIn("Next step: Bootstrap the work queue", context)

    def test_session_start_without_queue_is_silent(self) -> None:
        (self.bundle / okf.QUEUE_DOC).unlink()
        self.assertEqual(self.hook({"hook_event_name": "SessionStart", "source": "startup"}), (0, None))

    def test_stop_is_opt_in(self) -> None:
        self.append_tasks()
        self.assertEqual(self.hook({"hook_event_name": "Stop", "session_id": "s"}), (0, None))

    def test_stop_allows_a_safe_checkpoint_even_while_work_remains(self) -> None:
        # Remaining READY work belongs to a fresh session, not to a longer one.
        self.append_tasks()
        self.commit_all("tasks")
        event = {"hook_event_name": "Stop", "session_id": "s", "stop_hook_active": False}
        self.assertEqual(self.hook(event, OKF_AUTONOMOUS="1"), (0, None))

    def test_stop_blocks_an_unsafe_checkpoint_and_respects_the_cap(self) -> None:
        self.append_tasks()  # uncommitted: the tree is dirty
        event = {"hook_event_name": "Stop", "session_id": "s", "stop_hook_active": False}
        code, out = self.hook(event, OKF_AUTONOMOUS="1", OKF_AUTONOMOUS_MAX_CONTINUES="2")
        self.assertEqual(code, 0)
        self.assertEqual(out["decision"], "block")
        self.assertIn("block 1/2): unsafe checkpoint: clean tree", out["reason"])
        self.assertIn("Then end the session; do not start new work", out["reason"])
        self.assertNotIn("READY", out["reason"])
        self.assertEqual(self.hook(event, OKF_AUTONOMOUS="1", OKF_AUTONOMOUS_MAX_CONTINUES="2")[1]["decision"], "block")
        self.assertEqual(self.hook(event, OKF_AUTONOMOUS="1", OKF_AUTONOMOUS_MAX_CONTINUES="2"), (0, None))

    def test_stop_allows_when_paused_on_background_work(self) -> None:
        self.append_tasks()
        event = {"hook_event_name": "Stop", "session_id": "s", "background_tasks": [{"id": "t"}]}
        self.assertEqual(self.hook(event, OKF_AUTONOMOUS="1"), (0, None))

    def test_stop_allows_when_nothing_is_actionable_and_checkpoint_is_safe(self) -> None:
        self.append_tasks("\n### A — Only\n- State: BLOCKED\n- Blocker: needs a credential\n- Unblock: human supplies it\n")
        self.commit_all("blocked")
        self.assertEqual(self.hook({"hook_event_name": "Stop", "session_id": "s"}, OKF_AUTONOMOUS="1"), (0, None))

    def test_stop_blocks_on_unsafe_checkpoint_even_without_tasks(self) -> None:
        (self.repo / "work.txt").write_text("uncommitted\n")
        code, out = self.hook({"hook_event_name": "Stop", "session_id": "s"}, OKF_AUTONOMOUS="1")
        self.assertEqual(out["decision"], "block")
        self.assertIn("unsafe checkpoint: clean tree", out["reason"])


FAKE_AGENT = """\
import json, os, subprocess, sys
from pathlib import Path
sys.path.insert(0, {scripts!r})
import okf

log, mode, prompt = Path(sys.argv[1]), sys.argv[2], sys.argv[-1]
with log.open("a") as handle:
    handle.write(json.dumps({{"prompt": prompt, "autonomous": os.environ.get("OKF_AUTONOMOUS"), "temp": [os.environ.get(k) for k in ("TMPDIR", "TMP", "TEMP")], "handoff": os.environ.get("OKF_HANDOFF_REQUEST")}}) + "\\n")
if mode == "fail":
    sys.exit(7)
if mode == "idle":
    sys.exit(0)
if mode == "audit-overlap" and len(log.read_text().splitlines()) == 1:
    import time
    deadline = time.monotonic() + 3
    while not log.with_suffix(".audit-started").exists():
        assert time.monotonic() < deadline, "audit process did not start"
        time.sleep(.01)
    (Path.cwd() / "feature.py").write_text("def identity(value): return value" + chr(10))
    log.with_suffix(".source-started").write_text("real source work began")
    while not log.with_suffix(".audit-finished").exists():
        assert time.monotonic() < deadline, "audit and worker did not overlap"
        time.sleep(.01)
    log.with_suffix(".audit-result-path").write_text(os.environ["OKF_DOCUMENT_AUDIT"])
if mode == "dispatch-first" and len(log.read_text().splitlines()) == 1:
    queue = Path.cwd() / "knowledge" / okf.QUEUE_DOC
    queue.write_text(queue.read_text().replace("- State: READY\\n- Parent: D", "- State: IN_PROGRESS\\n- Owner: worker@source\\n- Parent: D"))
    # The owned worker starts with a durable base plus an uncommitted coordinator claim.
    code = "import pathlib,subprocess; assert subprocess.check_output(['git','log','-1','--format=%s'],text=True).strip()=='init'; assert 'Owner: worker@source' in pathlib.Path('knowledge/project/work-queue.md').read_text(); pathlib.Path('feature.py').write_text('def identity(value): return value'+chr(10)); assert 'return value' in pathlib.Path('feature.py').read_text()"
    subprocess.run([sys.executable, "-c", code], check=True)
if mode in ("planning", "document-planning"):
    import time
    if mode == "document-planning":
        (Path.cwd() / "plan.md").write_text("More planning, no implementation\\n")
    while not Path(os.environ["OKF_PROGRESS_REQUEST"]).exists():
        time.sleep(.01)
    assert not Path(os.environ["OKF_HANDOFF_REQUEST"]).exists(), "progress query incorrectly retired the worker"
    time.sleep(.4)  # continue investigation beyond the old discovery + handoff cutoff
    (Path.cwd() / "investigated.py").write_text("def identity(value): return value" + chr(10))
if mode.startswith("repair-"):
    launch = len(log.read_text().splitlines())
    marker = log.with_suffix(".gate-runs")
    feature = Path.cwd() / "feature.py"
    checkpoint_mode = mode in ("repair-checkpoint", "repair-retain-stall")
    if checkpoint_mode and launch == 2:
        feature.write_text("first=1\\nsecond=0\\npending=1\\n")
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "source checkpoint before validation"], check=True)
        sys.exit(0)
    step = launch - 1 if checkpoint_mode and launch > 2 else launch
    if step <= 3 or (mode == "repair-retain-stall" and launch == 5):
        value = "first=0\\nsecond=0\\n" if step == 1 else ("first=1\\nsecond=0\\n" if step == 2 else "first=1\\nsecond=1\\n")
        if mode != "repair-records" or launch == 1:
            feature.write_text(value)
        else:
            (Path.cwd() / "repair.md").write_text("claimed repair, unchanged source")
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "--allow-empty", "-qm", "candidate"], check=True)
        gate = "from pathlib import Path; p=Path(" + repr(str(marker)) + "); p.write_text(p.read_text()+'run' if p.exists() else 'run'); " + "v={{}}; exec(Path('feature.py').read_text(),v); assert v['first']==1; assert v['second']==1"
        value = {{"requirements": ["D.1"], "commands": [{{"label": "gate", "argv": [sys.executable, "-c", gate], "timeout_seconds": 2, "coverage": ["D.1"]}}]}}
        if step > 1 and not (mode == "repair-retain-stall" and launch == 5):
            previous = log.with_suffix(".result-path").read_text()
            key = "first" if step == 2 else "second"
            check = "from pathlib import Path; v={{}}; exec(Path('feature.py').read_text(),v); assert v[" + repr(key) + "]==" + ("2" if mode == "repair-bad-proof" else "1")
            value["commands"].insert(0, {{"label": "fixed-regression", "argv": [sys.executable, "-c", check], "timeout_seconds": 2, "coverage": ["D.1"]}})
            value["commands"][1]["after"] = ["fixed-regression"]
            value["repair"] = {{"failed_result": previous, "regression": "fixed-regression", "review": "independent source review retained for " + key}}
        plan_path = log.with_suffix(".plan.json")
        plan_path.write_text(json.dumps(value))
        subprocess.run([sys.executable, str(Path({scripts!r}) / "autonomy_validation.py"), "submit", "--plan", str(plan_path)], check=True)
        log.with_suffix(".result-path").write_text(str(Path(os.environ["OKF_VALIDATION_REQUEST"]).with_name("result.json")))
        sys.exit(0)
    result = json.loads(Path(log.with_suffix(".result-path").read_text()).read_text())
    assert result["state"] == "PASS", result
    queue = Path.cwd() / "knowledge" / okf.QUEUE_DOC
    queue.write_text(queue.read_text().replace("- State: NOT_READY", "- State: DONE\\n- Evidence: log.md").replace("- State: READY", "- State: DONE\\n- Evidence: log.md"))
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "reviewed integrated PASS delivery"], check=True)
    sys.exit(0)
if mode.startswith("validation"):
    launch = len(log.read_text().splitlines())
    if mode == "validation-closure-after-stall" and launch == 1:
        (Path.cwd() / "implementation.py").write_text("def identity(value): return value")
        git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "focused implementation before integrated gate"], check=True)
        sys.exit(0)
    if os.environ.get("OKF_AUTONOMOUS_RECOVERY") == "1":
        git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "--allow-empty", "-qm", "settle closure ownership"], check=True)
        sys.exit(0)
    if mode == "validation-slow-closure" and launch == 2:
        import time
        time.sleep(.4)  # acceptance result review outlives discovery's advisory query
        assert not Path(os.environ["OKF_HANDOFF_REQUEST"]).exists(), "closure reused discovery timer"
    if mode == "validation-environment" and launch == 2:
        import time
        time.sleep(.8)  # environment-only recovery needs no fabricated source edits
        log.with_suffix(".first-result-path").write_text(log.with_suffix(".result-path").read_text())
        plan_path = log.with_suffix(".plan.json")
        value = json.loads(plan_path.read_text())
        value["commands"][0]["env"] = {{"QUALIFICATION_READY": "yes"}}
        plan_path.write_text(json.dumps(value))
        subprocess.run([sys.executable, str(Path({scripts!r}) / "autonomy_validation.py"), "submit", "--plan", str(plan_path)], check=True)
        log.with_suffix(".result-path").write_text(str(Path(os.environ["OKF_VALIDATION_REQUEST"]).with_name("result.json")))
        sys.exit(0)
    if launch == 1 or (mode == "validation-closure-after-stall" and launch == 2) or mode == "validation-repeat":
        plan_path = log.with_suffix(".plan.json")
        marker = log.with_suffix(".validated")
        code = "import pathlib,time,sys; time.sleep(.8); pathlib.Path(" + repr(str(marker)) + ").write_text('actual assertion passed'); print('private command output')"
        timeout = 1.5
        if mode == "validation-budget":
            timeout = 20
        if mode == "validation-fail":
            code = "import sys; print('actual failed assertion', file=sys.stderr); sys.exit(7)"
        if mode == "validation-environment":
            code = "import os,sys; sys.exit(0 if os.environ.get('QUALIFICATION_READY')=='yes' else 7)"
        if mode == "validation-timeout":
            code = "import pathlib,subprocess,sys,time; c=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); pathlib.Path(" + repr(str(log.with_suffix('.test.pid'))) + ").write_text(str(c.pid)); time.sleep(60)"
            timeout = .2
        if mode == "validation-mutate":
            code = "import pathlib; pathlib.Path('unexpected.rs').write_text('source changed')"
        if mode == "validation-repeat":
            code = "print('same passing command, no delivery')"
            timeout = .2
        plan_path.write_text(json.dumps({{"requirements": ["D.1"], "commands": [{{"label": "public-contract", "argv": [sys.executable, "-c", code], "timeout_seconds": timeout, "coverage": ["D.1"]}}]}}))
        subprocess.run([sys.executable, str(Path({scripts!r}) / "autonomy_validation.py"), "submit", "--plan", str(plan_path)], check=True)
        log.with_suffix(".result-path").write_text(str(Path(os.environ["OKF_VALIDATION_REQUEST"]).with_name("result.json")))
        sys.exit(0)
    result = json.loads(Path(log.with_suffix(".result-path").read_text()).read_text())
    assert result["state"] == ({{"validation-fail": "FAIL", "validation-timeout": "TIMED_OUT"}}.get(mode, "PASS")), result
    if mode in ("validation-fail", "validation-timeout"):
        sys.exit(0)
    if mode == "validation-closure-no-delivery" and launch == 2:
        import time
        time.sleep(60)
if mode in ("rotate", "recover", "crash", "unsafe-recovery", "stuck-recovery"):
    import time
    launch = len(log.read_text().splitlines())
    recovering = os.environ.get("OKF_AUTONOMOUS_RECOVERY") == "1"
    if launch == 1:
        (Path.cwd() / "unfinished.txt").write_text("preserved implementation\\n")
        if mode == "crash":
            log.with_suffix(".pid").write_text("999999999")
            sys.exit(7)
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(.4 if " + repr(mode == "rotate") + " else 60)"])
        log.with_suffix(".pid").write_text(str(child.pid))
        if mode == "rotate":
            request = Path(os.environ["OKF_HANDOFF_REQUEST"])
            while not request.exists():
                time.sleep(.01)
            child.wait(timeout=2)
            (Path.cwd() / "check-result.txt").write_text("current check completed successfully\\n")
        else:
            time.sleep(60)
    elif recovering:
        pid = log.with_suffix(".pid").read_text()
        proc = Path("/proc/" + pid + "/stat")
        assert not proc.exists() or proc.read_text().split()[2] == "Z", "previous owner still running"
        assert (Path.cwd() / "unfinished.txt").read_text() == "preserved implementation\\n"
        if mode == "unsafe-recovery":
            sys.exit(0)
        if mode == "stuck-recovery":
            time.sleep(60)
    if launch == 1 or recovering:
        status = Path.cwd() / "knowledge" / okf.STATUS_DOC
        status.write_text(status.read_text().replace("## In flight\\n", "## In flight\\n\\nunfinished work preserved; resume focused checks\\n", 1))
        git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "wip: safe handoff"], check=True)
        sys.exit(0)
if mode == "hang":
    import time
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    log.with_suffix(".pid").write_text(str(child.pid))
    time.sleep(60)
if mode == "churn":
    (Path.cwd() / "implementation.py").write_text(str(len(log.read_text().splitlines())))
    status = Path.cwd() / "knowledge" / okf.STATUS_DOC
    status.write_text(status.read_text().replace("## In flight\\n", "## In flight\\n\\nmore repairs, no delivery\\n", 1))
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-qm", "more repairs, no delivery"], check=True)
    sys.exit(0)
if mode == "records-only":
    status = Path.cwd() / "knowledge" / okf.STATUS_DOC
    status.write_text(status.read_text().replace("## In flight\\n", "## In flight\\n\\nTry later; no source work performed\\n", 1))
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "defer without useful work"], check=True)
    sys.exit(0)
if mode == "bootstrap":
    assert "then start implementation in this session" in prompt
    assert "Objective: Desktop controller flow" in prompt
    assert "evaluation feeding" not in prompt
    queue = Path.cwd() / "knowledge" / okf.QUEUE_DOC
    queue.write_text(queue.read_text() + "\\n### DESKTOP.FLOW — Controller flow\\n- State: READY\\n")
    (Path.cwd() / "feature.py").write_text("def resume_selection(): return 'recent'\\n")
    subprocess.run([sys.executable, "-c", "import feature; assert feature.resume_selection() == 'recent'"], check=True)
if mode == "hold-after-preflight":
    queue = Path.cwd() / "knowledge" / okf.QUEUE_DOC
    queue.write_text(queue.read_text() + "- Hold: no native host available\\n- Unblock: native host supplied\\n")
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-qm", "record newly discovered execution hold"], check=True)
    sys.exit(0)
# Simulate an agent closing a single-member or two-member integrated batch; the driver only owns session boundaries.
bundle = Path.cwd() / "knowledge"
_, tasks = okf._load_queue(bundle)
task = next((task for task in tasks if task.state == "IN_PROGRESS" and not task.get("Hold")), None) or okf.next_tasks(tasks)[0]
queue = bundle / okf.QUEUE_DOC
members = (["D.1", "D"] if task.id == "D.1" else ["B", "C"]) if mode == "batch" else [task.id]
# Claims remain IN_PROGRESS through provisional work; simulate the integrated gate before closing all members.
for member in members:
    _, tasks = okf._load_queue(bundle)
    task = next(t for t in tasks if t.id == member)
    lines = queue.read_text().split("\\n")
    state = next(i for i in range(task.line, len(lines)) if lines[i].startswith("- State:"))
    lines[state:state + 1] = ["- State: IN_PROGRESS", "- Owner: test-agent@batch"]
    queue.write_text("\\n".join(lines))
assert all(okf.effective_states(okf._load_queue(bundle)[1])[member] == "IN_PROGRESS" for member in members)
for member in members:
    _, tasks = okf._load_queue(bundle)
    task = next(t for t in tasks if t.id == member)
    lines = queue.read_text().split("\\n")
    state = next(i for i in range(task.line, len(lines)) if lines[i].startswith("- State:"))
    assert lines[state + 1] == "- Owner: test-agent@batch"
    lines.pop(state + 1)
    lines[state:state + 1] = ["- State: DONE", "- Evidence: log.md"]
    queue.write_text("\\n".join(lines))
closed = ", ".join(members)
status = bundle / okf.STATUS_DOC
status.write_text(status.read_text().replace("## In flight\\n", "## In flight\\n\\nclosed " + closed + "\\n", 1))
git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
subprocess.run(git + ["add", "-A"], check=True)
subprocess.run(git + ["commit", "-qm", "close " + closed], check=True)
closure_launch = 3 if mode == "validation-closure-after-stall" else 2
if mode.startswith("validation-closure-") and len(log.read_text().splitlines()) == closure_launch:
    import time
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if mode not in ("validation-closure-unreleased", "validation-closure-after-stall"):
        receipt = {{"head": head, "external_workers_released": True}}
        if mode == "validation-closure-stale":
            receipt["head"] = "stale-head"
        Path(os.environ["OKF_CLOSURE_RELEASE"]).write_text(json.dumps(receipt))
    if mode == "validation-closure-dirty":
        (Path.cwd() / "unfinished.py").write_text("preserved implementation")
    if mode == "validation-closure-external":
        registry = Path(os.environ["OKF_WORK_REGISTRY"])
        rows = json.loads(registry.read_text())
        rows["unreleased-external-worktree"] = head
        registry.write_text(json.dumps(rows))
    time.sleep(60)
"""


@unittest.skipUnless(HAS_GIT, "git not installed")
class DriverTests(AutonomyTestCase):
    """Runs autonomy_driver.py as a CLI against a scripted agent that really edits and commits."""

    def setUp(self) -> None:
        super().setUp()
        self.append_tasks()
        self.init_git()
        self.commit_all("init")
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.agent = self.tmp / "agent.py"
        self.agent.write_text(FAKE_AGENT.format(scripts=str(SCRIPTS)))
        self.log = self.tmp / "sessions.jsonl"

    def drive(self, mode: str, *options: str) -> subprocess.CompletedProcess[str]:
        environment = {k: v for k, v in os.environ.items() if not k.startswith("OKF_AUTONOMOUS")}
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "autonomy_driver.py"), "--bundle", str(self.bundle), "--no-pr-sync", "--headless", *options,
             "--", sys.executable, str(self.agent), str(self.log), mode],
            capture_output=True, text=True, env=environment, check=False,
            timeout=15,
        )

    def sessions(self) -> list[dict[str, str]]:
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_runs_fresh_sessions_for_single_member_batches_until_nothing_is_actionable(self) -> None:
        result = self.drive("work")
        self.assertEqual(result.returncode, 0, result.stderr)
        sessions = self.sessions()
        # D.1 (P5), B (P20), then C (P10, after B) and D (after its child): four sessions, four commits.
        self.assertEqual(len(sessions), 4)
        timings = [json.loads(line.removeprefix("timing: ")) for line in result.stderr.splitlines()
                   if line.startswith("timing: ")]
        self.assertEqual(len(timings), len(sessions))
        self.assertEqual([entry["label"] for entry in timings],
                         [f"agent-session-{number}" for number in range(1, 5)])
        self.assertTrue(all(entry["exit_code"] == 0 and entry["outcome"] == "PASS" for entry in timings))
        self.assertNotIn("Session scope:", "\n".join(line for line in result.stderr.splitlines()
                                                   if line.startswith("timing: ")))
        self.assertTrue(all(s["autonomous"] == "1" for s in sessions))
        self.assertIn("Session scope: one bounded integrated batch", sessions[0]["prompt"])
        self.assertIn("Startup: READY", sessions[0]["prompt"])
        self.assertIn("HEAD: ", sessions[1]["prompt"])
        self.assertIn("close D.1", sessions[1]["prompt"])  # each prompt reflects the previous session's commit
        self.assertIn("driver: session 1/20 (READY: D.1, B)", result.stderr)
        self.assertIn("driver: stop: no READY or IN_PROGRESS task, no PR conflicts, and the checkpoint is safe", result.stderr)
        self.assertEqual(json.loads(self.run_ok("queue", "--next", "--json")), [])
        self.assertTrue(all(c.ok for c in okf.checkpoint(self.bundle)))

    def test_inherited_system_temp_is_replaced_for_agents_and_handoff(self) -> None:
        with mock.patch.dict(os.environ, {"TMPDIR": "/tmp", "TMP": "/tmp", "TEMP": "/tmp"}):
            result = self.drive("work")
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = self.repo / ".git" / "okf-scratch"
        self.assertTrue(self.sessions())
        for session in self.sessions():
            self.assertEqual(session["temp"], [str(expected)] * 3)
            self.assertEqual(Path(session["handoff"]).parent.parent, expected)
            self.assertIn("Do not use /tmp", session["prompt"])
        self.assertIn(f"Disk-backed scratch: {expected}", result.stderr)
        self.assertIn("GiB available", result.stderr)

    def test_one_session_can_close_multiple_related_tasks_then_resume_fresh(self) -> None:
        result = self.drive("batch")
        self.assertEqual(result.returncode, 0, result.stderr)
        sessions = self.sessions()
        self.assertEqual(len(sessions), 2)
        self.assertIn("close D.1, D", sessions[1]["prompt"])
        self.assertIn("Startup: READY", sessions[1]["prompt"])
        rows = json.loads(self.run_ok("queue", "--json"))
        self.assertTrue(all(row["state"] == "DONE" for row in rows), rows)
        self.assertEqual(json.loads(self.run_ok("queue", "--next", "--json")), [])
        self.assertTrue(all(c.ok for c in okf.checkpoint(self.bundle)))
        self.assertIn("driver: stop: no READY or IN_PROGRESS task", result.stderr)

    def test_source_dispatch_does_not_require_a_planning_or_claim_commit(self) -> None:
        result = self.drive("dispatch-first")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.repo / "feature.py").read_text(), "def identity(value): return value\n")
        self.assertNotIn("recovery session", result.stderr)
        self.assertTrue(all(check.ok for check in okf.checkpoint(self.bundle)))
        history = subprocess.check_output(["git", "-C", str(self.repo), "log", "--format=%s"], text=True)
        self.assertEqual(len(history.splitlines()), 5)  # initial base + four actual work/closure commits
        self.assertIn("without a planning/claim commit", self.sessions()[0]["prompt"])

    def test_empty_queue_bootstraps_and_implements_in_one_driver_session(self) -> None:
        queue = self.bundle / okf.QUEUE_DOC
        queue.write_text(queue.read_text().removesuffix(TASKS))
        self.set_section("Objective", "Desktop controller flow")
        self.commit_all("empty queue")
        result = self.drive("bootstrap", "--max-sessions", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.sessions()), 1)
        self.assertTrue((self.repo / "feature.py").exists())
        rows = json.loads(self.run_ok("queue", "--json"))
        self.assertEqual([(row["id"], row["state"]) for row in rows], [("DESKTOP.FLOW", "DONE")])
        self.assertTrue(all(check.ok for check in okf.checkpoint(self.bundle)))

    def configure_held_queue(self, held=True, other=False):
        path = self.bundle / okf.QUEUE_DOC
        text = path.read_text().removesuffix(TASKS)
        text += "\n### HELD — Unfinished validation\n- State: IN_PROGRESS\n- Owner: worker@held\n"
        if held:
            text += "- Hold: model-backed case allowance exhausted\n- Unblock: authorized new case\n"
        if other:
            text += "\n### OTHER — Independent work\n- State: READY\n"
        path.write_text(text)
        self.set_section("Active task", "HELD — worker@held")
        self.commit_all("execution eligibility")

    def configure_capped_task(self, sessions: int) -> None:
        path = self.bundle / okf.QUEUE_DOC
        text = path.read_text().removesuffix(TASKS)
        text += f"\n### BIG — Oversized batch\n- State: IN_PROGRESS\n- Owner: solo@run\n- Sessions: {sessions}\n"
        path.write_text(text)
        self.set_section("Active task", "BIG — solo@run")
        self.commit_all("claim BIG")

    def test_driver_refuses_a_task_at_the_session_cap_whatever_flags_are_passed(self) -> None:
        self.configure_capped_task(okf.SESSION_CAP)
        result = self.drive("work", "--max-stalled", "4", "--max-sessions", "50", "--max-idle", "50")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.sessions(), [])
        self.assertIn(f"task BIG has used {okf.SESSION_CAP} implementation sessions", result.stderr)
        self.assertIn("Raising --max-* flags does not reset this count", result.stderr)

    def test_driver_counts_each_implementation_session_in_the_queue(self) -> None:
        self.configure_capped_task(1)
        self.drive("fail")
        # The failed session is followed by one records-recovery session, which is not counted.
        self.assertIn("- Sessions: 2\n", (self.bundle / okf.QUEUE_DOC).read_text())

    def test_preflight_does_not_launch_a_model_for_held_in_progress_work(self) -> None:
        self.configure_held_queue()
        result = self.drive("fail")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.sessions(), [])
        self.assertIn("no executable task", result.stderr)
        self.assertIn("authorized new case", result.stderr)

    def test_execution_hold_does_not_stop_independent_ready_work(self) -> None:
        self.configure_held_queue(other=True)
        result = self.drive("work")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.sessions()), 1)
        rows = {row["id"]: row["state"] for row in json.loads(self.run_ok("queue", "--json"))}
        self.assertEqual(rows, {"HELD": "IN_PROGRESS", "OTHER": "DONE"})
        self.assertIn("Execution holds: HELD", self.sessions()[0]["prompt"])
        self.assertIn("ordinary deterministic CI failures", self.sessions()[0]["prompt"])

    def test_newly_recorded_hold_stops_before_repeating_blocker_checks(self) -> None:
        self.configure_held_queue(held=False)
        result = self.drive("hold-after-preflight", "--max-idle", "10", "--max-stalled", "4")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.sessions()), 1)
        self.assertIn("no executable task", result.stderr)
        self.assertNotIn("session 2/", result.stderr)

    def test_stall_limit_above_the_cap_is_rejected_before_any_session(self) -> None:
        self.configure_held_queue(held=False)
        result = self.drive("hold-after-preflight", "--max-stalled", "20")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("--max-stalled above 4 is rejected", result.stderr)
        self.assertEqual(len(self.sessions()), 0)

    def test_background_audit_and_actual_source_worker_overlap(self) -> None:
        audit_script = self.tmp / "slow_audit.py"
        audit_script.write_text("import pathlib,time\n"
                                + "root=pathlib.Path(" + repr(str(self.log)) + ")\n"
                                + "root.with_suffix('.audit-started').write_text('audit running')\n"
                                + "deadline=time.monotonic()+3\n"
                                + "while not root.with_suffix('.source-started').exists():\n"
                                + " assert time.monotonic()<deadline, 'worker was blocked on audit'\n time.sleep(.01)\n"
                                + "root.with_suffix('.audit-finished').write_text('audit observed real source work')\n")
        original = autonomy_driver.documentation_audit
        def controlled_audit(*args, **kwargs):
            return original(*args, **kwargs, command=[sys.executable, str(audit_script)])
        with mock.patch.object(autonomy_driver, "documentation_audit", controlled_audit):
            code = autonomy_driver.drive(self.bundle, [sys.executable, str(self.agent), str(self.log), "audit-overlap"],
                                         "solo", 10, 2, None, max_run_seconds=10, handoff_seconds=1)
        self.assertEqual(code, 0)
        self.assertTrue((self.repo / "feature.py").exists())
        audit = json.loads(Path(self.log.with_suffix(".audit-result-path").read_text()).read_text())
        self.assertEqual(audit["state"], "PASS")
        self.assertTrue(audit["advisory"])
        self.assertTrue(all(check.ok for check in okf.checkpoint(self.bundle)))

    def test_unfinished_background_audit_is_reaped_at_session_end(self) -> None:
        directory = self.tmp / "audit"
        directory.mkdir()
        pid_file = directory / "child.pid"
        command = [sys.executable, "-c", "import subprocess,sys,pathlib,time; c=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); pathlib.Path(" + repr(str(pid_file)) + ").write_text(str(c.pid)); time.sleep(60)"]
        with autonomy_driver.documentation_audit(self.bundle, directory, lambda *args: None, command=command):
            deadline = time.monotonic() + 3
            while not pid_file.exists():
                self.assertLess(time.monotonic(), deadline)
                time.sleep(.01)
        self.assertEqual(json.loads((directory / "documentation-audit.json").read_text())["state"], "CANCELLED")
        proc = Path("/proc") / pid_file.read_text() / "stat"
        self.assertTrue(not proc.exists() or proc.read_text().split()[2] == "Z")

    def test_conflict_brief_requalifies_integrated_batches_and_preserves_milestone_gate(self) -> None:
        brief = autonomy_driver.conflict_brief([pr_sync.Result(7, "milestone/m2", "main", "conflicts")])
        self.assertIn("#7", brief)
        self.assertIn("never rebase or force-push", brief)
        self.assertIn("resolve conflicts with focused checks", brief)
        self.assertIn("full Validation commands once per integrated batch, deduplicated", brief)
        self.assertIn("integrated commit", brief)
        self.assertIn("reopen invalidated requirement checkboxes", brief)
        self.assertIn("keep the milestone PR draft until its entire scope passes", brief)

    def test_driver_help_describes_batch_session_scope(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "autonomy_driver.py"), "--help"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("one bounded integrated batch (solo) or batch round", " ".join(result.stdout.split()))

    def test_orchestrator_role_reaches_the_prompt(self) -> None:
        self.drive("fail", "--role", "orchestrator")
        self.assertIn("Role: orchestrator (.ai/agents/orchestrator.md)", self.sessions()[0]["prompt"])

    def test_stops_when_sessions_make_no_progress(self) -> None:
        result = self.drive("idle", "--max-idle", "2")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.sessions()), 2)
        self.assertIn("2 session(s) made no source progress or evidenced delivery", result.stderr)

    def test_commits_without_delivery_do_not_reset_the_circuit_breaker(self) -> None:
        result = self.drive("churn")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len(self.sessions()), 2)
        self.assertTrue((self.repo / "implementation.py").exists())
        self.assertIn("2 session(s) delivered no evidenced DONE task", result.stderr)
        self.assertEqual(autonomy_driver.delivery_marker(self.bundle), {"A"})

    def test_records_only_commits_cannot_reset_idle_limit(self) -> None:
        result = self.drive("records-only")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len(self.sessions()), 2)
        self.assertIn("records-only commits do not reset this limit", result.stderr)
        self.assertEqual(autonomy_driver.delivery_marker(self.bundle), {"A"})

    def test_session_and_run_deadlines_stop_hung_agent_and_descendant(self) -> None:
        for session_limit, run_limit, launches in ((.2, 10, 2), (10, .5, 1)):
            with self.subTest(session_limit=session_limit, run_limit=run_limit):
                previous = len(self.sessions())
                result = self.drive("hang", "--max-session-seconds", str(session_limit),
                                    "--handoff-seconds", ".2", "--max-run-seconds", str(run_limit))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(len(self.sessions()), previous + launches)
                self.assertIn("owned process group stopped", result.stderr)
                self.assertIn('"exit_code": 124', result.stderr)
                pid = int(self.log.with_suffix(".pid").read_text())
                proc = Path(f"/proc/{pid}/stat")
                if proc.exists():
                    self.assertEqual(proc.read_text().split()[2], "Z", "agent descendant is still running")

    def test_checkpoint_window_finishes_current_check_then_continues_fresh(self) -> None:
        events = self.tmp / "progress.jsonl"
        result = self.drive("rotate", "--max-session-seconds", ".2", "--handoff-seconds", "1",
                            "--heartbeat-seconds", ".05", "--progress-file", str(events))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.sessions()), 5)
        self.assertTrue((self.repo / "check-result.txt").exists())
        self.assertIn("wip: safe handoff", self.sessions()[1]["prompt"])
        self.assertNotIn('"exit_code": 124', result.stderr)
        public = [json.loads(line) for line in events.read_text().splitlines()]
        self.assertTrue(any(event["kind"] == "handoff" and "tasks remaining" in event["text"] for event in public))
        self.assertTrue(all(check.ok for check in okf.checkpoint(self.bundle)))

    def test_timeout_recovers_dirty_work_before_replacement_and_finishes_queue(self) -> None:
        result = self.drive("recover", "--max-session-seconds", ".2", "--handoff-seconds", ".5")
        self.assertEqual(result.returncode, 0, result.stderr)
        sessions = self.sessions()
        self.assertEqual(len(sessions), 6)
        self.assertIn("RECOVERY ONLY", sessions[1]["prompt"])
        self.assertIn("Uncommitted work:", sessions[1]["prompt"])
        self.assertIn("wip: safe handoff", sessions[2]["prompt"])
        self.assertIn("Startup: READY", sessions[2]["prompt"])
        self.assertIn("Safe handoff; next session resumes", result.stderr)
        self.assertEqual((self.repo / "unfinished.txt").read_text(), "preserved implementation\n")
        self.assertEqual(json.loads(self.run_ok("queue", "--next", "--json")), [])
        self.assertTrue(all(check.ok for check in okf.checkpoint(self.bundle)))

    def test_failed_recovery_cannot_loop_or_launch_over_unsafe_work(self) -> None:
        for mode in ("unsafe-recovery", "stuck-recovery"):
            with self.subTest(mode=mode):
                self.log.unlink(missing_ok=True)
                result = self.drive(mode, "--max-session-seconds", ".2", "--handoff-seconds", ".4")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(len(self.sessions()), 2)
                self.assertTrue((self.repo / "unfinished.txt").exists())
                self.assertFalse(all(check.ok for check in okf.checkpoint(self.bundle)))

    def test_worker_failure_with_preserved_work_recovers_instead_of_stopping_run(self) -> None:
        result = self.drive("crash", "--handoff-seconds", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.sessions()), 6)
        self.assertIn("RECOVERY ONLY", self.sessions()[1]["prompt"])
        self.assertIn("Startup: READY", self.sessions()[2]["prompt"])
        self.assertEqual(json.loads(self.run_ok("queue", "--next", "--json")), [])

    def test_recovery_does_not_reset_delivery_or_session_limits(self) -> None:
        result = self.drive("recover", "--max-session-seconds", ".2", "--handoff-seconds", ".4",
                            "--max-stalled", "1")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len(self.sessions()), 2)
        self.assertIn("delivery stall limit retained after recovery", result.stderr)
        self.log.unlink()
        result = self.drive("recover", "--max-session-seconds", ".2", "--handoff-seconds", ".4",
                            "--max-sessions", "2")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len(self.sessions()), 2)
        self.assertIn("reached --max-sessions 2", result.stderr)

    def test_recovery_is_truncated_by_original_run_deadline(self) -> None:
        started = time.monotonic()
        result = self.drive("stuck-recovery", "--max-session-seconds", ".15", "--handoff-seconds", ".4",
                            "--max-run-seconds", ".75")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len(self.sessions()), 2)
        self.assertLess(time.monotonic() - started, 2)
        self.assertIn("recovery/run limit reached", result.stderr)

    def test_driver_does_not_launch_a_records_only_round_with_only_checkpoint_reserve(self) -> None:
        result = self.drive("work", "--max-run-seconds", ".2", "--handoff-seconds", ".3")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.sessions(), [])
        self.assertIn("only checkpoint reserve remains", result.stderr)

    def test_time_limits_cannot_be_disabled_with_zero_negative_or_nonfinite_values(self) -> None:
        for value in ("0", "-1", "nan", "inf"):
            for flag in ("--max-session-seconds", "--handoff-seconds", "--max-discovery-seconds", "--max-closure-seconds", "--validation-reserve-seconds"):
                result = self.drive("work", flag, value)
                self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.sessions(), [])

    def validation_result(self):
        return json.loads(Path(self.log.with_suffix(".result-path").read_text()).read_text())

    def test_managed_validation_outlives_model_session_then_closes_in_fresh_context(self) -> None:
        events = self.tmp / "validation-progress.jsonl"
        result = self.drive("validation", "--max-session-seconds", ".25", "--handoff-seconds", ".2",
                            "--validation-reserve-seconds", ".05", "--heartbeat-seconds", ".05",
                            "--progress-file", str(events))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.sessions()), 5)
        job = self.validation_result()
        self.assertEqual(job["state"], "PASS")
        self.assertGreater(job["commands"][0]["seconds"], .45)
        self.assertEqual(self.log.with_suffix(".validated").read_text(), "actual assertion passed")
        self.assertIn("CLOSURE ONLY", self.sessions()[1]["prompt"])
        self.assertIn("Managed validation results:", self.sessions()[1]["prompt"])
        public = [json.loads(line) for line in events.read_text().splitlines()]
        self.assertTrue(any(event["kind"] == "heartbeat" and "Managed validation" in event["text"] for event in public))
        self.assertNotIn("private command output", events.read_text())
        self.assertTrue(all(check.ok for check in okf.checkpoint(self.bundle)))

    def test_large_timeout_ceiling_does_not_defer_a_quick_gate_and_delivery(self) -> None:
        result = self.drive("validation-budget", "--max-run-seconds", "4", "--handoff-seconds", ".2", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.validation_result()["state"], "PASS")
        self.assertEqual(self.log.with_suffix(".validated").read_text(), "actual assertion passed")
        self.assertEqual(json.loads(self.run_ok("queue", "--next", "--json")), [])

    def test_closure_review_has_its_own_budget_instead_of_the_discovery_timer(self) -> None:
        result = self.drive("validation-slow-closure", "--max-discovery-seconds", ".1",
                            "--max-closure-seconds", "1", "--max-session-seconds", "2",
                            "--handoff-seconds", ".1", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("recovery session", result.stderr)
        self.assertEqual(json.loads(self.run_ok("queue", "--next", "--json")), [])

    def test_timed_out_closure_with_delivery_safe_checkpoint_and_release_skips_recovery(self) -> None:
        result = self.drive("validation-closure-released", "--max-closure-seconds", ".2",
                            "--max-session-seconds", "2", "--handoff-seconds", ".3",
                            "--max-stalled", "1", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("explicit worker release; no recovery session needed", result.stderr)
        self.assertNotIn("RECOVERY ONLY", " ".join(session["prompt"] for session in self.sessions()))
        self.assertEqual(len(self.sessions()), 5)
        self.assertTrue(all(check.ok for check in okf.checkpoint(self.bundle)))

    def assert_closure_requires_recovery(self, mode: str) -> None:
        result = self.drive("validation-closure-" + mode, "--max-closure-seconds", ".2",
                            "--max-session-seconds", "2", "--handoff-seconds", ".3",
                            "--max-stalled", "1", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RECOVERY ONLY", self.sessions()[2]["prompt"])
        self.assertNotIn("delivery stall limit retained", result.stderr)
        self.assertNotIn("explicit worker release; no recovery", result.stderr)
        self.assertTrue(all(check.ok for check in okf.checkpoint(self.bundle)))

    def test_safe_timed_out_delivery_does_not_imply_external_worker_release(self) -> None:
        self.assert_closure_requires_recovery("unreleased")

    def test_dirty_timed_out_delivery_requires_recovery_without_false_delivery_stall(self) -> None:
        self.assert_closure_requires_recovery("dirty")

    def test_interrupted_delivery_resets_prior_stall_before_ownership_recovery(self) -> None:
        result = self.drive("validation-closure-after-stall", "--max-closure-seconds", ".2",
                            "--max-session-seconds", "2", "--handoff-seconds", ".3",
                            "--max-stalled", "2", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RECOVERY ONLY", self.sessions()[3]["prompt"])
        self.assertNotIn("delivery stall limit retained", result.stderr)
        self.assertEqual(json.loads(self.run_ok("queue", "--next", "--json")), [])

    def test_stale_release_receipt_cannot_skip_recovery(self) -> None:
        self.assert_closure_requires_recovery("stale")

    def test_registered_external_worktree_cannot_skip_lifecycle_recovery(self) -> None:
        self.assert_closure_requires_recovery("external")

    def test_closure_timeout_without_delivery_retains_delivery_limit(self) -> None:
        result = self.drive("validation-closure-no-delivery", "--max-closure-seconds", ".2",
                            "--max-session-seconds", "2", "--handoff-seconds", ".3",
                            "--max-stalled", "1", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("delivery stall limit retained after recovery", result.stderr)
        self.assertEqual(len(self.sessions()), 3)

    def test_closure_budget_does_not_extend_the_session_limit(self) -> None:
        result = self.drive("validation-closure-no-delivery", "--max-closure-seconds", "10",
                            "--max-session-seconds", ".2", "--handoff-seconds", ".3",
                            "--max-stalled", "1", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("delivery stall limit retained after recovery", result.stderr)
        self.assertEqual(len(self.sessions()), 3)

    def test_closure_budget_does_not_extend_the_original_run_deadline(self) -> None:
        started = time.monotonic()
        result = self.drive("validation-closure-no-delivery", "--max-closure-seconds", "10",
                            "--max-session-seconds", "10", "--handoff-seconds", ".3",
                            "--max-run-seconds", "2", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("recovery/run limit reached", result.stderr)
        self.assertEqual(len(self.sessions()), 2)
        self.assertLess(time.monotonic() - started, 3.5)

    def test_environment_only_validation_retry_reuses_candidate_without_source_timer_or_docs_commit(self) -> None:
        result = self.drive("validation-environment", "--max-discovery-seconds", ".4", "--handoff-seconds", ".1",
                            "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("discovery budget exhausted", result.stderr)
        previous = json.loads(Path(self.log.with_suffix(".first-result-path").read_text()).read_text())
        current = self.validation_result()
        self.assertEqual((previous["state"], current["state"]), ("FAIL", "PASS"))
        self.assertEqual(previous["candidate"], current["candidate"])
        self.assertEqual(len(self.sessions()), 6)
        self.assertTrue(all(check.ok for check in okf.checkpoint(self.bundle)))

    def test_reviewed_repairs_reach_third_gate_before_done_with_stall_limit_one(self) -> None:
        result = self.drive("repair-good", "--max-stalled", "1", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.sessions()), 4)
        self.assertEqual(self.log.with_suffix(".gate-runs").read_text(), "runrunrun")
        self.assertEqual(self.validation_result()["state"], "PASS")
        self.assertEqual(result.stderr.count("Verified deterministic repair regression PASS"), 2)
        self.assertEqual(json.loads(self.run_ok("queue", "--next", "--json")), [])

    def test_records_only_repair_cannot_bypass_stall_limit(self) -> None:
        result = self.drive("repair-records", "--max-stalled", "1", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("records-only changes do not qualify", result.stderr)
        self.assertEqual(self.log.with_suffix(".gate-runs").read_text(), "run")

    def test_repair_binding_survives_source_checkpoint_before_submission(self) -> None:
        result = self.drive("repair-checkpoint", "--max-stalled", "2", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.sessions()), 5)
        self.assertEqual(self.log.with_suffix(".gate-runs").read_text(), "runrunrun")
        self.assertIn("Most recent managed result retained", self.sessions()[2]["prompt"])

    def test_verified_repairs_do_not_reset_an_earlier_stall(self) -> None:
        result = self.drive("repair-retain-stall", "--max-stalled", "2", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("repeated validation handoffs without delivery", result.stderr)
        self.assertEqual(len(self.sessions()), 5)
        self.assertEqual(self.log.with_suffix(".gate-runs").read_text(), "runrunrun")
        self.assertTrue(json.loads(self.run_ok("queue", "--next", "--json")))

    def test_failing_repair_regression_stops_before_full_gate(self) -> None:
        result = self.drive("repair-bad-proof", "--max-stalled", "1", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("repair regression did not earn", result.stderr)
        self.assertEqual(self.log.with_suffix(".gate-runs").read_text(), "run")
        self.assertEqual(self.validation_result()["commands"][0]["state"], "FAIL")

    def test_managed_validation_failure_and_timeout_are_retained_and_not_delivery(self) -> None:
        for mode, state in (("validation-fail", "FAIL"), ("validation-timeout", "TIMED_OUT")):
            with self.subTest(mode=mode):
                self.log.unlink(missing_ok=True)
                result = self.drive(mode, "--max-sessions", "2", "--validation-reserve-seconds", ".05")
                self.assertEqual(result.returncode, 1, result.stderr)
                job = self.validation_result()
                self.assertEqual(job["state"], state)
                self.assertEqual(len(job["commands"]), 1)
                self.assertEqual(autonomy_driver.delivery_marker(self.bundle), {"A"})
                self.assertTrue(Path(job["commands"][0]["log"]).exists())
                if state == "TIMED_OUT":
                    proc = Path("/proc") / self.log.with_suffix(".test.pid").read_text() / "stat"
                    self.assertTrue(not proc.exists() or proc.read_text().split()[2] == "Z")

    def test_managed_validation_rejects_source_mutation_and_repeated_handoffs(self) -> None:
        result = self.drive("validation-repeat", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len(self.sessions()), 3)
        self.assertIn("repeated validation handoffs without delivery", result.stderr)
        self.log.unlink()
        result = self.drive("validation-mutate", "--validation-reserve-seconds", ".05")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len(self.sessions()), 1)
        self.assertEqual(self.validation_result()["state"], "INVALIDATED")
        self.assertTrue((self.repo / "unexpected.rs").exists())

    def test_investigation_continues_past_progress_query_then_delivers(self) -> None:
        for mode in ("planning", "document-planning"):
            with self.subTest(mode=mode):
                self.log.unlink(missing_ok=True)
                started = time.monotonic()
                result = self.drive(mode, "--max-discovery-seconds", ".15", "--handoff-seconds", ".2",
                                    "--max-sessions", "10")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("concrete progress requested while work continues", result.stderr)
                self.assertNotIn("checkpoint now", result.stderr)
                self.assertTrue((self.repo / "investigated.py").exists())
                self.assertEqual(json.loads(self.run_ok("queue", "--next", "--json")), [])
                self.assertLess(time.monotonic() - started, 6)
                # A fresh fixture is not needed for the second subcase: reopen the same test tasks.
                if mode == "planning":
                    self.append_tasks("\n### E — Another bounded task\n- State: READY\n")
                    self.commit_all("next scenario")

    def chat_process(self, *, acknowledgement_seconds=1):
        progress, ack, marker, release = (self.tmp / name for name in ("progress.jsonl", "ack.json", "child.pid", "release"))
        child = self.tmp / "long_test.py"
        child.write_text("import json,pathlib,subprocess,sys,time\n"
                         "grand=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
                         f"pathlib.Path({str(marker)!r}).write_text(str(grand.pid))\n"
                         "print(json.dumps({'type':'item.started','item':{'type':'command_execution','command':'PRIVATE_TOOL_PAYLOAD'}}),flush=True)\n"
                         "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'Long-running test is underway'}}),flush=True)\n"
                         f"while not pathlib.Path({str(release)!r}).exists(): time.sleep(0.02)\n")
        process = subprocess.Popen([sys.executable, str(SCRIPTS / "autonomy_driver.py"), "--bundle", str(self.bundle),
                                    "--no-pr-sync", "--max-sessions", "1", "--max-session-seconds", "5",
                                    "--heartbeat-seconds", "0.1", "--chat-timeout-seconds", str(acknowledgement_seconds),
                                    "--progress-file", str(progress), "--chat-ack-file", str(ack), "--", sys.executable, str(child)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        return process, progress, ack, marker, release

    def await_progress(self, path, kind):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            if path.exists():
                entries = [json.loads(line) for line in path.read_text().splitlines() if line.endswith("}")]
                if any(event["kind"] == kind for event in entries):
                    return entries
            time.sleep(0.02)
        self.fail(f"progress event {kind} absent")

    def acknowledge(self, progress, ack):
        result = subprocess.run([sys.executable, str(SCRIPTS / "autonomy_progress.py"), "ack", "--file", str(progress),
                                 "--ack-file", str(ack)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_chat_acknowledgement_is_required_before_any_agent_launch(self) -> None:
        process, progress, ack, marker, release = self.chat_process(acknowledgement_seconds=0.4)
        stdout, stderr = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 1, stderr)
        self.assertFalse(marker.exists())
        self.assertIn("acknowledgement missing or expired", stderr)
        self.assertEqual(self.await_progress(progress, "stopped")[-1]["kind"], "stopped")

    def test_lost_chat_cancels_managed_validation_and_preserves_completed_results(self) -> None:
        progress, ack = self.tmp / "job-progress.jsonl", self.tmp / "job-ack.json"
        process = subprocess.Popen([sys.executable, str(SCRIPTS / "autonomy_driver.py"), "--bundle", str(self.bundle),
                                    "--no-pr-sync", "--chat-timeout-seconds", ".5", "--heartbeat-seconds", ".05",
                                    "--validation-reserve-seconds", ".05", "--progress-file", str(progress),
                                    "--chat-ack-file", str(ack), "--", sys.executable, str(self.agent), str(self.log), "validation"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        self.await_progress(progress, "started")
        self.acknowledge(progress, ack)
        self.await_progress(progress, "validation")
        self.acknowledge(progress, ack)
        stdout, stderr = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 1, stderr)
        self.assertEqual(self.validation_result()["state"], "CANCELLED")
        self.assertEqual(self.validation_result()["commands"][0]["state"], "CANCELLED")
        self.assertFalse(self.log.with_suffix(".validated").exists())

    def test_long_test_heartbeats_and_public_updates_continue_then_lost_chat_stops_tree(self) -> None:
        process, progress, ack, marker, release = self.chat_process()
        self.await_progress(progress, "started")
        self.acknowledge(progress, ack)
        entries = self.await_progress(progress, "heartbeat")
        self.assertTrue(any(event["text"] == "Long-running test is underway" for event in entries))
        self.assertNotIn("PRIVATE_TOOL_PAYLOAD", progress.read_text())
        self.assertTrue(marker.exists(), "actual long-running test did not start")
        stdout, stderr = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 1, stderr)
        self.assertIn("acknowledgement missing or expired", stderr)
        proc = Path(f"/proc/{int(marker.read_text())}/stat")
        if proc.exists():
            self.assertEqual(proc.read_text().split()[2], "Z", "unattended descendant survived")

    def test_renewed_chat_acknowledgement_allows_long_test_to_complete(self) -> None:
        process, progress, ack, marker, release = self.chat_process()
        self.await_progress(progress, "started")
        self.acknowledge(progress, ack)
        self.await_progress(progress, "heartbeat")
        self.acknowledge(progress, ack)
        release.write_text("finish the real child check")
        stdout, stderr = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 1, stderr)  # normal one-session cap, not lost chat
        self.assertIn("reached --max-sessions 1", stderr)
        self.assertNotIn("acknowledgement missing or expired", stderr)
        self.assertIn('"exit_code": 0', stderr)

    def test_default_cli_refuses_a_silent_unmonitored_launch(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPTS / "autonomy_driver.py"), "--bundle", str(self.bundle),
                                 "--no-pr-sync", "--", sys.executable, str(self.agent), str(self.log), "work"],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn("visible chat supervision required", result.stderr)
        self.assertEqual(self.sessions(), [])

    def test_stops_when_the_agent_fails_or_the_session_cap_is_reached(self) -> None:
        failed = self.drive("fail")
        self.assertEqual((failed.returncode, len(self.sessions())), (1, 1))
        self.assertIn("agent command exited 7", failed.stderr)
        timing = next(json.loads(line.removeprefix("timing: ")) for line in failed.stderr.splitlines()
                      if line.startswith("timing: "))
        self.assertEqual((timing["exit_code"], timing["outcome"]), (7, "FAIL"))
        capped = self.drive("work", "--max-sessions", "2")
        self.assertEqual(capped.returncode, 1)
        self.assertIn("reached --max-sessions 2", capped.stderr)
        self.assertEqual(len(self.sessions()), 3)

    def test_starts_no_session_when_nothing_is_actionable(self) -> None:
        path = self.bundle / okf.QUEUE_DOC
        path.write_text(path.read_text().replace("- State: READY", "- State: DEFERRED\n- Reason: later").replace("- State: NOT_READY", "- State: DEFERRED\n- Reason: later"))
        self.commit_all("defer everything")
        result = self.drive("work")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.sessions(), [])
        self.assertIn("Queue: 1 DONE, 4 DEFERRED", result.stderr)

    def test_driver_and_hook_leave_the_work_tree_clean(self) -> None:
        # Copied into a repository that does not ignore __pycache__, as when the toolkit is adopted elsewhere.
        scripts = self.repo / ".ai" / "scripts"
        scripts.mkdir(parents=True)
        for name in ("okf.py", "autonomy_driver.py", "autonomy_hook.py", "pr_sync.py", "timed_check.py", "autonomy_progress.py", "autonomy_validation.py", "scratch.py"):
            shutil.copy(SCRIPTS / name, scripts / name)
        self.commit_all("add toolkit")
        environment = {k: v for k, v in os.environ.items() if not k.startswith(("OKF_", "PYTHONDONTWRITEBYTECODE"))}
        subprocess.run(
            [sys.executable, str(scripts / "autonomy_hook.py")], input=json.dumps({"hook_event_name": "Stop", "session_id": "c"}),
            capture_output=True, text=True, env={**environment, "OKF_AUTONOMOUS": "1"}, check=True,
        )
        result = subprocess.run(
            [sys.executable, str(scripts / "autonomy_driver.py"), "--no-pr-sync", "--headless", "--", sys.executable, str(self.agent), str(self.log), "work"],
            capture_output=True, text=True, env=environment, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((scripts / "__pycache__").exists())
        self.assertTrue(all(c.ok for c in okf.checkpoint(self.bundle)), self.run_cli("checkpoint")[1])

    def test_requires_an_agent_command(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "autonomy_driver.py"), "--bundle", str(self.bundle)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("give the agent command after `--`", result.stderr)


if __name__ == "__main__":
    unittest.main()
