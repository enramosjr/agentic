"""Tests for the evidence ledger: `lifecycle.py run`, the verify requirements built on it, and
`lifecycle.py reuse` (AGENTS.md §8.4).

Run: python3 .ai/scripts/tests/test_ledger.py
"""

from __future__ import annotations

import json
import shlex
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ledger  # noqa: E402
import lifecycle  # noqa: E402
from test_lifecycle import LifecycleCase  # noqa: E402

PY = sys.executable
SCHEMA = {"label", "argv", "exit", "tree", "head", "duration", "at", "inputs", "inputs_sha256"}


class LedgerCase(LifecycleCase):
    def entries(self) -> list[dict]:
        return lifecycle.load(self.repo).get("ledger", [])

    def head(self) -> str:
        return lifecycle.head_sha(self.repo)


class LedgerRunTests(LedgerCase):
    def test_runs_argv_without_shell_in_scratch_and_refuses_without_tier(self) -> None:
        marker = self.repo / "marker.txt"
        probe = "import os, sys; open('marker.txt', 'w').write('x')"
        self.fails("run", "a", "--", PY, "-c", probe, message="no active lifecycle")
        self.assertFalse(marker.exists())
        self.ok("tier", "L1", "--reason", "small")
        script = (
            "import json, os, sys\n"
            "open('probe.json', 'w').write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd(), 'stdin': sys.stdin.read(),"
            " 'env': [os.environ.get(k) for k in ('TMPDIR', 'TMP', 'TEMP')]}))\n"
        )
        self.ok("run", "probe", "--", PY, "-c", script, "x; touch shell_ran", "$HOME")
        probe_data = json.loads((self.repo / "probe.json").read_text())
        self.assertEqual(probe_data["argv"], ["x; touch shell_ran", "$HOME"])
        self.assertFalse((self.repo / "shell_ran").exists())
        self.assertEqual(Path(probe_data["cwd"]).resolve(), self.repo)
        self.assertEqual(probe_data["stdin"], "")
        scratch_dir = str(lifecycle.scratch.directory(self.repo))
        self.assertEqual(probe_data["env"], [scratch_dir] * 3)
        with mock.patch.object(lifecycle.scratch, "environment", side_effect=ValueError("tmpfs")):
            self.fails("run", "b", "--", PY, "-c", probe, message="nothing was run")
        self.assertFalse(marker.exists())

    def test_entry_schema_exit_status_timeout_and_tail_on_failure(self) -> None:
        self.ok("tier", "L1", "--reason", "small")
        noisy = "for i in range(1, 21): print('line%d' % i)"
        code, out, _ = self.run_cli("run", "good", "--", PY, "-c", noisy)
        self.assertEqual(code, 0)
        self.assertNotIn("line20", out)  # Output is shown only on failure.
        first = self.entries()[-1]
        self.assertEqual(set(first), SCHEMA)
        self.assertEqual((first["label"], first["exit"], first["inputs"], first["inputs_sha256"]), ("good", 0, [], None))
        self.assertEqual(first["argv"], [PY, "-c", noisy])
        self.assertEqual(first["head"], self.head())
        self.assertEqual(first["tree"], lifecycle.tree_hash(self.repo))
        self.assertEqual(first["duration"], round(first["duration"], 3))
        code, out, _ = self.run_cli("run", "bad", "--", PY, "-c", noisy + "\nraise SystemExit(3)")
        self.assertEqual(code, 3)
        self.assertIn("line20", out)
        self.assertIn("line9", out)
        self.assertNotIn("line8\n", out)  # Only the last 12 lines.
        self.assertEqual(self.entries()[-1]["exit"], 3)
        code, _, _ = self.run_cli("run", "slow", "--timeout", "1", "--", PY, "-c", "import time; time.sleep(30)")
        self.assertEqual(code, 1)
        self.assertIsNone(self.entries()[-1]["exit"])
        code, _, _ = self.run_cli("run", "ghost", "--", "definitely-not-a-binary-xyz")
        self.assertEqual(code, 1)
        self.assertIsNone(self.entries()[-1]["exit"])

    def test_record_has_no_output_and_old_records_without_ledger_audit_clean(self) -> None:
        self.ok("tier", "L1", "--reason", "small")
        self.run_cli("run", "bad", "--", PY, "-c", "print('SECRET' + 'LINE'); raise SystemExit(2)")
        state = lifecycle.load(self.repo)
        text = lifecycle.record_path(self.repo, state).read_text()
        self.assertIn('"ledger"', text)
        self.assertNotIn("SECRETLINE", text)
        record = json.loads(text)
        self.assertEqual(record["version"], 1)
        self.assertNotIn("ledger", lifecycle.RECORD_KEYS)
        self.assertEqual(lifecycle.audit_problems(self.repo, record), [])
        for key in ("tail", "output", "stdout", "stderr", "surprise"):
            tainted = json.loads(text)
            tainted["ledger"][0][key] = "x"
            problems = lifecycle.audit_problems(self.repo, tainted)
            self.assertTrue(any("ledger" in p and key in p for p in problems), (key, problems))
        del record["ledger"]
        self.assertEqual(lifecycle.audit_problems(self.repo, record), [])

    def test_ledger_keeps_newest_100_entries(self) -> None:
        self.ok("tier", "L1", "--reason", "small")
        for index in range(101):
            self.ok("run", f"n{index}", "--", PY, "-c", "pass")
        labels = [entry["label"] for entry in self.entries()]
        self.assertEqual(len(labels), 100)
        self.assertEqual((labels[0], labels[-1]), ("n1", "n100"))


class ReuseTests(LedgerCase):
    def test_input_globs_match_rules_and_reject_absolute_and_dotdot(self) -> None:
        self.assertTrue(ledger.matches("src/*.py", "src/a.py"))
        self.assertTrue(ledger.matches("docs/", "docs/x/y.txt"))
        self.assertTrue(ledger.matches("app.py", "app.py"))
        self.assertFalse(ledger.matches("src/*.py", "src/a.txt"))
        self.assertFalse(ledger.matches("docs/", "docsx/y.txt"))
        for bad in ("/etc/passwd", "../x", "a/../b", "a/.."):
            with self.assertRaises(ValueError):
                ledger.check_globs([bad])
        self.assertEqual(ledger.check_globs(["src/*.py", "docs/"]), ["src/*.py", "docs/"])
        self.ok("tier", "L1", "--reason", "small")
        marker = self.repo / "marker.txt"
        probe = "open('marker.txt', 'w').write('x')"
        self.fails("run", "bad", "--inputs", "../x", "--", PY, "-c", probe, message="..")
        self.fails("run", "bad", "--inputs", "/abs", "--", PY, "-c", probe, message="absolute")
        self.assertFalse(marker.exists())

    def test_reuse_by_label_and_by_command_prints_verdict_and_exit_code(self) -> None:
        self.ok("tier", "L1", "--reason", "small")
        self.ok("run", "unit", "--inputs", "app.py", "--", PY, "-c", "pass")
        short = self.head()[:7]
        code, out, _ = self.run_cli("reuse", "unit")
        self.assertEqual((code, out.strip()), (0, f"REUSE unit head={short}"))
        code, out, _ = self.run_cli("reuse", shlex.join([PY, "-c", "pass"]))
        self.assertEqual((code, out.strip()), (0, f"REUSE unit head={short}"))
        code, out, err = self.run_cli("reuse", "other")
        self.assertEqual(code, 1)
        self.assertTrue((out + err).startswith("RERUN"), out + err)
        (self.repo / "unrelated.txt").write_text("x\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "unrelated")
        self.assertEqual(self.run_cli("reuse", "unit")[0], 0)  # A commit outside the inputs leaves the entry reusable.

    def test_rerun_on_each_condition_failed_unknown_inputs_input_commit_dirty_edit_unresolvable_head(self) -> None:
        self.ok("tier", "L1", "--reason", "small")

        def verdict(arg: str) -> str:
            code, out, err = self.run_cli("reuse", arg)
            self.assertEqual(code, 1, out + err)
            return (out + err).strip()

        self.assertIn("no ledger entry", verdict("ghost"))
        self.run_cli("run", "failed", "--inputs", "app.py", "--", PY, "-c", "raise SystemExit(1)")
        self.assertIn("exited 1", verdict("failed"))
        self.ok("run", "bare", "--", PY, "-c", "pass")
        self.assertIn("no --inputs", verdict("bare"))
        self.ok("run", "dirty", "--inputs", "app.py", "--", PY, "-c", "pass")
        (self.repo / "app.py").write_text("print('edited')\n")
        self.assertIn("edited since", verdict("dirty"))
        self.ok("run", "committed", "--inputs", "app.py", "--", PY, "-c", "pass")
        self.git("commit", "-qam", "change input")
        self.assertIn("changed in a commit", verdict("committed"))
        self.ok("run", "fresh", "--inputs", "*.py", "--", PY, "-c", "pass")
        self.assertEqual(self.run_cli("reuse", "fresh")[0], 0)
        (self.repo / "new_module.py").write_text("x = 1\n")  # An untracked file inside the glob changes the digest.
        self.assertIn("edited since", verdict("fresh"))
        (self.repo / "new_module.py").unlink()
        state = lifecycle.load(self.repo)
        state["ledger"][-1]["head"] = "0" * 40
        lifecycle.save(self.repo, state)
        self.assertIn("not resolvable", verdict("fresh"))

    def test_reuse_runs_nothing_and_leaves_ledger_unchanged(self) -> None:
        self.ok("tier", "L1", "--reason", "small")
        counter = "import pathlib; p = pathlib.Path('count.txt'); p.write_text(p.read_text() + 'x' if p.exists() else 'x')"
        self.ok("run", "count", "--inputs", "app.py", "--", PY, "-c", counter)
        state_file = lifecycle.state_path(self.repo)
        record = lifecycle.record_path(self.repo, lifecycle.load(self.repo))
        before = (state_file.read_bytes(), record.read_bytes(), (self.repo / "count.txt").read_text())
        self.assertEqual(self.run_cli("reuse", "count")[0], 0)
        self.assertEqual(self.run_cli("reuse", "missing")[0], 1)
        self.assertEqual((state_file.read_bytes(), record.read_bytes(), (self.repo / "count.txt").read_text()), before)


class LedgerVerifyTests(LedgerCase):
    def l2_to_verify(self) -> None:
        """An L2 task with approved intent, traced plan and approved review, ready for converge and verify."""
        self.ok("tier", "L2", "--reason", "feature", "--kind", "feature")
        self.ok("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")
        self.ok("stage", "plan", "--ref", "plan.md")
        self.ok("stage", "review", "--ref", "review.md")

    def l3_to_verify(self, kind: str = "feature", new: bool = False) -> None:
        """An L3 task on a queue intent: no spec, so no converge entries; the ledger alone must satisfy verify."""
        queue = self.repo / "knowledge/project/work-queue.md"
        queue.parent.mkdir(parents=True, exist_ok=True)
        queue.write_text("# Work queue\n")
        self.ok("tier", "L3", "--reason", "queued", "--kind", kind, *(["--new"] if new else []))
        self.ok("stage", "intent", "--note", "queue:T1", "--approved-by", "decision:ADR-1")
        self.ok("stage", "plan", "--note", "queue:T1")
        self.ok("stage", "review", "--ref", "review.md")

    def test_verify_needs_passing_current_entry_at_l2_and_not_at_l1(self) -> None:
        self.ok("tier", "L1", "--reason", "small")
        self.ok("stage", "intent", "--note", "goal; check; none")
        self.ok("stage", "plan", "--note", "edit app.py")
        self.fails("stage", "verify", message="--note")  # L1 keeps its required note.
        self.ok("stage", "verify", "--note", "ran tests by hand")  # And needs no ledger entry.
        self.l3_to_verify(new=True)
        self.fails("stage", "verify", "--note", "claimed green", message="lifecycle.py run LABEL -- CMD")
        self.ok("run", "unit", "--", PY, "-c", "pass")
        (self.repo / "app.py").write_text("print('changed after the run')\n")
        self.fails("stage", "verify", message="lifecycle.py run LABEL -- CMD")  # The entry is stale.
        self.ok("run", "unit", "--inputs", "docs/", "--", PY, "-c", "pass")
        (self.repo / "app.py").write_text("print('changed again')\n")
        self.ok("stage", "verify")  # Stale by tree, but `reuse` evaluates its label as REUSE.

    def test_newest_failing_entry_on_current_tree_blocks_verify(self) -> None:
        self.l3_to_verify()
        self.ok("run", "good", "--", PY, "-c", "pass")
        self.ok("run", "flaky", "--", PY, "-c", "pass")
        self.run_cli("run", "flaky", "--", PY, "-c", "raise SystemExit(1)")
        self.fails("stage", "verify", message="flaky")
        self.ok("run", "flaky", "--", PY, "-c", "pass")
        self.ok("stage", "verify")

    def test_generated_note_stored_and_agent_note_labelled(self) -> None:
        self.l3_to_verify()
        self.ok("run", "alpha", "--", PY, "-c", "pass")
        self.ok("run", "beta", "--", PY, "-c", "pass")
        short = lifecycle.tree_hash(self.repo)[:7]
        generated = f"alpha exit=0 tree={short}; beta exit=0 tree={short}"
        self.ok("stage", "verify", "--note", "my own words")
        stored = lifecycle.load(self.repo)["stages"]["verify"]["note"]
        self.assertEqual(stored, f"{generated} | agent note: my own words")
        record = json.loads(lifecycle.record_path(self.repo, lifecycle.load(self.repo)).read_text())
        self.assertEqual(record["stages"]["verify"]["note"], stored)
        self.ok("stage", "verify")
        self.assertEqual(lifecycle.load(self.repo)["stages"]["verify"]["note"], generated)

    def test_guard_and_autonomous_env_do_not_bypass_verify_checks(self) -> None:
        self.l3_to_verify()
        with mock.patch.dict("os.environ", {"LIFECYCLE_GUARD": "off", "OKF_AUTONOMOUS": "1"}):
            self.fails("stage", "verify", "--note", "claimed green", message="lifecycle.py run LABEL -- CMD")
            self.ok("run", "unit", "--", PY, "-c", "pass")
            self.run_cli("run", "unit", "--", PY, "-c", "raise SystemExit(1)")
            self.fails("stage", "verify", message="unit")
            code, _, err = self.run_cli("reuse", "unit")
            self.assertEqual(code, 1, err)

    def test_bugfix_still_needs_redgreen_and_redgreen_is_not_ledger_evidence(self) -> None:
        self.l3_to_verify(kind="bugfix")
        self.ok("run", "unit", "--", PY, "-c", "pass")
        self.fails("stage", "verify", message="red/green")
        check = "import pathlib, sys; sys.exit(0 if 'fixed' in pathlib.Path('app.py').read_text() else 1)"
        self.ok("redgreen", "red", "--", PY, "-c", check)
        (self.repo / "app.py").write_text("print('fixed')\n")
        self.ok("redgreen", "green", "--", PY, "-c", check)
        self.assertEqual([e["label"] for e in self.entries()], ["unit"])  # redgreen wrote no ledger entry.
        self.fails("stage", "verify", message="lifecycle.py run LABEL -- CMD")  # The earlier entry is for another tree.
        self.ok("run", "unit", "--", PY, "-c", check)
        self.ok("stage", "verify")

    def test_converge_appends_labelled_entries(self) -> None:
        self.l2_to_verify()
        self.converge_green()
        entries = self.entries()
        self.assertEqual([e["label"] for e in entries], ["converge:R1", "converge:R2"])
        for entry, test in zip(entries, ("test_hello", "test_empty")):
            self.assertEqual(set(entry), SCHEMA)
            self.assertEqual(entry["argv"], ["python3", "-m", "unittest", f"test_greet.GreetTests.{test}"])
            self.assertEqual((entry["exit"], entry["inputs"], entry["inputs_sha256"]), (0, [], None))
            self.assertEqual(entry["tree"], lifecycle.tree_hash(self.repo))
        self.assertEqual(set(lifecycle.load(self.repo)["converge"]), {"spec", "spec_sha256", "tree", "at", "results"})
        (self.repo / "test_greet.py").write_text((self.repo / "test_greet.py").read_text().replace("def test_empty(self):\n        pass", "def test_empty(self):\n        self.fail('x')"))
        self.run_cli("converge", "spec.md")
        self.assertEqual([e["exit"] for e in self.entries()][-2:], [0, 1])
        self.assertEqual(len(self.entries()), 4)


if __name__ == "__main__":
    unittest.main()
