#!/usr/bin/env python3
"""Public progress events and parent-chat acknowledgements; never publishes tool payloads."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
import time
import uuid

sys.dont_write_bytecode = True


class MonitorLost(RuntimeError):
    pass


class Progress:
    def __init__(self, path: Path, ack: Path | None, timeout: float):
        self.path, self.ack, self.timeout = path, ack, timeout
        self.run_id, self.sequence = str(uuid.uuid4()), 0
        self.lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.output = path.open("x", encoding="utf-8")
        self.emit("started", "Driver started; waiting for the chat supervisor acknowledgement." if ack
                  else "Driver started in explicitly selected headless mode.")

    def emit(self, kind: str, text: str):
        with self.lock:
            self.sequence += 1
            event = {"run_id": self.run_id, "sequence": self.sequence,
                     "at": datetime.now(timezone.utc).isoformat(), "kind": kind, "text": text[:2000]}
            self.output.write(json.dumps(event, ensure_ascii=False) + "\n")
            self.output.flush()

    def check(self):
        if self.ack is None:
            return
        try:
            value = json.loads(self.ack.read_text())
            age = time.monotonic() - value["acknowledged_at"]
            valid = (value["run_id"] == self.run_id and 0 <= age <= self.timeout
                     and type(value["sequence"]) is int and 1 <= value["sequence"] <= self.sequence)
        except (OSError, ValueError, KeyError, TypeError):
            valid = False
        if not valid:
            raise MonitorLost("chat supervisor acknowledgement missing or expired")

    def wait_for_chat(self):
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.check()
                return
            except MonitorLost:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))

    def observe(self, line: str):
        try:
            value = json.loads(line)
        except ValueError:
            return
        if not isinstance(value, dict):
            return
        kind = value.get("type")
        if kind == "assistant":
            # Cursor and Claude Code stream-json: only text blocks are public; tool_use/thinking are not.
            message = value.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                text = "\n".join(block["text"] for block in content if isinstance(block, dict)
                                 and block.get("type") == "text" and isinstance(block.get("text"), str))
                if text.strip():
                    self.emit("update", text)
            return
        item = value.get("item", {})
        if not isinstance(item, dict):
            return
        if (kind == "item.completed" and item.get("type") == "agent_message"
                and isinstance(item.get("text"), str)):
            self.emit("update", item["text"])
        elif kind in ("error", "turn.failed") or (kind == "result" and value.get("is_error") is True):
            self.emit("failure", "Agent reported a failure; inspect the private run log for details.")


def read_events(path: Path, after: int = 0) -> list[dict]:
    events = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.endswith("\n"):
                continue
            event = json.loads(line)
            if event["sequence"] > after:
                events.append(event)
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("read", "ack"))
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--after", type=int, default=0)
    parser.add_argument("--ack-file", type=Path,
                        help="with read --after N: first acknowledge event N (already relayed in chat), so one call per relay")
    args = parser.parse_args()

    def acknowledge(event: dict) -> None:
        value = {"run_id": event["run_id"], "sequence": event["sequence"], "acknowledged_at": time.monotonic()}
        temporary = args.ack_file.with_suffix(args.ack_file.suffix + ".tmp")
        temporary.write_text(json.dumps(value), encoding="utf-8")
        temporary.replace(args.ack_file)

    try:
        if args.action == "ack":
            events = read_events(args.file, args.after)
            if args.ack_file is None or not events:
                parser.error("ack needs --ack-file and at least one progress event")
            acknowledge(events[-1])
            print(json.dumps({"acknowledged_sequence": events[-1]["sequence"]}))
            return 0
        result: dict = {}
        if args.ack_file is not None and args.after > 0:
            # Acknowledge only what the previous read returned and chat has shown, never the new events.
            relayed = [event for event in read_events(args.file, args.after - 1) if event["sequence"] == args.after]
            if not relayed:
                raise ValueError(f"no event {args.after} to acknowledge")
            acknowledge(relayed[0])
            result["acknowledged_sequence"] = args.after
        events = read_events(args.file, args.after)
        result.update(events=events, next_sequence=events[-1]["sequence"] if events else args.after)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"progress: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
