#!/usr/bin/env python3
"""Run autonomous work as fresh agent sessions, one bounded integrated batch (or batch round) each.

Each session starts a new agent process with an empty context and the ``okf.py handoff --prompt``
text as its only input, so context never accumulates across batches. The agent selects related
requirements, schedules independent work and deduplicates full validation at the integrated gate;
the driver does not change queue readiness or schedule tasks. The agent ends its session
after a safe checkpoint; the driver then decides whether another session is needed.

    python3 .ai/scripts/autonomy_driver.py [--role solo|orchestrator] [--max-sessions N]
                                           [--max-idle N] -- AGENT_COMMAND [ARGS...]

The prompt is appended as the agent command's last argument, for example:

    ... --progress-file target/autonomy/run-1.jsonl --chat-ack-file target/autonomy/run-1.ack.json -- cursor-agent -p --output-format stream-json --force --trust
    ... --progress-file ... --chat-ack-file ... -- claude -p --output-format stream-json --verbose --permission-mode acceptEdits
    ... --progress-file ... --chat-ack-file ... -- codex exec --json --sandbox workspace-write
    ... --headless -- claude -p --permission-mode acceptEdits  # only when the user explicitly selects headless

Before every session it runs ``pr_sync.py``, which merges each base branch into the agents' open
PRs so they stay mergeable. PRs with real conflicts become the session's first job. Without a
working ``gh``, it stops rather than let PRs drift into conflict; ``--no-pr-sync`` opts out.

Session expiry requests a checkpoint before forced termination. One bounded recovery may
preserve interrupted work before replacement; every launch shares the original run budget.
Stops with exit 0 when no task is READY or IN_PROGRESS, no agent PR has conflicts, and the
checkpoint is safe. Unrecoverable failures, lost supervision and exhausted limits exit 1.
Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import math
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.dont_write_bytecode = True  # A __pycache__ beside okf.py would make the work tree, and so the checkpoint, unclean.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import okf  # noqa: E402
import pr_sync  # noqa: E402
import timed_check  # noqa: E402
import autonomy_progress  # noqa: E402
import autonomy_validation  # noqa: E402
import scratch  # noqa: E402

MAX_STALLED_CAP = 4  # Raising the stall limit does not make a batch converge; split it instead (§9.2).


def conflict_brief(conflicts: list[pr_sync.Result]) -> str:
    """Prompt lines that make conflicted agent PRs the session's first job."""
    lines = ["Before any other work, make these pull requests mergeable again. In each, merge the base into the branch"]
    lines.append("(never rebase or force-push), resolve conflicts with focused checks, and integrate each repair batch.")
    lines.append("Run the union of required full Validation commands once per integrated batch, deduplicated across members;")
    lines.append("record exact outcomes and the integrated commit, and rerun affected validation after changes invalidate that evidence.")
    lines.append("Push, reopen invalidated requirement checkboxes, and keep the milestone PR draft until its entire scope passes review, validation and exit criteria:")
    lines += [f"- {result.line()}" for result in conflicts]
    return "\n".join(lines)


def pending_work(bundle: Path, conflicts: list[pr_sync.Result] | None = None) -> str | None:
    """Why another session is needed, or None when nothing is actionable."""
    if conflicts:
        return "PR conflicts: " + ", ".join(f"#{r.number}" for r in conflicts)
    _, tasks = okf._load_queue(bundle)
    if not tasks:
        return "queue is empty: bootstrap it"
    states = okf.effective_states(tasks)
    active = [task.id for task in tasks if states[task.id] == "IN_PROGRESS" and not task.get("Hold")]
    if active:
        return "in progress: " + ", ".join(active[:3])
    ready = okf.next_tasks(tasks)
    if ready:
        return "READY: " + ", ".join(task.id for task in ready[:3])
    unsafe = [check for check in okf.checkpoint(bundle) if not check.ok]
    if unsafe:
        return "unsafe checkpoint: " + "; ".join(f"{c.name}: {c.detail}" for c in unsafe)
    return None


def progress_marker(bundle: Path) -> tuple[str | None, str]:
    """HEAD and the status checkpoint's content: a session that changes neither made no progress."""
    status = bundle / okf.STATUS_DOC
    digest = hashlib.sha256(status.read_bytes()).hexdigest() if status.is_file() else ""
    return okf._git_text(bundle.parent, "rev-parse", "HEAD"), digest


def delivery_marker(bundle: Path) -> set[str]:
    """Commits and status edits alone do not constitute delivered requirements."""
    _, tasks = okf._load_queue(bundle)
    return {task.id for task in tasks if task.state == "DONE" and task.get("Evidence")}


def remaining_summary(bundle: Path) -> str:
    _, tasks = okf._load_queue(bundle)
    states = okf.effective_states(tasks)
    remaining = [tid for tid, state in states.items() if state not in ("DONE", "CANCELLED")]
    active = [tid for tid, state in states.items() if state == "IN_PROGRESS"]
    safe = all(check.ok for check in okf.checkpoint(bundle))
    return (f"{len(remaining)} tasks remaining; active: {', '.join(active[:5]) or 'none'}; "
            f"checkpoint {'SAFE' if safe else 'UNSAFE'}. Acceptance remains unchanged.")


def closure_released(bundle: Path, registry: Path, receipt: Path) -> bool:
    """SAFE is not worker release; require explicit closure attestation on this HEAD.

    External worktrees have no executable lifecycle receipt yet, so a closure that
    dispatches one still needs normal ownership recovery after interruption.
    """
    try:
        workers = json.loads(registry.read_text())
        release = json.loads(receipt.read_text())
        return (isinstance(workers, dict) and isinstance(release, dict)
                and set(workers) == {str(bundle.parent.resolve())}
                and release.get("head") == okf._git_text(bundle.parent, "rev-parse", "HEAD")
                and release.get("external_workers_released") is True)
    except (OSError, ValueError, AttributeError):
        return False


@contextmanager
def documentation_audit(bundle: Path, directory: Path, report, *, command: list[str] | None = None):
    """Owned read-only diagnostic; never blocks dispatch or certifies a changing candidate."""
    log_path, result_path = directory / "documentation-audit.log", directory / "documentation-audit.json"
    process = None
    announced = False
    result = {"advisory": True, "state": "RUNNING", "log": str(log_path)}
    with log_path.open("x") as log:
        try:
            try:
                process = subprocess.Popen(command or [sys.executable, str(Path(__file__).with_name("okf.py")), "--bundle", str(bundle),
                                                        "validate", "--strict", "--json"], stdout=log, stderr=subprocess.STDOUT,
                                           cwd=bundle.parent, start_new_session=True)
            except OSError:
                result["state"] = "UNAVAILABLE"
            report("audit", "Read-only document audit runs alongside the worker; findings are deferred to handoff and cannot certify delivery."
                   if process is not None else "Background document audit unavailable; worker may proceed and full handoff audit remains required.")

            def poll():
                nonlocal announced
                if process is not None and process.poll() is not None and not announced:
                    result.update(state="PASS" if process.returncode == 0 else "FAIL", exit_code=process.returncode)
                    autonomy_validation.write_json(result_path, result)
                    report("audit", f"Background document diagnostic {result['state']}; continue owned work, assess findings at handoff: {log_path}")
                    announced = True
            yield poll
        finally:
            if process is not None:
                if process.poll() is None:
                    result["state"] = "CANCELLED"
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                if result["state"] == "RUNNING":
                    result["state"] = "PASS" if process.returncode == 0 else "FAIL"
                result["exit_code"] = process.returncode
            autonomy_validation.write_json(result_path, result)


def drive(bundle: Path, command: list[str], role: str, max_sessions: int, max_idle: int, remote: str | None,
          max_session_seconds: float = 1200, max_run_seconds: float = 3600,
          max_stalled: int = 2, progress: autonomy_progress.Progress | None = None,
          heartbeat_seconds: float = 30, handoff_seconds: float = 180,
          max_discovery_seconds: float = 120, validation_reserve_seconds: float = 60,
          max_closure_seconds: float = 600) -> int:
    idle = 0
    stalled = 0
    recovering = False
    recovery_used = False
    validation_result = None
    latest_result = None
    latest_digest = None
    validation_handoff = False
    runtime = Path(autonomy_validation.git(bundle.parent, "rev-parse", "--path-format=absolute", "--git-path", "okf-autonomy")) / str(uuid.uuid4())
    runtime.mkdir(parents=True)
    scratch_environment = scratch.environment(bundle.parent)
    deadline = time.monotonic() + max_run_seconds

    def report(kind: str, message: str) -> None:
        print(f"driver: {message}", file=sys.stderr, flush=True)
        if progress:
            progress.emit(kind, message)

    scratch_root = Path(scratch_environment["TMPDIR"])
    report("scratch", f"Disk-backed scratch: {scratch_root}; {shutil.disk_usage(scratch_root).free // (1024 ** 3)} GiB available. System /tmp is not used for workflow scratch.")

    for session in range(1, max_sessions + 1):
        if progress:
            progress.check()
        if time.monotonic() >= deadline:
            print("driver: stop: run time limit reached; inspect the checkpoint", file=sys.stderr)
            return 1
        conflicts: list[pr_sync.Result] = []
        if remote is not None and not recovering and validation_result is None:
            try:
                current = okf._git_text(bundle.parent, "rev-parse", "--abbrev-ref", "HEAD")
                milestone = current if current and current.startswith("milestone/m") and current[11:].isdigit() else None
                results = pr_sync.sync(bundle, remote, only_branch=milestone)
            except pr_sync.SyncError as error:
                print(f"driver: stop: PR sync failed: {error} (fix it, or pass --no-pr-sync to run without it)", file=sys.stderr)
                return 1
            for result in results:
                if result.action != "in sync":
                    print(f"driver: pr-sync: {result.line()}", file=sys.stderr)
            conflicts = [result for result in results if result.action == "conflicts"]
        reason = "checkpoint recovery after interrupted session" if recovering else pending_work(bundle, conflicts)
        if reason is None:
            _, tasks = okf._load_queue(bundle)
            held = [task for task in tasks if task.get("Hold")]
            if held:
                report("blocked", "stop: no executable task; execution holds require changed conditions before another model session. "
                       + "; ".join(f"{task.id}: {task.get('Hold')} (resume: {task.get('Unblock')})" for task in held))
            else:
                print("driver: stop: no READY or IN_PROGRESS task, no PR conflicts, and the checkpoint is safe", file=sys.stderr)
            blocked = okf.handoff(bundle).splitlines()
            print("\n".join(line for line in blocked if line.startswith(("Queue:", "Blocked:", "Held:"))), file=sys.stderr)
            return 0
        if not recovering and validation_result is None:
            blocked_by_cap = okf.session_gate(bundle)
            if blocked_by_cap:
                report("blocked", f"stop: {blocked_by_cap}")
                return 1
            counted = okf.record_session(bundle)
            if counted:
                report("session", f"Task {counted[0]} session {counted[1]} of {okf.SESSION_CAP}")
        print(f"driver: session {session}/{max_sessions} ({reason})", file=sys.stderr, flush=True)
        if progress:
            progress.emit("session", f"Session {session}/{max_sessions}: {reason}")
        before = progress_marker(bundle)
        delivered_before = delivery_marker(bundle)
        session_dir = runtime / str(session)
        session_dir.mkdir()
        validation_request = session_dir / "request.json"
        registry = session_dir / "workers.json"
        release_receipt = session_dir / "closure-release.json"
        autonomy_validation.register(registry, bundle.parent, bundle.parent)
        prompt = okf.handoff(bundle, "prompt", role=role)
        closure_only = validation_result is not None and json.loads(validation_result.read_text())["state"] == "PASS"
        validation_followup = validation_result is not None
        if validation_result is None and latest_result is not None:
            prompt += f"\nMost recent managed result retained for repair binding: {latest_result}; preserve its evidence across source checkpoints."
        if validation_result:
            prompt += (f"\nManaged validation results: {validation_result}. Inspect exact candidate, logs and coverage; "
                       "do not rerun unchanged passing commands. A PASS still requires independent evidence review "
                       "before DONE. Failed commands return to implementation with focused repair and affected requalification.")
            if not closure_only:
                prompt += ("\nFor a source-reviewed deterministic repair, add repair={failed_result: the supplied result path, "
                           "regression: first command label, review: retained independent source-review reference} to the next manifest. "
                           "That first command must assert the previously failing regression on the changed candidate; every full-gate "
                           "command must list it in after. The driver runs this check before the gate. A fresh PASS exempts only this "
                           "handoff from the stall counter, without resetting prior stalls or claiming DONE. Records-only changes, "
                           "unchanged retries, timeout/model-backed cases and passing gates awaiting closure do not qualify. "
                           "Reuse the existing acceptance mapping and review context; do not commission another general coverage review.")
        if closure_only:
            prompt += ("\nCLOSURE ONLY: review retained evidence and finalize this batch or report a concrete finding. "
                       "Do not start another batch in this session. Reuse the independent source reviewer's acceptance "
                       "context for result review where independence permits. After a SAFE delivery, verify inherited "
                       "and current worker lifecycle: query/reconcile relevant external writers, never infer release "
                       "from SAFE. Only when no external writer remains for this batch, write JSON to "
                       "OKF_CLOSURE_RELEASE with head=current HEAD and external_workers_released=true, then exit. "
                       "This receipt does not release unrelated ownership or authorize reclaiming its files.")
        validation_result = None
        if recovering:
            prompt += ("\nRECOVERY ONLY: the preceding owned process group has been reaped. Inspect preserved "
                       "diffs, evidence, running tests and worker ownership before reclaiming anything. Query any "
                       "surviving external worker; do not create overlapping owners. Preserve unfinished work, "
                       "record exact heads, completed checks, pending commands, owners and next action in status.md. "
                       "Do not implement new work, rerun expensive suites, mark unfinished tasks DONE or reset "
                       "attempt budgets. Reconcile records and commit a safe resumable checkpoint without "
                       "discarding work. Emit a public remaining-work report, then exit. If ownership cannot be "
                       "resolved safely, report that blocker and exit unsuccessfully.")
        if conflicts:
            prompt += "\n" + conflict_brief(conflicts)
        environment = {**scratch_environment, "OKF_AUTONOMOUS": "1", "OKF_VALIDATION_REQUEST": str(validation_request),
                       "OKF_WORK_REGISTRY": str(registry), "OKF_CLOSURE_RELEASE": str(release_receipt),
                       "OKF_DOCUMENT_AUDIT": str(session_dir / "documentation-audit.json")}
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print("driver: stop: run time limit reached before agent launch", file=sys.stderr)
            return 1
        if not recovering and not closure_only and remaining <= handoff_seconds:
            report("stopped", "stop: only checkpoint reserve remains; no implementation session launched and no records-only round required.")
            return 1
        target = min(max_session_seconds, max_closure_seconds) if closure_only else max_session_seconds
        session_limit = min(handoff_seconds if recovering else target + handoff_seconds, remaining)
        soft_limit = min(target, max(0, remaining - handoff_seconds))
        prompt += (f"\nThis launch has at most {session_limit:.1f} seconds including handoff; the run budget never resets. "
                   "Commits/status edits do not count as delivery. The two-case qualification ceiling applies only "
                   "to failed fresh model-backed qualification cases, not ordinary deterministic CI failures, "
                   "dependency advisories, code-generation drift or infrastructure checks that execute no fresh model-backed case. "
                   "Once a genuine case starts, retain its original failure-class/custody/retry counting even if infrastructure fails. Retain evidence "
                   "and repair deterministic checks within the unchanged run/session/delivery budgets. Genuine "
                   "model-backed cases retain their limits across freezes and sessions; never relabel them to evade a limit. "
                   "When a task has no executable action because of an actual limit or prerequisite, record Hold "
                   "and its concrete Unblock condition (or BLOCKED for external dependencies) before exiting. "
                   "Do not leave prohibited work apparently runnable as IN_PROGRESS or recheck an unchanged blocker in another session.")
        prompt += (f"\nDiscovery progress check after {max_discovery_seconds:g}s without source edits; investigation "
                   "may be useful without edits. Report concrete inspected code, findings and next executable step; "
                   "this check does not retire the worker or justify deferral. Use one compact plan; "
                   "do not wait for another planner to restate a sufficiently specified queue task. Register each "
                   "owned worker worktree BEFORE dispatch using python3 .ai/scripts/autonomy_validation.py "
                   "track-worker --worktree PATH. The driver observes source changes; prose/status edits do not qualify. "
                   "Run focused checks in workers. A session handoff does not require full validation: "
                   "preserve the active IN_PROGRESS batch, focused evidence, deferred full commands and next "
                   "source action, then continue implementation next session. Submit the full integrated gate "
                   "only when planned batch acceptance is implemented and reviewed, or an explicit required "
                   "readiness/qualification boundary is reached. For that gate, commit a SAFE checkpoint with "
                   "validation pending, prepare a JSON plan with requirements and commands (label, argv array, "
                   "positive timeout_seconds, coverage IDs, optional env), then run python3 .ai/scripts/autonomy_validation.py "
                   "submit --plan PATH and EXIT. The driver owns validation outside your session clock, with "
                   "durable per-command results and live supervision. Do not launch full validation as a child "
                   "of this model session. Keep the plan outside tracked files; submit after the final checkpoint commit.")
        prompt += ("\nPrepare the acceptance-to-command mapping and independent source review before validation submission, "
                   "while implementation's focused checks run where ownership allows. Retain that review context "
                   "for the result review; do not reconstruct it in a new planning/documentation round. Submit "
                   "and exit rather than keeping a model waiting for deterministic validation.")
        prompt += ("\nStart from the existing claim/brief. Before dispatch, record only task, owner, worktree and next check; "
                   "do not require a separate authorization log, full batch-plan rewrite, claim commit/push or SAFE "
                   "certification before source work. The launcher progress already records this run. Update persistent "
                   "records only when facts change, and commit them with the next source/integration/handoff boundary.")
        prompt += ("\nStartup handoff checks only actionable queue/Git prerequisites. A read-only document diagnostic "
                   "runs in parallel; do not wait for it or repair unrelated documentation before source work. "
                   "Parallel record preparation/read-only preflights need disjoint file/resource ownership; keep "
                   "Git merges and final tested-candidate mutation serialized. Full OKF checks still gate actual handoff. "
                   "For an unchanged candidate's validation retry, reuse its existing committed checkpoint and "
                   "submit the corrected command environment directly; do not rewrite/commit records or audit "
                   "the whole corpus just to submit. The manifest/result retains exact environment and attempt evidence.")
        prompt += ("\nDo useful work within this session: do not retire merely because investigation has not produced "
                   "an edit, a phase ended, the full batch may not fit, or a timeout ceiling looks large. Validation "
                   "runs incrementally within the actual remaining budget. Resume retained validation with "
                   "autonomy_validation.py submit --resume RESULT_JSON; unchanged PASS receipts are verified and reused. "
                   "A time-budget deferral is not an external blocker or delivery. Do not create a records-only "
                   "commit merely to say work is deferred; unchanged execution facts need no commit.")
        interrupted = False
        requested = False
        try:
            with tempfile.TemporaryDirectory(prefix="okf-handoff-", dir=scratch_root) as control, documentation_audit(bundle, session_dir, report) as audit_poll:
                request = Path(control) / "request.txt"
                environment["OKF_HANDOFF_REQUEST"] = str(request)
                progress_request = Path(control) / "progress.txt"
                environment["OKF_PROGRESS_REQUEST"] = str(progress_request)
                environment["OKF_AUTONOMOUS_RECOVERY"] = "1" if recovering else "0"
                prompt += (f"\nUse disk-backed scratch {scratch_root} for all temporary files, logs, worktrees and builds. "
                           "TMPDIR, TMP and TEMP are already set for you and descendants. Do not use /tmp, /var/tmp "
                           "or /dev/shm, hard-code temporary paths there, or override these variables. "
                           "Keep retained evidence in the supplied Git-metadata paths. Never restart to reset budgets.")
                prompt += (f"\nCheck OKF_HANDOFF_REQUEST ({request}) at tool/wait boundaries. "
                           f"A checkpoint request arrives after {soft_limit:.1f}s; at most {handoff_seconds:.1f}s "
                           "of handoff remains within the run budget. On request, stop new dispatch, query active "
                           "workers for head, current command, completed checks and remaining work. Let healthy "
                           "checks finish within that window; preserve their exact results. Report publicly what "
                           "remains (say unknown rather than invent an ETA), settle ownership, write a SAFE "
                           "checkpoint and exit for a fresh session. A worker ending is a handoff, not a run stop.")
                prompt += (f"\nCheck OKF_PROGRESS_REQUEST ({progress_request}) at tool boundaries. It asks for a "
                           "concrete work report while continuing implementation; it is not a checkpoint/stop request.")
                started = last_heartbeat = time.monotonic()
                source_started = False
                progress_requested = False
                def heartbeat():
                    nonlocal last_heartbeat, requested, source_started, progress_requested
                    if progress:
                        progress.check()
                    audit_poll()
                    now = time.monotonic()
                    if not recovering and not validation_followup and not validation_request.exists() and not source_started:
                        source_started = autonomy_validation.source_work(registry)
                        if not source_started and now - started >= max_discovery_seconds and not progress_requested:
                            progress_requested = True
                            progress_request.write_text("Report inspected source/commands, concrete findings and next executable action. Continue owned work; this is not a handoff or stop request.\n")
                            report("progress_requested", f"Session {session}: no source edits observed yet; concrete progress requested while work continues.")
                    if not recovering and now - started >= soft_limit and not request.exists():
                        requested = True
                        request.write_text("Checkpoint requested: stop dispatch, query workers, report remaining work, settle ownership and exit safely.\n")
                        report("handoff", f"Session {session}: checkpoint requested; allowing bounded handoff. " + remaining_summary(bundle))
                    if progress and now - last_heartbeat >= heartbeat_seconds:
                        progress.emit("heartbeat", f"Session {session} still running; {int(now - (deadline - max_run_seconds))}s elapsed in this run. No new acceptance result implied.")
                        last_heartbeat = now
                result = timed_check.run([*command, prompt], label=f"agent-session-{session}",
                                         cwd=bundle.parent, env=environment, timeout_seconds=session_limit,
                                         on_tick=heartbeat, tick_seconds=min(1, heartbeat_seconds, max_session_seconds / 4, max_discovery_seconds / 4),
                                         on_output=progress.observe if progress else None)
        except subprocess.TimeoutExpired:
            interrupted = True
            report("interrupted", "Handoff deadline exceeded; owned process group stopped and reaped. " + remaining_summary(bundle))
        except OSError as error:
            print(f"driver: stop: cannot run {command[0]!r}: {error}", file=sys.stderr)
            return 1
        unsafe = not all(check.ok for check in okf.checkpoint(bundle))
        delivered = delivery_marker(bundle) - delivered_before
        if delivered:
            idle = 0
            stalled = 0
            validation_handoff = False
        completed_closure = (interrupted and closure_only and not unsafe and bool(delivered)
                             and closure_released(bundle, registry, release_receipt))
        if completed_closure:
            report("delivery", "Interrupted closure already delivered evidenced DONE with a SAFE checkpoint and explicit worker release; no recovery session needed.")
        if ((interrupted and not completed_closure) or unsafe
                or (not interrupted and result.returncode != 0 and progress_marker(bundle) != before)):
            if recovering or recovery_used or time.monotonic() >= deadline:
                report("failure", "stop: recovery/run limit reached; preserved checkpoint requires inspection; no restart.")
                return 1
            if not delivered:
                stalled += 1
            recovering = recovery_used = True
            report("recovery", "Starting one bounded records/ownership recovery session before any replacement; budgets retained.")
            continue
        if not completed_closure and result.returncode != 0:
            print(f"driver: stop: agent command exited {result.returncode}", file=sys.stderr)
            return 1
        if recovering:
            report("recovery", "Recovery session returned. " + remaining_summary(bundle))
            if not all(check.ok for check in okf.checkpoint(bundle)):
                report("failure", "stop: recovery did not produce a safe checkpoint; no replacement launched.")
                return 1
            recovering = False
            if stalled >= max_stalled:
                report("failure", "stop: delivery stall limit retained after recovery; inspect blockers.")
                return 1
            report("replacement", "Safe handoff; next session resumes preserved work with fresh context and unchanged budgets.")
            continue
        if validation_request.exists():
            job = autonomy_validation.plan(json.loads(validation_request.read_text()))
            repair = autonomy_validation.repair_candidate(job, latest_result, latest_digest, bundle.parent)
            if validation_handoff and not (delivery_marker(bundle) - delivered_before):
                stalled += 1
                if stalled >= max_stalled and not repair:
                    report("failure", "stop: repeated validation handoffs without delivery; delivery-stall limit retained (separate from model-backed case limits).")
                    return 1
            last_validation_heartbeat = time.monotonic()
            def validation_tick():
                nonlocal last_validation_heartbeat
                if progress:
                    progress.check()
                now = time.monotonic()
                if now - last_validation_heartbeat >= heartbeat_seconds:
                    report("heartbeat", "Managed validation still running; model session has ended. No new acceptance result implied.")
                    last_validation_heartbeat = now
            report("validation", "SAFE candidate handed to managed validation; agent session is retired and no model waits on tests.")
            validation_result = autonomy_validation.run(validation_request, bundle.parent, deadline,
                                                        validation_reserve_seconds, report, validation_tick,
                                                        tick_seconds=min(1, heartbeat_seconds))
            state = json.loads(validation_result.read_text())["state"]
            latest_result, latest_digest = validation_result, autonomy_validation.digest(validation_result)
            if repair:
                results = json.loads(validation_result.read_text())["commands"]
                regression = next((entry for entry in results if entry["label"] == job["repair"]["regression"]), {})
                if (regression.get("state") == "PASS" and regression.get("exit_code") == 0
                        and not regression.get("reused_from") and state not in ("INVALIDATED", "CANCELLED")):
                    stalled = max(0, stalled - 1)
                    report("repair", "Verified deterministic repair regression PASS on changed source; this handoff is exempt from the stall count. Prior stalls and all budgets remain; full gate and independent closure still required.")
                elif stalled >= max_stalled:
                    report("failure", "stop: repair regression did not earn a stall exemption; prior stall limit retained.")
                    return 1
            if state in ("BUDGET_DEFERRED", "BUDGET_EXHAUSTED", "INVALIDATED"):
                report("failure", f"stop: validation {state}; candidate/results preserved; no command automatically retried.")
                return 1
            validation_handoff = True
            continue
        idle = 0 if delivered or autonomy_validation.source_work(registry) else idle + 1
        if idle >= max_idle:
            print(f"driver: stop: {idle} session(s) made no source progress or evidenced delivery; records-only commits do not reset this limit", file=sys.stderr)
            return 1
        if delivered:
            validation_handoff = False
        stalled = 0 if delivered else stalled + 1
        if stalled >= max_stalled:
            print(f"driver: stop: {stalled} session(s) delivered no evidenced DONE task despite commits/status edits; "
                  "inspect blockers before restarting", file=sys.stderr)
            return 1
        if requested:
            report("replacement", "Safe handoff; next session resumes preserved work with fresh context and unchanged budgets. " + remaining_summary(bundle))
    report("stopped", f"stop: reached --max-sessions {max_sessions}; no automatic restart. " + remaining_summary(bundle))
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autonomy_driver.py",
        description="Run the work queue as fresh agent sessions: one bounded integrated batch (solo) or batch round (orchestrator) each.",
        epilog="Example: autonomy_driver.py --role orchestrator --progress-file target/autonomy/run-1.jsonl --chat-ack-file target/autonomy/run-1.ack.json -- cursor-agent -p --output-format stream-json --force --trust. Use the harness that launched the run; `claude -p --output-format stream-json --verbose` and `codex exec --json` are also projected.",
    )
    parser.add_argument("--bundle", help="path to the OKF bundle directory")
    parser.add_argument("--role", choices=okf.ROLES, default="solo", help="session scope given to each agent (default: solo)")
    parser.add_argument("--max-sessions", type=int, default=20, metavar="N", help="sessions before stopping (default: 20)")
    parser.add_argument("--max-idle", type=int, default=2, metavar="N", help="stop after N sessions in a row without progress (default: 2)")
    parser.add_argument("--max-stalled", type=int, default=2, metavar="N",
                        help="stop after N non-delivery sessions; verified deterministic repair handoffs are exempt, commits alone are not")
    parser.add_argument("--max-session-seconds", type=float, default=1200,
                        help="request a checkpoint after this session duration (default 1200)")
    parser.add_argument("--handoff-seconds", type=float, default=180,
                        help="bounded checkpoint grace and recovery-session cap, inside the run budget (default 180)")
    parser.add_argument("--max-discovery-seconds", type=float, default=120,
                        help="request concrete progress without retiring a worker when no source edits are observed (default 120)")
    parser.add_argument("--max-closure-seconds", type=float, default=600,
                        help="closure checkpoint target, bounded by session/run budgets independently of discovery (default 600)")
    parser.add_argument("--validation-reserve-seconds", type=float, default=60,
                        help="reserve run time for closure; admit each validation command against actual remaining time (default 60)")
    parser.add_argument("--max-run-seconds", type=float, default=3600,
                        help="run deadline; bounds each agent launch to remaining time (default 3600)")
    parser.add_argument("--remote", default="origin", help="git remote of the agents' PR branches (default: origin)")
    parser.add_argument("--no-pr-sync", action="store_true", help="do not keep agent PRs mergeable before each session")
    parser.add_argument("--headless", action="store_true", help="explicitly allow running without a live chat supervisor")
    parser.add_argument("--progress-file", type=Path, help="fresh public JSONL progress file")
    parser.add_argument("--chat-ack-file", type=Path, help="parent-only acknowledgement file, renewed after visible chat updates")
    parser.add_argument("--chat-timeout-seconds", type=float, default=90, help="stop if chat acknowledgement expires (default 90)")
    parser.add_argument("--heartbeat-seconds", type=float, default=30, help="local progress heartbeat interval (default 30)")
    parser.add_argument("agent", nargs=argparse.REMAINDER, help="agent command after `--`; the prompt is appended")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.agent[1:] if args.agent[:1] == ["--"] else args.agent
    if not command:
        parser.error("give the agent command after `--`, e.g. -- claude -p")
    if args.max_sessions < 1 or args.max_idle < 1 or args.max_stalled < 1:
        parser.error("--max-sessions, --max-idle and --max-stalled must be at least 1")
    if args.max_stalled > MAX_STALLED_CAP:
        parser.error(f"--max-stalled above {MAX_STALLED_CAP} is rejected: split the batch instead (.ai/autonomous-execution.md §9.2)")
    if any(not math.isfinite(value) or value <= 0
           for value in (args.max_session_seconds, args.handoff_seconds, args.max_run_seconds, args.chat_timeout_seconds,
                         args.heartbeat_seconds, args.max_discovery_seconds, args.validation_reserve_seconds,
                         args.max_closure_seconds)):
        parser.error("time limits must be positive finite seconds")
    if not args.headless and (args.progress_file is None or args.chat_ack_file is None):
        parser.error("visible chat supervision required: pass --progress-file and --chat-ack-file, or explicitly choose --headless")
    if args.chat_ack_file and not args.progress_file:
        parser.error("--chat-ack-file requires --progress-file")
    if not args.headless and args.heartbeat_seconds > args.chat_timeout_seconds / 2:
        parser.error("heartbeat must be at most half the chat timeout")
    progress = None
    outcome = 1
    try:
        if args.progress_file:
            scratch.require_disk(args.progress_file)
            if args.chat_ack_file:
                scratch.require_disk(args.chat_ack_file)
            progress = autonomy_progress.Progress(args.progress_file, args.chat_ack_file if not args.headless else None,
                                                  args.chat_timeout_seconds)
            progress.wait_for_chat()
        remote = None if args.no_pr_sync else args.remote
        outcome = drive(okf.find_bundle(args.bundle), command, args.role, args.max_sessions, args.max_idle, remote,
                        args.max_session_seconds, args.max_run_seconds, args.max_stalled, progress, args.heartbeat_seconds,
                        args.handoff_seconds, args.max_discovery_seconds, args.validation_reserve_seconds,
                        args.max_closure_seconds)
        return outcome
    except autonomy_progress.MonitorLost as error:
        if progress:
            progress.emit("failure", "Chat supervisor acknowledgement missing or expired; owned agent tree stopped without retry.")
        print(f"driver: stop: {error}; no automatic restart", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"driver: stop: progress setup failed: {error}", file=sys.stderr)
        return 1
    except okf.OkfError as error:
        print(f"driver: error: {error}", file=sys.stderr)
        return 1
    except (ValueError, subprocess.CalledProcessError, timed_check.CaptureError) as error:
        print(f"driver: stop: invalid managed workflow state: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        outcome = 130
        print("driver: interrupted; run `okf.py checkpoint` before resuming", file=sys.stderr)
        return 130
    finally:
        if progress:
            progress.emit("stopped", f"Driver stopped with exit {outcome}; inspect the checkpoint before any restart.")
            progress.output.close()


if __name__ == "__main__":
    sys.exit(main())
