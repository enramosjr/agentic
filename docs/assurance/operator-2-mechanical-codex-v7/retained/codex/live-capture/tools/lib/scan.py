#!/usr/bin/env python3
"""Diff scan for lifecycle.py: stubs, deferred work and weak tests in added lines (AGENTS.md §8.1).

Critical findings block; High findings are informational. A finding is waived by
`lifecycle:allow RULE -- reason` on the same added line or the line before it. Nothing is stored:
the report carries rule, path and line, never the matched text. This module imports neither
lifecycle.py nor okf.py; the caller passes the `exempt` predicate.

Standard library only; Python 3.9+.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

sys.dont_write_bytecode = True  # Bytecode beside the scripts would dirty the work tree.

CRITICAL = (
    ("C1-stub", re.compile(r"todo!\(|unimplemented!\(|NotImplemented\w")),
    ("C2-pass-todo", re.compile(r"\bpass\b\s*#.*\b(?:TO[D]O|FIX[M]E)\b")),
    ("C3-deferred", re.compile(r"future\s+work|will\s+wire\s+later", re.I)),
)
TODO = re.compile(r"\b(?:TO[D]O|FIX[M]E)\b")
SKIP = re.compile(r"@unittest\.skip\b|@pytest\.mark\.(?:skip|xfail)\b|pytest\.skip\(|t\.Skip\(|#\[ignore\]")
WAIVER = re.compile(r"lifecycle:allow\s+([A-Z]\d-[a-z0-9-]+)\s+--[ \t]+(\S.*)")

# Assertion tokens and test-function openers per language; other extensions are listed as unscanned.
ASSERTS = {
    ".py": re.compile(r"\bassert\b|\bself\.assert\w*|\bself\.fail\(|\bpytest\.raises\b"),
    ".rs": re.compile(r"\bassert\w*!|\bpanic!|#\[should_panic\]"),
    ".go": re.compile(r"\bt\.(?:Error|Fatal|Fail)"),
}
TESTS = {
    ".py": re.compile(r"^\s*(?:async\s+)?def\s+test_\w*"),
    ".rs": re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+\w+"),
    ".go": re.compile(r"^\s*func\s+Test\w*\("),
}
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class ScanError(Exception):
    pass


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), "-c", "core.quotePath=false", *args], capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        raise ScanError(f"git {args[0]} failed: {(result.stderr.strip().splitlines() or ['no output'])[0]}")
    return result.stdout


def _changes(root: Path, base: str | None) -> dict[str, dict]:
    """Per path: added (line number, text) pairs and removed line texts, from `git diff -U0` plus untracked files."""
    changes: dict[str, dict] = {}
    has_head = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", "HEAD^{commit}"], capture_output=True).returncode == 0
    target = base or ("HEAD" if has_head else None)
    tracked = _git(root, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-renames", target, "--") if target else ""
    path, line = None, 0
    for text in tracked.splitlines():
        if text.startswith("diff --git "):
            path, line = None, 0
        elif path is None and text.startswith("+++ "):
            path = text[6:] if text.startswith("+++ b/") else None
            if path is not None:
                changes.setdefault(path, {"added": [], "removed": []})
        elif path is None:
            continue
        elif text.startswith("@@"):
            match = HUNK.match(text)
            line = int(match.group(1)) if match else 0
        elif text.startswith("+"):
            changes[path]["added"].append((line, text[1:]))
            line += 1
        elif text.startswith("-"):
            changes[path]["removed"].append(text[1:])
    untracked = _git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    cached = [] if has_head else _git(root, "ls-files", "--cached").splitlines()
    for name in untracked + cached:
        data = _read(root / name)
        if data is not None:
            changes[name] = {"added": list(enumerate(data, 1)), "removed": []}
    return changes


def _read(path: Path) -> list[str] | None:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None  # Binary or unreadable files carry no scannable lines.


def _body_end(lines: list[str], start: int, suffix: str) -> int:
    """Index just past the function that opens at `start`, by indentation (Python) or braces."""
    if suffix == ".py":
        indent = len(lines[start]) - len(lines[start].lstrip())
        end = start + 1
        while end < len(lines) and (not lines[end].strip() or len(lines[end]) - len(lines[end].lstrip()) > indent):
            end += 1
        return end
    depth, opened = 0, False
    for index in range(start, len(lines)):
        depth += lines[index].count("{") - lines[index].count("}")
        opened = opened or "{" in lines[index]
        if opened and depth <= 0:
            return index + 1
    return len(lines)


def _attributes(lines: list[str], index: int) -> list[str]:
    """The contiguous `#[...]` lines directly above a Rust function."""
    start = index
    while start > 0 and lines[start - 1].strip().startswith("#["):
        start -= 1
    return lines[start:index]


def _is_test(lines: list[str], index: int, suffix: str) -> bool:
    if not TESTS[suffix].match(lines[index]):
        return False
    return suffix != ".rs" or any(line.strip() == "#[test]" for line in _attributes(lines, index))


def _weak_tests(lines: list[str], added: set[int], suffix: str) -> list[int]:
    """Line numbers of added test functions whose post-change body holds no assertion token."""
    found = []
    for index in added:
        if not (0 <= index - 1 < len(lines)) or not _is_test(lines, index - 1, suffix):
            continue
        body = lines[index - 1:_body_end(lines, index - 1, suffix)]
        attributes = _attributes(lines, index - 1) if suffix == ".rs" else []
        if not any(ASSERTS[suffix].search(text) for text in body + attributes):
            found.append(index)
    return sorted(found)


def _waiver(lines: list[str] | None, line: int, rule: str, own: str) -> str | None:
    before = lines[line - 2] if lines and line >= 2 else ""
    for text in (own, before):
        match = WAIVER.search(text)
        if match and match.group(1) == rule and match.group(2).strip():
            return match.group(2).strip()
    return None


def scan(root: Path, base: str | None, exempt: Callable[[str], bool]) -> dict:
    findings: list[dict] = []
    unscanned: set[str] = set()
    for path, change in sorted(_changes(root, base).items()):
        if exempt(path) or not change["added"]:
            continue
        suffix = Path(path).suffix
        lines = _read(root / path)
        if lines is None:
            continue
        found: list[tuple[str, str, int]] = []
        for number, text in change["added"]:
            critical = [rule for rule, pattern in CRITICAL if pattern.search(text)]
            found += [(rule, "critical", number) for rule in critical]
            if "C2-pass-todo" not in critical and TODO.search(text):
                found.append(("H1-todo", "high", number))
            if SKIP.search(text):
                found.append(("H4-skip", "high", number))
        if suffix in ASSERTS:
            found += [("H2-no-assert", "high", number) for number in _weak_tests(lines, {n for n, _ in change["added"]}, suffix)]
            pattern = ASSERTS[suffix]
            removed = sum(bool(pattern.search(text)) for text in change["removed"])
            if removed > sum(bool(pattern.search(text)) for _, text in change["added"]):
                found.append(("H3-assert-removed", "high", change["added"][0][0]))
        else:
            unscanned.add(suffix or "(no extension)")
        texts = dict(change["added"])
        for rule, severity, number in found:
            reason = _waiver(lines, number, rule, texts.get(number, ""))
            findings.append({"rule": rule, "severity": severity, "path": path, "line": number, "waived": reason is not None, **({"reason": reason} if reason else {})})
    return {"findings": findings, "unscanned": sorted(unscanned)}


def blocking(report: dict) -> list[dict]:
    return [f for f in report["findings"] if f["severity"] == "critical" and not f["waived"]]


def render(report: dict) -> list[str]:
    lines = []
    for f in report["findings"]:
        label = "WAIVED" if f["waived"] else f["severity"].upper()
        lines.append(f"{label} {f['rule']} {f['path']}:{f['line']}" + (f" -- {f['reason']}" if f["waived"] else ""))
    if report["unscanned"]:
        lines.append("unscanned for H2-H3: " + ", ".join(report["unscanned"]))
    lines.append(f"scan-diff: {'FAIL' if blocking(report) else 'OK'} ({len(blocking(report))} unwaived critical, {len(report['findings'])} findings)")
    return lines
