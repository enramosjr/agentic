"""Bounded argv execution with a deadline owner independent of the caller.

The supervisor owns a separate session from both runner and command. It survives a
runner SIGKILL and always kills the command's process group, including descendants.
This is process supervision, not a sandbox against deliberately escaping children.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import selectors
import subprocess
import sys
import tempfile
import time
import uuid


OUTPUT_LIMIT = 4 * 1024 * 1024


def process_identity(pid: int) -> dict:
    """Linux birth identity prevents PID reuse from authorizing recovery signals."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
        if stat[0] == "Z":
            raise ProcessLookupError(pid)
        return {"pid": pid, "start_ticks": stat[19],
                "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
    except (OSError, IndexError, ValueError) as error:
        raise ProcessLookupError(pid) from error


def alive(identity: dict) -> bool:
    try:
        return process_identity(identity["pid"]) == {key: identity[key] for key in ("pid", "start_ticks", "boot")}
    except (ProcessLookupError, KeyError, TypeError):
        return False


class ProcessError(Exception):
    def __init__(self, code: str, message: str, output: str = ""):
        super().__init__(message)
        self.code = code
        self.output = output


def publish(path: Path, data: dict) -> None:
    """Durable publication; readers never observe a partial JSON document."""
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def stop_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def supervise(directory: Path) -> int:
    request = json.loads((directory / "request.json").read_text())
    # The runner must observe readiness before publishing its launch authorization.
    publish(directory / "ready.json", {"pid": os.getpid(), "token": request["token"]})
    arm = directory / "launch.json"
    while not arm.exists():
        if (time.time() >= request["deadline"] or (directory / "cancel.json").exists()
                or not (directory / "request.json").exists()):
            return 1
        time.sleep(0.01)
    if json.loads(arm.read_text()).get("token") != request["token"]:
        return 1
    child = None
    status = {"code": "launch", "exit": None, "message": "command did not launch"}
    try:
        with (directory / "output").open("wb") as output, (directory / "input").open("rb") as prompt:
            if time.time() >= request["deadline"] or (directory / "cancel.json").exists():
                raise ProcessError("timeout", "deadline expired before command launch")
            child_env = {**request["env"], "LIFECYCLE_EVAL_DEADLINE": str(request["deadline"])}
            child = subprocess.Popen(request["argv"], cwd=request["cwd"], env=child_env,
                                     stdin=prompt, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            try:
                child_identity = process_identity(child.pid)
            except ProcessLookupError:
                # An already-exited command has no recoverable live identity.
                child_identity = {"pid": child.pid, "start_ticks": None, "boot": None}
            publish(directory / "child.json", {**child_identity, "token": request["token"]})
            size, eof = 0, False
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                while True:
                    if (directory / "cancel.json").exists():
                        raise ProcessError("interrupted", "command cancelled by runner")
                    if time.time() >= request["deadline"]:
                        raise ProcessError("timeout", "command timed out")
                    for key, _ in selector.select(timeout=0.01):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            eof = True
                            selector.unregister(key.fileobj)
                            continue
                        remaining = request["output_limit"] - size
                        output.write(chunk[:remaining])
                        size += len(chunk)
                        if size > request["output_limit"]:
                            raise ProcessError("output-limit", "command exceeded output limit")
                    code = child.poll()
                    if code is not None:
                        stop_group(child.pid)
                        if eof:
                            status = {"code": "ok" if code == 0 else "exit", "exit": code,
                                      "message": f"command exit {code}"}
                            break
    except ProcessError as error:
        status = {"code": error.code, "exit": None, "message": str(error)}
    except (OSError, ValueError) as error:
        status = {"code": "launch", "exit": None, "message": f"cannot launch command: {error}"}
    finally:
        if child is not None:
            # Also remove background descendants left after an otherwise successful exit.
            stop_group(child.pid)
            child.wait()
            child.stdout.close()
        publish(directory / "result.json", status)
    return 0


def run(argv: list[str], cwd: Path, env: dict[str, str], storage: Path, *,
        timeout: float, input_text: str = "", output_limit: int = OUTPUT_LIMIT,
        before_launch=None, deadline: float | None = None, context: dict | None = None) -> subprocess.CompletedProcess:
    if os.name != "posix":
        raise ProcessError("supervision", "independent process-group supervision requires POSIX")
    if timeout <= 0:
        raise ProcessError("timeout", "command has no remaining time allowance")
    with tempfile.TemporaryDirectory(prefix="eval-process-", dir=storage) as temp:
        directory = Path(temp)
        end = min(time.time() + timeout, deadline) if deadline is not None else time.time() + timeout
        request = {"argv": argv, "cwd": str(cwd), "env": env, "deadline": end,
                   "output_limit": output_limit, "token": uuid.uuid4().hex, "context": context}
        (directory / "input").write_text(input_text, encoding="utf-8")
        publish(directory / "request.json", request)
        supervisor = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), str(directory)],
                                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, start_new_session=True,
                                      env={**env, "PYTHONDONTWRITEBYTECODE": "1"})
        armed = False
        try:
            ready = directory / "ready.json"
            handshake_deadline = min(request["deadline"], time.time() + 5)
            while not ready.exists():
                if supervisor.poll() is not None or time.time() >= handshake_deadline:
                    raise ProcessError("supervision", "independent deadline owner did not become ready")
                time.sleep(0.01)
            identity = json.loads(ready.read_text())
            if identity != {"pid": supervisor.pid, "token": request["token"]}:
                raise ProcessError("supervision", "deadline owner identity mismatch")
            identity.update(directory=str(directory), deadline=request["deadline"])
            identity.update(process_identity(supervisor.pid))
            identity["context"] = context
            if before_launch is not None:
                before_launch(identity)
            armed = True
            publish(directory / "launch.json", {"token": request["token"]})
            supervisor.wait(timeout=max(0.1, request["deadline"] - time.time()) + 5)
            result = json.loads((directory / "result.json").read_text())
            with (directory / "output").open("rb") as output:
                transcript = output.read(output_limit).decode("utf-8", errors="replace")
            if result["code"] != "ok":
                raise ProcessError(result["code"], result["message"], transcript)
            return subprocess.CompletedProcess(argv, result["exit"], transcript, "")
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            raise ProcessError("supervision", f"deadline supervision failed: {error}") from error
        finally:
            if supervisor.poll() is None:
                # On handled cancellation, stop the known child before its supervisor.
                child_file = directory / "child.json"
                if child_file.exists():
                    child = json.loads(child_file.read_text())
                    if child.get("token") == request["token"]:
                        stop_group(child["pid"])
                if armed:
                    # A cancellation marker closes the child-publication race: the
                    # supervisor owns cleanup even when no child ID is visible yet.
                    publish(directory / "cancel.json", {"token": request["token"]})
                    supervisor.wait(timeout=5)
                else:
                    supervisor.kill()
                    supervisor.wait()


if __name__ == "__main__":
    raise SystemExit(supervise(Path(sys.argv[1])))
