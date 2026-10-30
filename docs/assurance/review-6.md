# Review: Assurance STALE demo (increment 6)

Reviewer: `reviewer` subagent, independent of the implementation. Report saved by the implementing session because the reviewer had no file-write tool. Untracked working file.

## Findings

No Critical, High or Medium findings.

Low:
1. `IsolationTests` snapshots `git status --porcelain=v2 -z`, `HEAD` and the state file of the framework worktree while `run_tests.py` runs other classes in parallel. A concurrent test writing in that worktree could fail it spuriously. No such writer was found, and two full runs passed. Comparing only demo-relevant entries would remove the risk.
2. The runtime network check tolerates `socket` in `sys.modules`; the static AST check on `assurance_demo.py` still covers the demo's own imports, so R4 is met for the demo's code.
3. The `calls` list asserted in `test_only_git_okf_and_lifecycle_are_invoked_and_steps_are_lifecycle` is built by the demo, so asserting its prefix is partly tautological; the `subprocess.run` spy over real argv gives the assertion substance.
4. Cleanup runs on `DemoFailure`, other exceptions, `KeyboardInterrupt` and `SIGTERM`. The SIGTERM handler is installed in `main()` and has no test. Acceptable.

## Spec compliance

- R1: temp Git repo with script copies and one scoped `Verify:`/`Inputs:` obligation; demonstrated steps use `lifecycle.py` only; removed on success, step failure and a raising `prepare`.
- R2, R3: every printed status comes from `assure --json`; each step is compared with its expectation before printing; mismatch exits 1 with "step N (title): expected X, observed Y". `FailClosedTests` cover all-VERIFIED (fails at step 1) and STALE-as-VERIFIED (fails at step 4).
- R4: invoking repo only read as a copy source; `GIT_*` and lifecycle override variables dropped; before/after snapshot test.
- R5: limit sentence printed only after all steps pass, as the last line; absent on failure.
- R6: `EndToEndTests` runs the built script as a subprocess and asserts exit 0, ordered statuses, last line and an empty temp base.
- R7: one sentence added to `.ai/lifecycle.md`, one term added to the conformance test, nothing tracked under `docs/`, no `assure`, hook or gate change.

## Completeness (AGENTS.md §8.1)

No stubs, TODOs or deferred paths. Tests assert real outcomes (statuses, ordering, exit codes, removed directories, unchanged repository state).

## Validation Reviewed

- Ran `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_demo.py`: 10 tests, OK.
- Ran `python3 .ai/scripts/assurance_demo.py`: exit 0, statuses UNVERIFIED, VERIFIED, VERIFIED, STALE, STALE, VERIFIED; the worktree showed only the intended changes afterwards.
- Ran `python3 .ai/scripts/run_tests.py` twice in the worktree: 642 tests OK each time.
- Read the spec, the diff, `assurance_demo.py` and the whole test file.
- Not rerun: converge, the lifecycle stage records, and the author's broken-variant runs; relied on stated evidence.

## Verdict

Approved. The Low items are non-blocking; item 1 is the one to tighten if the parallel suite ever flakes.
