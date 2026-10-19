#!/usr/bin/env python3
"""Lifecycle state, stage gates, traceability, red/green evidence and harness hooks
(AGENTS.md §2.5 and §8.6, .ai/lifecycle.md).

State is one JSON file per branch in the git scratch directory, so it is untracked and
shared by worktrees of the same branch only. The hook command enforces three rules:
source edits need a declared tier and the stages that tier requires before Implement;
`git commit` (not `wip:`) and `gh pr create|ready` need Verify; a session starts with the
lifecycle router. It guards against skipping, not against a determined actor:
approvals are recorded claims. ``LIFECYCLE_GUARD=off`` disables the hook; autonomous
driver sessions (``OKF_AUTONOMOUS=1``) are governed by the work queue instead.

Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True  # Bytecode beside the scripts would dirty the work tree.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import scratch  # noqa: E402

TIERS = ("L0", "L1", "L2", "L3")
STAGES = ("intent", "plan", "review", "verify", "ship")
REQUIRED = {
    "L0": (),
    "L1": ("intent", "plan", "verify"),
    "L2": ("intent", "plan", "review", "verify"),
    "L3": ("intent", "plan", "review", "verify"),
}
KINDS = ("feature", "bugfix", "logic", "refactor", "docs")
TEST_FIRST_KINDS = ("bugfix", "logic")
EDIT_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch", "StrReplace", "Delete"})
SPEC_SECTIONS = ("requirements", "acceptance", "non-goals", "open questions")
REQ_LINE = re.compile(r"^\s*[-*]\s*`?(R\d+)`?\s*[:.)–—-]\s*(.+?)\s*$")
HOOK_COMMIT = re.compile(r"\bgit\s+(?:-\S+\s+(?:\S+\s+)?)*commit(?![-\w])")
HOOK_PR = re.compile(r"\bgh\s+pr\s+(?:create|ready)\b")
HOOK_WIP = re.compile(r"""(?:-[a-zA-Z]*m|--message)[ =]*["']?wip:""")  # Only a message that starts with `wip:` is exempt.


class LifecycleError(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE).strip()


def repo_root(start: Path | None = None) -> Path:
    try:
        return Path(git(start or Path.cwd(), "rev-parse", "--show-toplevel"))
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as error:
        raise LifecycleError("not inside a git repository") from error


def state_path(root: Path) -> Path:
    try:
        branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    except subprocess.CalledProcessError:
        branch = "HEAD"  # No commit yet.
    return scratch.directory(root) / f"lifecycle-{re.sub(r'[^A-Za-z0-9_.-]', '_', branch)}.json"


def load(root: Path) -> dict | None:
    path = state_path(root)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        return None


def save(root: Path, state: dict) -> None:
    state_path(root).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def rel(root: Path, path: str) -> str | None:
    """Repo-relative POSIX path, or None when the path is outside the repository."""
    candidate = Path(os.path.expanduser(path))
    candidate = candidate if candidate.is_absolute() else root / candidate
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


# --- spec model, lint and traceability -------------------------------------------------


def body(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[end + 4 :]
    return text


def sections(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in body(text).splitlines():
        match = re.match(r"^##\s+(.*?)\s*$", line)
        if match:
            current = result.setdefault(match.group(1).lower(), [])
        elif current is not None:
            current.append(line)
    return result


def find_section(found: dict[str, list[str]], key: str) -> list[str] | None:
    for heading, lines in found.items():
        if heading.startswith(key):
            return lines
    return None


def ids(lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        match = REQ_LINE.match(line)
        if match:
            result.setdefault(match.group(1), match.group(2))
    return result


def spec_model(path: Path) -> dict:
    found = sections(path.read_text())
    return {
        "found": found,
        "requirements": ids(find_section(found, "requirements") or []),
        "acceptance": ids(find_section(found, "acceptance") or []),
        "open": [ln.strip() for ln in (find_section(found, "open questions") or []) if ln.strip()],
    }


def lint_spec(path: Path, strict_open: bool = True) -> list[str]:
    model = spec_model(path)
    problems = [f"missing section '## {key.title()}'" for key in SPEC_SECTIONS if find_section(model["found"], key) is None]
    reqs, accs = model["requirements"], model["acceptance"]
    if not reqs:
        problems.append("no requirements: write bullets like `- R1: The tool MUST ...` under '## Requirements'")
    problems += [f"{rid} has no acceptance check under '## Acceptance'" for rid in reqs if rid not in accs]
    problems += [f"acceptance {rid} matches no requirement" for rid in accs if rid not in reqs]
    problems += [f"{rid} acceptance is a placeholder" for rid, text in accs.items() if re.search(r"\b(TBD|TODO)\b", text)]
    if strict_open and not (len(model["open"]) == 1 and model["open"][0].lower().lstrip("-* ").startswith("none")):
        problems.append("open questions remain: resolve them or the section must read `None. ...`")
    return problems


def corpus(root: Path, paths: list[str]) -> str:
    chunks: list[str] = []
    for item in paths:
        target = root / item
        files = [p for p in target.rglob("*") if p.is_file()] if target.is_dir() else [target]
        for file in files:
            try:
                chunks.append(file.read_text())
            except (OSError, UnicodeDecodeError):
                continue
    return "\n".join(chunks)


def trace(root: Path, spec: Path, plan: Path | None, tests: list[str]) -> list[str]:
    problems = lint_spec(spec, strict_open=False)
    reqs = spec_model(spec)["requirements"]
    plan_text = plan.read_text() if plan else None
    test_text = corpus(root, tests) if tests else None
    for rid in reqs:
        pattern = re.compile(rf"\b{rid}\b")
        if plan_text is not None and not pattern.search(plan_text):
            problems.append(f"{rid} is not cited by the plan")
        if test_text is not None and not pattern.search(test_text):
            problems.append(f"{rid} is not cited by any test")
    return problems


# --- stage logic -----------------------------------------------------------------------


def complete(state: dict, stage: str) -> bool:
    record = state.get("stages", {}).get(stage)
    if not record:
        return False
    if state["tier"] in ("L0", "L1") or stage in ("verify", "ship"):
        return True  # Notes suffice; at L2+ intent, plan and review need a validated artifact.
    return bool(record.get("ref")) or (state["tier"] == "L3" and str(record.get("note", "")).startswith("queue:"))


def redgreen_ok(state: dict) -> bool:
    return any(entry.get("green") for entry in state.get("redgreen", []))


def gate_problem(state: dict, target: str) -> str | None:
    """Why `target` (implement, review, verify, ship, commit) cannot start, or None."""
    tier = state["tier"]
    if tier == "L0" and target != "ship":
        return None
    need: tuple[str, ...]
    if target == "implement":
        need = ("intent", "plan") if tier != "L0" else ()
    elif target == "review":
        need = ("intent", "plan")
    elif target == "verify":
        need = ("intent", "plan") + (("review",) if tier in ("L2", "L3") else ())
    else:  # ship or commit
        need = REQUIRED[tier]
    missing = [stage for stage in need if not complete(state, stage)]
    if missing:
        return f"tier {tier} requires completed stage(s) before {target}: {', '.join(missing)} (python3 .ai/scripts/lifecycle.py stage NAME ...)"
    if target in ("verify", "ship", "commit") and state.get("kind") in TEST_FIRST_KINDS and not redgreen_ok(state):
        return f"kind {state['kind']} requires red/green evidence (AGENTS.md §8.6): lifecycle.py redgreen red -- CMD, fix, redgreen green -- CMD"
    return None


def read_verdict(path: Path) -> str:
    lines = body(path.read_text()).splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^##\s+Verdict\b", line, re.I):
            for follow in lines[index + 1 :]:
                if follow.strip():
                    return follow.strip()
    return ""


def cmd_tier(args: argparse.Namespace) -> int:
    root = repo_root()
    state = load(root)
    if args.new:
        state = None
    if state and not state.get("done") and TIERS.index(args.tier) < TIERS.index(state["tier"]) and state.get("user_set"):
        raise LifecycleError(f"the user set tier {state['tier']}; it cannot be lowered to {args.tier}")
    if state and is_active(state, root):
        history = state.setdefault("history", [])
        history.append({"tier": state["tier"], "to": args.tier, "reason": args.reason, "at": now()})
        state.update(tier=args.tier, reason=args.reason, user_set=state.get("user_set") or args.user_set)
        if args.tier in ("L2", "L3"):  # Stages validated only as L0/L1 notes or refs do not satisfy L2+.
            for stage in ("intent", "plan", "review", "verify"):
                if state["stages"].get(stage, {}).get("level") in ("L0", "L1"):
                    del state["stages"][stage]
    else:
        state = {"version": 1, "tier": args.tier, "reason": args.reason, "user_set": args.user_set, "stages": {}, "redgreen": [], "history": [], "head": head_sha(root)}
    if args.kind:
        state["kind"] = args.kind
    save(root, state)
    print(f"tier {state['tier']} ({state.get('kind', 'kind unset')}): {args.reason}")
    return 0


def head_sha(root: Path) -> str:
    return git(root, "rev-parse", "HEAD") if has_head(root) else ""


def is_active(state: dict | None, root: Path) -> bool:
    """A shipped task is inactive; an L0 declaration also ends at the next commit, so it cannot license a later task."""
    if state is None or state.get("done"):
        return False
    return not (state["tier"] == "L0" and state.get("head") != head_sha(root))


def require_state(root: Path) -> dict:
    state = load(root)
    if not is_active(state, root):
        raise LifecycleError("no active lifecycle: run `python3 .ai/scripts/lifecycle.py tier L0|L1|L2|L3 --reason TEXT` first")
    return state


def cmd_stage(args: argparse.Namespace) -> int:
    root = repo_root()
    state = require_state(root)
    tier, stage = state["tier"], args.stage
    if tier == "L0":
        raise LifecycleError("L0 has no stages; edit, run a focused check, and `okf.py affected`")
    if stage in ("review", "verify", "ship"):
        problem = gate_problem(state, stage)
        if problem:
            raise LifecycleError(problem)
    if stage == "plan" and not complete(state, "intent"):
        raise LifecycleError("record the intent stage before the plan, so the plan can be traced to the spec")
    record: dict = {"at": now(), "level": tier}
    ref = (root / args.ref) if args.ref else None
    if ref is not None and not ref.is_file():
        raise LifecycleError(f"--ref {args.ref} does not exist")
    if args.ref:
        record["ref"] = args.ref
    if args.note:
        record["note"] = args.note
    high = tier in ("L2", "L3")
    if stage == "intent":
        if tier == "L1" and not args.note:
            raise LifecycleError("L1 intent needs --note (goal, success check, assumptions)")
        if high:
            if tier == "L3" and args.note and args.note.startswith("queue:") and not args.ref:
                if not (root / "knowledge/project/work-queue.md").is_file():
                    raise LifecycleError("L3 intent note 'queue:' needs knowledge/project/work-queue.md")
            else:
                if ref is None:
                    raise LifecycleError(f"{tier} intent needs --ref SPEC (or, at L3, --note 'queue:IDS')")
                problems = lint_spec(ref)
                plan_ref = state["stages"].get("plan", {}).get("ref")
                if not problems and plan_ref:
                    problems = trace(root, ref, root / plan_ref, [])  # A re-recorded spec must still be covered by the plan.
                if problems:
                    raise LifecycleError("spec is not ready:\n  - " + "\n  - ".join(problems))
            if not args.approved_by or not re.match(r"^(human|decision):\S+", args.approved_by):
                raise LifecycleError("--approved-by human:<id> (the user approved the spec) or decision:<ADR> (autonomous, §9.7) is required")
            record["approved_by"] = args.approved_by
    elif stage == "plan":
        if tier == "L1" and not (args.note or args.ref):
            raise LifecycleError("L1 plan needs --note or --ref")
        if high:
            if ref is None and not (tier == "L3" and str(args.note or "").startswith("queue:")):
                raise LifecycleError(f"{tier} plan needs --ref PLAN (or, at L3, --note 'queue:IDS')")
            spec = state["stages"].get("intent", {}).get("ref")
            if spec and ref is not None:
                problems = trace(root, root / spec, ref, [])
                if problems:
                    raise LifecycleError("plan does not trace to the spec:\n  - " + "\n  - ".join(problems))
    elif stage == "review":
        if tier == "L1" and not args.note:
            raise LifecycleError("L1 review needs --note (self-review of the diff)")
        if high:
            if ref is None:
                raise LifecycleError(f"{tier} review needs --ref REVIEW_REPORT with a '## Verdict' section")
            verdict = read_verdict(ref)
            if not verdict.lower().startswith("approved"):
                raise LifecycleError(f"review verdict is not Approved: {verdict or 'no ## Verdict section'}")
    elif stage == "verify":
        if not args.note:
            raise LifecycleError("verify needs --note naming the commands run and their outcomes (AGENTS.md Gate 4)")
        if (root / "knowledge").is_dir():
            result = subprocess.run([sys.executable, str(root / ".ai/scripts/okf.py"), "records"], cwd=root, capture_output=True, text=True)
            if result.returncode != 0:
                raise LifecycleError("okf.py records failed:\n" + (result.stdout + result.stderr).strip()[-800:])
    elif stage == "ship":
        state["done"] = True
    state["stages"][stage] = record
    save(root, state)
    print(f"stage {stage} recorded for tier {tier}")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    state = require_state(repo_root())
    problem = gate_problem(state, args.target)
    if problem:
        print(f"BLOCKED: {problem}")
        return 1
    print(f"OK to {args.target}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    root = repo_root()
    state = load(root)
    if not is_active(state, root):
        print("no active lifecycle")
        return 0
    done = [s for s in STAGES if complete(state, s)]
    todo = [s for s in REQUIRED[state["tier"]] if s not in done]
    print(f"tier {state['tier']} kind={state.get('kind', '-')} user_set={state.get('user_set', False)}")
    print(f"complete: {', '.join(done) or 'none'}; still required: {', '.join(todo) or 'none'}")
    if state.get("kind") in TEST_FIRST_KINDS:
        print(f"red/green: {'recorded' if redgreen_ok(state) else 'missing'}")
    return 0


def work_hash(root: Path) -> str:
    digest = hashlib.sha1(git(root, "rev-parse", "HEAD").encode() if has_head(root) else b"")
    names = set(git(root, "ls-files", "-m", "-o", "--exclude-standard").splitlines())
    if has_head(root):
        names |= set(git(root, "diff", "--name-only", "HEAD").splitlines())  # Staged changes too.
    for name in sorted(names):
        digest.update(name.encode())
        try:
            digest.update((root / name).read_bytes())
        except OSError:
            digest.update(b"<missing>")
    return digest.hexdigest()


def has_head(root: Path) -> bool:
    return subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "-q", "HEAD"], capture_output=True).returncode == 0


def cmd_redgreen(args: argparse.Namespace) -> int:
    root = repo_root()
    state = require_state(root)
    command = [c for c in args.command if c != "--"]
    if not command:
        raise LifecycleError("give the test command after `--`")
    text = " ".join(command)
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=args.timeout)
    tail = "\n".join((result.stdout + result.stderr).strip().splitlines()[-12:])
    entry = next((e for e in state["redgreen"] if e["cmd"] == text and "green" not in e), None)
    if args.phase == "red":
        if result.returncode == 0:
            print(tail)
            raise LifecycleError("the command passed: a red run must fail for the reported reason (a vacuous test proves nothing)")
        state["redgreen"].append({"cmd": text, "red": {"exit": result.returncode, "at": now(), "work": work_hash(root), "tail": tail}})
        save(root, state)
        print(f"RED recorded (exit {result.returncode}):\n{tail}")
        return 0
    if entry is None:
        raise LifecycleError("no open red run for this exact command: run `redgreen red -- CMD` first")
    if result.returncode != 0:
        print(tail)
        raise LifecycleError("the command still fails; it is not green")
    if work_hash(root) == entry["red"]["work"]:
        raise LifecycleError("the working tree is unchanged since the red run; a green without a fix is not evidence")
    entry["green"] = {"exit": 0, "at": now(), "work": work_hash(root)}
    save(root, state)
    print("GREEN recorded; red then green evidence is complete")
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    root = repo_root()
    problems = trace(root, root / args.spec, (root / args.plan) if args.plan else None, args.tests or [])
    reqs = spec_model(root / args.spec)["requirements"]
    if problems:
        print(f"trace: {len(problems)} gap(s) across {len(reqs)} requirement(s)")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"trace: OK, {len(reqs)} requirement(s) traced")
    return 0


def cmd_queue_from_spec(args: argparse.Namespace) -> int:
    root = repo_root()
    spec = root / args.spec
    problems = lint_spec(spec)
    if problems:
        raise LifecycleError("spec is not ready:\n  - " + "\n  - ".join(problems))
    model = spec_model(spec)
    prefix = args.prefix if args.prefix is not None else spec.stem.upper().replace("_", "-") + "-"
    for rid, text in model["requirements"].items():
        check = model["acceptance"][rid]
        print(f"### {prefix}{rid} — {text[:80]}")
        print("- State: READY")
        print("- Priority: 100")
        print(f"- Group: {args.group}")
        print(f"- Acceptance: {args.spec}#{rid}: {check}")
        print(f"- Validation: {check}")
        print()
    return 0


# --- hooks -----------------------------------------------------------------------------


def router_text(root: Path) -> str:
    lines: list[str] = []
    capture = False
    source = root / ".ai/lifecycle.md"
    if source.is_file():
        for line in source.read_text().splitlines():
            if line.startswith("## "):
                capture = line.strip() == "## Router"
                continue
            if capture:
                lines.append(line)
    text = "Lifecycle router (AGENTS.md §2.5):\n" + "\n".join(lines).strip()
    state = load(root)
    if is_active(state, root):
        text += f"\nActive: tier {state['tier']}; complete stages: {', '.join(s for s in STAGES if complete(state, s)) or 'none'}."
    else:
        text += "\nNo tier declared yet: run `python3 .ai/scripts/lifecycle.py tier L0|L1|L2|L3 --reason TEXT` before editing source or committing (add --new when starting a different task)."
    return text


def edit_paths(data: dict, root: Path) -> list[str]:
    tool_input = data.get("tool_input") or {}
    raw: list[str] = []
    for key in ("file_path", "path", "target_file", "notebook_path"):
        if isinstance(tool_input.get(key), str):
            raw.append(tool_input[key])
    patch = tool_input.get("command") or tool_input.get("input") or ""
    if data.get("tool_name") == "apply_patch" and isinstance(patch, str):
        pairs = re.findall(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$", patch, re.M)
        raw += [part for pair in pairs for part in pair if part]
    return [p for p in (rel(root, item) for item in raw) if p is not None]


NO_TIER = (
    "No active lifecycle tier (AGENTS.md §2.5). Run `python3 .ai/scripts/lifecycle.py tier L0|L1|L2|L3 --reason TEXT [--kind bugfix|logic|feature|refactor|docs]` "
    "(add --new when starting a different task), then complete the stages that tier requires."
)


def exempt(path: str) -> bool:
    return path.startswith("knowledge/") or path.endswith(".md")


def hook_problem(data: dict, root: Path) -> str | None:
    state = load(root)
    active = is_active(state, root)
    tool = data.get("tool_name")
    if tool in EDIT_TOOLS:
        targets = [p for p in edit_paths(data, root) if not exempt(p)]
        if not targets:
            return None
        if not active:
            return NO_TIER
        return gate_problem(state, "implement")
    command = (data.get("tool_input") or {}).get("command")
    if tool in ("Bash", "Shell") and isinstance(command, str):
        if (HOOK_COMMIT.search(command) and not HOOK_WIP.search(command)) or HOOK_PR.search(command):
            return gate_problem(state, "commit") if active else NO_TIER
    return None


def emit(data: dict, event: str, message: str | None, context: str | None = None) -> None:
    cursor = "cursor_version" in data
    if event == "SessionStart":
        if context:
            payload = {"additional_context": context} if cursor else {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
            print(json.dumps(payload))
        return
    if message is None:
        if cursor:
            print(json.dumps({"permission": "allow"}))
        return
    text = f"Blocked by .ai/scripts/lifecycle.py: {message}"
    if cursor:
        print(json.dumps({"permission": "deny", "agent_message": text, "user_message": "Lifecycle guard"}))
    else:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": text}}))


def cmd_hook(_: argparse.Namespace) -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(data, dict):
        return 0
    if os.environ.get("LIFECYCLE_GUARD") == "off" or os.environ.get("OKF_AUTONOMOUS") == "1":
        return 0
    event = data.get("hook_event_name") or ""
    if event == "beforeShellExecution":  # Cursor's shell event carries the command at the top level.
        data = {**data, "tool_name": "Shell", "tool_input": {"command": data.get("command")}}
    try:
        roots = data.get("workspace_roots") or []
        start = os.environ.get("CLAUDE_PROJECT_DIR") or (roots[0] if roots else "") or data.get("cwd") or os.getcwd()
        root = repo_root(Path(start))
        if event.lower() == "sessionstart":
            emit(data, "SessionStart", None, router_text(root))
        else:
            emit(data, "PreToolUse", hook_problem(data, root))
    except Exception:  # noqa: BLE001 - a guard bug must never block work
        return 0
    return 0


def parser() -> argparse.ArgumentParser:
    main = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = main.add_subparsers(dest="command", required=True)
    p = sub.add_parser("tier", help="declare or escalate the lifecycle tier for this branch")
    p.add_argument("tier", choices=TIERS)
    p.add_argument("--reason", required=True)
    p.add_argument("--kind", choices=KINDS)
    p.add_argument("--user-set", action="store_true", help="the user chose this tier; it cannot be lowered")
    p.add_argument("--new", action="store_true", help="start a different task: discard the previous record and its stages")
    p.set_defaults(func=cmd_tier)
    p = sub.add_parser("stage", help="record a completed stage after validating its artifact")
    p.add_argument("stage", choices=STAGES)
    p.add_argument("--ref")
    p.add_argument("--note")
    p.add_argument("--approved-by")
    p.set_defaults(func=cmd_stage)
    p = sub.add_parser("gate", help="exit 1 unless the next step may start")
    p.add_argument("target", choices=("implement", "review", "verify", "ship", "commit"))
    p.set_defaults(func=cmd_gate)
    p = sub.add_parser("status", help="show the active tier and stages")
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("redgreen", help="run a test command and record red (must fail) or green (must pass after a change)")
    p.add_argument("phase", choices=("red", "green"))
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("command", nargs=argparse.REMAINDER)
    p.set_defaults(func=cmd_redgreen)
    p = sub.add_parser("trace", help="lint a spec and check that the plan and tests cite every requirement")
    p.add_argument("spec")
    p.add_argument("--plan")
    p.add_argument("--tests", nargs="*")
    p.set_defaults(func=cmd_trace)
    p = sub.add_parser("queue-from-spec", help="print work-queue entries (§9.3) for a spec's requirements")
    p.add_argument("spec")
    p.add_argument("--group", default="Spec")
    p.add_argument("--prefix", default=None)
    p.set_defaults(func=cmd_queue_from_spec)
    p = sub.add_parser("hook", help="harness hook: reads the event JSON on stdin")
    p.set_defaults(func=cmd_hook)
    return main


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except LifecycleError as error:
        print(f"lifecycle: {error}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print("lifecycle: command timed out", file=sys.stderr)
        return 1
    except OSError as error:  # For example a test command that does not exist.
        print(f"lifecycle: cannot run command: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
