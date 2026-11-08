#!/usr/bin/env python3
"""Read-only source hygiene for AGENTIC itself; adopter task artifacts are unchanged."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

import project_context


class PolicyError(ValueError):
    """Framework identity or source assets violate the artifact boundary."""


GUIDANCE = (
    'AGENTIC framework source uses intent, planning, and review in chat. '
    'Do not create self-task specs, plans, review/verification reports, knowledge/, '
    'lifecycle records, or lesson records, including in Git scratch. '
    'Run tests directly; keep only maintained product assets in source_documents.'
)
DOCUMENT_SUFFIXES = {'.md', '.markdown', '.rst', '.adoc'}
FORBIDDEN = ('knowledge', 'docs', '.ai/install-manifest.json', '.ai/plans', '.ai/specifications', '.ai/reviews',
             '.ai/history', '.ai/records', 'history/lifecycle')
OPERATIONAL = {'.git', '.worktrees', '__pycache__', 'node_modules', '.venv', 'venv',
               '.pytest_cache', '.mypy_cache', '.ruff_cache', '.cache', 'build', 'dist'}
KIT_ROOTS = {'.ai', '.claude', '.codex', '.cursor', '.agents'}


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=30)
    if result.returncode:
        raise PolicyError(result.stderr.decode('utf-8', errors='replace').strip())
    return result.stdout


def forbidden(name: str) -> bool:
    name = name.replace('\\', '/').strip('/').casefold()
    if name.startswith(('.ai/scripts/tests/fixtures/', '.ai/templates/')):
        return False  # Explicit reusable examples are source assets, not framework task state.
    return (any(name == part or name.startswith(part + '/') for part in FORBIDDEN)
            or '/history/lifecycle/' in '/' + name + '/'
            or (Path(name).name.startswith('lifecycle-') and name.endswith('.json')))


def document(name: str) -> bool:
    return (PurePosixPath(name).suffix.casefold() in DOCUMENT_SUFFIXES
            or name.casefold().startswith('.ai/docs/'))


def inventory(data: dict) -> set[str]:
    if data.get('repository_kind') != 'framework':
        raise PolicyError('source hygiene requires explicit repository_kind: framework')
    values = data.get('source_documents')
    if not isinstance(values, list):
        raise PolicyError('framework .agentic.json needs an explicit source_documents inventory')
    names: set[str] = set()
    folded: set[str] = set()
    for name in values:
        if (not isinstance(name, str) or not name or '\\' in name or ':' in name
                or any(ord(c) < 32 for c in name) or PurePosixPath(name).is_absolute()
                or not PurePosixPath(name).parts or '.git' in PurePosixPath(name).parts
                or '..' in PurePosixPath(name).parts or PurePosixPath(name).as_posix() != name
                or name.startswith('.git/') or forbidden(name) or name.casefold() in folded):
            raise PolicyError(f'unsafe or duplicate source_documents entry: {name!r}')
        names.add(name)
        folded.add(name.casefold())
    return names


def contents(root: Path, name: str, snapshot: str) -> bytes:
    if snapshot == 'working':
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()):
            raise PolicyError(f'source document escapes framework: {name}')
        return path.read_bytes()
    return git(root, 'show', (':' if snapshot == 'index' else 'HEAD:') + name)


def source_inventory(root: Path, snapshot: str = 'working') -> set[str]:
    try:
        data = json.loads(contents(root, '.agentic.json', snapshot))
    except (OSError, ValueError) as error:
        raise PolicyError(f'invalid framework .agentic.json: {error}') from error
    if not isinstance(data, dict):
        raise PolicyError('framework .agentic.json must be an object')
    return inventory(data)


def paths(root: Path, snapshot: str) -> set[str]:
    if snapshot != 'working':
        args = ('ls-files', '-z') if snapshot == 'index' else ('ls-tree', '-rz', '--name-only', 'HEAD')
        return {p.decode('utf-8', errors='surrogateescape') for p in git(root, *args).split(b'\0') if p}
    found: set[str] = set()
    for directory, directories, files in os.walk(root, followlinks=False):
        selected = []
        for name in directories:
            child = Path(directory) / name
            rel = child.relative_to(root)
            if name in {'.git', '__pycache__'} or (len(rel.parts) == 1 and name in OPERATIONAL):
                continue
            if rel.parts[0] not in KIT_ROOTS and (child / '.git').exists():
                continue
            selected.append(name)
        directories[:] = selected
        for name in files:
            found.add((Path(directory) / name).relative_to(root).as_posix())
    # Tracked files stay visible even inside otherwise operational directories.
    if (root / '.git').exists():
        for name in paths(root, 'index'):
            path = root / name
            if path.is_file():
                actual = path.resolve()
                found.add(actual.relative_to(root.resolve()).as_posix()
                          if actual.is_relative_to(root.resolve()) else name)
    if (root / 'knowledge').exists():
        found.add('knowledge')
    return found


def validate(root: Path, snapshot: str = 'working') -> None:
    allowed = source_inventory(root, snapshot)
    bad = []
    for name in sorted(paths(root, snapshot)):
        if forbidden(name) or (document(name) and name not in allowed):
            bad.append(name)
        elif document(name):
            contents(root, name, snapshot)  # Also reject escaping working-tree aliases.
    if bad:
        raise PolicyError('framework task artifacts/unregistered source documents: '
                          + ', '.join(repr(name) for name in bad) + '. ' + GUIDANCE)


def validate_source(root: Path) -> None:
    """Installer preflight; unwrapped templates and adopter re-exports retain their contract."""
    if project_context.kind(root) == 'framework':
        validate(root)


def edit_problem(root: Path, targets: list[Path], removed: set[Path]) -> str | None:
    allowed = source_inventory(root)
    for path in targets:
        absolute = Path(os.path.abspath(path))
        if absolute in removed:
            continue
        try:
            name = absolute.relative_to(root.resolve()).as_posix()
        except ValueError:
            # A linked worktree's common Git scratch is outside the worktree.
            common = Path(git(root, 'rev-parse', '--git-common-dir').decode().strip())
            common = (root / common).resolve()
            if absolute.is_relative_to(common) and (document(absolute.name) or forbidden(absolute.as_posix())):
                return f'framework self-task artifact refused: {absolute}. {GUIDANCE}'
            continue
        if os.name == 'nt' and absolute.exists() and absolute.resolve().is_relative_to(root.resolve()):
            name = absolute.resolve().relative_to(root.resolve()).as_posix()
        if forbidden(name) or (document(name) and name not in allowed):
            return f'framework self-task artifact refused: {name}. {GUIDANCE}'
        if document(name) and not absolute.resolve().is_relative_to(root.resolve()):
            return f'source document escapes framework: {name}'
    return None


def adopter_task(root: Path, *, exact_target: bool = False) -> Path:
    """Admission check before any adopter task producer or its lease writes."""
    root = Path(root)
    owner = root
    if not exact_target:
        result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'],
                                capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            owner = Path(result.stdout.strip())
    try:
        role = project_context.kind(owner)
    except (ValueError, OSError) as error:
        raise PolicyError(f'invalid repository identity: {error}') from error
    if role == 'framework':
        raise PolicyError('framework source does not run its own adopter task workflow. ' + GUIDANCE)
    return root


def ordinary_git(invocation: dict) -> None:
    """Do not check the normal index while a command selects another namespace."""
    selectors = {'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE',
                 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES'}
    if any(value and (key.upper() in selectors or key.upper().startswith('GIT_CONFIG_'))
           for key, value in invocation['env'].items()):
        raise PolicyError('framework publication requires an ordinary checkout/index, without Git namespace overrides')
    prefix = list(invocation['prefix'])
    while prefix:
        value = prefix.pop(0)
        if value == '-C' and prefix:
            prefix.pop(0)
        elif value.startswith('-C') and len(value) > 2 or value == '--no-pager':
            continue
        else:
            raise PolicyError('framework publication requires ordinary Git or literal git -C routing')


def checked_ref(root: Path, value: str) -> None:
    if value == 'HEAD':
        return
    branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD').decode().strip()
    if value not in ('HEAD', branch, 'refs/heads/' + branch):
        raise PolicyError('framework publication must select the checked-out HEAD/current branch, not an unchecked ref')


def push_refs(root: Path, arguments: list[str]) -> None:
    positional = []
    flags = {'-u', '--set-upstream', '-f', '--force', '--force-with-lease',
             '--force-if-includes', '--atomic', '--porcelain', '--progress',
             '-v', '--verbose', '-q', '--quiet', '-n', '--dry-run', '--no-verify'}
    for arg in arguments:
        if arg in flags or arg.startswith('--force-with-lease='):
            continue
        if arg.startswith('-'):
            raise PolicyError('framework push needs an explicit remote and current-branch refspec')
        positional.append(arg)
    if len(positional) < 2:
        raise PolicyError('framework push needs an explicit remote and current-branch refspec')
    for ref in positional[1:]:
        checked_ref(root, ref.lstrip('+').split(':', 1)[0])


def pr_head(root: Path, arguments: tuple[str, ...]) -> None:
    for index, arg in enumerate(arguments):
        if arg in ('--head', '-H'):
            if index + 1 >= len(arguments):
                raise PolicyError('PR head is missing')
            checked_ref(root, arguments[index + 1])
        elif arg.startswith('--head='):
            checked_ref(root, arg.split('=', 1)[1])
        elif arg.startswith('-H') and len(arg) > 2:
            checked_ref(root, arg[2:])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--snapshot', choices=('working', 'index', 'head'), default='working')
    args = parser.parse_args(argv)
    try:
        validate(args.root.resolve(), args.snapshot)
    except (PolicyError, OSError, subprocess.TimeoutExpired) as error:
        print(f'framework hygiene: {error}', file=sys.stderr)
        return 1
    print(f'framework hygiene: PASS ({args.snapshot})')
    return 0


if __name__ == '__main__':
    import process_runtime
    process_runtime.configure_windows_environment()
    raise SystemExit(main())
