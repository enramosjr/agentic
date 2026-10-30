"""Model-free process-visibility diagnostic using the installed sandbox helper."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ai/scripts'))
import review_guard as guard
import scratch


def main():
    if sys.argv[1:2] == ['--inside']:
        process = {'pid': int(sys.argv[2]), 'birth': sys.argv[3]}
        print(json.dumps({'registered': process, 'stopped': guard.stopped(process),
                          'current': guard.identity(process['pid']),
                          'pid_namespace': os.readlink('/proc/self/ns/pid')}))
        return
    proof = ROOT / 'docs/assurance/native-session-2-v7-visibility.json'
    if proof.exists():
        raise ValueError('preserve existing diagnostic evidence')
    environment = scratch.environment(ROOT)
    with tempfile.TemporaryDirectory(prefix='session-visibility-', dir=scratch.directory(ROOT)) as temporary:
        runtime = Path(temporary) / 'runtime'
        runtime.mkdir(mode=0o700)
        environment['XDG_RUNTIME_DIR'] = str(runtime)
        with subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], env=environment) as child:
            try:
                process = guard.identity(child.pid)
                command = ['codex', 'sandbox', '-c', 'sandbox_mode="workspace-write"',
                           '-c', 'approval_policy="never"', '--', sys.executable,
                           str(Path(__file__).resolve()), '--inside', str(child.pid), process['birth']]
                result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                                        text=True, timeout=20)
                value = {'command': command, 'host': process, 'host_stopped_after': guard.stopped(process),
                         'host_pid_namespace': os.readlink('/proc/self/ns/pid'),
                         'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr,
                         'model_calls': 0}
                with proof.open('x') as stream:
                    json.dump(value, stream, indent=2)
                    stream.write('\n')
                print(json.dumps(value))
            finally:
                child.terminate()
                child.wait(timeout=5)


if __name__ == '__main__':
    main()
