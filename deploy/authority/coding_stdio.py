"""Immutable worker-side bootstrap and bounded app-server transport.

The external parent owns OCI admission, the task watchdog and stopped-volume
export. A successful transport is deliberately not an isolation attestation.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time

sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parents[2] / '.ai/scripts')]
import authority_release
import codex_harness
from coding_worker import export_tree, materialize
from model_bridge import Bridge
import submission
from trusted_ci_policy import Refusal, loads, object_fields, require


def bootstrap(reader, clock=time.time):
    raw = reader.readline(65537)
    require(raw.endswith(b'\n') and len(raw) <= 65536, 'bounded worker bootstrap required')
    value = loads(raw)
    object_fields(value, ('schema_version', 'deployment', 'capability', 'expires',
                         'source_bytes', 'source_sha256'), 'worker bootstrap')
    codex_harness.profile(value['deployment'])
    codex_harness.environment(value['capability'])
    require(type(value['schema_version']) is int and value['schema_version'] == 2 and
            type(value['expires']) is int and clock() < value['expires'] <= clock() + 900 and
            type(value['source_bytes']) is int and 0 < value['source_bytes'] <= submission.MAX_BYTES,
            'current bounded worker source/deadline required')
    chunks, remaining = [], value['source_bytes']
    while remaining:
        chunk = reader.read(min(65536, remaining))
        require(chunk, 'incomplete worker source transfer')
        chunks.append(chunk)
        remaining -= len(chunk)
    source = b''.join(chunks)
    require(hashlib.sha256(source).hexdigest() == value['source_sha256'], 'worker source digest differs')
    submission.read_export(source)
    return value, source


def _proxy(child, reader, writer, end, bridge):
    """No blocking pipe read/write can hide a silent child from the deadline."""
    incoming, outgoing, errors = bytearray(), bytearray(), 0
    parent_eof, child_eof, sent, received = False, False, 0, 0
    streams = (reader.fileno(), writer.fileno(), child.stdin.fileno(), child.stdout.fileno(), child.stderr.fileno())
    for descriptor in streams: os.set_blocking(descriptor, False)
    try:
        while True:
            require(time.monotonic() < end and not bridge.stopped.is_set(), 'worker task ended')
            if parent_eof and not incoming and not child.stdin.closed:
                child.stdin.close()
            if child_eof and not outgoing:
                require(child.wait(timeout=max(.1, min(5, end - time.monotonic()))) == 0,
                        'app-server process failed')
                return
            with selectors.DefaultSelector() as selector:
                if not parent_eof and len(incoming) < 1024 * 1024:
                    selector.register(reader.fileno(), selectors.EVENT_READ, 'parent')
                if incoming and not child.stdin.closed:
                    selector.register(child.stdin.fileno(), selectors.EVENT_WRITE, 'input')
                if not child_eof and len(outgoing) < 1024 * 1024:
                    selector.register(child.stdout.fileno(), selectors.EVENT_READ, 'child')
                if not child.stderr.closed:
                    selector.register(child.stderr.fileno(), selectors.EVENT_READ, 'error')
                if outgoing: selector.register(writer.fileno(), selectors.EVENT_WRITE, 'output')
                for key, _ in selector.select(min(.2, max(.01, end - time.monotonic()))):
                    if key.data in ('parent', 'child', 'error'):
                        chunk = os.read(key.fd, 65536)
                        if key.data == 'parent':
                            parent_eof = not chunk
                            incoming.extend(chunk)
                            sent += len(chunk)
                        elif key.data == 'child':
                            child_eof = not chunk
                            outgoing.extend(chunk)
                            received += len(chunk)
                        else:
                            errors += len(chunk)
                            if not chunk: child.stderr.close()
                    elif key.data == 'input': del incoming[:os.write(key.fd, incoming)]
                    else: del outgoing[:os.write(key.fd, outgoing)]
                    require(max(sent, received, errors) <= codex_harness.MAX_STREAM,
                            'worker app-server stream limit exceeded')
    finally:
        for descriptor in streams:
            try: os.set_blocking(descriptor, True)
            except OSError: pass


def _stdio(reader, writer, workspace=Path('/work/project'), executable=Path('/opt/agentic/bin/codex'),
           socket_path=Path('/run/agentic-model/relay.sock'), home=Path('/home/agentic')):
    require(os.name == 'posix', 'POSIX managed worker required')
    # Covers even a parent that sends no header or stalls midway through the TAR.
    def expired(signum, frame): raise TimeoutError('worker bootstrap deadline')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.alarm(30)
    child = bridge = None
    try:
        value, source = bootstrap(reader)
        end = time.monotonic() + value['expires'] - time.time()
        signal.alarm(max(1, int(end - time.monotonic()) + 1))
        require(executable.is_file() and not executable.is_symlink() and executable.stat().st_size <= 256 * 1024 * 1024,
                'plain pinned app-server executable required')
        fingerprint = hashlib.sha256()
        with executable.open('rb') as binary:
            for chunk in iter(lambda: binary.read(1024 * 1024), b''): fingerprint.update(chunk)
        require(fingerprint.hexdigest() == value['deployment']['resources']['codex_sha'], 'app-server binary pin differs')
        environment = codex_harness.environment(value['capability'])
        require(home.is_dir() and not home.is_symlink() and not list(home.iterdir()), 'fresh private worker home required')
        environment.update(HOME=str(home), CODEX_HOME=str(home / '.codex'))
        version = subprocess.run([str(executable), '--version'], env=environment, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=False)
        require(version.returncode == 0 and version.stdout.strip() ==
                ('codex-cli ' + value['deployment']['resources']['codex_version']).encode(), 'app-server version pin differs')
        materialize(source, workspace)
        bridge = Bridge(socket_path, value['expires'])
        port = bridge._start(0)
        argv = codex_harness.command(value['deployment'], port)
        argv[0] = str(executable)
        child = subprocess.Popen(argv, cwd=workspace, env=environment, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, bufsize=0)
        writer.write((json.dumps(dict(kind='worker-ready', source_sha256=value['source_sha256'])) + '\n').encode())
        writer.flush()
        _proxy(child, reader, writer, end, bridge)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
        if child is not None:
            # The parent still stops the whole container: descendants can create
            # new sessions, so killing this process group alone proves nothing.
            try: os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            child.wait(timeout=5)
            for stream in (child.stdin, child.stdout, child.stderr): stream.close()
        if bridge is not None: bridge.close()


def main():
    authority_release.authorize('protected-run')
    require(sys.argv[1:] in (['--stdio'], ['--export']), 'fixed worker mode required')
    if sys.argv[1] == '--stdio': _stdio(sys.stdin.buffer, sys.stdout.buffer)
    else: sys.stdout.buffer.write(export_tree(Path('/work/project')))


if __name__ == '__main__':
    try: main()
    except (Refusal, OSError, ValueError):
        print('managed worker refused; no execution or qualification claimed', file=sys.stderr)
        sys.exit(1)
