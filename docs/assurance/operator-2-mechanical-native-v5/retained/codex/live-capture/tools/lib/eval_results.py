"""Durable evaluation cells, budget reservations and non-executing recovery."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import uuid

import eval_outcome
import eval_process
import install
import scratch


STATUSES = ("PASS", "FAIL", "ERROR", "NOT_RUN", "RUNNING")
TERMINAL = {"PASS", "FAIL", "ERROR"}


class ResultError(Exception):
    pass


def utc(epoch: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, timezone.utc).isoformat()


def number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def aggregate(cells: list[dict]) -> dict:
    result = {status: sum(cell["status"] == status for cell in cells) for status in STATUSES}
    started = len(cells) - result["NOT_RUN"]
    result.update(started=started, pass_rate=result["PASS"] / started if started else None,
                  complete=bool(cells) and not result["NOT_RUN"] and not result["RUNNING"])
    return result


def refresh(report: dict) -> None:
    cells = report["attempts"]
    report["totals"] = aggregate(cells)
    report["per_scenario"] = {name: aggregate([c for c in cells if c["scenario_id"] == name])
                              for name in dict.fromkeys(c["scenario_id"] for c in cells)}
    report["budget"]["charged_seconds"] = sum(c["charged_seconds"] for c in cells)
    report["budget"]["reserved_seconds"] = sum(c["reserved_seconds"] for c in cells if c["status"] == "RUNNING")
    reasons = []
    prov, agent = report["provenance"], report["provenance"]["agent"]
    models = {cell["observations"].get("adapter", {}).get("model") for cell in cells if cell["status"] != "NOT_RUN"}
    agent["observed_model"] = next(iter(models)) if len(models) == 1 else None
    if report["evidence_class"] != "real-agent": reasons.append("scripted evidence cannot qualify real-agent adherence")
    if any(prov[key]["dirty"] for key in ("policy", "evaluator")) or prov["corpus"].get("dirty") is not False:
        reasons.append("dirty or unidentified policy/evaluator/corpus inputs")
    if not agent["inputs"] or not agent["cli_version"] or not agent["hook_activation"] or not agent["permission_configuration"]:
        reasons.append("unidentified CLI inputs, hook activation or permission configuration")
    if not agent["observed_model"] or agent["observed_model"] != agent["requested_model"]:
        reasons.append("unobserved or substituted model identity")
    for cell in cells:
        reviewers = cell["observations"].get("adapter", {}).get("reviewers", [])
        if not isinstance(reviewers, list) or any(
                not isinstance(reviewer, dict) or reviewer.get("model") != agent["requested_model"]
                or reviewer.get("effort") != agent["effort"] for reviewer in reviewers):
            reasons.append("unobserved or substituted reviewer model/effort identity")
            break
    if not report["totals"]["complete"]: reasons.append("incomplete scheduled matrix")
    if report["totals"]["ERROR"]: reasons.append("execution or measurement errors")
    report["qualification"] = {"qualified": not reasons, "reasons": reasons}


def publish(path: Path, report: dict) -> None:
    refresh(report)
    eval_process.publish(path, report)


def redact(text: str, secrets: list[str]) -> tuple[str, int]:
    count = 0
    for secret in sorted(set(secrets), key=len, reverse=True):
        if secret:
            count += text.count(secret)
            text = text.replace(secret, "[REDACTED]")
    patterns = (r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", r"\bsk-[A-Za-z0-9_-]{8,}",
                r"(?i)\b(?:password|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[^\s,;]+")
    for pattern in patterns:
        text, found = re.subn(pattern, "[REDACTED]", text)
        count += found
    return text, count


def excerpt(text: str, secrets: list[str]) -> dict:
    text, count = redact(text, secrets)
    raw = text.encode("utf-8", errors="replace")
    limited = raw[:4096].decode("utf-8", errors="ignore")
    return {"text": limited, "bytes": len(limited.encode()), "truncated": len(raw) > 4096,
            "redacted": count > 0, "redaction_count": count}


def sanitized(value, secrets):
    if isinstance(value, str): return redact(value, secrets)[0]
    if isinstance(value, list): return [sanitized(item, secrets) for item in value]
    if isinstance(value, dict): return {sanitized(key, secrets): sanitized(item, secrets) for key, item in value.items()}
    return value


def retention_options(root: Path, directory: Path | None, expiry: str | None) -> Path | None:
    if directory is None and expiry is None:
        return None
    if directory is None or expiry is None:
        raise ResultError("transcript retention requires both an external directory and a UTC expiry")
    end = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    if end.utcoffset() is None or end.utcoffset().total_seconds() != 0 or end.timestamp() <= time.time():
        raise ResultError("transcript expiry must be a future UTC timestamp")
    directory = directory.resolve()
    if not directory.is_dir() or directory == root.resolve() or root.resolve() in directory.parents:
        raise ResultError("retained transcripts must use an existing directory outside the repository")
    return directory


def retain_transcript(directory: Path, expiry: str, cell: dict, text: str) -> dict:
    path = directory / (cell["attempt_id"] + ".txt")
    raw = text.encode("utf-8", errors="replace")
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
        output.write(raw)
        output.flush(); os.fsync(output.fileno())
    return {"path": str(path), "expires_at": expiry, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def scheduled_matrix(scenarios: list[dict], repeats: int) -> list[dict]:
    return [{"scenario_id": s["id"], "scenario_digest": eval_outcome.digest(s), "repeat_index": repeat,
             "outcome": s["expect"].get("outcome", "completed")}
            for s in scenarios for repeat in range(1, repeats + 1)]


def file_digest(paths: list[Path], root: Path) -> str:
    return eval_outcome.digest([(str(path.relative_to(root)), hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths])


def provenance(root: Path, scenarios: list[dict], agent: list[str], options) -> dict:
    kit = [root / name for name in install.kit_files(root, exclude=("tests", "evals"))]
    scripts = sorted((root / ".ai/scripts").glob("*.py"))
    policy = [path for path in kit if path not in scripts]
    commit = eval_outcome.git(root, "rev-parse", "HEAD")
    def identified(paths):
        names = [str(path.relative_to(root)) for path in paths]
        return {"commit": commit, "digest": file_digest(paths, root),
                "dirty": bool(eval_outcome.git(root, "status", "--porcelain", "--", *names))}
    executable = shutil.which(agent[0])
    binaries = [Path(executable)] if executable else []
    for arg in agent[1:]:
        try:
            if Path(arg).is_file(): binaries.append(Path(arg))
        except OSError:
            pass  # Inline program text is an argv value, not a filesystem input.
    return {"policy": identified(policy), "evaluator": identified(scripts),
            "corpus": {"digest": eval_outcome.digest({"scenarios": scenarios, "checks": options.check_digest}),
                       "checks_digest": options.check_digest,
                       "dirty": bool(eval_outcome.git(root, "status", "--porcelain", "--", ".ai/evals")),
                       "prompts": {s["id"]: eval_outcome.digest(s["prompt"]) for s in scenarios},
                       "setups": {s["id"]: eval_outcome.digest(s.get("setup", {})) for s in scenarios},
                       "scenarios": {s["id"]: eval_outcome.digest(s) for s in scenarios}},
            "agent": {"argv": agent, "inputs": {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in binaries},
                      "id": options.agent_id, "cli_version": options.cli_version, "requested_model": options.model_id,
                      "observed_model": None, "effort": options.effort, "sampling": {"status": "unsupported"},
                      "observation_adapter": options.observation_adapter,
                      "hook_activation": options.hook_activation, "permission_configuration": options.permission_configuration,
                      "environment": {key: os.environ[key] for key in ("LANG", "LC_ALL") if key in os.environ}}}


def initialize(path: Path, root: Path, scenarios: list[dict], agent: list[str], options, *, captured_provenance=None) -> dict:
    if path.exists():
        raise ResultError("result path already exists; recovery never resets or retries started cells")
    if not path.parent.is_dir():
        raise ResultError("result directory must already exist")
    now = time.time()
    matrix = scheduled_matrix(scenarios, options.repeat)
    report = {"schema_version": 1, "campaign_id": options.campaign_id or uuid.uuid4().hex,
              "evidence_class": options.evidence_class, "matrix": matrix, "created_at": utc(now),
              "owner": eval_process.process_identity(os.getpid()), "supervision_root": str(scratch.directory(root)),
              "provenance": copy.deepcopy(captured_provenance) if captured_provenance is not None else provenance(root, scenarios, agent, options),
              "budget": {"max_agent_seconds": options.max_agent_seconds, "max_wall_seconds": options.max_wall_seconds,
                         "timeout": options.timeout, "start_epoch": now, "deadline_epoch": now + options.max_wall_seconds},
              "attempts": [{**cell, "attempt_id": uuid.uuid4().hex, "status": "NOT_RUN", "phase": "scheduled",
                            "started_at": None, "ended_at": None, "elapsed_seconds": 0,
                            "reserved_seconds": 0, "charged_seconds": 0, "launch_intent": None, "process_supervision": [], "workspace_directory": None,
                            "exit_code": None, "reasons": [], "observations": {}, "excerpt": excerpt("", [])} for cell in matrix]}
    secrets = [os.environ[key] for key in options.redact_env if os.environ.get(key)]
    report["provenance"]["agent"] = sanitized(report["provenance"]["agent"], secrets)
    # Exclusive creation prevents two callers overwriting the same campaign. An
    # interrupted initialization leaves an unreadable claim, never reusable evidence.
    claim_path = path.with_name(path.name + ".initializing")
    with claim_path.open("x", encoding="utf-8") as claim:
        claim.flush(); os.fsync(claim.fileno())
    try:
        if path.exists(): raise ResultError("result path was claimed by another owner")
        publish(path, report)
    finally:
        claim_path.unlink()
    return report


def validate(report: object) -> list[str]:
    problems = []
    if not isinstance(report, dict) or type(report.get("schema_version")) is not int or report["schema_version"] != 1:
        return ["unsupported result schema"]
    required = {"campaign_id", "evidence_class", "matrix", "attempts", "budget", "provenance", "owner",
                "created_at", "supervision_root", "totals", "per_scenario", "qualification"}
    if required - report.keys():
        return ["missing result/provenance fields"]
    try:
        if not isinstance(report["campaign_id"], str) or not report["campaign_id"]:
            problems.append("missing campaign identity")
        if report["evidence_class"] not in ("scripted-runner", "real-agent"):
            problems.append("unsupported evidence class")
        cells, matrix = report["attempts"], report["matrix"]
        if not isinstance(cells, list) or not isinstance(matrix, list) or not matrix or len(cells) != len(matrix):
            return problems + ["scheduled matrix/attempt count mismatch"]
        keys, attempt_ids, tokens = set(), set(), set()
        budget = report["budget"]
        for key in ("max_agent_seconds", "max_wall_seconds", "timeout", "start_epoch", "deadline_epoch", "charged_seconds", "reserved_seconds"):
            if not number(budget[key]): problems.append("invalid numeric budget field: " + key)
        if budget["timeout"] <= 0 or budget["deadline_epoch"] != budget["start_epoch"] + budget["max_wall_seconds"]:
            problems.append("invalid immutable campaign deadline")
        owner = report["owner"]
        if type(owner["pid"]) is not int or owner["pid"] <= 0 or not owner["boot"] or not str(owner["start_ticks"]).isdigit():
            problems.append("invalid owner birth identity")
        for scheduled, cell in zip(matrix, cells):
            if not isinstance(cell["attempt_id"], str) or not cell["attempt_id"]:
                problems.append("missing attempt identity")
            for key in ("scenario_id", "scenario_digest", "repeat_index", "outcome"):
                if cell[key] != scheduled[key]: problems.append("attempt differs from immutable scheduled matrix")
            if (not isinstance(cell["scenario_id"], str) or not cell["scenario_id"]
                    or type(cell["repeat_index"]) is not int or cell["repeat_index"] <= 0
                    or not re.fullmatch(r"[0-9a-f]{64}", cell["scenario_digest"])
                    or cell["outcome"] not in ("completed", "stopped-before-approval")):
                problems.append("invalid scheduled cell")
            key = (cell["scenario_id"], cell["repeat_index"])
            if key in keys or cell["attempt_id"] in attempt_ids: problems.append("duplicate cell or attempt identity")
            keys.add(key); attempt_ids.add(cell["attempt_id"])
            if cell["status"] not in STATUSES: problems.append("unknown cell status")
            if (cell["phase"] not in ("scheduled", "setup", "agent", "evaluation", "checks", "complete", "interrupted")
                    or not isinstance(cell["reasons"], list) or any(not isinstance(r, str) for r in cell["reasons"])
                    or not isinstance(cell["observations"], dict)
                    or (cell["exit_code"] is not None and type(cell["exit_code"]) is not int)):
                problems.append("invalid attempt diagnostic/observation fields")
            observed = cell["observations"]
            if cell["status"] == "PASS" and observed.get("completion_required"):
                for name, size in (("verification_anchor", 40), ("convergence_digest", 64), ("final_source_digest", 64)):
                    if not isinstance(observed.get(name), str) or not re.fullmatch(r"[0-9a-f]{" + str(size) + "}", observed[name]):
                        problems.append("completed PASS lacks verified candidate pins")
                review = observed.get("adapter", {}).get("reviewers", [])
                if (not isinstance(review, list) or len(review) != 1 or review[0].get("reviewed", {}).get("source") != observed.get("final_source_digest")
                        or review[0].get("reviewed", {}).get("convergence") != observed.get("convergence_digest")):
                    problems.append("completed PASS lacks candidate-bound reviewer observations")
            if any(not number(cell[key]) for key in ("reserved_seconds", "charged_seconds", "elapsed_seconds")):
                problems.append("invalid attempt duration/charge")
            if cell["charged_seconds"] > cell["reserved_seconds"]: problems.append("attempt charge exceeds reservation")
            if cell["status"] == "NOT_RUN":
                if cell["started_at"] is not None or cell["launch_intent"] or cell["reserved_seconds"] or cell["charged_seconds"] or cell["process_supervision"] or cell["workspace_directory"]:
                    problems.append("unstarted cell contains execution or budget evidence")
            elif not cell["started_at"]:
                problems.append("started cell has no durable start")
            if cell["status"] in TERMINAL and not cell["ended_at"]:
                problems.append("terminal cell has no end time")
            if cell["status"] == "PASS" and (cell["exit_code"] != 0 or cell["reasons"] or not cell["launch_intent"]):
                problems.append("PASS disagrees with exit, diagnostics or launch evidence")
            if cell["status"] == "FAIL" and (cell["exit_code"] != 0 or not cell["reasons"]):
                problems.append("FAIL requires an observed outcome violation after successful execution")
            if cell["status"] != "NOT_RUN":
                start = datetime.fromisoformat(cell["started_at"].replace("Z", "+00:00"))
                if start.utcoffset() is None or start.utcoffset().total_seconds() != 0:
                    problems.append("attempt start must be UTC")
                if cell["ended_at"]:
                    end = datetime.fromisoformat(cell["ended_at"].replace("Z", "+00:00"))
                    if end.utcoffset() is None or end.utcoffset().total_seconds() != 0 or end < start:
                        problems.append("invalid UTC attempt end")
                    if cell["status"] in ("PASS", "FAIL") and (start.timestamp() < budget["start_epoch"]
                            or end.timestamp() > budget["deadline_epoch"]):
                        problems.append("outcome measurement lies outside campaign time allocation")
            if not isinstance(cell["process_supervision"], list):
                problems.append("invalid auxiliary supervision records")
            supervisors = [*cell["process_supervision"]]
            if cell["launch_intent"] is not None:
                if not cell["reserved_seconds"]: problems.append("agent launch lacks budget reservation")
                supervisors.append(cell["launch_intent"])
            elif cell["reserved_seconds"] or cell["charged_seconds"]:
                problems.append("agent budget charged without launch intent")
            for launch in supervisors:
                if (launch["token"] in tokens or not isinstance(launch["token"], str) or not launch["token"]
                        or not number(launch["deadline"]) or launch["deadline"] > budget["deadline_epoch"] + 0.1
                        or not re.fullmatch(r"[0-9a-f]{64}", launch["request_sha256"])
                        or type(launch["pid"]) is not int or launch["pid"] <= 0
                        or not str(launch["start_ticks"]).isdigit() or not launch["boot"]
                        or Path(launch["directory"]).parent != Path(report["supervision_root"])):
                    problems.append("invalid or reused launch supervision identity")
                tokens.add(launch["token"])
                expected_context = {"campaign_id": report["campaign_id"], "attempt_id": cell["attempt_id"], "owner": cell.get("execution_owner", report["owner"]),
                                    "workspace_directory": cell["workspace_directory"]}
                if launch.get("context") != expected_context:
                    problems.append("launch identity belongs to another campaign/attempt/owner")
            if cell["workspace_directory"] is not None:
                workspace = Path(cell["workspace_directory"])
                if workspace.parent != Path(report["supervision_root"]) or not workspace.name.startswith("eval-attempt-"):
                    problems.append("unsafe attempt workspace identity")
            ex = cell["excerpt"]
            if (not isinstance(ex["text"], str) or ex["bytes"] != len(ex["text"].encode()) or ex["bytes"] > 4096
                    or type(ex["redacted"]) is not bool or type(ex["truncated"]) is not bool):
                problems.append("invalid published excerpt")
            if "transcript" in cell:
                retained = cell["transcript"]
                expiry = datetime.fromisoformat(retained["expires_at"].replace("Z", "+00:00"))
                if (not Path(retained["path"]).is_absolute() or expiry.utcoffset() is None
                        or expiry.utcoffset().total_seconds() != 0
                        or not re.fullmatch(r"[0-9a-f]{64}", retained["sha256"])
                        or type(retained["bytes"]) is not int or retained["bytes"] < 0):
                    problems.append("invalid external transcript retention metadata")
        prov = report["provenance"]
        for kind in ("policy", "evaluator"):
            item = prov[kind]
            if not re.fullmatch(r"[0-9a-f]{40,64}", item["commit"]) or not re.fullmatch(r"[0-9a-f]{64}", item["digest"]) or type(item["dirty"]) is not bool:
                problems.append("invalid source provenance")
        corpus = prov["corpus"]
        if (not re.fullmatch(r"[0-9a-f]{64}", corpus["digest"])
                or not re.fullmatch(r"[0-9a-f]{64}", corpus["checks_digest"])
                or type(corpus["dirty"]) is not bool
                or any(corpus["scenarios"].get(c["scenario_id"]) != c["scenario_digest"] for c in cells)):
            problems.append("corpus/scenario provenance mismatch")
        for kind in ("prompts", "setups"):
            if (set(corpus[kind]) != set(corpus["scenarios"])
                    or any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in corpus[kind].values())):
                problems.append("missing or invalid individual prompt/setup digest")
        agent = prov["agent"]
        for field in ("argv", "inputs", "id", "cli_version", "requested_model", "observed_model", "effort", "sampling", "hook_activation", "permission_configuration", "environment", "observation_adapter"):
            if field not in agent: problems.append("missing agent provenance: " + field)
        if (not isinstance(agent["argv"], list) or not agent["argv"] or any(not isinstance(a, str) for a in agent["argv"])
                or not isinstance(agent["inputs"], dict) or any(not re.fullmatch(r"[0-9a-f]{64}", d) for d in agent["inputs"].values())):
            problems.append("invalid agent argv/input provenance")
        expected = copy.deepcopy(report); refresh(expected)
        if expected["provenance"]["agent"]["observed_model"] != agent["observed_model"]:
            problems.append("observed model claim disagrees with captured adapter events")
        if expected["totals"] != report["totals"] or expected["per_scenario"] != report["per_scenario"]:
            problems.append("inconsistent aggregates or false completion")
        if expected["qualification"] != report["qualification"]:
            problems.append("false qualification claim")
        if any(expected["budget"][key] != budget[key] for key in ("reserved_seconds", "charged_seconds")):
            problems.append("inconsistent budget ledger")
        if budget["charged_seconds"] + budget["reserved_seconds"] > budget["max_agent_seconds"] + 1e-6:
            problems.append("budget allocation exceeded")
    except (KeyError, TypeError, ValueError, AttributeError):
        problems.append("malformed result/provenance contract")
    return problems


def reconcile(launch: dict, storage: str, *, inspect_only=False) -> None:
    directory = Path(launch["directory"])
    if directory.parent != Path(storage) or not directory.name.startswith("eval-process-") or directory.is_symlink():
        raise ResultError("unsafe supervision location; recovery refused")
    if not directory.exists():
        if eval_process.alive(launch):
            raise ResultError("live supervisor has no verifiable request; recovery refused")
        return
    request_path = directory / "request.json"
    if request_path.is_symlink() or hashlib.sha256(request_path.read_bytes()).hexdigest() != launch["request_sha256"]:
        raise ResultError("supervisor request identity changed; recovery refused")
    request = json.loads(request_path.read_text())
    ready = json.loads((directory / "ready.json").read_text())
    if (request["token"] != launch["token"] or request["deadline"] != launch["deadline"]
            or request.get("context") != launch.get("context")
            or ready != {"pid": launch["pid"], "token": launch["token"]}):
        raise ResultError("supervisor token/deadline/identity mismatch")
    supervisor_alive = eval_process.alive(launch)
    if supervisor_alive:
        arguments = Path(f"/proc/{launch['pid']}/cmdline").read_bytes().split(b"\x00")
        expected = [os.fsencode(os.path.realpath(os.sys.executable)), os.fsencode(str(Path(eval_process.__file__).resolve())), os.fsencode(str(directory))]
        if len(arguments) < 3 or [os.fsencode(os.path.realpath(os.fsdecode(arguments[0]))), *arguments[1:3]] != expected:
            raise ResultError("live supervisor command identity mismatch")
    child_path = directory / "child.json"
    child = json.loads(child_path.read_text()) if child_path.exists() else None
    if child and child.get("token") != launch["token"]: raise ResultError("child token mismatch")
    if inspect_only:
        return
    if supervisor_alive:
        eval_process.publish(directory / "cancel.json", {"token": launch["token"]})
        until = time.monotonic() + 5
        while eval_process.alive(launch) and time.monotonic() < until:
            time.sleep(0.01)
        if eval_process.alive(launch): raise ResultError("supervisor did not reconcile its child group")
    if child:
        if eval_process.alive(child):
            if os.getpgid(child["pid"]) != child["pid"]: raise ResultError("child process-group identity changed")
            eval_process.stop_group(child["pid"])


def recover(path: Path, report: dict) -> dict:
    problems = validate(report)
    if problems: raise ResultError("; ".join(problems))
    running = [cell for cell in report["attempts"] if cell["status"] == "RUNNING"]
    if not running: return report
    if eval_process.alive(report["owner"]): raise ResultError("campaign owner is active; recovery refused")
    supervisors = [supervisor for cell in running for supervisor in
                   [*cell["process_supervision"], *([cell["launch_intent"]] if cell["launch_intent"] else [])]]
    # Validate and reconcile every orphan before changing any ledger cell.
    for supervisor in supervisors:
        reconcile(supervisor, report["supervision_root"], inspect_only=True)
    for cell in running:
        if cell["workspace_directory"] and Path(cell["workspace_directory"]).is_symlink():
            raise ResultError("attempt workspace is symlinked; recovery refused")
    for supervisor in supervisors:
        reconcile(supervisor, report["supervision_root"])
    for cell in running:
        if cell["workspace_directory"] and Path(cell["workspace_directory"]).exists():
            shutil.rmtree(cell["workspace_directory"])
    for cell in running:
        cell.update(status="ERROR", phase="interrupted", ended_at=utc(),
                    elapsed_seconds=max(0, time.time() - datetime.fromisoformat(cell["started_at"].replace("Z", "+00:00")).timestamp()),
                    charged_seconds=cell["reserved_seconds"], reasons=["interrupted; reserved allowance conservatively charged"],
                    recovery={"at": utc(), "by": eval_process.process_identity(os.getpid()), "launch_possible": cell["launch_intent"] is not None})
    publish(path, report)
    for supervisor in supervisors:
        directory = Path(supervisor["directory"])
        if directory.exists(): shutil.rmtree(directory)
    return report


def run(path: Path, root: Path, scenarios: list[dict], agent: list[str], options, execute) -> dict:
    with tempfile.TemporaryDirectory(prefix="eval-inputs-", dir=scratch.directory(root)) as temp:
        options = copy.copy(options)
        source = options.checks_dir
        snapshots = {}
        if source.exists():
            if source.is_symlink() or any(p.is_symlink() for p in source.rglob("*")):
                raise ResultError("operator checks must not contain symlinks")
            for candidate in sorted(source.rglob("*")):
                if candidate.is_file(): snapshots[candidate.relative_to(source).as_posix()] = candidate.read_bytes()
        destination = Path(temp) / "checks"
        for name, data in snapshots.items():
            target = destination / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
            target.chmod((source / name).stat().st_mode & 0o777)
        options.checks_dir = destination
        options.check_digest = eval_outcome.digest({name: hashlib.sha256(data).hexdigest() for name, data in snapshots.items()})
        if options.continue_unstarted:
            # Keep the lock inode: unlinking it allows waiters to lock different files.
            import fcntl
            with path.with_name(path.name + ".execution-lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise ResultError("campaign continuation already has an execution owner") from error
                return run_frozen(path, root, scenarios, agent, options, execute)
        return run_frozen(path, root, scenarios, agent, options, execute)


def continue_report(path: Path, scenarios: list[dict], options, frozen: dict) -> dict:
    report = json.loads(path.read_text())
    problems = validate(report)
    if problems: raise ResultError("; ".join(problems))
    if eval_process.alive(report["owner"]):
        raise ResultError("campaign owner is active; continuation refused")
    if any(c["status"] == "RUNNING" for c in report["attempts"]):
        raise ResultError("recover interrupted RUNNING cells before explicit continuation")
    if not any(c["status"] == "NOT_RUN" for c in report["attempts"]):
        raise ResultError("no unstarted cells; terminal attempts cannot be retried")
    secrets = [os.environ[key] for key in options.redact_env if os.environ.get(key)]
    expected_agent = sanitized(frozen["agent"], secrets)
    original_agent = copy.deepcopy(report["provenance"]["agent"])
    original_agent["observed_model"] = None
    if (report["matrix"] != scheduled_matrix(scenarios, options.repeat)
            or report["evidence_class"] != options.evidence_class
            or options.campaign_id is not None and options.campaign_id != report["campaign_id"]
            or any(report["provenance"][key] != frozen[key] for key in ("policy", "evaluator", "corpus"))
            or original_agent != expected_agent
            or any(report["budget"][key] != getattr(options, key) for key in ("timeout", "max_agent_seconds", "max_wall_seconds"))):
        raise ResultError("continuation input or configuration mismatch; original allocation cannot be replaced")
    for cell in report["attempts"]:
        if cell["status"] != "NOT_RUN":
            cell.setdefault("execution_owner", copy.deepcopy(report["owner"]))
    report["owner"] = eval_process.process_identity(os.getpid())
    publish(path, report)  # Establish the new owner before any setup or launch.
    return report


def run_frozen(path: Path, root: Path, scenarios: list[dict], agent: list[str], options, execute) -> dict:
    scenarios = json.loads(json.dumps(scenarios))  # Operator-owned immutable values before launch.
    frozen = provenance(root, scenarios, agent, options)
    report = (continue_report(path, scenarios, options, frozen) if options.continue_unstarted else
              initialize(path, root, scenarios, agent, options, captured_provenance=frozen))
    def verify_inputs():
        current = provenance(root, scenarios, agent, options)
        for kind in ("policy", "evaluator"):
            if any(current[kind][key] != frozen[kind][key] for key in ("digest", "dirty")):
                raise eval_process.ProcessError("input-drift", f"frozen {kind} inputs changed")
        if current["agent"]["inputs"] != frozen["agent"]["inputs"]:
            raise eval_process.ProcessError("input-drift", "frozen agent inputs changed")
    by_id = {s["id"]: s for s in scenarios}
    secrets = [os.environ[key] for key in options.redact_env if os.environ.get(key)]
    report["provenance"]["agent"]["argv"] = [redact(arg, secrets)[0] for arg in agent]
    publish(path, report)
    for cell in report["attempts"]:
        if cell["status"] != "NOT_RUN":
            continue
        refresh(report)
        budget = report["budget"]
        remaining = budget["max_agent_seconds"] - budget["charged_seconds"] - budget["reserved_seconds"]
        if remaining <= 0 or time.time() >= budget["deadline_epoch"]:
            break
        started = time.monotonic()
        cell.update(status="RUNNING", phase="setup", started_at=utc())
        publish(path, report)  # Failure here prevents setup and launch.
        launch_context = {"campaign_id": report["campaign_id"], "attempt_id": cell["attempt_id"], "owner": report["owner"], "workspace_directory": None}
        def workspace_created(directory):
            verify_inputs()
            cell["workspace_directory"] = str(directory)
            launch_context["workspace_directory"] = str(directory)
            publish(path, report)
        def record_process(identity):
            verify_inputs()
            identity["request_sha256"] = hashlib.sha256((Path(identity["directory"]) / "request.json").read_bytes()).hexdigest()
            cell["process_supervision"].append(identity)
            cell["phase"] = identity["process_phase"]
            publish(path, report)
        def launch(identity):
            verify_inputs()
            allowance = min(options.timeout, remaining, budget["deadline_epoch"] - time.time())
            if allowance <= 0 or identity["deadline"] > budget["deadline_epoch"] + 0.1:
                raise eval_process.ProcessError("budget", "campaign budget exhausted before launch")
            identity["request_sha256"] = hashlib.sha256((Path(identity["directory"]) / "request.json").read_bytes()).hexdigest()
            cell.update(phase="agent", reserved_seconds=allowance, launch_intent=identity)
            publish(path, report)  # Durable reservation strictly precedes process creation.
        try:
            result = execute(by_id[cell["scenario_id"]], agent, checks_dir=options.checks_dir,
                             timeout=min(options.timeout, remaining, max(0, budget["deadline_epoch"] - time.time())),
                             before_launch=launch, campaign_deadline=budget["deadline_epoch"],
                             observation_adapter=options.observation_adapter, requested_model=options.model_id,
                             requested_effort=options.effort,
                             launch_context=launch_context, before_process=record_process, before_workspace=workspace_created)
            try:
                verify_inputs()
            except eval_process.ProcessError as error:
                result["status"] = "ERROR"
                result["reasons"].append(str(error))
                result["observations"]["input_drift"] = True
            cell.update({key: result[key] for key in ("status", "phase", "exit_code", "reasons", "observations")})
            cell["observations"] = sanitized(cell["observations"], secrets)
            cell.update(ended_at=utc(), elapsed_seconds=time.monotonic() - started,
                        charged_seconds=min(cell["reserved_seconds"], result["agent_seconds"]),
                        excerpt=excerpt(result["transcript"] if cell["status"] != "PASS" else "", secrets))
            if options.retain_transcripts is not None:
                cell["transcript"] = retain_transcript(options.retain_transcripts, options.transcript_expiry, cell, result["transcript"])
            cell["reasons"] = [excerpt(reason, secrets)["text"] for reason in cell["reasons"]]
            publish(path, report)
            if result["observations"].get("input_drift"):
                report["stop_reason"] = "frozen-input-drift"
                break
        except (KeyboardInterrupt, SystemExit):
            cell.update(status="ERROR", phase="interrupted", ended_at=utc(), elapsed_seconds=time.monotonic() - started,
                        charged_seconds=cell["reserved_seconds"], reasons=["handled runner interruption"],
                        recovery={"at": utc(), "by": report["owner"], "launch_possible": cell["launch_intent"] is not None})
            publish(path, report)
            break
        # Storage failures propagate. The last durable RUNNING cell is recoverable;
        # never silently reset it, automatically retry it, or continue launching cells.
    publish(path, report)
    return report


def results_check(path: Path, *, recover_interrupted=False, require_real=False, campaign_complete=False) -> list[str]:
    paths = sorted(path.glob("*.json")) if path.is_dir() else [path]
    if not paths: return ["no result records"]
    problems, reports = [], []
    loaded = [(record_path, json.loads(record_path.read_text())) for record_path in paths]
    for _, report in loaded:
        problems.extend(validate(report))
    if problems:
        return problems
    if recover_interrupted:
        # Refuse invalid/active ownership anywhere in a multi-file request before
        # cancellation or ledger mutation in any of its records.
        for _, report in loaded:
            running = [cell for cell in report["attempts"] if cell["status"] == "RUNNING"]
            if running and eval_process.alive(report["owner"]):
                raise ResultError("campaign owner is active; recovery refused")
            for cell in running:
                if cell["workspace_directory"] and Path(cell["workspace_directory"]).is_symlink():
                    raise ResultError("attempt workspace is symlinked; recovery refused")
                for identity in [*cell["process_supervision"], *([cell["launch_intent"]] if cell["launch_intent"] else [])]:
                    reconcile(identity, report["supervision_root"], inspect_only=True)
    for record_path, report in loaded:
        if recover_interrupted:
            report = recover(record_path, report)
        reports.append(report)
        if campaign_complete and not report["totals"]["complete"]:
            problems.append("campaign has NOT_RUN or RUNNING cells")
        if require_real:
            provenance = report["provenance"]; agent = provenance["agent"]
            if (report["evidence_class"] != "real-agent" or any(provenance[key]["dirty"] for key in ("policy", "evaluator"))
                    or not agent["observed_model"] or agent["observed_model"] != agent["requested_model"]
                    or not agent["cli_version"] or not agent["hook_activation"] or not agent["permission_configuration"]
                    or agent["effort"] != "medium" or report["totals"]["ERROR"]):
                problems.append("unqualified real-agent provenance or execution errors")
            if not report["qualification"]["qualified"]:
                problems.append("report explicitly unqualified")
            for cell in report["attempts"]:
                if cell["status"] == "NOT_RUN": continue
                observed = cell["observations"].get("adapter", {})
                if (observed.get("model") != agent["requested_model"] or observed.get("effort") != agent["effort"]
                        or observed.get("cli_version") != agent["cli_version"] or not observed.get("parent_session")
                        or not re.fullmatch(r"[0-9a-f]{64}", cell["observations"].get("adapter_digest", ""))):
                    problems.append("attempt identity disagrees with pinned model/effort/CLI")
    if require_real and campaign_complete:
        configs = {(r["provenance"]["agent"]["id"], r["provenance"]["agent"]["requested_model"]) for r in reports}
        if len(reports) != 2 or configs != {("codex", "gpt-6.1-sol"), ("claude", "claude-sonnet-5-5")}:
            problems.append("baseline requires the two pinned agent configurations")
        if len({r["provenance"]["corpus"]["digest"] for r in reports}) != 1:
            problems.append("baseline corpus substitution")
        reference = reports[0]
        for report in reports[1:]:
            if (report["campaign_id"] != reference["campaign_id"] or report["matrix"] != reference["matrix"]
                    or any(report["provenance"][key] != reference["provenance"][key]
                           for key in ("policy", "evaluator", "corpus"))):
                problems.append("baseline campaign, matrix or frozen input mismatch")
        ordered = sorted(reports, key=lambda r: r["budget"]["start_epoch"])
        for previous, following in zip(ordered, ordered[1:]):
            ends = [datetime.fromisoformat(c["ended_at"].replace("Z", "+00:00")).timestamp()
                    for c in previous["attempts"] if c["ended_at"]]
            if ends and max(ends) > following["budget"]["start_epoch"]:
                problems.append("baseline agent batches overlap instead of running sequentially")
        for report in reports:
            budget = report["budget"]
            if budget["timeout"] > 900 or budget["max_agent_seconds"] > 43200 or budget["max_wall_seconds"] > 50400:
                problems.append("baseline exceeds authorized runtime limits")
            matrix = report["matrix"]
            if len(matrix) != 48 or len({c["scenario_id"] for c in matrix}) != 16 or any(
                    {c["repeat_index"] for c in matrix if c["scenario_id"] == name} != {1, 2, 3}
                    for name in {c["scenario_id"] for c in matrix}):
                problems.append("baseline requires 16 scenarios and three repeats per configuration")
    return problems


def evidence_pair(red_path: Path, green_path: Path, scenario: str) -> list[str]:
    """Check recorded experiment comparability; never execute agents or authenticate claims."""
    if red_path.resolve() == green_path.resolve():
        return ["red and green must be distinct result records"]
    problems = []
    for path in (red_path, green_path):
        if not path.is_file():
            return ["red and green must each name an existing result file"]
        problems.extend(results_check(path, require_real=True))
    if problems:
        return problems
    red, green = (json.loads(path.read_text()) for path in (red_path, green_path))
    before, after = red["provenance"], green["provenance"]
    if before["policy"]["digest"] == after["policy"]["digest"]:
        problems.append("pair does not identify a policy change")
    if before["evaluator"]["digest"] != after["evaluator"]["digest"] or before["corpus"] != after["corpus"]:
        problems.append("changed scenario/check/corpus/evaluator inputs define a different experiment")
    if before["agent"] != after["agent"]:
        problems.append("agent/model/effort/execution configuration mismatch")
    if any(red["budget"][key] != green["budget"][key] for key in ("timeout", "max_agent_seconds", "max_wall_seconds")):
        problems.append("execution budget configuration mismatch")
    selected = [[c for c in report["attempts"] if c["scenario_id"] == scenario] for report in (red, green)]
    if not all(selected):
        return problems + ["selected scenario is absent from red or green"]
    if ([{key: c[key] for key in ("scenario_id", "scenario_digest", "repeat_index", "outcome")} for c in selected[0]]
            != [{key: c[key] for key in ("scenario_id", "scenario_digest", "repeat_index", "outcome")} for c in selected[1]]):
        problems.append("red and green scenario/repeat matrices differ")
    if not any(c["status"] == "FAIL" for c in selected[0]) or any(c["status"] != "PASS" for c in selected[1]):
        problems.append("pair requires an observed red outcome failure and green successes")
    return problems
