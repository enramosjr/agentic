#!/usr/bin/env python3
"""Pre-shell hook: reject shell reads, listings, searches, and file writes that
an agent's own tools or ``okf.py`` already do with fewer tokens.

Wired as a Cursor ``beforeShellExecution`` hook and a Claude Code or Codex
``PreToolUse`` hook on ``Bash`` (the two share one payload shape). Reads the hook JSON on stdin, prints the
decision JSON for whichever harness sent it, and always exits 0. Unparseable
input or commands are allowed, so a guard bug never blocks work.

Filtering another command's output (``cargo test 2>&1 | tail -30``) is allowed;
only commands that start a pipeline are judged. Set ``OKF_SHELL_GUARD=off`` in
the environment that launches the agent to disable the guard.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

OKF = "python3 .ai/scripts/okf.py"
READERS = frozenset({"cat", "head", "tail", "less", "more", "nl", "bat"})
SEARCHERS = frozenset({"grep", "egrep", "fgrep", "rg", "ag", "ack"})
LISTERS = frozenset({"ls", "find", "tree"})
SEPARATORS = frozenset({";", "&&", "||", "|", "&", "|&"})
REDIRECTS = frozenset({"<", ">", ">>", "<<", "<<<", ">&", "&>", "<&", ">|", "&>>"})
EXEMPT_PREFIXES = ("/tmp/", "/dev/", "/proc/")
_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
_PY_WRITE_RE = re.compile(r"write_text\(|write_bytes\(|\.write\(|open\([^)]*['\"][wax]")
_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_]\w*=")
_LIVE_DISPLAY_RE = re.compile(r"(?<![\w.])(?:DISPLAY=:[01](?:\.\d+)?(?!\d)|WAYLAND_DISPLAY=)")

REPO = "python3 .ai/scripts/repo.py"
TOOLS = "Claude Code: Read (file_path, offset, limit), Edit, Write. Cursor: Read, Grep, Glob, StrReplace, Write."
MESSAGES = {
    "okf-read": (
        f"Read knowledge/ and .ai/ with okf.py, not the shell: `{OKF} context` (session overview), "
        f"`{OKF} show PATH [PATH...] --outline --depth 2`, `--section HEADING`, `--lines A-B`, `--meta`."
    ),
    "okf-search": (
        f"Search knowledge/ with `{OKF} search PATTERN [--regex 'a|b'] [--under DIR|FILE] [--count]` "
        "(log.md skipped; --include-log adds it)."
    ),
    "okf-list": f"List knowledge/ and .ai/ with `{OKF} context` or `{OKF} list [--long] [--under DIR]`.",
    "read": (
        "Read files with your file-read tool (bounded, line-numbered), not cat/head/tail/sed. "
        f"Without one (Codex): `{REPO} read PATH --lines A-B`, never a whole-file `grep '^'`. {TOOLS}"
    ),
    "search": (
        f"Search file contents with `{REPO} grep PATTERN [--regex 'a|b'] [-i] [--glob '*.rs'] [--under DIR] [--count]` "
        "(or a Grep tool if your harness has one), not grep/rg/git grep."
    ),
    "list": (
        f"Find files with `{REPO} files 'GLOB' [...] [--under DIR] [--depth N]`, e.g. `files 'app/**/*.kt'` or "
        "`files --under app/lib --depth 1` (or a Glob tool if your harness has one), not ls/find/tree/git ls-files."
    ),
    "display": (
        "Do not run tests or apps on the user's live display. Use an isolated virtual display (`xvfb-run -a CMD`, or a "
        "private `Xvfb :NN`), injected input events and a capture/null audio sink. A check that cannot run unattended "
        "that way is out of the batch's scope (.ai/autonomous-execution.md §9.2)."
    ),
    "write": (
        "Create and edit files with your write/edit tools, not heredocs, sed -i, tee, or Python scripts. "
        f"OKF frontmatter: `{OKF} set` / `stamp`. {TOOLS}"
    ),
}


def _strip_heredoc_bodies(command: str) -> str:
    lines = command.split("\n")
    kept: list[str] = []
    pending: list[str] = []
    for line in lines:
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        kept.append(line)
        pending.extend(match.group(2) for match in _HEREDOC_RE.finditer(line))
    return "\n".join(kept)


def _segments(command: str) -> list[tuple[list[str], bool]]:
    """(tokens, reads_from_pipe) for each simple command."""
    result: list[tuple[list[str], bool]] = []
    for line in _strip_heredoc_bodies(command).split("\n"):
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
        current: list[str] = []
        piped = False
        for token in tokens + [";"]:
            if token in SEPARATORS:
                if current:
                    result.append((current, piped))
                piped = token in ("|", "|&")
                current = []
            else:
                current.append(token)
    return result


class Scope:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.cwd_protected = False

    def outside(self, arg: str) -> bool:
        path = Path(os.path.expanduser(arg))
        if not path.is_absolute():
            return False
        if arg.startswith(EXEMPT_PREFIXES):
            return True
        try:
            path.resolve().relative_to(self.root)
        except ValueError:
            return True
        return False

    def protected(self, arg: str) -> bool:
        if self.outside(arg):
            return False
        if self.cwd_protected and not arg.startswith("-"):
            return True
        path = Path(os.path.expanduser(arg))
        if "knowledge" in path.parts:
            return True
        return ".ai" in path.parts and path.suffix in ("", ".md")


def _operands(tokens: list[str]) -> list[str]:
    """Non-option arguments, without redirection operators and their targets."""
    operands: list[str] = []
    skip = False
    for token in tokens[1:]:
        if skip:
            skip = False
        elif token in REDIRECTS:
            skip = True
        elif not token.startswith("-"):
            operands.append(token)
    return operands


def _judge_segment(tokens: list[str], piped: bool, scope: Scope, raw: str) -> str | None:
    while tokens and _ASSIGNMENT_RE.match(tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return None
    prog = os.path.basename(tokens[0])
    operands = _operands(tokens)
    if prog == "cd":
        scope.cwd_protected = bool(operands) and scope.protected(operands[0])
        return None

    for i, token in enumerate(tokens[:-1]):
        if token in (">", ">>") and prog in ("cat", "echo", "printf") and not scope.outside(tokens[i + 1]):
            if not tokens[i + 1].startswith("/dev/"):
                return "write"
    if prog == "tee" and any(not scope.outside(t) for t in operands):
        return "write"
    if prog == "sed" and any(t == "-i" or t.startswith(("-i", "--in-place")) for t in tokens[1:]):
        return "write"
    if prog == "perl" and any(re.match(r"-\w*i", t) for t in tokens[1:]):
        return "write"
    if prog.startswith("python") and "<<" in tokens and _PY_WRITE_RE.search(raw):
        return "write"
    if piped:
        return None

    sub = 1
    while prog == "git" and sub < len(tokens) and tokens[sub].startswith("-"):
        sub += 2 if tokens[sub] in ("-C", "-c") else 1
    if prog == "git" and sub < len(tokens) and tokens[sub] in ("ls-files", "grep", "ls-tree"):
        prog = {"ls-files": "find", "ls-tree": "find", "grep": "grep"}[tokens[sub]]
        tokens = [prog, *tokens[sub + 1 :]]
        operands = _operands(tokens)
        if prog == "find":
            return "okf-list" if any(scope.protected(p) for p in operands) else "list"
    if prog in READERS or (prog == "sed" and "-n" in tokens) or prog == "awk":
        files = operands[1:] if prog in ("sed", "awk") else operands
        files = [f for f in files if not re.fullmatch(r"[+-]?\d+", f)]
        if not files or all(scope.outside(f) for f in files):
            return None
        return "okf-read" if any(scope.protected(f) for f in files) else "read"
    if prog in SEARCHERS:
        if operands and all(scope.outside(f) for f in operands[1:]) and len(operands) > 1:
            return None
        return "okf-search" if any(scope.protected(f) for f in operands[1:]) or scope.cwd_protected else "search"
    if prog in LISTERS:
        if prog == "find" and any(t in ("-exec", "-execdir", "-delete") for t in tokens):
            return None
        paths = operands if prog != "find" else [t for t in tokens[1:2] if not t.startswith("-")]
        if paths and all(scope.outside(p) for p in paths):
            return None
        return "okf-list" if any(scope.protected(p) for p in paths) or scope.cwd_protected else "list"
    return None


def judge(command: str, root: Path) -> str | None:
    """Return a MESSAGES key when the command should be blocked, else None."""
    scope = Scope(root.resolve())
    if _LIVE_DISPLAY_RE.search(_strip_heredoc_bodies(command)):
        return "display"
    try:
        segments = _segments(command)
    except ValueError:
        return None
    for tokens, piped in segments:
        verdict = _judge_segment(tokens, piped, scope, command)
        if verdict:
            return verdict
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    claude = "tool_input" in data
    command = (data.get("tool_input") or {}).get("command") if claude else data.get("command")
    if not isinstance(command, str) or os.environ.get("OKF_SHELL_GUARD") == "off":
        return 0
    roots = data.get("workspace_roots") or []
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or (roots[0] if roots else "") or data.get("cwd") or os.getcwd())
    try:
        verdict = judge(command, root)
    except Exception:  # noqa: BLE001 - a guard bug must never block work
        return 0
    if verdict is None:
        if not claude:
            print(json.dumps({"permission": "allow"}))
        return 0
    message = f"Blocked by .ai/scripts/shell_guard.py: {MESSAGES[verdict]}"
    if claude:
        decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": message}
        print(json.dumps({"hookSpecificOutput": decision}))
    else:
        print(json.dumps({"permission": "deny", "agent_message": message, "user_message": "Shell guard: " + verdict}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
