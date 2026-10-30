#!/usr/bin/env python3
"""Run a check unchanged and emit one administrative timing record on stderr."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import threading
import time
from typing import Callable

sys.dont_write_bytecode = True


class CaptureError(RuntimeError):
    """Command output could not be retained completely."""


def run(command: list[str], *, label: str, cwd: Path | None = None,
        env: dict[str, str] | None = None, timeout_seconds: float | None = None,
        on_tick: Callable[[], None] | None = None, tick_seconds: float = 30,
        on_output: Callable[[str], None] | None = None,
        merge_stderr: bool = False) -> subprocess.CompletedProcess:
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    exit_code = 127
    child = None
    reader = None
    reader_errors = []
    try:
        child = subprocess.Popen(command, cwd=cwd, env=env,
                                 start_new_session=timeout_seconds is not None,
                                 stdout=subprocess.PIPE if on_output else None,
                                 stderr=subprocess.STDOUT if merge_stderr else None,
                                 text=True if on_output else None,
                                 encoding="utf-8" if on_output else None,
                                 errors="backslashreplace" if on_output else None)
        if on_output:
            def forward():
                try:
                    for line in child.stdout:
                        print(line, end="", flush=True)
                        on_output(line)
                except Exception as error:
                    reader_errors.append(error)
            reader = threading.Thread(target=forward, daemon=True)
            reader.start()
        deadline = time.monotonic() + timeout_seconds if timeout_seconds is not None else None
        while True:
            if reader_errors:
                raise CaptureError("command output capture failed") from reader_errors[0]
            remaining = None if deadline is None else max(0, deadline - time.monotonic())
            interval = remaining
            if on_tick:
                interval = tick_seconds if remaining is None else min(tick_seconds, remaining)
            try:
                result = subprocess.CompletedProcess(command, child.wait(timeout=interval))
                break
            except subprocess.TimeoutExpired:
                if deadline is not None and time.monotonic() >= deadline:
                    raise
                if on_tick:
                    on_tick()
        exit_code = result.returncode
        return result
    except subprocess.TimeoutExpired:
        exit_code = 124
        raise
    except KeyboardInterrupt:
        exit_code = 130
        raise
    except OSError:
        raise
    except BaseException:
        exit_code = 1
        raise
    finally:
        if child is not None and (timeout_seconds is not None or exit_code in (1, 124, 130)):
            if timeout_seconds is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif child.poll() is None:
                child.kill()
            child.wait()
        if reader is not None:
            reader.join(timeout=1)
            if child.stdout is not None and not reader.is_alive():
                child.stdout.close()
        capture_failed = reader is not None and (reader_errors or reader.is_alive()) and sys.exc_info()[0] is None
        if capture_failed:
            exit_code = 1
        print("timing: " + json.dumps({
            "label": label, "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "exit_code": exit_code, "outcome": "PASS" if exit_code == 0 else "FAIL",
        }, sort_keys=True), file=sys.stderr, flush=True)
        if capture_failed:
            raise CaptureError("command output capture failed; retained log may be incomplete")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="administrative check name; no private content")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide a command after --")
    try:
        import scratch
        try:
            environment = scratch.environment(Path.cwd())
        except subprocess.CalledProcessError:
            environment = scratch.environment(Path(__file__).resolve().parents[2])
        code = run(command, label=args.label, env=environment).returncode
        return code if code >= 0 else 128 - code
    except OSError as error:
        print(f"timed check: cannot start command: {error.strerror}", file=sys.stderr)
        return 127
    except KeyboardInterrupt:
        return 130
    except (ValueError, subprocess.CalledProcessError) as error:
        print(f"timed check: scratch setup failed: {error}", file=sys.stderr)
        return 127


if __name__ == "__main__":
    sys.exit(main())
