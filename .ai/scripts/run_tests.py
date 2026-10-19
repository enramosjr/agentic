#!/usr/bin/env python3
"""Run a unittest suite in parallel, one worker process per test class.

Runs the same tests as `python3 -m unittest discover -s DIR` and prints only
failures, errors and a one-line summary. Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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
    }))
    return 0


def run_group(start: Path, name: str, expected: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        result_path = Path(tmp) / "result.json"
        process = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "-s", str(start), "--worker", name, "--result", str(result_path)],
            capture_output=True, text=True, errors="replace")
        if result_path.is_file():
            return json.loads(result_path.read_text())
    output = (process.stdout + process.stderr)[-4000:]
    return {"run": expected, "failures": [], "errors": [[name, f"worker exited {process.returncode}\n{output}"]],
            "unexpected": [], "skipped": 0}


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
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = list(pool.map(lambda n: run_group(start, n, counts[n]), names))

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
    sys.exit(main())
