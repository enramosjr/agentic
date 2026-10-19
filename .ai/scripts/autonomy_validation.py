#!/usr/bin/env python3
"""Submit immutable validation plans and track owned source work for the driver."""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
import timed_check
import scratch


# These identify the supervising session, not the product under validation.
# Remove them from execution too: ignored inputs must not influence a check.
SESSION_ENV = frozenset({
    "CODEX_THREAD_ID", "SHLVL", "_", "OKF_VALIDATION_REQUEST",
    "OKF_WORK_REGISTRY", "OKF_CLOSURE_RELEASE", "OKF_DOCUMENT_AUDIT",
    "OKF_HANDOFF_REQUEST", "OKF_PROGRESS_REQUEST", "OKF_AUTONOMOUS_RECOVERY",
})


def command_environment(repo: Path, command: dict, validation_kind: str) -> dict:
    inherited = dict(os.environ)
    if validation_kind == "deterministic":
        inherited = {key: value for key, value in inherited.items() if key not in SESSION_ENV}
    # Explicit command inputs always count, even when they name session keys.
    return scratch.environment(repo, {**inherited, **command.get("env", {})})


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def plan(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("validation plan must be an object")
    if value.get("validation_kind", "deterministic") not in ("deterministic", "model-backed"):
        raise ValueError("validation_kind must be deterministic or model-backed")
    requirements, commands = value.get("requirements"), value.get("commands")
    if not isinstance(requirements, list) or not requirements or not all(isinstance(x, str) and x for x in requirements):
        raise ValueError("plan needs nonempty requirements")
    if not isinstance(commands, list) or not commands:
        raise ValueError("plan needs commands")
    if type(value.get("max_parallel", 1)) is not int or not 1 <= value.get("max_parallel", 1) <= 8:
        raise ValueError("max_parallel must be an integer between 1 and 8")
    covered, seen, labels = set(), set(), set()
    for command in commands:
        if not isinstance(command, dict):
            raise ValueError("each command must be an object")
        argv, timeout, coverage = command.get("argv"), command.get("timeout_seconds"), command.get("coverage")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            raise ValueError("command argv must be a nonempty string array")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("command timeout_seconds must be positive and finite")
        if not isinstance(coverage, list) or not coverage or not all(x in requirements for x in coverage):
            raise ValueError("command coverage must name declared requirements")
        if tuple(argv) in seen:
            raise ValueError("duplicate validation command; deduplicate the gate")
        if not isinstance(command.get("label"), str) or not command["label"]:
            raise ValueError("command needs an administrative label")
        if command["label"] in labels:
            raise ValueError("command labels must be unique")
        labels.add(command["label"])
        for field in ("resources", "after"):
            items = command.get(field, [])
            if not isinstance(items, list) or not all(isinstance(x, str) and x for x in items) or len(items) != len(set(items)):
                raise ValueError(f"command {field} must be an array of unique nonempty strings")
        if not isinstance(command.get("env", {}), dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in command.get("env", {}).items()):
            raise ValueError("command env must map strings to strings")
        if "inputs" in command:
            paths = command["inputs"]
            if (not isinstance(paths, list) or not paths or
                    not all(isinstance(path, str) and path and "\\" not in path and
                            all(part not in ("", ".", "..") for part in path.split("/")) for path in paths) or
                    len(paths) != len(set(paths))):
                raise ValueError("command inputs must be unique literal repository-relative paths")
            if value.get("validation_kind", "deterministic") != "deterministic":
                raise ValueError("model-backed validation cannot declare commit-independent inputs")
        seen.add(tuple(argv))
        covered.update(coverage)
    if covered != set(requirements):
        raise ValueError("every requirement must have command coverage")
    dependencies = {command["label"]: set(command.get("after", [])) for command in commands}
    if any(not parents <= labels for parents in dependencies.values()):
        raise ValueError("command after must name declared labels")
    resolved = set()
    while len(resolved) < len(labels):
        ready = {label for label, parents in dependencies.items() if parents <= resolved} - resolved
        if not ready:
            raise ValueError("command after dependencies contain a cycle")
        resolved.update(ready)
    if "repair" in value:
        repair = value["repair"]
        if (not isinstance(repair, dict) or any(not isinstance(repair.get(key), str) or not repair[key].strip()
                for key in ("failed_result", "regression", "review"))):
            raise ValueError("repair needs failed_result, regression command label and independent review reference")
        if value.get("validation_kind", "deterministic") != "deterministic":
            raise ValueError("repair stall exception applies only to deterministic validation")
        regression = repair["regression"]
        if commands[0]["label"] != regression or commands[0].get("after"):
            raise ValueError("repair regression must be the first command, without prerequisites")
        if any(regression not in command.get("after", []) for command in commands[1:]):
            raise ValueError("every full-gate command must run after the repair regression")
    return value


def repair_candidate(job: dict, previous: Path | None, previous_digest: str | None, repo: Path) -> bool:
    """A source repair can earn one handoff's exemption, never reset prior stalls."""
    if not job.get("repair"):
        return False
    if (previous is None or Path(job["repair"]["failed_result"]).resolve() != previous.resolve()
            or digest(previous) != previous_digest):
        raise ValueError("repair must bind the unchanged immediately preceding managed result")
    result = json.loads(previous.read_text())
    if result["state"] != "FAIL" or result.get("validation_kind", "deterministic") != "deterministic":
        raise ValueError("repair needs a failed deterministic gate, not PASS, timeout or model-backed evidence")
    if digest(previous.with_name("request.json")) != result.get("request_sha256"):
        raise ValueError("repair's failed manifest changed")
    failed = [entry for entry in result["commands"] if entry["state"] == "FAIL"]
    if not failed or any(digest(Path(entry["log"])) != entry.get("log_sha256") for entry in failed):
        raise ValueError("repair's failed command evidence is missing or changed")
    candidate = git(repo, "rev-parse", "HEAD")
    if job.get("candidate") != candidate:
        raise ValueError("repair candidate must match current HEAD")
    subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", result["candidate"], candidate],
                   check=True, capture_output=True)
    paths = git(repo, "diff", "--name-only", result["candidate"], candidate).splitlines()
    if not any(path and not path.startswith("knowledge/") and Path(path).suffix.lower()
               not in (".md", ".txt", ".log", ".jsonl") for path in paths):
        raise ValueError("repair exception needs changed source; records-only changes do not qualify")
    return True


def register(registry: Path, repo: Path, worktree: Path) -> None:
    worktree = worktree.resolve()
    if Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")) != Path(git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir")):
        raise ValueError("worker worktree must belong to the same repository")
    with registry.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = json.loads(registry.read_text()) if registry.exists() else {}
        rows.setdefault(str(worktree), git(worktree, "rev-parse", "HEAD"))
        write_json(registry, rows)


def source_work(registry: Path) -> bool:
    rows = json.loads(registry.read_text())
    for worktree, base in rows.items():
        repo = Path(worktree)
        paths = git(repo, "diff", "--name-only", base).splitlines()
        paths += git(repo, "ls-files", "--others", "--exclude-standard").splitlines()
        if any(path and not path.startswith("knowledge/") and Path(path).suffix.lower() not in (".md", ".txt", ".log", ".jsonl") for path in paths):
            return True
    return False


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipts(job: dict) -> list[dict]:
    if not job.get("resume_from"):
        return []
    previous = Path(job["resume_from"])
    result = json.loads(previous.read_text())
    if result.get("state") == "INVALIDATED":
        raise ValueError("resume inputs were invalidated; prior checks cannot be reused")
    if digest(previous.with_name("request.json")) != result.get("request_sha256"):
        raise ValueError("resume manifest changed or has no verifiable receipt")
    passed = [entry for entry in result["commands"] if entry["state"] == "PASS"]
    for entry in passed:
        if entry.get("exit_code") != 0:
            raise ValueError("retained PASS has a nonzero or missing exit code")
        if digest(Path(entry["log"])) != entry.get("log_sha256"):
            raise ValueError("retained PASS log changed; resume refused")
    return passed


def source_inputs(command: dict, repo: Path, candidate: str) -> dict:
    """Opt-in content identity; unknown dependencies retain exact-commit binding."""
    if "inputs" not in command:
        return {"candidate": candidate}
    trees = {}
    for path in command["inputs"]:
        entries = subprocess.check_output(
            ["git", "-C", str(repo), "ls-tree", "-r", "-z", candidate, "--", ":(literal)" + path])
        if not entries:
            raise ValueError(f"declared validation input has no tracked files: {path}")
        # Link targets and submodule working trees are not captured by blob IDs.
        if any(not entry.startswith((b"100644 ", b"100755 ")) for entry in entries.split(b"\0") if entry):
            raise ValueError(f"declared validation input contains a symlink or submodule: {path}")
        trees[path] = hashlib.sha256(entries).hexdigest()
    return {"trees": trees}


class Cancelled(Exception):
    """A peer failed or the owning supervisor stopped validation."""


def execute(command: dict, number: int, log_path: Path, repo: Path, environment: dict,
            available: float, cancel: threading.Event) -> dict:
    started = time.monotonic()
    def check_cancel():
        if cancel.is_set():
            raise Cancelled()
    try:
        check_cancel()
        with log_path.open("x") as log:
            outcome = timed_check.run(command["argv"], label=f"validation-{number}", cwd=repo,
                                      env=environment,
                                      timeout_seconds=min(command["timeout_seconds"], available),
                                      on_tick=check_cancel, tick_seconds=.05,
                                      on_output=lambda line: (log.write(line), log.flush()), merge_stderr=True)
        value = {"state": "PASS" if outcome.returncode == 0 else "FAIL", "exit_code": outcome.returncode}
    except Cancelled:
        value = {"state": "CANCELLED", "exit_code": 130}
    except subprocess.TimeoutExpired:
        value = {"state": "BUDGET_EXHAUSTED" if available < command["timeout_seconds"] else "TIMED_OUT", "exit_code": 124}
    except timed_check.CaptureError:
        value = {"state": "CAPTURE_FAILED", "exit_code": 1}
    except OSError:
        value = {"state": "FAIL", "exit_code": 127}
    value["seconds"] = round(time.monotonic() - started, 3)
    if log_path.exists():
        value["log_sha256"] = digest(log_path)
    return value


def run(request: Path, repo: Path, deadline: float, reserve: float, report, tick, tick_seconds: float = 1) -> Path:
    job = plan(json.loads(request.read_text()))
    candidate = job.get("candidate")
    validation_kind = job.get("validation_kind", "deterministic")
    result_path = request.with_name("result.json")
    if result_path.exists():
        raise ValueError("validation request already has a result; do not rerun it")
    retained = receipts(job)
    result = {"candidate": candidate, "requirements": job["requirements"], "state": "PENDING", "commands": [],
              "request_sha256": digest(request), "validation_kind": validation_kind}
    if job.get("repair"):
        result["repair"] = job["repair"]

    def unchanged() -> bool:
        return candidate == git(repo, "rev-parse", "HEAD") and not git(repo, "status", "--porcelain")

    if not unchanged():
        result["state"] = "INVALIDATED"
    elif reserve >= deadline - time.monotonic():
        result["state"] = "BUDGET_DEFERRED"
    else:
        result["state"] = "RUNNING"
    write_json(result_path, result)
    try:
        if result["state"] != "RUNNING":
            return result_path
        pending = list(enumerate(job["commands"], 1))
        active, passed = {}, set()
        cancel = threading.Event()
        # Dependency inputs join the receipt fingerprint: changing preparation
        # cannot accidentally reuse an assertion run against different artifacts.
        by_label = {command["label"]: command for command in job["commands"]}
        def dependency_inputs(command):
            found, remaining = set(), list(command.get("after", []))
            while remaining:
                label = remaining.pop()
                if label not in found:
                    found.add(label)
                    remaining.extend(by_label[label].get("after", []))
            return [{"command": by_label[label],
                     "source": source_inputs(by_label[label], repo, candidate),
                     "environment": command_environment(repo, by_label[label], validation_kind)}
                    for label in sorted(found)]
        def finish(future):
            number, command, entry = active.pop(future)
            entry.update(future.result())
            if entry["state"] == "PASS":
                passed.add(command["label"])
            write_json(result_path, result)
            report("validation", f"Validation {number}/{len(job['commands'])}: {command['label']} {entry['state']} in {entry['seconds']}s.")
            return entry["state"]
        with ThreadPoolExecutor(max_workers=job.get("max_parallel", 1)) as pool:
            try:
                while pending or active:
                    tick()
                    if not unchanged():
                        result["state"] = "INVALIDATED"
                        break
                    for future in list(active):
                        if future.done():
                            state = finish(future)
                            if state != "PASS":
                                result["state"] = state
                                break
                    if result["state"] != "RUNNING":
                        break
                    for number, command in list(pending):
                        if len(active) >= job.get("max_parallel", 1):
                            break
                        if not set(command.get("after", [])) <= passed:
                            continue
                        resources = command.get("resources")
                        if active and (resources is None or any(other.get("resources") is None or
                                set(resources) & set(other["resources"]) for _, other, _ in active.values())):
                            continue
                        environment = command_environment(repo, command, validation_kind)
                        inputs = {"source": source_inputs(command, repo, candidate), "command": command, "environment": environment,
                                  "validation_kind": validation_kind}
                        if command.get("after"):
                            inputs["dependencies"] = dependency_inputs(command)
                        fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
                        components = {key: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
                                      for key, value in inputs.items()}
                        reusable = None if job.get("repair", {}).get("regression") == command["label"] else next(
                            (entry for entry in retained if entry.get("input_fingerprint") == fingerprint), None)
                        if reusable:
                            result["commands"].append({**reusable, "reused_from": job["resume_from"]})
                            passed.add(command["label"])
                            pending.remove((number, command))
                            write_json(result_path, result)
                            report("validation", f"Validation {number}/{len(job['commands'])}: {command['label']} reused verified PASS on unchanged inputs.")
                            continue
                        prior = next((entry for entry in retained if entry.get("label") == command["label"]), None)
                        if prior and prior.get("input_fingerprint") != fingerprint:
                            old = prior.get("input_components")
                            reason = (", ".join(sorted(key for key in set(old) | set(components)
                                                      if old.get(key) != components.get(key))) if old else
                                      "legacy fingerprint mismatch; component hashes unavailable")
                            report("validation", f"{command['label']}: retained PASS not reused: {reason}.")
                            if not old:
                                raise ValueError(f"{command['label']}: legacy PASS fingerprint cannot be matched; "
                                                 "reconcile retained evidence and submit only missing checks; "
                                                 "do not silently repeat completed validation")
                        available = deadline - time.monotonic() - reserve
                        if available <= 0:
                            result["state"] = "BUDGET_EXHAUSTED"
                            break
                        report("validation", f"Validation {number}/{len(job['commands'])}: {command['label']} started; candidate {candidate[:12]}.")
                        log_path = request.with_name(f"command-{number}.log")
                        entry = {"label": command["label"], "argv": command["argv"], "coverage": command["coverage"],
                                 "tested_candidate": candidate,
                                 "log": str(log_path), "state": "RUNNING", "input_fingerprint": fingerprint,
                                 "input_components": components,
                                 "scratch_directory": environment["TMPDIR"]}
                        result["commands"].append(entry)
                        write_json(result_path, result)
                        future = pool.submit(execute, command, number, log_path, repo, environment, available, cancel)
                        active[future] = (number, command, entry)
                        pending.remove((number, command))
                    if result["state"] != "RUNNING":
                        break
                    if active:
                        wait(active, timeout=tick_seconds, return_when=FIRST_COMPLETED)
            finally:
                cancel.set()
                for future in list(active):
                    finish(future)
        if result["state"] == "RUNNING":
            result["state"] = "PASS" if unchanged() else "INVALIDATED"
    except BaseException:
        result["state"] = "CANCELLED"
        for entry in result["commands"]:
            if entry["state"] == "RUNNING":
                entry["state"] = "CANCELLED"
        raise
    finally:
        write_json(result_path, result)
        report("validation", f"Validation job {result['state']} ({validation_kind}); durable results: {result_path}. Independent evidence review still required.")
    return result_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--plan", type=Path)
    submit.add_argument("--resume", type=Path, help="prior result.json; reuse only verified PASS receipts on identical inputs")
    track = sub.add_parser("track-worker")
    track.add_argument("--worktree", type=Path, required=True)
    args = parser.parse_args()
    try:
        repo = Path.cwd()
        if args.action == "track-worker":
            register(Path(os.environ["OKF_WORK_REGISTRY"]), repo, args.worktree)
        else:
            if args.plan is None and args.resume is None:
                raise ValueError("submit needs --plan or --resume")
            source = args.plan if args.plan else args.resume.with_name("request.json")
            value = plan(json.loads(source.read_text()))
            value["candidate"] = git(repo, "rev-parse", "HEAD")
            if args.resume:
                value["resume_from"] = str(args.resume.resolve())
                receipts(value)
            if git(repo, "status", "--porcelain"):
                raise ValueError("commit a clean SAFE handoff before submitting validation")
            destination = Path(os.environ["OKF_VALIDATION_REQUEST"])
            with destination.open("x") as stream:
                json.dump(value, stream, indent=2)
            print(f"Validation submitted for {value['candidate']}; exit this agent session so the driver can execute it.")
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"validation: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
