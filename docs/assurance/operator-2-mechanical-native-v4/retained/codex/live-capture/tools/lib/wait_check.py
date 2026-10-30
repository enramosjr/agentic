#!/usr/bin/env python3
"""Start a long check detached and block on it without model polling.

`start` runs COMMAND in its own process group, writing merged output to LOG,
the supervisor PID to LOG.pid and the exit status to LOG.exit. `wait` blocks
until the check exits, a --fail pattern appears, a --done pattern appears or
--max seconds pass, then prints one status record and the log tail. A timeout
never stops the check; rerun the same `wait` to keep blocking.

Exit status of `wait`: the check's own exit code once it has finished, 0 for a
--done match, 4 for a --fail match while still running, 124 when --max passes
and 125 when the check stopped without recording an exit status.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True

FAIL_MATCH = 4
TIMED_OUT = 124
LOST = 125


def _exit_path(log: Path) -> Path:
    return log.with_name(log.name + ".exit")


def _pid_path(log: Path) -> Path:
    return log.with_name(log.name + ".pid")


class LogInUse(RuntimeError):
    """Another check still owns this log."""


def start(log: Path, command: list[str]) -> int:
    if _pid_path(log).exists() and _recorded_exit(log) is None:
        owner = int(_pid_path(log).read_text().strip())
        if _alive(owner):
            raise LogInUse(f"check {owner} still owns {log}; wait for it or use another --log")
    for stale in (_exit_path(log), _pid_path(log)):
        stale.unlink(missing_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_bytes(b"")
    supervisor = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_supervise", str(log), "--", *command],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  start_new_session=True)
    _pid_path(log).write_text(f"{supervisor.pid}\n")
    return supervisor.pid


def supervise(log: Path, command: list[str]) -> int:
    with log.open("ab") as output:
        try:
            code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
        except OSError as error:
            output.write(f"wait_check: cannot start command: {error.strerror}\n".encode())
            code = 127
    code = code if code >= 0 else 128 - code
    pending = log.with_name(log.name + ".exit.tmp")
    pending.write_text(f"{code}\n")
    os.replace(pending, _exit_path(log))
    return code


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return True
    return state != "Z"


def _recorded_exit(log: Path) -> int | None:
    try:
        return int(_exit_path(log).read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def _tail(log: Path, lines: int) -> str:
    if lines <= 0 or not log.exists():
        return ""
    with log.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - 64 * 1024))
        text = handle.read().decode("utf-8", "backslashreplace")
    return "\n".join(text.splitlines()[-lines:])


def wait(log: Path, *, pid: int | None, fail: list[re.Pattern[str]], done: list[re.Pattern[str]],
         max_seconds: float, interval: float = 1.0) -> tuple[int, dict]:
    if pid is None and _pid_path(log).exists():
        pid = int(_pid_path(log).read_text().strip())
    started = time.monotonic()
    offset, partial = 0, ""

    def scan() -> tuple[str, str] | None:
        nonlocal offset, partial
        if not log.exists():
            return None
        with log.open("rb") as handle:
            handle.seek(offset)
            chunk = handle.read()
        offset += len(chunk)
        lines = (partial + chunk.decode("utf-8", "backslashreplace")).split("\n")
        partial = lines.pop()
        for line in lines:
            for pattern in fail:
                if pattern.search(line):
                    return "fail-match", line
            for pattern in done:
                if pattern.search(line):
                    return "done-match", line
        return None

    while True:
        code = _recorded_exit(log)
        elapsed = round(time.monotonic() - started, 1)
        if code is not None:
            return code, {"state": "finished", "exit_code": code, "waited_seconds": elapsed}
        hit = scan()
        if hit and hit[0] == "fail-match":
            return FAIL_MATCH, {"state": "fail-match", "line": hit[1], "waited_seconds": elapsed}
        if hit:
            return 0, {"state": "done-match", "line": hit[1], "waited_seconds": elapsed}
        if pid is not None and not _alive(pid):
            code = _recorded_exit(log)
            if code is not None:
                return code, {"state": "finished", "exit_code": code, "waited_seconds": elapsed}
            return LOST, {"state": "lost", "pid": pid, "waited_seconds": elapsed}
        if pid is None and not log.exists():
            return LOST, {"state": "lost", "reason": "no log, pid or exit record", "waited_seconds": elapsed}
        if elapsed >= max_seconds:
            return TIMED_OUT, {"state": "running", "waited_seconds": elapsed}
        time.sleep(min(interval, max(0.05, max_seconds - elapsed)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("start", help="run COMMAND detached; print its supervisor PID")
    p.add_argument("--log", required=True, type=Path)
    p.add_argument("command", nargs=argparse.REMAINDER)
    p = sub.add_parser("wait", help="block until the check finishes, matches, or --max passes")
    p.add_argument("--log", required=True, type=Path)
    p.add_argument("--pid", type=int, help="process to watch when the check was not started by `start`")
    p.add_argument("--fail", action="append", default=[], metavar="REGEX", help="stop waiting when a log line matches (repeatable)")
    p.add_argument("--done", action="append", default=[], metavar="REGEX", help="return 0 when a log line matches (repeatable)")
    p.add_argument("--max", type=float, default=540, metavar="SECONDS", help="longest block; set to the harness tool limit (default 540)")
    p.add_argument("--tail", type=int, default=15, metavar="N", help="log lines to print when it returns (default 15)")
    p = sub.add_parser("_supervise")
    p.add_argument("log", type=Path)
    p.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    if args.action in ("start", "_supervise"):
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not command:
            parser.error("provide a command after --")
        if args.action == "_supervise":
            return supervise(args.log, command)
        try:
            pid = start(args.log, command)
        except LogInUse as error:
            print(f"wait_check: {error}", file=sys.stderr)
            return 1
        print(json.dumps({"pid": pid, "log": str(args.log), "exit_file": str(_exit_path(args.log))}))
        return 0

    try:
        fail = [re.compile(rx) for rx in args.fail]
        done = [re.compile(rx) for rx in args.done]
    except re.error as error:
        parser.error(f"invalid pattern: {error}")
    code, record = wait(args.log, pid=args.pid, fail=fail, done=done, max_seconds=args.max)
    tail = _tail(args.log, args.tail if record["state"] != "running" else min(args.tail, 3))
    if tail:
        print(tail)
    print("wait: " + json.dumps(record, sort_keys=True), file=sys.stderr, flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
