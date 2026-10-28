#!/usr/bin/env python3
"""Requirement assurance status for lifecycle.py: capability obligations evaluated against ledger evidence.

A structured capability requirement may declare `- Verify:` (one backticked command, or `manual`
and a reason) and `- Inputs:` (backticked repo-relative globs) before its first scenario. Evidence
is a `req:<ID>` ledger entry in a lifecycle record; freshness is the ledger's own verdict. This
module reads files and writes nothing. It imports neither lifecycle.py nor its state.

Standard library only; Python 3.9+.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

sys.dont_write_bytecode = True  # Bytecode beside the scripts would dirty the work tree.

import brownfield  # noqa: E402
import ledger  # noqa: E402

SCHEMA_VERSION = 1
RECORDS_EXCLUDE = '!knowledge/history/lifecycle/**'  # Recording evidence must not stale it.
FAILING = ('STALE', 'FAILED', 'UNVERIFIED', 'INVALID')
STATUSES = ('VERIFIED', *FAILING, 'MANUAL', 'UNDECLARED')
VERIFY = re.compile(r'^\s+[-*] Verify:(.*)$')
INPUTS = re.compile(r'^\s+[-*] Inputs:(.*)$')
SCENARIO = re.compile(r'^\s+[-*] Scenario [^:\r\n]+:')
COMMAND = re.compile(r'^`([^`]*)`$')
MANUAL = re.compile(r'^manual(?![\w-])\s*[-–—:]?\s*(.*)$')
SPAN = re.compile(r'`([^`]*)`')
WHOLE_TREE = 'no Inputs: declared, so the whole tree counts'


@dataclass(frozen=True)
class Obligation:
    id: str
    capability: str
    argv: tuple = ()
    manual: str | None = None
    globs: tuple = ()
    invalid: str | None = None
    declared: bool = True

    @property
    def evidence_globs(self) -> list[str]:
        return [*self.globs, RECORDS_EXCLUDE] if self.globs else []


def parse(rid: str, capability: str, raw: str) -> Obligation:
    """The obligation a requirement block declares, or why it is INVALID."""
    found: dict[str, str] = {}
    scenario = False
    for line in raw.splitlines()[1:]:
        if SCENARIO.match(line):
            scenario = True
            continue
        for kind, pattern in (('Verify', VERIFY), ('Inputs', INPUTS)):
            match = pattern.match(line)
            if not match:
                continue
            if scenario:
                return Obligation(rid, capability, invalid=f'{kind}: line after a scenario')
            if kind in found:
                return Obligation(rid, capability, invalid=f'duplicate {kind}: line')
            found[kind] = match[1].strip()
    if 'Verify' not in found:
        if 'Inputs' in found:
            return Obligation(rid, capability, invalid='Inputs: without Verify:')
        return Obligation(rid, capability, declared=False)
    globs: tuple = ()
    if 'Inputs' in found:
        spans = SPAN.findall(found['Inputs'])
        rest = SPAN.sub('', found['Inputs']).replace(',', ' ').strip()
        if not spans or rest:
            return Obligation(rid, capability, invalid='Inputs: needs one or more backticked globs')
        try:
            globs = tuple(ledger.check_globs(spans))
        except ValueError as error:
            return Obligation(rid, capability, invalid='Inputs: ' + str(error).replace('--inputs ', ''))
    value = found['Verify']
    manual = MANUAL.match(value)
    if manual:
        if not manual[1].strip():
            return Obligation(rid, capability, invalid='Verify: manual needs a reason')
        return Obligation(rid, capability, manual=manual[1].strip(), globs=globs)
    command = COMMAND.match(value)
    if not command:
        return Obligation(rid, capability, invalid='Verify: needs one backticked command, or manual and a reason')
    try:
        argv = tuple(shlex.split(command[1]))
    except ValueError as error:
        return Obligation(rid, capability, invalid=f'Verify: command cannot be parsed ({error})')
    if not argv:
        return Obligation(rid, capability, invalid='Verify: command is empty')
    return Obligation(rid, capability, argv=argv, globs=globs)


def requirements(root: Path) -> tuple[list[Obligation], list[str]]:
    """Obligations of every structured capability; prose capabilities have none. Diagnostics name unreadable files."""
    directory = root / 'knowledge/capabilities'
    found: list[Obligation] = []
    diagnostics: list[str] = []
    if not directory.is_dir():
        return found, diagnostics
    for path in sorted(directory.rglob('*.md')):
        if path.name in ('index.md', 'log.md') or not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        try:
            text = brownfield.read(path)
            meta, spans = brownfield.document(text)
            if not meta.get('namespace') or 'requirements' not in spans:
                continue
            blocks = brownfield.blocks(text, spans['requirements'])
        except (OSError, UnicodeError, ValueError) as error:
            diagnostics.append(f'{relative}: capability cannot be parsed ({error})')
            continue
        found.extend(parse(rid, relative, block.raw) for rid, block in blocks.items())
    return found, diagnostics


@dataclass(frozen=True)
class Evidence:
    record: str
    index: int
    entry: dict

    @property
    def order(self) -> tuple:
        return (str(self.entry.get('at') or ''), self.record, self.index)


def evidence(records_dir: Path, state: dict | None) -> tuple[list[Evidence], list[str]]:
    """`req:` ledger entries from committed records and the active state; malformed records contribute nothing."""
    items: list[Evidence] = []
    diagnostics: list[str] = []
    active = state.get('task') if isinstance(state, dict) else None

    def add(name: str, record: object) -> None:
        if not isinstance(record, dict):
            diagnostics.append(f'{name}: record is not a JSON object; ignored')
            return
        problems = ledger.audit(record.get('ledger'))
        if problems:
            diagnostics.append(f'{name}: {problems[0]}; ignored')
            return
        for index, entry in enumerate(record.get('ledger') or []):
            if str(entry.get('label', '')).startswith('req:'):
                items.append(Evidence(name, index, entry))

    files = sorted(records_dir.glob('*.json')) if records_dir.is_dir() else []
    for path in files:
        if active and path.stem == active:
            continue  # The working state is newer than its own published record.
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError) as error:
            diagnostics.append(f'{path.name}: unreadable record ({type(error).__name__}); ignored')
            continue
        add(path.name, record)
    if isinstance(state, dict):
        add(f'{active}.json' if active else 'active state', state)
    return items, diagnostics


def result(obligation: Obligation, status: str, reason: str, basis: str = 'none', found: Evidence | None = None) -> dict:
    record = None
    if found is not None:
        record = {'record': found.record, 'head': found.entry.get('head'),
                  'at': found.entry.get('at'), 'exit': found.entry.get('exit')}
    return {'id': obligation.id, 'capability': obligation.capability, 'status': status,
            'basis': basis, 'evidence': record, 'reason': reason}


def evaluate(root: Path, obligation: Obligation, items: list[Evidence], tree: str) -> dict:
    """One requirement's status: only a passing, current ledger entry for this exact obligation is VERIFIED."""
    if obligation.invalid:
        return result(obligation, 'INVALID', obligation.invalid)
    if not obligation.declared:
        return result(obligation, 'UNDECLARED', 'no Verify: line')
    if obligation.manual is not None:
        return result(obligation, 'MANUAL', 'human judgment: ' + obligation.manual, 'declared')
    label = 'req:' + obligation.id
    mine = [item for item in items if item.entry.get('label') == label]
    matching = [item for item in mine if item.entry.get('argv') == list(obligation.argv)
                and (item.entry.get('inputs') or []) == obligation.evidence_globs]
    hint = f'run `python3 .ai/scripts/lifecycle.py assure --run {obligation.id}`'
    if not matching:
        if mine:
            return result(obligation, 'UNVERIFIED', f'evidence is for a different command or inputs; {hint}')
        return result(obligation, 'UNVERIFIED', f'no evidence; {hint}')
    newest = max(matching, key=lambda item: item.order)
    if newest.entry.get('exit') != 0:
        return result(obligation, 'FAILED', f"newest run exited {newest.entry.get('exit')}", 'mechanical', newest)
    current, text = ledger._entry_verdict(root, newest.entry, tree)
    if current:
        scope = 'the identical tree' if not obligation.globs else 'unchanged inputs'
        return result(obligation, 'VERIFIED', f'passed on {scope}; covers only this command on these inputs', 'mechanical', newest)
    if not obligation.globs:
        text = WHOLE_TREE + ', and the tree changed since the run'
    return result(obligation, 'STALE', f'{text}; {hint}', 'mechanical', newest)


def selected(globs: list[str], path: str) -> bool:
    """The same include/exclude order `ledger.input_paths` applies: the last matching glob wins."""
    chosen = False
    for glob in globs:
        negative = glob.startswith('!')
        if ledger.matches(glob[1:] if negative else glob, path):
            chosen = not negative
    return chosen


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True, timeout=60)


def changed(root: Path, base: str, obligations: list[Obligation]) -> list[tuple[Obligation, str]]:
    """Obligations a change from BASE to the working tree may affect, with why; ValueError for a bad BASE."""
    if not base or base.startswith('-'):
        raise ValueError(f'invalid --base {base!r}')
    resolved = _git(root, 'rev-parse', '--verify', '--quiet', base + '^{commit}')
    if resolved.returncode:
        raise ValueError(f'--base {base!r} is not a commit')
    diff = _git(root, 'diff', '--name-only', resolved.stdout.strip(), '--')
    others = _git(root, 'ls-files', '--others', '--exclude-standard')
    if diff.returncode or others.returncode:
        raise ValueError('cannot list changed files: ' + (diff.stderr or others.stderr).strip())
    files = sorted(set(diff.stdout.splitlines()) | set(others.stdout.splitlines()))
    listed = []
    for obligation in obligations:
        if not obligation.declared:
            continue
        if obligation.invalid:
            listed.append((obligation, 'obligation is invalid, so its scope is unknown'))
        elif not obligation.globs:
            listed.append((obligation, WHOLE_TREE))
        else:
            hits = [name for name in files if selected(obligation.evidence_globs, name)]
            if hits:
                listed.append((obligation, 'inputs changed: ' + ', '.join(hits[:8]) + (' ...' if len(hits) > 8 else '')))
    return listed


def exit_code(results: list[dict], strict: bool, broken: bool) -> int:
    failing = FAILING + (('UNDECLARED',) if strict else ())
    return 1 if broken or any(item['status'] in failing for item in results) else 0


def summary(results: list[dict]) -> dict:
    return {status: sum(item['status'] == status for item in results) for status in STATUSES}


def render(results: list[dict], diagnostics: list[str]) -> str:
    lines = []
    for item in results:
        evidence = item['evidence']
        where = f" head={str(evidence['head'] or '?')[:7]} at={evidence['at']}" if evidence else ''
        lines.append(f"{item['status']:<10} {item['id']} {item['capability']}{where} - {item['reason']}")
    if not results:
        lines.append('assure: no structured capability requirements')
    lines.extend('diagnostic: ' + text for text in diagnostics)
    counts = summary(results)
    lines.append('assure: ' + ', '.join(f'{counts[s]} {s}' for s in STATUSES if counts[s]) if results else 'assure: 0 requirements')
    return '\n'.join(lines)


def document(results: list[dict], diagnostics: list[str], base: str | None = None) -> dict:
    data = {'schema_version': SCHEMA_VERSION, 'requirements': results, 'diagnostics': diagnostics,
            'summary': summary(results)}
    if base is not None:
        data['changed_base'] = base
    return data
