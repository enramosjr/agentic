"""Contracts for immutable managed validation and observed source-work tracking."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest import mock

from test_autonomy import AutonomyTestCase, HAS_GIT, SCRIPTS
import autonomy_validation


@unittest.skipUnless(HAS_GIT, "git not installed")
class ValidationTests(AutonomyTestCase):
    def setUp(self):
        super().setUp()
        self.init_git()
        self.commit_all("initial")
        self.runtime = self.repo / ".git" / "validation"
        self.runtime.mkdir()

    def command(self, code="print('contract asserted')"):
        return {"label": "contract-" + hashlib.sha256(code.encode()).hexdigest()[:8], "argv": [sys.executable, "-c", code],
                "timeout_seconds": .5, "coverage": ["A"]}

    def test_plan_rejects_missing_coverage_duplicates_and_unbounded_time(self):
        for value in ([], {}, {"requirements": ["A"], "commands": []},
                      {"requirements": ["A", "B"], "commands": [self.command()]},
                      {"requirements": ["A"], "commands": [self.command(), self.command()]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                autonomy_validation.plan(value)
        for seconds in (0, -1, float("nan"), float("inf"), True):
            command = {**self.command(), "timeout_seconds": seconds}
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                autonomy_validation.plan({"requirements": ["A"], "commands": [command]})

    def test_validation_kind_rejects_unknown_or_nonstring_classifications(self):
        for kind in (None, "", "model", "unknown", True, [], {}):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "validation_kind"):
                autonomy_validation.plan({"requirements": ["A"], "commands": [self.command()], "validation_kind": kind})

    def test_repair_plan_requires_review_and_serializes_gate_after_regression(self):
        check = {**self.command(), "label": "regression"}
        gate = {**self.command("print('full gate')"), "label": "gate", "after": ["regression"]}
        valid = {"requirements": ["A"], "commands": [check, gate], "max_parallel": 2,
                 "repair": {"failed_result": "/retained/result.json", "regression": "regression", "review": "source review"}}
        self.assertEqual(autonomy_validation.plan(valid), valid)
        invalid = [{**valid, "repair": None}, {**valid, "repair": {**valid["repair"], "review": ""}},
                   {**valid, "repair": {**valid["repair"], "regression": "gate"}},
                   {**valid, "commands": [check, {**gate, "after": []}]},
                   {**valid, "validation_kind": "model-backed"}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                autonomy_validation.plan(value)

    def test_repair_binds_untampered_failure_and_requires_source_change(self):
        request = self.request(self.runtime / "failed", [self.command("raise SystemExit(7)")])
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        fingerprint = autonomy_validation.digest(result)
        job = {"candidate": self.git_head(), "repair": {"failed_result": str(result)}}
        with self.assertRaisesRegex(ValueError, "changed source"):
            autonomy_validation.repair_candidate(job, result, fingerprint, self.repo)
        (self.repo / "notes.md").write_text("records-only")
        self.commit_all("records")
        job["candidate"] = self.git_head()
        with self.assertRaisesRegex(ValueError, "changed source"):
            autonomy_validation.repair_candidate(job, result, fingerprint, self.repo)
        (self.repo / "feature.py").write_text("fixed = True")
        self.commit_all("source repair")
        job["candidate"] = self.git_head()
        self.assertTrue(autonomy_validation.repair_candidate(job, result, fingerprint, self.repo))
        with self.assertRaisesRegex(ValueError, "preceding"):
            autonomy_validation.repair_candidate(job, None, None, self.repo)
        result.write_text(result.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "unchanged immediately preceding"):
            autonomy_validation.repair_candidate(job, result, fingerprint, self.repo)

    def test_repair_refuses_pass_timeout_and_model_backed_results(self):
        request = self.request(self.runtime / "failed", [self.command("raise SystemExit(7)")])
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        original = json.loads(result.read_text())
        job = {"candidate": self.git_head(), "repair": {"failed_result": str(result)}}
        for changes in ({"state": "PASS"}, {"state": "TIMED_OUT"}, {"validation_kind": "model-backed"}):
            result.write_text(json.dumps({**original, **changes}))
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "failed deterministic"):
                autonomy_validation.repair_candidate(job, result, autonomy_validation.digest(result), self.repo)

    def test_repair_regression_executes_fresh_even_with_matching_pass_receipt(self):
        counter = self.runtime / "proof-runs"
        check = {**self.command(f"from pathlib import Path; p=Path({str(counter)!r}); p.write_text(p.read_text()+'run' if p.exists() else 'run')"), "label": "regression"}
        gate = {**self.command("raise SystemExit(7)"), "after": ["regression"]}
        request = self.request(self.runtime / "first", [check, gate])
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        repair = {"failed_result": str(result), "regression": "regression", "review": "source review"}
        request = self.request(self.runtime / "second", [check, gate], result, repair=repair)
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        self.assertEqual(counter.read_text(), "runrun")
        self.assertNotIn("reused_from", json.loads(result.read_text())["commands"][0])

    def test_default_and_explicit_kinds_survive_actual_success_and_failure(self):
        for kind in (None, "deterministic", "model-backed"):
            for exit_code in (0, 7):
                with self.subTest(kind=kind, exit_code=exit_code):
                    options = {} if kind is None else {"validation_kind": kind}
                    command = self.command(f"print('actual assertion'); raise SystemExit({exit_code})")
                    request = self.request(self.runtime / f"{kind}-{exit_code}", [command], **options)
                    reports = []
                    result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02,
                                                    lambda *args: reports.append(args), lambda: None)
                    value = json.loads(result.read_text())
                    self.assertEqual(value["validation_kind"], kind or "deterministic")
                    self.assertEqual(value["state"], "FAIL" if exit_code else "PASS")
                    self.assertEqual(value["commands"][0]["exit_code"], exit_code)
                    self.assertIn(f"({kind or 'deterministic'})", reports[-1][1])

    def test_kind_change_reruns_pass_while_explicit_default_reuses_default(self):
        counter = self.runtime / "kind-counter"
        command = self.command(f"from pathlib import Path; p=Path({str(counter)!r}); p.write_text(p.read_text()+'run' if p.exists() else 'run')")
        result = None
        for number, kind in enumerate((None, "deterministic", "model-backed", "deterministic")):
            options = {} if kind is None else {"validation_kind": kind}
            request = self.request(self.runtime / f"kind-{number}", [command], result, **options)
            result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
            value = json.loads(result.read_text())
            self.assertEqual(value["state"], "PASS")
            self.assertEqual("reused_from" in value["commands"][0], number == 1)
        self.assertEqual(counter.read_text(), "runrunrun")

    def test_worker_tracking_observes_source_changes_without_resetting_baseline(self):
        worker = self.repo.parent / (self.repo.name + "-worker")
        self.git("worktree", "add", "-b", "worker", str(worker))
        self.addCleanup(lambda: self.git("worktree", "remove", "--force", str(worker)))
        registry = self.runtime / "workers.json"
        autonomy_validation.register(registry, self.repo, worker)
        self.assertFalse(autonomy_validation.source_work(registry))
        (worker / "notes.md").write_text("longer planning")
        self.assertFalse(autonomy_validation.source_work(registry))
        (worker / "feature.py").write_text("def implemented(): return 42\n")
        autonomy_validation.register(registry, self.repo, worker)
        self.assertTrue(autonomy_validation.source_work(registry))

    def test_unrelated_repository_cannot_satisfy_source_work_guard(self):
        other = self.runtime / "other"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        with self.assertRaises(ValueError):
            autonomy_validation.register(self.runtime / "workers.json", self.repo, other)

    def test_parallel_registrations_retain_every_owned_worktree(self):
        registry = self.runtime / "workers.json"
        workers = [self.repo.parent / (self.repo.name + f"-parallel-{number}") for number in range(3)]
        for number, worker in enumerate(workers):
            self.git("worktree", "add", "-b", f"parallel-{number}", str(worker))
            self.addCleanup(lambda worker=worker: self.git("worktree", "remove", "--force", str(worker)))
        processes = [subprocess.Popen([sys.executable, str(SCRIPTS / "autonomy_validation.py"),
                                       "track-worker", "--worktree", str(worker)], cwd=self.repo,
                                      env={**os.environ, "OKF_WORK_REGISTRY": str(registry)},
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for worker in workers]
        for process in processes:
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(set(json.loads(registry.read_text())), {str(worker) for worker in workers})

    def test_each_completed_command_is_durable_before_next_command(self):
        result = self.runtime / "result.json"
        second = self.command("import json,pathlib; r=json.loads(pathlib.Path(" + repr(str(result)) + ").read_text()); assert r['commands'][0]['state']=='PASS'; print('second verified first receipt')")
        request = self.runtime / "request.json"
        request.write_text(json.dumps({"candidate": self.git_head(), "requirements": ["A"], "commands": [self.command(), second]}))
        path = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .05, lambda *args: None, lambda: None)
        value = json.loads(path.read_text())
        self.assertEqual(value["state"], "PASS")
        self.assertEqual([entry["state"] for entry in value["commands"]], ["PASS", "PASS"])
        self.assertIn("second verified", Path(value["commands"][1]["log"]).read_text())
        with self.assertRaises(ValueError):
            autonomy_validation.run(request, self.repo, time.monotonic() + 5, .05, lambda *args: None, lambda: None)

    def git_head(self):
        return autonomy_validation.git(self.repo, "rev-parse", "HEAD")

    @unittest.skipUnless(Path("/dev/full").exists(), "requires a failing evidence device")
    def test_successful_command_cannot_pass_when_evidence_storage_is_full(self):
        request = self.runtime / "request.json"
        request.write_text(json.dumps({"candidate": self.git_head(), "requirements": ["A"], "commands": [self.command()]}))
        original = Path.open
        def failing_log(path, *args, **kwargs):
            if path.name == "command-1.log":
                return original(Path("/dev/full"), "w")
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, "open", failing_log):
            result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .05, lambda *args: None, lambda: None)
        value = json.loads(result.read_text())
        self.assertNotEqual(value["state"], "PASS")
        self.assertNotEqual(value["commands"][0]["state"], "PASS")

    def test_submit_cli_requires_clean_candidate_and_is_single_use(self):
        manifest = self.runtime / "plan.json"
        manifest.write_text(json.dumps({"requirements": ["A"], "commands": [self.command()]}))
        request = self.runtime / "request.json"
        args = [sys.executable, str(SCRIPTS / "autonomy_validation.py"), "submit", "--plan", str(manifest)]
        environment = {**os.environ, "OKF_VALIDATION_REQUEST": str(request)}
        (self.repo / "unfinished.py").write_text("print('unfinished')")
        dirty = subprocess.run(args, cwd=self.repo, env=environment, capture_output=True, text=True)
        self.assertEqual(dirty.returncode, 1, dirty.stderr)
        self.assertFalse(request.exists())
        self.commit_all("preserve implementation")
        submitted = subprocess.run(args, cwd=self.repo, env=environment, capture_output=True, text=True)
        self.assertEqual(submitted.returncode, 0, submitted.stderr)
        self.assertEqual(json.loads(request.read_text())["candidate"], self.git_head())
        duplicate = subprocess.run(args, cwd=self.repo, env=environment, capture_output=True, text=True)
        self.assertEqual(duplicate.returncode, 1)

    def request(self, directory, commands, resume=None, **options):
        directory.mkdir(exist_ok=True)
        value = {"candidate": self.git_head(), "requirements": ["A"], "commands": commands, **options}
        if resume:
            value["resume_from"] = str(resume)
        request = directory / "request.json"
        request.write_text(json.dumps(value))
        return request

    def test_incremental_validation_retains_and_resumes_passes_without_repeating_them(self):
        counter = self.runtime / "counter"
        first = self.command("from pathlib import Path; p=Path(" + repr(str(counter)) + "); p.write_text(p.read_text()+'run' if p.exists() else 'run'); print('first asserted')")
        second = self.command("import time; time.sleep(.4); print('second asserted')")
        second["timeout_seconds"] = 2
        commands = [first, second]
        request = self.request(self.runtime / "first", commands)
        result = autonomy_validation.run(request, self.repo, time.monotonic() + .25, .02, lambda *args: None, lambda: None)
        original = json.loads(result.read_text())
        self.assertEqual(original["state"], "BUDGET_EXHAUSTED")
        self.assertEqual(original["commands"][0]["state"], "PASS")
        self.assertEqual(counter.read_text(), "run")
        resumed = self.request(self.runtime / "resumed", commands, result)
        finished = autonomy_validation.run(resumed, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        final = json.loads(finished.read_text())
        self.assertEqual(final["state"], "PASS")
        self.assertEqual(counter.read_text(), "run", "completed validation command was rerun")
        self.assertEqual(final["commands"][0]["reused_from"], str(result))
        self.assertEqual(final["commands"][1]["state"], "PASS")

    def test_resume_reruns_changed_candidate_and_refuses_tampered_receipt(self):
        request = self.request(self.runtime / "first", [self.command()])
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        log = Path(json.loads(result.read_text())["commands"][0]["log"])
        original = log.read_bytes()
        log.write_text("fabricated PASS")
        resumed = self.request(self.runtime / "resumed", [self.command()], result)
        with self.assertRaisesRegex(ValueError, "log changed"):
            autonomy_validation.run(resumed, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        log.write_bytes(original)
        (self.repo / "changed.py").write_text("print('changed input')")
        self.commit_all("changed candidate")
        resumed = self.request(self.runtime / "changed", [self.command()], result)
        final = autonomy_validation.run(resumed, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        self.assertEqual(json.loads(final.read_text())["state"], "PASS")
        self.assertNotIn("reused_from", json.loads(final.read_text())["commands"][0])

    def test_input_declarations_reject_ambiguous_paths_and_model_backed_jobs(self):
        for paths in (None, [], "src", [True], [""], ["../src"], ["/src"], ["src/"],
                      ["src/../tests"], ["src\\test"], ["src", "src"]):
            with self.subTest(paths=paths), self.assertRaisesRegex(ValueError, "inputs"):
                autonomy_validation.plan({"requirements": ["A"], "commands": [{**self.command(), "inputs": paths}]})
        with self.assertRaisesRegex(ValueError, "model-backed"):
            autonomy_validation.plan({"validation_kind": "model-backed", "requirements": ["A"],
                                      "commands": [{**self.command(), "inputs": ["src"]}]})

    def test_cli_resume_reuses_product_check_after_records_commit_and_reruns_changed_inputs(self):
        source = self.repo / "src"
        source.mkdir()
        (source / "value.txt").write_text("42")
        counter = self.runtime / "product-runs"
        harness = self.repo / "check.py"
        harness.write_text("from pathlib import Path\n"
                           "assert Path('src/value.txt').read_text() == '42'\n"
                           f"p = Path({str(counter)!r})\n"
                           "p.write_text(p.read_text() + 'run' if p.exists() else 'run')\n")
        self.commit_all("product and acceptance harness")
        command = {**self.command(), "argv": [sys.executable, "check.py"], "inputs": ["src", "check.py"]}
        request = self.request(self.runtime / "original", [command])
        original_head = self.git_head()
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        self.assertEqual(json.loads(result.read_text())["state"], "PASS")
        (self.repo / "knowledge" / "log.md").write_text("## 2026-10-17\n\nRecords updated.\n")
        self.commit_all("records only")
        destination = self.runtime / "cli-resume" / "request.json"
        destination.parent.mkdir()
        submitted = subprocess.run([sys.executable, str(SCRIPTS / "autonomy_validation.py"), "submit", "--resume", str(result)],
                                   cwd=self.repo, env={**os.environ, "OKF_VALIDATION_REQUEST": str(destination)}, capture_output=True, text=True)
        self.assertEqual(submitted.returncode, 0, submitted.stderr)
        resumed = autonomy_validation.run(destination, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        receipt = json.loads(resumed.read_text())["commands"][0]
        self.assertEqual(receipt["tested_candidate"], original_head)
        self.assertEqual(receipt["reused_from"], str(result))
        self.assertEqual(counter.read_text(), "run")
        # An added fixture invalidates directory inputs, then a source defect
        # must execute the actual assertion and fail rather than reuse PASS.
        (source / "fixture.txt").write_text("new fixture")
        self.commit_all("new fixture")
        request = self.request(self.runtime / "fixture", [command], resumed)
        changed = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        self.assertEqual(json.loads(changed.read_text())["state"], "PASS")
        self.assertNotIn("reused_from", json.loads(changed.read_text())["commands"][0])
        self.assertEqual(counter.read_text(), "runrun")
        (source / "value.txt").write_text("broken")
        self.commit_all("source regression")
        request = self.request(self.runtime / "regression", [command], changed)
        failed = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        self.assertEqual(json.loads(failed.read_text())["state"], "FAIL")
        self.assertNotEqual(json.loads(failed.read_text())["commands"][0]["exit_code"], 0)

    def test_missing_link_and_submodule_inputs_fail_closed(self):
        for path in ("missing.py", "AGENTS.md"):
            if path == "AGENTS.md":
                (self.repo / path).unlink()
                (self.repo / path).symlink_to("knowledge/log.md")
                self.commit_all("linked input")
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "no tracked files|symlink or submodule"):
                autonomy_validation.source_inputs({"inputs": [path]}, self.repo, self.git_head())
        self.git("update-index", "--add", "--cacheinfo", f"160000,{self.git_head()},vendor")
        self.git("commit", "-m", "submodule input")
        with self.assertRaisesRegex(ValueError, "submodule"):
            autonomy_validation.source_inputs({"inputs": ["vendor"]}, self.repo, self.git_head())

    def test_prerequisite_source_or_commit_binding_invalidates_consumer_across_commits(self):
        (self.repo / "prepare.txt").write_text("v1")
        self.commit_all("prepare input")
        for scoped in (False, True):
            first = {**self.command("print('prepare')"), "label": "prepare"}
            if scoped:
                first["inputs"] = ["prepare.txt"]
            second = {**self.command("print('assert consumer')"), "inputs": ["AGENTS.md"], "after": ["prepare"]}
            request = self.request(self.runtime / f"deps-{scoped}", [first, second])
            result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
            (self.repo / "prepare.txt").write_text(f"changed-{scoped}")
            self.commit_all("change prerequisite")
            request = self.request(self.runtime / f"deps-changed-{scoped}", [first, second], result)
            changed = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
            value = json.loads(changed.read_text())
            self.assertEqual(value["state"], "PASS")
            self.assertTrue(all("reused_from" not in entry for entry in value["commands"]))

    def test_invalidated_job_cannot_supply_pass_receipts_after_tree_is_restored(self):
        command = self.command("from pathlib import Path; Path('drift.py').write_text('changed'); print('exit zero with changed inputs')")
        request = self.request(self.runtime / "first", [command])
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        self.assertEqual(json.loads(result.read_text())["state"], "INVALIDATED")
        self.assertEqual(json.loads(result.read_text())["commands"][0]["state"], "PASS")
        (self.repo / "drift.py").unlink()
        resumed = self.request(self.runtime / "resumed", [command], result)
        with self.assertRaisesRegex(ValueError, "inputs were invalidated"):
            autonomy_validation.run(resumed, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)

    def test_changed_environment_reruns_instead_of_reusing_pass(self):
        counter = self.runtime / "counter"
        command = self.command("from pathlib import Path; p=Path(" + repr(str(counter)) + "); p.write_text(p.read_text()+'run' if p.exists() else 'run')")
        request = self.request(self.runtime / "first", [command])
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        resumed = self.request(self.runtime / "resumed", [command], result)
        reports = []
        with mock.patch.dict(os.environ, {"VALIDATION_TEST_ENV_REVISION": "changed"}):
            final = autonomy_validation.run(resumed, self.repo, time.monotonic() + 5, .02,
                                            lambda *args: reports.append(args), lambda: None)
        self.assertEqual(json.loads(final.read_text())["state"], "PASS")
        self.assertEqual(counter.read_text(), "runrun")
        self.assertNotIn("reused_from", json.loads(final.read_text())["commands"][0])
        self.assertTrue(any("not reused: environment" in message for _, message in reports))

    def test_fresh_session_reuses_passes_and_strips_inherited_bookkeeping(self):
        counter = self.runtime / "session-counter"
        first = self.command("import os; from pathlib import Path; "
                             "assert 'CODEX_THREAD_ID' not in os.environ; "
                             "assert 'OKF_HANDOFF_REQUEST' not in os.environ; "
                             f"p=Path({str(counter)!r}); p.write_text(p.read_text()+'run' if p.exists() else 'run')")
        second = {**self.command("print('dependent assertion')"), "after": [first["label"]]}
        result = None
        runner = (f"import sys,time; sys.path.insert(0, {str(SCRIPTS)!r}); "
                  "from pathlib import Path; import autonomy_validation as v; "
                  "v.run(Path(sys.argv[1]), Path(sys.argv[2]), time.monotonic()+5, .02, "
                  "lambda *args: None, lambda: None)")
        for number in range(2):
            request = self.request(self.runtime / f"session-{number}", [first, second], result)
            executed = subprocess.run([sys.executable, "-c", runner, str(request), str(self.repo)],
                                      env={**os.environ, "CODEX_THREAD_ID": f"thread-{number}",
                                           "OKF_HANDOFF_REQUEST": f"handoff-{number}",
                                           "SHLVL": str(number), "_": f"launcher-{number}"},
                                      capture_output=True, text=True, timeout=10)
            self.assertEqual(executed.returncode, 0, executed.stderr)
            result = request.with_name("result.json")
            value = json.loads(result.read_text())
            self.assertEqual(value["state"], "PASS")
            self.assertTrue(all(("reused_from" in entry) == bool(number) for entry in value["commands"]))
        self.assertEqual(counter.read_text(), "run")

    def test_explicit_bookkeeping_env_is_an_input_and_model_backed_env_stays_exact(self):
        for kind in ("deterministic", "model-backed"):
            counter = self.runtime / f"{kind}-env-counter"
            command = self.command("import os; from pathlib import Path; "
                                   "assert os.environ['CODEX_THREAD_ID'] == 'required'; "
                                   f"p=Path({str(counter)!r}); p.write_text(p.read_text()+'run' if p.exists() else 'run')")
            if kind == "deterministic":
                command["env"] = {"CODEX_THREAD_ID": "required"}
            result = None
            for number in range(2):
                if kind == "deterministic":
                    command = {**command, "env": {"CODEX_THREAD_ID": "required", "SHLVL": str(number)}}
                request = self.request(self.runtime / f"{kind}-{number}", [command], result, validation_kind=kind)
                with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": "required", "OKF_HANDOFF_REQUEST": str(number)}):
                    result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02,
                                                     lambda *args: None, lambda: None)
                value = json.loads(result.read_text())
                self.assertEqual(value["state"], "PASS")
                self.assertNotIn("reused_from", value["commands"][0])
            self.assertEqual(counter.read_text(), "runrun")

    def test_legacy_schema_mismatch_stops_before_repeating_completed_command(self):
        counter = self.runtime / "legacy-counter"
        command = self.command(f"from pathlib import Path; p=Path({str(counter)!r}); "
                               "p.write_text(p.read_text()+'run' if p.exists() else 'run')")
        request = self.request(self.runtime / "legacy", [command])
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        value = json.loads(result.read_text())
        # The pre-input-scope validator used candidate at the top level and
        # retained the entire effective environment, with no component hashes.
        inputs = {"candidate": self.git_head(), "command": command,
                  "environment": autonomy_validation.scratch.environment(self.repo),
                  "validation_kind": "deterministic"}
        entry = value["commands"][0]
        entry["input_fingerprint"] = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        del entry["input_components"]
        del entry["tested_candidate"]
        result.write_text(json.dumps(value))
        resumed = self.request(self.runtime / "legacy-resume", [command], result)
        with self.assertRaisesRegex(ValueError, "legacy PASS fingerprint cannot be matched"):
            autonomy_validation.run(resumed, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        self.assertEqual(counter.read_text(), "run")
        stopped = json.loads(resumed.with_name("result.json").read_text())
        self.assertEqual(stopped["state"], "CANCELLED")
        self.assertEqual(stopped["commands"], [])

    def test_resume_cli_builds_plan_from_retained_request_without_new_docs(self):
        request = self.request(self.runtime / "first", [self.command()])
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        destination = self.runtime / "next" / "request.json"
        destination.parent.mkdir()
        submitted = subprocess.run([sys.executable, str(SCRIPTS / "autonomy_validation.py"), "submit", "--resume", str(result)],
                                   cwd=self.repo, env={**os.environ, "OKF_VALIDATION_REQUEST": str(destination)}, capture_output=True, text=True)
        self.assertEqual(submitted.returncode, 0, submitted.stderr)
        self.assertEqual(json.loads(destination.read_text())["resume_from"], str(result))
        self.assertEqual(json.loads(destination.read_text())["candidate"], self.git_head())

    def test_no_command_starts_when_only_actual_closure_reserve_remains(self):
        request = self.request(self.runtime / "first", [self.command()])
        result = autonomy_validation.run(request, self.repo, time.monotonic() + .1, .2, lambda *args: None, lambda: None)
        self.assertEqual(json.loads(result.read_text())["state"], "BUDGET_DEFERRED")
        self.assertEqual(json.loads(result.read_text())["validation_kind"], "deterministic")
        self.assertEqual(json.loads(result.read_text())["commands"], [])

    def test_parallel_plan_rejects_invalid_limits_resources_labels_and_dependencies(self):
        first = {**self.command(), "label": "first"}
        second = {**self.command("print('other')"), "label": "second"}
        for maximum in (0, 9, 1.5, True, "2"):
            with self.subTest(maximum=maximum), self.assertRaises(ValueError):
                autonomy_validation.plan({"requirements": ["A"], "commands": [first], "max_parallel": maximum})
        for field in ("resources", "after"):
            for items in ("cargo", [""], [True], ["cargo", "cargo"], None):
                with self.subTest(field=field, items=items), self.assertRaises(ValueError):
                    autonomy_validation.plan({"requirements": ["A"], "commands": [{**first, field: items}]})
        for commands in ([first, {**second, "label": "first"}],
                         [{**first, "after": ["missing"]}],
                         [{**first, "after": ["first"]}],
                         [{**first, "after": ["second"]}, {**second, "after": ["first"]}]):
            with self.subTest(commands=commands), self.assertRaises(ValueError):
                autonomy_validation.plan({"requirements": ["A"], "commands": commands})

    def run_commands(self, commands, **options):
        request = self.request(self.runtime / "parallel", commands, **options)
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 10, .02,
                                         lambda *args: None, lambda: None, tick_seconds=.02)
        return json.loads(result.read_text())

    def test_disjoint_resources_really_overlap_and_callbacks_stay_on_owner_thread(self):
        import threading
        owner = threading.get_ident()
        callback_threads = []
        commands = []
        for name, peer in (("one", "two"), ("two", "one")):
            code = ("from pathlib import Path; import time; "
                    f"Path({str(self.runtime / name)!r}).touch(); peer=Path({str(self.runtime / peer)!r}); "
                    "deadline=time.monotonic()+2\n"
                    "while not peer.exists() and time.monotonic()<deadline: time.sleep(.01)\n"
                    "assert peer.exists(), 'peer never ran concurrently'\nprint('overlap asserted')")
            commands.append({**self.command(code), "resources": [name], "timeout_seconds": 3})
        request = self.request(self.runtime / "parallel", commands, max_parallel=2)
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 10, .02,
                    lambda *args: callback_threads.append(threading.get_ident()),
                    lambda: callback_threads.append(threading.get_ident()), tick_seconds=.02)
        self.assertEqual(json.loads(result.read_text())["state"], "PASS")
        self.assertEqual(set(callback_threads), {owner})

    def test_shared_or_undeclared_resources_serialize_even_with_parallel_capacity(self):
        lock = self.runtime / "exclusive"
        for resources in ((["cargo"], ["cargo"]), (None, ["other"]), (["other"], None)):
            commands = []
            for number, declared in enumerate(resources):
                code = ("from pathlib import Path; import time; "
                        f"p=Path({str(lock)!r}); p.mkdir(); print({number}); time.sleep(.1); p.rmdir()")
                command = {**self.command(code), "timeout_seconds": 2}
                if declared is not None:
                    command["resources"] = declared
                commands.append(command)
            directory = self.runtime / ("serialized-" + str(len(list(self.runtime.iterdir()))))
            request = self.request(directory, commands, max_parallel=2)
            result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
            self.assertEqual(json.loads(result.read_text())["state"], "PASS")

    def test_forward_dependency_waits_for_durable_preparation_pass(self):
        artifact = self.runtime / "prepared"
        prepare = {**self.command(f"from pathlib import Path; Path({str(artifact)!r}).write_text('verified package')"),
                   "label": "prepare", "resources": ["package"]}
        inspect = {**self.command(f"from pathlib import Path; assert Path({str(artifact)!r}).read_text()=='verified package'"),
                   "label": "inspect", "resources": ["consumer"], "after": ["prepare"]}
        result = self.run_commands([inspect, prepare], max_parallel=2)
        self.assertEqual(result["state"], "PASS")
        self.assertEqual([entry["label"] for entry in result["commands"]], ["prepare", "inspect"])

    def test_failure_cancels_and_reaps_running_peer_without_launching_dependents(self):
        pid = self.runtime / "peer-pid"
        marker = self.runtime / "must-not-finish"
        peer = {**self.command(f"from pathlib import Path; import os,time; Path({str(pid)!r}).write_text(str(os.getpid())); time.sleep(10); Path({str(marker)!r}).touch()"),
                "label": "peer", "resources": ["peer"], "timeout_seconds": 20}
        fail = {**self.command(f"from pathlib import Path; import time; p=Path({str(pid)!r})\nwhile not p.exists(): time.sleep(.01)\nraise SystemExit(7)"),
                "label": "fail", "resources": ["fail"], "timeout_seconds": 2}
        dependent = {**self.command(f"from pathlib import Path; Path({str(marker)!r}).touch()"),
                     "label": "dependent", "resources": [], "after": ["peer"]}
        started = time.monotonic()
        result = self.run_commands([peer, fail, dependent], max_parallel=2)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(result["state"], "FAIL")
        self.assertEqual({row["label"]: row["state"] for row in result["commands"]}, {"peer": "CANCELLED", "fail": "FAIL"})
        self.assertFalse(marker.exists())
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pid.read_text()), 0)

    def test_supervisor_loss_cancels_all_running_peers_and_retains_results(self):
        pids = [self.runtime / f"pid-{number}" for number in range(2)]
        commands = [{**self.command(f"from pathlib import Path; import os,time; Path({str(pid)!r}).write_text(str(os.getpid())); time.sleep(10)"),
                     "resources": [str(number)], "timeout_seconds": 20} for number, pid in enumerate(pids)]
        request = self.request(self.runtime / "parallel", commands, max_parallel=2, validation_kind="model-backed")
        def lost_supervisor():
            if all(pid.exists() for pid in pids):
                raise RuntimeError("supervisor lease expired")
        with self.assertRaisesRegex(RuntimeError, "supervisor lease expired"):
            autonomy_validation.run(request, self.repo, time.monotonic() + 10, .02,
                                    lambda *args: None, lost_supervisor, tick_seconds=.01)
        result = json.loads(request.with_name("result.json").read_text())
        self.assertEqual(result["state"], "CANCELLED")
        self.assertEqual(result["validation_kind"], "model-backed")
        self.assertEqual([entry["state"] for entry in result["commands"]], ["CANCELLED", "CANCELLED"])
        for pid in pids:
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pid.read_text()), 0)

    def test_command_timeout_cancels_peer_and_preserves_timeout_state(self):
        pid = self.runtime / "peer-pid"
        peer = {**self.command(f"from pathlib import Path; import os,time; Path({str(pid)!r}).write_text(str(os.getpid())); time.sleep(10)"),
                "label": "peer", "resources": ["peer"], "timeout_seconds": 20}
        timeout = {**self.command("import time; time.sleep(10)"), "label": "timeout",
                   "resources": ["timeout"], "timeout_seconds": .15}
        result = self.run_commands([peer, timeout], max_parallel=2)
        self.assertEqual(result["state"], "TIMED_OUT")
        self.assertEqual({row["label"]: row["state"] for row in result["commands"]}, {"peer": "CANCELLED", "timeout": "TIMED_OUT"})
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pid.read_text()), 0)

    def test_parallelism_never_exceeds_declared_limit(self):
        state = self.runtime / "concurrency.json"
        mutex = self.runtime / "counter.lock"
        state.write_text(json.dumps({"active": 0, "maximum": 0}))
        commands = []
        for number in range(4):
            code = ("from pathlib import Path; import fcntl,json,time\n"
                    f"p=Path({str(state)!r}); lock=open({str(mutex)!r},'a')\n"
                    "fcntl.flock(lock,fcntl.LOCK_EX); value=json.loads(p.read_text()); value['active']+=1; "
                    "value['maximum']=max(value['maximum'],value['active']); p.write_text(json.dumps(value)); "
                    "fcntl.flock(lock,fcntl.LOCK_UN); time.sleep(.1)\n"
                    "fcntl.flock(lock,fcntl.LOCK_EX); value=json.loads(p.read_text()); value['active']-=1; "
                    f"p.write_text(json.dumps(value)); print({number})")
            commands.append({**self.command(code), "resources": [], "timeout_seconds": 2})
        result = self.run_commands(commands, max_parallel=2)
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(json.loads(state.read_text()), {"active": 0, "maximum": 2})

    def test_parallel_input_drift_invalidates_and_cancels_peers(self):
        pid = self.runtime / "peer-pid"
        peer = {**self.command(f"from pathlib import Path; import os,time; Path({str(pid)!r}).write_text(str(os.getpid())); time.sleep(10)"),
                "resources": ["peer"], "timeout_seconds": 20}
        drift = {**self.command(f"from pathlib import Path; import time; p=Path({str(pid)!r})\nwhile not p.exists(): time.sleep(.01)\nPath('drift.py').write_text('changed')"),
                 "resources": ["drift"], "timeout_seconds": 2}
        result = self.run_commands([peer, drift], max_parallel=2)
        self.assertEqual(result["state"], "INVALIDATED")
        self.assertEqual(result["commands"][0]["state"], "CANCELLED")
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pid.read_text()), 0)

    def test_parallel_resume_reuses_pass_but_dependency_change_invalidates_consumer(self):
        counter = self.runtime / "counter"
        first = {**self.command(f"from pathlib import Path; p=Path({str(counter)!r}); p.write_text(p.read_text()+'run' if p.exists() else 'run')"),
                 "label": "prepare", "resources": ["package"]}
        second = {**self.command("print('consumer assertion')"), "resources": [], "after": ["prepare"]}
        request = self.request(self.runtime / "first", [first, second], max_parallel=2)
        result = autonomy_validation.run(request, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        resumed = self.request(self.runtime / "resumed", [first, second], result, max_parallel=2)
        final = autonomy_validation.run(resumed, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        value = json.loads(final.read_text())
        self.assertEqual(value["state"], "PASS")
        self.assertEqual(counter.read_text(), "run")
        self.assertTrue(all("reused_from" in entry for entry in value["commands"]))
        changed_first = {**first, "env": {"PREPARATION_REVISION": "2"}}
        resumed = self.request(self.runtime / "changed", [changed_first, second], result, max_parallel=2)
        changed = autonomy_validation.run(resumed, self.repo, time.monotonic() + 5, .02, lambda *args: None, lambda: None)
        self.assertEqual(json.loads(changed.read_text())["state"], "PASS")
        self.assertTrue(all("reused_from" not in entry for entry in json.loads(changed.read_text())["commands"]))
        self.assertEqual(counter.read_text(), "runrun")
