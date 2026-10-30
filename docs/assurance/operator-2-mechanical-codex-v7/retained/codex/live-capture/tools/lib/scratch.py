"""Disk-backed scratch shared by workflow processes and their descendants."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile


def require_disk(path: Path) -> Path:
    root = path.resolve()
    if any(root == path or path in root.parents for path in
           (Path("/tmp"), Path("/var/tmp"), Path("/dev/shm"))):
        raise ValueError(f"scratch must be outside system temporary storage: {root}")
    mounts = Path("/proc/self/mountinfo")
    if mounts.exists():
        matches = []
        for line in mounts.read_text().splitlines():
            fields, filesystem = line.split(" - ", 1)
            mount = Path(re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), fields.split()[4]))
            if root == mount or mount in root.parents:
                matches.append((len(mount.parts), filesystem.split()[0]))
        if matches and max(matches)[1] in ("tmpfs", "ramfs"):
            raise ValueError(f"scratch must be disk-backed: {root}")
    return root


def git_common_dir(repo: Path) -> Path:
    return Path(subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True,
        stderr=subprocess.PIPE).strip())


def location(repo: Path) -> Path:
    """The scratch path without creating or probing it, for readers in a read-only sandbox."""
    return git_common_dir(repo).resolve() / "okf-scratch"


def directory(repo: Path) -> Path:
    root = require_disk(git_common_dir(repo) / "okf-scratch")
    root.mkdir(parents=True, exist_ok=True)
    # Fail before launching a model/check, rather than falling back to /tmp.
    with tempfile.TemporaryFile(dir=root) as probe:
        probe.write(b"scratch preflight\n")
        probe.flush()
    return root


def environment(repo: Path, values: dict[str, str] | None = None) -> dict[str, str]:
    result = dict(os.environ if values is None else values)
    root = str(directory(repo))
    # Override inherited and manifest settings consistently for Python, Rust,
    # Dart/Flutter and their child processes. Keep effective inputs in receipts.
    result.update(TMPDIR=root, TMP=root, TEMP=root)
    return result
