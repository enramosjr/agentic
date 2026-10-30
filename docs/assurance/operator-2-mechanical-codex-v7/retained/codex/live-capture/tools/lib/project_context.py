"""Explicit project identity and read-only startup diagnostics; no bootstrap."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess


def kind(root: Path) -> str:
    marker = root / '.agentic.json'
    if marker.is_file():
        value = json.loads(marker.read_text())
        role = value.get('repository_kind') if isinstance(value, dict) else None
        if role not in ('framework', 'adopter'):
            raise ValueError('.agentic.json: repository_kind must be framework or adopter')
        if role == 'framework' and (root / '.ai/install-manifest.json').exists():
            raise ValueError('repository_kind conflicts with an installed adopter manifest')
        return role
    if (root / '.ai/install-manifest.json').is_file() or (root / 'knowledge/index.md').is_file():
        return 'adopter'
    return 'unknown'


def git(root: Path, *args: str):
    return subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True, timeout=10)


def report(root: Path) -> dict:
    data = {'schema_version': 1, 'root': str(root.resolve()), 'repository_kind': kind(root)}
    head = git(root, 'rev-parse', '--verify', 'HEAD')
    branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD')
    upstream = git(root, 'rev-parse', '--abbrev-ref', '@{upstream}')
    freshness, ahead, behind = 'no-upstream', None, None
    if upstream.returncode == 0:
        counts = git(root, 'rev-list', '--left-right', '--count', 'HEAD...@{upstream}')
        if counts.returncode == 0:
            ahead, behind = map(int, counts.stdout.split())
            freshness = 'diverged' if ahead and behind else 'behind' if behind else 'ahead' if ahead else 'equal'
        else:
            freshness = 'unknown'
    data['git'] = {'head': head.stdout.strip() if head.returncode == 0 else None,
                   'branch': branch.stdout.strip() if branch.returncode == 0 else None,
                   'upstream': upstream.stdout.strip() if upstream.returncode == 0 else None,
                   'freshness': freshness, 'ahead': ahead, 'behind': behind,
                   'remote_verified': False,
                   'note': 'Local refs only; no fetch or remote authentication was attempted.',
                   'author_configured': git(root, 'var', 'GIT_AUTHOR_IDENT').returncode == 0,
                   'committer_configured': git(root, 'var', 'GIT_COMMITTER_IDENT').returncode == 0,
                   'dirty': bool(git(root, 'status', '--porcelain').stdout.strip())}
    data['discovery'] = {
        'commands': 'python3 .ai/scripts/repo.py commands TOOL [SUBCOMMAND]',
        'headings': 'python3 .ai/scripts/repo.py headings PATH',
        'tools': ['repo', 'lifecycle', 'okf', 'install', 'artifacts', 'autonomy_validation', 'validation_select']}
    return data
