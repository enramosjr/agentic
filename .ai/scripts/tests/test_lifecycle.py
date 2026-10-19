"""Behavioral tests for lifecycle.py: tier and stage gates, spec traceability, red/green
evidence, queue-from-spec, and the harness hooks.

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
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

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
        self.fails("stage", "verify", message="--note")
        self.ok("stage", "verify", "--note", "unit tests PASS")
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


if __name__ == "__main__":
    unittest.main()
