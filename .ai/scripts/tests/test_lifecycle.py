"""Behavioral tests for lifecycle.py: tier and stage gates, spec traceability, red/green
evidence, queue-from-spec, and the harness hooks.

Run: python3 -m unittest discover -s .ai/scripts/tests
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import disk_tmp  # noqa: E402,F401
import lifecycle  # noqa: E402
import okf  # noqa: E402

SPEC = """# Spec: Greeter

## Problem and outcome

Greet people.

## Requirements

- R1: The greeter MUST return "Hello, NAME".
- R2: The greeter MUST reject an empty name.

## Acceptance

- R1: `python3 -m unittest test_greet.GreetTests.test_hello` passes.
- R2: `python3 -m unittest test_greet.GreetTests.test_empty` passes.

## Constraints

None.

## Non-goals

Localization.

## Assumptions

None.

## Open questions

None. The spec is ready for planning.
"""

PLAN = "# Plan\n\n## Steps\n\n### Step 1: R1 hello\n### Step 2: R2 empty name\n"
REVIEW_OK = "# Review Report\n\n## Verdict\nApproved\n"
REVIEW_BAD = "# Review Report\n\n## Verdict\nChanges requested - R2 missing.\n"


class LifecycleCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.repo)
        self.git("init", "-q")
        (self.repo / "app.py").write_text("print('hi')\n")
        (self.repo / "spec.md").write_text(SPEC)
        (self.repo / "plan.md").write_text(PLAN)
        (self.repo / "review.md").write_text(REVIEW_OK)
        self.git("add", "-A")
        self.git("commit", "-qm", "initial")
        self.old_cwd = os.getcwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, self.old_cwd)
        os.environ.pop("OKF_AUTONOMOUS", None)
        os.environ.pop("LIFECYCLE_GUARD", None)

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.email=t@t", "-c", "user.name=t", *args], check=True, capture_output=True)

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = lifecycle.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def ok(self, *argv: str) -> str:
        code, out, err = self.run_cli(*argv)
        self.assertEqual(code, 0, f"{argv} failed: {out}{err}")
        return out

    def fails(self, *argv: str, message: str) -> None:
        code, out, err = self.run_cli(*argv)
        self.assertEqual(code, 1, f"{argv} should fail: {out}{err}")
        self.assertIn(message, out + err)

    def hook(self, payload: dict, **env: str) -> str:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "lifecycle.py"), "hook"], input=json.dumps(payload), cwd=self.repo,
            capture_output=True, text=True, env={**os.environ, **env},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def edit(self, path: str = "app.py") -> dict:
        return {"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": {"file_path": str(self.repo / path)}, "cwd": str(self.repo)}

    def denied(self, output: str) -> bool:
        return bool(output) and '"deny"' in output

    def converge_green(self) -> None:
        """Make SPEC's acceptance commands pass and record the converge run that L2 verify requires."""
        (self.repo / "test_greet.py").write_text(
            "import unittest\n\n\nclass GreetTests(unittest.TestCase):\n    def test_hello(self):\n        pass\n\n    def test_empty(self):\n        pass\n"
        )
        self.ok("converge", "spec.md")


class SpecTests(LifecycleCase):
    def test_trace_passes_when_plan_and_tests_cite_every_requirement(self) -> None:
        (self.repo / "test_greet.py").write_text("# R1 R2\n")
        self.assertIn("2 requirement(s) traced", self.ok("trace", "spec.md", "--plan", "plan.md", "--tests", "test_greet.py"))

    def test_trace_reports_requirement_missing_from_plan_and_tests(self) -> None:
        (self.repo / "plan.md").write_text("# Plan\n\n### Step 1: R1 only\n")
        (self.repo / "test_greet.py").write_text("# R1\n")
        code, out, _ = self.run_cli("trace", "spec.md", "--plan", "plan.md", "--tests", "test_greet.py")
        self.assertEqual(code, 1)
        self.assertIn("R2 is not cited by the plan", out)
        self.assertIn("R2 is not cited by any test", out)

    def test_lint_flags_requirement_without_acceptance_and_open_questions(self) -> None:
        text = SPEC.replace("- R2: `python3 -m unittest test_greet.GreetTests.test_empty` passes.\n", "")
        text = text.replace("None. The spec is ready for planning.", "- Should names be trimmed?")
        (self.repo / "spec.md").write_text(text)
        problems = lifecycle.lint_spec(self.repo / "spec.md")
        self.assertIn("R2 has no acceptance check under '## Acceptance'", problems)
        self.assertTrue(any("open questions remain" in p for p in problems))

    def test_queue_from_spec_entries_pass_okf_validation(self) -> None:
        shutil.copytree(SCRIPTS, self.repo / ".ai/scripts", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        subprocess.run([sys.executable, ".ai/scripts/okf.py", "init", "--autonomous"], cwd=self.repo, check=True, capture_output=True)
        entries = self.ok("queue-from-spec", "spec.md", "--group", "Greeter")
        self.assertIn("### SPEC-R1", entries)
        queue = self.repo / "knowledge/project/work-queue.md"
        queue.write_text(queue.read_text() + "\n" + entries)
        result = subprocess.run([sys.executable, ".ai/scripts/okf.py", "queue", "--json"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = {task["id"]: task for task in json.loads(result.stdout)}
        self.assertEqual(listed["SPEC-R2"]["state"], "READY")
        validate = subprocess.run([sys.executable, ".ai/scripts/okf.py", "validate"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

    def test_queue_from_spec_refuses_unready_spec(self) -> None:
        (self.repo / "spec.md").write_text(SPEC.replace("None. The spec is ready for planning.", "- unresolved"))
        self.fails("queue-from-spec", "spec.md", message="spec is not ready")


class StageTests(LifecycleCase):
    def test_l2_requires_approved_spec_traced_plan_and_approved_review(self) -> None:
        self.ok("tier", "L2", "--reason", "new behavior")
        self.fails("stage", "intent", "--ref", "spec.md", message="--approved-by")
        self.ok("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")
        self.fails("gate", "ship", message="before ship")
        (self.repo / "plan.md").write_text("# Plan\n\nonly R1\n")
        self.fails("stage", "plan", "--ref", "plan.md", message="R2 is not cited by the plan")
        (self.repo / "plan.md").write_text(PLAN)
        self.ok("stage", "plan", "--ref", "plan.md")
        self.ok("gate", "implement")
        self.fails("stage", "verify", "--note", "ran tests", message="review")
        (self.repo / "review.md").write_text(REVIEW_BAD)
        self.fails("stage", "review", "--ref", "review.md", message="not Approved")
        (self.repo / "review.md").write_text(REVIEW_OK)
        self.ok("stage", "review", "--ref", "review.md")
        self.converge_green()
        self.ok("stage", "verify", "--note", "unit tests PASS")  # At L2 the note is optional: the converge ledger entries are the evidence.
        self.assertTrue(lifecycle.load(self.repo)["stages"]["verify"]["note"].endswith("| agent note: unit tests PASS"))
        self.ok("stage", "ship")
        self.assertIn("no active lifecycle", self.ok("status"))

    def test_spec_with_open_questions_cannot_be_approved(self) -> None:
        (self.repo / "spec.md").write_text(SPEC.replace("None. The spec is ready for planning.", "- Which locale?"))
        self.ok("tier", "L2", "--reason", "x")
        self.fails("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me", message="open questions remain")

    def test_l1_accepts_notes_but_escalation_to_l2_invalidates_them(self) -> None:
        self.ok("tier", "L1", "--reason", "small")
        self.ok("stage", "intent", "--note", "goal; check; none")
        self.ok("stage", "plan", "--note", "edit app.py")
        self.ok("gate", "implement")
        self.ok("tier", "L2", "--reason", "touches a public contract")
        self.fails("gate", "implement", message="intent, plan")

    def test_plan_cannot_precede_intent(self) -> None:
        self.ok("tier", "L2", "--reason", "feature")
        self.fails("stage", "plan", "--ref", "plan.md", message="intent stage before the plan")

    def test_re_recording_intent_retraces_an_existing_plan(self) -> None:
        self.ok("tier", "L2", "--reason", "feature")
        self.ok("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")
        self.ok("stage", "plan", "--ref", "plan.md")
        grown = SPEC.replace("MUST reject an empty name.\n", "MUST reject an empty name.\n- R3: A third MUST.\n")
        grown = grown.replace("test_empty` passes.\n", "test_empty` passes.\n- R3: `python3 -c 1` exits 0.\n")
        (self.repo / "spec.md").write_text(grown)
        self.fails("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me", message="R3 is not cited by the plan")

    def test_l1_stages_with_a_ref_do_not_survive_escalation(self) -> None:
        self.ok("tier", "L1", "--reason", "small")
        (self.repo / "any.md").write_text("anything\n")
        self.ok("stage", "intent", "--ref", "any.md", "--note", "n")
        self.ok("stage", "plan", "--ref", "any.md")
        self.ok("stage", "review", "--ref", "any.md", "--note", "self-review")
        self.ok("stage", "verify", "--note", "ran tests")
        self.ok("tier", "L2", "--reason", "contract effect found")
        self.assertIn("still required: intent, plan, review, verify", self.ok("status"))
        self.fails("gate", "implement", message="intent, plan")

    def test_user_set_tier_cannot_be_lowered(self) -> None:
        self.ok("tier", "L2", "--reason", "user said", "--user-set")
        self.fails("tier", "L1", "--reason", "seems small", message="cannot be lowered")

    def test_new_flag_discards_previous_stages(self) -> None:
        self.ok("tier", "L1", "--reason", "a")
        self.ok("stage", "intent", "--note", "n")
        self.ok("tier", "L1", "--reason", "b", "--new")
        self.assertIn("still required: intent, plan, verify", self.ok("status"))

    def test_l0_declaration_expires_at_the_next_commit(self) -> None:
        self.ok("tier", "L0", "--reason", "typo")
        self.assertFalse(self.denied(self.hook(self.edit())))
        (self.repo / "app.py").write_text("print('typo fixed')\n")
        self.git("commit", "-qam", "fix typo")
        self.assertTrue(self.denied(self.hook(self.edit())))

    def test_verify_runs_the_records_gate_when_a_bundle_exists(self) -> None:
        shutil.copytree(SCRIPTS, self.repo / ".ai/scripts", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        subprocess.run([sys.executable, ".ai/scripts/okf.py", "init"], cwd=self.repo, check=True, capture_output=True)
        (self.repo / "knowledge/project/sync-ignore").write_text(".ai/*\n")
        (self.repo / "knowledge/capabilities/broken.md").write_text("no frontmatter\n")
        self.ok("tier", "L1", "--reason", "x")
        self.ok("stage", "intent", "--note", "n")
        self.ok("stage", "plan", "--note", "p")
        self.fails("stage", "verify", "--note", "ran", message="okf.py records failed")


class RedGreenTests(LifecycleCase):
    def test_bugfix_needs_red_then_green_with_a_change_between(self) -> None:
        (self.repo / "check.py").write_text("import sys; sys.exit(0 if open('flag').read().strip() == 'fixed' else 1)\n")
        (self.repo / "flag").write_text("broken\n")
        self.ok("tier", "L1", "--reason", "bug", "--kind", "bugfix")
        self.ok("stage", "intent", "--note", "n")
        self.ok("stage", "plan", "--note", "p")
        self.fails("stage", "verify", "--note", "ran", message="red/green")
        self.fails("redgreen", "green", "--", sys.executable, "check.py", message="no open red run")
        self.ok("redgreen", "red", "--", sys.executable, "check.py")
        self.fails("redgreen", "green", "--", sys.executable, "check.py", message="still fails")
        (self.repo / "flag").write_text("fixed\n")
        self.ok("redgreen", "green", "--", sys.executable, "check.py")
        self.ok("stage", "verify", "--note", "check.py red then green")

    def test_staging_the_fix_between_red_and_green_still_counts_as_a_change(self) -> None:
        (self.repo / "check.py").write_text("import sys; sys.exit(0 if open('flag').read().strip() == 'fixed' else 1)\n")
        (self.repo / "flag").write_text("broken\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "add check")
        self.ok("tier", "L1", "--reason", "bug", "--kind", "bugfix")
        self.ok("redgreen", "red", "--", sys.executable, "check.py")
        (self.repo / "flag").write_text("fixed\n")
        self.git("add", "flag")
        self.ok("redgreen", "green", "--", sys.executable, "check.py")

    def test_red_run_that_passes_is_rejected_as_vacuous(self) -> None:
        self.ok("tier", "L1", "--reason", "bug", "--kind", "bugfix")
        self.fails("redgreen", "red", "--", sys.executable, "-c", "pass", message="vacuous")

    def test_green_without_a_change_since_red_is_rejected(self) -> None:
        (self.repo / "flaky.py").write_text("import os,sys; sys.exit(0 if os.path.exists('ok') else 1)\n")
        self.ok("tier", "L1", "--reason", "bug", "--kind", "bugfix")
        self.ok("redgreen", "red", "--", sys.executable, "flaky.py")
        (self.repo / "ok").write_text("")
        self.ok("redgreen", "green", "--", sys.executable, "flaky.py")
        self.ok("redgreen", "red", "--", sys.executable, "-c", "import sys; sys.exit(3)")
        self.fails("redgreen", "green", "--", sys.executable, "-c", "import sys; sys.exit(3)", message="still fails")


class HookTests(LifecycleCase):
    def test_source_edit_without_a_tier_is_denied_with_the_fix_in_the_message(self) -> None:
        output = self.hook(self.edit())
        self.assertTrue(self.denied(output))
        self.assertIn("lifecycle.py tier", output)

    def test_markdown_and_knowledge_edits_are_exempt(self) -> None:
        self.assertEqual(self.hook(self.edit("README.md")), "")
        self.assertEqual(self.hook(self.edit("knowledge/project/x.yaml")), "")

    def test_edit_waits_for_the_stages_of_the_tier(self) -> None:
        self.ok("tier", "L2", "--reason", "feature")
        self.assertTrue(self.denied(self.hook(self.edit())))
        self.ok("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")
        self.ok("stage", "plan", "--ref", "plan.md")
        self.assertEqual(self.hook(self.edit()), "")

    def test_apply_patch_paths_are_checked(self) -> None:
        patch = "*** Begin Patch\n*** Update File: app.py\n@@\n-print('hi')\n+print('yo')\n*** End Patch\n"
        payload = {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "tool_input": {"command": patch}, "cwd": str(self.repo)}
        self.assertTrue(self.denied(self.hook(payload)))

    def test_commit_needs_verify_but_wip_commit_does_not(self) -> None:
        self.ok("tier", "L1", "--reason", "small")
        bash = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": 'git commit -m "feat: x"'}, "cwd": str(self.repo)}
        self.assertTrue(self.denied(self.hook(bash)))
        bash["tool_input"]["command"] = 'git commit -m "wip: partial"'
        self.assertEqual(self.hook(bash), "")
        bash["tool_input"]["command"] = "gh pr create --fill"
        self.assertTrue(self.denied(self.hook(bash)))

    def bash(self, command: str) -> dict:
        return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(self.repo)}

    def test_commit_and_pr_are_denied_when_no_tier_is_active(self) -> None:
        for command in ('git commit -m "feat: x"', "git -C . commit -am x", "gh pr create --fill", "gh pr ready"):
            output = self.hook(self.bash(command))
            self.assertTrue(self.denied(output), command)
            self.assertIn("lifecycle.py tier", output)

    def test_l0_allows_commits_and_unrelated_commands_pass(self) -> None:
        self.ok("tier", "L0", "--reason", "typo")
        self.assertEqual(self.hook(self.bash('git commit -m "fix: typo"')), "")
        self.assertEqual(self.hook(self.bash("git status")), "")
        self.assertEqual(self.hook(self.bash("git commit-tree HEAD^{tree} -m x")), "")

    def test_wip_exemption_applies_only_to_a_message_that_starts_with_wip(self) -> None:
        self.ok("tier", "L1", "--reason", "small")
        self.assertEqual(self.hook(self.bash('git commit -m "wip: partial"')), "")
        self.assertEqual(self.hook(self.bash("git commit --message='wip: partial'")), "")
        self.assertEqual(self.hook(self.bash('git commit -am "wip: x"')), "")
        self.assertEqual(self.hook(self.bash('git commit -qm "wip: x"')), "")
        self.assertTrue(self.denied(self.hook(self.bash('git commit -m "fix: handle wip: prefix"'))))
        self.assertTrue(self.denied(self.hook(self.bash('git commit -m "feat: x" # wip:'))))

    def test_non_object_json_and_missing_test_command_fail_open_or_cleanly(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPTS / "lifecycle.py"), "hook"], input="[1]", cwd=self.repo, capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.ok("tier", "L1", "--reason", "bug", "--kind", "bugfix")
        self.fails("redgreen", "red", "--", "definitely-not-a-command-xyz", message="cannot run command")

    def test_cursor_payload_gets_cursor_shaped_decisions(self) -> None:
        payload = self.edit() | {"cursor_version": "1.0", "tool_name": "Write", "workspace_roots": [str(self.repo)]}
        decision = json.loads(self.hook(payload))
        self.assertEqual(decision["permission"], "deny")
        self.assertIn("lifecycle.py tier", decision["agent_message"])
        allowed = json.loads(self.hook(payload | {"tool_input": {"file_path": str(self.repo / "NOTES.md")}}))
        self.assertEqual(allowed, {"permission": "allow"})

    def test_cursor_before_shell_execution_gates_commits(self) -> None:
        self.ok("tier", "L1", "--reason", "small")
        event = {"hook_event_name": "beforeShellExecution", "command": 'git commit -m "feat: x"', "cursor_version": "1", "workspace_roots": [str(self.repo)]}
        self.assertEqual(json.loads(self.hook(event))["permission"], "deny")

    def test_session_start_injects_the_router_and_the_missing_tier(self) -> None:
        (self.repo / ".ai").mkdir()
        shutil.copy(SCRIPTS.parent / "lifecycle.md", self.repo / ".ai/lifecycle.md")
        context = json.loads(self.hook({"hook_event_name": "SessionStart", "cwd": str(self.repo)}))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Pick the tier", context)
        self.assertIn("No tier declared yet", context)
        cursor = json.loads(self.hook({"hook_event_name": "sessionStart", "cursor_version": "1", "workspace_roots": [str(self.repo)]}))
        self.assertIn("Pick the tier", cursor["additional_context"])

    def test_guard_can_be_disabled_and_autonomous_sessions_are_not_gated(self) -> None:
        self.assertEqual(self.hook(self.edit(), LIFECYCLE_GUARD="off"), "")
        self.assertEqual(self.hook(self.edit(), OKF_AUTONOMOUS="1"), "")

    def test_unparseable_input_and_outside_paths_are_allowed(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPTS / "lifecycle.py"), "hook"], input="not json", cwd=self.repo, capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        outside = self.edit() | {"tool_input": {"file_path": "/etc/hosts"}}
        self.assertEqual(self.hook(outside), "")


class AuditTrailTests(LifecycleCase):
    """The committed, hash-bound record (knowledge/specifications/lifecycle-audit-trail.md R1 to R6)."""

    def records(self) -> list[Path]:
        return sorted((self.repo / "knowledge/history/lifecycle").glob("*.json"))

    def record(self) -> dict:
        (path,) = self.records()
        return json.loads(path.read_text())

    def l2_through_review(self) -> None:
        self.ok("tier", "L2", "--reason", "feature")
        self.ok("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")
        self.ok("stage", "plan", "--ref", "plan.md")
        self.ok("stage", "review", "--ref", "review.md")

    def bash(self, command: str) -> dict:
        return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(self.repo)}

    def test_record_written_per_task_and_not_for_l0(self) -> None:  # R1
        self.ok("tier", "L1", "--reason", "small")
        (first,) = self.records()
        self.assertRegex(first.name, r"^\d{8}T\d{6}Z(-\d+)?-[A-Za-z0-9_.-]+\.json$")
        self.ok("stage", "intent", "--note", "goal; check; none")
        self.assertIn("intent", self.record()["stages"])
        self.ok("tier", "L1", "--reason", "another task", "--new")
        self.assertEqual(len(self.records()), 2)
        self.ok("tier", "L0", "--reason", "typo", "--new")
        self.assertEqual(len(self.records()), 2)

    def test_first_record_in_a_bundle_keeps_okf_records_passing(self) -> None:  # R1 with the Constraints' okf rule
        shutil.copytree(SCRIPTS, self.repo / ".ai/scripts", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        subprocess.run([sys.executable, ".ai/scripts/okf.py", "init"], cwd=self.repo, check=True, capture_output=True)
        (self.repo / "knowledge/project/sync-ignore").write_text(".ai/*\n")
        self.ok("tier", "L1", "--reason", "x")
        self.ok("stage", "intent", "--note", "n")
        self.ok("stage", "plan", "--note", "p")
        self.ok("stage", "verify", "--note", "ran")
        self.assertEqual(len(self.records()), 1)

    def test_bundle_can_still_be_initialized_after_the_first_record(self) -> None:  # AGENTS.md §1 bootstrap
        shutil.copytree(SCRIPTS, self.repo / ".ai/scripts", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        self.ok("tier", "L1", "--reason", "x")
        self.assertFalse((self.repo / "knowledge/index.md").exists())
        okf_cli = [sys.executable, ".ai/scripts/okf.py"]
        subprocess.run([*okf_cli, "init"], cwd=self.repo, check=True, capture_output=True)
        self.assertEqual(len(self.records()), 1)
        result = subprocess.run([*okf_cli, "records"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_record_fields_and_no_output_tail(self) -> None:  # R2
        self.ok("tier", "L1", "--reason", "bug", "--kind", "bugfix")
        self.ok("redgreen", "red", "--", sys.executable, "-c", "import sys; print('MARKER-' + 'TAIL-XYZ'); sys.exit(2)")
        record = self.record()
        for key in ("version", "task", "branch", "head", "tier", "kind", "reason", "user_set", "history", "stages", "redgreen"):
            self.assertIn(key, record)
        self.assertEqual(record["redgreen"][0]["red"]["exit"], 2)
        self.assertIn("work", record["redgreen"][0]["red"])
        self.assertNotIn("MARKER-TAIL-XYZ", self.records()[0].read_text())
        self.assertIn("MARKER-TAIL-XYZ", json.dumps(lifecycle.load(self.repo)))

    def test_ref_hash_ignores_frontmatter(self) -> None:  # R3
        (self.repo / "spec.md").write_text("---\ntype: Specification\nstatus: draft\n---\n\n" + SPEC)
        self.ok("tier", "L2", "--reason", "feature")
        self.ok("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")
        self.assertRegex(self.record()["stages"]["intent"]["sha256"], r"^[0-9a-f]{64}$")
        (self.repo / "spec.md").write_text("---\ntype: Specification\nstatus: stable\nverified: { by: process:x }\n---\n\n" + SPEC)
        self.ok("audit")

    def test_audit_detects_changed_ref_and_malformed_record(self) -> None:  # R4
        self.l2_through_review()
        (path,) = self.records()
        self.assertIn("OK", self.ok("audit", str(path)))
        (self.repo / "spec.md").write_text(SPEC.replace("Hello, NAME", "Hi, NAME"))
        self.fails("audit", message="spec.md changed")
        (self.repo / "spec.md").write_text(SPEC)
        (self.repo / "plan.md").unlink()
        self.fails("audit", message="plan.md is missing")
        (self.repo / "plan.md").write_text(PLAN)
        unapproved = json.loads(path.read_text())
        del unapproved["stages"]["intent"]["approved_by"]
        other = self.repo / "unapproved.json"
        other.write_text(json.dumps(unapproved))
        self.fails("audit", str(other), message="approved_by")
        other.write_text("{not json")
        self.fails("audit", str(other), message="unparseable")
        self.ok("audit")

    def test_verify_refuses_failed_audit(self) -> None:  # R5
        self.l2_through_review()
        (self.repo / "spec.md").write_text(SPEC.replace("reject an empty name", "accept any name"))
        self.fails("stage", "verify", "--note", "ran", message="audit")
        (self.repo / "spec.md").write_text(SPEC)
        self.converge_green()
        self.ok("stage", "verify", "--note", "ran")

    def test_commit_hook_requires_staged_record(self) -> None:  # R6
        self.ok("tier", "L1", "--reason", "small")
        self.ok("stage", "intent", "--note", "n")
        self.ok("stage", "plan", "--note", "p")
        self.ok("stage", "verify", "--note", "ran")
        (path,) = self.records()
        relative = path.relative_to(self.repo).as_posix()
        output = self.hook(self.bash('git commit -m "feat: x"'))
        self.assertTrue(self.denied(output))
        self.assertIn(f"git add {relative}", output)
        self.assertEqual(self.hook(self.bash('git add -A && git commit -m "feat: x"')), "")
        self.assertEqual(self.hook(self.bash('git commit -m "wip: partial"')), "")
        self.git("add", relative)
        self.assertEqual(self.hook(self.bash('git commit -m "feat: x"')), "")
        self.git("commit", "-qm", "feat: x")
        self.assertEqual(self.hook(self.bash('git commit -m "feat: y"')), "")
        self.ok("stage", "verify", "--note", "ran again")
        self.assertTrue(self.denied(self.hook(self.bash('git commit -m "feat: y"'))))
        self.assertEqual(self.hook(self.bash('git commit -am "feat: y"')), "")
        self.ok("tier", "L0", "--reason", "typo", "--new")
        self.assertEqual(self.hook(self.bash('git commit -m "fix: typo"')), "")

    def verified_l1_with_untracked_record(self) -> str:
        self.ok("tier", "L1", "--reason", "small")
        self.ok("stage", "intent", "--note", "n")
        self.ok("stage", "plan", "--note", "p")
        self.ok("stage", "verify", "--note", "ran")
        return self.records()[0].relative_to(self.repo).as_posix()

    def test_staging_another_knowledge_path_does_not_count(self) -> None:  # R6, review M1
        relative = self.verified_l1_with_untracked_record()
        self.assertTrue(self.denied(self.hook(self.bash('git add knowledge/other.md && git commit -m "feat: x"'))))
        self.assertTrue(self.denied(self.hook(self.bash('git add knowledge-other && git commit -m "feat: x"'))))
        for staged in ("knowledge", "knowledge/history/", "knowledge/history/lifecycle", relative, "--all", "."):
            self.assertEqual(self.hook(self.bash(f'git add {staged} && git commit -m "feat: x"')), "", staged)

    def test_commit_all_flag_is_read_from_the_commit_command_only(self) -> None:  # R6, review L1
        relative = self.verified_l1_with_untracked_record()
        self.git("add", relative)
        self.git("commit", "-qm", "feat: x")
        self.ok("stage", "verify", "--note", "again")
        for command in ('ls -a && git commit -m "feat: y"', 'git commit -m "fix -a thing"', "git commit --amend --no-edit"):
            self.assertTrue(self.denied(self.hook(self.bash(command))), command)
        for command in ('git commit -a -m "feat: y"', 'git commit --all -m "feat: y"', 'git commit -qam "feat: y"'):
            self.assertEqual(self.hook(self.bash(command)), "", command)

    def test_staged_deletion_of_the_record_is_denied(self) -> None:  # R6, review L3
        relative = self.verified_l1_with_untracked_record()
        self.git("add", relative)
        self.git("commit", "-qm", "feat: x")
        self.git("rm", "-q", relative)
        self.assertTrue(self.denied(self.hook(self.bash('git commit -m "feat: y"'))))

    def test_state_from_before_the_audit_trail_reaches_verify(self) -> None:  # R5, review M2
        self.ok("tier", "L1", "--reason", "small")
        self.ok("stage", "intent", "--note", "n")
        self.ok("stage", "plan", "--note", "p")
        state = lifecycle.load(self.repo)
        del state["task"]
        lifecycle.state_path(self.repo).write_text(json.dumps(state))
        for path in self.records():
            path.unlink()
        self.ok("stage", "verify", "--note", "ran")
        self.assertEqual(len(self.records()), 1)

    def test_ref_is_stored_repo_relative(self) -> None:  # R2, review L5
        self.ok("tier", "L2", "--reason", "feature")
        self.ok("stage", "intent", "--ref", str(self.repo / "spec.md"), "--approved-by", "human:me")
        self.assertEqual(self.record()["stages"]["intent"]["ref"], "spec.md")


R1_REQ = 'The greeter MUST return "Hello, NAME".'
R1_ACC = "- R1: `python3 -m unittest test_greet.GreetTests.test_hello` passes.\n"
R2_REQ = "- R2: The greeter MUST reject an empty name.\n"
R2_ACC = "- R2: `python3 -m unittest test_greet.GreetTests.test_empty` passes.\n"


class SpecAnalysisTests(LifecycleCase):
    """Graded spec analysis (knowledge/specifications/spec-analysis-convergence.md R1 to R3)."""

    def lint(self, text: str) -> list:
        (self.repo / "spec.md").write_text(text)
        return lifecycle.lint_spec(self.repo / "spec.md")

    def cats(self, findings: list) -> list[tuple[str, str]]:
        return [(f.severity, f.category) for f in findings]

    def req(self, text: str) -> str:
        return SPEC.replace(R1_REQ, text)

    def test_duplicate_ids_reported_and_continuation_lines_kept(self) -> None:  # R1
        self.assertEqual(self.lint(SPEC), [])
        text = SPEC.replace(R2_REQ, R2_REQ + "- R1: The greeter MUST log each call.\n")
        text = text.replace(R2_ACC, R2_ACC + "- R1: `python3 -c 1` exits 0.\n")
        dups = [f for f in self.lint(text) if f.category == "duplicate-id"]
        self.assertEqual(sorted(dups), ["R1 is defined more than once under '## Acceptance'", "R1 is defined more than once under '## Requirements'"])
        self.assertEqual({f.severity for f in dups}, {"Critical"})
        continued = SPEC.replace(R2_REQ, "- R2: The greeter MUST reject an empty name\n  and answer quickly.\n\nA robust paragraph outside any bullet.\n")
        findings = self.lint(continued)
        self.assertEqual(findings, ["R2 uses the vague term 'quickly'"])
        self.assertEqual(self.cats(findings), [("High", "vague-term")])

    def test_lint_flags_modal_vague_identical_and_manual(self) -> None:  # R2
        no_modal = self.lint(self.req("The tool is fast."))
        self.assertEqual([f for f in no_modal if f.category == "missing-modal"], ["R1 has no MUST or SHOULD"])
        self.assertEqual(self.cats(self.lint(self.req("The tool MUST be fast."))), [("High", "vague-term")])
        self.assertEqual(self.lint(self.req("The tool MUST be fast.")), ["R1 uses the vague term 'fast'"])
        works = self.lint(SPEC.replace(R1_ACC, "- R1: `python3 -c 1` works well.\n"))
        self.assertEqual((works, self.cats(works)), (["acceptance R1 uses the vague term 'works well'"], [("High", "vague-term")]))
        twin = self.lint(SPEC.replace(R2_REQ, '- R2: the greeter  MUST return "hello, name".\n'))
        self.assertEqual((twin, self.cats(twin)), (["R2 repeats the text of R1"], [("High", "identical-requirements")]))
        manual = self.lint(SPEC.replace(R1_ACC, "- R1: A reviewer reads the greeting.\n"))
        self.assertEqual(manual, ["acceptance R1 has no backticked command; converge lists it as MANUAL"])
        self.assertEqual(self.cats(manual), [("Medium", "manual-check")])
        self.assertEqual(self.lint(self.req("The greeter MUST accept the `fast` flag.")), [])
        self.assertEqual(self.lint(SPEC.replace(R1_ACC, "- R1: `python3 -c \"print('etc')\"` exits 0.\n")), [])
        self.assertEqual(self.lint(self.req("The tool MUST answer within 200 ms.")), [])
        self.assertEqual(self.lint(self.req("The tool SHOULD answer within 200 ms.")), [])

    def test_project_vague_terms_extend_defaults(self) -> None:  # R2
        project = self.repo / "knowledge/project"
        project.mkdir(parents=True)
        (project / "guide.md").write_text("# Guide\n\n## Vague terms\n\n- snappy\n- `Blazing`\n\n## Other\n\n- zippy\n")
        (project / "bad.md").write_bytes(b"## Vague terms\n\n- \xff\xfe\n")
        self.assertEqual(self.lint(self.req("The tool MUST be snappy.")), ["R1 uses the vague term 'snappy'"])
        self.assertEqual(self.lint(self.req("The tool MUST be blazing.")), ["R1 uses the vague term 'blazing'"])
        self.assertEqual(self.lint(self.req("The tool MUST be zippy.")), [])
        self.assertEqual(self.lint(self.req("The tool MUST be fast.")), ["R1 uses the vague term 'fast'"])
        shutil.rmtree(self.repo / "knowledge")
        self.assertEqual(self.lint(self.req("The tool MUST be snappy.")), [])
        self.assertEqual(self.lint(self.req("The tool MUST be fast.")), ["R1 uses the vague term 'fast'"])

    def test_analyze_severities_and_exit_code(self) -> None:  # R3
        self.assertEqual(lifecycle.CATEGORY_SEVERITY, {
            "missing-section": "Critical", "no-requirements": "Critical", "duplicate-id": "Critical",
            "uncovered-requirement": "Critical", "orphan-acceptance": "Critical", "placeholder-acceptance": "Critical",
            "missing-modal": "High", "vague-term": "High", "identical-requirements": "High", "open-questions": "High",
            "manual-check": "Medium",
        })
        cases = {
            ("Critical", "missing-section"): SPEC.replace("## Non-goals\n\nLocalization.\n", ""),
            ("Critical", "no-requirements"): SPEC.replace("- R1: " + R1_REQ + "\n" + R2_REQ, ""),
            ("Critical", "uncovered-requirement"): SPEC.replace(R2_ACC, ""),
            ("Critical", "orphan-acceptance"): SPEC.replace(R2_ACC, R2_ACC + "- R3: `python3 -c 1` exits 0.\n"),
            ("Critical", "placeholder-acceptance"): SPEC.replace(R1_ACC, "- R1: `python3 -c 1` TBD.\n"),
            ("High", "missing-modal"): self.req("The greeter returns a greeting."),
            ("High", "open-questions"): SPEC.replace("None. The spec is ready for planning.", "- Which locale?"),
        }
        for pair, text in cases.items():
            self.assertIn(pair, self.cats(self.lint(text)), pair)
        mixed = self.req("The tool MUST be fast.").replace(R2_ACC, "- R2: A reviewer checks it.\n")
        mixed = mixed.replace(R2_REQ, R2_REQ + "- R2: The greeter MUST log each call.\n")
        (self.repo / "spec.md").write_text(mixed)
        code, out, _ = self.run_cli("analyze", "spec.md")
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertIn("Critical duplicate-id spec.md: R2 is defined more than once under '## Requirements'", lines)
        self.assertIn("High vague-term spec.md: R1 uses the vague term 'fast'", lines)
        self.assertIn("Medium manual-check spec.md: acceptance R2 has no backticked command; converge lists it as MANUAL", lines)
        (self.repo / "spec.md").write_text(self.req("The tool MUST be fast."))
        self.assertEqual(self.run_cli("analyze", "spec.md")[0], 1)
        (self.repo / "spec.md").write_text(SPEC.replace(R2_ACC, "- R2: A reviewer checks it.\n"))
        code, out, _ = self.run_cli("analyze", "spec.md")
        self.assertEqual(code, 0, out)
        self.assertIn("Medium manual-check spec.md:", out)
        (self.repo / "spec.md").write_text(SPEC)
        (self.repo / "other.md").write_text(self.req("The tool MUST be fast."))
        code, out, _ = self.run_cli("analyze", "spec.md", "other.md")
        self.assertEqual((code, out.strip()), (1, "High vague-term other.md: R1 uses the vague term 'fast'"))
        (self.repo / "other.md").write_text(SPEC)
        self.assertIn("analyze: OK, 2 spec(s)", self.ok("analyze", "spec.md", "other.md"))
        self.fails("analyze", "missing.md", message="missing.md")

    def test_only_critical_and_high_block_intent_plan_trace_and_queue(self) -> None:  # R3
        medium = SPEC.replace(R2_ACC, "- R2: A reviewer confirms an empty name is rejected.\n")
        high = self.req("The greeter MUST be fast.")
        spec = self.repo / "spec.md"
        self.ok("tier", "L2", "--reason", "feature")
        spec.write_text(high)
        self.fails("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me", message="spec is not ready")
        self.fails("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me", message="R1 uses the vague term 'fast'")
        spec.write_text(medium)
        code, out, err = self.run_cli("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")
        self.assertEqual(code, 0, out + err)
        self.assertIn("Medium manual-check spec.md:", err)
        code, out, err = self.run_cli("stage", "plan", "--ref", "plan.md")
        self.assertEqual(code, 0, out + err)
        self.assertIn("Medium manual-check spec.md:", err)
        code, out, err = self.run_cli("trace", "spec.md", "--plan", "plan.md")
        self.assertEqual(code, 0, out + err)
        self.assertIn("Medium manual-check spec.md:", err)
        code, out, err = self.run_cli("queue-from-spec", "spec.md")
        self.assertEqual(code, 0, err)
        self.assertIn("### SPEC-R2", out)
        self.assertNotIn("manual-check", out)
        self.assertIn("Medium manual-check spec.md:", err)
        spec.write_text(high)
        code, out, _ = self.run_cli("trace", "spec.md", "--plan", "plan.md")
        self.assertEqual(code, 1)
        self.assertIn("R1 uses the vague term 'fast'", out)
        self.fails("queue-from-spec", "spec.md", message="spec is not ready")
        self.fails("stage", "plan", "--ref", "plan.md", message="R1 uses the vague term 'fast'")
        spec.write_text(SPEC.replace(R2_ACC, ""))
        self.fails("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me", message="R2 has no acceptance check under '## Acceptance'")
        self.assertIn("R2 has no acceptance check under '## Acceptance'", self.run_cli("analyze", "spec.md")[1])


PY = shlex.quote(sys.executable)


class ConvergeTests(LifecycleCase):
    """Acceptance execution and the verify gate (knowledge/specifications/spec-analysis-convergence.md R4 to R6)."""

    def converge_spec(self, *checks: str) -> str:
        reqs = "".join(f"- R{n}: The tool MUST satisfy check {n}.\n" for n in range(1, len(checks) + 1))
        accs = "".join(f"- R{n}: {check}\n" for n, check in enumerate(checks, 1))
        head, tail = SPEC.split("## Requirements")[0], SPEC.split("## Constraints")[1]
        text = f"{head}## Requirements\n\n{reqs}\n## Acceptance\n\n{accs}\n## Constraints{tail}"
        (self.repo / "spec.md").write_text(text)
        (self.repo / "plan.md").write_text("# Plan\n\n" + "".join(f"### Step {n}: R{n}\n" for n in range(1, len(checks) + 1)))
        return text

    def approve(self) -> None:
        self.ok("tier", "L2", "--reason", "feature")
        self.ok("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")

    def record(self) -> tuple[Path, dict]:
        (path,) = sorted((self.repo / "knowledge/history/lifecycle").glob("*.json"))
        return path, json.loads(path.read_text())

    def test_converge_runs_acceptance_commands_and_records_results(self) -> None:  # R4
        self.converge_spec(
            f"`{PY} -c pass` exits 0.",
            f"`{PY} -c \"print('TAIL-' + 'R2-MARKER'); raise SystemExit(3)\"` exits 0.",
            f"`{PY} -c \"import time; time.sleep(5)\"` exits 0.",
            "A reviewer reads the output.",
        )
        self.approve()
        code, out, err = self.run_cli("converge", "spec.md", "--timeout", "1")
        self.assertEqual(code, 1, out + err)
        lines = out.splitlines()
        for line in ("R1 PASS", "R2 FAIL (exit 3)", "R3 FAIL (timeout)", "R4 MANUAL"):
            self.assertIn(line, lines)
        self.assertIn("TAIL-R2-MARKER", out)
        path, record = self.record()
        run = record["converge"]
        self.assertEqual([(r["id"], r["status"], r["exit"]) for r in run["results"]], [("R1", "PASS", 0), ("R2", "FAIL", 3), ("R3", "FAIL", None), ("R4", "MANUAL", None)])
        self.assertEqual(run["results"][0]["cmd"], f"{PY} -c pass")
        self.assertEqual(run["spec"], "spec.md")
        self.assertRegex(run["spec_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(run["tree"], r"^[0-9a-f]{64}$")
        self.assertNotIn("TAIL-R2-MARKER", path.read_text())
        self.assertNotIn("TAIL-R2-MARKER", json.dumps(lifecycle.load(self.repo)))
        self.assertEqual(lifecycle.load(self.repo)["converge"], run)
        self.converge_spec("`definitely-not-a-command-xyz --flag` exits 0.", "`bad 'quote` exits 0.")
        self.ok("tier", "L2", "--reason", "another spec", "--new")
        self.ok("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")
        code, out, err = self.run_cli("converge", "spec.md")
        self.assertEqual(code, 1, out + err)
        self.assertIn("R1 FAIL (cannot run)", out.splitlines())
        self.assertIn("R2 FAIL (cannot run)", out.splitlines())

    def test_converge_refuses_unbound_or_edited_spec_without_running_commands(self) -> None:  # R5
        text = self.converge_spec(f"`{PY} -c \"open('marker', 'w').close()\"` exits 0.")
        marker = self.repo / "marker"

        def refused(spec: str) -> None:
            code, out, err = self.run_cli("converge", spec)
            self.assertEqual(code, 1, out + err)
            self.assertIn("audit", out + err)
            self.assertFalse(marker.exists())

        refused("spec.md")
        self.ok("tier", "L1", "--reason", "small")
        refused("spec.md")
        self.approve()
        (self.repo / "other.md").write_text(text)
        refused("other.md")
        (self.repo / "spec.md").write_text(text.replace("check 1", "check one"))
        refused("spec.md")
        (self.repo / "spec.md").write_text(text)
        approved = lifecycle.load(self.repo)
        unapproved = json.loads(json.dumps(approved))
        del unapproved["stages"]["intent"]["approved_by"]
        lifecycle.state_path(self.repo).write_text(json.dumps(unapproved))
        refused("spec.md")
        lifecycle.state_path(self.repo).write_text(json.dumps(approved))
        self.assertIn("R1 PASS", self.ok("converge", "spec.md"))
        self.assertTrue(marker.exists())

    def test_verify_requires_current_passing_converge(self) -> None:  # R6
        self.ok("tier", "L1", "--reason", "small")
        self.ok("stage", "intent", "--note", "n")
        self.ok("stage", "plan", "--note", "p")
        self.ok("stage", "verify", "--note", "ran")
        (self.repo / "check.py").write_text("import sys; sys.exit(0 if open('flag').read().strip() == 'fixed' else 1)\n")
        (self.repo / "flag").write_text("broken\n")
        self.converge_spec(f"`{PY} check.py` exits 0.")
        self.git("add", "-A")
        self.git("commit", "-qm", "check")
        self.ok("tier", "L2", "--reason", "feature", "--new")
        self.ok("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")
        self.ok("stage", "plan", "--ref", "plan.md")
        self.ok("stage", "review", "--ref", "review.md")
        self.fails("stage", "verify", "--note", "ran", message="no converge run for spec.md")
        self.assertEqual(self.run_cli("converge", "spec.md")[0], 1)
        self.fails("stage", "verify", "--note", "ran", message="converge failed for R1")
        (self.repo / "flag").write_text("fixed\n")
        self.ok("converge", "spec.md")
        (self.repo / "app.py").write_text("print('changed')\n")
        self.fails("stage", "verify", "--note", "ran", message="stale")
        self.ok("converge", "spec.md")
        (self.repo / "notes.md").write_text("notes\n")
        (self.repo / "knowledge/note.md").write_text("notes\n")
        self.ok("stage", "verify", "--note", "ran")

    def test_verify_requires_review_note_for_manual_checks(self) -> None:  # R6
        self.converge_spec(f"`{PY} -c pass` exits 0.", "A reviewer confirms the greeting text.")
        self.approve()
        self.ok("stage", "plan", "--ref", "plan.md")
        self.ok("stage", "review", "--ref", "review.md")
        self.assertIn("R2 MANUAL", self.ok("converge", "spec.md").splitlines())
        self.fails("stage", "verify", "--note", "ran", message="manual check(s) R2 not cited in '## Validation Reviewed' of review.md")
        (self.repo / "review.md").write_text(REVIEW_OK + "\n## Validation Reviewed\nR1 PASS per converge.\n\n## Notes\nR2\n")
        self.ok("stage", "review", "--ref", "review.md")
        self.fails("stage", "verify", "--note", "ran", message="R2 not cited")
        (self.repo / "review.md").write_text(REVIEW_OK + "\n## Validation Reviewed\nR2 checked by reading the output.\n")
        self.ok("stage", "review", "--ref", "review.md")
        self.ok("stage", "verify", "--note", "ran")

    def test_converge_runs_commands_with_disk_backed_scratch_and_non_utf8_output(self) -> None:  # R4
        self.converge_spec(
            f"`{PY} -c \"import os; open('seen', 'w').write(os.environ['TMPDIR'])\"` exits 0.",
            f"`{PY} -c \"import sys; sys.stdout.buffer.write(bytes([255]))\"` exits 0.",
        )
        self.approve()
        previous = os.environ.get("TMPDIR")
        self.addCleanup(lambda: os.environ.__setitem__("TMPDIR", previous) if previous is not None else os.environ.pop("TMPDIR", None))
        os.environ["TMPDIR"] = "/tmp"
        self.assertEqual(self.ok("converge", "spec.md").splitlines()[:2], ["R1 PASS", "R2 PASS"])
        self.assertEqual(Path((self.repo / "seen").read_text()), lifecycle.scratch.directory(self.repo))

    def test_converge_refuses_without_disk_backed_scratch(self) -> None:  # R4
        self.converge_spec(f"`{PY} -c \"open('marker', 'w').close()\"` exits 0.")
        self.approve()
        real = lifecycle.scratch.environment

        def unusable(*_: object, **__: object) -> dict:
            raise ValueError("scratch must be outside system temporary storage")

        lifecycle.scratch.environment = unusable
        self.addCleanup(setattr, lifecycle.scratch, "environment", real)
        self.fails("converge", "spec.md", message="nothing was run: no disk-backed scratch directory")
        self.assertFalse((self.repo / "marker").exists())

    def test_l3_spec_ref_requires_converge_and_queue_intent_does_not(self) -> None:  # R6
        self.converge_spec(f"`{PY} -c pass` exits 0.")
        self.ok("tier", "L3", "--reason", "milestone")
        self.ok("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")
        self.ok("stage", "plan", "--ref", "plan.md")
        self.ok("stage", "review", "--ref", "review.md")
        self.fails("stage", "verify", "--note", "ran", message="no converge run for spec.md")
        self.ok("converge", "spec.md")
        self.ok("stage", "verify", "--note", "ran")
        (self.repo / "knowledge/project").mkdir(parents=True, exist_ok=True)
        (self.repo / "knowledge/project/work-queue.md").write_text("# Work queue\n")
        self.ok("tier", "L3", "--reason", "queue batch", "--new")
        self.ok("stage", "intent", "--note", "queue:T1", "--approved-by", "human:me")
        self.ok("stage", "plan", "--note", "queue:T1")
        self.ok("stage", "review", "--ref", "review.md")
        self.ok("run", "unit", "--", PY, "-c", "pass")  # The queue intent has no converge run, so the ledger must supply the evidence.
        self.ok("stage", "verify", "--note", "ran")

    def test_reapproved_spec_or_new_head_stales_the_run(self) -> None:  # R6
        text = self.converge_spec(f"`{PY} -c pass` exits 0.")
        self.approve()
        self.ok("stage", "plan", "--ref", "plan.md")
        self.ok("stage", "review", "--ref", "review.md")
        self.ok("converge", "spec.md")
        (self.repo / "spec.md").write_text(text.replace("check 1", "check one"))
        self.ok("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")
        self.fails("stage", "verify", "--note", "ran", message="spec.md changed since the run")
        self.ok("converge", "spec.md")
        (self.repo / "knowledge").mkdir(exist_ok=True)
        (self.repo / "knowledge/note.md").write_text("records only\n")
        self.git("add", "knowledge/note.md")
        self.git("commit", "-qm", "wip: records")
        self.fails("stage", "verify", "--note", "ran", message="HEAD or a source file changed since the run")


if __name__ == "__main__":
    unittest.main()
