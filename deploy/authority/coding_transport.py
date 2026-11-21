"""Outer task transport watchdog; protocol completion is not an attestation."""
import hashlib
import json
import subprocess
import threading
import time

import authority_release
import codex_harness
import submission
from trusted_ci_policy import Refusal, loads, require

ENGINE_ENVIRONMENT = dict(PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                          HOME='/nonexistent', DOCKER_CONFIG='/nonexistent')


def capture_export(argv, guard, abort, seconds=30):
    """Read a fixed exporter through bounded binary pipes; always remove its ID."""
    require(type(seconds) in (int, float) and 0 < seconds <= 30, 'bounded export deadline required')
    failed, expired = threading.Event(), threading.Event()
    lock, aborted, abort_failed = threading.Lock(), [False], [False]
    process, readers, output = None, [], []

    def remove():
        with lock:
            if not aborted[0]:
                try: abort()
                except Exception: abort_failed[0] = True
                finally: aborted[0] = True

    def timeout():
        expired.set()
        remove()

    def read(stream, limit, retain):
        count = 0
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk: return
                count += len(chunk)
                require(count <= limit, 'export transport output limit exceeded')
                if retain: output.append(chunk)
        except Exception:
            failed.set()

    timer = threading.Timer(seconds, timeout)
    timer.daemon = True
    timer.start()
    result = None
    try:
        guard()
        require(not expired.is_set(), 'export admission expired')
        process = subprocess.Popen(argv, env=ENGINE_ENVIRONMENT, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, close_fds=True, bufsize=0)
        readers = [threading.Thread(target=read, args=(process.stdout, submission.MAX_BYTES, True), daemon=True),
                   threading.Thread(target=read, args=(process.stderr, 1024 * 1024, False), daemon=True)]
        for reader in readers: reader.start()
        while True:
            require(not expired.is_set() and not failed.is_set(), 'export transport expired or refused')
            guard()
            require(not expired.is_set(), 'export authorization observation expired')
            if process.poll() is not None and not any(reader.is_alive() for reader in readers):
                require(process.returncode == 0 and not failed.is_set(), 'exporter did not complete')
                result = b''.join(output)
                submission.read_export(result)
                break
            expired.wait(.05)
    finally:
        timer.cancel()
        try:
            remove()
        finally:
            if process is not None:
                if process.poll() is None: process.kill()
                process.wait(timeout=5)
                for reader in readers: reader.join(timeout=5)
                for stream in (process.stdout, process.stderr): stream.close()
            timer.join(timeout=35)
            require(not timer.is_alive() and not any(reader.is_alive() for reader in readers) and not abort_failed[0],
                    'owned exporter cleanup not confirmed')
    require(result is not None and not expired.is_set(), 'export did not finish within its deadline')
    guard()
    return result


def conversation(box, deployment, source, capability, prompt, expires, guard, cancelled=lambda: False):
    authority_release.authorize('protected-run')
    return _conversation(box, deployment, source, capability, prompt, expires, guard, cancelled)


def _conversation(box, deployment, source, capability, prompt, expires, guard,
                  cancelled=lambda: False, budget=None):
    codex_harness.profile(deployment)
    codex_harness.environment(capability)
    submission.read_export(source)
    require(type(expires) is int and time.time() < expires <= time.time() + 900,
            'current bounded task deadline required')
    duration = min(deployment['policy']['limits']['seconds'], expires - time.time())
    if budget is not None:
        require(type(budget) in (int, float) and 0 < budget <= duration, 'bounded transport budget required')
        duration = budget
    require(type(expires) is int and 0 < duration <= 900, 'current bounded task deadline required')
    end = time.monotonic() + duration
    header = dict(schema_version=2, deployment=deployment, capability=capability, expires=expires,
                  source_bytes=len(source), source_sha256=hashlib.sha256(source).hexdigest())
    process, threads, results, errors = None, [], [], []
    done, failed = threading.Event(), threading.Event()
    finished, stop_done, stop_failed = threading.Event(), False, False
    stop_lock = threading.Lock()

    def stop_once():
        nonlocal stop_done, stop_failed
        with stop_lock:
            if not stop_done:
                try: box.stop()
                except Exception: stop_failed = True
                finally: stop_done = True
            require(not stop_failed, 'owned task termination could not be confirmed')

    def watchdog():
        try:
            while not finished.wait(.05):
                # cancelled is a local event predicate; remote observations belong
                # in guard and cannot prevent this independent container stop.
                if time.monotonic() >= end or cancelled():
                    failed.set()
                    stop_once()
                    return
        except Exception:
            failed.set()
            try: stop_once()
            except Exception: pass

    def protocol():
        try:
            # Raw pipe writes can be short for a large source transfer.
            for raw in ((json.dumps(header, allow_nan=False) + '\n').encode(), source):
                offset = 0
                while offset < len(raw):
                    written = process.stdin.write(raw[offset:offset + 65536])
                    require(written is not None and written > 0, 'worker source transfer failed')
                    offset += written
            process.stdin.flush()
            raw = process.stdout.readline(1025)
            require(raw.endswith(b'\n') and len(raw) <= 1024 and
                    loads(raw) == dict(kind='worker-ready', source_sha256=header['source_sha256']),
                    'worker did not accept the exact source')
            results.append(codex_harness.conversation(process.stdout, process.stdin, deployment, prompt))
            process.stdin.close()
        except Exception:
            errors.append('task protocol refused')
            failed.set()
        finally:
            done.set()

    def diagnostics():
        count = 0
        try:
            while True:
                chunk = process.stderr.read(65536)
                if not chunk: return
                count += len(chunk)
                require(count <= codex_harness.MAX_STREAM, 'task diagnostic limit exceeded')
        except Exception:
            errors.append('task diagnostics refused')
            failed.set()

    succeeded = False
    watcher = threading.Thread(target=watchdog, daemon=True)
    watcher.start()
    try:
        guard()
        require(time.monotonic() < end and not failed.is_set(), 'task attachment admission expired')
        process = box._attach()
        threads = [threading.Thread(target=protocol, daemon=True), threading.Thread(target=diagnostics, daemon=True)]
        for thread in threads: thread.start()
        while True:
            require(time.monotonic() < end and not cancelled() and not failed.is_set(),
                    'task transport expired, cancelled or refused')
            guard()
            require(time.monotonic() < end and not cancelled(), 'task authorization observation expired')
            if done.is_set():
                require(len(results) == 1 and not errors, 'task protocol did not complete')
                code = process.poll()
                if code is not None:
                    require(code == 0, 'worker transport failed')
                    succeeded = True
                    break
            failed.wait(min(.1, max(.001, end - time.monotonic())))
    finally:
        # Stop the entire candidate first; killing the attached CLI alone cannot
        # terminate worker descendants that created their own process sessions.
        finished.set()
        try:
            stop_once()
        finally:
            watcher.join(timeout=35)
            if process is not None:
                if process.poll() is None: process.kill()
                process.wait(timeout=5)
                for thread in threads: thread.join(timeout=5)
                require(not any(thread.is_alive() for thread in threads), 'task pipe cleanup not confirmed')
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None and not stream.closed: stream.close()
            require(not watcher.is_alive(), 'task watchdog cleanup not confirmed')
    require(succeeded and not errors, 'task transport did not finish cleanly')
    guard()
    return results[0]
