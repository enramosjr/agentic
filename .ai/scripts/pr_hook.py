"""Bounded, literal GitHub CLI routing shared by lifecycle and review hooks."""
from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath
import re
import shlex
import subprocess
from dataclasses import dataclass


class RoutingError(ValueError):
    """An actual PR command cannot be safely assigned to a local worktree."""


def check_directory_spelling(value: str, label: str) -> None:
    """Refuse paths whose drive-local cwd is not represented in the hook event."""
    if os.name == 'nt':
        path = PureWindowsPath(value)
        if path.drive and not path.root:
            raise RoutingError(f'ambiguous {label}: drive-relative paths are unsupported; use a fully qualified or plain relative path')


@dataclass(frozen=True)
class Invocation:
    directory: str | None
    argv: tuple[str, ...]


# Keep raw word spelling: shlex alone loses the distinction between a quoted
# operator argument and a shell operator. Decode each complete word separately.
TOKEN = re.compile(r'''(?:[^\s;&|()<>\n'"\\]+|'[^']*'|"(?:\\.|[^"\\])*"|\\[\s\S])+|&&|\|\||[;&|()<>\n]''')
WINDOWS_TOKEN = re.compile(r'''(?:[^\s;&|()<>\n'"]+|'(?:[^']|'')*'|"(?:[^"]|"")*")+|&&|\|\||[;&|()<>\n]''')
OPERATORS = frozenset(('&&', '||', ';', '&', '|', '(', ')', '<', '>', '\n'))


def split_words(text: str) -> list[str]:
    """Decode literal shell words without treating Windows path separators as escapes."""
    if os.name == 'nt':
        words, current, quote = [], [], None
        started, index = False, 0
        while index < len(text):
            char = text[index]
            if quote:
                if char == quote:
                    if index + 1 < len(text) and text[index + 1] == quote:
                        current.append(char)
                        index += 2
                        continue
                    quote = None
                else:
                    current.append(char)
            elif char in "'\"":
                quote, started = char, True
            elif char.isspace():
                if started:
                    words.append(''.join(current))
                    current, started = [], False
            else:
                current.append(char)
                started = True
            index += 1
        if quote:
            raise ValueError('unclosed literal quote')
        if started:
            words.append(''.join(current))
        return words
    lexer = shlex.shlex(text, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ''
    return list(lexer)


def _gh(value: str) -> bool:
    return Path(value).name.lower() in (('gh', 'gh.exe') if os.name == 'nt' else ('gh',))


def _dynamic(raw: str) -> bool:
    quote, escaped = '', False
    for index, char in enumerate(raw):
        if escaped:
            escaped = False
        elif char == '\\' and quote != "'" and os.name != 'nt':
            escaped = True
        elif quote:
            if char == quote:
                quote = ''
            elif quote == '"' and char in '$`':
                return True
        elif char in "'\"":
            quote = char
        elif char == '~' and os.name == 'nt':
            # A DOS short-name component is literal, unlike a home selector.
            component = re.split(r'[\\/:=]', raw[:index])[-1] + raw[index:]
            component = re.split(r'[\\/]', component, maxsplit=1)[0]
            if (len(component.partition('.')[0]) <= 8 and
                    re.fullmatch(r"[\w!#%&'()@^-]{1,6}~[0-9]{1,6}(?:\.[\w!#%&'()@^-]{1,3})?", component)):
                continue
            return True
        elif char in '$`*?[]{}~':
            return True
    return False


def recognize(command: str) -> Invocation | None:
    """Recognize executable PR positions; never interpret argument examples."""
    tokens = []
    offset = 0
    malformed = False
    for match in (WINDOWS_TOKEN if os.name == 'nt' else TOKEN).finditer(command):
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
            decoded = [raw] if raw in OPERATORS else split_words(raw)
            if len(decoded) != 1:
                raise ValueError('invalid literal token')
            value = decoded[0]
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
        if (len(words) >= index + 3 and _gh(words[index])
                and words[index + 1] == 'pr' and words[index + 2] in ('create', 'ready')):
            prs.append(segment)
    if not prs:
        return None
    error = 'PR routing requires one direct gh command or `cd LITERAL_DIRECTORY && gh pr create|ready ...`'
    if os.name == 'nt':
        error = ('PR routing requires one direct gh command or one literal Set-Location/cd prefix; '
                 'use tool_input.workdir for other directory state')
    if malformed or len(prs) != 1:
        raise RoutingError(error)
    if os.name == 'nt' and tokens[:1] and tokens[0][0] == '&':
        tokens = tokens[1:]
    directory = None
    start = 0
    locations = ('cd', 'chdir', 'sl', 'set-location') if os.name == 'nt' else ('cd',)
    first = tokens[0][1].lower() if os.name == 'nt' and tokens else tokens[0][1] if tokens else ''
    if first in locations:
        separator = next((n for n, token in enumerate(tokens) if token[2]), len(tokens))
        allowed = ('&&', ';', '\n') if os.name == 'nt' else ('&&',)
        arguments = tokens[1:separator]
        if os.name == 'nt' and arguments and arguments[0][1].lower() in ('-literalpath', '-path'):
            arguments = arguments[1:]
        if (tokens[0][2] or len(arguments) != 1 or separator >= len(tokens)
                or tokens[separator][0] not in allowed):
            raise RoutingError(error)
        if (not arguments[0][1].strip() or arguments[0][1].startswith('-')
                or _dynamic(arguments[0][0])):
            raise RoutingError('invalid PR routing directory: use a non-empty literal Git worktree path')
        directory, start = arguments[0][1], separator + 1
    remaining = tokens[start:]
    if os.name == 'nt' and remaining[:1] and remaining[0][0] == '&':
        remaining = remaining[1:]
    if (any(token[2] for token in remaining) or remaining != prs[0]
            or len(remaining) < 3 or not _gh(remaining[0][1])
            or any(_dynamic(token[0]) for token in remaining[:3])):
        raise RoutingError(error)
    return Invocation(directory, tuple(token[1] for token in remaining))


def operation(data: dict, invocation: Invocation) -> tuple[Path, Path]:
    """Select one validated PR directory/root for every enforcement layer."""
    roots = data.get('workspace_roots') or []
    base = Path(data.get('cwd') or os.environ.get('CLAUDE_PROJECT_DIR') or
                (roots[0] if roots else '') or os.getcwd())
    check_directory_spelling(str(base), 'session cwd')
    values = data.get('tool_input') or {}

    def validate(directory: Path, label: str) -> tuple[Path, Path]:
        try:
            directory = directory.resolve()
            if not directory.is_dir():
                raise ValueError('directory does not exist or is not a directory')
            import review_guard
            result = subprocess.run(['git', '-C', str(directory), 'rev-parse', '--show-toplevel'],
                                     capture_output=True, text=True, encoding='utf-8', timeout=10,
                                    env=review_guard.git_environment())
            if result.returncode or not result.stdout.strip():
                raise ValueError('directory is not a Git worktree')
            return directory, Path(result.stdout.strip()).resolve()
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            raise RoutingError(f'invalid PR routing {label}: {error}; select an existing Git worktree directory') from error

    if 'workdir' in values:
        value = values['workdir']
        if not isinstance(value, str) or not value.strip():
            raise RoutingError('invalid PR routing tool_input.workdir: provide a non-empty directory path')
        check_directory_spelling(value, 'PR routing tool_input.workdir')
        base, _ = validate(base / Path(value).expanduser(), 'tool_input.workdir')
    if invocation.directory is not None:
        check_directory_spelling(invocation.directory, 'PR routing directory')
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
        # Windows resolves lexical '..' before following a directory junction.
        # Inspect the prefix explicitly, rather than trusting resolve() to expose
        # the same alias/parent ambiguity as a POSIX physical-directory lookup.
        cursor = Path(joined.anchor)
        for part in joined.parts[1 if joined.anchor else 0:]:
            if part == '..' and cursor.resolve() != cursor.absolute():
                raise RoutingError('ambiguous PR routing through symlink and ..; use an unambiguous absolute path')
            cursor /= part
        logical = Path(os.path.normpath(str(joined)))
        if logical.resolve() != joined.resolve():
            raise RoutingError('ambiguous PR routing through symlink and ..; use an unambiguous absolute path')
        base = joined
    return validate(base, 'directory')
