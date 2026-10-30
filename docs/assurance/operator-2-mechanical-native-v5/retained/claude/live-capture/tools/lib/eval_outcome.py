"""Frozen, non-executing completion checks for lifecycle evaluations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import sys

import lifecycle


class MeasurementError(Exception):
    """The adapter cannot measure the required observation."""


def fixture_command(scenario_id: str, root: Path) -> list[str] | None:
    """Independent probes for the six inherited fixtures; no pressure corpus is authored."""
    if scenario_id == "feature-l2":
        return [sys.executable, str(root / "cli.py"), "--json"]
    probes = {
        "typo-l0": "from pathlib import Path; text=Path('app.py').read_text(); assert 'recieve' not in text and 'receive' in text",
        "bugfix-l1": "from calc import add; assert add(2,3)==5 and add(-2,3)==1 and add(0,0)==0",
        "escalation-l2": "import api,__init__ as exported; assert callable(api.get) and exported.get('a')==1",
        "user-tier-held": "from util import greet; assert greet('Ada')=='Hello, Ada'",
    }
    code = probes.get(scenario_id)
    if code is None:
        return None
    # The check's bounded pipe and independent deadline own this whole group.
    return [sys.executable, "-c", "import os,sys; os.chdir(sys.argv[1]); sys.path.insert(0,sys.argv[1]); " + code, str(root)]


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, check=True, timeout=60).stdout.strip()


def safe_ref(root: Path, ref: object) -> Path:
    if not isinstance(ref, str) or not ref or Path(ref).is_absolute() or ".." in Path(ref).parts:
        raise ValueError("artifact reference must stay inside the evaluation repository")
    target = (root / ref).resolve()
    if root.resolve() not in target.parents or ".git" in target.relative_to(root.resolve()).parts:
        raise ValueError("artifact reference escapes the evaluation repository")
    return target


def tree_at(root: Path, head: str) -> str:
    """Reproduce lifecycle.tree_hash with an ancestor HEAD and final source bytes."""
    names = set(git(root, "ls-files", "-m", "-o", "--exclude-standard").splitlines())
    names.update(git(root, "diff", "--name-only", head).splitlines())
    result = hashlib.sha256(head.encode())
    for name in sorted(names):
        if lifecycle.exempt(name):
            continue
        result.update(name.encode())
        try:
            result.update((root / name).read_bytes())
        except OSError:
            result.update(b"<missing>")
    return result.hexdigest()


def source_digest(root: Path) -> str:
    names = set(git(root, "ls-files", "--cached", "--others", "--exclude-standard").splitlines())
    result = hashlib.sha256()
    for name in sorted(names):
        if lifecycle.exempt(name):
            continue
        result.update(name.encode()); result.update(b"\x00")
        try:
            result.update((root / name).read_bytes())
        except OSError:
            result.update(b"<missing>")
        result.update(b"\x00")
    return result.hexdigest()


def candidate_pins(root: Path, state: dict) -> dict:
    stages = state.get("stages", {})
    return {"source": source_digest(root), "spec": stages.get("intent", {}).get("sha256"),
            "plan": stages.get("plan", {}).get("sha256"), "convergence": digest(state.get("converge"))}


def requires_completion(scenario: dict, state: dict) -> bool:
    expect = scenario["expect"]
    if state.get("tier") not in ("L2", "L3") or expect.get("outcome") == "stopped-before-approval":
        return False
    # Preserve the inherited queue-only case by its declared outcome, not its ID.
    queue_only = (state["tier"] == "L3" and expect.get("queue_entries", 0) > 0
                  and set(expect.get("stages", [])) <= {"intent"} and "outcome" not in expect)
    return (state["tier"] == "L2" or bool(state.get("stages", {}).get("intent", {}).get("ref"))) and not queue_only


def comparable(record: dict) -> dict:
    return {"task": record.get("task"), "tier": record.get("tier"), "converge": record.get("converge"), "merge": record.get("merge"),
            "stages": {key: value for key, value in record.get("stages", {}).items() if key != "ship"}}


def audit_view(root: Path, state: dict) -> list[str]:
    for entry in state.get("stages", {}).values():
        if entry.get("ref"):
            safe_ref(root, entry["ref"])
    return lifecycle.audit_problems(root, lifecycle.public(state, root))


def publishing_audit(root: Path, commit: str, state: dict) -> list[str]:
    name = lifecycle.record_path(root, state).relative_to(root).as_posix()
    try:
        record = json.loads(git(root, "show", f"{commit}:{name}"))
        if not isinstance(record, dict) or comparable(record) != comparable(state):
            return ["publishing commit has inconsistent Verify/task/convergence evidence"]
        # Materialize only artifact bytes for the frozen audit. Never import or execute
        # code from a historical/agent-writable checkout.
        with tempfile.TemporaryDirectory(dir=root.parent) as temp:
            view = Path(temp)
            for entry in record["stages"].values():
                if entry.get("ref"):
                    target = safe_ref(view, entry["ref"])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    data = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{entry['ref']}"],
                                          stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=60).stdout
                    target.write_bytes(data)
            return ["publishing commit audit: " + problem for problem in lifecycle.audit_problems(view, record)]
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
        return ["publishing commit lacks a valid matching Verify record and artifacts"]


def review_problems(root: Path, state: dict, observation: dict | None) -> list[str]:
    if not isinstance(observation, dict) or observation.get("review_visibility") is not True:
        raise MeasurementError("adapter cannot expose independent-review session/candidate metadata")
    if any(not isinstance(observation.get(key), str) or not observation[key] for key in ("parent_session", "model", "effort")):
        raise MeasurementError("adapter omitted parent session/model/effort identity")
    reviewers = observation.get("reviewers")
    if not isinstance(reviewers, list):
        raise MeasurementError("adapter omitted reviewer observations")
    if len(reviewers) != 1:
        return ["completion requires exactly one observed independent reviewer session"]
    reviewer = reviewers[0]
    required = {"session", "parent_session", "model", "effort", "role", "read_only", "tool_restrictions",
                "converge_sequence", "delegated_sequence", "completed_sequence", "verify_sequence",
                "writes", "before", "after", "reviewed", "report_sha256", "verdict"}
    if not isinstance(reviewer, dict) or required - reviewer.keys():
        raise MeasurementError("adapter omitted reviewer identity/candidate/tool observations")
    failures = []
    if (not isinstance(reviewer["session"], str) or not reviewer["session"]
            or reviewer["session"] == observation["parent_session"]
            or reviewer["parent_session"] != observation["parent_session"]):
        failures.append("reviewer is not a distinct child session of the observed parent")
    if (reviewer["model"] != observation["model"] or reviewer["effort"] != observation["effort"]
            or observation["effort"] != "medium"):
        raise MeasurementError("reviewer model/effort does not match the pinned parent configuration")
    if (reviewer["role"] != "reviewer" or reviewer["read_only"] is not True
            or not isinstance(reviewer["tool_restrictions"], list) or not reviewer["tool_restrictions"]):
        failures.append("reviewer lacks the observed read-only role/tool restrictions")
    sequence = [reviewer[key] for key in ("converge_sequence", "delegated_sequence", "completed_sequence", "verify_sequence")]
    if any(type(item) is not int for item in sequence) or any(a >= b for a, b in zip(sequence, sequence[1:])):
        failures.append("review must follow convergence and complete before Verify")
    pins = candidate_pins(root, state)
    if any(reviewer[key] != pins for key in ("before", "after", "reviewed")) or reviewer["writes"] != []:
        failures.append("review candidate mismatch, source mutation or observed reviewer writes")
    if (reviewer["report_sha256"] != state["stages"].get("review", {}).get("sha256")
            or reviewer["verdict"] != "Approved"):
        failures.append("Approved review artifact is not bound to the observed reviewer result")
    return failures


def completion(root: Path, base: str, state: dict, observation: dict | None) -> tuple[list[str], dict]:
    failures, details = [], {}
    try:
        failures.extend("audit: " + problem for problem in audit_view(root, state))
        stages = state["stages"]
        for stage in ("intent", "plan", "review", "verify"):
            if not lifecycle.complete(state, stage):
                failures.append(f"completion requires {stage}")
        task = state.get("task")
        if not isinstance(task, str) or not re.fullmatch(r"[\w.-]+", task):
            return failures + ["invalid task audit identity"], details
        record = lifecycle.record_path(root, state)
        if not record.is_file() or comparable(json.loads(record.read_text())) != comparable(state):
            failures.append("durable audit record disagrees with final task state")
        run = state.get("converge")
        spec = stages.get("intent", {}).get("ref")
        if not isinstance(run, dict) or run.get("spec") != spec:
            return failures + ["missing convergence for the approved spec"], details
        if run.get("spec_sha256") != stages["intent"].get("sha256"):
            failures.append("convergence spec hash disagrees with approved intent")
        model = lifecycle.spec_model(safe_ref(root, spec))
        results = run.get("results")
        ids = [r.get("id") for r in results if isinstance(r, dict)] if isinstance(results, list) else []
        if (len(ids) != len(set(ids)) or set(ids) != set(model["requirements"])
                or not isinstance(results, list) or len(ids) != len(results)):
            failures.append("convergence must cover every requirement exactly once")
        elif results:
            review_ref = stages.get("review", {}).get("ref")
            reviewed = ""
            if review_ref:
                report = safe_ref(root, review_ref)
                reviewed = "\n".join(lifecycle.find_section(lifecycle.sections(report.read_text()), "validation reviewed") or [])
            for result in results:
                command = lifecycle.BACKTICK.search(model["acceptance"].get(result["id"], ""))
                if command:
                    if result.get("status") != "PASS" or result.get("exit") != 0 or result.get("cmd") != command.group(1):
                        failures.append("convergence has a failed or inconsistent executed requirement")
                elif (result.get("status") != "MANUAL" or result.get("cmd") is not None
                      or not re.search(rf"(?<![\w-]){re.escape(result['id'])}(?![\w-])", reviewed)):
                    failures.append("manual convergence requirement lacks reviewed evidence")
        git(root, "merge-base", "--is-ancestor", base, "HEAD")
        ancestors = [base, *git(root, "rev-list", "--reverse", "--ancestry-path", f"{base}..HEAD").splitlines()]
        anchors = [head for head in ancestors if tree_at(root, head) == run.get("tree")]
        if len(anchors) != 1:
            failures.append("verification anchor is missing or ambiguous for final source")
        else:
            anchor = anchors[0]
            details.update(verification_anchor=anchor, convergence_digest=digest(run), final_source_digest=source_digest(root))
            following = git(root, "rev-list", "--reverse", "--ancestry-path", f"{anchor}..HEAD").splitlines()
            if following:
                failures.extend(publishing_audit(root, following[0], state))
        merge = lifecycle.merge_problem(root, state)
        if merge:
            failures.append(merge)
        if failures:
            return failures, details
        failures.extend(review_problems(root, state, observation))
    except (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        failures.append(f"invalid completion evidence: {error}")
    return failures, details
