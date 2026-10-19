---
type: Playbook
title: Run the script test suite
description: "How to run the .ai/scripts tests serially or in parallel, and where their temporary fixtures live."
tags: [testing, playbook]
status: stable
evidence: validated-runtime
generated: { by: agent/cursor, at: 2026-10-19T20:57:01Z }
sources:
  - id: ai-scripts-run-tests-py
    resource: ../../.ai/scripts/run_tests.py
  - id: ai-scripts-tests-disk-tmp-py
    resource: ../../.ai/scripts/tests/disk_tmp.py
  - id: ai-scripts-tests-test-efficiency-py
    resource: ../../.ai/scripts/tests/test_efficiency.py
---

# Run the script test suite

How to run the .ai/scripts tests serially or in parallel, and where their temporary fixtures live.

## Commands

- Reference (serial): `python3 -m unittest discover -s .ai/scripts/tests`.
- Parallel: `python3 .ai/scripts/run_tests.py [-j N] [-s DIR]`. It discovers the same tests, runs each test class in its own worker process (default N: CPU count, larger classes first), and prints only failures, errors, and one summary line: `Ran N tests in Xs with J workers: OK|FAILED (...)`. Exit 0 only when nothing failed or errored. A module that cannot import is reported as an error under the module name.
- One module or class: `cd .ai/scripts/tests && python3 -m unittest test_lifecycle` (or `test_lifecycle.ClassName`).

Measured 2026-10-19 on 32 cores: serial 179 s, `run_tests.py` 46 s, same 497 tests and the same five failing ids.

## Temporary fixtures

`scratch.py` refuses scratch under `/tmp`, `/var/tmp`, `/dev/shm`, or tmpfs. Test fixture repositories are created with `tempfile`, so `tests/disk_tmp.py` (imported by the base test modules) checks the system temporary directory with `scratch.require_disk` and, only when it is refused, points `tempfile`, `TMPDIR`, `TMP` and `TEMP` at `$XDG_CACHE_HOME/okf-tests` (default `~/.cache/okf-tests`). A temporary directory that already passes, such as macOS's, is left alone. The cache directory is assumed to be outside any git work tree (a dotfiles repository at `$HOME` would break that; `test_efficiency.DiskTmp` then fails). New test modules that create git fixtures import `disk_tmp` or a base class from `test_autonomy` / `test_lifecycle`.

## Known failures

Without template-only `knowledge/` documents (for example `knowledge/project/lifecycle.md`, `knowledge/capabilities/learning-loop.md`, `knowledge/playbooks/install-and-upgrade.md`, `knowledge/project/aidlc-roadmap.md`), five documentation tests error with `FileNotFoundError`. They are independent of the code under test.
