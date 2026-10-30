"""Pinned CLI observation, with no inferred model/effort or fabricated review.

The launch and hook modes run outside the evaluated checkout. The adapter only
reads their captured evidence. This is instrumentation, not a hostile-agent sandbox.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import time


LIMIT = 4 * 1024 * 1024
VERSIONS = {"codex": "0.162.1", "claude": "2.1.312"}
MODELS = {"codex": "gpt-6.1-sol", "claude": "claude-sonnet-5-5"}
EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop", "Stop")


def report_hash(text):
    if text.startswith("---\n") and "\n---" in text[4:]:
        text = text[text.find("\n---", 4) + 4:]
    return hashlib.sha256(text.strip().encode()).hexdigest()


def assemble(agent, events, native):
    starts = [event for event in events if event.get("event") == "SessionStart"]
    if not starts or not starts[0].get("session"):
        raise ValueError("no observed SessionStart: hook activation is unqualified")
    parent = starts[0]["session"]
    identity = native.get(parent, {})
    if not all(isinstance(identity.get(key), str) and identity[key]
               for key in ("model", "reasoningEffort", "cliVersion")):
        raise ValueError("native CLI omitted observed parent model/effort/version")
    if any((event.get("model") and event["model"] != identity["model"])
           or (event.get("effort") and event["effort"] != identity["reasoningEffort"]) for event in events):
        raise ValueError("active parent/reviewer model or effort changed during the attempt")
    result = {"review_visibility": True, "parent_session": parent, "model": identity["model"],
              "effort": identity["reasoningEffort"], "cli_version": identity["cliVersion"], "reviewers": [],
              "instrumentation": {"events": len(events), "identity_source":
                                  "native persisted thread metadata plus active-model hooks" if agent == "codex"
                                  else "assistant stream models plus effective-effort hooks"}}
    for delegated_index, start in enumerate(events, 1):
        if start.get("event") != "SubagentStart":
            continue
        child = start.get("agent")
        observed = native.get(child, {})
        if not all(isinstance(observed.get(key), str) and observed[key]
                   for key in ("model", "reasoningEffort", "cliVersion")):
            raise ValueError("native CLI omitted observed reviewer model/effort/version")
        next_start = next((index for index, event in enumerate(events, 1) if index > delegated_index
                           and event.get("event") == "SubagentStart" and event.get("agent") == child), len(events) + 1)
        stops = [(index, event) for index, event in enumerate(events, 1)
                 if delegated_index < index < next_start and event.get("event") == "SubagentStop" and event.get("agent") == child]
        if not stops:
            raise ValueError("reviewer session has no observed completion")
        if len(stops) != 1:
            raise ValueError("reviewer re-review interval lacks an observed start boundary")
        completed_index, stop = stops[-1]
        if not start.get("workspace") or not stop.get("workspace"):
            raise ValueError("reviewer interval lacks full-workspace snapshots")
        pins = start.get("pins", {})
        converged = [index for index, event in enumerate(events, 1) if index < delegated_index
                     and event.get("converged") and event.get("pins", {}).get("convergence") == pins.get("convergence")]
        verified = [index for index, event in enumerate(events, 1) if index > completed_index and event.get("verified")]
        during = events[delegated_index:completed_index]
        writes = list(observed.get("writes", []))
        if any(event.get("pins", {}).get("source") not in (None, pins.get("source")) for event in during):
            writes.append("source mutation during reviewer interval")
        if any(event.get("workspace") not in (None, start["workspace"]) for event in during):
            writes.append("workspace mutation during reviewer interval (including Markdown and knowledge)")
        previous = [review for review in result["reviewers"] if review["session"] == child]
        for review in previous:
            writes.extend(review["writes"])
        result["reviewers"] = [review for review in result["reviewers"] if review["session"] != child]
        result["reviewers"].append({
            "session": child, "parent_session": observed.get("parentThreadId"), "model": observed["model"],
            "effort": observed["reasoningEffort"], "role": observed.get("agentRole", start.get("role")),
            "read_only": start.get("role") == "reviewer", "tool_restrictions":
                ["reviewer role forbids writes; source snapshots and native tool events observed; no hostile-process sandbox"],
            "converge_sequence": max(converged, default=0), "delegated_sequence": delegated_index,
            "completed_sequence": completed_index, "verify_sequence": min(verified, default=0),
            "before": pins, "after": stop.get("pins", {}), "reviewed": pins, "writes": writes,
            "report_sha256": observed.get("reportHash"), "verdict": observed.get("verdict")})
    return result


def arm_deadline(deadline):
    if os.name != "posix" or not hasattr(signal, "setitimer"):
        raise ValueError("native hook deadline supervision requires POSIX timers")
    remaining = deadline - time.time()
    if remaining <= 0: raise ValueError("native hook envelope deadline expired")
    def expired(signum, frame):
        os.killpg(os.getpgrp(), signal.SIGKILL)
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, remaining)


def workspace_digest(root):
    import behavior
    names = behavior.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], root).splitlines()
    result = hashlib.sha256()
    for name in sorted(set(names)):
        result.update(name.encode()); result.update(b"\x00")
        try:
            path = root / name
            if path.is_symlink():
                result.update(b"<symlink>" + os.readlink(path).encode())
            else:
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(65536), b""):
                        result.update(chunk)
        except FileNotFoundError:
            result.update(b"<missing>")
        result.update(b"\x00")
    return result.hexdigest()


def hook():
    # Native CLIs can put hooks in separate sessions. This timer independently
    # stops that hook's group at the original supervisor deadline after runner death.
    arm_deadline(float(os.environ["LIFECYCLE_EVAL_DEADLINE"]))
    payload = json.loads(sys.stdin.buffer.read(LIMIT + 1))
    root, directory = Path(os.environ["GAP5_WORKSPACE"]), Path(os.environ["GAP5_CAPTURE"])
    sys.path.insert(0, str(Path(__file__).parent / "lib"))
    import lifecycle
    import eval_outcome
    state = lifecycle.load(root)
    event = {"event": payload["hook_event_name"], "session": payload["session_id"],
             "agent": payload.get("agent_id"), "role": payload.get("agent_type"),
             "model": payload.get("model"), "effort": (payload.get("effort") or {}).get("level"),
             "tool": payload.get("tool_name"), "tool_use_id": payload.get("tool_use_id"),
             "workspace": workspace_digest(root),
             "pins": eval_outcome.candidate_pins(root, state) if state else {},
             "converged": bool(state and state.get("converge")), "verified": bool(state and lifecycle.complete(state, "verify"))}
    text = payload.get("last_assistant_message")
    tool_input = payload.get("tool_input") or {}
    if payload.get("tool_name") == "SubagentHandback":
        text = tool_input.get("message")
    if isinstance(text, str) and "## Verdict" in text:
        event["reportHash"] = report_hash(text)
        event["verdict"] = "Approved" if "\nApproved" in text.split("## Verdict", 1)[1] else "Changes requested"
    data = (json.dumps(event, separators=(",", ":")) + "\n").encode()
    path = directory / "events.jsonl"
    with path.open("ab") as output:
        fcntl.flock(output, fcntl.LOCK_EX)
        if output.tell() + len(data) > LIMIT:
            raise ValueError("observation event output cap exhausted")
        output.write(data); output.flush(); os.fsync(output.fileno())


def native_codex(binary, thread_ids, hook_cwd=None, config=None):
    """Read persisted metadata; never send thread/start/resume or turn/start."""
    result, buffer, total = {}, bytearray(), 0
    config = codex_config(hook_cwd, {}) if config is None and hook_cwd else (config or [])
    with subprocess.Popen([str(binary), *config, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, cwd=hook_cwd) as server:
        end = time.monotonic() + 20
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(server.stdout, selectors.EVENT_READ)
                def request(index, method, params):
                    nonlocal total, buffer
                    server.stdin.write((json.dumps({"id": index, "method": method, "params": params}) + "\n").encode())
                    server.stdin.flush()
                    while time.monotonic() < end:
                        while b"\n" in buffer:
                            line, _, rest = buffer.partition(b"\n"); buffer = bytearray(rest)
                            message = json.loads(line)
                            if message.get("id") == index:
                                if "error" in message:
                                    raise ValueError("native thread/read refused: " + str(message["error"]))
                                return message["result"]
                        if not selector.select(max(0, end - time.monotonic())):
                            break
                        chunk = os.read(server.stdout.fileno(), 16384)
                        total += len(chunk)
                        if not chunk or total > LIMIT:
                            raise ValueError("native metadata closed or exceeded output cap")
                        buffer.extend(chunk)
                    raise ValueError("native metadata deadline expired")
                request(1, "initialize", {"clientInfo": {"name": "gap5_readonly_observer", "version": "1"},
                                          "capabilities": {"experimentalApi": True}})
                server.stdin.write(b'{"method":"initialized"}\n'); server.stdin.flush()
                if hook_cwd:
                    result["_hooks"] = request(2, "hooks/list", {"cwds": [str(hook_cwd)]})
                    result["_models"] = request(3, "model/list", {"limit": 100, "includeHidden": True})
                    result["_configuration"] = request(4, "config/read", {"cwd": str(hook_cwd), "includeLayers": False})["config"]
                for index, thread_id in enumerate(thread_ids, 5):
                    thread = request(index, "thread/read", {"threadId": thread_id, "includeTurns": True})["thread"]
                    if thread.get("id") != thread_id:
                        raise ValueError("native thread identity mismatch")
                    texts, writes = [], []
                    for turn in thread.get("turns", []):
                        for item in turn.get("items", []):
                            if item.get("type") == "agentMessage": texts.append(item.get("text", ""))
                            if item.get("type") == "fileChange": writes.append(item.get("id", "file change"))
                    reports = [text for text in texts if "## Verdict" in text]
                    report = reports[-1] if reports else ""
                    result[thread_id] = {key: thread.get(key) for key in
                                         ("model", "reasoningEffort", "cliVersion", "parentThreadId", "agentRole")}
                    result[thread_id].update(reportHash=report_hash(report) if report else None, writes=writes,
                                             verdict="Approved" if report and "\nApproved" in report.split("## Verdict", 1)[1]
                                             else "Changes requested")
        finally:
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=5)
    return result


def native_claude(events, output, version):
    starts = [event for event in events if event["event"] == "SessionStart"]
    if not starts: raise ValueError("Claude SessionStart was not observed")
    parent = starts[0]["session"]
    delegated = [event for event in events if event["event"] == "SubagentStart"]
    native = {}
    for session in [parent, *(event["agent"] for event in delegated)]:
        matching = [event for event in events if (event.get("agent") == session if session != parent else not event.get("agent"))]
        efforts = {event["effort"] for event in matching if event.get("effort")}
        models = {event["model"] for event in matching if event.get("model")}
        delegation_ids = set()
        if session != parent:
            start_index = next(index for index, event in enumerate(events)
                               if event.get("event") == "SubagentStart" and event.get("agent") == session)
            calls = [event.get("tool_use_id") for event in events[:start_index]
                     if event.get("event") == "PreToolUse" and event.get("tool") in ("Agent", "Task")]
            if calls: delegation_ids.add(calls[-1])
        # Actual assistant stream messages carry model identity; request flags do not.
        for line in output.splitlines():
            try: message = json.loads(line)
            except ValueError: continue
            if message.get("type") != "assistant": continue
            child = message.get("agent_id")
            if ((session == parent and not message.get("parent_tool_use_id") and not child)
                    or child == session or message.get("parent_tool_use_id") in delegation_ids):
                model = message.get("message", {}).get("model")
                if model: models.add(model)
        if len(models) != 1 or len(efforts) != 1:
            raise ValueError("Claude active model/effective effort is missing or changed")
        reports = [event for event in matching if event.get("reportHash")]
        native[session] = {"model": next(iter(models)), "reasoningEffort": next(iter(efforts)),
                           "cliVersion": version, "parentThreadId": parent if session != parent else None,
                           "agentRole": "reviewer" if session != parent else None,
                           "reportHash": reports[-1]["reportHash"] if reports else None,
                           "verdict": reports[-1]["verdict"] if reports else None,
                           "writes": [event.get("tool") for event in matching if event.get("tool") in
                                      ("Edit", "Write", "MultiEdit", "NotebookEdit", "apply_patch")]}
    return native


def toml(value):
    if isinstance(value, dict): return "{" + ",".join(json.dumps(k) + "=" + toml(v) for k, v in value.items()) + "}"
    if isinstance(value, list): return "[" + ",".join(toml(v) for v in value) + "]"
    return json.dumps(value)


def codex_config(root, hooks):
    # The CLI splits dotted override keys before TOML parsing, including quoted
    # path segments. Override the whole table so .git/dotted paths stay intact.
    values = {"projects": {str(root): {"trust_level": "trusted"}},
              "model": MODELS["codex"], "model_reasoning_effort": "medium",
              "approval_policy": "never", "approvals_reviewer": "user",
              "sandbox_mode": "workspace-write",
              "sandbox_workspace_write": {"writable_roots": [str(root / ".git/okf-scratch")]}}
    config = ["--dangerously-bypass-hook-trust"]
    for key, value in values.items(): config.extend(["-c", key + "=" + toml(value)])
    for event, groups in hooks.items(): config.extend(["-c", "hooks." + event + "=" + toml(groups)])
    return config


def require_codex_hooks(preflight, collector=None):
    entries = preflight.get("_hooks", {}).get("data", [])
    if not entries or any(entry.get("errors") for entry in entries):
        raise ValueError("native Codex hook discovery is unavailable; model launch refused")
    enabled = [hook for entry in entries for hook in entry.get("hooks", []) if hook.get("enabled")]
    if not any(hook.get("eventName") == "preToolUse" and "lifecycle.py" in hook.get("command", "") for hook in enabled):
        raise ValueError("native Codex reported no active lifecycle edit gate; model launch refused")
    if not any(hook.get("eventName") == "preToolUse" and "shell_guard.py" in hook.get("command", "") for hook in enabled):
        raise ValueError("native Codex reported no active shell guard; model launch refused")
    if not any(item.get("model") == MODELS["codex"] for item in preflight.get("_models", {}).get("data", [])):
        raise ValueError("pinned Codex model absent from native account catalog; model launch refused")
    if collector:
        required = {event[0].lower() + event[1:] for event in EVENTS}
        observed = {hook.get("eventName") for hook in enabled if hook.get("command") == collector}
        if not required <= observed:
            raise ValueError("native Codex observation hooks missing; model launch refused")
        if not any(hook.get("eventName") == "sessionStart" and "lifecycle.py" in hook.get("command", "")
                   for hook in enabled):
            raise ValueError("native Codex lifecycle router missing; model launch refused")


def configuration_digest(value, directory):
    # Fixture/helper locations vary per cell; configuration contents do not.
    def normalize(item):
        if isinstance(item, str): return item.replace(str(directory), "$ATTEMPT")
        if isinstance(item, list): return [normalize(value) for value in item]
        if isinstance(item, dict): return {normalize(key): normalize(value) for key, value in item.items()}
        return item
    encoded = json.dumps(normalize(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def pin_configuration(value, pin, initialize_only):
    if pin is None:
        return
    if initialize_only:
        with pin.open("x") as output:
            json.dump({"configuration_sha256": value}, output); output.flush(); os.fsync(output.fileno())
    elif json.loads(pin.read_text()).get("configuration_sha256") != value:
        raise ValueError("effective CLI configuration changed from the frozen preflight; model launch refused")


def launch(agent, binary, initialize_only=False, configuration_pin=None):
    # Refuse before CLI creation unless independent supervision supplied a deadline.
    deadline = float(os.environ["LIFECYCLE_EVAL_DEADLINE"])
    if deadline <= time.time(): raise ValueError("agent envelope deadline expired")
    root = Path.cwd().resolve()
    directory = root.parent / "live-capture"
    directory.mkdir(mode=0o700)
    tools = directory / "tools"; tools.mkdir()
    operator = Path(__file__).resolve()
    sys.path.insert(0, str(operator.parent))
    import behavior
    version_output = behavior.run([str(binary), "--version"], root)
    versions = re.findall(r"(?<![\d.])\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.]+)?", version_output)
    if versions != [VERSIONS[agent]]:
        raise ValueError("CLI version changed from the frozen configuration")
    library = tools / "lib"; library.mkdir()
    for source in (operator.parents[2] / "scripts").glob("*.py"):
        shutil.copy2(source, library / source.name)
    helper = tools / operator.name; shutil.copy2(operator, helper)
    shutil.copy2(operator.parent / "behavior.py", tools / "behavior.py")
    command = shlex.join([sys.executable, str(helper), "hook"])
    hooks = {event: [{"hooks": [{"type": "command", "command": command, "timeout": 10}]}] for event in EVENTS}
    if agent == "codex":
        config = codex_config(root, hooks)
        preflight = native_codex(binary, [], hook_cwd=root, config=config)
        require_codex_hooks(preflight, collector=command)
        configuration = configuration_digest(preflight["_configuration"], root.parent)
        pin_configuration(configuration, configuration_pin, initialize_only)
        if initialize_only:
            print(json.dumps({"initialization_only": True, "model_requested": False,
                              "cli_version": versions[0], "qualification": "native enabled hook inventory"}))
            return 0
        argv = [str(binary), *config, "exec", "--json"]
    else:
        settings = {"hooks": hooks, "permissions": {"allow": ["Bash(python3 .ai/scripts/*)",
                    "Bash(python3 -m unittest*)", "Bash(git *)"]}}
        project_hooks = json.loads((root / ".claude/settings.json").read_text())["hooks"]
        for event, groups in project_hooks.items():
            settings["hooks"][event] = [*groups, *settings["hooks"].get(event, [])]
        configuration = configuration_digest({"settings": settings,
            "project": (root / ".claude/settings.json").read_text()}, root.parent)
        pin_configuration(configuration, configuration_pin, initialize_only)
        argv = [str(binary), "-p", "--output-format", "stream-json", "--verbose", "--forward-subagent-text",
                "--include-hook-events", "--model", MODELS[agent], "--effort", "medium",
                "--permission-mode", "acceptEdits", "--permission-prompts", "none", "--setting-sources", "project",
                "--strict-mcp-config", "--settings", json.dumps(settings)]
        if initialize_only: argv.extend(["--init-only", "--debug-file", str(directory / "native-debug.log")])
    env = {**os.environ, "GAP5_WORKSPACE": str(root), "GAP5_CAPTURE": str(directory), "PYTHONDONTWRITEBYTECODE": "1"}
    # CLI/reviewer processes retain the outer supervisor group. Native hook groups
    # independently inherit the same absolute deadline through arm_deadline().
    data = bytearray()
    with subprocess.Popen(argv, stdin=sys.stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env) as child:
        try:
            while True:
                chunk = os.read(child.stdout.fileno(), 16384)
                if not chunk: break
                event_path = directory / "events.jsonl"
                if len(data) + len(chunk) + (event_path.stat().st_size if event_path.exists() else 0) > LIMIT:
                    raise ValueError("combined agent/reviewer event-output cap exhausted")
                data.extend(chunk); sys.stdout.buffer.write(chunk); sys.stdout.buffer.flush()
            code = child.wait()
        finally:
            if child.poll() is None: child.kill(); child.wait(timeout=5)
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    if initialize_only:
        if not any(event["event"] == "SessionStart" for event in events):
            raise ValueError("no-model initialization did not activate observation hooks")
        print(json.dumps({"initialization_only": True, "model_requested": False,
                          "cli_version": versions[0], "session_start_events": len(events)}))
        return code
    if agent == "codex":
        ids = list(dict.fromkeys([events[0]["session"], *(event["agent"] for event in events if event["event"] == "SubagentStart")]))
        native = native_codex(binary, ids)
    else:
        native = native_claude(events, data.decode("utf-8", errors="replace"), versions[0])
    observations = assemble(agent, events, native)
    observations["instrumentation"]["configuration_sha256"] = configuration
    path = root.parent / "live-observations.json"
    with path.open("x") as output:
        path.chmod(0o600); json.dump(observations, output); output.flush(); os.fsync(output.fileno())
    return code


if __name__ == "__main__":
    if sys.argv[1] == "hook": hook()
    elif sys.argv[1] in ("launch", "preflight"):
        raise SystemExit(launch(sys.argv[2], Path(sys.argv[3]), initialize_only=sys.argv[1] == "preflight",
                               configuration_pin=Path(sys.argv[4]) if len(sys.argv) > 4 else None))
    elif sys.argv[1] == "adapter":
        root = Path(sys.argv[2]).resolve()
        print((root.parent / "live-observations.json").read_text())
    else: raise SystemExit("unknown observation mode")
