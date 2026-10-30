"""Real sandbox CLI workflow with a synthetic registration; no agent/model execution."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '.ai/scripts/tests'), str(ROOT / '.ai/scripts')]
import lifecycle
import review_guard as guard
import scratch
from test_review_enforcement import NativeCase


def main():
    proof = ROOT / 'docs/assurance/native-session-2-v7-workflow.json'
    if proof.exists():
        raise ValueError('preserve existing workflow evidence')
    case = NativeCase()
    case.setUp()
    outcomes = []
    try:
        case.prepare_native('codex', enable=False)
        environment = scratch.environment(case.root, case.env)
        with tempfile.TemporaryDirectory(prefix='sandbox-runtime-', dir=scratch.directory(case.root)) as temporary:
            runtime_dir = Path(temporary) / 'runtime'
            runtime_dir.mkdir(mode=0o700)
            environment['XDG_RUNTIME_DIR'] = str(runtime_dir)
            with subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], env=environment) as host:
                try:
                    runtime = guard.identity(host.pid)
                    case.native.handle(case.root, 'codex', {'hook_event_name': 'SessionStart',
                        'session_id': 'parent', 'cwd': str(case.root)}, runtime)
                    def invoke(arguments, expected):
                        flags = ['codex', 'sandbox', '-c', 'sandbox_mode="workspace-write"',
                                 '-c', 'approval_policy="never"', '-c', 'sandbox_workspace_write.writable_roots=' +
                                 json.dumps([str(scratch.directory(case.root))]), '--', sys.executable,
                                 str(case.scripts / 'lifecycle.py')]
                        result = subprocess.run([*flags, *arguments], cwd=case.root, env=environment,
                                                capture_output=True, text=True, timeout=25)
                        outcomes.append({'arguments': arguments, 'exit': result.returncode,
                                         'stdout': result.stdout, 'stderr': result.stderr})
                        if result.returncode != expected:
                            raise AssertionError(outcomes[-1])
                        return result
                    result = invoke(['review', 'status'], 0)
                    status = json.loads(result.stdout)
                    if status['observed_sessions'] != [{'adapter': 'codex', 'session': 'parent'}]:
                        raise AssertionError(status)
                    if status['runtime_liveness'] != 'not_assessed':
                        raise AssertionError(status)
                    report = 'knowledge/history/reviews/native.md'
                    invoke(['review', 'enable', '--adapter', 'codex', '--session', 'parent', '--report', report], 0)
                    invoke(['stage', 'review', '--ref', report], 1)
                    invoke(['stage', 'verify'], 1)
                    state, journal = lifecycle.load(case.root), guard.read(case.root)
                    if journal['interval'] is not None or any(name in state['stages'] for name in ('review', 'verify')):
                        raise AssertionError('registration-only request qualified')
                    if guard.stopped(runtime):
                        raise AssertionError('test host stopped before diagnostic completed')
                    value = {'passed': True, 'model_calls': 0, 'native_review_qualified': False,
                             'registration': 'synthetic callback with real host lifetime',
                             'host_runtime': runtime, 'host_alive_after': True,
                             'request_phase': journal['request']['phase'], 'outcomes': outcomes}
                    with proof.open('x') as stream:
                        json.dump(value, stream, indent=2)
                        stream.write('\n')
                    print('PASS: real sandbox discovers/opts in; registration cannot qualify Review/Verify; no model calls')
                finally:
                    host.terminate()
                    host.wait(timeout=5)
    finally:
        case.doCleanups()


if __name__ == '__main__':
    main()
