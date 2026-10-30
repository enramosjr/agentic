"""Bounded, literal GitHub CLI routing shared by lifecycle and review hooks."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import subprocess
from dataclasses import dataclass


class RoutingError(ValueError):
    """An actual PR command cannot be safely assigned to a local worktree."""


@dataclass(frozen=True)
class Invocation:
    directory: str | None
    argv: tuple[str, ...]


# Keep raw word spelling: shlex alone loses the distinction between a quoted
# operator argument and a shell operator. Decode each complete word separately.
TOKEN = re.compile(r'''(?:[^\s;&|()<>\n'"\\]+|'[^']*'|"(?:\\.|[^"\\])*"|\\[\s\S])+|&&|\|\||[;&|()<>\n]''')
OPERATORS = frozenset(('&&', '||', ';', '&', '|', '(', ')', '<', '>', '\n'))


def _dynamic(raw: str) -> bool:
    quote, escaped = '', False
    for char in raw:
        if escaped:
            escaped = False
        elif char == '\\' and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = ''
            elif quote == '"' and char in '$`':
                return True
        elif char in "'\"":
            quote = char
        elif char in '$`*?[]{}~':
            return True
    return False


def recognize(command: str) -> Invocation | None:
    """Recognize executable PR positions; never interpret argument examples."""
    tokens = []
    offset = 0
    malformed = False
    for match in TOKEN.finditer(command):
        if command[offset:match.start()].strip(' \t\r'):
            malformed = True
        raw = match.group()
        offset = match.end()
        if raw.startswith('#'):
            # Shell comments are inert through the end of this line.
            if '\n' not in command[match.start():]:
                break
            malformed = True  # compound/commented PR forms are unsupported
        try:
            value = raw if raw in OPERATORS else shlex.split(raw)[0]
        except (ValueError, IndexError):
            malformed = True
            continue
        tokens.append((raw, value, raw in OPERATORS))
    malformed |= bool(command[offset:].strip(' \t\r'))
    segments, current = [], []
    for token in tokens:
        if token[2]:
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)
    prs = []
    for segment in segments:
        words = [token[1] for token in segment]
        # Wrappers are recognized only to deny unsupported routing, not to
        # silently remove an existing shipping gate around a real command.
        index = 0
        while index < len(words) and (words[index] in ('env', 'command') or
                re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', words[index])):
            index += 1
        if (len(words) >= index + 3 and Path(words[index]).name == 'gh'
                and words[index + 1] == 'pr' and words[index + 2] in ('create', 'ready')):
            prs.append(segment)
    if not prs:
        return None
    error = 'PR routing requires one direct gh command or `cd LITERAL_DIRECTORY && gh pr create|ready ...`'
    if malformed or len(prs) != 1:
        raise RoutingError(error)
    directory = None
    start = 0
    if len(tokens) >= 3 and tokens[0][1] == 'cd':
        if tokens[0][2] or tokens[1][2] or tokens[2][0] != '&&':
            raise RoutingError(error)
        if (not tokens[1][1].strip() or tokens[1][1].startswith('-')
                or _dynamic(tokens[1][0])):
            raise RoutingError('invalid PR routing directory: use a non-empty literal Git worktree path')
        directory, start = tokens[1][1], 3
    remaining = tokens[start:]
    if (any(token[2] for token in remaining) or remaining != prs[0]
            or len(remaining) < 3 or Path(remaining[0][1]).name != 'gh'
            or any(_dynamic(token[0]) for token in remaining[:3])):
        raise RoutingError(error)
    return Invocation(directory, tuple(token[1] for token in remaining))


def operation(data: dict, invocation: Invocation) -> tuple[Path, Path]:
    """Select one validated PR directory/root for every enforcement layer."""
    roots = data.get('workspace_roots') or []
    base = Path(data.get('cwd') or os.environ.get('CLAUDE_PROJECT_DIR') or
                (roots[0] if roots else '') or os.getcwd())
    values = data.get('tool_input') or {}

    def validate(directory: Path, label: str) -> tuple[Path, Path]:
        try:
            directory = directory.resolve()
            if not directory.is_dir():
                raise ValueError('directory does not exist or is not a directory')
            result = subprocess.run(['git', '-C', str(directory), 'rev-parse', '--show-toplevel'],
                                    capture_output=True, text=True, timeout=10,
                                    env={key: value for key, value in os.environ.items()
                                         if not key.startswith('GIT_')})
            if result.returncode or not result.stdout.strip():
                raise ValueError('directory is not a Git worktree')
            return directory, Path(result.stdout.strip()).resolve()
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            raise RoutingError(f'invalid PR routing {label}: {error}; select an existing Git worktree directory') from error

    if 'workdir' in values:
        value = values['workdir']
        if not isinstance(value, str) or not value.strip():
            raise RoutingError('invalid PR routing tool_input.workdir: provide a non-empty directory path')
        base, _ = validate(base / Path(value).expanduser(), 'tool_input.workdir')
    if invocation.directory is not None:
        directory = Path(invocation.directory)
        environment = {**os.environ, **(values.get('env') or {})}
        if (not directory.is_absolute() and (directory.parts[0] if directory.parts else '.') not in ('.', '..')
                and not invocation.directory.startswith('./') and environment.get('CDPATH')):
            raise RoutingError('ambiguous PR routing with CDPATH; use an absolute path or ./ prefix')
        if not directory.is_absolute() and '..' in directory.parts:
            pwd = Path(environment.get('PWD') or str(base))
            if pwd.resolve() == base.resolve() and os.path.normpath(str(pwd)) != os.path.normpath(str(base)):
                raise RoutingError('ambiguous PR routing with logical PWD; use an absolute path')
        joined = base / directory
        logical = Path(os.path.normpath(str(joined)))
        if logical.resolve() != joined.resolve():
            raise RoutingError('ambiguous PR routing through symlink and ..; use an unambiguous absolute path')
        base = joined
    return validate(base, 'directory')
