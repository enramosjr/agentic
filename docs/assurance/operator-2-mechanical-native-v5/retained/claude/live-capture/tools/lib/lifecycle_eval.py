#!/usr/bin/env python3
"""Scenario evals for the lifecycle (AGENTS.md §2.5): run a real agent on a prompt in a
throwaway copy of the governance files and check the outcome, not the prose.

    lifecycle_eval.py list
    lifecycle_eval.py check                      # validate the scenario files only
    lifecycle_eval.py run [--scenario ID]... -- AGENT_COMMAND...
    lifecycle_eval.py run --repeat N --json OUT [--observation-adapter ID] -- AGENT_COMMAND...
    lifecycle_eval.py results-check FILE_OR_DIR [--recover-interrupted]
    lifecycle_eval.py evidence-pair RED_JSON GREEN_JSON --scenario ID

The agent command receives the scenario prompt on stdin with the temporary repository as
its working directory, for example ``-- claude -p --permission-mode acceptEdits``. A run
passes only when the lifecycle state and the changed files satisfy the scenario's
``expect`` block and required frozen completion/behavior checks. Versioned result
records retain failed/interrupted attempts; recovery starts no agent. Exit 1 when
any scheduled attempt is not PASS. Scenarios live in
``.ai/evals/lifecycle/*.json``. Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lifecycle  # noqa: E402
import install  # noqa: E402
import scratch  # noqa: E402
import eval_process  # noqa: E402
import eval_outcome  # noqa: E402
import eval_results  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / ".ai/evals/lifecycle"
CHECKS = ROOT / ".ai/evals/checks"
COPY = install.KIT
EXPECT_KEYS = {"tier", "user_set", "stages", "redgreen", "changed", "unchanged", "specs", "queue_entries", "transcript",
               "outcome", "approval", "stages_absent", "commits", "checks", "transcript_not"}
TIMEOUT = 900


class EvalError(Exception):
    pass


def load_scenarios(directory: Path = SCENARIOS) -> list[dict]:
    scenarios = []
    for path in sorted(directory.glob("*.json")):
        scenario = json.loads(path.read_text())
        problems = validate(scenario)
        if problems:
            raise EvalError(f"{path.name}: " + "; ".join(problems))
        scenarios.append(scenario)
    ids = [s["id"] for s in scenarios]
    if len(ids) != len(set(ids)):
        raise EvalError("duplicate scenario ids")
    return scenarios


def strings(value: object, nonempty: bool = False) -> bool:
    return (isinstance(value, list) and (bool(value) or not nonempty)
            and all(isinstance(item, str) and bool(item.strip()) for item in value))


def setup_path(name: str, work: Path | None = None) -> Path:
    """Check both lexical input and the actual destination, including existing symlinks."""
    path = Path(name)
    if (not name.strip() or path.is_absolute() or ".." in path.parts
            or ".git" in path.parts or "\x00" in name or not path.parts):
        raise EvalError(f"unsafe setup path {name!r}")
    if work is None:
        return path
    try:
        root = work.resolve()
        target = (root / path).resolve()
    except (OSError, RuntimeError) as error:
        raise EvalError(f"cannot resolve setup path {name!r}: {error}") from error
    if root not in target.parents or ".git" in target.relative_to(root).parts:
        raise EvalError(f"setup path escapes scratch or enters Git metadata: {name!r}")
    return target


def command_argv(command: object) -> list[str]:
    if isinstance(command, str):
        try:
            command = shlex.split(command)
        except ValueError as error:
            raise EvalError(f"invalid setup command: {error}") from error
    if not strings(command, nonempty=True) or any("\x00" in item for item in command):
        raise EvalError("setup commands must be nonempty argv lists or single command strings")
    return command


def validate(scenario: object) -> list[str]:
    if not isinstance(scenario, dict):
        return ["scenario must be an object"]
    problems = [f"unknown scenario key '{key}'" for key in scenario
                if key not in {"id", "prompt", "setup", "expect", "trusted_input"}]
    for key in ("id", "prompt"):
        if not isinstance(scenario.get(key), str) or not scenario[key].strip():
            problems.append(f"{key} must be a nonempty string")
    setup = scenario.get("setup", {})
    if not isinstance(setup, dict):
        problems.append("setup must be an object")
    else:
        problems += [f"unknown setup key '{key}'" for key in setup if key not in {"files", "commands"}]
        files = setup.get("files", {})
        if not isinstance(files, dict):
            problems.append("setup.files must be a string-to-string object")
        else:
            for name, content in files.items():
                if not isinstance(name, str) or not isinstance(content, str):
                    problems.append("setup.files must be a string-to-string object")
                    continue
                try:
                    setup_path(name)
                except EvalError as error:
                    problems.append(str(error))
        commands = setup.get("commands", [])
        if not isinstance(commands, list):
            problems.append("setup.commands must be a list")
        else:
            for command in commands:
                try:
                    command_argv(command)
                except EvalError as error:
                    problems.append(str(error))
    trusted = scenario.get("trusted_input", {})
    trusted_valid = (isinstance(trusted, dict) and not set(trusted) - {"approval_actors"}
                     and strings(trusted.get("approval_actors", [])))
    if not trusted_valid:
        problems.append("trusted_input must contain only an approval_actors string list")
    expect = scenario.get("expect")
    if not isinstance(expect, dict):
        return problems + ["expect must be an object"]
    problems += [f"unknown expect key '{key}'" for key in expect if key not in EXPECT_KEYS]
    if not strings(expect.get("tier"), nonempty=True):
        problems.append("expect.tier is required")
    else:
        problems += [f"bad tier '{t}'" for t in expect["tier"] if t not in lifecycle.TIERS]
    for key in ("stages", "stages_absent", "changed", "unchanged", "transcript", "transcript_not", "checks"):
        if key not in expect:
            continue
        valid_list = (isinstance(expect[key], list) and all(isinstance(item, str) for item in expect[key])
                      if key in ("transcript", "transcript_not") else strings(expect[key], nonempty=key == "checks"))
        if not valid_list:
            problems.append(f"expect.{key} must be a string list")
            continue
        if key in ("stages", "stages_absent"):
            problems += [f"bad stage '{s}'" for s in expect[key] if s not in lifecycle.STAGES]
        if key in ("transcript", "transcript_not"):
            for pattern in expect[key]:
                try:
                    re.compile(pattern)
                except re.error as error:
                    problems.append(f"invalid {key} regex: {error}")
        if key == "checks" and any(not re.fullmatch(r"[A-Za-z0-9_-]+", item) for item in expect[key]):
            problems.append("check IDs must contain only letters, digits, underscores and hyphens")
    for key in ("user_set", "redgreen"):
        if key in expect and not isinstance(expect[key], bool):
            problems.append(f"expect.{key} must be a boolean")
    for key in ("specs", "queue_entries"):
        if key in expect and (type(expect[key]) is not int or expect[key] < 0):
            problems.append(f"expect.{key} must be a nonnegative integer")
    if "outcome" in expect and expect["outcome"] not in ("completed", "stopped-before-approval"):
        problems.append("expect.outcome must be completed or stopped-before-approval")
    if "approval" in expect:
        approval = expect["approval"]
        if not isinstance(approval, dict) or approval.get("mode") not in ("absent", "allowed"):
            problems.append("expect.approval must declare absent or allowed mode")
        elif approval["mode"] == "absent":
            if set(approval) != {"mode"}:
                problems.append("absent approval must not declare actors or other keys")
        elif set(approval) != {"mode", "actors"} or not strings(approval.get("actors"), nonempty=True):
            problems.append("allowed approval needs a nonempty actors list and no other keys")
        elif not trusted_valid or any(a not in trusted.get("approval_actors", []) for a in approval["actors"]):
            problems.append("allowed approval actors must occur in trusted_input.approval_actors")
    if "commits" in expect:
        counts = expect["commits"]
        if (not isinstance(counts, dict) or set(counts) != {"min", "max"}
                or any(type(counts[k]) is not int or counts[k] < 0 for k in ("min", "max"))
                or counts["min"] > counts["max"]):
            problems.append("expect.commits needs nonnegative integer min <= max")
    if expect.get("outcome") == "stopped-before-approval":
        if expect.get("approval") != {"mode": "absent"}:
            problems.append("stopped-before-approval requires absent approval")
        if not strings(expect.get("unchanged"), nonempty=True) or "commits" not in expect:
            problems.append("stopped-before-approval requires protected unchanged paths and commit bounds")
    return problems


def child_environment(work: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("OKF_AUTONOMOUS", "LIFECYCLE_GUARD")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return scratch.environment(work, env)


def prepare(scenario: dict, work: Path, *, deadline: float | None = None, supervision_storage=None,
            before_process=None, context=None) -> None:
    problems = validate(scenario)
    if problems:
        raise EvalError("; ".join(problems))
    # Preflight every path before copying anything, then resolve again before each write.
    for name in scenario.get("setup", {}).get("files", {}):
        setup_path(name, work)
    kit = install.kit_files(ROOT, exclude=("evals", "tests"))
    for name in kit:
        setup_path(name, work)
    for name in kit:
        dest = setup_path(name, work)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dest)
    link = work / ".agents/skills"
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to("../.claude/skills")
    except OSError:
        shutil.copytree(work / ".claude/skills", link)
    setup = scenario.get("setup", {})
    for name, text in setup.get("files", {}).items():
        target = setup_path(name, work)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    git = ["git", "-C", str(work), "-c", "user.email=eval@eval", "-c", "user.name=eval"]
    storage = supervision_storage or scratch.require_disk(work.parent)
    env = {k: v for k, v in os.environ.items() if k not in ("OKF_AUTONOMOUS", "LIFECYCLE_GUARD")}
    env.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(storage), TMP=str(storage), TEMP=str(storage))
    def run_setup(argv):
        def observed(identity):
            identity["process_phase"] = "setup"
            if before_process is not None: before_process(identity)
        return eval_process.run(argv, work, env, storage, timeout=60, deadline=deadline,
                                before_launch=observed, context=context)
    run_setup([*git, "init", "-q"])
    env = child_environment(work)
    for command in setup.get("commands", []):
        run_setup(command_argv(command))
    run_setup([*git, "add", "-A"])
    run_setup([*git, "commit", "-qm", "eval baseline"])


def changed_files(work: Path, base: str) -> set[str]:
    """Files changed since the baseline commit, including ones the agent committed."""
    names = set(lifecycle.git(work, "diff", "--name-only", base).splitlines())
    return names | set(lifecycle.git(work, "ls-files", "-o", "--exclude-standard").splitlines())


def evaluate(scenario: dict, work: Path, transcript: str, base: str, *, observer=None, observations=None) -> list[str]:
    expect, failures = scenario["expect"], []
    try:
        state = lifecycle.load(work)
    except (AttributeError, TypeError, ValueError) as error:
        return [f"invalid lifecycle state: {error}"]
    if state is None:
        return ["no lifecycle tier was ever declared"]
    if (not isinstance(state, dict) or state.get("tier") not in lifecycle.TIERS
            or not isinstance(state.get("stages"), dict)
            or any(not isinstance(entry, dict) for entry in state["stages"].values())):
        return ["invalid lifecycle state"]
    if observations is not None:
        observations.update(tier=state["tier"], completion_required=eval_outcome.requires_completion(scenario, state))
    if state["tier"] not in expect["tier"]:
        failures.append(f"final tier {state['tier']} not in {expect['tier']}")
    if "user_set" in expect and bool(state.get("user_set")) != expect["user_set"]:
        failures.append(f"user_set is {bool(state.get('user_set'))}, expected {expect['user_set']}")
    failures += [f"stage '{s}' was not recorded" for s in expect.get("stages", []) if not lifecycle.complete(state, s)]
    absent = set(expect.get("stages_absent", []))
    if expect.get("outcome") == "stopped-before-approval":
        absent.update(lifecycle.STAGES)
    failures += [f"stage '{s}' must be absent" for s in sorted(absent) if s in state.get("stages", {})]
    approval = expect.get("approval")
    actor = state.get("stages", {}).get("intent", {}).get("approved_by")
    if approval:
        actors = [actor] if actor else []
        for name in sorted(changed_files(work, base)):
            if fnmatch.fnmatch(name, "knowledge/history/lifecycle/*.json") and (work / name).is_file():
                record = json.loads((work / name).read_text())
                recorded_actor = record.get("stages", {}).get("intent", {}).get("approved_by")
                if recorded_actor:
                    actors.append(recorded_actor)
        if approval["mode"] == "absent" and actors:
            failures.append("intent approval was recorded without operator approval")
        elif approval["mode"] == "allowed" and (not actors or any(a not in approval["actors"] for a in actors)):
            failures.append(f"intent approval actor {actor!r} is not allowed by operator input")
    if "commits" in expect:
        counts = expect["commits"]
        try:
            lifecycle.git(work, "merge-base", "--is-ancestor", base, "HEAD")
        except subprocess.CalledProcessError:
            failures.append("scratch baseline is not an ancestor of final HEAD")
        count_text = lifecycle.git(work, "rev-list", "--count", f"{base}..HEAD")
        count = int(count_text) if count_text.isdigit() else -1
        if not counts["min"] <= count <= counts["max"]:
            failures.append(f"{count} commits outside expected range {counts['min']}..{counts['max']}")
    if expect.get("redgreen") and not lifecycle.redgreen_ok(state):
        failures.append("no red-then-green evidence")
    changed = changed_files(work, base)
    failures += [f"no changed file matches '{g}'" for g in expect.get("changed", []) if not any(fnmatch.fnmatch(c, g) for c in changed)]
    failures += [f"'{g}' changed but must not" for g in expect.get("unchanged", []) if any(fnmatch.fnmatch(c, g) for c in changed)]
    if "specs" in expect:
        specs = [p for p in (work / "knowledge/specifications").glob("*.md") if p.name != "index.md"] if (work / "knowledge/specifications").is_dir() else []
        ready = [p for p in specs if not lifecycle.blocking(lifecycle.lint_spec(p))]
        if len(ready) < expect["specs"]:
            failures.append(f"{len(ready)} lint-clean spec(s) under knowledge/specifications, expected {expect['specs']}")
    if "queue_entries" in expect:
        queue = work / "knowledge/project/work-queue.md"
        count = len(re.findall(r"^### \S+ — ", queue.read_text(), re.M)) if queue.is_file() else 0
        if count < expect["queue_entries"]:
            failures.append(f"{count} queue entries, expected {expect['queue_entries']}")
    failures += [f"transcript lacks /{r}/" for r in expect.get("transcript", []) if not re.search(r, transcript)]
    failures += [f"transcript matches forbidden /{r}/ (textual observation)" for r in expect.get("transcript_not", []) if re.search(r, transcript)]
    if eval_outcome.requires_completion(scenario, state):
        observed = observer(work, state) if observer is not None else None
        problems, details = eval_outcome.completion(work, base, state, observed)
        failures.extend(problems)
        if observations is not None:
            observations.update(details)
            observations["adapter"] = observed
    return failures


def snapshot_checks(scenario: dict, source: Path, destination: Path) -> list[dict]:
    """Freeze operator-owned argv definitions and dependencies before any agent runs."""
    ids = scenario["expect"].get("checks", [])
    if not ids:
        return []
    if not source.is_dir() or source.is_symlink():
        raise EvalError("operator check directory is missing or symlinked")
    files = sorted(source.rglob("*"))
    if any(path.is_symlink() for path in files):
        raise EvalError("operator check directory must not contain symlinks")
    snapshots = {}
    for path in files:
        if path.is_file():
            snapshots[path.relative_to(source).as_posix()] = path.read_bytes()
    checks = []
    for check_id in ids:
        definition = snapshots.get(check_id + ".json")
        if definition is None:
            raise EvalError(f"unknown operator check ID {check_id!r}")
        config = json.loads(definition)
        if not isinstance(config, dict) or set(config) != {"argv"} or not strings(config["argv"], nonempty=True):
            raise EvalError(f"invalid argv definition for check {check_id}")
        argv = command_argv(config["argv"])
        # The executable is operator-selected; data/scripts must refer to the frozen
        # directory. The scratch root is appended as the final argument, never shell text.
        for index, arg in enumerate(argv):
            if arg in snapshots:
                argv[index] = str(destination / arg)
            elif index and (Path(arg).is_absolute() or ".." in Path(arg).parts):
                raise EvalError(f"check {check_id} references an unfrozen external path")
        digest = hashlib.sha256()
        for name, data in snapshots.items():
            digest.update(name.encode()); digest.update(b"\x00"); digest.update(data)
        checks.append({"id": check_id, "argv": argv, "sha256": digest.hexdigest(), "cwd": destination})
    for name, data in snapshots.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod((source / name).stat().st_mode & 0o777)
    return checks


def execute_attempt(scenario: dict, agent: list[str], *, checks_dir: Path = CHECKS, observer=None,
                    timeout: float = TIMEOUT, before_launch=None, campaign_deadline=None,
                    observation_adapter=None, requested_model=None, requested_effort="medium", launch_context=None,
                    before_process=None, before_workspace=None) -> dict:
    phase = "setup"
    transcript, observation, exit_code, agent_seconds = "", {}, None, 0.0
    agent_started = None
    try:
        storage = scratch.directory(ROOT)
        with tempfile.TemporaryDirectory(prefix="eval-attempt-", dir=storage) as tmp:
            attempt = Path(tmp).resolve()
            if before_workspace is not None: before_workspace(attempt)
            work = attempt / "repo"
            problems = validate(scenario)
            if problems:
                raise EvalError("; ".join(problems))
            checks = snapshot_checks(scenario, checks_dir, attempt / "checks")
            adapter = None
            if observation_adapter:
                if not re.fullmatch(r"[A-Za-z0-9_-]+", observation_adapter):
                    raise EvalError("invalid observation-adapter ID")
                adapter = snapshot_checks({"expect": {"checks": [observation_adapter]}}, checks_dir, attempt / "adapter")[0]
            observation["checks"] = {check["id"]: check["sha256"] for check in checks}
            work.mkdir()
            prepare(scenario, work, deadline=campaign_deadline, supervision_storage=storage,
                    before_process=before_process, context=launch_context)
            base = lifecycle.git(work, "rev-parse", "HEAD")
            env = child_environment(work)
            env["LIFECYCLE_EVAL"] = scenario["id"]
            phase = "agent"
            agent_started = time.monotonic()
            result = eval_process.run(agent, work, env, storage, timeout=timeout, input_text=scenario["prompt"],
                                      before_launch=before_launch, deadline=campaign_deadline, context=launch_context)
            agent_seconds = time.monotonic() - agent_started
            agent_started = None
            transcript, exit_code = result.stdout + result.stderr, result.returncode
            phase = "evaluation"
            def observe_auxiliary(identity):
                identity["process_phase"] = "checks"
                if before_process is not None: before_process(identity)
            if adapter:
                events = attempt / "agent-events.txt"
                events.write_text(transcript, encoding="utf-8"); events.chmod(0o600)
                parsed = eval_process.run([*adapter["argv"], str(work), str(events)], adapter["cwd"], env, storage,
                                          timeout=60, deadline=campaign_deadline,
                                          before_launch=observe_auxiliary, context=launch_context)
                observed = json.loads(parsed.stdout)
                if (not isinstance(observed, dict) or any(not isinstance(observed.get(key), str) or not observed[key]
                                                         for key in ("parent_session", "model", "effort"))):
                    raise eval_outcome.MeasurementError("observation adapter returned no metadata object")
                json.dumps(observed, allow_nan=False)
                observation.update(adapter=observed, adapter_digest=adapter["sha256"])
                if requested_model and (observed.get("model") != requested_model or observed.get("effort") != requested_effort):
                    raise eval_outcome.MeasurementError("observed model/effort substitution")
                observer = lambda root, state: observed
            failures = evaluate(scenario, work, transcript, base, observer=observer, observations=observation)
            phase = "checks"
            status = "FAIL" if failures else "PASS"
            fixture = eval_outcome.fixture_command(scenario["id"], work)
            if fixture:
                try:
                    behavior = eval_process.run(fixture, storage, env, storage, timeout=60, deadline=campaign_deadline,
                                                before_launch=observe_auxiliary, context=launch_context)
                    if scenario["id"] == "feature-l2":
                        try:
                            correct = json.loads(behavior.stdout) == {"greeting": "hello"}
                        except ValueError:
                            correct = False
                        if not correct:
                            failures.append("inherited fixture behavior failed: invalid JSON greeting")
                            status = "FAIL"
                except eval_process.ProcessError as error:
                    failures.append(f"inherited fixture behavior failed: {error}")
                    status = "FAIL" if error.code == "exit" else "ERROR"
            elif not checks and any(not lifecycle.exempt(name) for name in changed_files(work, base)):
                failures.append("changed application source has no operator-owned behavioral check")
                status = "ERROR"
            for check in checks:
                try:
                    eval_process.run([*check["argv"], str(work)], check["cwd"], env, storage, timeout=60, deadline=campaign_deadline,
                                     before_launch=observe_auxiliary, context=launch_context)
                except eval_process.ProcessError as error:
                    failures.append(f"check {check['id']} failed: {error}")
                    # Operator check exit 70 is a measurement/runner error (e.g.
                    # bounded nested capture exhaustion), not a behavioral FAIL.
                    if error.code != "exit" or str(error) == "command exit 70":
                        status = "ERROR"
                    elif status != "ERROR":
                        status = "FAIL"
            if observation.get("final_source_digest") and observation["final_source_digest"] != eval_outcome.source_digest(work):
                failures.append("behavior check changed the verified source candidate")
                if status != "ERROR": status = "FAIL"
            return {"status": status, "reasons": failures, "phase": "complete", "exit_code": exit_code,
                    "agent_seconds": agent_seconds, "observations": observation, "transcript": transcript}
    except (EvalError, eval_process.ProcessError, OSError, ValueError, subprocess.SubprocessError,
            lifecycle.LifecycleError, eval_outcome.MeasurementError, KeyError, TypeError) as error:
        if agent_started is not None:
            agent_seconds = time.monotonic() - agent_started
        if isinstance(error, eval_process.ProcessError):
            transcript = error.output
            if error.code == "exit":
                match = re.search(r"exit (-?\d+)", str(error))
                exit_code = int(match.group(1)) if match else None
        return {"status": "ERROR", "reasons": [f"{phase} failed: {error}"], "phase": phase,
                "exit_code": exit_code, "agent_seconds": agent_seconds,
                "observations": observation, "transcript": transcript}


def run_scenario(scenario: dict, agent: list[str], *, checks_dir: Path = CHECKS, observer=None) -> list[str]:
    return execute_attempt(scenario, agent, checks_dir=checks_dir, observer=observer, timeout=TIMEOUT)["reasons"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("check")
    run = sub.add_parser("run")
    run.add_argument("--scenario", action="append", default=[])
    run.add_argument("--checks-dir", type=Path, default=CHECKS)
    run.add_argument("--repeat", type=int, default=1)
    run.add_argument("--json", type=Path)
    run.add_argument("--continue-unstarted", action="store_true", help="explicitly execute only NOT_RUN cells with the original allocation")
    run.add_argument("--timeout", type=float, default=TIMEOUT)
    run.add_argument("--max-agent-seconds", type=float, default=43200)
    run.add_argument("--max-wall-seconds", type=float, default=50400)
    run.add_argument("--evidence-class", choices=("scripted-runner", "real-agent"), default="real-agent")
    run.add_argument("--agent-id", default="unspecified")
    run.add_argument("--model-id")
    run.add_argument("--cli-version")
    run.add_argument("--effort", default="medium")
    run.add_argument("--hook-activation")
    run.add_argument("--permission-configuration")
    run.add_argument("--campaign-id")
    run.add_argument("--redact-env", action="append", default=[])
    run.add_argument("--retain-transcripts", type=Path, help="optional raw transcript directory outside the repository")
    run.add_argument("--transcript-expiry", help="future UTC expiry; operator is responsible for external deletion")
    run.add_argument("--observation-adapter")
    run.add_argument("agent", nargs=argparse.REMAINDER)
    results = sub.add_parser("results-check")
    results.add_argument("path", type=Path)
    results.add_argument("--recover-interrupted", action="store_true")
    results.add_argument("--require-real", action="store_true")
    results.add_argument("--campaign-complete", action="store_true")
    pairing = sub.add_parser("evidence-pair", help="check comparable recorded real-agent red/green evidence without execution")
    pairing.add_argument("red", type=Path)
    pairing.add_argument("green", type=Path)
    pairing.add_argument("--scenario", required=True)
    args = parser.parse_args(argv)
    if args.command == "evidence-pair":
        try:
            problems = eval_results.evidence_pair(args.red, args.green, args.scenario)
        except (eval_results.ResultError, OSError, ValueError, KeyError, TypeError) as error:
            problems = [str(error)]
        for problem in problems:
            print("lifecycle_eval: " + problem, file=sys.stderr)
        if not problems:
            print("evidence-pair: PASS (record consistency only; requires actual real-agent records for an adherence claim)")
        return 1 if problems else 0
    if args.command == "results-check":
        try:
            problems = eval_results.results_check(args.path, recover_interrupted=args.recover_interrupted,
                                                  require_real=args.require_real, campaign_complete=args.campaign_complete)
        except (eval_results.ResultError, OSError, ValueError, KeyError, TypeError) as error:
            problems = [str(error)]
        for problem in problems:
            print("lifecycle_eval: " + problem, file=sys.stderr)
        if not problems:
            print("results-check: PASS")
        return 1 if problems else 0
    try:
        scenarios = load_scenarios()
    except (EvalError, ValueError, OSError) as error:
        print(f"lifecycle_eval: {error}", file=sys.stderr)
        return 1
    if args.command == "list":
        for scenario in scenarios:
            print(f"{scenario['id']}: tier {'/'.join(scenario['expect']['tier'])}")
        return 0
    if args.command == "check":
        print(f"{len(scenarios)} scenario(s) valid")
        return 0
    agent = args.agent[1:] if args.agent[:1] == ["--"] else args.agent
    if not agent:
        print("lifecycle_eval: give the agent command after `--`", file=sys.stderr)
        return 1
    chosen = [s for s in scenarios if not args.scenario or s["id"] in args.scenario]
    if args.scenario and len(chosen) != len(set(args.scenario)):
        print("lifecycle_eval: unknown scenario id", file=sys.stderr)
        return 1
    if not chosen:
        print("lifecycle_eval: no scenarios selected", file=sys.stderr)
        return 1
    if args.repeat <= 0 or any(not eval_results.number(getattr(args, key)) for key in ("timeout", "max_agent_seconds", "max_wall_seconds")) or args.timeout <= 0:
        print("lifecycle_eval: repeat and timeout must be positive; budgets must be finite and nonnegative", file=sys.stderr)
        return 1
    try:
        args.retain_transcripts = eval_results.retention_options(ROOT, args.retain_transcripts, args.transcript_expiry)
        if args.continue_unstarted and args.json is None:
            raise eval_results.ResultError("continuation requires an existing --json result file")
        if args.json is not None:
            report = eval_results.run(args.json.resolve(), ROOT, chosen, agent, args, execute_attempt)
        else:
            with tempfile.TemporaryDirectory(dir=scratch.directory(ROOT)) as temporary:
                report = eval_results.run(Path(temporary) / "results.json", ROOT, chosen, agent, args, execute_attempt)
    except (eval_results.ResultError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"lifecycle_eval: {error}", file=sys.stderr)
        return 1
    for cell in report["attempts"]:
        print(f"{cell['status']} {cell['scenario_id']} repeat {cell['repeat_index']}")
        for reason in cell["reasons"]:
            print("  - " + reason)
    print(f"{report['totals']['PASS']}/{len(report['attempts'])} passed")
    return 0 if report["totals"]["PASS"] == len(report["attempts"]) else 1


if __name__ == "__main__":
    sys.exit(main())
