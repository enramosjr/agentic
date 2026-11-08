"""Observe actual driver output; no clock injection or production budget change."""
import contextlib
import subprocess
import threading
import time

import process_runtime


@contextlib.contextmanager
def observe(command, environment, startup_seconds, run_seconds):
    tree = process_runtime.ProcessTree()
    output, errors, markers, failures = [], [], [], []
    changed = threading.Event()
    threads, child = [], None
    started = time.monotonic()

    def drain(stream, lines, stderr=False):
        total = 0
        try:
            for line in iter(lambda: stream.readline(65537), ''):
                total += len(line)
                if len(line) > 65536 or total > 4 * 1024 * 1024:
                    failures.append('bounded CLI diagnostics exceeded')
                    break
                lines.append(line)
                if stderr and line.startswith('driver: Disk-backed scratch:'):
                    markers.append(time.monotonic())
                    if len(markers) != 1: failures.append('duplicate run-start marker')
                changed.set()
        except (OSError, ValueError):
            failures.append('CLI diagnostic capture failed')
        finally: changed.set()

    try:
        child = tree.start(command, env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
        for stream, lines, stderr in ((child.stdout, output, False), (child.stderr, errors, True)):
            thread = threading.Thread(target=drain, args=(stream, lines, stderr), daemon=True)
            thread.start()
            threads.append(thread)
        while child.poll() is None:
            if failures: raise AssertionError(failures[0])
            if markers:
                if time.monotonic() - markers[0] >= run_seconds:
                    raise AssertionError('run deadline observer exceeded; ' + ''.join(errors))
            elif time.monotonic() - started >= startup_seconds:
                raise AssertionError('startup watchdog exceeded before run-start marker')
            changed.wait(.02)
            changed.clear()
        # Do not close the owned tree before the caller checks descendants: that
        # would conceal a leak by killing it on behalf of the driver under test.
        for thread in threads: thread.join(timeout=2)
        if any(thread.is_alive() for thread in threads): raise AssertionError('CLI diagnostic pipes remain open after exit')
        if failures: raise AssertionError(failures[0])
        if len(markers) != 1: raise AssertionError('exactly one run-start marker required; ' + ''.join(errors))
        if markers[0] - started >= startup_seconds: raise AssertionError('startup watchdog exceeded before run-start marker')
        elapsed = time.monotonic() - markers[0]
        if elapsed >= run_seconds: raise AssertionError('run deadline observer exceeded; ' + ''.join(errors))
        yield subprocess.CompletedProcess(command, child.returncode, ''.join(output), ''.join(errors)), elapsed
    finally:
        tree.close()
        if child is not None:
            child.wait(timeout=6)
            for thread in threads: thread.join(timeout=6)
            for stream in (child.stdout, child.stderr): stream.close()
        if any(thread.is_alive() for thread in threads): raise AssertionError('deadline observer capture did not terminate')
