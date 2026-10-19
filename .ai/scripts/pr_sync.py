#!/usr/bin/env python3
"""Keep the agents' open pull requests mergeable.

    python3 .ai/scripts/pr_sync.py [--remote origin] [--dry-run]

Agent PRs include milestone integration branches named ``milestone/m<N>``. For compatibility
with existing runs, task ``Owner`` branches in the queue/archive and the current branch are
also recognized. New work uses one PR per milestone, never per task or run-state update.
For each one whose base branch has moved on, the base is merged into the head branch, using the
OKF merge driver, and pushed. History is never rebased or force-pushed. A merge with real
conflicts is aborted instead. If that PR was ready, it goes back to draft with a comment listing
the files, and the next agent session resolves them.

Branches of IN_PROGRESS tasks are skipped, because their owner merges the base before reporting.
``autonomy_driver.py`` runs this before every session.

Exit status: 0 when every agent PR is mergeable; 1 when some need an agent; 2 when git or gh
fails. ``OKF_GH`` overrides the gh command. Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.dont_write_bytecode = True  # A __pycache__ beside okf.py would make the work tree, and so the checkpoint, unclean.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import okf  # noqa: E402
import scratch  # noqa: E402


class SyncError(Exception):
    """git or gh failed in a way that needs a human (missing tool, auth, identity, network)."""


@dataclass
class Result:
    number: int
    branch: str
    base: str
    action: str  # "in sync" | "synced" | "conflicts" | "would sync" | "skipped"
    files: list[str] = field(default_factory=list)
    note: str = ""

    def line(self) -> str:
        detail = f": {', '.join(self.files)}" if self.files else ""
        note = f" ({self.note})" if self.note else ""
        return f"#{self.number} {self.branch} <- {self.base}: {self.action}{detail}{note}"


def _run(command: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError as error:
        raise SyncError(f"{command[0]} not found ({error})") from error
    if check and result.returncode != 0:
        output = (result.stderr or result.stdout).strip().splitlines()
        raise SyncError(f"`{' '.join(command[:3])}` failed: {output[-1] if output else f'exit {result.returncode}'}")
    return result


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(["git", *args], cwd, check=check)


def _gh(cwd: Path, *args: str) -> str:
    return _run([os.environ.get("OKF_GH", "gh"), *args], cwd).stdout


def agent_branches(bundle: Path) -> tuple[set[str], set[str]]:
    """(branches to keep mergeable, branches whose task is IN_PROGRESS), from task Owner fields."""
    _, tasks = okf._load_queue(bundle)
    states = okf.effective_states(tasks)
    syncable: set[str] = set()
    active: set[str] = set()
    for task in tasks:
        owner = task.get("Owner")
        if "@" in owner:
            (active if states[task.id] == "IN_PROGRESS" else syncable).add(owner.rsplit("@", 1)[1])
    return syncable - active, active


def _merge_base_into(worktree: Path, remote: str, base: str, branch: str, number: int) -> list[str]:
    """Merge remote/base into the checkout at `worktree`; return conflicted files (merge aborted)."""
    message = f"Merge {base} into {branch} to keep #{number} mergeable (pr_sync.py)"
    result = _git(worktree, "merge", "--no-ff", "--no-edit", "-m", message, f"{remote}/{base}", check=False)
    if result.returncode == 0:
        return []
    conflicted = _git(worktree, "diff", "--name-only", "--diff-filter=U").stdout.split()
    if not conflicted:  # Not a content conflict: identity, hooks, or a broken driver.
        raise SyncError(f"merging {base} into {branch} failed: {(result.stderr or result.stdout).strip().splitlines()[-1:]}")
    _git(worktree, "merge", "--abort")
    return conflicted


def sync_pr(repo: Path, remote: str, pr: dict[str, object], current: str, dry_run: bool) -> Result:
    number, branch, base = int(pr["number"]), str(pr["headRefName"]), str(pr["baseRefName"])
    if _git(repo, "merge-base", "--is-ancestor", f"{remote}/{base}", f"{remote}/{branch}", check=False).returncode == 0:
        return Result(number, branch, base, "in sync")
    if branch == current:
        # The run branch is checked out here: merge in place so the local branch stays current.
        if _git(repo, "status", "--porcelain").stdout.strip():
            return Result(number, branch, base, "skipped", note="checkout has uncommitted changes")
        worktree, cleanup = repo, None
    else:
        worktree = Path(tempfile.mkdtemp(prefix="pr-sync-", dir=scratch.directory(repo)))
        _git(repo, "worktree", "add", "--quiet", "--detach", str(worktree), f"{remote}/{branch}")
        cleanup = worktree
    try:
        conflicted = _merge_base_into(worktree, remote, base, branch, number)
        if conflicted:
            if not dry_run and not pr.get("isDraft"):
                _gh(repo, "pr", "ready", str(number), "--undo")
                body = (
                    f"Returned to draft by `pr_sync.py`: merging `{base}` into `{branch}` conflicts in "
                    + ", ".join(f"`{name}`" for name in conflicted)
                    + ". The next agent session merges the base, resolves the conflicts, and reruns validation. "
                    "This PR stays draft until the entire milestone meets the readiness criteria in AGENTS.md §9."
                )
                _gh(repo, "pr", "comment", str(number), "--body", body)
            return Result(number, branch, base, "conflicts", conflicted, "returned to draft" if not pr.get("isDraft") and not dry_run else "")
        if dry_run:
            _git(worktree, "reset", "--quiet", "--hard", "ORIG_HEAD")
            return Result(number, branch, base, "would sync")
        _git(worktree, "push", "--quiet", remote, f"HEAD:refs/heads/{branch}")
        return Result(number, branch, base, "synced")
    finally:
        if cleanup is not None:
            _git(repo, "worktree", "remove", "--force", str(cleanup), check=False)
            shutil.rmtree(cleanup, ignore_errors=True)


def sync(bundle: Path, remote: str = "origin", *, dry_run: bool = False,
         only_branch: str | None = None) -> list[Result]:
    repo = bundle.parent
    syncable, active = agent_branches(bundle)
    current = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    prs = json.loads(_gh(repo, "pr", "list", "--state", "open", "--limit", "200", "--json", "number,headRefName,baseRefName,isDraft"))
    _git(repo, "fetch", "--quiet", remote)
    results: list[Result] = []
    for pr in sorted(prs, key=lambda p: int(p["number"])):
        branch = str(pr["headRefName"])
        if only_branch is not None and branch != only_branch:
            continue
        if branch in active:
            results.append(Result(int(pr["number"]), branch, str(pr["baseRefName"]), "skipped", note="task IN_PROGRESS; its owner merges the base"))
        elif branch in syncable or branch == current or (branch.startswith("milestone/m") and branch[11:].isdigit()):
            results.append(sync_pr(repo, remote, pr, current, dry_run))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pr_sync.py", description="Keep the agents' open pull requests mergeable.")
    parser.add_argument("--bundle", help="path to the OKF bundle directory")
    parser.add_argument("--remote", default="origin", help="git remote the PR branches live on (default: origin)")
    parser.add_argument("--dry-run", action="store_true", help="trial-merge only: push nothing and change no PR")
    args = parser.parse_args(argv)
    try:
        results = sync(okf.find_bundle(args.bundle), args.remote, dry_run=args.dry_run)
    except (SyncError, okf.OkfError) as error:
        print(f"pr_sync: error: {error}", file=sys.stderr)
        return 2
    for result in results:
        print(result.line())
    if not results:
        print("no open agent PRs")
    return 1 if any(r.action == "conflicts" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
