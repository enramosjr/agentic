#!/usr/bin/env python3
"""Scenario evals for the lifecycle (AGENTS.md §2.5): run a real agent on a prompt in a
throwaway copy of the governance files and check the outcome, not the prose.

    lifecycle_eval.py list
    lifecycle_eval.py check                      # validate the scenario files only
    lifecycle_eval.py run [--scenario ID]... -- AGENT_COMMAND...

The agent command receives the scenario prompt on stdin with the temporary repository as
its working directory, for example ``-- claude -p --permission-mode acceptEdits``. A run
passes only when the lifecycle state and the changed files satisfy the scenario's
``expect`` block. Exit 1 when any scenario fails. Scenarios live in
``.ai/evals/lifecycle/*.json``. Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lifecycle  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / ".ai/evals/lifecycle"
COPY = ("AGENTS.md", "CLAUDE.md", ".ai", ".claude", ".codex", ".cursor", ".agents")
EXPECT_KEYS = {"tier", "user_set", "stages", "redgreen", "changed", "unchanged", "specs", "queue_entries", "transcript"}
TIMEOUT = 1800


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


def validate(scenario: dict) -> list[str]:
    problems = [f"missing '{key}'" for key in ("id", "prompt", "expect") if not scenario.get(key)]
    expect = scenario.get("expect") or {}
    problems += [f"unknown expect key '{key}'" for key in expect if key not in EXPECT_KEYS]
    problems += [f"bad tier '{t}'" for t in expect.get("tier", []) if t not in lifecycle.TIERS]
    problems += [f"bad stage '{s}'" for s in expect.get("stages", []) if s not in lifecycle.STAGES]
    if not expect.get("tier"):
        problems.append("expect.tier is required")
    return problems


def prepare(scenario: dict, work: Path) -> None:
    for name in COPY:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, work / name, ignore=shutil.ignore_patterns("__pycache__", "evals", "tests"))
        elif source.is_file():
            shutil.copy(source, work / name)
    setup = scenario.get("setup", {})
    for name, text in setup.get("files", {}).items():
        target = work / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    git = ["git", "-C", str(work), "-c", "user.email=eval@eval", "-c", "user.name=eval"]
    subprocess.run([*git, "init", "-q"], check=True)
    for command in setup.get("commands", []):
        subprocess.run(command, shell=True, cwd=work, check=True, capture_output=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "eval baseline"], check=True, capture_output=True)


def changed_files(work: Path, base: str) -> set[str]:
    """Files changed since the baseline commit, including ones the agent committed."""
    names = set(lifecycle.git(work, "diff", "--name-only", base).splitlines())
    return names | set(lifecycle.git(work, "ls-files", "-o", "--exclude-standard").splitlines())


def evaluate(scenario: dict, work: Path, transcript: str, base: str) -> list[str]:
    expect, failures = scenario["expect"], []
    state = lifecycle.load(work)
    if state is None:
        return ["no lifecycle tier was ever declared"]
    if state["tier"] not in expect["tier"]:
        failures.append(f"final tier {state['tier']} not in {expect['tier']}")
    if "user_set" in expect and bool(state.get("user_set")) != expect["user_set"]:
        failures.append(f"user_set is {bool(state.get('user_set'))}, expected {expect['user_set']}")
    failures += [f"stage '{s}' was not recorded" for s in expect.get("stages", []) if not lifecycle.complete(state, s)]
    if expect.get("redgreen") and not lifecycle.redgreen_ok(state):
        failures.append("no red-then-green evidence")
    changed = changed_files(work, base)
    failures += [f"no changed file matches '{g}'" for g in expect.get("changed", []) if not any(fnmatch.fnmatch(c, g) for c in changed)]
    failures += [f"'{g}' changed but must not" for g in expect.get("unchanged", []) if any(fnmatch.fnmatch(c, g) for c in changed)]
    if "specs" in expect:
        specs = [p for p in (work / "knowledge/specifications").glob("*.md") if p.name != "index.md"] if (work / "knowledge/specifications").is_dir() else []
        ready = [p for p in specs if not lifecycle.lint_spec(p)]
        if len(ready) < expect["specs"]:
            failures.append(f"{len(ready)} lint-clean spec(s) under knowledge/specifications, expected {expect['specs']}")
    if "queue_entries" in expect:
        queue = work / "knowledge/project/work-queue.md"
        count = len(re.findall(r"^### \S+ — ", queue.read_text(), re.M)) if queue.is_file() else 0
        if count < expect["queue_entries"]:
            failures.append(f"{count} queue entries, expected {expect['queue_entries']}")
    failures += [f"transcript lacks /{r}/" for r in expect.get("transcript", []) if not re.search(r, transcript)]
    return failures


def run_scenario(scenario: dict, agent: list[str]) -> list[str]:
    base = os.environ.get("TMPDIR") or None
    with tempfile.TemporaryDirectory(dir=base) as tmp:
        work = Path(tmp).resolve()
        prepare(scenario, work)
        base = lifecycle.git(work, "rev-parse", "HEAD")
        env = {k: v for k, v in os.environ.items() if k not in ("OKF_AUTONOMOUS", "LIFECYCLE_GUARD")}
        env["LIFECYCLE_EVAL"] = scenario["id"]
        try:
            result = subprocess.run(agent, input=scenario["prompt"], cwd=work, env=env, capture_output=True, text=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            return [f"agent timed out after {TIMEOUT}s"]
        return evaluate(scenario, work, result.stdout + result.stderr, base)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("check")
    run = sub.add_parser("run")
    run.add_argument("--scenario", action="append", default=[])
    run.add_argument("agent", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        scenarios = load_scenarios()
    except (EvalError, ValueError) as error:
        print(f"lifecycle_eval: {error}", file=sys.stderr)
        return 1
    if args.command == "list":
        for scenario in scenarios:
            print(f"{scenario['id']}: tier {'/'.join(scenario['expect']['tier'])}")
        return 0
    if args.command == "check":
        print(f"{len(scenarios)} scenario(s) valid")
        return 0
    agent = [a for a in args.agent if a != "--"]
    if not agent:
        print("lifecycle_eval: give the agent command after `--`", file=sys.stderr)
        return 1
    chosen = [s for s in scenarios if not args.scenario or s["id"] in args.scenario]
    if args.scenario and len(chosen) != len(set(args.scenario)):
        print("lifecycle_eval: unknown scenario id", file=sys.stderr)
        return 1
    failed = 0
    for scenario in chosen:
        failures = run_scenario(scenario, agent)
        failed += bool(failures)
        print(f"{'FAIL' if failures else 'PASS'} {scenario['id']}")
        for failure in failures:
            print(f"  - {failure}")
    print(f"{len(chosen) - failed}/{len(chosen)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
