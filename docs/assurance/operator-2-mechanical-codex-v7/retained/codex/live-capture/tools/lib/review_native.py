#!/usr/bin/env python3
"""Native review callbacks and lifecycle integration; Python 3.9+, stdlib only.

Synthetic callbacks exercise this contract, not actual native-runtime qualification.
The CLI accepts callbacks only beneath an identifiable native launcher on Linux.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

sys.dont_write_bytecode = True
import review_guard as guard

EVENTS = ('SessionStart', 'SubagentStart', 'SubagentStop', 'PreToolUse', 'PostToolUse')


def configuration(root: Path, adapter: str) -> str:
    name = '.claude/settings.json' if adapter == 'claude' else '.codex/hooks.json'
    path = root / name
    try:
        data = json.loads(path.read_text())
        hooks = data['hooks']
        for event in EVENTS:
            matches = [hook for group in hooks.get(event, []) for hook in group.get('hooks', [])
                       if group.get('matcher') in (None, '', '*', '.*',
                          *(['reviewer'] if event in ('SubagentStart', 'SubagentStop') else []))
                       if hook.get('type') == 'command' and 'review_native.py' in hook.get('command', '')
                       and f'--adapter {adapter}' in hook['command']]
            if not matches:
                raise guard.ReviewError(f'{name}: required native {event} handler is missing')
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise guard.ReviewError(f'native hook configuration unavailable: {error}') from error
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_launcher(adapter: str) -> dict:
    """Native process ancestry is execution evidence, not a parent role/trust flag."""
    pid = os.getppid()
    for _ in range(32):
        try:
            process = Path(f'/proc/{pid}')
            argv = [os.fsdecode(word) for word in (process / 'cmdline').read_bytes().split(b'\0') if word]
            names = {Path(word).name for word in argv[:3]}
            if names & {adapter, adapter + '.exe', adapter + '.js'}:
                return guard.identity(pid)
            fields = (process / 'stat').read_text().rsplit(')', 1)[1].split()
            pid = int(fields[1])
            if pid <= 1:
                break
        except (OSError, ValueError, IndexError):
            break
    raise guard.ReviewError('native launcher cannot be identified; mechanical capture is unavailable on this runtime')


def file_pin(path: Path) -> dict:
    if path.is_symlink():
        return {'kind': 'symlink', 'target': os.readlink(path)}
    try:
        return {'kind': 'file', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'executable': bool(path.stat().st_mode & 0o111)}
    except FileNotFoundError:
        return {'kind': 'missing'}


def metadata(text: str) -> str:
    stripped = guard.body(text)
    return text[:-len(stripped)] if stripped else text


def candidate(root: Path, state: dict) -> dict:
    """Caller provides guard→state serialization for native start/completion."""
    import lifecycle
    value = guard.read(root)
    request = value.get('request') or {}
    if request.get('task') != state.get('task'):
        raise guard.ReviewError('mechanical review task changed')
    report = request['report']
    inventory = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z', '-co',
                                         '--exclude-standard']).split(b'\0')
    names = {os.fsdecode(name) for name in inventory if name}
    source = {}
    for name in sorted(names):
        if name.startswith(lifecycle.RECORD_DIR + '/') and name.endswith('.json'):
            continue
        if name == report:
            continue
        if not (root / name).exists() and not (root / name).is_symlink():
            continue  # A committed deletion and the reviewed deletion have identical content.
        source[name] = file_pin(root / name)
    report_path = root / report
    if report_path.is_symlink() or not report_path.is_file():
        raise guard.ReviewError('reserved native report is missing or is a symlink')
    refs = {}
    for stage in ('intent', 'plan'):
        record = state.get('stages', {}).get(stage) or {}
        ref = record.get('ref')
        if not ref or not (root / ref).is_file() or lifecycle.ref_hash(root / ref) != record.get('sha256'):
            raise guard.ReviewError(f'approved {stage} artifact is missing or changed')
        refs[stage] = dict(record)
    return {'source': source, 'artifacts': refs, 'converge': state.get('converge'),
            'native_session': value['sessions'].get(request['adapter'] + ':' + request['session']),
            'task_contract': {key: state.get(key) for key in ('task', 'tier', 'kind', 'user_set')},
            'redgreen': state.get('redgreen', []),
            'report_metadata': metadata(report_path.read_text()),
            'report_executable': bool(report_path.stat().st_mode & 0o111)}


def snapshot(root: Path, *, starting=False):
    import lifecycle
    with lifecycle.state_lock(root):
        state = lifecycle.require_state(root)
        if starting:
            if state['tier'] not in ('L2', 'L3'):
                raise guard.ReviewError('mechanically bound review requires L2/L3')
            problem = lifecycle.gate_problem(state, 'review')
            if problem:
                raise guard.ReviewError(problem)
            run = state.get('converge') or {}
            intent = state['stages'].get('intent') or {}
            if (not run or run.get('spec_sha256') != intent.get('sha256')
                    or run.get('tree') != lifecycle.tree_hash(root)
                    or any(r.get('status') == 'FAIL' for r in run.get('results', []))):
                raise guard.ReviewError('current successful convergence is required before native review')
        pins = candidate(root, state)
        if starting:
            return pins, state.get('ledger', [])
        problem = guard.evidence_problem(root, state)
        if problem:
            raise guard.ReviewError(problem)
        return pins


def problem(root: Path, state: dict, report: Path | None = None) -> str | None:
    request = guard.read(root).get('request') or {}
    expected = state.get('mechanical_review')
    recorded_native = state.get('stages', {}).get('review', {}).get('native_review')
    if request.get('task') != state.get('task') and not expected and not recorded_native:
        return None
    if request.get('task') != state.get('task'):
        return 'mechanical review journal/request is unavailable; native mode cannot downgrade to legacy'
    if expected and (not isinstance(expected, dict) or
                     any(request.get(key) != item for key, item in expected.items())):
        return 'mechanical review journal disagrees with the durable task opt-in'
    try:
        destination = root / request['report']
        if report is not None and report.resolve() != destination.resolve():
            return 'Review must use the reserved native report path'
        issue = guard.evidence_problem(root, state)
        if issue:
            return issue
        content = (report or destination).read_text()
        issue = guard.qualification_problem(root, state['task'], candidate(root, state), content)
        if issue:
            return issue
        if report is None and state.get('stages', {}).get('review', {}).get('native_review') != identity(root):
            return 'record mechanically bound Review for this native completion before advancement'
        return None
    except (OSError, ValueError, KeyError) as error:
        return f'mechanical review unavailable: {error}'


def identity(root: Path) -> dict:
    interval = guard.read(root).get('interval') or {}
    return {key: interval.get(key) for key in ('id', 'adapter', 'session', 'child',
            'capture_sha256', 'completion_sha256', 'report_sha256')}


def full_index_commit(command: str, environment: dict | None = None) -> bool:
    """Path-limited commits select a different tree than the checked full index."""
    try:
        tokens = shlex.split(command)
        if any(word.partition('=')[0] in guard.GIT_TARGET_ENV or word.startswith('GIT_CONFIG_') for word in tokens):
            return False
        if any(word.partition('=')[0] in ('--git-dir', '--work-tree') for word in tokens):
            return False
        effective = os.environ if environment is None else environment
        if any(key in guard.GIT_TARGET_ENV or key.startswith('GIT_CONFIG_') for key in effective):
            return False
        invocations = guard.git_invocations(command, Path.cwd(), os.environ if environment is None else environment)
        if any(word == '-c' or word.startswith('-c') or word.startswith('--config-env')
               for invocation in invocations for word in invocation['prefix']):
            return False
        offset = next(n for n, word in enumerate(tokens) if Path(word).name == 'git') + 1
        while offset < len(tokens) and tokens[offset].startswith('-'):
            offset += 2 if tokens[offset] in ('-C', '-c', '--git-dir', '--work-tree', '--namespace') else 1
        if offset >= len(tokens) or tokens[offset] != 'commit':
            return False
        args = tokens[offset + 1:]
    except (ValueError, StopIteration, guard.ReviewError):
        return False
    valued = {'-m', '-F', '-C', '-c', '-t', '--message', '--file', '--reuse-message',
              '--reedit-message', '--author', '--date', '--cleanup', '--template', '--trailer'}
    plain = {'--all', '--verbose', '--quiet', '--amend', '--no-edit', '--edit', '--signoff',
             '--no-signoff', '--no-verify', '--allow-empty', '--allow-empty-message', '--gpg-sign',
             '--no-gpg-sign', '--no-post-rewrite', '--reset-author', '--status', '--no-status'}
    offset = 0
    while offset < len(args):
        word = args[offset]
        if word in ('&&', ';', '||', '|'):
            break
        if word in ('--', '--only') or word.startswith('--pathspec-from-file'):
            return False
        if word in valued:
            offset += 2
            continue
        if word.startswith('--'):
            if word.partition('=')[0] not in valued | plain:
                return False
        if word.startswith('-') and not word.startswith('--'):
            for n, flag in enumerate(word[1:], 1):
                if flag in 'mFCct':
                    if n == len(word) - 1:
                        offset += 1
                    break
                if flag == 'S':
                    break
                if flag not in 'avqnse':
                    return False
        elif not word.startswith('-'):
            return False
        offset += 1
    return True


def index_problem(root: Path, state: dict, command: str | None = None,
                  environment: dict | None = None) -> str | None:
    """A fresh working candidate cannot authorize delivery of different staged bytes."""
    import lifecycle
    value = guard.read(root)
    request = value.get('request') or {}
    if request.get('task') != state.get('task'):
        return None
    if command is not None and not full_index_commit(command, environment):
        return 'mechanical review requires a supported full index commit without path or tree-selection options'
    interval = value.get('interval') or {}
    expected = (interval.get('pins') or {}).get('source', {})
    actual = {}
    staged_report = None
    staged_report_executable = None
    try:
        records = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--stage', '-z'])
        for entry in records.split(b'\0'):
            if not entry:
                continue
            info, path = entry.split(b'\t', 1)
            mode, oid, stage = info.decode().split()
            name = os.fsdecode(path)
            if stage != '0':
                return 'index contains unresolved merge stages'
            if name.startswith(lifecycle.RECORD_DIR + '/') and name.endswith('.json'):
                continue
            content = subprocess.check_output(['git', '-C', str(root), 'cat-file', 'blob', oid])
            if name == request['report']:
                staged_report = content.decode()
                staged_report_executable = mode == '100755'
                continue
            if mode == '120000':
                actual[name] = {'kind': 'symlink', 'target': os.fsdecode(content)}
            elif mode in ('100644', '100755'):
                actual[name] = {'kind': 'file', 'sha256': hashlib.sha256(content).hexdigest(),
                                'executable': mode == '100755'}
            else:
                return f'index contains unsupported mode for {name}'
        if actual != expected:
            changed = sorted(k for k in actual.keys() | expected.keys() if actual.get(k) != expected.get(k))
            return 'index differs from reviewed source: ' + ', '.join(changed[:8])
        if (staged_report is None or guard.report_hash(staged_report) != interval.get('report_sha256')
                or metadata(staged_report) != interval.get('pins', {}).get('report_metadata')
                or staged_report_executable != interval.get('pins', {}).get('report_executable')):
            return 'index must include the unchanged captured report and its reviewed metadata'
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        return f'cannot verify reviewed index: {error}'
    return None


def handle(root: Path, adapter: str, data: dict, runtime: dict) -> None:
    """Normalize the two documented native payload families within the trust boundary."""
    if adapter not in ('claude', 'codex'):
        raise guard.ReviewError('unsupported native adapter')
    event, session = data.get('hook_event_name'), data.get('session_id')
    if not session or Path(data.get('cwd', '')).resolve() != root.resolve():
        raise guard.ReviewError('native callback is missing session/worktree identity')
    if data.get('trustStatus') in ('untrusted', 'disabled'):
        raise guard.ReviewError('current native callback reports untrusted/disabled execution; capture refused')
    request = guard.read(root).get('request') or {}
    if event in ('PreToolUse', 'PostToolUse', 'PostToolUseFailure'):
        granted = []
        try:
            for target in guard.operation_roots(data):
                native_tool(target, adapter, data, runtime)
                granted.append(target)
        except guard.ReviewError:
            if event == 'PreToolUse':
                for target in granted:
                    native_tool(target, adapter, {**data, 'hook_event_name': 'PostToolUseFailure'}, runtime)
            raise
        return
    if event != 'SessionStart' and not request:
        return
    pin = configuration(root, adapter)
    if event == 'SessionStart':
        guard.observe_session(root, adapter, data)
        with guard.transaction(root) as value:
            previous = value['sessions'][adapter + ':' + session]
            if ((value.get('interval') or {}).get('phase') == 'active'
                    and (previous.get('runtime') not in (None, runtime)
                         or previous.get('configuration') not in (None, pin))):
                raise guard.ReviewError('native runtime/configuration changed during active review; abandon and restart')
            value['sessions'][adapter + ':' + session].update(runtime=runtime, configuration=pin)
        return
    observed = guard.read(root)['sessions'].get(adapter + ':' + session)
    if not observed or observed.get('runtime') != runtime or observed.get('configuration') != pin:
        raise guard.ReviewError('native session/runtime/configuration changed or was not observed; restart the native session')
    if request.get('adapter') != adapter or request.get('session') != session:
        return  # Unrelated sessions/subagents have no requested review to satisfy.
    if data.get('agent_type') != 'reviewer':
        return
    task, child = request['task'], data.get('agent_id')
    if not isinstance(child, str) or not child:
        raise guard.ReviewError('native reviewer identity is missing')
    if event == 'SubagentStart':
        guard.start(root, task, adapter, session, child, 'reviewer', lambda: snapshot(root, starting=True), [])
    elif event == 'SubagentStop':
        guard.stop(root, task, adapter, session, child,
                   data.get('last_assistant_message'), lambda: snapshot(root))


def native_tool(root: Path, adapter: str, data: dict, runtime: dict) -> None:
    event = data['hook_event_name']
    if event == 'PreToolUse' and not guard.tool_mutates(data):
        return
    invocation = data.get('tool_use_id')
    if not isinstance(invocation, str) or not invocation:
        if guard.tool_mutates(data):
            raise guard.ReviewError('native mutation is missing its tool invocation ID')
        return
    key = hashlib.sha256((adapter + ':' + data['session_id'] + ':' + invocation).encode()).hexdigest()[:32]
    with guard.transaction(root) as value:
        if event == 'PreToolUse':
            issue = guard.active_problem(value)
            if issue:
                raise guard.ReviewError(issue)
            command = (data.get('tool_input') or {}).get('command')
            if isinstance(command, str):
                if driver_invocation(root, data, command):
                    return  # Its guarded write transactions release before agent launch/wait.
            if key in value['writers']:
                raise guard.ReviewError('duplicate native mutation start')
            owner = {'id': key, 'root': str(root.resolve()), 'nonce': invocation,
                     'process': runtime, 'phase': 'running', 'native': True}
            guard.atomic(guard.lease_path(root, key) / 'owner.json', owner)
            value['writers'][key] = {'native': True, 'session': data['session_id'], 'invocation': invocation}
        elif key in value['writers']:
            owner_path = guard.lease_path(root, key) / 'owner.json'
            owner = guard.document(owner_path)
            if owner.get('process') != runtime or not owner.get('native'):
                raise guard.ReviewError('native mutation completion identity conflicts')
            guard.atomic(owner_path, {**owner, 'phase': 'closed'})
            del value['writers'][key]


def driver_invocation(root: Path, data: dict, command: str) -> bool:
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if not words or any(word in ('&&', ';', '||', '|', '&') for word in words):
        return False
    if words[:1] == ['env']:
        words.pop(0)
    while words and '=' in words[0] and not words[0].startswith('-'):
        words.pop(0)
    if not words:
        return False
    invoked = words.pop(0)
    executable = Path(invoked).name
    if re.fullmatch(r'python(?:\d+(?:\.\d+)*)?(?:\.exe)?', executable):
        while words and words[0] in ('-u', '-B', '-E', '-I', '-s', '-S', '-O', '-OO', '-q', '--'):
            words.pop(0)
        if not words:
            return False
        script = words[0]
    elif executable == 'autonomy_driver.py':
        script = invoked
    else:
        return False
    base = Path(data.get('cwd') or root)
    if (data.get('tool_input') or {}).get('workdir'):
        base /= Path(data['tool_input']['workdir'])
    return (base / script).resolve() == (root / '.ai/scripts/autonomy_driver.py').resolve()


def prepare_report(root: Path, state: dict, name: str) -> str:
    import lifecycle
    import project_context
    destination = root / name
    if (Path(name).is_absolute() or '..' in Path(name).parts
            or not destination.resolve().is_relative_to(root.resolve())):
        raise guard.ReviewError('report must be a fresh repo-relative path')
    if any(p.is_symlink() for p in [destination, *destination.parents] if p != root.parent):
        raise guard.ReviewError('report path contains a symlink')
    tracked = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--', name], text=True)
    if destination.exists() or tracked.strip():
        raise guard.ReviewError('report path is pre-existing/tracked; choose a fresh destination')
    for entry in state.get('ledger', []):
        if name in entry.get('inputs', []):
            raise guard.ReviewError('report path is an explicit command input; choose another destination')
    if project_context.kind(root) != 'framework':
        try:
            relative = destination.relative_to(root / 'knowledge').as_posix()
        except ValueError as error:
            raise guard.ReviewError('adopter review report must be inside knowledge/') from error
        base = [sys.executable, str(root / '.ai/scripts/okf.py')]
        result = guard.run_owned([*base, 'new', relative, '--type', 'Review', '--title', 'Native review',
                                 '--description', 'Pending native independent review; no approval yet.'],
                                cwd=root, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise guard.ReviewError(result.stdout + result.stderr)
        result = guard.run_owned([*base, 'log', f'Mechanical review prepared at {name}; awaiting native reviewer completion.'],
                                cwd=root, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise guard.ReviewError(result.stdout + result.stderr)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text('# Pending native review\n\nNo approval recorded.\n')
    lifecycle.save(root, state)
    return name


def registered_runtime(entry: dict) -> bool:
    """Captured identity is registration evidence, not a sandbox-local lifetime proof."""
    runtime = entry.get('runtime')
    return (isinstance(runtime, dict) and type(runtime.get('pid')) is int
            and runtime['pid'] > 0 and isinstance(runtime.get('birth'), str)
            and bool(runtime['birth']) and bool(entry.get('configuration')))


def command(args) -> int:
    import lifecycle
    root = lifecycle.repo_root()
    if args.action == 'status':
        value = guard.read(root)
        state = lifecycle.require_state(root)
        issue = problem(root, state)
        print(json.dumps({'request': value.get('request'), 'phase': (value.get('interval') or {}).get('phase'),
                          'problem': issue, 'writers': value['writers'],
                          'runtime_liveness': 'not_assessed',
                          'observed_sessions': [{'adapter': entry.get('adapter'), 'session': entry.get('session')}
                              for entry in value['sessions'].values() if registered_runtime(entry)]}, sort_keys=True))
        return int(bool(issue))
    if args.action == 'abandon':
        with guard.transaction(root) as value:
            guard.assert_quiet(value)
            interval = value.get('interval')
            if interval is not None:
                interval['phase'] = 'abandoned'
                value['history'].append({'outcome': 'abandoned', 'reason': args.reason,
                                         'interval': dict(interval)})
            if value.get('request'):
                value['request']['phase'] = 'abandoned'
        return 0
    if args.action == 'recover':
        guard.recover_writers(root)
        with guard.lock(root):
            value = guard.read(root)
            guard.assert_quiet(value)
            if (value.get('interval') or {}).get('id'):
                with lifecycle.state_lock(root):
                    guard.recover_publication(root, lifecycle.require_state(root))
        return 0
    with guard.producer(root):
        with lifecycle.state_lock(root):
            state = lifecycle.require_state(root)
            request = guard.read(root).get('request') or {}
            if args.action in ('enable', 'restart'):
                if state['tier'] not in ('L2', 'L3'):
                    raise guard.ReviewError('mechanically bound review requires an L2/L3 task')
                if args.action == 'enable' and (request.get('task') == state['task'] or state.get('mechanical_review')):
                    raise guard.ReviewError('task already opted in; explicitly abandon/restart')
                if args.action == 'restart' and state.get('mechanical_review') and not request:
                    raise guard.ReviewError('mechanical review journal is unavailable; restore history before restart')
                adapter = args.adapter or request.get('adapter')
                session = args.session or request.get('session')
                observed = guard.read(root)['sessions'].get(str(adapter) + ':' + str(session))
                if not observed or observed.get('configuration') != configuration(root, adapter):
                    raise guard.ReviewError('native parent/configuration not observed; restart with current hooks')
                # A command sandbox may hide the host PID namespace. Pending opt-in
                # selects a registration; actual native start/stop revalidate its identity.
                if not registered_runtime(observed):
                    raise guard.ReviewError('observed native parent runtime identity is incomplete; restart with native hooks')
                state['mechanical_review'] = {'adapter': adapter, 'session': session, 'report': args.report}
                name = prepare_report(root, state, args.report)
                # No state lock is held across guard acquisition. Source preparation is complete.
            else:
                interval = guard.read(root).get('interval') or {}
                if request.get('task') != state['task'] or interval.get('phase') != 'completed':
                    raise guard.ReviewError('no completed native report to export')
                issue = guard.qualification_problem(root, state['task'], candidate(root, state))
                if issue:
                    raise guard.ReviewError(issue)
                path = root / request['report']
                existing = path.read_text()
                if guard.report_hash(existing) == interval['report_sha256']:
                    return 0
                # Only the pending scaffold may be replaced; never overwrite another report.
                if guard.report_hash(existing) != request.get('pending_sha256'):
                    raise guard.ReviewError('reserved report has conflicting content; restart instead')
                path.write_text(metadata(existing) + '\n\n' + guard.body(interval['report']))
                return 0
        guard.enable(root, state['task'], adapter, session, name)
    print('Mechanical review requested; awaiting qualified native reviewer start/completion.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['hook'])
    parser.add_argument('--adapter', choices=['claude', 'codex'], required=True)
    args = parser.parse_args(argv)
    try:
        import lifecycle
        raw = sys.stdin.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise guard.ReviewError('native callback exceeds capture size limit; no qualification recorded')
        data = json.loads(raw)
        root = lifecycle.repo_root(Path(data['cwd']))
        request = guard.read(root).get('request')
        if not request and data.get('hook_event_name') not in (*EVENTS, 'PostToolUseFailure'):
            return 0
        try:
            runtime = native_launcher(args.adapter)
        except guard.ReviewError:
            if not request:
                return 0  # Unsupported legacy harnesses do not acquire mechanical provenance.
            raise
        handle(root, args.adapter, data, runtime)
        return 0
    except (guard.ReviewError, ValueError, OSError, KeyError) as error:
        print(f'mechanical review: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
