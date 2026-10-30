"""Lossless, read-only models and rendering for approval-bound capability deltas."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

import okf

ID = r'[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-R[1-9][0-9]*'
ENTRY = re.compile(r'^[-*] (`?(' + ID + r')`?)\s*:\s*(.+)')
NAMESPACE = re.compile(r'[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\Z')
OPERATIONS = ('added requirements', 'modified requirements', 'removed requirements')


class DeltaError(ValueError):
    def __init__(self, message, category='delta-invalid'):
        super().__init__(message)
        self.category = category


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def spec_hash(path):
    return sha(okf.split_frontmatter(path.read_text())[1].strip())


def read(path):
    return path.read_bytes().decode('utf-8')


@dataclass
class Block:
    id: str
    raw: str
    start: int
    end: int

    @property
    def text(self):
        return ' '.join(line.strip() for line in self.raw.splitlines())[len(self.id) + 3:]


def document(text):
    """Section content spans into the original text; fenced examples are not headings."""
    fm, _, body_line = okf.split_frontmatter(text)
    meta = okf.parse_frontmatter(fm) if fm is not None else {}
    result, offset, current, fence = {}, 0, None, None
    for n, line in enumerate(text.splitlines(keepends=True), 1):
        if n >= body_line:
            marker = re.match(r'^\s*(`{3,}|~{3,})', line)
            if marker:
                if fence is None:
                    fence = marker[1][0]
                elif marker[1][0] == fence:
                    fence = None
            match = re.match(r'^## (.+?)\s*$', line) if fence is None and not marker else None
            if match:
                if current is not None:
                    result[current][1] = offset
                current = match[1].lower()
                if current in result:
                    raise DeltaError('duplicate section ' + current, 'delta-structure')
                result[current] = [offset + len(line), len(text)]
        offset += len(line)
    return meta, result


def blocks(text, span):
    start, end = span
    lines = text[start:end].splitlines(keepends=True)
    result, begin, rid, offset = {}, None, None, start
    for line in lines + ['']:
        match = ENTRY.match(line)
        if match or not line:
            if rid is not None:
                raw = text[begin:offset]
                # Keep the final line terminator; separator blank lines belong to the document.
                trimmed = raw.splitlines(keepends=True)
                while trimmed and not trimmed[-1].strip():
                    trimmed.pop()
                raw = ''.join(trimmed)
                if rid in result:
                    raise DeltaError('duplicate requirement ' + rid, 'delta-structure')
                result[rid] = Block(rid, raw, begin, begin + len(raw))
            rid, begin = (match[2], offset) if match else (None, None)
        elif line.strip() and not line[:1].isspace():
            raise DeltaError('ambiguous requirement block: ' + line.strip(), 'delta-structure')
        offset += len(line)
    return result


def is_delta(path):
    text = read(path)
    fm, body, _ = okf.split_frontmatter(text)
    meta = okf.parse_frontmatter(fm) if fm is not None else {}
    return 'target' in meta or any(re.search(r'^## ' + name + r'\s*$', body, re.M | re.I) for name in OPERATIONS)


def target_path(bundle, target):
    if (not isinstance(target, str) or not target.startswith('/capabilities/')
            or '..' in target.split('/') or '\\' in target or not target.endswith('.md')):
        raise DeltaError('invalid target: use /capabilities/<path>.md', 'delta-target')
    if '/' + Path(target).as_posix().lstrip('/') != target:
        raise DeltaError('target must use canonical /capabilities/<path>.md spelling', 'delta-target')
    path = bundle / target.lstrip('/')
    if (not bundle.resolve().is_relative_to(bundle.parent.resolve())
            or not (bundle / 'capabilities').resolve().is_relative_to(bundle.resolve())
            or path.name in ('index.md', 'log.md')
            or not path.resolve().is_relative_to((bundle / 'capabilities').resolve())):
        raise DeltaError('target escapes capability boundary: ' + target, 'delta-target')
    if not path.is_file():
        raise DeltaError('target is not an existing regular capability: ' + target, 'delta-target')
    return path


def receipt_schema(receipt):
    if not isinstance(receipt, dict) or receipt.get('format') != 1 or receipt.get('state') not in ('pending', 'completed'):
        raise DeltaError('malformed merge receipt', 'delta-receipt')
    for key in ('spec', 'spec_sha256', 'target', 'log_id', 'log_message', 'log_date'):
        if not isinstance(receipt.get(key), str) or not receipt[key]:
            raise DeltaError('merge receipt missing ' + key, 'delta-receipt')
    ops = receipt.get('operations')
    if not isinstance(ops, list) or not ops:
        raise DeltaError('merge receipt missing operations', 'delta-receipt')
    seen = set()
    for op in ops:
        if not isinstance(op, dict) or op.get('kind') not in OPERATIONS or not re.fullmatch(ID, str(op.get('id', ''))):
            raise DeltaError('malformed merge operation', 'delta-receipt')
        if op['id'] in seen:
            raise DeltaError('duplicate merge receipt ID ' + op['id'], 'delta-receipt')
        seen.add(op['id'])
        for key in ('before', 'after'):
            if op.get(key) is not None and not re.fullmatch('[0-9a-f]{64}', str(op[key])):
                raise DeltaError('malformed merge receipt hash ' + op['id'], 'delta-receipt')
        replacement = op.get('replacement')
        if not isinstance(replacement, str) or (sha(replacement) if replacement else None) != op.get('after'):
            raise DeltaError('merge receipt replacement hash mismatch ' + op['id'], 'delta-receipt')
        original = op.get('original')
        if not isinstance(original, str) or (sha(original) if original else None) != op.get('before'):
            raise DeltaError('merge receipt original hash mismatch ' + op['id'], 'delta-receipt')
        if ((op['kind'] == 'added requirements') != (op.get('before') is None)
                or (op['kind'] == 'removed requirements') != (op.get('after') is None)):
            raise DeltaError('merge receipt operation semantics invalid ' + op['id'], 'delta-receipt')


def find_receipt(root, spec, target):
    found = None
    relative = spec.relative_to(root).as_posix()
    for file in sorted((root / 'knowledge/history/lifecycle').glob('*.json')):
        try:
            record = json.loads(read(file))
        except (ValueError, OSError) as error:
            raise DeltaError('unreadable lifecycle record ' + file.name, 'delta-receipt') from error
        receipt = record.get('merge') if isinstance(record, dict) else None
        if receipt is not None:
            receipt_schema(receipt)
        if receipt and receipt['spec'] == relative and receipt['spec_sha256'] == spec_hash(spec):
            intent = record.get('stages', {}).get('intent', {})
            if (receipt['target'] != target or intent.get('ref') != relative
                    or intent.get('sha256') != receipt['spec_sha256'] or not intent.get('approved_by')):
                raise DeltaError('merge receipt is not bound to approved intent', 'delta-receipt')
            if found is not None:
                raise DeltaError('multiple merge receipts for approved spec', 'delta-receipt')
            found = (file, record, receipt)
    return found


def scenarios(raw):
    lines = raw.splitlines(keepends=True)
    directive, first, names = None, None, set()
    for i, line in enumerate(lines[1:], 1):
        if line.strip().startswith('Scenarios:'):
            if directive is not None or line.strip() != 'Scenarios: replace':
                raise DeltaError('invalid Scenarios: replace directive', 'delta-structure')
            directive = i
        match = re.match(r'^\s+[-*] Scenario ([^:\r\n]+):', line)
        if match:
            if match[1].strip() in names:
                raise DeltaError('duplicate scenario ' + match[1], 'delta-structure')
            names.add(match[1].strip())
            if first is None:
                first = i
    if directive is not None and first is not None and directive > first:
        raise DeltaError('scenario directive must precede scenarios', 'delta-structure')
    return lines, directive, first


def replacement(block, old, kind):
    if kind == 'removed requirements':
        return ''
    lines, directive, first = scenarios(block.raw)
    if kind == 'modified requirements' and first is not None and directive is None:
        raise DeltaError(block.id + ' scenarios require Scenarios: replace', 'delta-structure')
    if directive is not None:
        del lines[directive]
    result = ''.join(lines)
    if old is not None:
        oldlines, _, oldfirst = scenarios(old.raw)
        if directive is None and oldfirst is not None:
            result += ''.join(oldlines[oldfirst:])
    return result


def model(spec, root):
    bundle = root / 'knowledge'
    text = read(spec)
    meta, spans = document(text)
    target = meta.get('target')
    cap = target_path(bundle, target)
    if cap.resolve() == spec.resolve():
        raise DeltaError('self target is forbidden', 'delta-target')
    required = (*OPERATIONS, 'target baseline', 'acceptance', 'constraints', 'non-goals', 'assumptions', 'open questions')
    for heading in required:
        if heading not in spans:
            raise DeltaError('missing section ' + heading, 'delta-structure')
    if 'requirements' in spans:
        raise DeltaError('delta must not have a whole-feature Requirements section', 'delta-structure')
    captext = read(cap)
    capmeta, capspans = document(captext)
    namespace = capmeta.get('namespace')
    if not isinstance(namespace, str) or not NAMESPACE.fullmatch(namespace) or 'requirements' not in capspans:
        raise DeltaError('target needs structured Requirements and a valid namespace; prepare an approved baseline', 'delta-structure')
    for doc in okf.iter_docs(bundle):
        if doc.path != cap and doc.rel.startswith('capabilities/') and doc.meta and doc.meta.get('namespace') == namespace:
            raise DeltaError('duplicate capability namespace ' + namespace, 'delta-structure')
    living = blocks(captext, capspans['requirements'])
    for rid, block in living.items():
        if not re.fullmatch(re.escape(namespace) + r'-R[1-9][0-9]*', rid):
            raise DeltaError('foreign namespace ID ' + rid, 'delta-structure')
        scenarios(block.raw)
    operations, reqs = [], {}
    for kind in OPERATIONS:
        content = text[slice(*spans[kind])].strip()
        entries = {} if content == 'None.' else blocks(text, spans[kind])
        if not entries and content != 'None.':
            raise DeltaError('empty operation section must contain None.: ' + kind, 'delta-structure')
        for rid, block in entries.items():
            if rid in reqs or not re.fullmatch(re.escape(namespace) + r'-R[1-9][0-9]*', rid):
                raise DeltaError('duplicate or foreign delta ID ' + rid, 'delta-structure')
            if kind == 'removed requirements' and not re.search(r'Reason:\s*\S', block.raw):
                raise DeltaError(rid + ' removal needs Reason:', 'delta-invalid')
            if kind == 'removed requirements' and not re.search(r'\bMUST\b', block.raw.split('Reason:', 1)[0]):
                raise DeltaError(rid + ' removal needs a MUST retirement statement', 'delta-invalid')
            reqs[rid] = block.text
            operations.append((kind, block))
    if not operations:
        raise DeltaError('delta has no operations', 'delta-structure')
    receipt_info = find_receipt(root, spec, target)
    if receipt_info is None:
        for kind, block in operations:
            if kind == 'added requirements' and block.id in living:
                raise DeltaError('added ID already exists: ' + block.id, 'delta-structure')
            if kind != 'added requirements' and block.id not in living:
                raise DeltaError('unknown modified/removed ID ' + block.id, 'delta-structure')
    baseline = text[slice(*spans['target baseline'])]
    mirrors = re.findall(r'^Target:\s*(.+?)\s*$', baseline, re.M)
    if mirrors != [target]:
        raise DeltaError('target frontmatter disagrees with approved body mirror', 'delta-target')
    pins = {}
    for line in baseline.splitlines():
        if line.startswith('- '):
            match = re.fullmatch(r'- (' + ID + r'): (absent|sha256:[0-9a-f]{64})', line)
            if not match or match[1] in pins:
                raise DeltaError('invalid or duplicate baseline pin', 'delta-invalid')
            pins[match[1]] = None if match[2] == 'absent' else match[2][7:]
    if set(pins) != set(reqs):
        raise DeltaError('baseline pins must cover exactly the operated IDs', 'delta-invalid')
    receipt_ops = {op['id']: op for op in receipt_info[2]['operations']} if receipt_info else {}
    if receipt_info and set(receipt_ops) != set(reqs):
        raise DeltaError('receipt operation IDs disagree with spec', 'delta-receipt')
    conflicts = []
    for kind, block in operations:
        current = sha(living[block.id].raw) if block.id in living else None
        recorded = receipt_ops.get(block.id)
        allowed = {pins[block.id]}
        if recorded:
            allowed = {recorded.get('after')} if receipt_info[2]['state'] == 'completed' else {pins[block.id], recorded.get('after')}
        if current not in allowed:
            conflicts.append(block.id)
    if conflicts:
        raise DeltaError('stale target ' + target + ': ' + ', '.join(conflicts), 'delta-invalid')
    rendered = []
    for kind, block in operations:
        rid, old = block.id, living.get(block.id)
        before = pins[rid]
        if (kind == 'added requirements') != (before is None):
            raise DeltaError('invalid baseline membership for ' + rid, 'delta-structure')
        current = sha(old.raw) if old else None
        recorded = receipt_ops.get(rid)
        if recorded:
            if recorded['kind'] != kind or recorded.get('before') != before:
                raise DeltaError('receipt baseline mismatch ' + rid, 'delta-receipt')
            allowed = {recorded.get('after')} if receipt_info[2]['state'] == 'completed' else {before, recorded.get('after')}
            if current not in allowed:
                raise DeltaError('stale target ' + target + ': ' + rid, 'delta-invalid')
            original = Block(rid, recorded['original'], 0, len(recorded['original'])) if recorded['original'] else None
            new = replacement(block, original, kind)
            if recorded['replacement'] != new:
                raise DeltaError('receipt replacement disagrees with approved delta ' + rid, 'delta-receipt')
        else:
            if kind == 'added requirements' and old is not None:
                raise DeltaError('added ID already exists: ' + rid, 'delta-structure')
            if kind != 'added requirements' and old is None:
                raise DeltaError('unknown modified/removed ID ' + rid, 'delta-structure')
            if current != before:
                raise DeltaError('stale target ' + target + ': ' + rid, 'delta-invalid')
            new = replacement(block, old, kind)
        rendered.append(dict(id=rid, kind=kind, before=before, after=sha(new) if new else None, replacement=new,
                             original=recorded['original'] if recorded else (old.raw if old else '')))
    # Retained removal specs reserve IDs even before their history is archived.
    added = {b.id for k, b in operations if k == 'added requirements'}
    warning = []
    for doc in okf.iter_docs(bundle):
        if doc.path == spec or not doc.rel.startswith('specifications/') or not doc.meta or doc.meta.get('target') != target:
            continue
        try:
            othertext = read(doc.path)
            _, othersections = document(othertext)
            others = {}
            for kind in OPERATIONS:
                if kind in othersections and othertext[slice(*othersections[kind])].strip() != 'None.':
                    others[kind] = blocks(othertext, othersections[kind])
        except (DeltaError, UnicodeError):
            if doc.meta.get('status') == 'draft':
                continue  # Malformed advisory evidence cannot block the requested delta.
            raise
        retired = others.get('removed requirements', {})
        if added.intersection(retired):
            raise DeltaError('retired ID cannot be reused: ' + ', '.join(sorted(added.intersection(retired))), 'delta-structure')
        if doc.meta.get('status') == 'draft':
            overlap = set()
            for entries in others.values():
                overlap.update(entries)
            overlap.intersection_update(reqs)
            if overlap:
                warning.append('local draft overlap ' + doc.rel + ': ' + ', '.join(sorted(overlap)) + '; unobserved branches are outside warning coverage')
    for file in (bundle / 'history/lifecycle').glob('*.json'):
        record = json.loads(read(file))
        receipt = record.get('merge')
        if receipt and receipt['target'] == target and (receipt_info is None or file != receipt_info[0]):
            retired = {op['id'] for op in receipt['operations'] if op['kind'] == 'removed requirements'}
            if added & retired:
                raise DeltaError('retired ID cannot be reused: ' + ', '.join(sorted(added & retired)), 'delta-structure')
    acceptance = blocks(text, spans['acceptance'])
    return dict(delta=True, found={k: text[a:b].splitlines() for k, (a, b) in spans.items()},
                requirements=reqs, acceptance={k: v.text for k, v in acceptance.items()},
                duplicates={'requirements': [], 'acceptance': []},
                open=[ln.strip() for ln in text[slice(*spans['open questions'])].splitlines() if ln.strip()],
                cap=cap, captext=captext, capmeta=capmeta, capspans=capspans, living=living,
                target=target, operations=rendered, receipt_info=receipt_info, warnings=warning)


def render(model, spec):
    text = model['captext']
    replacements = []
    added = []
    for op in model['operations']:
        old = model['living'].get(op['id'])
        if old:
            replacements.append((old.start, old.end, op['replacement']))
        elif op['replacement']:
            added.append(op['replacement'])
    if added:
        end = model['capspans']['requirements'][1]
        replacements.append((end, end, '\n' + '\n'.join(added) + '\n'))
    for start, end, new in sorted(replacements, reverse=True):
        text = text[:start] + new + text[end:]
    sources = model['capmeta'].get('sources', [])
    if not isinstance(sources, list):
        raise DeltaError('capability sources must be a list', 'delta-target')
    resource = Path(os.path.relpath(spec, model['cap'].parent)).as_posix()
    if not any(isinstance(s, dict) and s.get('resource') == resource for s in sources):
        text = okf.update_frontmatter(text, {'sources': [*sources, {'id': 'delta-' + sha(resource)[:16], 'resource': resource}]})
    return text
