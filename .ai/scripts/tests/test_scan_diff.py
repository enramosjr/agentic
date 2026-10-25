"""Tests for `lifecycle.py scan-diff` (AGENTS.md §8.1 stubs and weak tests as a fail-closed scan).

Every marker below is assembled from parts, so this file does not trip the scan it tests.
Run: python3 .ai/scripts/tests/test_scan_diff.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lifecycle  # noqa: E402
from test_lifecycle import LifecycleCase  # noqa: E402

TODO_MACRO = "todo" + "!()"
UNIMPL_MACRO = "unimplemented" + "!()"
NOT_IMPL_ERROR = "NotImplemented" + "Error"
NOT_IMPL_EXC = "NotImplemented" + "Exception"
NOT_IMPL_OTHER = "NotImplemented" + "Thing"
TODO = "TO" + "DO"
FIXME = "FIX" + "ME"
FUTURE = "future" + " work"
WIRE = "will wire" + " later"
ALLOW = "lifecycle" + ":allow"
PASS = "def f():\n    pas" + "s"


class ScanCase(LifecycleCase):
    def git_out(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout.strip()

    def put(self, path: str, text: str) -> None:
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def scan(self, *argv: str) -> tuple[int, dict]:
        code, out, _ = self.run_cli("scan-diff", "--json", *argv)
        return code, json.loads(out)

    def found(self, *argv: str) -> set[tuple[str, str, int]]:
        return {(f["rule"], f["path"], f["line"]) for f in self.scan(*argv)[1]["findings"] if not f["waived"]}

    def rules(self, path: str) -> set[str]:
        return {rule for rule, p, _ in self.found() if p == path}


class ScanDiffTests(ScanCase):
    def test_scans_added_lines_only_untracked_included_markdown_skipped(self) -> None:
        self.put("old.py", f"def a():\n    raise {NOT_IMPL_ERROR}\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "old stub")
        self.assertEqual(self.scan(), (0, {"findings": [], "unscanned": []}), "a committed stub is not an added line")

        self.put("old.py", f"def a():\n    raise {NOT_IMPL_ERROR}\n\ndef b():\n    return 1\n")
        self.assertEqual(self.scan()[1]["findings"], [], "unchanged stub lines are not scanned")

        self.put("new.py", f"x = 1\nraise {NOT_IMPL_ERROR}\n")
        self.put("notes.md", f"- {FUTURE}\n")
        self.put("knowledge/log.md", f"{FUTURE}\n")
        code, report = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["path"], f["line"]) for f in report["findings"]], [("C1-stub", "new.py", 2)])

        self.git("add", "-A")
        self.git("commit", "-qm", "new")
        self.assertEqual(self.found(), set())
        first = self.git_out("rev-list", "--max-parents=0", "HEAD")
        self.assertIn(("C1-stub", "new.py", 2), self.found("--base", first))

    def test_each_critical_rule_fails_and_exit_code_is_one(self) -> None:
        cases = {
            "c1a.rs": (f"fn f() {{ {TODO_MACRO} }}\n", "C1-stub"),
            "c1b.rs": (f"fn f() {{ {UNIMPL_MACRO} }}\n", "C1-stub"),
            "c1c.py": (f"raise {NOT_IMPL_ERROR}\n", "C1-stub"),
            "c1d.cs": (f"throw new {NOT_IMPL_EXC}();\n", "C1-stub"),
            "c1e.py": (f"raise {NOT_IMPL_OTHER}\n", "C1-stub"),
            "c2.py": (PASS + "  # " + TODO + " later\n", "C2-pass-todo"),
            "c2b.py": (PASS + " # " + FIXME + "\n", "C2-pass-todo"),
            "c3a.py": (f"# Reuse is {FUTURE.title()}\n", "C3-deferred"),
            "c3b.py": (f"# the caller {WIRE.upper()}\n", "C3-deferred"),
        }
        for path, (text, rule) in cases.items():
            self.put(path, text)
            code, report = self.scan()
            self.assertEqual(code, 1, path)
            self.assertIn(rule, {f["rule"] for f in report["findings"] if f["path"] == path}, path)
            (self.repo / path).unlink()
        self.put("fine.py", "def f():\n    return NotImplemented\n\nx = 1  # a pass-through\n")
        self.assertEqual(self.scan(), (0, {"findings": [], "unscanned": []}))
        code, out, _ = self.run_cli("scan-diff")
        self.assertEqual(code, 0)
        self.put("bad.py", f"raise {NOT_IMPL_ERROR}\n")
        code, out, _ = self.run_cli("scan-diff")
        self.assertEqual(code, 1)
        self.assertIn("CRITICAL C1-stub bad.py:1", out)

    def test_each_high_rule_is_reported_without_failing(self) -> None:
        self.put("h1.py", f"# {TODO}: later\n# {FIXME} too\n")
        self.put("test_h2.py", "import unittest\n\nclass T(unittest.TestCase):\n    def test_nothing(self):\n        x = 1\n")
        self.put("h2.rs", "#[test]\nfn nothing() {\n    let x = 1;\n}\n")
        self.put("h2_test.go", "package a\n\nfunc TestNothing(t *testing.T) {\n\t_ = 1\n}\n")
        self.put("h4.py", "@unittest.skip('x')\ndef a(): pass\n\n@pytest.mark.xfail\ndef b(): pass\n\npytest.skip('y')\n@unittest.skipUnless(True, 'cond')\ndef c(): pass\n")
        self.put("h4.go", "func TestA(t *testing.T) {\n\tt.Skip()\n\tt.Fatal(1)\n}\n")
        self.put("h4.rs", "#[ignore]\n#[test]\nfn a() { assert!(true); }\n")
        code, report = self.scan()
        self.assertEqual(code, 0, report)
        found = {(f["rule"], f["path"], f["line"]) for f in report["findings"]}
        self.assertEqual(
            found,
            {
                ("H1-todo", "h1.py", 1), ("H1-todo", "h1.py", 2),
                ("H2-no-assert", "test_h2.py", 4), ("H2-no-assert", "h2.rs", 2), ("H2-no-assert", "h2_test.go", 3),
                ("H4-skip", "h4.py", 1), ("H4-skip", "h4.py", 4), ("H4-skip", "h4.py", 7),
                ("H4-skip", "h4.go", 2), ("H4-skip", "h4.rs", 1),
            },
        )
        self.assertTrue(all(f["severity"] == "high" for f in report["findings"]))
        code, out, _ = self.run_cli("scan-diff")
        self.assertEqual(code, 0)
        self.assertIn("HIGH H2-no-assert test_h2.py:4", out)

        # H3: a file whose removed assertion lines outnumber its added ones.
        self.put("strong.py", "def test_a(self):\n    assert 1\n    assert 2\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        self.put("strong.py", "def check(self):\n    assert 1\n")
        code, report = self.scan()
        self.assertEqual(code, 0, report)
        self.assertEqual({(f["rule"], f["path"]) for f in report["findings"]}, {("H3-assert-removed", "strong.py")})

    def test_assertion_tokens_per_language_and_unscanned_note(self) -> None:
        self.put("test_ok.py", "class T:\n    def test_a(self):\n        self.assertEqual(1, 1)\n    def test_b(self):\n        assert 1\n"
                 "    def test_c(self):\n        with pytest.raises(ValueError):\n            f()\n    def test_d(self):\n        self.fail('x')\n")
        self.put("ok.rs", "#[test]\nfn a() { assert_eq!(1, 1); }\n#[test]\nfn b() { panic!(\"x\"); }\n#[test]\n#[should_panic]\nfn c() { f(); }\n")
        self.put("ok_test.go", "func TestA(t *testing.T) {\n\tt.Errorf(\"x\")\n}\nfunc TestB(t *testing.T) {\n\tt.Fatal(1)\n}\nfunc TestC(t *testing.T) {\n\tt.Fail()\n}\n")
        self.put("spec.test.js", "test('a', () => { expect(1).toBe(1); });\n")
        self.put("run.sh", "echo hi\n")
        code, report = self.scan()
        self.assertEqual(code, 0)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["unscanned"], [".js", ".sh"])
        code, out, _ = self.run_cli("scan-diff")
        self.assertIn("unscanned for H2-H3: .js, .sh", out)

    def test_waiver_needs_matching_rule_and_reason_and_is_still_printed(self) -> None:
        stub = f"raise {NOT_IMPL_ERROR}"
        self.put("same.py", f"{stub}  # {ALLOW} C1-stub -- fixture for the scan\n")
        self.put("before.py", f"# {ALLOW} C1-stub -- fixture for the scan\n{stub}\n")
        self.put("noreason.py", f"{stub}  # {ALLOW} C1-stub\n")
        self.put("emptyreason.py", f"{stub}  # {ALLOW} C1-stub --   \n")
        self.put("wrong.py", f"{stub}  # {ALLOW} C3-deferred -- not this rule\n")
        self.put("far.py", f"# {ALLOW} C1-stub -- too far away\nx = 1\n{stub}\n")
        code, report = self.scan()
        self.assertEqual(code, 1)
        waived = {f["path"] for f in report["findings"] if f["waived"]}
        blocking = {f["path"] for f in report["findings"] if not f["waived"]}
        self.assertEqual(waived, {"same.py", "before.py"})
        self.assertEqual(blocking, {"noreason.py", "emptyreason.py", "wrong.py", "far.py"})
        for path in ("noreason.py", "emptyreason.py", "wrong.py", "far.py"):
            (self.repo / path).unlink()
        code, out, _ = self.run_cli("scan-diff")
        self.assertEqual(code, 0)
        self.assertIn("WAIVED C1-stub same.py:1 -- fixture for the scan", out)
        self.assertIn("WAIVED C1-stub before.py:2 -- fixture for the scan", out)


class ScanStageTests(ScanCase):
    STUB = f"raise {NOT_IMPL_ERROR}\n"

    def l1_to_review(self) -> None:
        self.ok("tier", "L1", "--reason", "x")
        self.ok("stage", "intent", "--note", "n")
        self.ok("stage", "plan", "--note", "p")

    def test_review_and_verify_fail_on_unwaived_critical_at_l1_and_l2(self) -> None:
        self.l1_to_review()
        self.put("bad.py", self.STUB)
        self.ok("retrospect", "--no-new-lessons", "This fixture adds no new project lessons.")
        self.fails("stage", "review", "--note", "self-review", message="C1-stub bad.py:1")
        self.fails("stage", "verify", "--note", "ran", message="C1-stub bad.py:1")
        self.put("bad.py", f"{self.STUB[:-1]}  # {ALLOW} C1-stub -- fixture\n")
        self.ok("stage", "review", "--note", "self-review")
        self.ok("stage", "verify", "--note", "ran")
        self.ok("stage", "ship")

        self.ok("tier", "L2", "--reason", "feature", "--new")
        self.ok("stage", "intent", "--ref", "spec.md", "--approved-by", "human:me")
        self.ok("stage", "plan", "--ref", "plan.md")
        self.put("worse.py", self.STUB)
        self.fails("stage", "review", "--ref", "review.md", message="C1-stub worse.py:1")
        (self.repo / "worse.py").unlink()
        self.ok("stage", "review", "--ref", "review.md")
        self.put("worse.py", self.STUB)
        self.converge_green()
        self.ok("retrospect", "--no-new-lessons", "The L2 scan fixture adds no new project lessons.")
        self.fails("stage", "verify", message="C1-stub worse.py:1")
        (self.repo / "worse.py").unlink()
        self.converge_green()
        self.ok("stage", "verify")

    def test_scan_writes_nothing_to_record(self) -> None:
        self.l1_to_review()
        self.put("bad.py", self.STUB)
        self.ok("retrospect", "--no-new-lessons", "This fixture adds no new project lessons.")
        files = [lifecycle.state_path(self.repo), lifecycle.record_path(self.repo, lifecycle.load(self.repo))]
        before = [path.read_bytes() for path in files]
        self.fails("stage", "review", "--note", "self-review", message="C1-stub")
        self.fails("stage", "verify", "--note", "ran", message="C1-stub")
        self.run_cli("scan-diff")
        self.assertEqual([path.read_bytes() for path in files], before)
        self.put("bad.py", f"{self.STUB[:-1]}  # {ALLOW} C1-stub -- fixture\n")
        self.ok("stage", "review", "--note", "self-review")
        for path in files:
            text = path.read_text()
            self.assertNotIn("NotImplemented", text)
            self.assertNotIn("scan", text.replace("scratch", ""))


if __name__ == "__main__":
    unittest.main()
