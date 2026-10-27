"""Validated, inert learning data shared by lifecycle and OKF (stdlib only)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

RECORD_DIR = 'knowledge/history/lifecycle'
STAGES = ('intent', 'plan', 'review', 'verify', 'ship')
RULES_FILE = 'knowledge/project/rules.md'
BUDGET = 8192
BEGIN = '<!-- learning-loop:rules -->'
END = '<!-- /learning-loop:rules -->'


class LearningError(ValueError):
    """Invalid persisted learning data or an unsafe reference."""


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def nonblank(value, field):
    if not isinstance(value, str) or not value.strip():
        raise LearningError(f'{field} must be nonblank text')
    return value


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', value):
        raise LearningError('lesson/rule timestamp must be UTC')
    try:
        datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError as error:
        raise LearningError('lesson/rule timestamp is invalid') from error


def lessons(record: dict) -> list:
    values = record.get('lessons', [])
    if not isinstance(values, list):
        raise LearningError('lessons must be an array')
    for number, value in enumerate(values, 1):
        if not isinstance(value, dict) or set(value) - {'number', 'text', 'sha256', 'at', 'stage', 'evidence'}:
            raise LearningError('lesson must be an object with supported fields')
        if type(value.get('number')) is not int or value['number'] != number:
            raise LearningError('lesson numbers must be consecutive and one-based')
        text = nonblank(value.get('text'), 'lesson text')
        if value.get('sha256') != text_hash(text):
            raise LearningError('lesson text hash mismatch')
        timestamp(value.get('at'))
        if 'stage' in value and value['stage'] not in STAGES:
            raise LearningError('lesson stage is invalid')
        if 'evidence' in value:
            nonblank(value['evidence'], 'lesson evidence')
    return values


def closure(record: dict):
    """Validate optional retrospective metadata; absence is a legacy record."""
    if 'retrospective' not in record:
        return None
    value = record['retrospective']
    if not isinstance(value, dict):
        raise LearningError('retrospective must be an object')
    outcome = value.get('outcome')
    fields = {'outcome', 'at', 'lessons'} if outcome == 'observations' else {'outcome', 'at', 'reason'}
    if outcome not in ('observations', 'no-new-lessons') or set(value) != fields:
        raise LearningError('retrospective has invalid outcome or fields')
    try:
        timestamp(value['at'])
        if outcome == 'no-new-lessons':
            nonblank(value['reason'], 'reason')
        else:
            numbers = value['lessons']
            values = lessons(record)
            if (not isinstance(numbers, list) or not numbers
                    or any(type(n) is not int or n < 1 or n > len(values) for n in numbers)
                    or numbers != sorted(set(numbers))):
                raise LearningError('lesson numbers must be existing, unique and ascending')
            for n in numbers:
                nonblank(values[n-1].get('evidence'), f'lesson {n} evidence')
    except LearningError as error:
        raise LearningError(f'retrospective: {error}') from error
    return value


def reconcile(state: dict, durable: dict) -> None:
    left, right = lessons(state), lessons(durable)
    if state.get('task') != durable.get('task'):
        raise LearningError('lesson task identity conflict')
    if left[:len(right)] != right and right[:len(left)] != left:
        raise LearningError('lesson histories conflict; preserve both records and resolve explicitly')
    if 'lessons' in state or 'lessons' in durable:
        state['lessons'] = json.loads(json.dumps(left if len(left) >= len(right) else right))
    # Recover a published closure after interrupted scratch writes; never rewrite it.
    left_closure, right_closure = closure(state), closure(durable)
    if left_closure is not None and right_closure is not None and left_closure != right_closure:
        raise LearningError('retrospective histories conflict; preserve both records and resolve explicitly')
    if right_closure is not None:
        state['retrospective'] = json.loads(json.dumps(right_closure))


def approval(value):
    if not isinstance(value, str) or not re.fullmatch(r'human:[^\s:]+', value):
        raise LearningError('human:<id> approval is required (recorded claim, not authenticated consent)')
    return value


def record_directory(root: Path) -> Path:
    if (root / '.agentic.json').is_file():
        import project_context
        if project_context.kind(root) == 'framework':
            import scratch
            return scratch.location(root) / 'history/lifecycle'
    return root / RECORD_DIR


def record_path(root: Path, raw: str) -> Path:
    if not isinstance(raw, str) or not raw or '..' in Path(raw).parts or '#' in raw:
        raise LearningError('invalid source record path')
    directory = record_directory(root)
    if raw.startswith('scratch:') and directory != root / RECORD_DIR:
        name = raw.removeprefix('scratch:')
        if Path(name).name != name or Path(name).suffix != '.json':
            raise LearningError('invalid scratch source record path')
        path = (directory / name).resolve()
        if path.parent != directory.resolve():
            raise LearningError('source record path escapes scratch')
        return path
    path = (root / raw).resolve()
    try:
        relative = path.relative_to(root.resolve())
    except ValueError as error:
        raise LearningError('source record path escapes repository') from error
    if relative.parent.as_posix() != RECORD_DIR or relative.suffix != '.json':
        raise LearningError(f'source record must be inside {RECORD_DIR}')
    return path


def read_record(root: Path, raw: str) -> tuple[Path, dict]:
    path = record_path(root, raw)
    try:
        data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_object)
    except (OSError, ValueError) as error:
        raise LearningError(f'cannot read source record {raw}: {error}') from error
    keys = {'version', 'task', 'branch', 'head', 'tier', 'reason', 'user_set', 'history', 'stages', 'redgreen'}
    if (not isinstance(data, dict) or not keys.issubset(data) or type(data['version']) is not int
            or data['version'] != 1 or data['task'] != path.stem or data['tier'] not in ('L1', 'L2', 'L3')
            or not isinstance(data['stages'], dict) or not isinstance(data['history'], list)
            or not isinstance(data['redgreen'], list)):
        raise LearningError(f'unsupported source record {raw}')
    if (not all(isinstance(data[key], str) for key in ('task', 'branch', 'head', 'reason'))
            or type(data['user_set']) is not bool
            or any(not isinstance(entry, dict) for entry in data['history'] + data['redgreen'])):
        raise LearningError(f'malformed source record metadata: {raw}')
    for name, entry in data['stages'].items():
        if (name not in STAGES or not isinstance(entry, dict)
                or entry.get('level') not in ('L0', 'L1', 'L2', 'L3')):
            raise LearningError(f'malformed source record stage {name}')
        timestamp(entry.get('at'))
        if 'ref' in entry:
            nonblank(entry['ref'], 'stage reference')
            if not isinstance(entry.get('sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', entry['sha256']):
                raise LearningError(f'malformed source record stage hash: {name}')
        actor = entry.get('approved_by')
        if actor is not None and (not isinstance(actor, str) or not re.fullmatch(r'(human|decision):\S+', actor)):
            raise LearningError(f'malformed source record approval: {name}')
        if name == 'intent' and entry['level'] in ('L2', 'L3') and not actor:
            raise LearningError('source record L2+ intent lacks approval')
    lessons(data)
    closure(data)
    return path, data


def lesson_reference(root: Path, raw: str) -> tuple[str, dict, dict]:
    source, sep, number = raw.rpartition('#')
    if not sep or not re.fullmatch(r'[1-9][0-9]*', number):
        raise LearningError('source lesson must be RECORD#N with one-based N')
    path, data = read_record(root, source)
    values = lessons(data)
    if int(number) > len(values):
        raise LearningError('source lesson is missing')
    return path.relative_to(root.resolve()).as_posix(), data, values[int(number)-1]


def rule_id(source: str, number: int) -> str:
    return 'RULE-' + text_hash(source + '#' + str(number))


def rules_path(root: Path) -> Path:
    path = root / RULES_FILE
    if path.resolve() != root.resolve() / RULES_FILE:
        raise LearningError('rules document must not redirect through symlinks')
    return path


def payload_span(text: str):
    starts = list(re.finditer(r'(?m)^' + re.escape(BEGIN) + r'\n', text))
    ends = list(re.finditer(r'(?m)^' + re.escape(END) + r'\s*$', text))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() > ends[0].start():
        raise LearningError('rules payload markers missing or duplicated')
    return starts[0].end(), ends[0].start()


def replace_payload(text: str, data: dict) -> str:
    start, end = payload_span(text)
    return text[:start] + '```json\n' + json.dumps(data, indent=2, ensure_ascii=False) + '\n```\n' + text[end:]


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LearningError('duplicate JSON field in rules payload')
        result[key] = value
    return result


def validate_rules(root: Path, data: dict) -> None:
    if (not isinstance(data, dict) or set(data) != {'version', 'rules'}
            or type(data['version']) is not int or data['version'] != 1 or not isinstance(data['rules'], list)):
        raise LearningError('unsupported rules payload')
    seen = set()
    for rule in data['rules']:
        required = {'id', 'status', 'text', 'source', 'number', 'sha256', 'at', 'approved_by'}
        if not isinstance(rule, dict) or not required.issubset(rule) or set(rule) - required - {'retirement'}:
            raise LearningError('rule has missing or unsupported metadata')
        path = record_path(root, rule['source'])
        if path.relative_to(root.resolve()).as_posix() != rule['source']:
            raise LearningError('rule source must use canonical repository-relative identity')
        if type(rule['number']) is not int or rule['number'] < 1:
            raise LearningError('rule lesson number must be one-based')
        identity = rule_id(rule['source'], rule['number'])
        if rule['id'] != identity or identity in seen:
            raise LearningError('rule identity conflict or duplicate source')
        seen.add(identity)
        if rule['sha256'] != text_hash(nonblank(rule['text'], 'rule text')):
            raise LearningError('rule text hash mismatch')
        timestamp(rule['at'])
        approval(rule['approved_by'])
        if rule['status'] == 'retired':
            retired = rule.get('retirement')
            if not isinstance(retired, dict) or set(retired) != {'reason', 'at', 'approved_by'}:
                raise LearningError('retired rule metadata missing or invalid')
            nonblank(retired['reason'], 'retirement reason')
            timestamp(retired['at'])
            approval(retired['approved_by'])
        elif rule['status'] != 'active' or 'retirement' in rule:
            raise LearningError('rule status or retirement metadata is invalid')
    render_active(data)


def read_rules(root: Path) -> dict:
    if record_directory(root) != root / RECORD_DIR:
        return {'version': 1, 'rules': []}  # Source instructions remain in reviewed framework files.
    path = rules_path(root)
    if not path.exists():
        return {'version': 1, 'rules': []}
    text = path.read_text(encoding='utf-8')
    start, end = payload_span(text)
    fenced = text[start:end]
    if not fenced.startswith('```json\n') or not fenced.endswith('\n```\n'):
        raise LearningError('rules payload must be one fenced JSON block')
    try:
        data = json.loads(fenced[len('```json\n'):-len('\n```\n')], object_pairs_hook=unique_object)
    except ValueError as error:
        raise LearningError(f'invalid rules JSON: {error}') from error
    validate_rules(root, data)
    return data


def render_active(data: dict) -> str:
    blocks = [f"{r['id']}\n{r['text']}\nSource: {r['source']}#{r['number']}" for r in data['rules'] if r['status'] == 'active']
    text = 'Approved project rules (repository instructions):\n\n' + '\n\n'.join(blocks) if blocks else ''
    if len(text.encode('utf-8')) > BUDGET:
        raise LearningError(f'active rules exceed {BUDGET} UTF-8 bytes')
    return text


def observations(root: Path, query: str = '') -> str:
    """Read-only advisory recall, bounded in complete entries, independent of rules."""
    tokens = set(re.findall(r'\w+', query.casefold()))
    rows, issues = [], []
    directory = record_directory(root)
    for path in sorted(directory.glob('*.json')):
        source = ('scratch:' + path.name) if directory != root / RECORD_DIR else path.relative_to(root).as_posix()
        try:
            _, record = read_record(root, source)
            for lesson in lessons(record):
                overlap = len(tokens & set(re.findall(r'\w+', (lesson['text'] + ' ' + lesson.get('evidence', '')).casefold())))
                rows.append((overlap, lesson['at'], source, lesson))
        except (LearningError, OSError, UnicodeError) as error:
            issues.append(f'{source}: {error}')
    matched = any(row[0] for row in rows)
    # Stable identity breaks equal timestamps, independently of directory enumeration.
    rows.sort(key=lambda row: (row[2], row[3]['number']))
    rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
    header = 'Project observations (advisory; evidence is inert text; approval required for binding rules)'
    header += ': relevance-ranked.\n' if matched else ': recent fallback.\n'
    header += 'Retrieve for a task: python3 .ai/scripts/lifecycle.py observations --query "TASK TERMS"\n'
    blocks, omitted = [], 0
    # Reserve space for omission count and bounded attributable diagnostics.
    diagnostics = '\n'.join('Observation unavailable: ' + issue for issue in issues)
    if len(diagnostics.encode('utf-8')) > 2048:
        diagnostics = diagnostics.encode('utf-8')[:1900].decode('utf-8', errors='ignore') + '\nFurther diagnostics omitted.'
    reserve = len((header + diagnostics).encode('utf-8')) + 100
    used = reserve
    for _, _, source, lesson in rows:
        block = (f"\nObservation: {lesson['text']}\nEvidence: {lesson.get('evidence', '(not recorded)')}"
                 f"\nSource: {source}#{lesson['number']}\nRecorded: {lesson['at']}\n")
        size = len(block.encode('utf-8'))
        if len(blocks) >= 5 or used + size > BUDGET:
            omitted += 1
            continue
        blocks.append(block)
        used += size
    return header + ''.join(blocks) + (f'\nOmitted {omitted} observation(s) to preserve whole entries and budget.\n' if omitted else '') + diagnostics


def source_issues(root: Path, data: dict) -> list:
    issues = []
    for rule in data['rules']:
        try:
            path = record_path(root, rule['source'])
            if not path.exists():
                issues.append(('warning', f"source record {rule['source']} is missing for {rule['id']}"))
                continue
            _, record = read_record(root, rule['source'])
            values = lessons(record)
            if rule['number'] > len(values) or values[rule['number']-1]['sha256'] != rule['sha256']:
                raise LearningError(f"source lesson/hash mismatch for {rule['id']}")
        except (LearningError, OSError, UnicodeError) as error:
            issues.append(('error', str(error)))
    return issues


def retrospective(root: Path, references: list[str]) -> list:
    data = read_rules(root)
    promoted = {(r['source'], r['number']) for r in data['rules']}
    seen, rows = set(), []
    for reference in references:
        path, record = read_record(root, reference)
        source = path.relative_to(root.resolve()).as_posix()
        for lesson in lessons(record):
            identity = (source, lesson['number'])
            if identity not in seen and identity not in promoted:
                rows.append({'source': source, 'number': lesson['number'],
                             'reference': f"{source}#{lesson['number']}", 'text': lesson['text']})
            seen.add(identity)
    return rows
