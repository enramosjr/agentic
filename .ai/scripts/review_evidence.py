#!/usr/bin/env python3
"""Review-report helpers for the assurance report: the semantics `lifecycle.py` applies to review stages.

`lifecycle.py` hashes a review ref, reads its verdict and checks `## Validation Reviewed` citations;
`assurance.py` must do the same without importing it. These are stdlib-only copies, held equal by
`tests/test_review_evidence.py` (a corpus parity test and a check on the converge regex). This module
reads files and writes nothing.

Standard library only; Python 3.9+.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re

BOUNDARY = r'(?<![\w-]){}(?![\w-])'  # lifecycle.converge_problem's citation rule, with the id in the braces.
PIN = re.compile(r'@([0-9A-Fa-f]{12,})(?![\w-])')


def body(text: str) -> str:
    if text.startswith('---\n'):
        end = text.find('\n---', 4)
        if end != -1:
            return text[end + 4:]
    return text


def sections(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in body(text).splitlines():
        match = re.match(r'^##\s+(.*?)\s*$', line)
        if match:
            current = result.setdefault(match.group(1).lower(), [])
        elif current is not None:
            current.append(line)
    return result


def find_section(found: dict[str, list[str]], key: str) -> list[str] | None:
    for heading, lines in found.items():
        if heading.startswith(key):
            return lines
    return None


def reviewed_section(text: str) -> str:
    """The `## Validation Reviewed` section, or ''."""
    return '\n'.join(find_section(sections(text), 'validation reviewed') or [])


def verdict(text: str) -> str:
    """The first non-blank line after the `## Verdict` heading, or ''."""
    lines = body(text).splitlines()
    for index, line in enumerate(lines):
        if re.match(r'^##\s+Verdict\b', line, re.I):
            for follow in lines[index + 1:]:
                if follow.strip():
                    return follow.strip()
    return ''


def approved(text: str) -> bool:
    return verdict(text).lower().startswith('approved')


def read_verdict(path: Path) -> str:
    return verdict(path.read_text())


def _digest(path: Path, text: str | None = None) -> str:
    if path.suffix == '.md':
        return hashlib.sha256(body(path.read_text() if text is None else text).strip().encode()).hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref_hash(path: Path) -> str:
    """sha256 of a stage artifact; for Markdown only the body, so frontmatter stamps do not count as edits."""
    return _digest(path)


def load_review(path: Path) -> tuple[str, str]:
    """(digest, text) of a review report, reading it once."""
    text = path.read_text()
    return _digest(path, text), text


def citations(section: str, rid: str) -> list[tuple[str, str]]:
    """Each citation of RID in SECTION: ('plain', ''), ('pin', hex) or ('malformed', '@text')."""
    found = []
    for match in re.finditer(BOUNDARY.format(re.escape(rid)), section):
        rest = section[match.end():]
        if not rest.startswith('@'):
            found.append(('plain', ''))
            continue
        pin = PIN.match(rest)
        found.append(('pin', pin[1]) if pin else ('malformed', re.match(r'@\S*', rest)[0]))
    return found
