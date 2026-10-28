#!/usr/bin/env python3
"""Lifecycle state, stage gates, spec analysis, acceptance convergence, traceability, red/green
evidence and harness hooks (AGENTS.md §2.5 and §8.6, .ai/lifecycle.md).

``analyze`` grades spec findings (Critical, High, Medium); stages refuse only Critical and High.
``converge`` runs each requirement's acceptance command from the active task's approved,
unedited spec, and at L2+ ``stage verify`` requires a current converge run with no FAIL.

Working state is one JSON file per branch in the git scratch directory, so it is untracked
and shared by worktrees of the same branch only. Above L0 every save also writes the
committed audit record ``knowledge/history/lifecycle/<task>.json``: the same state without
command output, with a sha256 bound to each stage's ``--ref``, checked by ``audit``. The
hook command enforces four rules: source edits need a declared tier and the stages that
tier requires before Implement; `git commit` (not `wip:`) and `gh pr create|ready` need
Verify; a commit must include the task's audit record; a session starts with the
lifecycle router. It guards against skipping, not against a determined actor:
approvals are recorded claims. ``LIFECYCLE_GUARD=off`` disables the hook; autonomous
driver sessions (``OKF_AUTONOMOUS=1``) are governed by the work queue instead.

Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True  # Bytecode beside the scripts would dirty the work tree.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import scratch  # noqa: E402


def lazy(name: str):
    """Import NAME on first attribute use: the hook runs before every shell command and rarely needs it."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.find_spec(name)
    spec.loader = importlib.util.LazyLoader(spec.loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


brownfield = lazy("brownfield")
okf = lazy("okf")
learning = lazy("learning")
ledger = lazy("ledger")
scan = lazy("scan")
project_context = lazy('project_context')
import difflib  # noqa: E402
from datetime import date

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
HOOK_ADD = re.compile(r"\bgit\s+add\b([^;&|]*)")
RECORD_DIR = "knowledge/history/lifecycle"
RUN_ROOTS_ENV = "_AGENTIC_LIFECYCLE_RUN_ROOTS"
MUTATING_COMMANDS = frozenset({'tier', 'stage', 'redgreen', 'run', 'converge', 'merge', 'learn', 'promote', 'retire', 'retrospect', 'finish'})
RECORD_KEYS = ("version", "task", "branch", "head", "tier", "reason", "user_set", "history", "stages", "redgreen")
DEFAULT_VAGUE_TERMS = (
    "fast", "quickly", "robust", "intuitive", "user-friendly", "appropriate", "as needed", "easy",
    "flexible", "efficient", "reasonable", "seamless", "works well", "properly", "etc",
)
DELTA_CATEGORY_SEVERITY = {
    "delta-structure": "Critical",
    "delta-invalid": "High",
    "delta-target": "High",
    "delta-receipt": "High",
}
CATEGORY_SEVERITY = {
    "missing-section": "Critical",
    "no-requirements": "Critical",
    "duplicate-id": "Critical",
    "uncovered-requirement": "Critical",
    "orphan-acceptance": "Critical",
    "placeholder-acceptance": "Critical",
    "missing-modal": "High",
    "vague-term": "High",
    "identical-requirements": "High",
    "open-questions": "High",
    "manual-check": "Medium",
}
BLOCKING = ("Critical", "High")
BACKTICK = re.compile(r"`([^`\n]+)`")


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


def branch_name(root: Path) -> str:
    try:
        return git(root, "rev-parse", "--abbrev-ref", "HEAD")
    except subprocess.CalledProcessError:
        return "HEAD"  # No commit yet.


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)


def state_path(root: Path, write: bool = True) -> Path:
    base = scratch.directory(root) if write else scratch.location(root)  # Reads must work in a read-only sandbox.
    return base / f"lifecycle-{slug(branch_name(root))}.json"


def new_task_id(root: Path) -> str:
    """UTC start stamp plus branch slug; a numeric suffix keeps two tasks started in the same second apart."""
    base = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{slug(branch_name(root))}"
    task, n = base, 1
    while record_path(root, {'task': task}).exists():
        n += 1
        task = base.replace("Z-", f"Z-{n}-", 1)
    return task


def record_path(root: Path, state: dict) -> Path:
    if project_context.kind(root) == 'framework':
        return scratch.location(root) / 'history/lifecycle' / f"{state['task']}.json"
    return root / RECORD_DIR / f"{state['task']}.json"


def public(state: dict, root: Path) -> dict:
    """The committed view: the working state without command output tails."""
    view = json.loads(json.dumps(state))
    view.setdefault("branch", branch_name(root))
    for entry in view.get("redgreen", []):
        for phase in ("red", "green"):
            if isinstance(entry.get(phase), dict):
                entry[phase].pop("tail", None)
    return view


def load(root: Path) -> dict | None:
    path = state_path(root, write=False)
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text())
        if state.get("task") and record_path(root, state).is_file():
            durable = json.loads(record_path(root, state).read_text())
            learning.reconcile(state, durable)
            if durable.get("merge") is not None:
                brownfield.receipt_schema(durable["merge"])
                if durable.get("task") != state.get("task") or durable.get("stages", {}).get("intent") != state.get("stages", {}).get("intent"):
                    raise LifecycleError("committed merge journal disagrees with scratch intent")
                state["merge"] = durable["merge"]
        return state
    except learning.LearningError:
        raise
    except ValueError:
        return None


@contextmanager
def state_lock(root: Path):
    """Serialize state transactions, never the checks whose results they record."""
    path = state_path(root).with_suffix('.lock')
    with path.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            if not handle.tell():
                handle.write(b'\0')
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def evidence_state(root: Path, expected: dict) -> dict:
    """Reload under state_lock so a completed check cannot overwrite newer state."""
    current = load(root)
    if (current is None or current.get('task') != expected.get('task')
            or current.get('head') != expected.get('head')
            or current.get('stages', {}).get('intent') != expected.get('stages', {}).get('intent')):
        raise LifecycleError('lifecycle task changed while check was running; result was not recorded')
    return current


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as handle:
            temp = Path(handle.name)
            handle.write(json.dumps(data, indent=2, sort_keys=True) + '\n')
        os.replace(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def save(root: Path, state: dict, publish: bool = True) -> None:
    """Write the working state and, above L0, the committed audit record."""
    if state["tier"] != "L0" and publish:
        if not state.get("task"):
            state["task"] = new_task_id(root)  # A record started before the audit trail existed.
        state.setdefault("branch", branch_name(root))
        learning.lessons(state)
        learning.closure(state)
        if record_path(root, state).is_file():
            learning.reconcile(state, json.loads(record_path(root, state).read_text()))
        first = project_context.kind(root) != 'framework' and not (root / RECORD_DIR).is_dir()
        write_atomic(record_path(root, state), public(state, root))
        if first and (root / "knowledge/index.md").is_file():  # The new directory needs its index once, or `okf.py records` fails.
            try:
                result = subprocess.run([sys.executable, str(root / ".ai/scripts/okf.py"), "reindex"], cwd=root, capture_output=True, text=True, timeout=60)
                failed = result.returncode != 0
            except (OSError, subprocess.TimeoutExpired):
                failed = True
            if failed:
                print("lifecycle: warning: `okf.py reindex` failed; run it before `stage verify`", file=sys.stderr)
    write_atomic(state_path(root), state)


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


def items(lines: list[str]) -> list[tuple[str, str]]:
    """`R<n>` bullets in order, each with its indented or blank continuation lines joined into its text."""
    result: list[tuple[str, list[str]]] = []
    parts: list[str] | None = None
    for line in lines:
        match = REQ_LINE.match(line)
        if match:
            parts = [match.group(2)]
            result.append((match.group(1), parts))
        elif parts is not None and (not line.strip() or line[:1].isspace()):
            if line.strip():
                parts.append(line.strip())
        else:
            parts = None
    return [(rid, " ".join(text)) for rid, text in result]


def ids(lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for rid, text in items(lines):
        result.setdefault(rid, text)
    return result


def duplicates(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    repeated: list[str] = []
    for rid, _ in items(lines):
        if rid in seen and rid not in repeated:
            repeated.append(rid)
        seen.add(rid)
    return repeated


def spec_model(path: Path) -> dict:
    if brownfield.is_delta(path):
        return brownfield.model(path, repo_root(path.parent))
    found = sections(path.read_text())
    requirements, acceptance = find_section(found, "requirements") or [], find_section(found, "acceptance") or []
    return {
        "found": found,
        "requirements": ids(requirements),
        "acceptance": ids(acceptance),
        "duplicates": {"requirements": duplicates(requirements), "acceptance": duplicates(acceptance)},
        "open": [ln.strip() for ln in (find_section(found, "open questions") or []) if ln.strip()],
    }


class Finding(str):
    """A lint message carrying its category and severity; it compares, joins and prints as the message."""

    category: str
    severity: str

    def __new__(cls, message: str, category: str) -> Finding:
        finding = super().__new__(cls, message)
        finding.category = category
        finding.severity = (CATEGORY_SEVERITY if category in CATEGORY_SEVERITY else DELTA_CATEGORY_SEVERITY)[category]
        return finding


def blocking(findings: list) -> list:
    """Critical and High findings; a plain string (a `trace` citation gap) always blocks."""
    return [f for f in findings if getattr(f, "severity", "High") in BLOCKING]


def warnings(findings: list) -> list:
    return [f for f in findings if getattr(f, "severity", None) == "Medium"]


def format_finding(finding: Finding, file: str) -> str:
    return f"{finding.severity} {finding.category} {file}: {finding}"


def vague_terms(root: Path | None) -> list[str]:
    """The default vague terms plus each bullet under `## Vague terms` in knowledge/project/*.md; unreadable files are skipped."""
    terms = list(DEFAULT_VAGUE_TERMS)
    directory = root / "knowledge/project" if root else None
    try:
        files = sorted(directory.glob("*.md")) if directory is not None and directory.is_dir() else []
    except OSError:
        files = []
    for file in files:
        try:
            text = file.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for line in sections(text).get("vague terms", []):
            if not line.lstrip().startswith(("-", "*")):
                continue
            term = line.strip().lstrip("-*").strip().strip("`").strip().lower()
            if term and term not in terms:
                terms.append(term)
    return terms


def vague_hits(text: str, terms: list[str]) -> list[str]:
    plain = BACKTICK.sub(" ", text)
    return [t for t in terms if re.search(r"(?<![\w-])" + r"\s+".join(map(re.escape, t.split())) + r"(?![\w-])", plain, re.I)]


def lint_spec(path: Path, strict_open: bool = True, root: Path | None = None) -> list[Finding]:
    try:
        model = spec_model(path)
    except brownfield.DeltaError as error:
        return [Finding(str(error), error.category)]
    except (ValueError, UnicodeError, OSError) as error:
        return [Finding(str(error), "delta-target")]
    if root is None:
        try:
            root = repo_root(path.parent)
        except LifecycleError:
            root = None  # Outside a repository only the default vague terms apply.
    terms = vague_terms(root)
    required = tuple(k for k in SPEC_SECTIONS if k != "requirements") if model.get("delta") else SPEC_SECTIONS
    problems = [Finding(f"missing section '## {key.title()}'", "missing-section") for key in required if find_section(model["found"], key) is None]
    reqs, accs = model["requirements"], model["acceptance"]
    if not reqs:
        problems.append(Finding("no requirements: write bullets like `- R1: The tool MUST ...` under '## Requirements'", "no-requirements"))
    for heading, key in (("Requirements", "requirements"), ("Acceptance", "acceptance")):
        problems += [Finding(f"{rid} is defined more than once under '## {heading}'", "duplicate-id") for rid in model["duplicates"][key]]
    problems += [Finding(f"{rid} has no acceptance check under '## Acceptance'", "uncovered-requirement") for rid in reqs if rid not in accs]
    problems += [Finding(f"acceptance {rid} matches no requirement", "orphan-acceptance") for rid in accs if rid not in reqs]
    problems += [Finding(f"{rid} acceptance is a placeholder", "placeholder-acceptance") for rid, text in accs.items() if re.search(r"\b(TBD|TODO)\b", text)]
    first_with: dict[str, str] = {}
    for rid, text in reqs.items():
        if not re.search(r"\b(?:MUST|SHOULD)\b", text):
            problems.append(Finding(f"{rid} has no MUST or SHOULD", "missing-modal"))
        problems += [Finding(f"{rid} uses the vague term '{term}'", "vague-term") for term in vague_hits(text, terms)]
        normalized = " ".join(text.lower().split())
        if normalized in first_with:
            problems.append(Finding(f"{rid} repeats the text of {first_with[normalized]}", "identical-requirements"))
        else:
            first_with[normalized] = rid
    for rid, text in accs.items():
        problems += [Finding(f"acceptance {rid} uses the vague term '{term}'", "vague-term") for term in vague_hits(text, terms)]
        if not BACKTICK.search(text):
            problems.append(Finding(f"acceptance {rid} has no backticked command; converge lists it as MANUAL", "manual-check"))
    if strict_open and not (len(model["open"]) == 1 and model["open"][0].lower().lstrip("-* ").startswith("none")):
        problems.append(Finding("open questions remain: resolve them or the section must read `None. ...`", "open-questions"))
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
    problems: list[str] = list(lint_spec(spec, strict_open=False, root=root))
    reqs = spec_model(spec)["requirements"]
    plan_text = plan.read_text() if plan else None
    test_text = corpus(root, tests) if tests else None
    for rid in reqs:
        pattern = re.compile(rf"(?<![\w-]){re.escape(rid)}(?![\w-])")
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


def stage_example(tier: str) -> str:
    """The complete commands for intent and plan at this tier, so one error message is enough."""
    cli = "python3 .ai/scripts/lifecycle.py stage"
    if tier == "L3":
        return (f"example: {cli} intent --note queue:TASK_ID[,TASK_ID] --approved-by decision:ADR_OR_QUEUE_ENTRY "
                f"&& {cli} plan --note queue:TASK_ID[,TASK_ID]")
    if tier == "L2":
        return f"example: {cli} intent --ref SPEC.md --approved-by human:USER && {cli} plan --ref PLAN.md"
    return f"example: {cli} intent --note 'goal; success check; assumptions' && {cli} plan --note 'steps'"


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
        hint = stage_example(tier) if {"intent", "plan"} & set(missing) else "(python3 .ai/scripts/lifecycle.py stage NAME ...)"
        return f"tier {tier} requires completed stage(s) before {target}: {', '.join(missing)}\n{hint}"
    if target in ("verify", "ship", "commit") and state.get("kind") in TEST_FIRST_KINDS and not redgreen_ok(state):
        return f"kind {state['kind']} requires red/green evidence (AGENTS.md §8.6): lifecycle.py redgreen red -- CMD, fix, redgreen green -- CMD"
    if tier != 'L0' and target in ('verify', 'ship', 'commit') and learning.closure(state) is None:
        return ('closing retrospective required: run `python3 .ai/scripts/lifecycle.py retrospect --lessons 1 2` '
                '(existing lessons with evidence), or `python3 .ai/scripts/lifecycle.py retrospect '
                '--no-new-lessons "REASON"`')
    return None


def ref_hash(path: Path) -> str:
    """sha256 of a stage artifact; for Markdown only the body, so frontmatter stamps do not count as edits."""
    if path.suffix == ".md":
        return hashlib.sha256(body(path.read_text()).strip().encode()).hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_problems(root: Path, record: object) -> list[str]:
    """Why a committed record does not hold up against the repository, or [] when it does."""
    if not isinstance(record, dict):
        return ["record is not a JSON object"]
    problems = [f"missing field '{key}'" for key in RECORD_KEYS if key not in record]
    try:
        learning.lessons(record)
        learning.closure(record)
    except learning.LearningError as error:
        problems.append(str(error))
    if record.get("merge") is not None:
        try:
            brownfield.receipt_schema(record["merge"])
        except brownfield.DeltaError as error:
            problems.append(str(error))
    problems += ledger.audit(record.get("ledger"))
    if record.get("tier") not in TIERS:
        problems.append(f"invalid tier {record.get('tier')!r}")
    stages = record.get("stages")
    if not isinstance(stages, dict):
        return problems + ["'stages' is not an object"]
    for name, entry in sorted(stages.items()):
        if not isinstance(entry, dict):
            problems.append(f"stage {name} is not an object")
            continue
        if name == "intent" and entry.get("level") in ("L2", "L3") and not entry.get("approved_by"):
            problems.append("L2+ intent has no approved_by")
        ref = entry.get("ref")
        if not ref:
            continue
        target = root / ref
        if not target.is_file():
            problems.append(f"stage {name}: {ref} is missing")
        elif not entry.get("sha256"):
            problems.append(f"stage {name}: {ref} has no recorded sha256")
        elif ref_hash(target) != entry["sha256"]:
            problems.append(f"stage {name}: {ref} changed since it was recorded (re-record the stage, with fresh approval for intent)")
    for entry in record.get("redgreen") or []:
        if isinstance(entry, dict) and any(isinstance(entry.get(p), dict) and "tail" in entry[p] for p in ("red", "green")):
            problems.append(f"red/green entry for {entry.get('cmd')!r} contains command output")
    return problems


def record_audit(root: Path, state: dict) -> list[str]:
    """The audit `stage verify` runs on the active task's record; `converge` runs the same one."""
    state.setdefault("task", new_task_id(root))  # A state started before the audit trail gets its id before the audit.
    return audit_problems(root, public(state, root))


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
        if args.tier == 'L0':
            import uuid
            state['task'] = new_task_id(root) + '-' + uuid.uuid4().hex[:12]
    if args.kind:
        state["kind"] = args.kind
    save(root, state)
    print(f"tier {state['tier']} ({state.get('kind', 'kind unset')}): {args.reason}")
    print(learning.observations(root, args.reason))
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
        raise LifecycleError("record the intent stage before the plan, so the plan can be traced to the spec\n" + stage_example(tier))
    record: dict = {"at": now(), "level": tier}
    ref = (root / args.ref) if args.ref else None
    if ref is not None and not ref.is_file():
        raise LifecycleError(f"--ref {args.ref} does not exist")
    if args.ref:
        record["ref"] = rel(root, args.ref) or args.ref  # Repo-relative, so the committed record names no local path.
        record["sha256"] = ref_hash(ref)
    if args.note:
        record["note"] = args.note
    high = tier in ("L2", "L3")
    if stage == "intent":
        if tier == "L1" and not args.note:
            raise LifecycleError("L1 intent needs --note (goal, success check, assumptions)")
        if high:
            # Report every missing piece at once: one round trip per flag cost agents several turns each.
            missing: list[str] = []
            findings = []
            if tier == "L3" and args.note and args.note.startswith("queue:") and not args.ref:
                if not (root / "knowledge/project/work-queue.md").is_file():
                    missing.append("L3 intent note 'queue:' needs knowledge/project/work-queue.md")
            elif ref is None:
                missing.append(f"{tier} intent needs --ref SPEC" + (" or --note 'queue:IDS' (the frozen queue Acceptance)" if tier == "L3" else ""))
            else:
                findings = lint_spec(ref, root=root)
                problems = blocking(findings)
                plan_ref = state["stages"].get("plan", {}).get("ref")
                if not problems and plan_ref:
                    problems = blocking(trace(root, ref, root / plan_ref, []))  # A re-recorded spec must still be covered by the plan.
                if problems:
                    missing.append("spec is not ready:\n    - " + "\n    - ".join(problems))
            if not args.approved_by or not re.match(r"^(human|decision):\S+", args.approved_by):
                missing.append("--approved-by human:<id> (the user approved the spec) or decision:<ADR> (autonomous, §9.7) is required")
            if missing:
                raise LifecycleError("intent not recorded:\n  - " + "\n  - ".join(missing) + "\n" + stage_example(tier))
            for finding in warnings(findings):
                print(format_finding(finding, args.ref), file=sys.stderr)
            record["approved_by"] = args.approved_by
    elif stage == "plan":
        if tier == "L1" and not (args.note or args.ref):
            raise LifecycleError("L1 plan needs --note or --ref")
        if high:
            if ref is None and not (tier == "L3" and str(args.note or "").startswith("queue:")):
                raise LifecycleError(f"{tier} plan needs --ref PLAN (or, at L3, --note 'queue:IDS')")
            spec = state["stages"].get("intent", {}).get("ref")
            if spec and ref is not None:
                findings = trace(root, root / spec, ref, [])
                problems = blocking(findings)
                if problems:
                    raise LifecycleError("plan does not trace to the spec:\n  - " + "\n  - ".join(problems))
                for finding in warnings(findings):
                    print(format_finding(finding, spec), file=sys.stderr)
    elif stage == "review":
        if tier == "L1" and not args.note:
            raise LifecycleError("L1 review needs --note (self-review of the diff)")
        problem = scan_problem(root, state)
        if problem:
            raise LifecycleError(problem)
        if high:
            if ref is None:
                raise LifecycleError(f"{tier} review needs --ref REVIEW_REPORT with a '## Verdict' section")
            verdict = read_verdict(ref)
            if not verdict.lower().startswith("approved"):
                raise LifecycleError(f"review verdict is not Approved: {verdict or 'no ## Verdict section'}")
    elif stage == "verify":
        if not args.note and not high:
            raise LifecycleError("verify needs --note naming the commands run and their outcomes (AGENTS.md Gate 4)")
        problems = record_audit(root, state)
        if problems:
            raise LifecycleError("lifecycle.py audit failed:\n  - " + "\n  - ".join(problems))
        problem = merge_problem(root, state)
        if problem:
            raise LifecycleError(problem)
        problem = converge_problem(root, state)
        if problem:
            raise LifecycleError(problem)
        if high:  # Evidence comes from the ledger, not from the agent's words; `LIFECYCLE_GUARD` and `OKF_AUTONOMOUS` are not read here.
            entries, tree = state.get("ledger") or [], tree_hash(root)
            problem = ledger.verify_problem(root, entries, tree)
            if problem:
                raise LifecycleError(problem)
            record["note"] = ledger.note(ledger.current_entries(root, entries, tree)) + (f" | agent note: {args.note}" if args.note else "")
        problem = scan_problem(root, state)
        if problem:
            raise LifecycleError(problem)
        if project_context.kind(root) != 'framework' and (root / "knowledge/index.md").is_file():
            okf_cli = [sys.executable, str(root / ".ai/scripts/okf.py")]
            result = subprocess.run([*okf_cli, "sync-check", "--base", state.get("head") or "HEAD"], cwd=root, capture_output=True, text=True)
            if result.returncode != 0:
                raise LifecycleError("okf.py sync-check failed:\n" + (result.stdout + result.stderr).strip()[-800:])
            result = subprocess.run([*okf_cli, "records"], cwd=root, capture_output=True, text=True)
            if result.returncode != 0:
                raise LifecycleError("okf.py records failed:\n" + (result.stdout + result.stderr).strip()[-800:])
    elif stage == "ship":
        state["done"] = True
    state["stages"][stage] = record
    save(root, state, publish=stage != "ship")  # Ship follows the commit, so it stays out of the committed record.
    print(f"stage {stage} recorded for tier {tier}")
    return 0


def cmd_retrospect(args: argparse.Namespace) -> int:
    root = repo_root()
    state = require_state(root)
    if state['tier'] == 'L0':
        raise LifecycleError('L0 is exempt from closing retrospectives')
    proposed = {'outcome': 'observations', 'lessons': sorted(set(args.lessons)), 'at': now()} if args.lessons else {
        'outcome': 'no-new-lessons', 'reason': args.no_new_lessons, 'at': now()}
    previous = learning.closure(state)
    if previous is not None:
        if {k: v for k, v in previous.items() if k != 'at'} != {k: v for k, v in proposed.items() if k != 'at'}:
            raise LifecycleError('retrospective retry conflicts with recorded closure')
    else:
        state['retrospective'] = proposed
    learning.closure(state)
    save(root, state)
    result = state['retrospective']
    detail = ', '.join(map(str, result['lessons'])) if result['outcome'] == 'observations' else result['reason']
    print(f"retrospective recorded: {result['outcome']}: {detail}")
    return 0


def cmd_observations(args: argparse.Namespace) -> int:
    print(learning.observations(repo_root(), args.query), end='')
    return 0


def cmd_learn(args: argparse.Namespace) -> int:
    root = repo_root()
    state = require_state(root)
    if state['tier'] == 'L0':
        raise LifecycleError('L0 has no durable task lessons; use an L1+ task')
    text = learning.nonblank(args.text, 'lesson text')
    values = learning.lessons(state)
    entry = {'number': len(values) + 1, 'text': text, 'sha256': learning.text_hash(text), 'at': now()}
    if args.stage is not None:
        entry['stage'] = args.stage
    if args.evidence is not None:
        entry['evidence'] = learning.nonblank(args.evidence, 'lesson evidence')
    state['lessons'] = values + [entry]
    save(root, state)
    target = record_path(root, state)
    print(f"recorded lesson {rel(root, str(target)) or str(target)}#{entry['number']}")
    return 0


def finish_rule_operation(root: Path, data: dict, rule: dict, operation: str) -> None:
    """Retryable rules -> log -> indexes publication; original metadata owns the log."""
    try:
        okf.publish_rules(root / 'knowledge', data)
        metadata = rule if operation == 'promote' else rule['retirement']
        marker = f'learning-loop:{operation}:{rule["id"]}'
        okf.append_log(root / 'knowledge',
                       f"{operation.capitalize()} {rule['id']} ({metadata['approved_by']}; {metadata['at']}).",
                       date.fromisoformat(metadata['at'][:10]), once=marker)
        okf.reindex(root / 'knowledge')
    except (OSError, okf.OkfError) as error:
        raise LifecycleError(f'rule publication incomplete; retry the same {operation} command: {error}') from error


def cmd_promote(args: argparse.Namespace) -> int:
    root = repo_root()
    if project_context.kind(root) == 'framework':
        raise LifecycleError('promotion writes adopter rules; framework instructions need a reviewed source edit')
    actor = learning.approval(args.approved_by)
    source, record, lesson = learning.lesson_reference(root, args.reference)
    problems = audit_problems(root, record)
    if problems:
        raise LifecycleError('source record audit failed: ' + '; '.join(problems))
    data = okf.read_project_rules(root / 'knowledge')
    identity = learning.rule_id(source, lesson['number'])
    rule = next((r for r in data['rules'] if r['id'] == identity), None)
    if rule is not None:
        if rule['sha256'] != lesson['sha256'] or rule['text'] != lesson['text']:
            raise LifecycleError('source lesson changed since promotion')
    else:
        rule = {'id': identity, 'status': 'active', 'source': source, 'number': lesson['number'],
                'text': lesson['text'], 'sha256': lesson['sha256'], 'at': now(), 'approved_by': actor}
        data['rules'].append(rule)
    learning.validate_rules(root, data)
    finish_rule_operation(root, data, rule, 'promote')
    print(f"rule {rule['id']} ({rule['status']})")
    return 0


def cmd_retire(args: argparse.Namespace) -> int:
    root = repo_root()
    if project_context.kind(root) == 'framework':
        raise LifecycleError('retirement writes adopter rules; framework instructions need a reviewed source edit')
    actor = learning.approval(args.approved_by)
    reason = learning.nonblank(args.reason, 'retirement reason')
    data = okf.read_project_rules(root / 'knowledge')
    rule = next((r for r in data['rules'] if r['id'] == args.rule), None)
    if rule is None:
        raise LifecycleError('rule ID is missing')
    if rule['status'] == 'retired':
        if rule['retirement']['reason'] != reason or rule['retirement']['approved_by'] != actor:
            raise LifecycleError('retirement retry conflicts with recorded retirement')
    else:
        rule.update(status='retired', retirement={'reason': reason, 'at': now(), 'approved_by': actor})
    learning.validate_rules(root, data)
    finish_rule_operation(root, data, rule, 'retire')
    print(f"retired rule {rule['id']}")
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


def changed_names(root: Path) -> set[str]:
    names = set(git(root, "ls-files", "-m", "-o", "--exclude-standard").splitlines())
    if has_head(root):
        names |= set(git(root, "diff", "--name-only", "HEAD").splitlines())  # Staged changes too.
    return names


def work_hash(root: Path) -> str:
    digest = hashlib.sha1(git(root, "rev-parse", "HEAD").encode() if has_head(root) else b"")
    for name in sorted(changed_names(root)):
        if name.startswith(RECORD_DIR + "/"):
            continue  # Recording evidence is not a fix.
        digest.update(name.encode())
        try:
            digest.update((root / name).read_bytes())
        except OSError:
            digest.update(b"<missing>")
    return digest.hexdigest()


def tree_hash(root: Path) -> str:
    """HEAD plus every changed source file; Markdown and knowledge/ edits (see `exempt`) leave a converge run current."""
    digest = hashlib.sha256(head_sha(root).encode())
    for name in sorted(changed_names(root)):
        if exempt(name):
            continue
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


def run_roots() -> list[str]:
    """Inherited owner roots protect ancestor evidence across independent fixtures."""
    try:
        roots = json.loads(os.environ.get(RUN_ROOTS_ENV, '[]'))
    except ValueError as error:
        raise LifecycleError('invalid lifecycle run ownership metadata') from error
    if not isinstance(roots, list) or any(not isinstance(root, str) for root in roots):
        raise LifecycleError('invalid lifecycle run ownership metadata')
    return roots


def cmd_run(args: argparse.Namespace) -> int:
    root = repo_root()
    with state_lock(root):
        state = require_state(root)
    command = args.run_command
    if not command:
        raise LifecycleError("give the command after `--`: lifecycle.py run LABEL -- CMD")
    try:
        profile = ledger.infer_inputs(root, command) if not args.inputs else None
        globs = ledger.check_globs(args.inputs or (profile[1] if profile else []))
        if profile:
            globs = [*globs, '!knowledge/history/lifecycle/**']  # Output receipts cannot fingerprint themselves.
        env = scratch.environment(root)  # Checks build fixtures with tempfile; scratch refuses /tmp and tmpfs.
        if profile:
            for key in ledger.SESSION_KEYS:
                env.pop(key, None)
        env[RUN_ROOTS_ENV] = json.dumps([*run_roots(), str(root.resolve())])
        before_digest = ledger.inputs_digest(root, globs)
        before_files = ledger.inputs_snapshot(root, globs) if profile else None
        before_context = ledger.context_digest(command) if profile else None
        before_tree, before_head = tree_hash(root), head_sha(root)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise LifecycleError(f"run refused, nothing was run: {error}") from error
    started, code, output = time.monotonic(), None, ""
    try:
        result = subprocess.run(command, cwd=root, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", timeout=args.timeout)
        code, output = result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired as error:
        output = decoded(error.stdout) + decoded(error.stderr) + "\ntimeout"
    except (ValueError, OSError) as error:
        output = f"cannot run: {error}"
    entry = ledger.make_entry(args.label, command, code, before_tree if globs else tree_hash(root),
                              before_head if globs else head_sha(root), time.monotonic() - started,
                              now(), globs, before_digest)
    if profile:
        entry.update(profile=profile[0], input_files=before_files, context_sha256=before_context)
    with state_lock(root):
        state = evidence_state(root, state)
        ledger.append(state, entry)
        save(root, state)
    print(f"run {args.label}: exit={code if code is not None else 'none'} tree={entry['tree'][:7]}")
    if code != 0:
        for line in output.strip().splitlines()[-12:]:
            print(f"    {line}")
    return 1 if code is None else code


def cmd_reuse(args: argparse.Namespace) -> int:
    """Print REUSE or RERUN for a ledger entry; it runs nothing and writes nothing."""
    root = repo_root()
    state = require_state(root)
    reusable, text = ledger.verdict(root, state.get("ledger") or [], args.target, tree_hash(root))
    print(text)
    return 0 if reusable else 1


def scan_problem(root: Path, state: dict) -> str | None:
    """Unwaived Critical findings in everything added since the task's head, one `RULE path:line` per line."""
    try:
        report = scan.scan(root, state.get("head") or None, exempt)
    except scan.ScanError as error:
        raise LifecycleError(str(error)) from error
    found = scan.blocking(report)
    if not found:
        return None
    return "scan-diff found unwaived Critical findings (fix them, or waive with `lifecycle:allow RULE -- reason`):\n  - " + "\n  - ".join(f"{f['rule']} {f['path']}:{f['line']}" for f in found)


def cmd_scan_diff(args: argparse.Namespace) -> int:
    """Scan added lines for stubs and weak tests; exit 1 only on an unwaived Critical finding."""
    root = repo_root()
    try:
        report = scan.scan(root, args.base, exempt)
    except scan.ScanError as error:
        raise LifecycleError(str(error)) from error
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n".join(scan.render(report)))
    return 1 if scan.blocking(report) else 0


def converge_refusal(root: Path, state: dict | None, spec: str | None) -> str | None:
    """Why `converge` must not run SPEC's commands: only the active L2+ task's approved, unedited spec may run."""
    if state is None or not is_active(state, root):
        return "no active lifecycle task"
    if state["tier"] not in ("L2", "L3"):
        return f"tier {state['tier']} has no approved spec"
    intent = state["stages"].get("intent", {})
    if spec is None or intent.get("ref") != spec:
        return f"{spec or 'SPEC'} is not the active intent's --ref ({intent.get('ref') or 'none'})"
    if not intent.get("approved_by"):
        return "the intent has no approved_by"
    problems = record_audit(root, state)
    if problems:
        return "audit: " + "; ".join(problems)
    return None


def converge_problem(root: Path, state: dict) -> str | None:
    """Why an L2+ task with a spec --ref cannot verify: no, failed or stale converge run, or an uncited MANUAL check."""
    intent = state["stages"].get("intent", {})
    ref = intent.get("ref")
    if state["tier"] not in ("L2", "L3") or not ref:
        return None  # L0, L1 and L3 `queue:` intents are not converged.
    run = state.get("converge")
    rerun = f"python3 .ai/scripts/lifecycle.py converge {ref}"
    if not isinstance(run, dict) or run.get("spec") != ref:
        return f"no converge run for {ref}: run {rerun}"
    results = run.get("results") or []
    failed = [r.get("id") for r in results if r.get("status") == "FAIL"]
    if failed:
        return f"converge failed for {', '.join(failed)}: fix them and rerun {rerun}"
    if run.get("spec_sha256") != intent.get("sha256"):
        return f"converge run is stale: {ref} changed since the run; rerun {rerun}"
    if run.get("tree") != tree_hash(root):
        return f"converge run is stale: HEAD or a source file changed since the run; rerun {rerun}"
    manual = [r.get("id") for r in results if r.get("status") == "MANUAL"]
    if manual:
        review = state["stages"].get("review", {}).get("ref")
        target = root / review if review else None
        cited = "\n".join(find_section(sections(target.read_text()), "validation reviewed") or []) if target and target.is_file() else ""
        missing = [rid for rid in manual if not re.search(rf"(?<![\w-]){re.escape(rid)}(?![\w-])", cited)]
        if missing:
            return f"manual check(s) {', '.join(missing)} not cited in '## Validation Reviewed' of {review or 'the review report'}"
    return None


def decoded(output: object) -> str:
    return output.decode(errors="replace") if isinstance(output, bytes) else str(output or "")


def cmd_converge(args: argparse.Namespace) -> int:
    root = repo_root()
    with state_lock(root):
        state = load(root)
        spec = rel(root, args.spec)
        reason = converge_refusal(root, state, spec)
    if reason:
        raise LifecycleError(f"converge refused, nothing was run: {reason}; check with python3 .ai/scripts/lifecycle.py audit")
    if brownfield.is_delta(root / spec):
        problems = blocking(lint_spec(root / spec, root=root))
        if problems:
            raise LifecycleError("delta convergence refused: " + "; ".join(problems))
    try:
        env = scratch.environment(root)  # Acceptance tests build fixtures with tempfile; scratch refuses /tmp.
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise LifecycleError(f"converge refused, nothing was run: no disk-backed scratch directory ({error})") from error
    model = spec_model(root / spec)
    results: list[dict] = []
    durations: dict[str, float] = {}
    for rid in model["requirements"]:
        match = BACKTICK.search(model["acceptance"].get(rid, ""))
        if match is None:
            results.append({"id": rid, "cmd": None, "status": "MANUAL", "exit": None})
            print(f"{rid} MANUAL")
            continue
        entry: dict = {"id": rid, "cmd": match.group(1), "status": "FAIL", "exit": None}
        started = time.monotonic()
        try:
            argv = shlex.split(entry["cmd"])
            if not argv:
                raise ValueError("empty command")
            result = subprocess.run(argv, cwd=root, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", timeout=args.timeout)
        except subprocess.TimeoutExpired as error:
            entry["error"], output = "timeout", decoded(error.stdout) + decoded(error.stderr)
        except (ValueError, OSError) as error:
            entry["error"], output = "cannot run", str(error)
        else:
            entry["exit"], output = result.returncode, result.stdout + result.stderr
            if result.returncode == 0:
                entry["status"] = "PASS"
        if entry["status"] == "PASS":
            print(f"{rid} PASS")
        else:
            print(f"{rid} FAIL ({entry.get('error') or 'exit ' + str(entry['exit'])})")
            for line in output.strip().splitlines()[-12:]:
                print(f"    {line}")
        results.append(entry)
        durations[rid] = time.monotonic() - started
    tree = tree_hash(root)
    with state_lock(root):
        state = evidence_state(root, state)
        for entry in results:  # MANUAL checks ran nothing.
            if entry["cmd"] is not None:
                ledger.append(state, ledger.make_entry(f"converge:{entry['id']}", words(entry["cmd"]), entry["exit"], tree, head_sha(root), durations[entry["id"]], now(), [], None))
        state["converge"] = {"spec": spec, "spec_sha256": ref_hash(root / spec), "tree": tree, "at": now(), "results": results}
        save(root, state)
    counts = {status: sum(r["status"] == status for r in results) for status in ("PASS", "FAIL", "MANUAL")}
    print(f"converge: {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['MANUAL']} MANUAL")
    return 1 if counts["FAIL"] else 0


def merge_bookkeeping(root: Path, model: dict, receipt: dict) -> str | None:
    resource = Path(os.path.relpath(root / receipt['spec'], model['cap'].parent)).as_posix()
    if not any(isinstance(s, dict) and s.get('resource') == resource for s in model['capmeta'].get('sources', [])):
        return 'missing spec source in ' + model['target']
    log = root / 'knowledge/log.md'
    if not log.is_file() or receipt['log_id'] not in log.read_text():
        return 'missing merge log ' + receipt['log_id']
    if okf.reindex(root / 'knowledge', check=True):
        return 'incomplete merge indexes; run merge again'
    return None


def merge_problem(root: Path, state: dict) -> str | None:
    spec = state.get('stages', {}).get('intent', {}).get('ref')
    if state['tier'] not in ('L2', 'L3') or not spec or not brownfield.is_delta(root / spec):
        return None
    try:
        model = brownfield.model(root / spec, root)
        info = model['receipt_info']
        if not info or info[1].get('task') != state.get('task') or info[2]['state'] != 'completed':
            return 'merge required for ' + model['target'] + ': missing completed receipt'
        return merge_bookkeeping(root, model, info[2])
    except (ValueError, OSError) as error:
        return 'merge validation failed: ' + str(error)


def cmd_merge(args: argparse.Namespace) -> int:
    root = repo_root()
    spec = (root / args.spec).resolve()
    try:
        spec.relative_to(root)
    except ValueError as error:
        raise LifecycleError('merge spec must be inside repository') from error
    if not brownfield.is_delta(spec):
        raise LifecycleError('merge requires a delta spec with target')
    problems = blocking(lint_spec(spec, root=root))
    if problems:
        raise LifecycleError('merge refused: ' + '; '.join(problems))
    model = brownfield.model(spec, root)
    for warning in model['warnings']:
        print(warning, file=sys.stderr)
    rendered = brownfield.render(model, spec)
    info = model['receipt_info']
    receipt = info[2] if info else None
    current = bool(receipt and receipt['state'] == 'completed' and not merge_bookkeeping(root, model, receipt))
    if args.dry_run:
        if current:
            print('up to date: ' + model['target'])
        else:
            print(''.join(difflib.unified_diff(model['captext'].splitlines(keepends=True),
                                            rendered.splitlines(keepends=True),
                                            fromfile=model['target'], tofile=model['target'])), end='')
        return 0
    state = require_state(root)
    reason = converge_refusal(root, state, spec.relative_to(root).as_posix())
    if reason:
        raise LifecycleError('merge refused: ' + reason)
    if info and info[1].get('task') != state.get('task'):
        raise LifecycleError('merge receipt belongs to another task')
    if current:
        print('up to date: ' + model['target'])
        return 0
    if brownfield.read(model['cap']) != model['captext']:
        raise LifecycleError('target changed during merge preflight; retry')
    okf.preflight_bundle_writes(root / 'knowledge', [model['cap'], record_path(root, state)])
    if not receipt:
        identity = 'merge:' + state['task'] + ':' + brownfield.spec_hash(spec)
        receipt = dict(format=1, state='pending', spec=spec.relative_to(root).as_posix(),
                       spec_sha256=brownfield.spec_hash(spec), target=model['target'],
                       operations=model['operations'], log_id=identity, log_date=date.today().isoformat(),
                       log_message='Applied delta ' + spec.relative_to(root).as_posix() + ' to ' + model['target'] + ' [' + identity + '].')
    else:
        receipt = dict(receipt, state='pending')
    state['merge'] = receipt
    save(root, state)
    if brownfield.read(model['cap']) != model['captext']:
        raise LifecycleError('target changed before replacement; pending merge can be retried')
    if rendered != model['captext']:
        okf.write_text(model['cap'], rendered)
    bundle = root / 'knowledge'
    if not (bundle / 'log.md').is_file() or receipt['log_id'] not in (bundle / 'log.md').read_text():
        okf.append_log(bundle, receipt['log_message'], date.fromisoformat(receipt['log_date']))
    okf.reindex(bundle)
    post = brownfield.model(spec, root)
    for op in receipt['operations']:
        block = post['living'].get(op['id'])
        if (brownfield.sha(block.raw) if block else None) != op['after']:
            raise LifecycleError('merge postimage mismatch ' + op['id'])
    problem = merge_bookkeeping(root, post, receipt)
    if problem:
        raise LifecycleError(problem)
    state['merge'] = dict(receipt, state='completed')
    save(root, state)
    print('merged: ' + model['target'])
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    root = repo_root()
    if args.record:
        path = Path(args.record) if Path(args.record).is_absolute() else root / args.record
    else:
        state = require_state(root)
        if state["tier"] == "L0" or not state.get("task"):
            raise LifecycleError("the active task has no committed record (L0, or started before the audit trail)")
        path = record_path(root, state)
    try:
        record = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise LifecycleError(f"{path.name} is unreadable or unparseable: {error}") from error
    problems = audit_problems(root, record)
    if problems:
        print(f"audit: {len(problems)} problem(s) in {path.name}")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"audit: OK, {path.name}")
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    root = repo_root()
    findings = trace(root, root / args.spec, (root / args.plan) if args.plan else None, args.tests or [])
    reqs = spec_model(root / args.spec)["requirements"]
    for finding in warnings(findings):
        print(format_finding(finding, args.spec), file=sys.stderr)
    problems = blocking(findings)
    if problems:
        print(f"trace: {len(problems)} gap(s) across {len(reqs)} requirement(s)")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"trace: OK, {len(reqs)} requirement(s) traced")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    root = repo_root()
    found = refused = False
    for name in args.specs:
        if not (root / name).is_file():
            raise LifecycleError(f"{name} does not exist")
        findings = lint_spec(root / name, root=root)
        for finding in findings:
            print(format_finding(finding, name))
        found = found or bool(findings)
        refused = refused or bool(blocking(findings))
    if not found:
        print(f"analyze: OK, {len(args.specs)} spec(s)")
    return 1 if refused else 0


def cmd_queue_from_spec(args: argparse.Namespace) -> int:
    root = repo_root()
    spec = root / args.spec
    findings = lint_spec(spec, root=root)
    problems = blocking(findings)
    if problems:
        raise LifecycleError("spec is not ready:\n  - " + "\n  - ".join(problems))
    for finding in warnings(findings):
        print(format_finding(finding, args.spec), file=sys.stderr)  # Stdout stays the queue entries.
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
    try:
        state = load(root)
    except (learning.LearningError, OSError, UnicodeError) as error:
        state = None
        text += f'\nActive lifecycle unavailable: {error}'
    if is_active(state, root):
        text += f"\nActive: tier {state['tier']}; complete stages: {', '.join(s for s in STAGES if complete(state, s)) or 'none'}."
    else:
        text += "\nNo tier declared yet: run `python3 .ai/scripts/lifecycle.py tier L0|L1|L2|L3 --reason TEXT` before editing source or committing (add --new when starting a different task)."
    block = project_rules_context(root)
    if block:
        text += '\n\n' + block
    text += '\n\n' + learning.observations(root, state.get('reason', '') if state else '')
    return text


def project_rules_context(root: Path) -> str:
    try:
        return learning.render_active(okf.read_project_rules(root / 'knowledge'))
    except (learning.LearningError, OSError, UnicodeError) as error:
        return f'Project rules unavailable: {error}'


def session_directory(data: dict) -> Path:
    roots = data.get("workspace_roots") or []
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or (roots[0] if roots else "") or data.get("cwd") or os.getcwd())


def git_commit_directory(command: str) -> tuple[list[str], str] | None:
    """Recognize a single Git -C commit, without interpreting shell programs."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if not tokens or tokens[0] != "git":
        return None
    has_directory = any(token.startswith("-C") for token in tokens[1:])
    # Remove quoted/escaped text before looking for shell operators; a message
    # such as ';' is a literal argument, while an unquoted ';' starts a command.
    unquoted = re.sub(r"'[^']*'|\"(?:\\.|[^\"\\])*\"|\\.", "", command)
    if re.search(r"[;&|()<>\n]", unquoted):
        if has_directory and "commit" in tokens:
            raise LifecycleError("git -C commit routing requires a single command; run the commit separately")
        return None
    directories: list[str] = []
    index = 1
    while index < len(tokens) and tokens[index].startswith("-"):
        option = tokens[index]
        if option in ("-C", "-c") and index + 1 < len(tokens):
            if option == "-C":
                directories.append(tokens[index + 1])
            index += 2
        elif option.startswith("-C") and len(option) > 2:
            directories.append(option[2:])
            index += 1
        else:
            if has_directory and "commit" in tokens:
                raise LifecycleError("unsupported git -C commit options; use `git -C DIRECTORY commit ...`")
            return None
    if directories and index < len(tokens) and tokens[index] == "commit":
        return directories, shlex.join(["git", *tokens[index:]])
    return None


def operation_directory(data: dict, git_directories: list[str]) -> tuple[Path, Path]:
    """Select the operation directory; invalid explicit targets fail closed."""
    roots = data.get("workspace_roots") or []
    directory = Path(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or (roots[0] if roots else "") or os.getcwd())
    tool_input = data.get("tool_input") or {}

    def explicit(value: object, label: str, base: Path, check_git: bool = True) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise LifecycleError(f"invalid {label}: provide a non-empty directory path inside a Git worktree")
        try:
            candidate = Path(value).expanduser()
            candidate = (candidate if candidate.is_absolute() else base / candidate).resolve()
            if not candidate.is_dir():
                raise LifecycleError("directory does not exist or is not a directory")
            if check_git:
                repo_root(candidate)
        except (LifecycleError, OSError, ValueError) as error:
            raise LifecycleError(f"invalid {label} {value!r}: {error}; select an existing Git worktree directory") from error
        return candidate

    if "workdir" in tool_input:
        directory = explicit(tool_input["workdir"], "tool_input.workdir", directory)
    for index, value in enumerate(git_directories):
        directory = explicit(value, "git -C directory", directory, check_git=index == len(git_directories) - 1)
    return directory, repo_root(directory)


def edit_paths(data: dict, root: Path, directory: Path | None = None) -> list[str]:
    tool_input = data.get("tool_input") or {}
    raw: list[str] = []
    for key in ("file_path", "path", "target_file", "notebook_path"):
        if isinstance(tool_input.get(key), str):
            raw.append(tool_input[key])
    patch = tool_input.get("command") or tool_input.get("input") or ""
    if data.get("tool_name") == "apply_patch" and isinstance(patch, str):
        pairs = re.findall(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$", patch, re.M)
        raw += [part for pair in pairs for part in pair if part]
    return [p for p in (rel(root, str((directory or root) / Path(item).expanduser())) for item in raw) if p is not None]


NO_TIER = (
    "No active lifecycle tier (AGENTS.md §2.5). Run `python3 .ai/scripts/lifecycle.py tier L0|L1|L2|L3 --reason TEXT [--kind bugfix|logic|feature|refactor|docs]` "
    "(add --new when starting a different task), then complete the stages that tier requires."
)


def exempt(path: str) -> bool:
    return path.startswith("knowledge/") or path.endswith(".md")


def unmerged_paths(root: Path) -> set[str]:
    """Files git lists as conflicted; resolving a merge is mechanical and needs no tier."""
    try:
        return set(git(root, "diff", "--name-only", "--diff-filter=U").splitlines())
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return set()


def hook_problem(data: dict, root: Path, directory: Path | None = None) -> str | None:
    state = load(root)
    active = is_active(state, root)
    tool = data.get("tool_name")
    if tool in EDIT_TOOLS:
        targets = [p for p in edit_paths(data, root, directory) if not exempt(p)]
        if not targets:
            return None
        if not active:
            if set(targets) <= unmerged_paths(root):
                return None
            return NO_TIER
        return gate_problem(state, "implement")
    command = (data.get("tool_input") or {}).get("command")
    if tool in ("Bash", "Shell") and isinstance(command, str):
        committing = bool(HOOK_COMMIT.search(command)) and not HOOK_WIP.search(command)
        if committing or HOOK_PR.search(command):
            if not active:
                return NO_TIER
            problem = gate_problem(state, "commit")
            if problem is None and committing and state["tier"] != "L0":
                problem = record_problem(root, state, command)
            return problem
    return None


def words(text: str) -> list[str]:
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def stages_record(command: str, relative: str) -> bool:
    """True when a `git add` in the same command covers the record: everything, or a path that contains it."""
    covering = {".", "knowledge", "knowledge/history", RECORD_DIR, relative}
    for match in HOOK_ADD.finditer(command):
        if any(arg in ("-A", "--all") or arg.rstrip("/") in covering for arg in words(match.group(1))):
            return True
    return False


def commits_all(command: str) -> bool:
    """True when the commit command itself has -a/--all; flags that take a value end the short-flag cluster."""
    match = HOOK_COMMIT.search(command)
    if match is None:
        return False
    for arg in words(re.split(r"[;&|]", command[match.end() :], maxsplit=1)[0]):
        if arg == "--all":
            return True
        if arg.startswith("-") and not arg.startswith("--"):
            for flag in arg[1:]:
                if flag == "a":
                    return True
                if flag in "mFCcSu":  # The rest of the cluster, or the next word, is that flag's value.
                    break
    return False


def record_problem(root: Path, state: dict, command: str) -> str | None:
    """Why a commit would leave the task's audit record out, or None."""
    if project_context.kind(root) == 'framework':
        return None  # Source receipts live in Git scratch; adopter commit gates are unchanged.
    if not state.get("task"):
        return None  # A state from before the audit trail; verify assigns its id.
    relative = record_path(root, state).relative_to(root).as_posix()
    if stages_record(command, relative):
        return None
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", relative], capture_output=True, text=True, check=True).stdout
    if not status:
        return None  # Committed and unchanged, or not written at all (nothing to include).
    if status.startswith("??"):
        return f"the lifecycle audit record is untracked: run `git add {relative}` so the commit carries it"
    if status[0] == "D":
        return f"the commit would delete the lifecycle audit record: run `git restore --staged --worktree {relative}`"
    if status[1] != " " and not commits_all(command):
        return f"the lifecycle audit record has unstaged changes: run `git add {relative}` (or commit with -a)"
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


DRIVER_REQUESTS = ("OKF_HANDOFF_REQUEST", "OKF_PROGRESS_REQUEST")


def driver_request() -> str | None:
    """A pending autonomy_driver.py request, delivered once so the agent never polls for it.

    The `.delivered` marker makes the next tool call proceed; if it cannot be written the
    request is not delivered here (blocking every call would be worse than the file fallback)."""
    for variable in DRIVER_REQUESTS:
        value = os.environ.get(variable)
        if not value or not Path(value).is_file():
            continue
        marker = Path(value + ".delivered")
        if marker.exists():
            continue
        try:
            text = Path(value).read_text().strip()
            marker.write_text("")
        except OSError:
            continue
        return f"autonomy driver {variable}: {text} (delivered once; your next command runs normally)"
    return None


def cmd_hook(args: argparse.Namespace) -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(data, dict):
        return 0
    event = data.get("hook_event_name") or ""
    if event.lower() != "sessionstart":
        request = driver_request()
        if request:
            emit(data, "PreToolUse", request)
            return 0
    bypass = os.environ.get("LIFECYCLE_GUARD") == "off" or os.environ.get("OKF_AUTONOMOUS") == "1"
    if bypass and event.lower() != 'sessionstart':
        return 0
    if event == "beforeShellExecution":  # Cursor's shell event carries the command at the top level.
        data = {**data, "tool_name": "Shell", "tool_input": {**(data.get("tool_input") or {}), "command": data.get("command")}}
    try:
        start = session_directory(data)
        # Cursor also runs .claude/settings.json hooks; its own .cursor/hooks.json entry makes the same decision.
        if args.skip_in_cursor and "cursor_version" in data and (Path(start) / ".cursor/hooks.json").is_file():
            return 0
        command = (data.get("tool_input") or {}).get("command")
        git_commit = git_commit_directory(command) if data.get("tool_name") in ("Bash", "Shell") and isinstance(command, str) else None
        if git_commit:
            data = {**data, "tool_input": {**data["tool_input"], "command": git_commit[1]}}
            command = git_commit[1]
        if (data.get("tool_name") in ("Bash", "Shell") and isinstance(command, str)
                and not HOOK_COMMIT.search(command) and not HOOK_PR.search(command)):
            emit(data, "PreToolUse", None)
            return 0
        if event.lower() == "sessionstart":
            root = repo_root(start)
            context = project_rules_context(root) + '\n\n' + learning.observations(root) if bypass else router_text(root)
            emit(data, "SessionStart", None, context)
        else:
            if data.get("tool_name") not in EDIT_TOOLS | {"Bash", "Shell"}:
                emit(data, "PreToolUse", None)
                return 0
            directory, root = operation_directory(data, git_commit[0] if git_commit else [])
            problem = hook_problem(data, root, directory)
            emit(data, "PreToolUse", f"worktree {root}: {problem}" if problem else None)
    except LifecycleError as error:
        if event.lower() != 'sessionstart':
            emit(data, 'PreToolUse', str(error))
    except learning.LearningError as error:
        # Invalid persisted learning data is a gate failure, not an internal guard bug.
        emit(data, 'PreToolUse', f'invalid lifecycle learning data: {error}; repair the conflicting record before continuing')
    except Exception:  # noqa: BLE001 - a guard bug must never block work
        return 0
    return 0


def parser() -> argparse.ArgumentParser:
    main = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = main.add_subparsers(dest="command", required=True)
    p = sub.add_parser('retrospect', help='close the active task with evidenced observations or an explicit reason')
    choice = p.add_mutually_exclusive_group(required=True)
    choice.add_argument('--lessons', type=int, nargs='+')
    choice.add_argument('--no-new-lessons', metavar='REASON')
    p.set_defaults(func=cmd_retrospect)
    p = sub.add_parser('observations', help='retrieve bounded advisory observations without changing records')
    p.add_argument('--query', default='')
    p.set_defaults(func=cmd_observations)
    p = sub.add_parser('learn', help='capture an optional, inert task lesson at any stage')
    p.add_argument('text')
    p.add_argument('--stage', choices=STAGES)
    p.add_argument('--evidence')
    p.set_defaults(func=cmd_learn)
    p = sub.add_parser('promote', help='promote RECORD#N with a human approval claim; consent is not authenticated')
    p.add_argument('reference')
    p.add_argument('--approved-by')
    p.set_defaults(func=cmd_promote)
    p = sub.add_parser('retire', help='retire a rule with a human approval claim and reason')
    p.add_argument('rule')
    p.add_argument('--reason')
    p.add_argument('--approved-by')
    p.set_defaults(func=cmd_retire)
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
    p = sub.add_parser("run", help="run CMD (argv, no shell) in scratch and record it in the evidence ledger; exits with CMD's status")
    p.add_argument("label")
    p.add_argument("--inputs", nargs="+", metavar="GLOB", help="repo-relative globs whose content `reuse` re-checks")
    p.add_argument("--timeout", type=float, default=600)
    p.set_defaults(func=cmd_run, run_command=[])
    p = sub.add_parser('finish', help='consolidate completion blockers; --apply uses existing evidence only')
    p.add_argument('--json', action='store_true')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--tests', nargs='+', default=[])
    p.add_argument('--bind', action='append', default=[], metavar='knowledge/PATH=LABEL')
    p.set_defaults(func=cmd_finish)
    p = sub.add_parser("reuse", help="print REUSE or RERUN for a recorded check (label or exact command); exit 1 on RERUN")
    p.add_argument("target", metavar="LABEL_OR_CMD")
    p.set_defaults(func=cmd_reuse)
    p = sub.add_parser("scan-diff", help="scan added lines for stubs, deferred work and weak tests; exit 1 on an unwaived Critical finding")
    p.add_argument("--base", metavar="REV", help="compare against REV (default: the working tree against HEAD)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_scan_diff)
    p = sub.add_parser("audit", help="check a committed lifecycle record against the repository; exit 1 on problems")
    p.add_argument("record", nargs="?", help=f"record path (default: the active task's file under {RECORD_DIR}/)")
    p.set_defaults(func=cmd_audit)
    p = sub.add_parser("merge", help="preview or apply an approved capability delta")
    p.add_argument("spec")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_merge)
    p = sub.add_parser("trace", help="lint a spec and check that the plan and tests cite every requirement")
    p.add_argument("spec")
    p.add_argument("--plan")
    p.add_argument("--tests", nargs="*")
    p.set_defaults(func=cmd_trace)
    p = sub.add_parser("analyze", help="print graded spec findings; exit 1 on any Critical or High finding")
    p.add_argument("specs", nargs="+", metavar="spec")
    p.set_defaults(func=cmd_analyze)
    p = sub.add_parser("converge", help="run each requirement's acceptance command from the approved spec; exit 1 on any FAIL")
    p.add_argument("spec")
    p.add_argument("--timeout", type=int, default=600, help="seconds per command (default 600)")
    p.set_defaults(func=cmd_converge)
    p = sub.add_parser("queue-from-spec", help="print work-queue entries (§9.3) for a spec's requirements")
    p.add_argument("spec")
    p.add_argument("--group", default="Spec")
    p.add_argument("--prefix", default=None)
    p.set_defaults(func=cmd_queue_from_spec)
    p = sub.add_parser("hook", help="harness hook: reads the event JSON on stdin")
    p.add_argument("--skip-in-cursor", action="store_true",
                   help="do nothing when Cursor runs this and the project has .cursor/hooks.json (for .claude/settings.json)")
    p.set_defaults(func=cmd_hook)
    return main


def cmd_finish(args):
    import completion
    return completion.finish(args)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command: list[str] = []
    if argv[:1] == ["run"] and "--" in argv:  # The command is everything after the first `--`, verbatim.
        split = argv.index("--")
        argv, command = argv[:split], argv[split + 1 :]
    args = parser().parse_args(argv)
    if args.command == "run":
        args.run_command = command
    try:
        verb = args.func.__name__.removeprefix('cmd_')
        if verb in MUTATING_COMMANDS and not ((verb == 'merge' and args.dry_run) or (verb == 'finish' and not args.apply)):
            roots = run_roots()
            if roots and str(repo_root().resolve()) in roots:
                raise LifecycleError('invoke lifecycle mutations directly, outside lifecycle.py run; ancestor run owns this repository evidence')
            if verb not in {'run', 'converge'}:
                with state_lock(repo_root()):
                    return args.func(args)
        return args.func(args)
    except LifecycleError as error:
        print(f"lifecycle: {error}", file=sys.stderr)
        return 1
    except (brownfield.DeltaError, okf.OkfError, UnicodeError, ValueError) as error:
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
