"""Worktree review journal and protected-producer leases (stdlib, Python 3.9+).

No lifecycle or OKF imports: callers acquire ownership before their state lock.
Borrowers use per-process atomic registrations, never the guard/state locks.
This is ordinary-workflow coordination, not authentication against local forgery.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger
import scratch

LEASE_ENV = '_AGENTIC_REVIEW_PRODUCER'
VERSION = 1


class ReviewError(ValueError):
    """A review boundary could not be proved; the operation must refuse."""


def directory(root: Path) -> Path:
    identity = hashlib.sha256(os.fsencode(str(root.resolve()))).hexdigest()
    common = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--path-format=absolute',
                                      '--git-common-dir'], env=git_environment(), text=True,
                                     stderr=subprocess.PIPE).strip()
    try:
        return scratch.require_disk(Path(common) / 'okf-scratch' / 'review' / identity)
    except ValueError as error:
        raise ReviewError(str(error)) from error


def git_environment() -> dict:
    # Namespace discovery follows the physical target, not a caller's Git override.
    return {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}


def atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def document(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ReviewError(f'invalid review record {path.name}: {error}') from error
    if not isinstance(value, dict):
        raise ReviewError(f'invalid review record {path.name}: expected object')
    return value


def read(root: Path) -> dict:
    base = directory(root)
    path = base / 'journal.json'
    latch = base.parent.parent / 'review-expectations' / (base.name + '.json')
    expected = document(latch) if latch.exists() else None
    if not path.exists():
        if expected is not None:
            raise ReviewError('mechanical review journal is missing; restore its evidence, do not downgrade to legacy')
        return {'version': VERSION, 'root': str(root.resolve()), 'writers': {},
                'interval': None, 'history': [], 'sessions': {}}
    value = document(path)
    if (value.get('version') != VERSION or value.get('root') != str(root.resolve())
            or not isinstance(value.get('writers'), dict)
            or not isinstance(value.get('history'), list)
            or not isinstance(value.get('sessions'), dict)
            or value.get('request') is not None and not isinstance(value['request'], dict)
            or value.get('interval') is not None and not isinstance(value['interval'], dict)):
        raise ReviewError('invalid review journal schema/worktree; preserve it for diagnosis')
    request = value.get('request')
    if expected is not None:
        if (expected.get('root') != str(root.resolve()) or not isinstance(request, dict)
                or any(request.get(key) != item for key, item in expected.get('request', {}).items())):
            raise ReviewError('mechanical review journal disagrees with its independent opt-in expectation')
    elif request is not None:
        raise ReviewError('mechanical review opt-in expectation is missing; restore its evidence')
    return value


@contextmanager
def lock(root: Path):
    base = directory(root)
    base.mkdir(parents=True, exist_ok=True)
    with (base / 'guard.lock').open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            if not stream.tell():
                stream.write(b'\0')
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


@contextmanager
def transaction(root: Path):
    with lock(root):
        value = read(root)
        yield value
        atomic(directory(root) / 'journal.json', value)


def identity(pid: int | None = None) -> dict:
    pid = os.getpid() if pid is None else pid
    birth = None
    try:
        # comm may contain spaces and parentheses; fields after its final ')' are stable.
        birth = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError):
        pass
    return {'pid': pid, 'birth': birth}


def stopped(process: dict) -> bool:
    if (not isinstance(process, dict) or not isinstance(process.get('pid'), int)
            or process['pid'] <= 0):
        raise ReviewError('invalid producer process identity')
    if os.name == 'nt':
        # Unlike POSIX, os.kill(pid, 0) terminates on Windows. This adapter has
        # no supported Windows lifetime proof: preserve unresolved ownership.
        return False
    pid = process['pid']
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    current = identity(pid)
    return bool(process.get('birth') and current.get('birth')
                and process['birth'] != current['birth'])


def lease_path(root: Path, lease: str) -> Path:
    if not isinstance(lease, str) or len(lease) != 32 or any(c not in '0123456789abcdef' for c in lease):
        raise ReviewError('invalid inherited producer lease ID')
    return directory(root) / 'producers' / lease


def borrowers_quiet(path: Path) -> bool:
    for registration in (path / 'borrowers').glob('*.json'):
        value = document(registration)
        if value.get('phase') not in ('running', 'done'):
            raise ReviewError('invalid borrower phase')
        if value['phase'] != 'done':
            if not stopped(value.get('process')):
                return False
            if value.get('group') is not None and not group_stopped(value['group']):
                return False
    return True


def active_problem(value: dict) -> str | None:
    if (value.get('interval') or {}).get('phase') == 'active':
        return 'active review freezes protected writers; wait for native completion or explicitly abandon'
    return None


def assert_quiet(value: dict) -> None:
    if value['writers']:
        raise ReviewError('live or unresolved producer; resolve every producer before review/recovery')


def inherited(root: Path) -> dict | None:
    raw = os.environ.get(LEASE_ENV)
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except ValueError as error:
        raise ReviewError('invalid inherited producer descriptor') from error
    if not isinstance(value, dict):
        raise ReviewError('invalid inherited producer descriptor')
    if value.get('root') != str(root.resolve()):
        return None  # A separate fixture/worktree needs its own ownership.
    return value


def validate_owner(root: Path, descriptor: dict) -> tuple[Path, dict]:
    path = lease_path(root, descriptor.get('id'))
    owner = document(path / 'owner.json')
    if (owner.get('nonce') != descriptor.get('nonce') or owner.get('root') != str(root.resolve())
            or owner.get('phase') != 'running' or stopped(owner.get('process'))):
        raise ReviewError('invalid or expired inherited producer ownership')
    return path, owner


@contextmanager
def borrow(root: Path, descriptor: dict, *, group=False):
    path, owner = validate_owner(root, descriptor)
    if owner['process'] == identity() and owner.get('thread') == threading.get_ident():
        yield
        return
    registration = path / 'borrowers' / (uuid.uuid4().hex + '.json')
    record = {'process': identity(), 'phase': 'running'}
    if group:
        record['group'] = os.getpgrp()
    atomic(registration, record)
    try:
        # Registration precedes the second owner read. Owner closes grants before
        # enumerating borrowers, so neither race can grant effects after release.
        validate_owner(root, descriptor)
        yield
    finally:
        atomic(registration, {**record, 'phase': 'done'})


@contextmanager
def producer(root: Path):
    """Own/borrow a protected transaction. Never acquire this under state_lock."""
    root = root.resolve()
    descriptor = inherited(root)
    if descriptor is not None:
        with borrow(root, descriptor):
            yield
        return
    lease = uuid.uuid4().hex
    descriptor = {'root': str(root), 'id': lease, 'nonce': uuid.uuid4().hex}
    path = lease_path(root, lease)
    owner = {**descriptor, 'process': identity(), 'thread': threading.get_ident(), 'phase': 'running'}
    with transaction(root) as value:
        problem = active_problem(value)
        if problem:
            raise ReviewError(problem)
        atomic(path / 'owner.json', owner)
        value['writers'][lease] = descriptor
    previous = os.environ.get(LEASE_ENV)
    os.environ[LEASE_ENV] = json.dumps(descriptor)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(LEASE_ENV, None)
        else:
            os.environ[LEASE_ENV] = previous
        # Close future grants before checking already-authorized borrowers.
        atomic(path / 'owner.json', {**owner, 'phase': 'closing'})
        with transaction(root) as value:
            if borrowers_quiet(path):
                value['writers'].pop(lease, None)
                atomic(path / 'owner.json', {**owner, 'phase': 'closed'})


def recover_writers(root: Path) -> None:
    """Explicitly retain recovery history; never infer safety from a timeout."""
    with transaction(root) as value:
        if active_problem(value):
            raise ReviewError('abandon active review before producer recovery')
        resolved = []
        for lease in value['writers']:
            path = lease_path(root, lease)
            owner = document(path / 'owner.json')
            if owner.get('native') and owner.get('phase') != 'closed':
                raise ReviewError('native invocation terminal proof is missing; host liveness alone cannot clear it')
            if (owner.get('phase') == 'running' and not stopped(owner.get('process'))
                    or not borrowers_quiet(path)):
                raise ReviewError('producer or borrower is still live; recovery refused')
            if owner.get('phase') not in ('running', 'closing', 'closed'):
                raise ReviewError('invalid producer phase; recovery refused')
            resolved.append((lease, path, owner))
        for lease, path, owner in resolved:
            atomic(path / 'owner.json', {**owner, 'phase': 'closed'})
            value['history'].append({'outcome': 'producer-recovered', 'owner': owner})
            del value['writers'][lease]


def body(text: str) -> str:
    if text.startswith('---\n'):
        end = text.find('\n---', 4)
        if end != -1:
            return text[end + 4:]
    return text


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode()).hexdigest()


def report_hash(text: str) -> str:
    return hashlib.sha256(body(text).strip().encode()).hexdigest()


def verdict(text: str) -> str:
    content = body(text).strip()
    if not content.startswith('# Review Report\n'):
        raise ReviewError('native report is not canonical: expected # Review Report first')
    headings = re.findall(r'^## (.+?)\s*$', content, re.MULTILINE)
    required = ['Verdict', 'Scope', 'Persona Applied', 'Findings',
                'Validation Reviewed', 'Residual Risks']
    if headings != required:
        raise ReviewError('native report is not canonical: missing, repeated or reordered sections')
    sections = re.split(r'^## .+?\s*$', content, flags=re.MULTILINE)[1:]
    if any(not section.strip() for section in sections):
        raise ReviewError('native report is not canonical: empty section')
    result = sections[0].strip()
    if not re.match(r'^(Approved|Changes requested|Unable to complete review)(?:\b|$)', result):
        raise ReviewError('native report is not canonical: missing explicit verdict')
    return result


def observe_session(root: Path, adapter: str, payload: dict) -> None:
    """Called by the native callback adapter, never by a parent approval API."""
    if adapter not in ('claude', 'codex'):
        raise ReviewError('unsupported native review adapter')
    session = payload.get('session_id')
    if (not isinstance(session, str) or not session.strip()
            or payload.get('hook_event_name') != 'SessionStart'
            or Path(payload.get('cwd', '')).resolve() != root.resolve()):
        raise ReviewError('native SessionStart identity/worktree is missing')
    with transaction(root) as value:
        key = adapter + ':' + session
        existing = value['sessions'].get(key)
        record = {'adapter': adapter, 'session': session, 'root': str(root.resolve())}
        if existing is not None and any(existing.get(key) != item for key, item in record.items()):
            raise ReviewError('conflicting native session observation')
        if existing is None:
            value['sessions'][key] = record


def enable(root: Path, task: str, adapter: str, session: str, report: str) -> None:
    """Request native qualification. Observation is not completion or trust proof."""
    with transaction(root) as value:
        if adapter not in ('claude', 'codex'):
            raise ReviewError('unsupported native review adapter')
        if adapter + ':' + session not in value['sessions']:
            raise ReviewError('native parent session has not been observed; restart with native hooks enabled')
        if active_problem(value):
            raise ReviewError('overlapping review request')
        request = value.get('request')
        if request:
            value['history'].append({'outcome': 'superseded-request', 'request': request,
                                     'interval': value.get('interval')})
        value['request'] = {'task': task, 'adapter': adapter, 'session': session,
                            'report': report, 'phase': 'awaiting-native-review'}
        if (root / report).is_file():
            value['request']['pending_sha256'] = report_hash((root / report).read_text())
        value['interval'] = None
        base = directory(root)
        atomic(base.parent.parent / 'review-expectations' / (base.name + '.json'),
               {'root': str(root.resolve()), 'request': {key: value['request'][key]
                 for key in ('task', 'adapter', 'session', 'report')}})


def request_for(value: dict, task: str, adapter: str, session: str) -> dict:
    request = value.get('request')
    if (not isinstance(request, dict) or request.get('task') != task
            or request.get('adapter') != adapter or request.get('session') != session):
        raise ReviewError('native review task/session/adapter does not match the opt-in request')
    return request


def start(root: Path, task: str, adapter: str, session: str, child: str,
          profile: str, pins: dict, entries: list) -> None:
    with transaction(root) as value:
        request_for(value, task, adapter, session)
        assert_quiet(value)
        if value.get('interval') is not None:
            raise ReviewError('overlapping or completed review; explicitly restart with a fresh report path')
        if not child or child == session or profile != 'reviewer':
            raise ReviewError('native distinct reviewer identity/profile is missing')
        for previous in value['history']:
            old = previous.get('interval') or {}
            if (old.get('adapter'), old.get('session'), old.get('child')) == (adapter, session, child):
                raise ReviewError('native reviewer child identity cannot be reused; spawn a new reviewer invocation')
        if callable(pins):
            pins, entries = pins()
        value['interval'] = {'id': uuid.uuid4().hex, 'task': task, 'adapter': adapter,
                             'session': session, 'child': child, 'profile': profile,
                             'phase': 'active', 'pins': pins, 'archive': entries}
        interval = value['interval']
        capture = {key: interval[key] for key in ('id', 'task', 'adapter', 'session',
                                                 'child', 'profile', 'pins', 'archive')}
        base = directory(root) / 'captures' / interval['id']
        atomic(base / 'capture.json', capture)
        (base / 'capture.json').chmod(0o444)
        interval['capture_sha256'] = digest(capture)
        atomic(base / 'publication.json', {'initial': digest(entries), 'completed': [], 'pending': None})


def stop(root: Path, task: str, adapter: str, session: str, child: str,
         report: str, pins: dict) -> None:
    failure = None
    with transaction(root) as value:
        request_for(value, task, adapter, session)
        assert_quiet(value)
        interval = value.get('interval')
        if not isinstance(interval, dict) or interval.get('child') != child:
            raise ReviewError('native completion has no matching reviewer start')
        if interval['phase'] == 'completed' and interval.get('report') == report and interval['pins'] == pins:
            return
        if interval['phase'] != 'active':
            raise ReviewError('native completion conflicts with closed review; restart explicitly')
        if callable(pins):
            pins = pins()
        interval['report'] = report if isinstance(report, str) else None
        try:
            if not isinstance(report, str):
                raise ReviewError('native completion report is missing')
            result = verdict(report)
            if pins != interval['pins']:
                raise ReviewError('reviewed candidate changed during native review')
            interval.update(phase='completed', verdict=result, report_sha256=report_hash(report))
        except ReviewError as error:
            failure = str(error)
            interval.update(phase='failed', problem=failure)
        completion = {key: interval.get(key) for key in ('id', 'task', 'adapter', 'session', 'child',
                      'phase', 'pins', 'report', 'report_sha256', 'verdict', 'problem')}
        completion_path = directory(root) / 'captures' / interval['id'] / 'completion.json'
        atomic(completion_path, completion)
        completion_path.chmod(0o444)
        interval['completion_sha256'] = digest(completion)
        value['history'].append({'outcome': interval['phase'], 'interval': dict(interval)})
    if failure:
        raise ReviewError(failure)


def qualification_problem(root: Path, task: str, pins: dict, report: str | None = None) -> str | None:
    value = read(root)
    if (value.get('request') or {}).get('task') != task:
        return None  # Historical and non-opted-in tasks retain their existing behavior.
    interval = value.get('interval') or {}
    if interval.get('phase') != 'completed':
        return 'mechanical review requested; awaiting qualified native reviewer completion'
    if not str(interval.get('verdict', '')).startswith('Approved'):
        return 'native reviewer did not approve this candidate'
    if interval.get('pins') != pins:
        old, new = interval.get('pins', {}), pins
        changed = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
        return 'mechanical review candidate changed: ' + ', '.join(changed)
    captured = interval.get('report')
    try:
        completion = document(directory(root) / 'captures' / interval['id'] / 'completion.json')
        if (digest(completion) != interval.get('completion_sha256') or
                any(interval.get(key) != item for key, item in completion.items())):
            return 'immutable native completion receipt changed'
        if not isinstance(captured, str) or verdict(captured) != interval.get('verdict'):
            return 'native report receipt is malformed'
    except ReviewError as error:
        return str(error)
    if report_hash(captured) != interval.get('report_sha256'):
        return 'native captured report hash changed'
    if report is not None and report_hash(report) != interval['report_sha256']:
        return 'saved report body does not match the actual native reviewer report'
    return None


def assert_owned(root: Path) -> None:
    """Direct internal producers must already own the opted-in transaction."""
    value = read(root)
    if value.get('request') is None and not active_problem(value):
        return
    descriptor = inherited(root)
    if descriptor is None:
        raise ReviewError(active_problem(value) or 'protected producer requires ownership before state locking')
    validate_owner(root, descriptor)


def captured_window(root: Path, interval: dict) -> list:
    path = directory(root) / 'captures' / interval['id'] / 'capture.json'
    receipt = document(path)
    if digest(receipt) != interval.get('capture_sha256'):
        raise ReviewError('immutable reviewed archive changed')
    if any(receipt.get(key) != interval.get(key) for key in receipt):
        raise ReviewError('review interval disagrees with immutable reviewed archive')
    entries = receipt.get('archive')
    if not isinstance(entries, list) or len(entries) > ledger.MAX_ENTRIES:
        raise ReviewError('invalid reviewed ledger archive')
    return entries


def proven_window(root: Path, interval: dict, *, allow_pending=False) -> tuple[list, dict, Path]:
    window = captured_window(root, interval)
    path = directory(root) / 'captures' / interval['id'] / 'publication.json'
    chain = document(path)
    if chain.get('initial') != digest(window) or not isinstance(chain.get('completed'), list):
        raise ReviewError('invalid ledger publication archive/chain')
    for sequence, transition in enumerate(chain['completed'], 1):
        if transition.get('outcome') == 'aborted':
            replay_append(window, transition, sequence)
            continue
        window = replay_append(window, transition, sequence)
    if chain.get('pending') is not None and not allow_pending:
        raise ReviewError('interrupted ledger publication; explicitly recover before advancement')
    return window, chain, path


def replay_append(previous: list, transition: dict, sequence: int) -> list:
    additions = transition.get('append')
    if (transition.get('sequence') != sequence or transition.get('previous') != digest(previous)
            or not isinstance(additions, list) or not additions):
        raise ReviewError('invalid ledger append transition sequence/payload')
    all_entries = previous + additions
    expected = all_entries[-ledger.MAX_ENTRIES:]
    evicted = all_entries[:-ledger.MAX_ENTRIES]
    if transition.get('expected') != digest(expected) or transition.get('evicted') != evicted:
        raise ReviewError('invalid ledger append transition digest/oldest eviction')
    return expected


def evidence_problem(root: Path, state: dict) -> str | None:
    value = read(root)
    if (value.get('request') or {}).get('task') != state.get('task'):
        return None
    interval = value.get('interval') or {}
    if interval.get('phase') not in ('active', 'completed'):
        return 'mechanical review has no captured ledger archive'
    try:
        window, _, _ = proven_window(root, interval)
        if window != state.get('ledger', []):
            return 'reviewed ledger changed without an exact append transition'
    except (ReviewError, KeyError, TypeError) as error:
        return str(error)
    return None


def append_evidence(root: Path, state: dict, entries: list, publish) -> None:
    """Caller holds state_lock and producer ownership, never the guard lock.

    Keep ledger.append semantics unchanged. A pending write makes crashes fail closed.
    """
    value = read(root)
    interval = value.get('interval') or {}
    opted = ((value.get('request') or {}).get('task') == state.get('task')
             and interval.get('phase') == 'completed')
    if not opted:
        for entry in entries:
            ledger.append(state, entry)
        publish(state)
        return
    window, chain, path = proven_window(root, interval)
    if state.get('ledger', []) != window:
        raise ReviewError('ledger changed outside proven append publication')
    expected_state = {'ledger': list(window)}
    for entry in entries:
        ledger.append(expected_state, entry)
    expected = expected_state['ledger']
    transition = {'sequence': len(chain['completed']) + 1, 'previous': digest(window),
                  'append': entries, 'expected': digest(expected),
                  'evicted': (window + entries)[:-ledger.MAX_ENTRIES]}
    replay_append(window, transition, transition['sequence'])
    chain['pending'] = transition
    atomic(path, chain)
    state['ledger'] = expected
    publish(state)
    chain['completed'].append(transition)
    chain['pending'] = None
    atomic(path, chain)


def recover_publication(root: Path, state: dict) -> None:
    """Explicit recovery under state_lock after unresolved writers are cleared."""
    interval = read(root).get('interval') or {}
    window, chain, path = proven_window(root, interval, allow_pending=True)
    pending = chain.get('pending')
    if pending is None:
        return
    expected = replay_append(window, pending, len(chain['completed']) + 1)
    if state.get('ledger', []) == expected:
        chain['completed'].append(pending)
    elif state.get('ledger', []) == window:
        chain['completed'].append({**pending, 'outcome': 'aborted'})
    else:
        raise ReviewError('interrupted ledger publication has a third state; preserve for diagnosis')
    chain['pending'] = None
    atomic(path, chain)


@contextmanager
def target_producer(target: Path):
    """Protect the actual Git target; a non-Git bootstrap has no review state."""
    root = git_root(target)
    if root is None:
        yield
        return
    with producer(root):
        yield


def git_root(target: Path) -> Path | None:
    target = Path(target).resolve()
    probe = target
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    result = subprocess.run(['git', '-C', str(probe if probe.is_dir() else probe.parent),
                             'rev-parse', '--show-toplevel'], env=git_environment(), capture_output=True, text=True)
    if result.returncode:
        return None
    return Path(result.stdout.strip()).resolve()


def protected(select, when=None):
    """Wrap public producer boundaries, including direct Python workflow calls."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if when is not None and not when(*args, **kwargs):
                return function(*args, **kwargs)
            with target_producer(select(*args, **kwargs)):
                return function(*args, **kwargs)
        return wrapped
    return decorate


EDIT_TOOLS = frozenset({'Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'apply_patch', 'StrReplace', 'Delete'})
GIT_TARGET_ENV = frozenset({'GIT_DIR', 'GIT_COMMON_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE',
                            'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES'})
READERS = {
    'lifecycle.py': {'status', 'gate', 'reuse', 'scan-diff', 'audit', 'trace', 'analyze',
                     'queue-from-spec', 'observations', 'hook'},
    'okf.py': {'show', 'list', 'search', 'context', 'validate', 'records', 'affected',
               'sync-check', 'checkpoint', 'handoff'},
}
GIT_WRITERS = frozenset({'commit', 'merge', 'reset', 'checkout', 'switch', 'fetch', 'pull', 'push',
    'add', 'rm', 'mv', 'restore', 'clean', 'apply', 'checkout-index', 'update-index', 'read-tree'})


def git_invocations(command: str, cwd: Path, environment: dict) -> list[dict]:
    """Recognize literal Git segments; leave arbitrary programs outside this boundary."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|')
    lexer.whitespace_split, lexer.commenters = True, ''
    try:
        tokens = list(lexer)
    except ValueError as failure:
        raise ReviewError('unsupported shell syntax for Git routing; use a literal git command') from failure
    segments, current = [], []
    for word in tokens:
        if word in (';', '&&', '||'):
            segments.append(current)
            current = []
        else:
            current.append(word)
    segments.append(current)
    result = []
    for words in segments:
        if not words:
            continue
        env, words = dict(environment), list(words)
        if words[0] == 'cd' and len(words) == 2:
            if any(char in words[1] for char in ('$','`')):
                raise ReviewError('dynamic shell directory is unsupported; use tool workdir or literal git -C')
            cwd = (cwd / Path(words[1]).expanduser()).resolve()
            continue
        while words and words[0] in ('command', 'env'):
            words.pop(0)
        if words and words[0].startswith('-') and any(Path(word).name in ('git', 'git.exe') for word in words):
            raise ReviewError('unsupported Git command wrapper options; use literal env assignments or git -C')
        while words and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', words[0]):
            key, _, value = words.pop(0).partition('=')
            env[key] = value
        if not words or Path(words[0]).name not in ('git', 'git.exe'):
            continue
        executable, prefix = words.pop(0), []
        while words and words[0].startswith('-'):
            word = words.pop(0)
            key = word.partition('=')[0]
            if word in ('-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env'):
                if not words:
                    raise ReviewError('Git global option is missing its value; routing refused')
                prefix.extend([word, words.pop(0)])
            elif (word.startswith(('-C', '-c')) and len(word) > 2 or
                  '=' in word and key in ('--git-dir', '--work-tree', '--namespace', '--config-env')):
                prefix.append(word)
            elif word in ('--no-pager', '-P', '--no-optional-locks', '--literal-pathspecs',
                          '--glob-pathspecs', '--noglob-pathspecs', '--icase-pathspecs'):
                prefix.append(word)
            else:
                raise ReviewError('unsupported Git global option; use a literal checkout or git -C')
        if not words:
            continue
        verb, arguments = words[0], words[1:]
        if verb in GIT_WRITERS and (any(w in ('|','&') for w in arguments) or
                any(char in word for word in [executable, *prefix, *[env[k] for k in GIT_TARGET_ENV if k in env]]
                    for char in ('$','`'))):
            raise ReviewError('dynamic Git target routing is unsupported; use literal workdir/selector values')
        result.append({'executable': executable, 'prefix': prefix, 'env': env,
                       'cwd': cwd, 'verb': verb, 'arguments': arguments})
    return result


def git_probe(invocation: dict, arguments: list[str]) -> list[str]:
    env = {**invocation['env'], 'GIT_TERMINAL_PROMPT': '0', 'GIT_PAGER': 'cat'}
    try:
        result = subprocess.run([invocation['executable'], *invocation['prefix'], '--no-pager', *arguments],
            cwd=invocation['cwd'], env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as failure:
        raise ReviewError('Git target metadata probe unavailable; mutation refused') from failure
    if result.returncode:
        raise ReviewError('Git target cannot be established; use an existing literal checkout or git -C')
    return result.stdout.splitlines()


def metadata_owners(path: Path, *, shared=False) -> set[Path]:
    """Use Git's registered checkouts, including linked worktrees; never slice '.git'."""
    physical = git_root(path)
    if physical is not None:
        return {physical}
    candidate = path if path.is_dir() else path.parent
    for _ in range(12):
        probe = {'executable': 'git', 'prefix': ['--git-dir=' + str(candidate)],
                 'env': git_environment(), 'cwd': candidate if candidate.is_dir() else candidate.parent}
        try:
            common = git_probe(probe, ['rev-parse', '--path-format=absolute', '--git-common-dir'])
            if len(common) != 1:
                raise ReviewError('invalid Git metadata identity')
            rows = git_probe(probe, ['worktree', 'list', '--porcelain'])
            owners = []
            for row in rows:
                if not row.startswith('worktree '):
                    continue
                root = Path(row[len('worktree '):]).resolve()
                if not root.is_dir() or git_root(root) != root:
                    continue
                own = {'executable': 'git', 'prefix': ['-C', str(root)], 'env': git_environment(), 'cwd': root}
                gitdir = Path(git_probe(own, ['rev-parse', '--absolute-git-dir'])[0]).resolve()
                owners.append((gitdir, root))
            matches = [(len(gitdir.parts), root) for gitdir, root in owners
                       if path == gitdir or gitdir in path.parents]
            if shared and owners:
                return {root for _, root in owners}
            if matches:
                depth = max(n for n, _ in matches)
                return {root for n, root in matches if n == depth}
        except ReviewError:
            pass  # A metadata file's immediate parent need not itself be a Git directory.
        if candidate.parent == candidate:
            break
        candidate = candidate.parent
    raise ReviewError('Git metadata owner is unsupported or ambiguous; use an ordinary checkout/index')


def git_operation_roots(command: str, cwd: Path, environment: dict) -> set[Path]:
    roots = set()
    for invocation in git_invocations(command, cwd, environment):
        if invocation['verb'] not in GIT_WRITERS:
            continue
        rows = git_probe(invocation, ['rev-parse', '--path-format=absolute', '--show-toplevel'])
        if len(rows) != 1:
            raise ReviewError('Git worktree routing is unavailable; mutation refused')
        root = Path(rows[0]).resolve()
        if git_root(root) != root:
            raise ReviewError('Git selected a non-checkout target; mutation refused')
        roots.add(root)
        gitdir = Path(git_probe(invocation, ['rev-parse', '--absolute-git-dir'])[0]).resolve()
        roots.update(metadata_owners(gitdir))
        for key, name, shared in (('GIT_INDEX_FILE', 'index', False),
                                  ('GIT_OBJECT_DIRECTORY', 'objects', True)):
            if key in invocation['env']:
                target = Path(git_probe(invocation, ['rev-parse', '--path-format=absolute', '--git-path', name])[0]).resolve()
                roots.update(metadata_owners(target, shared=shared))
        if 'GIT_COMMON_DIR' in invocation['env']:
            common = Path(git_probe(invocation, ['rev-parse', '--path-format=absolute', '--git-common-dir'])[0]).resolve()
            roots.update(metadata_owners(common, shared=True))
        if 'GIT_ALTERNATE_OBJECT_DIRECTORIES' in invocation['env']:
            raise ReviewError('alternate Git object directory lists are unsupported for protected mutations')
    return roots


def command_mutates(command: str) -> bool:
    try:
        if any(inv['verb'] in GIT_WRITERS for inv in git_invocations(command, Path.cwd(), os.environ)):
            return True
    except ReviewError:
        if re.search(r'\bgit\b', command) and any(re.search(r'\b' + re.escape(verb) + r'\b', command) for verb in GIT_WRITERS):
            return True
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    for index, token in enumerate(tokens):
        name = Path(token).name
        remaining = tokens[index + 1:]
        if name in ('lifecycle.py', 'okf.py'):
            if name == 'okf.py' and remaining[:1] == ['--bundle']:
                remaining = remaining[2:]
            elif name == 'okf.py' and remaining and remaining[0].startswith('--bundle='):
                remaining = remaining[1:]
            verb = remaining[0] if remaining else ''
            if verb in READERS[name]:
                continue
            if name == 'lifecycle.py':
                if (verb == 'review' and remaining[1:2] in (['status'], ['abandon'], ['recover'])):
                    continue
                if (verb == 'assure' and '--run' not in remaining or
                        verb == 'finish' and '--apply' not in remaining or
                        verb == 'merge' and '--dry-run' in remaining):
                    continue
            else:
                if (verb == 'reindex' and '--check' in remaining or
                        verb == 'queue' and '--archive' not in remaining and '--record-session' not in remaining):
                    continue
            return True
        if name == 'install.py' and '--check' not in remaining:
            return True
        if name in ('pr_sync.py', 'autonomy_driver.py', 'autonomy_validation.py'):
            return True
        if name == 'artifacts.py' and remaining[:1] != ['verify']:
            return True
        if name == 'gh' and remaining[:2] in (['pr', 'create'], ['pr', 'ready']):
            return True
    return False


def tool_mutates(data: dict) -> bool:
    if data.get('tool_name') in EDIT_TOOLS:
        return True
    command = (data.get('tool_input') or {}).get('command', data.get('command'))
    return isinstance(command, str) and command_mutates(command)


def operation_roots(data: dict) -> list[Path]:
    """Resolve recognized explicit targets; Git metadata/non-Git scratch is separate."""
    values = data.get('tool_input') or {}
    base = Path(data.get('cwd') or os.getcwd()).expanduser()
    if 'workdir' in values:
        workdir = values['workdir']
        if not isinstance(workdir, str) or not workdir.strip():
            raise ReviewError('invalid tool_input.workdir: provide a non-empty directory path inside a Git worktree')
        base = (base / Path(workdir).expanduser()).resolve()
        if not base.is_dir() or git_root(base) is None:
            raise ReviewError('invalid tool_input.workdir: select an existing Git worktree directory')
    base = base.resolve()
    paths, selected_roots = [], set()
    if data.get('tool_name') in EDIT_TOOLS:
        edits = [values, *(values.get('edits') or [])]
        for edit in edits:
            if not isinstance(edit, dict):
                continue
            for key in ('file_path', 'path', 'target_file', 'notebook_path'):
                if isinstance(edit.get(key), str):
                    paths.append(base / Path(edit[key]).expanduser())
        patch = values.get('command') or values.get('input') or values.get('patch') or ''
        if data.get('tool_name') == 'apply_patch' and isinstance(patch, str):
            for pair in re.findall(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$', patch, re.M):
                paths.extend(base / Path(name).expanduser() for name in pair if name)
    else:
        try:
            tokens = shlex.split(values.get('command') or data.get('command') or '')
        except ValueError:
            tokens = []
        selected_roots = git_operation_roots(values.get('command') or data.get('command') or '',
            base, {**os.environ, **(values.get('env') or {})})
        for index, token in enumerate(tokens):
            name, remaining = Path(token).name, tokens[index + 1:]
            if name == 'install.py':
                positional = [word for word in remaining if not word.startswith('-')]
                if positional:
                    paths.append(base / Path(positional[0]).expanduser())
            if name in ('okf.py', 'pr_sync.py'):
                if '--bundle' in remaining and remaining.index('--bundle') + 1 < len(remaining):
                    paths.append((base / remaining[remaining.index('--bundle') + 1]).parent)
                for word in remaining:
                    if word.startswith('--bundle='):
                        paths.append((base / word.partition('=')[2]).parent)
    roots = selected_roots | {root for path in (paths or ([] if selected_roots else [base]))
                             if (root := git_root(path)) is not None}
    return sorted(roots)


def group_stopped(group: int) -> bool:
    if os.name != 'posix' or not isinstance(group, int) or group <= 0:
        return False
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def launch_plan(root: Path, command: list[str]) -> tuple[list[str], Path | None]:
    """Register the real command/group before exec, including non-cooperating checks."""
    descriptor = inherited(root)
    if os.name != 'posix' or descriptor is None:
        return command, None
    validate_owner(root, descriptor)
    error = lease_path(root, descriptor['id']) / 'launch-errors' / (uuid.uuid4().hex + '.json')
    argv = [sys.executable, '-I', '-S', str(Path(__file__).resolve()), '--producer-exec', str(root.resolve()),
            json.dumps(descriptor), str(error), '--', *command]
    return argv, error


def check_launch(error: Path | None) -> None:
    if error is not None and error.is_file():
        value = document(error)
        raise OSError(value['errno'], value['strerror'], value.get('filename'))


def run(root: Path, command: list[str], **kwargs):
    """subprocess.run with original argv/OS-error semantics and registered lifetime."""
    argv, error = launch_plan(root, command)
    check = kwargs.pop('check', False)
    try:
        result = subprocess.run(argv, **kwargs)
    except subprocess.TimeoutExpired as failure:
        failure.cmd = command
        raise
    check_launch(error)
    result.args = command
    if check:
        result.check_returncode()
    return result


def run_owned(command: list[str], **kwargs):
    """Keep execution cwd separate from the transaction's owning worktree."""
    raw = os.environ.get(LEASE_ENV)
    if not raw:
        return subprocess.run(command, **kwargs)
    descriptor = json.loads(raw)
    return run(Path(descriptor['root']), command, **kwargs)


def producer_exec(argv: list[str]) -> int:
    """Internal child pregrant handshake. Successful exec preserves PID and group."""
    if len(argv) < 6 or argv[0] != '--producer-exec' or argv[4] != '--':
        raise ReviewError('invalid internal producer launch')
    root, descriptor, error = Path(argv[1]), json.loads(argv[2]), Path(argv[3])
    command = argv[5:]
    if not command or descriptor.get('root') != str(root.resolve()):
        raise ReviewError('invalid internal producer launch identity/command')
    expected = lease_path(root, descriptor.get('id')) / 'launch-errors'
    if error.parent.resolve() != expected.resolve():
        raise ReviewError('invalid internal producer launch error destination')
    if os.getpgrp() != os.getpid():
        os.setsid()
    with borrow(root, descriptor, group=True):
        try:
            os.execvpe(command[0], command, os.environ)
        except OSError as failure:
            atomic(error, {'errno': failure.errno, 'strerror': failure.strerror,
                           'filename': os.fsdecode(failure.filename or command[0])})
    return 127


if __name__ == '__main__':
    try:
        raise SystemExit(producer_exec(sys.argv[1:]))
    except (ReviewError, OSError, KeyError) as failure:
        print(f'review producer: {failure}', file=sys.stderr)
        raise SystemExit(1)
