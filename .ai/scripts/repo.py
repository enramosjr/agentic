#!/usr/bin/env python3
"""Bounded file listing, content search and line-range reading for agents whose
harness lacks a Glob, Grep or ranged Read tool (Claude Code has no Glob/Grep;
Codex has no Read). Respects .gitignore through git when the repository is a
work tree. Standard library only; Python 3.9+.

    python3 .ai/scripts/repo.py files 'app/**/*.kt' '*.dart' [--under DIR] [--depth N]
    python3 .ai/scripts/repo.py grep PATTERN [--regex] [-i] [--glob '*.rs'] [--under DIR] [--count]
    python3 .ai/scripts/repo.py read PATH [PATH...] [--lines A-B] [--limit N]
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = frozenset({".git", "node_modules", "target", "build", ".dart_tool", "__pycache__", ".venv", "dist"})
MAX_BYTES = 1_000_000


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def candidate_files(root: Path) -> list[str]:
    """Tracked plus untracked-but-not-ignored files; a filtered walk outside git."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-co", "--exclude-standard"],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        result = None
    if result is not None and result.returncode == 0:
        return sorted({p for p in result.stdout.splitlines() if p and (root / p).is_file()})
    found: list[str] = []
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        rel = Path(directory).relative_to(root)
        found.extend((rel / name).as_posix() for name in filenames)
    return sorted(found)


def glob_regex(pattern: str) -> re.Pattern[str]:
    """``**`` spans directories, ``*`` and ``?`` stay within one; no slash matches the file name."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    body = "".join(out)
    return re.compile(body + "$" if "/" in pattern else r"(?:^|.*/)" + body + "$")


def select(paths: list[str], globs: list[str], under: str | None, depth: int | None) -> list[str]:
    prefix = Path(under).as_posix().strip("/") if under else ""
    prefix = "" if prefix in ("", ".") else prefix + "/"
    paths = [p for p in paths if p.startswith(prefix)]
    if depth is not None:
        paths = [p for p in paths if p[len(prefix):].count("/") < depth]
    if globs:
        compiled = [glob_regex(g) for g in globs]
        paths = [p for p in paths if any(c.match(p) for c in compiled)]
    return paths


def _print_limited(lines: list[str], limit: int) -> None:
    if not lines:
        print("no matches", file=sys.stderr)
        return
    print("\n".join(lines[:limit]))
    if len(lines) > limit:
        print(f"... {len(lines) - limit} more (raise --limit or narrow --under/--glob)")


def cmd_files(root: Path, args: argparse.Namespace) -> int:
    _print_limited(select(candidate_files(root), args.globs, args.under, args.depth), args.limit)
    return 0


def within(paths: list[str], targets: list[str]) -> list[str]:
    """Files equal to or below any target path (a file or a directory); all files when none, or '.', is given."""
    wanted = [Path(t).as_posix().strip("/") for t in targets]
    if not wanted or any(t in ("", ".") for t in wanted):
        return paths
    return [p for p in paths if any(p == t or p.startswith(t + "/") for t in wanted)]


def cmd_grep(root: Path, args: argparse.Namespace) -> int:
    flags = re.IGNORECASE if args.ignore_case else 0
    use_regex = args.regex or args.extended
    pattern = re.compile(args.pattern if use_regex else re.escape(args.pattern), flags)
    lines: list[str] = []
    for rel in within(select(candidate_files(root), args.glob or [], args.under, None), args.paths):
        path = root / rel
        if path.stat().st_size > MAX_BYTES:
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue
        text = data.decode("utf-8", errors="replace").split("\n")
        hits = [(n, line) for n, line in enumerate(text, start=1) if pattern.search(line)]
        if args.count or args.count_flag:
            lines.extend([f"{rel}: {len(hits)}"] if hits else [])
            continue
        shown: dict[int, str] = {}
        for n, line in hits:
            for near in range(max(1, n - args.before), min(len(text), n + args.after) + 1):
                shown.setdefault(near, "-")
            shown[n] = ":"
        lines.extend(f"{rel}{mark}{n}{mark} {text[n - 1].strip()[:200]}" for n, mark in sorted(shown.items()))
    if not lines and not use_regex and re.search(r"\||\\[bdsw]|\.\*", args.pattern):
        print("no matches (the pattern is literal; add --regex for alternation or escapes)", file=sys.stderr)
        return 0
    _print_limited(lines, args.limit)
    return 0


def line_range(spec: str) -> tuple[int, int | None]:
    """'A-B', 'A-' or 'A' (1-based, inclusive) to (start, end or None)."""
    match = re.fullmatch(r"(\d+)(?:-(\d*))?", spec.strip())
    if not match or int(match.group(1)) < 1:
        raise ValueError(f"--lines must look like A-B, A- or A with A >= 1, got {spec!r}")
    start = int(match.group(1))
    if match.group(2) is None:
        return start, start
    end = int(match.group(2)) if match.group(2) else None
    if end is not None and end < start:
        raise ValueError(f"--lines end {end} is before start {start}")
    return start, end


def read_one(root: Path, name: str, spec: str | None, limit: int) -> None:
    path = Path(name) if Path(name).is_absolute() else root / name
    if not path.is_file():
        raise ValueError(f"no file at {name}")
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        raise ValueError(f"{name} is binary")
    lines = data.decode("utf-8", errors="replace").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    start, end = line_range(spec) if spec else (1, None)
    if start > len(lines):
        raise ValueError(f"{name} has {len(lines)} line(s); --lines starts at {start}")
    last = min(len(lines), end or len(lines), start + limit - 1)
    print("\n".join(f"{n:>6}\t{lines[n - 1]}" for n in range(start, last + 1)))
    wanted = min(len(lines), end or len(lines))
    if last < wanted:
        print(f"... lines {last + 1}-{wanted} not shown (of {len(lines)}); continue with --lines {last + 1}-{wanted}")


def cmd_read(root: Path, args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")
    spec = args.lines
    if spec is None and (args.start or args.end):  # Common guesses; same meaning as --lines START-END.
        spec = f"{args.start or 1}-{args.end or ''}"
    if len(args.paths) == 1:
        read_one(root, args.paths[0], spec, args.limit)
        return 0
    failed = 0
    for name in args.paths:  # One call for several files saves a model turn per file.
        print(f"==> {name} <==")
        try:
            read_one(root, name, spec, args.limit)
        except ValueError as error:
            print(f"repo: error: {error}")
            failed = 1
    return failed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repo.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("files", help="list repo files matching globs (gitignored files excluded)")
    p.add_argument("globs", nargs="*", metavar="GLOB", help="e.g. 'app/**/*.kt' or '*.dart'; none lists all")
    p.add_argument("--under", metavar="DIR", help="only files below this directory")
    p.add_argument("--depth", type=int, metavar="N", help="at most N levels below --under (1 = like ls)")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(handler=cmd_files)

    p = sub.add_parser("grep", help="search repo file contents; prints path:line: text")
    p.add_argument("pattern")
    p.add_argument("paths", nargs="*", metavar="PATH", help="files or directories to search (like --under, several allowed)")
    p.add_argument("--regex", action="store_true", help="treat pattern as a regular expression, e.g. 'parser|renderer'")
    p.add_argument("-i", "--ignore-case", action="store_true")
    # grep spellings that agents reach for by habit; they map onto the options above.
    p.add_argument("-E", "-P", dest="extended", action="store_true", help="same as --regex")
    p.add_argument("-c", dest="count_flag", action="store_true", help="same as --count")
    p.add_argument("-n", "-r", "-R", "-H", action="store_true", help="accepted and ignored: line numbers and recursion are always on")
    p.add_argument("-A", dest="after", type=int, default=0, metavar="N", help="also print N lines after each match")
    p.add_argument("-B", dest="before", type=int, default=0, metavar="N", help="also print N lines before each match")
    p.add_argument("-C", dest="context", type=int, metavar="N", help="N lines before and after each match")
    p.add_argument("--glob", action="append", metavar="GLOB", help="only files matching this glob (repeatable)")
    p.add_argument("--under", metavar="DIR", help="only files below this directory")
    p.add_argument("--count", action="store_true", help="print match counts per file instead of lines")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(handler=cmd_grep)

    p = sub.add_parser("read", help="print numbered lines of files, bounded; use instead of cat/head/sed -n")
    p.add_argument("paths", nargs="+", metavar="PATH", help="repo-relative or absolute file paths; several print with ==> PATH <== headers")
    p.add_argument("--lines", metavar="A-B", help="1-based inclusive range: 'A-B', 'A-' or 'A' (default: from line 1)")
    p.add_argument("--start", type=int, help=argparse.SUPPRESS)
    p.add_argument("--end", type=int, help=argparse.SUPPRESS)
    p.add_argument("--limit", type=int, default=250, help="maximum lines printed per file (default: 250)")
    p.set_defaults(handler=cmd_read)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "context", None) is not None:
        args.before = args.after = args.context
    try:
        return args.handler(Path(os.environ.get("REPO_ROOT") or repo_root()), args)
    except re.error as error:
        print(f"repo: error: bad --regex pattern: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"repo: error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
