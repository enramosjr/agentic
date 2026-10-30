"""Increment 7 acceptance: independent oracles and real assurance subprocesses."""
import ast
from dataclasses import replace
from functools import lru_cache
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))
import disk_tmp  # noqa: E402,F401
import assurance_demo  # noqa: E402
import assurance_measure as measure  # noqa: E402

NAMES = ("feature", "requirement-change", "regression", "stale-evidence", "dependency", "handoff")
LIMIT = "Measures mechanism behavior on fixtures, not agent outcomes."
METRICS = ("caught", "false_stale", "missed", "changed_missed", "reruns", "baseline_reruns")
EXPECTED = {
    "feature": [(1, 0, 0, 0, 1, 2)],
    "requirement-change": [(1, 0, 0, 1, 1, 2)],
    "regression": [(1, 0, 0, 0, 1, 2)],
    "stale-evidence": [(0, 0, 0, 0, 0, 2), (1, 0, 0, 0, 1, 2)],
    "dependency": [(2, 0, 0, 0, 2, 2), (0, 0, 1, 1, 0, 2), (0, 1, 0, 0, 1, 3)],
    "handoff": [(1, 0, 0, 0, 1, 2)],
}
TOTALS = dict(zip(METRICS, (7, 1, 1, 2, 8, 19)))
CONTRIBUTION = {"reruns_avoided": 11, "whole_tree_false_stale": 1,
                "changed_listed": 6, "changed_missed": 2, "handoff_from_record": 1}


def hook_status(status, conditional=False, no_evidence=False):
    def hook(scripts):
        path = scripts / "assurance.py"
        suffix = ("\n_original = evaluate\ndef evaluate(*a, **k):\n"
                  "    result = _original(*a, **k)\n")
        if conditional:
            suffix += "    if result[\"status\"] == \"STALE\":\n        result[\"status\"] = \"VERIFIED\"\n"
        else:
            suffix += f"    result[\"status\"] = {status!r}\n"
        if no_evidence:
            suffix += "    result[\"evidence\"] = None\n"
        path.write_text(path.read_text() + suffix + "    return result\n")
    return hook


def snapshot():
    paths = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    result = {}
    for name in paths.split(b"\0"):
        if name:
            path = ROOT / os.fsdecode(name)
            result[name] = os.readlink(path) if path.is_symlink() else path.read_bytes()
    return result


@lru_cache(maxsize=1)
def observed():
    """One full run shared by read-only classes, including command and status evidence."""
    calls, repos, statuses, clean = [], [], [], []
    real = assurance_demo.Session.exec

    def spy(session, argv, *args, **kwargs):
        result = real(session, argv, *args, **kwargs)
        calls.append((str(session.repo), list(argv)))
        if "assure" in argv and "--json" in argv:
            statuses.append(json.loads(result.stdout))
        if argv[-3:-1] == ["commit", "-qm"]:
            check = real(session, ["git", "status", "--porcelain"])
            clean.append(check.stdout)
        return result

    def hook(scripts):
        repos.append(scripts.parents[1])
        capability = scripts.parents[1] / "knowledge/capabilities/measure.md"
        assert "MEAS-R1" in capability.read_text()

    before = snapshot()
    with tempfile.TemporaryDirectory() as directory:
        with mock.patch.object(assurance_demo.Session, "exec", spy):
            data = measure.measure(base=Path(directory), hook=hook)
        leftovers = list(Path(directory).iterdir())
    return data, calls, repos, statuses, clean, before, snapshot(), leftovers


class ScenarioTests(unittest.TestCase):
    """R1: six isolated repositories, real JSON statuses, caller unchanged."""
    def test_scenarios_and_observations(self):
        data, calls, repos, statuses, clean, before, after, leftovers = observed()
        self.assertEqual([s["name"] for s in data["scenarios"]], list(NAMES))
        self.assertEqual(len(repos), 6)
        self.assertEqual(len(set(repos)), 6)
        self.assertTrue(all(not p.exists() for p in repos))
        self.assertEqual(before, after)
        self.assertEqual(leftovers, [])
        self.assertTrue(clean)
        self.assertEqual(set(clean), {""})
        self.assertTrue(statuses)
        self.assertTrue(any(r["status"] == "STALE" for d in statuses for r in d["requirements"]))
        for repo in repos:
            self.assertTrue(any(cwd == str(repo) and "assure" in argv and "--json" in argv
                                for cwd, argv in calls))


class OracleTests(unittest.TestCase):
    """R2: true reads are independent of Inputs and missing reads fail closed."""
    def test_oracle_intersections_and_no_mechanism_imports(self):
        for scenario in measure.SCENARIOS:
            for step in scenario.steps:
                if step.affected is None:
                    expected = {r.id for r in scenario.reqs if set(r.reads) & set(step.change)}
                    self.assertEqual(measure.affected(scenario.reqs, step), expected)
        req = measure.Req("MEAS-R9", (), ("declared.txt",), ("actual.txt",))
        step = replace(measure.SCENARIOS[0].steps[0], change={"actual.txt": "ok"}, affected=None)
        self.assertEqual(measure.affected((req,), step), {"MEAS-R9"})
        tree = ast.parse((SCRIPTS / "assurance_measure.py").read_text())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
        self.assertFalse(imports & {"assurance", "lifecycle", "ledger"})

    def test_check_reads_every_true_input_and_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for scenario in measure.SCENARIOS:
                for req in scenario.reqs:
                    for name in req.reads:
                        path = base / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text("ok")
                    script = base / "check.py"
                    script.write_text(measure.check_script(req))
                    def check():
                        return subprocess.run([sys.executable, str(script)], cwd=base, capture_output=True).returncode
                    self.assertEqual(check(), 0)
                    for name in req.reads:
                        path = base / name
                        path.unlink()
                        self.assertNotEqual(check(), 0, name)
                        path.write_text("broken")
                        self.assertNotEqual(check(), 0, name)
                        path.write_text("ok")


class MetricTests(unittest.TestCase):
    """R3: metrics checked against hand-calculated constants for every step."""
    def test_exact_metrics(self):
        data = observed()[0]
        for scenario in data["scenarios"]:
            self.assertEqual(len(scenario["steps"]), len(EXPECTED[scenario["name"]]))
            for step, expected in zip(scenario["steps"], EXPECTED[scenario["name"]]):
                self.assertEqual(set(step), {"title", "affected", "flagged", *METRICS})
                self.assertEqual(tuple(step[k] for k in METRICS), expected)
                self.assertEqual(step["caught"], len(set(step["affected"]) & set(step["flagged"])))
                self.assertEqual(step["affected"], sorted(set(step["affected"])))
        self.assertEqual(data["totals"], TOTALS)


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)

    def run_measure(self, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        code = measure.run(base=self.base, out=out, err=err, **kwargs)
        return code, out.getvalue(), err.getvalue()


class RerunTests(Base):
    """R4: actual reruns and fail-closed comparison of resulting statuses."""
    def test_reruns_and_final_statuses(self):
        data, calls, _, statuses, *_ = observed()
        self.assertEqual(data["failures"], [])
        self.assertTrue(any(r["status"] == "FAILED" for d in statuses for r in d["requirements"]))
        self.assertGreaterEqual(sum("--run" in argv for _, argv in calls), 14)
        regression = next(s for s in measure.SCENARIOS if s.name == "regression")
        wrong = replace(regression.steps[0], after={"MEAS-R1": "VERIFIED"})
        with mock.patch.object(measure, "SCENARIOS", (replace(regression, steps=(wrong,)),)):
            code, out, err = self.run_measure(only=("regression",))
        self.assertEqual(code, 1, out + err)
        self.assertIn("regression/", out + err)
        self.assertIn("expected VERIFIED observed FAILED", out + err)


class ExpectationTests(Base):
    """R5: expected counts detect real mechanism regressions through copied scripts."""
    def test_known_profile(self):
        self.assertEqual(observed()[0]["failures"], [])
        code, out, err = self.run_measure(only=("feature",))
        self.assertEqual(code, 0, err)
        self.assertNotIn("FAIL", out)

    def test_missed_and_false_stale_fail(self):
        for hook, metric in ((hook_status("VERIFIED", True), "missed"), (hook_status("STALE"), "false_stale")):
            code, out, err = self.run_measure(only=("feature",), hook=hook)
            self.assertEqual(code, 1, out + err)
            self.assertIn("feature/", out + err)
            self.assertIn(metric + " expected", out + err)
            self.assertNotIn(LIMIT, out)

    def test_lost_handoff_evidence_is_reported_as_a_failure(self):
        code, out, err = self.run_measure(only=("handoff",), hook=hook_status("UNVERIFIED", no_evidence=True))
        self.assertEqual(code, 1, out + err)
        self.assertIn("handoff/input changed after handoff: false_stale expected 0 observed 1", out)
        self.assertIn("status expected VERIFIED observed UNVERIFIED", out)
        self.assertNotIn(LIMIT, out)


class ReportTests(Base):
    """R6: deterministic text and CLI JSON, totals and contributions."""
    def test_report_and_determinism(self):
        data = observed()[0]
        self.assertEqual(set(data), {"schema_version", "scenarios", "totals", "contribution", "failures"})
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["contribution"], CONTRIBUTION)
        outputs = []
        for _ in range(2):
            out = io.StringIO()
            measure.report(data, out)
            outputs.append(out.getvalue())
        self.assertEqual(*outputs)
        text = outputs[0]
        self.assertEqual(text.splitlines()[-1], LIMIT)

        def assert_row(label, expected):
            line = next(line for line in text.splitlines() if line.startswith(label))
            self.assertEqual([int(value) for value in line[len(label):].split()], expected, label)

        for scenario in data["scenarios"]:
            expected_rows = []
            for step, counts in zip(scenario["steps"], EXPECTED[scenario["name"]]):
                caught, false_stale, missed, changed_missed, reruns, baseline = counts
                expected = [caught + missed, reruns, *counts]
                expected_rows.append(expected)
                assert_row(scenario["name"] + ": " + step["title"], expected)
            assert_row(scenario["name"] + " total", [sum(column) for column in zip(*expected_rows)])
        assert_row("grand total", [8, 8, *TOTALS.values()])
        self.assertIn("contribution:", text)
        for key, value in CONTRIBUTION.items():
            self.assertIn(f"  {key}: {value}\n", text)
        self.assertNotRegex(text, r"/[a-z]|\d{4}-\d\d-\d\d|\b[0-9a-f]{40}\b")

    def test_cli_json_two_runs_byte_identical(self):
        env = {**os.environ, "TMPDIR": str(self.base), "PYTHONDONTWRITEBYTECODE": "1"}
        results = [subprocess.run([sys.executable, str(SCRIPTS / "assurance_measure.py"), "--json"],
                                 cwd=ROOT, env=env, capture_output=True, text=True, timeout=300) for _ in range(2)]
        for result in results:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout), observed()[0])
        self.assertEqual(results[0].stdout, results[1].stdout)


class ReportOnlyTests(unittest.TestCase):
    """R7: measurement leaves the invoking mechanism and regression tests untouched."""
    def test_protected_files_unchanged(self):
        _, _, _, _, _, before, after, _ = observed()
        for name in ("assurance.py", "ledger.py", "lifecycle.py", "okf.py",
                     "tests/test_assurance.py", "tests/test_assurance_attested.py", "assurance_demo.py"):
            key = ('.ai/scripts/' + name).encode()
            self.assertIn(key, before, name)
            self.assertEqual(before[key], after[key], name)


class CleanupTests(Base):
    """R8: cleanup on success, command failure, hook exception and SIGTERM; bad base exits 2."""
    def test_cleanup(self):
        for hook, expected in ((None, 0), (hook_status("VERIFIED", True), 1)):
            code, out, err = self.run_measure(only=("feature",), hook=hook)
            self.assertEqual(code, expected, out + err)
            self.assertEqual(list(self.base.iterdir()), [])
        def boom(scripts):
            raise RuntimeError("hook failed")
        with self.assertRaisesRegex(RuntimeError, "hook failed"):
            self.run_measure(hook=boom)
        self.assertEqual(list(self.base.iterdir()), [])
        def invalid(scripts):
            (scripts / "lifecycle.py").write_text("raise SystemExit(17)\n")
        code, out, err = self.run_measure(only=("feature",), hook=invalid)
        self.assertEqual(code, 1)
        self.assertIn("assurance_measure:", err)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_bad_base(self):
        with mock.patch.object(measure, "_base", side_effect=assurance_demo.DemoFailure("no disk-backed temporary directory")):
            err = io.StringIO()
            self.assertEqual(measure.run(err=err), 2)
            self.assertEqual(len(err.getvalue().splitlines()), 1)
        err = io.StringIO()
        self.assertEqual(measure.run(base=Path("/dev/shm"), err=err), 2)
        self.assertEqual(len(err.getvalue().splitlines()), 1)

    def test_sigterm_removes_repository(self):
        marker = self.base / "ready"
        probe = ("import sys,time\n"
                 f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
                 "import assurance_measure as m\nfrom pathlib import Path\n"
                 "original = m.measure\n"
                 "def hook(scripts):\n"
                 f"    Path({str(marker)!r}).write_text(str(scripts))\n"
                 "    time.sleep(60)\n"
                 "def wrapped(**kw):\n    kw[\"hook\"] = hook\n    return original(**kw)\n"
                 "m.measure = wrapped\nsys.exit(m.main([]))\n")
        env = {**os.environ, "TMPDIR": str(self.base), "PYTHONDONTWRITEBYTECODE": "1"}
        proc = subprocess.Popen([sys.executable, "-c", probe], cwd=ROOT, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 30
            while not marker.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            if not marker.exists():
                out, err = proc.communicate(timeout=10)
                self.fail("never reached prepared repository: " + out + err)
            proc.send_signal(signal.SIGTERM)
            out, err = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 143, out + err)
            marker.unlink()
            self.assertEqual(list(self.base.iterdir()), [])
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.communicate()


if __name__ == "__main__":
    unittest.main()
