# Spec: Measurement of the assurance mechanism (increment 7)

Version: **0.1.0-draft**, 2026-10-28. Framework base: `9efcfb7` (increments 1, 4, 6 merged). Tier: L2, kind feature.
Context: architecture §6 row 7 and §8. Untracked working file: the repository holds no documents.

## Problem and outcome

The gate (increment 2) is blocked on a measured false-positive rate, and nothing yet says which assurance features earn their cost. Real agent campaigns are out of budget. Architecture §8 asks for a deterministic scenario fixture set that reports detection, false STALE and rerun counts against a "rerun everything" baseline.

When this ships, `python3 .ai/scripts/assurance_measure.py` builds six scenarios in throwaway repositories, drives the real `lifecycle.py assure`, and prints per-step and total counts of caught stale requirements, false STALE, missed stale requirements and reruns versus the baseline, plus how much each feature contributed. It exits 1 if any measured count differs from the count the mechanism is known to produce. It measures mechanism behavior, not agent outcomes.

## Users and scenarios

- A maintainer deciding whether to build the gate runs the command and reads the false-STALE and missed counts.
- A maintainer changing `assurance.py` or `ledger.py` runs it; a regression in detection (a missed stale requirement) turns the exit code to 1.
- A reader of the output sees which features saved reruns and which scenarios expose the known limits (an undeclared dependency, the whole-tree default).

## Requirements

- R1: `assurance_measure.py` MUST run six named scenarios (`feature`, `requirement-change`, `regression`, `stale-evidence`, `dependency`, `handoff`), each in its own throwaway Git repository holding a copy of these scripts and structured capability requirements with `Verify:` and `Inputs:`, and MUST observe status only from `lifecycle.py assure --json`. The invoking repository MUST NOT be modified.
- R2: The ground truth of each step MUST NOT be derived from `assure`. For a step that edits files, the affected set is the requirements whose declared true reads (a map from requirement to the files its check script actually reads, kept independent of `Inputs:`) intersect the edited files; for a step that edits a requirement block, the affected set is declared explicitly. Each check script MUST fail when any file in its true reads is missing.
- R3: For each step, after the change and before any rerun, the report MUST give `affected`, `flagged` (requirements whose status is STALE, FAILED or UNVERIFIED), `caught` (affected and flagged), `false_stale` (flagged, not affected), `missed` (affected, not flagged), `changed_missed` (affected requirements that `assure --changed --base HEAD` does not list), `reruns` (the size of `flagged`) and `baseline_reruns` (the number of declared requirements).
- R4: After measuring a step, the harness MUST rerun the flagged requirements with `assure --run` and compare their resulting statuses with the step's expected statuses (a broken check yields FAILED, all others VERIFIED); a difference MUST be reported as a failure of that step.
- R5: Each step MUST carry the expected `caught`, `false_stale` and `missed` counts. The command MUST exit 1 and name the scenario, step and metric when any observed count or post-rerun status differs, and exit 0 when all match. The known profile is: `missed` is 1 only for the step that edits a file the check reads but `Inputs:` omits; `false_stale` is 1 only for the step that edits an unrelated file under a requirement with no `Inputs:`; every other step has `missed` 0 and `false_stale` 0.
- R6: The text report MUST show a row per step, scenario totals, grand totals and a `contribution` section: reruns avoided by scoped `Inputs:` (baseline minus reruns, summed), false STALE caused by the whole-tree default, affected requirements `--changed` listed and missed, and the number of handoff detections served from a committed record. It MUST end with the sentence "Measures mechanism behavior on fixtures, not agent outcomes." `--json` MUST emit `schema_version` 1 with `scenarios`, `totals` and `contribution`. Output MUST be deterministic: two runs are byte-identical and contain no paths, timestamps or hashes.
- R7: The change MUST be report-only: no edit to `assurance.py`, `ledger.py`, `lifecycle.py` or to `assure` output, no gate, hook, stage or `okf.py` rule, and nothing removed. Pruning appears only as the contribution numbers of R6.
- R8: The temporary repositories MUST be removed on success, failure and SIGTERM. The command MUST exit 2 with a one-line reason when no disk-backed temporary directory exists, and MUST accept an optional hook that edits the copied scripts before a scenario runs, so a test can inject a broken `assure`.
- R9: The `## Assurance status` section of `.ai/lifecycle.md` MUST name `python3 .ai/scripts/assurance_measure.py` in one sentence, and the existing conformance test MUST check it.

## Acceptance

- R1: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py -k ScenarioTests` passes (six scenarios, each in its own repository, statuses read from `assure --json`, the invoking repository byte-identical before and after).
- R2: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py -k OracleTests` passes (the affected set equals the true-reads intersection for every file-edit step; deleting a true-read file makes its check exit nonzero; the oracle code imports neither `assurance` nor `lifecycle`).
- R3: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py -k MetricTests` passes (exact key set per step; hand-computed counts for one step of each scenario).
- R4: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py -k RerunTests` passes (the regression step ends FAILED, the others VERIFIED; a forced wrong expectation is reported as a step failure).
- R5: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py -k ExpectationTests` passes (the unmodified mechanism exits 0 with the known profile; a hook making `assure` report STALE as VERIFIED exits 1 naming `missed`; a hook making every requirement STALE exits 1 naming `false_stale`).
- R6: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py -k ReportTests` passes (rows, totals, contribution numbers equal the hand-computed ones, closing sentence, `--json` key set and `schema_version` 1, two runs byte-identical).
- R7: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py -k ReportOnlyTests` passes (`git diff` on the four named scripts is empty for this change; `test_assurance.py` and `test_assurance_attested.py` pass unmodified).
- R8: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py -k CleanupTests` passes (no temporary repository remains after success, after a forced failure and after SIGTERM; exit 2 when the temporary directory is not disk-backed).
- R9: `python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle_conformance.py -k Assurance` passes.

Each new test class is shown to fail against a deliberately broken variant before acceptance (`AGENTS.md` §8.6); a variant that cannot be observed is equivalent and is replaced.

## Constraints

- Standard library only, Python 3.9+. May reuse `Session`, `DemoFailure` and the temporary-directory helper of `assurance_demo.py` without changing its behavior or output.
- Runs with no network and no spend; total runtime is bounded by running each scenario once.
- No `knowledge/` and no new committed documents in the framework source; `docs/` stays untracked. Editing the existing `.ai/lifecycle.md` and its conformance test is allowed.

## Non-goals

- Measuring agent outcomes, paid or long campaigns, or comparison with other tools.
- Scanning this repository's own lifecycle records for accepted changes later found to invalidate earlier verification (the framework source has no capability requirements with `Verify:`); this is a known limit.
- Removing or changing any feature, the gate (increment 2), input adapters (increment 5) or architecture constraints (increment 3).
- Timing or performance benchmarks.

## Assumptions

- Replaces "what is the ground truth?": hand-declared true reads per requirement, with the check scripts reading exactly those files, so the oracle is independent of `Inputs:` and of `assure`.
- Replaces "what counts as flagged?": status STALE, FAILED or UNVERIFIED after the change, the set a maintainer would rerun.
- Replaces "what is the baseline?": rerun every declared requirement after every change; it catches every affected requirement by construction, so only its rerun count is compared.
- The six scenarios are the architecture §8 list. `feature` edits a source file one requirement reads and adds an unrelated file; `requirement-change` edits a `Verify:` command; `regression` breaks a file a check reads; `stale-evidence` edits an unrelated file and then an input of a single requirement; `dependency` edits a declared dependency, an undeclared one (a known miss) and an unrelated file under a whole-tree requirement (a known false STALE); `handoff` records evidence, commits it, starts a new task and edits an input, so the status comes from a committed record.
- A step's expected counts are written by hand from the mechanism's documented behavior (inputs bind evidence; no `Inputs:` binds the whole tree), not copied from a run.

## Open questions

None.
