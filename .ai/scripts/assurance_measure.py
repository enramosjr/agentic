#!/usr/bin/env python3
"""Measure assurance detection and rerun costs on six deterministic fixtures."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field, replace
import json
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import time
from typing import Callable, Optional, TextIO

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from assurance_demo import Session, DemoFailure, _base, build, HERE  # noqa: E402
import scratch  # noqa: E402

LIMIT = "Measures mechanism behavior on fixtures, not agent outcomes."
CAPABILITY = "knowledge/capabilities/measure.md"
METRICS = ("caught", "false_stale", "missed", "changed_missed", "reruns", "baseline_reruns")


@dataclass(frozen=True)
class Req:
    id: str
    verify_flags: tuple[str, ...]
    inputs: Optional[tuple[str, ...]]
    reads: tuple[str, ...]


@dataclass(frozen=True)
class Step:
    title: str
    change: dict[str, str]
    expect: tuple[int, int, int]
    setup: tuple[Req, ...] = ()
    affected: Optional[tuple[str, ...]] = None
    after: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    name: str
    reqs: tuple[Req, ...]
    steps: tuple[Step, ...]


CALC = Req("MEAS-R1", (), ("src/calc.py", "src/lib.py"), ("src/calc.py", "src/lib.py"))
DOCS = Req("MEAS-R2", (), ("docs/guide.txt",), ("docs/guide.txt",))
CONFIG = Req("MEAS-R3", (), ("src/lib.py",), ("config.ini", "src/lib.py"))
WHOLE = Req("MEAS-R4", (), None, ("docs/guide.txt",))
SCENARIOS = (
    Scenario("feature", (CALC, DOCS), (
        Step("source and feature added", {"src/calc.py": "ok feature\n", "src/feature.py": "ok\n"}, (1, 0, 0)),)),
    Scenario("requirement-change", (CALC, DOCS), (
        Step("verification command changed", {}, (1, 0, 0), affected=("MEAS-R1",)),)),
    Scenario("regression", (CALC, DOCS), (
        Step("source broken", {"src/calc.py": "broken\n"}, (1, 0, 0), after={"MEAS-R1": "FAILED"}),)),
    Scenario("stale-evidence", (CALC, DOCS), (
        Step("unrelated note changed", {"notes.txt": "note edited\n"}, (0, 0, 0)),
        Step("guide changed", {"docs/guide.txt": "ok edited\n"}, (1, 0, 0)))),
    Scenario("dependency", (CALC, CONFIG), (
        Step("declared dependency changed", {"src/lib.py": "ok edited\n"}, (2, 0, 0)),
        Step("undeclared dependency changed", {"config.ini": "ok edited\n"}, (0, 0, 1)),
        Step("whole tree unrelated edit", {"notes.txt": "note edited\n"}, (0, 1, 0), setup=(WHOLE,)))),
    Scenario("handoff", (CALC, DOCS), (
        Step("input changed after handoff", {"src/calc.py": "ok handoff\n"}, (1, 0, 0)),)),
)


def affected(reqs: tuple[Req, ...], step: Step) -> set[str]:
    if step.affected is not None:
        return set(step.affected)
    return {req.id for req in reqs if set(req.reads) & set(step.change)}


def check_script(req: Req) -> str:
    return ("from pathlib import Path\nimport sys\n"
            f"reads = {req.reads!r}\n"
            "texts = [Path(name).read_text() for name in reads]\n"
            "sys.exit(3 if any(\"broken\" in text for text in texts) else 0)\n")


def capability(reqs: tuple[Req, ...]) -> str:
    text = "---\ntype: Capability\ntitle: Measurement\nnamespace: MEAS\nstatus: draft\n---\n\n# Measurement\n\n## Requirements\n\n"
    for req in reqs:
        command = " ".join(("python3", f"checks/{req.id}.py", *req.verify_flags))
        text += f"- {req.id}: The fixture MUST pass its check.\n  - Verify: `{command}`\n"
        if req.inputs is not None:
            inputs = (f"checks/{req.id}.py", *req.inputs)
            text += "  - Inputs: " + " ".join(f"`{name}`" for name in inputs) + "\n"
        text += "  - Scenario check: All true reads exist and contain no broken marker.\n"
    return text + "\n## Notes\n\nFixture measurement only.\n"


def observe(session: Session, reqs: tuple[Req, ...], *extra: str) -> dict[str, dict]:
    result = session.lifecycle("assure", "--json", *extra, ok=(0, 1))
    try:
        document = json.loads(result.stdout)
        items = {item["id"]: item for item in document["requirements"]}
        if "--changed" not in extra and set(items) != {req.id for req in reqs}:
            raise ValueError("unexpected requirement ids")
        for item in items.values():
            if item["status"] not in {"VERIFIED", "STALE", "FAILED", "UNVERIFIED"}:
                raise ValueError("unexpected requirement status")
        return items
    except (ValueError, KeyError, TypeError):
        raise DemoFailure("assure --json returned invalid measurement requirements")


def commit(session: Session) -> None:
    session.git("add", "-A")
    session.git("commit", "-qm", "measurement checkpoint")


def measure(base: Optional[Path] = None, hook: Optional[Callable[[Path], None]] = None,
            only: Optional[tuple[str, ...]] = None) -> dict:
    base = scratch.require_disk(base if base is not None else _base())
    data = {"schema_version": 1, "scenarios": [], "totals": dict.fromkeys(METRICS, 0),
            "contribution": {"reruns_avoided": 0, "whole_tree_false_stale": 0,
                             "changed_listed": 0, "changed_missed": 0, "handoff_from_record": 0},
            "failures": []}
    for scenario in SCENARIOS:
        if only is not None and scenario.name not in only:
            continue
        directory = Path(tempfile.mkdtemp(prefix="assurance-measure-", dir=base))
        try:
            session = Session(directory / "repo", [])
            reqs = scenario.reqs

            def prepare(repo: Path) -> None:
                (repo / "knowledge/capabilities/demo.md").unlink()
                for name in ("src/calc.py", "src/lib.py", "docs/guide.txt", "config.ini", "notes.txt"):
                    session.write(name, "ok\n")
                for req in reqs:
                    session.write(f"checks/{req.id}.py", check_script(req))
                session.write(CAPABILITY, capability(reqs))
                session.tool("okf.py", "reindex")
                if hook:
                    hook(repo / ".ai/scripts")

            build(session, prepare)
            session.lifecycle("assure", "--run", ok=(0, 1))
            commit(session)
            if scenario.name == "handoff":
                # Records and task names have second precision. Give the later task a later
                # timestamp so this fixture measures handoff rather than same-second ordering.
                time.sleep(1.05)
                session.lifecycle("tier", "L1", "--reason", "measurement handoff", "--new")
            rows = []
            for step in scenario.steps:
                if step.setup:
                    reqs += step.setup
                    for req in step.setup:
                        session.write(f"checks/{req.id}.py", check_script(req))
                    session.write(CAPABILITY, capability(reqs))
                    session.lifecycle("assure", "--run", *(req.id for req in step.setup), ok=(0, 1))
                    commit(session)
                for name, text in step.change.items():
                    session.write(name, text)
                if step.affected is not None:
                    reqs = tuple(replace(req, verify_flags=("--strict",)) if req.id in step.affected else req for req in reqs)
                    session.write(CAPABILITY, capability(reqs))
                items = observe(session, reqs)
                listed = set(observe(session, reqs, "--changed", "--base", "HEAD"))
                truth = affected(reqs, step)
                flagged = {rid for rid, item in items.items() if item["status"] in {"STALE", "FAILED", "UNVERIFIED"}}
                row = {"title": step.title, "affected": sorted(truth), "flagged": sorted(flagged),
                       "caught": len(truth & flagged), "false_stale": len(flagged - truth),
                       "missed": len(truth - flagged), "changed_missed": len(truth - listed),
                       "reruns": len(flagged), "baseline_reruns": len(items)}
                label = scenario.name + "/" + step.title
                for metric, expected in zip(("caught", "false_stale", "missed"), step.expect):
                    if row[metric] != expected:
                        data["failures"].append(f"{label}: {metric} expected {expected} observed {row[metric]}")
                contribution = data["contribution"]
                contribution["reruns_avoided"] += row["baseline_reruns"] - row["reruns"]
                contribution["whole_tree_false_stale"] += len((flagged - truth) & {r.id for r in reqs if r.inputs is None})
                contribution["changed_listed"] += len(truth & listed)
                contribution["changed_missed"] += row["changed_missed"]
                if scenario.name == "handoff":
                    for rid in truth & flagged:
                        record = (items[rid].get("evidence") or {}).get("record")
                        if record and session.exec(["git", "ls-files", "--", "knowledge/history/lifecycle/" + record]).stdout.strip():
                            contribution["handoff_from_record"] += 1
                if flagged:
                    session.lifecycle("assure", "--run", *sorted(flagged), ok=(0, 1))
                    after = observe(session, reqs)
                    for rid in sorted(flagged):
                        expected = step.after.get(rid, "VERIFIED")
                        status = after[rid]["status"]
                        if status != expected:
                            data["failures"].append(f"{label}: {rid} status expected {expected} observed {status}")
                commit(session)
                rows.append(row)
                for key in METRICS:
                    data["totals"][key] += row[key]
            data["scenarios"].append({"name": scenario.name, "steps": rows})
        finally:
            shutil.rmtree(directory)
    return data


def report(data: dict, out: TextIO) -> None:
    out.write(" " * 53 + " ".join(f"{key:>15}" for key in ("affected", "flagged", *METRICS)) + "\n")

    def row(label: str, values: dict) -> None:
        counts = [len(values[key]) if isinstance(values[key], list) else values[key]
                  for key in ("affected", "flagged", *METRICS)]
        out.write(f"{label:53}" + " ".join(f"{value:15}" for value in counts) + "\n")

    for scenario in data["scenarios"]:
        for step in scenario["steps"]:
            row(scenario["name"] + ": " + step["title"], step)
        totals = {key: sum(s[key] for s in scenario["steps"]) for key in METRICS}
        totals.update({key: sum(len(s[key]) for s in scenario["steps"]) for key in ("affected", "flagged")})
        row(scenario["name"] + " total", totals)
    row("grand total", {**data["totals"], "affected": data["totals"]["caught"] + data["totals"]["missed"],
                        "flagged": data["totals"]["reruns"]})
    out.write("contribution:\n")
    for key, value in data["contribution"].items():
        out.write(f"  {key}: {value}\n")
    if data["failures"]:
        for failure in data["failures"]:
            out.write("FAIL " + failure + "\n")
    else:
        out.write(LIMIT + "\n")


def run(base: Optional[Path] = None, hook: Optional[Callable[[Path], None]] = None,
        only: Optional[tuple[str, ...]] = None, out: Optional[TextIO] = None,
        err: Optional[TextIO] = None, json_output: bool = False) -> int:
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        base = scratch.require_disk(base if base is not None else _base())
    except (DemoFailure, ValueError, OSError) as failure:
        err.write(f"assurance_measure: {failure}\n")
        return 2
    try:
        data = measure(base=base, hook=hook, only=only)
        if json_output:
            out.write(json.dumps(data, sort_keys=True) + "\n")
        else:
            report(data, out)
        return 1 if data["failures"] else 0
    except DemoFailure as failure:
        err.write(f"assurance_measure: {failure}\n")
        return 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit deterministic JSON")
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(143))
    return run(json_output=args.json)


if __name__ == "__main__":
    sys.exit(main())
