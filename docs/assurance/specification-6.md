# Spec: Assurance STALE demo (increment 6)

Version: **0.2.0-draft**, 2026-10-27. Framework base: `4031aab` (increment 1 merged, PR #19). Tier: L2, kind feature.
Revised from 0.1.0: the walkthrough document and drift checker were dropped; the repository holds no docs.
Context: architecture §6 row 6 (adoption).

## Problem and outcome

Increment 1 ships `lifecycle.py assure`, but a new reader cannot see its differentiator (a later change invalidates earlier verification, and only the affected requirement must be rerun) without composing a repository by hand.

When this ships, one command, `python3 .ai/scripts/assurance_demo.py`, shows in under a minute a requirement going VERIFIED, then STALE naming the edited file, then VERIFIED again after rerun, with an unrelated edit leaving it VERIFIED, and states what VERIFIED covers. Its output is the walkthrough: no document is added to the repository. A test fails if the demo's behavior stops matching the real CLI. No `assure` behavior, hook, gate or lifecycle rule changes.

## Users and scenarios

- An evaluator or adopter runs the demo and sees STALE detection without touching their own repository.
- A maintainer changes `assurance.py`, `ledger.py` or the CLI output; the demo test fails if the shown behavior breaks.

## Requirements

- R1: `.ai/scripts/assurance_demo.py` MUST build a temporary Git repository containing copies of the framework scripts and a structured capability with one scoped `- Verify:` obligation, run only the real `lifecycle.py` CLI for the demonstrated steps, and remove the temporary repository on exit, including on failure.
- R2: The demo MUST print, in order, these steps with the real `assure` status for each: UNVERIFIED before any run; VERIFIED after `assure --run`; VERIFIED after an edit to a file outside the declared inputs; STALE naming the edited input file after an input edit; `assure --changed --base` listing that obligation; VERIFIED after `assure --run` again.
- R3: The demo MUST obtain every status it prints from `lifecycle.py assure --json` output and MUST exit nonzero, naming the step, if any status differs from the step's expectation; it MUST NOT print a status it did not observe.
- R4: The demo MUST NOT read, write or change the invoking repository's files, Git state, lifecycle state or ledger, and MUST run offline with the standard library only (Python 3.9+).
- R5: The demo MUST print, as its last line after a successful run, the sentence `VERIFIED covers only the declared command on its declared inputs.`
- R6: A test MUST run the built demo script as a subprocess and fail when any R2 step is unobserved, out of order, or reported with a different status, when the R5 sentence is missing, or when the temporary repository survives the run.
- R7: `.ai/lifecycle.md` Assurance status SHOULD gain one sentence naming `python3 .ai/scripts/assurance_demo.py`; no other existing document changes, no file is added under `docs/`, and existing tests MUST keep their outcomes.

## Acceptance

- R1: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_demo.py -k BuildTests` passes, asserting the temp repo holds the capability and the scripts, every demonstrated step command is `lifecycle.py`, and the directory is gone after a normal run and after a forced step failure.
- R2: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_demo.py -k SequenceTests` passes, asserting the six steps appear in order with statuses UNVERIFIED, VERIFIED, VERIFIED, STALE (message contains the input file name), a `--changed` listing, VERIFIED.
- R3: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_demo.py -k FailClosedTests` passes, using a patched `assurance.py` that always reports VERIFIED; the demo exits nonzero naming the step and prints no false status.
- R4: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_demo.py -k IsolationTests` passes, asserting the invoking repo's `git status`, state file and lifecycle records are byte-identical before and after, and that no network module is imported.
- R5: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_demo.py -k LimitSentenceTests` passes, asserting the sentence is the last output line of a successful run and absent from a failed run.
- R6: `python3 .ai/scripts/assurance_demo.py` exits 0, and `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_demo.py -k EndToEndTests` passes, driving the built script as a subprocess and asserting the six ordered steps, the final VERIFIED, the R5 sentence and the removed temp repo.
- R7: `python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle_conformance.py` passes, and `python3 .ai/scripts/run_tests.py` passes.

Each new test class is shown to fail against a deliberately broken variant before
acceptance (`AGENTS.md` §8.6).

## Constraints

- Standard library only, Python 3.9+; reuse the `Case` fixture pattern (copy scripts, `git init`, `okf.py init`, `disk_tmp`); extract shared fixture helpers only if duplication exceeds a few lines.
- Report-only: no new `assure` flag, status, schema or exit code; no hook, stage, tier or gate change.
- No paid, network or long-running steps; the demo completes in seconds.
- Framework source: no `knowledge/` edits and no committed documents; this spec is an untracked working file.

## Non-goals

- Adapters, attested evidence, constraint rules, dashboards, measurement (increments 3-5, 7).
- Demonstrating an adopter's own repository, or a recorded terminal session or video.
- A tutorial for writing capabilities in general.
- Showing the unscoped (whole-tree) obligation as a demo step.
- A walkthrough document or a check that parses documentation.

## Assumptions

- The demo lives at `.ai/scripts/assurance_demo.py`, so a user can run it directly and a test can import it.
- It never touches the user's repo: a throwaway temp repo only, with no `--keep` option.
- The demo output replaces the walkthrough; the `.ai/lifecycle.md` sentence only points to the command.
- `assure --changed` is included as the minimal-rerun differentiator; the unscoped case is excluded.
- Increment 1 (PR #19) is merged and is the baseline.

## Open questions

None.
