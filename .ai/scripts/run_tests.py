#!/usr/bin/env python3
"""Run a unittest suite in parallel, one worker process per test class.

Runs the same tests as `python3 -m unittest discover -s DIR` and prints only
failures, errors and a one-line summary. Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.dont_write_bytecode = True

DEFAULT_START = Path(__file__).resolve().parent / "tests"
RULE = "=" * 70


def leaves(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from leaves(item)
        else:
            yield item


def groups(start: Path) -> dict[str, int]:
    """Test count per `module.Class`; a module that fails to import or load is its own group, named by the module."""
    sys.path.insert(0, str(start))
    counts: dict[str, int] = {}
    suite = unittest.TestLoader().discover(str(start), top_level_dir=str(start))
    for test in leaves(suite):
        test_id = test.id()
        key = test_id.rsplit(".", 1)[1] if test_id.startswith("unittest.loader.") else test_id.rsplit(".", 1)[0]
        counts[key] = counts.get(key, 0) + 1
    return counts


def worker(start: Path, name: str, result_path: Path) -> int:
    sys.path.insert(0, str(start))
    suite = unittest.TestLoader().loadTestsFromName(name)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    result_path.write_text(json.dumps({
        "run": result.testsRun,
        "failures": [[test.id(), trace] for test, trace in result.failures],
        "errors": [[test.id(), trace] for test, trace in result.errors],
        "unexpected": [test.id() for test in result.unexpectedSuccesses],
        "skipped": len(result.skipped),
    }), encoding='utf-8')
    return 0


def tree_fingerprint(start: Path) -> str:
    """Digest of every file the suite can depend on: the .ai tree, .github, and the test directory."""
    ai = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for top in (ai, ai.parent / ".github", start):
        for path in sorted(top.rglob("*")) if top.is_dir() else ():
            if path.is_file() and "__pycache__" not in path.parts:
                digest.update(str(path.relative_to(top.parent)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


class Resume:
    """Opt-in AGENTIC_TEST_RESUME=FILE: skip classes that already passed on exactly this tree, so an
    interrupted run restarts at the class in flight. Without the variable nothing is read or written."""

    def __init__(self, start: Path):
        value = os.environ.get('AGENTIC_TEST_RESUME')
        self.path = Path(value) if value else None
        self.lock = threading.Lock()
        self.passed: dict[str, dict] = {}
        if self.path:
            self.fingerprint = tree_fingerprint(start)
            try:
                saved = json.loads(self.path.read_text(encoding='utf-8'))
                if saved.get("fingerprint") == self.fingerprint:
                    self.passed = saved["passed"]
            except (OSError, ValueError, KeyError):
                pass

    def record(self, name: str, result: dict) -> None:
        if self.path and not (result["failures"] or result["errors"] or result["unexpected"]):
            with self.lock:
                self.passed[name] = result
                self.path.write_text(json.dumps({"fingerprint": self.fingerprint, "passed": self.passed}),
                                     encoding='utf-8')


def run_group(start: Path, name: str, expected: int, resume: Resume | None = None) -> dict:
    progress = os.environ.get('AGENTIC_TEST_PROGRESS') == '1'
    if resume and name in resume.passed:
        if progress:
            print(f'RESUMED {name}', flush=True)
        return resume.passed[name]
    if progress:
        print(f'START {name}', flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        result_path = Path(tmp) / "result.json"
        process = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "-s", str(start), "--worker", name, "--result", str(result_path)],
            capture_output=True, text=True, encoding='utf-8', errors="replace")
        if result_path.is_file():
            result = json.loads(result_path.read_text(encoding='utf-8'))
        else:
            output = (process.stdout + process.stderr)[-4000:]
            result = {"run": expected, "failures": [], "errors": [[name, f"worker exited {process.returncode}\n{output}"]],
                      "unexpected": [], "skipped": 0}
    if resume:
        resume.record(name, result)
    if progress:
        print(f'FINISH {name}: run={result["run"]} failures={len(result["failures"])} '
              f'errors={len(result["errors"])} unexpected={len(result["unexpected"])}', flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    # sys.dont_write_bytecode covers this process only. Fixture commands inherit
    # the environment and must not add cache files to acceptance repositories.
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("-s", "--start", type=Path, default=DEFAULT_START, help="test directory (default: .ai/scripts/tests)")
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1, help="worker processes (default: CPU count)")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--result", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    start = args.start.resolve()
    if args.worker:
        return worker(start, args.worker, args.result)

    began = time.monotonic()
    counts = groups(start)
    names = sorted(counts, key=lambda n: -counts[n])  # Larger classes first shortens the tail.
    resume = Resume(start)
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = list(pool.map(lambda n: run_group(start, n, counts[n], resume), names))

    run = sum(r["run"] for r in results)
    failures = [f for r in results for f in r["failures"]]
    errors = [e for r in results for e in r["errors"]]
    unexpected = [u for r in results for u in r["unexpected"]]
    skipped = sum(r["skipped"] for r in results)
    for kind, items in (("ERROR", errors), ("FAIL", failures)):
        for test_id, trace in items:
            print(f"{RULE}\n{kind}: {test_id}\n{'-' * 70}\n{trace}")
    for test_id in unexpected:
        print(f"{RULE}\nUNEXPECTED SUCCESS: {test_id}")
    details = ", ".join(f"{label}={n}" for label, n in (("failures", len(failures)), ("errors", len(errors)),
                                                        ("unexpected successes", len(unexpected)), ("skipped", skipped)) if n)
    ok = not (failures or errors or unexpected)
    verdict = ("OK" + (f" ({details})" if details else "")) if ok else f"FAILED ({details})"
    print(f"Ran {run} tests in {time.monotonic() - began:.1f}s with {max(1, args.jobs)} workers: {verdict}")
    return 0 if ok else 1


if __name__ == "__main__":
    import process_runtime
    process_runtime.configure_windows_environment()
    sys.exit(main())
