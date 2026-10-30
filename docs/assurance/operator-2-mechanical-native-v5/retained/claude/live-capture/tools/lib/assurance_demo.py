#!/usr/bin/env python3
"""Watch a requirement go VERIFIED, STALE, VERIFIED in a throwaway repository.

Builds a temporary Git repository with a copy of these scripts and one requirement that declares
how it is verified and which files that depends on, then drives the real `lifecycle.py assure`.
Every status printed is read from `assure --json`; the invoking repository is never touched.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional, TextIO

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scratch  # noqa: E402

LIMIT = "VERIFIED covers only the declared command on its declared inputs."
REQUIREMENT = "DEMO-R1"
CHECK = "import pathlib, sys\nsys.exit(0 if pathlib.Path('src/calc.py').read_text().startswith('ok') else 3)\n"
CAPABILITY = (
    "---\ntype: Capability\ntitle: Demo\nnamespace: DEMO\nstatus: draft\n---\n\n# Demo\n\n## Requirements\n\n"
    "- DEMO-R1: The calculator MUST add.\n"
    "  - Verify: `python3 check.py`\n"
    "  - Inputs: `check.py` `src/**`\n"
    "  - Scenario add: 1 + 1 is 2.\n\n## Notes\n\nProse.\n"
)
DROPPED_ENV = {"_AGENTIC_LIFECYCLE_RUN_ROOTS", "OKF_AUTONOMOUS", "LIFECYCLE_GUARD"}


class DemoFailure(Exception):
    pass


def _base() -> Path:
    last: Optional[Exception] = None
    for candidate in (Path(tempfile.gettempdir()),
                      Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "okf-tests"):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return scratch.require_disk(candidate)
        except (ValueError, OSError) as error:
            last = error
    raise DemoFailure(f"no disk-backed temporary directory: {last}")


class Session:
    """Runs commands inside the throwaway repository; `calls` holds the demonstrated lifecycle commands."""

    def __init__(self, repo: Path, calls: list[str]) -> None:
        self.repo = repo
        self.calls = calls
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k not in DROPPED_ENV}
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"

    def exec(self, argv: list[str], ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess:
        try:
            result = subprocess.run(argv, cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            raise DemoFailure(f"timed out: {' '.join(argv[:3])}")
        if result.returncode not in ok:
            raise DemoFailure(f"{' '.join(argv[:3])} exited {result.returncode}: {(result.stdout + result.stderr).strip()[-300:]}")
        return result

    def git(self, *args: str) -> None:
        self.exec(["git", "-c", "user.name=Demo", "-c", "user.email=demo@example.invalid", *args])

    def tool(self, script: str, *args: str, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess:
        return self.exec([sys.executable, str(self.repo / ".ai/scripts" / script), *args], ok)

    def lifecycle(self, *args: str, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess:
        self.calls.append("python3 .ai/scripts/lifecycle.py " + " ".join(args))
        return self.tool("lifecycle.py", *args, ok=ok)

    def write(self, name: str, text: str) -> None:
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def build(session: Session, prepare: Optional[Callable[[Path], None]] = None) -> None:
    repo = session.repo
    (repo / ".ai/scripts").mkdir(parents=True)
    for source in HERE.glob("*.py"):
        shutil.copy2(source, repo / ".ai/scripts" / source.name)
    session.git("init", "-q")
    session.tool("okf.py", "init")
    session.write("knowledge/project/sync-ignore", "*\n")
    session.write("check.py", CHECK)
    session.write("src/calc.py", "ok\n")
    session.write("notes.txt", "unrelated\n")
    session.write("knowledge/capabilities/demo.md", CAPABILITY)
    session.tool("okf.py", "reindex")
    if prepare:
        prepare(repo)
    session.git("add", "-A")
    session.git("commit", "-qm", "demo fixture")
    session.tool("lifecycle.py", "tier", "L1", "--reason", "assurance demo", "--new")


def observe(session: Session, *extra: str) -> dict:
    result = session.lifecycle("assure", "--json", *extra, ok=(0, 1))
    try:
        document = json.loads(result.stdout)
    except ValueError:
        raise DemoFailure("assure --json did not return JSON")
    item = next((r for r in document.get("requirements", []) if r.get("id") == REQUIREMENT), None)
    if item is None:
        raise DemoFailure(f"{REQUIREMENT} is missing from the assure output")
    return item


def _record(session: Session) -> None:
    session.lifecycle("assure", "--run")


def _edit_unrelated(session: Session) -> None:
    session.write("notes.txt", "unrelated, edited\n")


def _edit_input(session: Session) -> None:
    session.write("src/calc.py", "ok\n# edited\n")


# title, action before observing, extra assure arguments, expected status, text the reason must contain
STEPS = (
    ("declared, never run", None, (), "UNVERIFIED", ""),
    ("evidence recorded", _record, (), "VERIFIED", ""),
    ("unrelated file edited", _edit_unrelated, (), "VERIFIED", ""),
    ("input edited", _edit_input, (), "STALE", "src/calc.py"),
    ("what a change touches", None, ("--changed", "--base", "HEAD"), "STALE", "src/calc.py"),
    ("rerun after the change", _record, (), "VERIFIED", ""),
)


def run(base: Optional[Path] = None, prepare: Optional[Callable[[Path], None]] = None, out: Optional[TextIO] = None,
        err: Optional[TextIO] = None, calls: Optional[list[str]] = None) -> int:
    out = out or sys.stdout
    err = err or sys.stderr
    calls = calls if calls is not None else []
    repo_dir = Path(tempfile.mkdtemp(prefix="assurance-demo-", dir=base or _base()))
    try:
        session = Session(repo_dir / "repo", calls)
        build(session, prepare)
        calls.clear()
        out.write("Assurance demo: a throwaway repository is used; nothing in your repository is changed.\n")
        for number, (title, action, extra, expected, mention) in enumerate(STEPS, 1):
            start = len(calls)
            if action:
                action(session)
            item = observe(session, *extra)
            observed = item["status"]
            if observed != expected:
                raise DemoFailure(f"step {number} ({title}): expected {expected}, observed {observed}")
            if mention and mention not in item.get("reason", ""):
                raise DemoFailure(f"step {number} ({title}): reason does not name {mention}")
            out.write(f"STEP {number}/{len(STEPS)} {observed} - {title}\n")
            for command in calls[start:]:
                out.write(f"  $ {command}\n")
            out.write(f"  {REQUIREMENT}: {observed} - {item.get('reason', '')}\n")
        out.write(LIMIT + "\n")
        return 0
    except DemoFailure as failure:
        err.write(f"assurance_demo: {failure}\n")
        return 1
    finally:
        shutil.rmtree(repo_dir, ignore_errors=True)
        if repo_dir.exists():
            err.write(f"assurance_demo: could not remove {repo_dir}\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(143))
    return run()


if __name__ == "__main__":
    sys.exit(main())
