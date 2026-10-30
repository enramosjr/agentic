"""Guarded two-attempt proposal. Do not invoke without fresh allocation/trust approval."""
import hashlib
import json
import os
import signal
from pathlib import Path
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
NAMESPACE = ROOT / 'docs/assurance/operator-2-mechanical-native-v5'


def check_pin(path, expected):
    if (hashlib.sha256(path.read_bytes()).hexdigest() != expected['sha256'] or
            oct(stat.S_IMODE(path.stat().st_mode)) != expected['mode']):
        raise ValueError('prepared bytes/mode changed: ' + str(path))


def check_selected_campaign(path, agent):
    """A settled one-cell selection is distinct from the evaluator's full baseline."""
    result = json.loads(path.read_text())
    matrix = result.get('matrix', [])
    attempts = result.get('attempts', [])
    if (len(matrix) != 1 or matrix[0].get('scenario_id') != 'control-delta'
            or matrix[0].get('repeat_index') != 1 or matrix[0].get('outcome') != 'completed'
            or len(attempts) != 1 or attempts[0].get('scenario_id') != 'control-delta'
            or attempts[0].get('repeat_index') != 1 or attempts[0].get('outcome') != 'completed'
            or attempts[0].get('status') not in ('PASS', 'FAIL', 'ERROR')
            or not result.get('totals', {}).get('complete')
            or result.get('budget', {}).get('reserved_seconds') != 0
            or result.get('provenance', {}).get('agent', {}).get('id') != agent):
        raise ValueError('selected campaign is incomplete or outside the approved one-cell scope')


def main():
    if sys.argv[1:] != ['--authorized-allocation-and-scoped-trust']:
        raise ValueError('fresh explicit two-attempt allocation AND invocation-local trust approval required; no models launched')
    # The exact lifecycle.run command gives this wrapper its own supervised group.
    if os.name != 'posix' or os.getpgrp() != os.getpid():
        raise ValueError('invoke through the exact prepared lifecycle run command')
    deadline = time.monotonic() + 660
    def expired(*_):
        os.killpg(os.getpgrp(), signal.SIGKILL)
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 660)
    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise ValueError('aggregate campaign wall budget exhausted')
        return seconds
    report = json.loads((NAMESPACE / 'preparation.json').read_text())
    for agent in ('claude', 'codex'):
        if (NAMESPACE / (agent + '-results.json')).exists() or (NAMESPACE / (agent + '-started')).exists():
            raise ValueError('prior attempt exists; never overwrite or retry')
    for name, expected in report['files'].items():
        check_pin(ROOT / name, expected)
        check_pin(Path(report['frozen_source']) / name, expected)
    for name, expected in report['operator_inputs'].items():
        check_pin(Path(name), expected)
    for expected in report['binaries'].values():
        check_pin(Path(expected['path']), expected)
    env = dict(os.environ)
    for key in list(env):
        if (key in {'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL',
                    'OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_API_BASE'} or
                key.startswith(('CLAUDE_CODE_USE_', 'AZURE_OPENAI_', 'OPENROUTER_'))):
            env.pop(key, None)
    claude = report['binaries']['claude']['path']
    auth = subprocess.run([claude, 'auth', 'status'], cwd=report['frozen_source'], env=env,
                          capture_output=True, text=True, check=True, timeout=min(15, remaining()))
    value = json.loads(auth.stdout)
    if not (value.get('loggedIn') and value.get('authMethod') == 'claude.ai'
            and value.get('apiProvider') == 'firstParty' and value.get('subscriptionType') == 'pro'):
        raise ValueError('Claude Pro first-party subscription required; no models launched')
    env['MECHANICAL_NATIVE_ALLOCATION'] = 'two-control-cells-and-local-trust'
    commands = json.loads((NAMESPACE / 'planned-commands.json').read_text())
    exit_code = 0
    for agent in ('claude', 'codex'):
        with (NAMESPACE / (agent + '-started')).open('x') as marker:
            marker.write('One authorized attempt reserved; no retries.\n')
            marker.flush()
            os.fsync(marker.fileno())
        command = list(commands[agent])
        # Budget may only shrink. Reserve time for integrity checking, and place
        # each evaluator/agent absolute deadline inside the same aggregate envelope.
        available = int(remaining()) - 5
        if available <= 0:
            raise ValueError('insufficient aggregate budget for another attempt')
        wall = command.index('--max-wall-seconds') + 1
        command[wall] = str(min(int(command[wall]), available))
        attempt = command.index('--timeout') + 1
        command[attempt] = str(min(int(command[attempt]), available))
        agent_budget = command.index('--max-agent-seconds') + 1
        command[agent_budget] = str(min(int(command[agent_budget]), available))
        code = subprocess.run(command, cwd=report['frozen_source'], env=env, timeout=remaining()).returncode
        if code:
            exit_code = exit_code or (code if code > 0 else 1)
        check_selected_campaign(NAMESPACE / (agent + '-results.json'), agent)
        check = subprocess.run([sys.executable, str(Path(report['frozen_source']) / '.ai/scripts/lifecycle_eval.py'),
            'results-check', str(NAMESPACE / (agent + '-results.json')), '--require-real'],
            cwd=report['frozen_source'], env=env, timeout=remaining())
        if check.returncode:
            exit_code = exit_code or (check.returncode if check.returncode > 0 else 1)
    return exit_code


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('native allocation refused: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
