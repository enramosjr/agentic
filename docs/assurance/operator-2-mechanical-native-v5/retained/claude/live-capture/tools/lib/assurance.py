#!/usr/bin/env python3
"""Requirement assurance status for lifecycle.py: capability obligations evaluated against ledger evidence.

A structured capability requirement may declare `- Verify:` (one backticked command, or `manual`
and a reason) and `- Inputs:` (backticked repo-relative globs) before its first scenario. Evidence
is a `req:<ID>` ledger entry in a lifecycle record; freshness is the ledger's own verdict. This
module reads files and writes nothing. It imports neither lifecycle.py nor its state.

Standard library only; Python 3.9+.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
import datetime
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

sys.dont_write_bytecode = True  # Bytecode beside the scripts would dirty the work tree.

import brownfield  # noqa: E402
import ledger  # noqa: E402
import review_evidence  # noqa: E402

SCHEMA_VERSION = 1
RECORDS_EXCLUDE = '!knowledge/history/lifecycle/**'  # Recording evidence must not stale it.
FAILING = ('STALE', 'FAILED', 'UNVERIFIED', 'INVALID')
STATUSES = ('VERIFIED', *FAILING, 'MANUAL', 'UNDECLARED')
VERIFY = re.compile(r'^\s+[-*] Verify:(.*)$')
INPUTS = re.compile(r'^\s+[-*] Inputs:(.*)$')
RISK = re.compile(r'^\s+[-*] Accept-risk:(.*)$')
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
    risk: tuple = ()  # (until, by, reason) of a valid Accept-risk: line
    block_sha256: str = ''

    @property
    def evidence_globs(self) -> list[str]:
        return [*self.globs, RECORDS_EXCLUDE] if self.globs else []


def parse_risk(value: str) -> tuple | str:
    """(until, by, reason) of an `Accept-risk:` value, or why it is malformed."""
    parts = value.split(None, 1)
    until = parts[0] if parts else ''
    try:
        if not re.match(r'^\d{4}-\d\d-\d\d$', until):
            raise ValueError(until)
        datetime.date.fromisoformat(until)
    except ValueError:
        return 'Accept-risk: date must be a valid YYYY-MM-DD'
    by = re.match(r'by\s+((?:human|decision):\S+)(.*)$', parts[1] if len(parts) > 1 else '')
    if not by:
        return "Accept-risk: needs 'by human:<id>' or 'by decision:<ADR>'"
    reason = re.match(r'\s+[-–—]\s+(\S.*)$', by[2])
    if not reason:
        return "Accept-risk: needs a reason after ' - '"
    return until, by[1], reason[1].strip()


def parse(rid: str, capability: str, raw: str) -> Obligation:
    """The obligation a requirement block declares, or why it is INVALID."""
    found: dict[str, str] = {}
    scenario = False
    for line in raw.splitlines()[1:]:
        if SCENARIO.match(line):
            scenario = True
            continue
        for kind, pattern in (('Verify', VERIFY), ('Inputs', INPUTS), ('Accept-risk', RISK)):
            match = pattern.match(line)
            if not match:
                continue
            if scenario:
                return Obligation(rid, capability, invalid=f'{kind}: line after a scenario')
            if kind in found:
                return Obligation(rid, capability, invalid=f'duplicate {kind}: line')
            found[kind] = match[1].strip()
    risk: tuple = ()
    if 'Accept-risk' in found:
        parsed = parse_risk(found['Accept-risk'])
        if isinstance(parsed, str):
            return Obligation(rid, capability, invalid=parsed)
        risk = parsed
    if 'Verify' not in found:
        if 'Inputs' in found:
            return Obligation(rid, capability, invalid='Inputs: without Verify:')
        return Obligation(rid, capability, declared=False, risk=risk)
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
        return Obligation(rid, capability, manual=manual[1].strip(), globs=globs, risk=risk)
    command = COMMAND.match(value)
    if not command:
        return Obligation(rid, capability, invalid='Verify: needs one backticked command, or manual and a reason')
    try:
        argv = tuple(shlex.split(command[1]))
    except ValueError as error:
        return Obligation(rid, capability, invalid=f'Verify: command cannot be parsed ({error})')
    if not argv:
        return Obligation(rid, capability, invalid='Verify: command is empty')
    return Obligation(rid, capability, argv=argv, globs=globs, risk=risk)


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
        found.extend(dataclasses.replace(parse(rid, relative, block.raw), block_sha256=brownfield.sha(block.raw))
                     for rid, block in blocks.items())
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


def _records(records_dir: Path, state: dict | None) -> list[tuple[str, dict]]:
    """Readable lifecycle records as `evidence()` selects them; unreadable ones contribute nothing."""
    active = state.get('task') if isinstance(state, dict) else None
    found: list[tuple[str, dict]] = []
    files = sorted(records_dir.glob('*.json')) if records_dir.is_dir() else []
    for path in files:
        if active and path.stem == active:
            continue
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError):
            continue
        if isinstance(record, dict):
            found.append((path.name, record))
    if isinstance(state, dict):
        found.append((f'{active}.json' if active else 'active state', state))
    return found


def _review_target(root: Path, stage: object) -> Path | None:
    """The review report a record's review stage names, if it is a repo-relative file inside ROOT."""
    if not isinstance(stage, dict) or not all(isinstance(stage.get(key), str) for key in ('ref', 'sha256', 'at')):
        return None
    if Path(stage['ref']).is_absolute():
        return None
    target = (root / stage['ref']).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        return None
    return target


def _judge(record_name: str, record: dict, stage: dict, digest: str, text: str, obligation: Obligation) -> tuple[dict | None, list[str]]:
    """An honored attestation of OBLIGATION by one cited review, or why not (reasons are empty when it is not cited)."""
    found = review_evidence.citations(review_evidence.reviewed_section(text), obligation.id)
    if not found:
        return None, []
    problems = ledger.audit(record.get('ledger'))
    if problems:
        return None, [f'record failed ledger audit: {problems[0]}']
    if digest != stage['sha256']:
        return None, [f"review {stage['ref']} changed since it was recorded"]
    if not review_evidence.approved(text):
        return None, ['verdict is not Approved: ' + review_evidence.verdict(text)[:80]]
    pins = [value for kind, value in found if kind == 'pin']
    pinned = any(obligation.block_sha256.startswith(value.lower()) for value in pins)
    if not pinned and not any(kind == 'plain' for kind, _ in found):
        reasons = []
        if pins:
            reasons.append(f'requirement changed since attestation (current block sha256 starts {obligation.block_sha256[:12]})')
        reasons += [f'malformed pin {value}' for kind, value in found if kind == 'malformed']
        return None, reasons
    approver = (record.get('stages') or {}).get('intent', {}).get('approved_by')
    reason = None if pinned else f'not bound to requirement text; pin with @{obligation.block_sha256[:12]} after the id'
    return {'basis': 'attested', 'judgment': True, 'record': record_name, 'review': stage['ref'],
            'review_sha256': digest, 'at': stage['at'], 'intent_approved_by': approver if isinstance(approver, str) else None,
            'pinned': pinned, 'reason': reason}, []


def attest(root: Path, records_dir: Path, state: dict | None, manual: list[Obligation]) -> tuple[dict[str, dict], list[str]]:
    """Newest honored attestation per MANUAL requirement id, and notes for citations that were not honored."""
    if not manual:
        return {}, []
    honored: dict[str, tuple] = {}
    refused: dict[str, list[str]] = {}
    for name, record in _records(records_dir, state):
        stage = (record.get('stages') or {}).get('review') if isinstance(record.get('stages'), dict) else None
        target = _review_target(root, stage)
        if target is None:
            continue
        try:
            digest, text = review_evidence.load_review(target)
        except (OSError, UnicodeError):
            continue
        for obligation in manual:
            attestation, reasons = _judge(name, record, stage, digest, text, obligation)
            if attestation is not None:
                order = (attestation['at'], name)
                if obligation.id not in honored or order > honored[obligation.id][0]:
                    honored[obligation.id] = (order, attestation)
            for reason in reasons:
                refused.setdefault(obligation.id, []).append(f'attestation: {obligation.id}: {name}: not honored ({reason})')
    notes = [note for rid, found in refused.items() if rid not in honored for note in found]
    return {rid: pair[1] for rid, pair in honored.items()}, notes


def annotate(root: Path, records_dir: Path, state: dict | None, obligations: list[Obligation], results: list[dict],
             today: datetime.date | None = None) -> list[str]:
    """Add `attested` to MANUAL results and `risk_acceptance` to STALE, FAILED and UNVERIFIED ones; return notes.

    Nothing here changes a status, `basis` or exit code. With no citations and no Accept-risk: line it adds nothing.
    """
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    paired = list(zip(obligations, results))
    manual = [o for o, item in paired if item['status'] == 'MANUAL']
    attested, notes = attest(root, records_dir, state, manual)
    for obligation, item in paired:
        if item['status'] == 'MANUAL' and obligation.id in attested:
            item['attested'] = attested[obligation.id]
        if item['status'] in ('STALE', 'FAILED', 'UNVERIFIED') and obligation.risk:
            until, by, reason = obligation.risk
            item['risk_acceptance'] = {'basis': 'declared', 'until': until, 'by': by, 'reason': reason,
                                       'state': 'active' if until >= today.isoformat() else 'expired'}
    return sorted(set(notes))


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


def _git(root: Path, *args: str, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=not binary, timeout=60)


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


def touched(root: Path, base: str, obligations: list[Obligation], operated: tuple = ()) -> list[Obligation]:
    """Gate scope from task-start BASE, including requirement edits; unlike changed(), fail closed."""
    def git(*args: str) -> str:
        result = _git(root, *args, binary=True)
        if result.returncode:
            raise ValueError('assurance selection failed: ' + decoded_git(result.stderr).strip())
        return decoded_git(result.stdout)

    def decoded_git(value: bytes | str) -> str:
        # Preserve blob CRLF and NUL-delimited path bytes; text-mode universal newlines alter both.
        return value.decode('utf-8') if isinstance(value, bytes) else value

    if not base or base.startswith('-'):
        raise ValueError('assurance baseline is missing or invalid')
    try:
        resolved = git('rev-parse', '--verify', '--quiet', base + '^{commit}').strip()
    except ValueError as error:
        raise ValueError(f'assurance baseline {base!r} is not a resolvable commit') from error
    files = set(git('diff', '--no-renames', '--name-only', '-z', resolved, '--').split('\0'))
    files.update(git('ls-files', '--others', '--exclude-standard', '-z').split('\0'))
    files.discard('')
    baseline = {}
    paths = git('ls-tree', '-r', '--name-only', '-z', resolved, '--', 'knowledge/capabilities').split('\0')
    for name in paths:
        if not name.endswith('.md') or Path(name).name in ('index.md', 'log.md'):
            continue
        text = git('show', f'{resolved}:{name}')
        meta, spans = brownfield.document(text)
        if meta.get('namespace') and 'requirements' in spans:
            for rid, block in brownfield.blocks(text, spans['requirements']).items():
                baseline[name, rid] = brownfield.sha(block.raw)
    ids = [o.id for o in obligations]
    if len(ids) != len(set(ids)):
        raise ValueError('assurance capabilities contain duplicate requirement IDs')
    return [o for o in obligations if o.id in operated or o.invalid
            or baseline.get((o.capability, o.id)) != o.block_sha256
            or (o.declared and (not o.globs or any(selected(o.evidence_globs, name) for name in files)))]


def gate_problem(root: Path, state: dict, records_dir: Path, tree: str) -> str | None:
    """Read-only Verify check; risk and attested annotations do not waive mechanical failures."""
    try:
        obligations, diagnostics = requirements(root)
        if diagnostics:
            raise ValueError('; '.join(diagnostics))
        if not obligations:
            return None
        operated = tuple(op['id'] for op in (state.get('merge') or {}).get('operations', []))
        chosen = touched(root, state.get('head'), obligations, operated)
        items, diagnostics = evidence(records_dir, state)
        if diagnostics:
            raise ValueError('; '.join(diagnostics))
        results = [evaluate(root, o, items, tree) for o in chosen]
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as error:
        return f'assurance gate refused: {error}; repair selection/evidence and retry Verify'
    failing = [item for item in results if item['status'] in FAILING]
    if failing:
        return 'assurance gate refused:\n' + '\n'.join(
            f"  {item['id']} {item['status']}: {item['reason']}; repair invalid declarations if needed, "
            f"then run `python3 .ai/scripts/lifecycle.py assure --run {item['id']}` and retry Verify"
            for item in failing)
    return None


def exit_code(results: list[dict], strict: bool, broken: bool) -> int:
    failing = FAILING + (('UNDECLARED',) if strict else ())
    return 1 if broken or any(item['status'] in failing for item in results) else 0


def summary(results: list[dict]) -> dict:
    return {status: sum(item['status'] == status for item in results) for status in STATUSES}


def render(results: list[dict], diagnostics: list[str], notes: list[str] | tuple = ()) -> str:
    lines = []
    for item in results:
        evidence = item['evidence']
        where = f" head={str(evidence['head'] or '?')[:7]} at={evidence['at']}" if evidence else ''
        lines.append(f"{item['status']:<10} {item['id']} {item['capability']}{where} - {item['reason']}")
        if 'attested' in item:
            att = item['attested']
            lines.append(f"    judgment (attested, not verified): approved review {att['review']} "
                         f"(sha256 {att['review_sha256'][:12]}) at {att['at']}; recorded in {att['record']}; "
                         f"intent approved_by {att['intent_approved_by'] or 'none recorded'} (claim); "
                         f"{att['reason'] or 'pinned to the current requirement text'}")
        if 'risk_acceptance' in item:
            risk = item['risk_acceptance']
            when = 'active until' if risk['state'] == 'active' else 'expired on'
            lines.append(f"    risk acceptance (declared, not verified): {when} {risk['until']}, claimed by "
                         f"{risk['by']} - {risk['reason']}; status still {item['status']}")
    if not results:
        lines.append('assure: no structured capability requirements')
    lines.extend('diagnostic: ' + text for text in diagnostics)
    lines.extend('note: ' + text for text in notes)
    counts = summary(results)
    lines.append('assure: ' + ', '.join(f'{counts[s]} {s}' for s in STATUSES if counts[s]) if results else 'assure: 0 requirements')
    return '\n'.join(lines)


def document(results: list[dict], diagnostics: list[str], base: str | None = None, notes: list[str] | tuple = ()) -> dict:
    data = {'schema_version': SCHEMA_VERSION, 'requirements': results, 'diagnostics': diagnostics,
            'summary': summary(results)}
    if notes:
        data['notes'] = list(notes)
    if base is not None:
        data['changed_base'] = base
    return data
