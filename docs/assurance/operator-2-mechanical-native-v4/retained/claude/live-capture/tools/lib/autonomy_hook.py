#!/usr/bin/env python3
"""Agent-harness hook for autonomous execution. Reads the hook event as JSON on stdin.

SessionStart (startup, resume, clear, compact): injects ``okf.py handoff`` as additional
context, so every fresh, resumed, or compacted session starts from the repository checkpoint.

Stop (opt-in with ``OKF_AUTONOMOUS=1``, which ``autonomy_driver.py`` sets): blocks ending the
session only while the checkpoint is unsafe, so every session ends resumable. Remaining work
does not keep a session alive: a fresh session (the driver's next one) continues it with an
empty context. It allows the stop when background work is pending or after
``OKF_AUTONOMOUS_MAX_CONTINUES`` blocks in one session.

Does nothing when the bundle has no work queue. Standard library only; Python 3.9+.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # A __pycache__ beside okf.py would make the work tree, and so the checkpoint, unclean.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import okf  # noqa: E402
import scratch  # noqa: E402

DEFAULT_MAX_CONTINUES = 3  # Each block is a full turn; an agent that cannot fix it in 3 will not in 10.


def _bundle() -> Path:
    return okf.find_bundle(None)


def session_start(bundle: Path) -> dict[str, object] | None:
    if not (bundle / okf.QUEUE_DOC).is_file():
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": okf.handoff(bundle),
        }
    }


def _continue_count(session_id: str, bundle: Path) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")
    return scratch.directory(bundle.parent) / f"okf-autonomy-{safe}.count"


def stop(bundle: Path, event: dict[str, object]) -> dict[str, object] | None:
    if os.environ.get("OKF_AUTONOMOUS") != "1" or not (bundle / okf.QUEUE_DOC).is_file():
        return None
    if event.get("background_tasks") or event.get("session_crons"):
        return None  # The session is paused waiting for work that will wake it.
    unsafe = [c for c in okf.checkpoint(bundle) if not c.ok]
    if not unsafe:
        return None

    counter = _continue_count(str(event.get("session_id", "")), bundle)
    try:
        count = int(counter.read_text()) if counter.is_file() else 0
    except ValueError:
        count = 0
    limit = int(os.environ.get("OKF_AUTONOMOUS_MAX_CONTINUES", DEFAULT_MAX_CONTINUES))
    if count >= limit:
        return None
    counter.write_text(str(count + 1))

    return {
        "decision": "block",
        "reason": (
            f"Autonomous mode (OKF_AUTONOMOUS=1, block {count + 1}/{limit}): unsafe checkpoint: "
            + "; ".join(f"{c.name}: {c.detail}" for c in unsafe)
            + ". Finish the current atomic step, commit it (prefix `wip:` if incomplete), update the "
            "status checkpoint, and rerun `okf.py checkpoint` until it prints SAFE. Then end the "
            "session; do not start new work, because a fresh session continues from the checkpoint."
        ),
    }


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    name = event.get("hook_event_name")
    try:
        if name == "SessionStart":
            output = session_start(_bundle())
        elif name == "Stop":
            output = stop(_bundle(), event)
        else:
            output = None
    except okf.OkfError as error:
        print(f"autonomy hook: {error}", file=sys.stderr)
        return 1  # Non-blocking error: the session continues without the hook.
    if output is not None:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
