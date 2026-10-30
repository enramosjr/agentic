"""Isolated native orchestration. Execution requires a separately approved allocation.

The frozen collector/scorer remain unchanged. Never call its Codex launch/config helper.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time


def load_observer(operator):
    sys.path.insert(0, str(operator.parent))
    spec = importlib.util.spec_from_file_location('frozen_live_observer', operator)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def override(observer, key, value):
    return ['-c', key + '=' + observer.toml(value)]


def signature(event, group, hook):
    return (event[0].lower() + event[1:], 'command', hook['command'], group.get('matcher'),
            hook.get('async', False), hook.get('timeout', 600), hook.get('statusMessage'),
            hook.get('additionalContextLimit'))


def allowed_handlers(root, collector):
    deployed = json.loads((root / '.codex/hooks.json').read_text())['hooks']
    return {source: {signature(event, group, hook)
        for event, groups in events.items() for group in groups for hook in group['hooks']
        if hook.get('type') == 'command'}
        for source, events in ((str(root / '.codex/hooks.json'), deployed),
                              ('/<session-flags>/config.toml', collector))}


def selected_handlers(preflight, expected, *, trusted=False):
    seen = {source: set() for source in expected}
    selected = []
    groups = preflight.get('_hooks', {}).get('data', [])
    if not groups or any(group.get('errors') for group in groups):
        raise ValueError('native hook discovery unavailable; no model launch')
    for group in groups:
        for hook in group.get('hooks', []):
            if not hook.get('enabled'):
                continue
            source = hook.get('sourcePath')
            actual = (hook.get('eventName'), hook.get('handlerType'), hook.get('command'),
                hook.get('matcher'), hook.get('async', False), hook.get('timeoutSec'),
                hook.get('statusMessage'), hook.get('additionalContextLimit'))
            if source not in expected or actual not in expected[source]:
                raise ValueError('unapproved enabled hook; no model launch')
            digest, key = hook.get('currentHash'), hook.get('key')
            if not isinstance(key, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest or ''):
                raise ValueError('native hook key/hash missing')
            if trusted and hook.get('trustStatus') != 'trusted':
                raise ValueError('exact fixture hook trust unavailable; no model launch')
            seen[source].add(actual)
            selected.append((key, digest))
    if seen != expected:
        raise ValueError('required frozen handlers missing or disabled')
    return sorted(selected)


def trust_overlay(observer, preflight, expected):
    # This policy requires explicit human approval of the frozen definitions. It is
    # invocation-local normal hash trust; it never disables the trust check.
    selected = selected_handlers(preflight, expected)
    state = copy.deepcopy(preflight.get('_configuration', {}).get('hooks', {}).get('state', {}))
    if not isinstance(state, dict):
        raise ValueError('native hook trust state malformed')
    for key, digest in selected:
        state[key] = {**state.get(key, {}), 'trusted_hash': digest}
    return override(observer, 'hooks.state', state), selected


def supplement(agent):
    return f'''\n\nMechanical review verification supplement (additional workflow constraint):
Preserve every original scenario success criterion. Use adapter {agent}. After declaring
the task and recording approved intent/plan, run lifecycle.py review status to identify
the actually observed current native parent session. Enable mechanical review BEFORE
convergence with review enable --adapter {agent} --session OBSERVED_SESSION --report
knowledge/history/reviews/native-review.md. Use the installed .ai/scripts/lifecycle.py.
Then complete convergence and delegate exactly one native reviewer using its reviewer
profile. Do not delegate other analysis/planning agents. Reviewer must remain read-only,
use the existing canonical template and return the complete Markdown report without a
preface/fence. Do not ask the reviewer to probe a denied write. After native completion,
use review save-report and record stage review at that exact reserved path. Never
reconstruct/repair/prefix the report. Append any required real validation refresh without
rerunning convergence, then finish existing Verify requirements. Stop honestly if capture,
runtime trust, canonical output or a gate refuses; no restart, retry or second reviewer.
Do not commit, push, create a PR or change trust/configuration. Existing strict outcome
and observer checks apply unchanged.\n'''


def retain_mechanical(root, agent, *, require_success):
    import lifecycle
    import review_guard
    import review_native
    destination = root.parent / 'mechanical-capture'
    destination.mkdir(mode=0o700)
    journal = review_guard.directory(root)
    if journal.is_dir():
        shutil.copytree(journal, destination / 'journal')
    errors = []
    try:
        state = lifecycle.load(root)
    except (OSError, ValueError, KeyError) as error:
        state = None
        errors.append('lifecycle state: ' + str(error))
    (destination / 'lifecycle-state.json').write_text(json.dumps(state, indent=2) + '\n')
    expectation = journal.parent.parent / 'review-expectations' / (journal.name + '.json')
    if expectation.is_file():
        shutil.copy2(expectation, destination / 'expectation.json')
    try:
        value = review_guard.read(root)
    except (OSError, ValueError, KeyError) as error:
        value = {}
        errors.append('mechanical journal: ' + str(error))
    if errors:
        (destination / 'capture-errors.json').write_text(json.dumps(errors, indent=2) + '\n')
    report_name = (value.get('request') or {}).get('report')
    if report_name and (root / report_name).is_file():
        shutil.copy2(root / report_name, destination / 'saved-review.md')
    # Evaluator attempt directories are temporary. Retain raw evidence externally
    # before its unchanged cleanup, including unsuccessful/trust-refused attempts.
    retained = Path(__file__).resolve().parent / 'retained' / agent
    retained.mkdir(parents=True, exist_ok=True)
    shutil.copytree(destination, retained / 'mechanical-capture', symlinks=True)
    if (root.parent / 'live-capture').is_dir():
        shutil.copytree(root.parent / 'live-capture', retained / 'live-capture', symlinks=True)
    if not require_success:
        return
    if errors:
        raise ValueError('native state is malformed; raw capture retained')
    if not state or 'verify' not in state.get('stages', {}):
        raise ValueError('native mechanical attempt did not reach Verify')
    issue = review_native.problem(root, state)
    if issue:
        raise ValueError('native mechanical final state refused: ' + issue)
    if (value.get('request', {}).get('adapter') != agent or
            not state.get('stages', {}).get('review', {}).get('native_review')):
        raise ValueError('actual native review receipt absent or wrong adapter')
    (retained / 'qualified-final-state.json').write_text(json.dumps({
        'adapter': agent, 'native_review': state['stages']['review']['native_review'],
        'verify': state['stages']['verify']}, indent=2) + '\n')


def prepare_capture_storage(root, agent):
    """Retain real Git receipts from the first write, even after attempt SIGKILL."""
    import review_guard
    import scratch
    value = review_guard.read(root)
    if value.get('writers') or value.get('request') or value.get('interval'):
        raise ValueError('fixture already has a producer/review; cannot relocate capture storage')
    retained = Path(__file__).resolve().parent / 'retained' / agent
    retained.mkdir(parents=True)
    metadata = retained / 'git-metadata'
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    def git(*args):
        return subprocess.run(['git', '-C', str(root), *args], env=env,
            capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    if Path(git('rev-parse', '--absolute-git-dir')).resolve() != (root / '.git').resolve() or not (root / '.git').is_dir():
        raise ValueError('expected independent fixture Git directory before relocation')
    head = git('rev-parse', 'HEAD')
    git('init', '-q', '--separate-git-dir', str(metadata))
    if git('rev-parse', 'HEAD') != head or Path(git('rev-parse', '--absolute-git-dir')).resolve() != metadata.resolve():
        raise ValueError('fixture Git relocation changed identity')
    refreshed = scratch.environment(root)
    temporary = (metadata / 'okf-scratch').resolve()
    if any(Path(refreshed[name]).resolve() != temporary for name in ('TMPDIR', 'TMP', 'TEMP')):
        raise ValueError('relocated scratch environment has an unexpected destination')
    os.environ.update({name: refreshed[name] for name in ('TMPDIR', 'TMP', 'TEMP')})
    (retained / 'relocation.json').write_text(json.dumps({'fixture': str(root), 'head': head,
        'git_metadata': str(metadata), 'temporary_environment': {
            name: os.environ[name] for name in ('TMPDIR', 'TMP', 'TEMP')}}, indent=2) + '\n')
    return retained


def capture_tools(observer, root, agent):
    directory = Path(__file__).resolve().parent / 'retained' / agent / 'live-capture'
    directory.mkdir(mode=0o700)
    tools = directory / 'tools'
    tools.mkdir()
    library = tools / 'lib'
    library.mkdir()
    for source in (Path(__file__).parent / '.ai/scripts').glob('*.py'):
        shutil.copy2(source, library / source.name)
    operator = Path(__file__).parent / '.ai/evals/checks/live_observer.py'
    helper = tools / 'live_observer.py'
    shutil.copy2(operator, helper)
    shutil.copy2(operator.parent / 'behavior.py', tools / 'behavior.py')
    command = shlex.join([sys.executable, str(helper), 'hook'])
    hooks = {event: [{'hooks': [{'type': 'command', 'command': command, 'timeout': 10}]}]
             for event in observer.EVENTS}
    return directory, hooks, command


def stream_native(observer, argv, root, directory, prompt):
    env = {**os.environ, 'GAP5_WORKSPACE': str(root), 'GAP5_CAPTURE': str(directory),
           'PYTHONDONTWRITEBYTECODE': '1'}
    data = bytearray()
    with (directory / 'native-stream.jsonl').open('xb') as raw, subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env) as child:
        try:
            child.stdin.write(prompt.encode())
            child.stdin.close()
            while True:
                chunk = os.read(child.stdout.fileno(), 16384)
                if not chunk:
                    break
                events_path = directory / 'events.jsonl'
                if len(data) + len(chunk) + (events_path.stat().st_size if events_path.exists() else 0) > observer.LIMIT:
                    raise ValueError('combined event-output cap exhausted')
                data.extend(chunk)
                raw.write(chunk)
                raw.flush()
                os.fsync(raw.fileno())
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
            code = child.wait()
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
    return code, data


def save_observations(root, agent, observations):
    destinations = (root.parent / 'live-observations.json',
        Path(__file__).resolve().parent / 'retained' / agent / 'live-observations.json')
    for path in destinations:
        with path.open('x') as output:
            path.chmod(0o600)
            json.dump(observations, output)
            output.flush()
            os.fsync(output.fileno())


def claude_launch(observer, binary, root, prompt):
    directory, hooks, _ = capture_tools(observer, root, 'claude')
    settings = {'hooks': hooks, 'permissions': {'allow': ['Bash(python3 .ai/scripts/*)',
        'Bash(python3 -m unittest*)', 'Bash(git *)']}}
    project = (root / '.claude/settings.json').read_text()
    for event, groups in json.loads(project)['hooks'].items():
        settings['hooks'][event] = [*groups, *settings['hooks'].get(event, [])]
    configuration = observer.configuration_digest({'settings': settings, 'project': project}, root.parent)
    argv = [str(binary), '-p', '--output-format', 'stream-json', '--verbose', '--forward-subagent-text',
        '--include-hook-events', '--model', observer.MODELS['claude'], '--effort', 'medium',
        '--permission-mode', 'acceptEdits', '--permission-prompts', 'none', '--setting-sources', 'project',
        '--strict-mcp-config', '--settings', json.dumps(settings)]
    (directory / 'invocation.json').write_text(json.dumps(argv, indent=2) + '\n')
    code, data = stream_native(observer, argv, root, directory, prompt)
    events = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]
    if len([event for event in events if event.get('event') == 'SubagentStart']) != 1:
        raise ValueError('exactly one observed native reviewer is required')
    native = observer.native_claude(events, data.decode('utf-8', errors='replace'), observer.VERSIONS['claude'])
    observations = observer.assemble('claude', events, native)
    observations['instrumentation']['configuration_sha256'] = configuration
    save_observations(root, 'claude', observations)
    return code


def codex_launch(observer, binary, root, prompt):
    import scratch
    directory, hooks, command = capture_tools(observer, root, 'codex')
    flags = ['--strict-config']
    values = {'projects': {str(root): {'trust_level': 'trusted'}},
        'model': observer.MODELS['codex'], 'model_reasoning_effort': 'medium',
        'model_provider': 'openai', 'model_providers': {}, 'approval_policy': 'never',
        'approvals_reviewer': 'user', 'sandbox_mode': 'workspace-write',
        'sandbox_workspace_write': {'writable_roots': [str(scratch.directory(root))]},
        'analytics': {'enabled': False}}
    for key, value in values.items():
        flags += override(observer, key, value)
    for event, groups in hooks.items():
        flags += override(observer, 'hooks.' + event, groups)
    expected = allowed_handlers(root, hooks)
    discovered = observer.native_codex(binary, [], hook_cwd=root, config=flags)
    overlay, selected = trust_overlay(observer, discovered, expected)
    flags += overlay
    preflight = observer.native_codex(binary, [], hook_cwd=root, config=flags)
    if selected_handlers(preflight, expected, trusted=True) != selected:
        raise ValueError('native handler hashes changed; no model launch')
    observer.require_codex_hooks(preflight, collector=command)
    effective = preflight['_configuration']
    if effective.get('model_provider') != 'openai' or effective.get('model_providers'):
        raise ValueError('custom provider configuration refused; no model launch')
    configuration = observer.configuration_digest(effective, root.parent)
    (directory / 'preflight.json').write_text(json.dumps({'handlers': selected,
        'flags': flags, 'configuration_sha256': configuration}, indent=2) + '\n')
    code, _ = stream_native(observer, [str(binary), *flags, 'exec', '--json', '-'], root, directory, prompt)
    events = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]
    starts = [event for event in events if event.get('event') == 'SubagentStart']
    if len(starts) != 1:
        raise ValueError('exactly one observed native reviewer is required')
    ids = list(dict.fromkeys([events[0]['session'], starts[0]['agent']]))
    native = observer.native_codex(binary, ids, hook_cwd=root, config=flags)
    if (selected_handlers(native, expected, trusted=True) != selected or
            observer.configuration_digest(native['_configuration'], root.parent) != configuration):
        raise ValueError('native configuration/handler drift after execution')
    observations = observer.assemble('codex', events, native)
    observations['instrumentation']['configuration_sha256'] = configuration
    save_observations(root, 'codex', observations)
    return code


def main():
    if os.environ.get('MECHANICAL_NATIVE_ALLOCATION') != 'two-control-cells-and-local-trust':
        raise ValueError('fresh explicit allocation and scoped trust approval required; no models launched')
    agent = sys.argv[1]
    if agent not in ('claude', 'codex'):
        raise ValueError('unsupported adapter')
    deadline = float(os.environ['LIFECYCLE_EVAL_DEADLINE'])
    if deadline <= time.time():
        raise ValueError('supervisor deadline expired')
    namespace = Path(__file__).resolve().parent
    manifest = json.loads((namespace / 'preparation.json').read_text())
    binary = Path(manifest['binaries'][agent]['path'])
    import hashlib
    if hashlib.sha256(binary.read_bytes()).hexdigest() != manifest['binaries'][agent]['sha256']:
        raise ValueError('native binary drift; no models launched')
    observer = load_observer(namespace / '.ai/evals/checks/live_observer.py')
    sys.path.insert(0, str(namespace / '.ai/scripts'))
    output = subprocess.run([str(binary), '--version'], capture_output=True, text=True, check=True, timeout=10).stdout
    if re.findall(r'(?<![\d.])\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.]+)?', output) != [observer.VERSIONS[agent]]:
        raise ValueError('pinned CLI version changed; no models launched')
    prompt = sys.stdin.read() + supplement(agent)
    root = Path.cwd().resolve()
    prepare_capture_storage(root, agent)
    if agent == 'codex':
        auth = subprocess.run([str(binary), 'login', 'status'], capture_output=True, text=True, timeout=10)
        if auth.returncode or 'Logged in using ChatGPT' not in auth.stdout + auth.stderr:
            raise ValueError('ChatGPT subscription authentication required; no models launched')
        try:
            code = codex_launch(observer, binary, root, prompt)
        except BaseException:
            retain_mechanical(Path.cwd().resolve(), agent, require_success=False)
            raise
        retain_mechanical(Path.cwd().resolve(), agent, require_success=code == 0)
        return code
    try:
        code = claude_launch(observer, binary, root, prompt)
    except BaseException:
        retain_mechanical(root, agent, require_success=False)
        raise
    retain_mechanical(Path.cwd().resolve(), agent, require_success=code == 0)
    return code


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('mechanical native launch refused: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
