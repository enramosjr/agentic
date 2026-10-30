"""Guarded Codex-only proposal; execution needs fresh allocation and scoped-trust approval."""
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
NAMESPACE = ROOT / 'docs/assurance/operator-2-mechanical-codex-v7'


def check_pin(path, expected):
    if (hashlib.sha256(path.read_bytes()).hexdigest() != expected['sha256'] or
            oct(stat.S_IMODE(path.stat().st_mode)) != expected['mode']):
        raise ValueError('prepared bytes/mode changed: ' + str(path))


def check_selected_campaign(path):
    value = json.loads(path.read_text())
    matrix, attempts = value.get('matrix', []), value.get('attempts', [])
    if (len(matrix) != 1 or len(attempts) != 1 or
            any(item.get('scenario_id') != 'control-delta' or item.get('repeat_index') != 1
                or item.get('outcome') != 'completed' for item in [*matrix, *attempts]) or
            attempts[0].get('status') not in ('PASS', 'FAIL', 'ERROR') or
            not value.get('totals', {}).get('complete') or
            value.get('budget', {}).get('reserved_seconds') != 0 or
            value.get('provenance', {}).get('agent', {}).get('id') != 'codex'):
        raise ValueError('selected campaign is incomplete or outside the approved Codex-only scope')


def main():
    if sys.argv[1:] != ['--authorized-allocation-and-scoped-trust']:
        raise ValueError('fresh explicit Codex-only allocation AND invocation-local trust approval required; no models launched')
    if os.name != 'posix' or os.getpgrp() != os.getpid():
        raise ValueError('invoke through the exact prepared lifecycle run command')
    deadline = time.monotonic() + 330
    def expired(*_):
        os.killpg(os.getpgrp(), signal.SIGKILL)
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 330)
    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise ValueError('aggregate campaign wall budget exhausted')
        return seconds
    if (NAMESPACE / 'codex-results.json').exists() or (NAMESPACE / 'codex-started').exists():
        raise ValueError('prior attempt exists; never overwrite or retry')
    report = json.loads((NAMESPACE / 'preparation.json').read_text())
    if report['limits'] != {'attempts': 1, 'per_attempt_seconds': 300, 'agent_seconds': 300, 'wall_seconds': 330}:
        raise ValueError('proposal allocation is outside the Codex-only bounds')
    for name, expected in report['files'].items():
        check_pin(ROOT / name, expected)
        check_pin(Path(report['frozen_source']) / name, expected)
    for name, expected in report['operator_inputs'].items():
        check_pin(Path(name), expected)
    if set(report['binaries']) != {'codex'}:
        raise ValueError('only Codex may be launched')
    binary = report['binaries']['codex']
    check_pin(Path(binary['path']), binary)
    env = dict(os.environ)
    for key in list(env):
        if (key in {'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL',
                    'OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_API_BASE'} or
                key.startswith(('CLAUDE_CODE_USE_', 'AZURE_OPENAI_', 'OPENROUTER_'))):
            env.pop(key, None)
    auth = subprocess.run([binary['path'], 'login', 'status'], cwd=report['frozen_source'], env=env,
        capture_output=True, text=True, check=True, timeout=min(15, remaining()))
    if 'Logged in using ChatGPT' not in auth.stdout + auth.stderr:
        raise ValueError('first-party ChatGPT subscription authentication required; no models launched')
    env['MECHANICAL_NATIVE_ALLOCATION'] = 'two-control-cells-and-local-trust'
    env['MECHANICAL_NATIVE_PREPARED_BRANCH'] = 'codex/named-greeting'
    commands = json.loads((NAMESPACE / 'planned-commands.json').read_text())
    if set(commands) != {'codex'}:
        raise ValueError('prepared commands are outside the Codex-only scope')
    with (NAMESPACE / 'codex-started').open('x') as marker:
        marker.write('One authorized Codex-only attempt reserved; no retries.\n')
        marker.flush()
        os.fsync(marker.fileno())
    command = list(commands['codex'])
    available = int(remaining()) - 5
    if available <= 0:
        raise ValueError('insufficient aggregate budget')
    for option in ('--max-wall-seconds', '--timeout', '--max-agent-seconds'):
        index = command.index(option) + 1
        command[index] = str(min(int(command[index]), available))
    code = subprocess.run(command, cwd=report['frozen_source'], env=env, timeout=remaining()).returncode
    check_selected_campaign(NAMESPACE / 'codex-results.json')
    check = subprocess.run([sys.executable, str(Path(report['frozen_source']) / '.ai/scripts/lifecycle_eval.py'),
        'results-check', str(NAMESPACE / 'codex-results.json'), '--require-real'],
        cwd=report['frozen_source'], env=env, timeout=remaining())
    return code if code > 0 else (1 if code < 0 else check.returncode)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('native allocation refused: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
