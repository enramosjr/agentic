#!/usr/bin/env python3
"""Evidence ledger helpers for lifecycle.py: entry schema, input globs, reuse verdicts, verify checks.

The ledger is the list of commands `lifecycle.py run` executed for the active task. It stores
no command output. This module imports neither lifecycle.py nor okf.py.

Standard library only; Python 3.9+.
"""

from __future__ import annotations

import fnmatch
import hashlib
import shlex
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # Bytecode beside the scripts would dirty the work tree.

KEYS = ("label", "argv", "exit", "tree", "head", "duration", "at", "inputs", "inputs_sha256")
OUTPUT_KEYS = ("tail", "output", "stdout", "stderr")
MAX_ENTRIES = 100
RUN_HINT = "python3 .ai/scripts/lifecycle.py run LABEL -- CMD"


def check_globs(globs: list[str]) -> list[str]:
    """Repo-relative POSIX input globs, or ValueError for an absolute path or a `..` segment."""
    for glob in globs:
        if not glob.strip():
            raise ValueError("an --inputs glob is empty")
        if glob.startswith("/"):
            raise ValueError(f"--inputs {glob!r} is an absolute path; use a repo-relative glob")
        if ".." in glob.split("/"):
            raise ValueError(f"--inputs {glob!r} contains a '..' segment; use a repo-relative glob")
    return list(globs)


def matches(glob: str, path: str) -> bool:
    """fnmatch on the path, or a directory prefix when the glob ends in `/`."""
    if glob.endswith("/"):
        return path.startswith(glob)
    return fnmatch.fnmatchcase(path, glob)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def inputs_digest(root: Path, globs: list[str]) -> str | None:
    """sha256 over the sorted matching files' paths and bytes, or None when no inputs are declared."""
    if not globs:
        return None
    listing = _git(root, "ls-files", "-co", "--exclude-standard").stdout.splitlines()
    digest = hashlib.sha256()
    for name in sorted({n for n in listing if any(matches(g, n) for g in globs)}):
        digest.update(name.encode() + b"\0")
        try:
            digest.update((root / name).read_bytes())
        except OSError:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def make_entry(label: str, argv: list[str], code: int | None, tree: str, head: str, duration: float,
               at: str, globs: list[str], digest: str | None) -> dict:
    return {"label": label, "argv": list(argv), "exit": code, "tree": tree, "head": head,
            "duration": round(duration, 3), "at": at, "inputs": list(globs), "inputs_sha256": digest}


def append(state: dict, entry: dict) -> None:
    state["ledger"] = ((state.get("ledger") or []) + [entry])[-MAX_ENTRIES:]


def audit(entries: object) -> list[str]:
    """Why a record's ledger breaks the schema or carries command output; a missing ledger is valid."""
    if entries is None:
        return []
    if not isinstance(entries, list):
        return ["ledger is not a list"]
    problems = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"ledger entry {index} is not an object")
            continue
        for key in sorted(entry):
            if key in OUTPUT_KEYS:
                problems.append(f"ledger entry {index} carries command output key '{key}'")
            elif key not in KEYS:
                problems.append(f"ledger entry {index} has key '{key}' outside the schema")
    return problems


def _entry_verdict(root: Path, entry: dict) -> tuple[bool, str]:
    name = entry.get("label", "?")
    if entry.get("exit") != 0:
        return False, f"{name} last exited {entry.get('exit')}"
    globs = entry.get("inputs") or []
    if not globs:
        return False, f"{name} declared no --inputs, so nothing proves it is still valid"
    head = entry.get("head") or ""
    if not head or _git(root, "cat-file", "-e", f"{head}^{{commit}}").returncode != 0:
        return False, f"the commit {head[:7] or '?'} it ran on is not resolvable"
    changed = _git(root, "diff", "--name-only", head, "HEAD").stdout.splitlines()
    hit = next((n for n in changed if any(matches(g, n) for g in globs)), None)
    if hit:
        return False, f"{hit} changed in a commit since the run"
    if inputs_digest(root, globs) != entry.get("inputs_sha256"):
        return False, f"an input of {name} was edited since the run"
    return True, f"REUSE {name} head={head[:7]}"


def verdict(root: Path, entries: list[dict], argument: str) -> tuple[bool, str]:
    """(True, 'REUSE label head=abc1234') or (False, 'RERUN reason') for a label or an exact command."""
    try:
        argv = shlex.split(argument)
    except ValueError:
        argv = None
    for entry in reversed(entries):
        if entry.get("label") == argument or (argv and entry.get("argv") == argv):
            ok, text = _entry_verdict(root, entry)
            return ok, text if ok else f"RERUN {text}"
    return False, f"RERUN no ledger entry for {argument!r}"


def current_entries(root: Path, entries: list[dict], tree: str) -> list[dict]:
    """The newest entry per label that passed and is current: same tree, or a REUSE verdict."""
    seen: set[str] = set()
    current = []
    for entry in reversed(entries):
        label = entry.get("label")
        if label in seen:
            continue
        seen.add(label)
        if entry.get("exit") == 0 and (entry.get("tree") == tree or _entry_verdict(root, entry)[0]):
            current.append(entry)
    return list(reversed(current))


def verify_problem(root: Path, entries: list[dict], tree: str) -> str | None:
    """Why `stage verify` at L2+ must refuse on this ledger, or None."""
    newest: dict[str, dict] = {}
    for entry in entries:
        if entry.get("tree") == tree:
            newest[entry.get("label")] = entry
    failing = [label for label, entry in newest.items() if entry.get("exit") != 0]
    if failing:
        return f"the newest run of {', '.join(map(str, failing))} on this tree did not pass: fix it and rerun `{RUN_HINT}`"
    if not current_entries(root, entries, tree):
        return f"no passing ledger entry is current for this tree: record one with `{RUN_HINT}`"
    return None


def note(entries: list[dict]) -> str:
    return "; ".join(f"{e.get('label')} exit=0 tree={str(e.get('tree'))[:7]}" for e in entries)
