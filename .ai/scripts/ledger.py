#!/usr/bin/env python3
"""Evidence ledger helpers for lifecycle.py: entry schema, input globs, reuse verdicts, verify checks.

The ledger is the list of commands `lifecycle.py run` executed for the active task. It stores
no command output. This module imports neither lifecycle.py nor okf.py.

Standard library only; Python 3.9+.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # Bytecode beside the scripts would dirty the work tree.

KEYS = ("label", "argv", "exit", "tree", "head", "duration", "at", "inputs", "inputs_sha256")
OPTIONAL_KEYS = ('input_files', 'context_sha256', 'profile')
SESSION_KEYS = {'CODEX_THREAD_ID', 'SHLVL', '_'}
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


def default_inputs(argv):
    """Infer only known checks; workspace tests use all files rather than guess imports/assets."""
    if not argv:
        return None
    if any(arg.startswith(('/', '--manifest-path', '--target-dir', '--config')) or '..' in Path(arg).parts for arg in argv[1:]):
        return None  # External inputs/build roots need an explicit mapping.
    executable = Path(argv[0]).name
    if executable in ('cargo', 'cargo.exe'):
        if argv[1:2] == ['fmt']:
            return 'cargo-format', ['*.rs', '*Cargo.toml', 'Cargo.lock', '*rustfmt.toml', '.cargo/**', 'rust-toolchain*']
        if argv[1:2] in (['test'], ['build'], ['clippy']):
            return 'cargo-workspace', ['**']
    if executable.startswith('python'):
        if argv[1:3] == ['-m', 'unittest'] or (len(argv) > 1 and argv[1] == '.ai/scripts/run_tests.py'):
            return 'python-tests', ['**']
    return None


def input_paths(root, globs):
    result = _git(root, "ls-files", "-z", "-co", "--exclude-standard")
    if result.returncode:
        raise ValueError('cannot read input inventory: ' + result.stderr.strip())
    listing = result.stdout.rstrip('\0').split('\0') if result.stdout else []
    selected = set()
    for glob in globs:
        negative = glob.startswith('!')
        hits = {n for n in listing if matches(glob[1:] if negative else glob, n)}
        selected = selected - hits if negative else selected | hits
    return sorted(selected)


def package_inputs(root, argv, metadata):
    wanted = []
    for index, arg in enumerate(argv):
        if arg in ('-p', '--package') and index + 1 < len(argv):
            wanted.append(argv[index + 1])
        elif arg.startswith('--package='):
            wanted.append(arg.split('=', 1)[1])
    if not wanted or '--workspace' in argv or '--all' in argv:
        return ['**']
    members = {p['name']: p for p in metadata['packages'] if p['id'] in metadata['workspace_members']}
    if not set(wanted) <= members.keys():
        return ['**']
    selected = set(wanted)
    pending = list(wanted)
    while pending:
        for dependency in members[pending.pop()].get('dependencies', []):
            path = dependency.get('path')
            if path and not Path(path).resolve().is_relative_to(root):
                return None
            name = dependency['name']
            if name in members and name not in selected:
                selected.add(name)
                pending.append(name)
    globs = ['**']
    for name, package in members.items():
        directory = Path(package['manifest_path']).parent.resolve()
        if not directory.is_relative_to(root):
            return None
        relative = directory.relative_to(root).as_posix()
        if name not in selected:
            if relative == '.':
                return ['**']
            if any(Path(members[item]['manifest_path']).parent.resolve().is_relative_to(directory)
                   for item in selected):
                continue  # Excluding this parent would also hide a selected nested package.
            globs.extend(['!' + relative + '/**', relative + '/Cargo.toml'])
    return globs


def infer_inputs(root, argv):
    profile = default_inputs(argv)
    if profile and profile[0] == 'cargo-workspace':
        try:
            result = subprocess.run(['cargo', 'metadata', '--format-version', '1', '--no-deps', '--offline', '--locked'],
                                    cwd=root, capture_output=True, text=True, timeout=15, check=True)
            globs = package_inputs(root, argv, json.loads(result.stdout))
            return ('cargo-packages', globs) if globs else None
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            return None
    return profile


def inputs_snapshot(root: Path, globs: list[str]) -> dict:
    files = {}
    for name in input_paths(root, globs):
        path = root / name
        try:
            data = path.read_bytes()
        except OSError:
            data = b'<missing>'
        files[name] = hashlib.sha256(data).hexdigest()
    return files


def inputs_digest(root: Path, globs: list[str]) -> str | None:
    if not globs:
        return None
    # Preserve the digest algorithm used by existing receipts.
    digest = hashlib.sha256()
    for name in input_paths(root, globs):
        digest.update(name.encode() + b'\0')
        try:
            digest.update((root / name).read_bytes())
        except OSError:
            digest.update(b'<missing>')
        digest.update(b'\0')
    return digest.hexdigest()


def context_digest(argv):
    env = {k: v for k, v in os.environ.items()
           if k not in SESSION_KEYS | {'TMP', 'TEMP', 'TMPDIR', '_AGENTIC_LIFECYCLE_RUN_ROOTS'}}
    executable = shutil.which(argv[0])
    runtime = hashlib.sha256(Path(executable).read_bytes()).hexdigest() if executable else None
    return hashlib.sha256(json.dumps({'env': env, 'executable': executable, 'runtime': runtime}, sort_keys=True).encode()).hexdigest()


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
            elif key not in KEYS + OPTIONAL_KEYS:
                problems.append(f"ledger entry {index} has key '{key}' outside the schema")
    return problems


def _entry_verdict(root: Path, entry: dict, tree: str | None = None) -> tuple[bool, str]:
    name = entry.get("label", "?")
    if entry.get("exit") != 0:
        return False, f"{name} last exited {entry.get('exit')}"
    globs = entry.get("inputs") or []
    if not globs:
        # Without declared inputs only an identical working tree proves the result still holds.
        if tree and entry.get("tree") == tree:
            return True, f"REUSE {name} tree={tree[:7]} (unchanged working tree)"
        return False, f"{name} declared no --inputs and the working tree changed since it ran (declare --inputs to reuse across edits)"
    head = entry.get("head") or ""
    if not head or _git(root, "cat-file", "-e", f"{head}^{{commit}}").returncode != 0:
        return False, f"the commit {head[:7] or '?'} it ran on is not resolvable"
    try:
        if entry.get('context_sha256') and context_digest(entry['argv']) != entry['context_sha256']:
            return False, f'{name} execution environment or runtime changed'
        current_digest = inputs_digest(root, globs)
    except (OSError, ValueError) as error:
        return False, f'{name} inputs could not be verified: {error}'
    if current_digest != entry.get("inputs_sha256"):
        if 'input_files' in entry:
            current, previous = inputs_snapshot(root, globs), entry['input_files']
            changed = sorted(p for p in current.keys() | previous.keys() if current.get(p) != previous.get(p))
            return False, f"{name} inputs changed: {', '.join(changed[:8])}" + (' ...' if len(changed) > 8 else '')
        changed = _git(root, "diff", "--name-only", head, "HEAD").stdout.splitlines()
        hit = next((n for n in changed if any(matches(g, n) for g in globs)), None)
        if hit:
            return False, f"{hit} changed in a commit since the run"
        return False, f"an input of {name} was edited since the run"
    return True, f"REUSE {name} head={head[:7]}"


def verdict(root: Path, entries: list[dict], argument: str, tree: str | None = None) -> tuple[bool, str]:
    """(True, 'REUSE label head=abc1234') or (False, 'RERUN reason') for a label or an exact command."""
    try:
        argv = shlex.split(argument)
    except ValueError:
        argv = None
    for entry in reversed(entries):
        if entry.get("label") == argument or (argv and entry.get("argv") == argv):
            ok, text = _entry_verdict(root, entry, tree)
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
        if entry.get("exit") == 0 and _entry_verdict(root, entry, tree)[0]:
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
