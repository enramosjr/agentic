# Increment 7 implementation evidence

Persona: Python principal engineer. Tier: L2, existing approved spec and plan; no behavior decisions reopened. No commits, pushes or PRs authorized.

## Implementation

- Added the stdlib-only measurement script, six fixture scenarios, true-read oracle, expected counts, reruns and post-rerun checks, deterministic text/JSON and contribution report.
- Added acceptance classes for R1-R8 and the R9 lifecycle sentence and conformance check.
- Mechanism files, demo, and existing assurance/attestation tests remain unchanged. No dependency, gate, hook, stage or removal.
- Framework mode has no knowledge bundle. `okf.py affected` reports no bundle; `.agentic.json` and `repo.py context --json` confirm framework mode. Do not initialize a bundle. Existing lifecycle guide is synchronized; this evidence stays ignored.

## Red then green

- `lifecycle.py redgreen red -- python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py`: recorded RED, missing `assurance_measure` import.
- `lifecycle.py run measure-demo-baseline -- python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_demo.py`: PASS.
- `lifecycle.py redgreen green -- python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py`: recorded GREEN after implementing the approved behavior and correcting the test harness.
- `lifecycle.py run measure-conformance -- python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle_conformance.py -k Assurance`: PASS.

## Finding and retrospective

The handoff fixture initially ran two tasks within the same second. Source uses second precision for record timestamps and task names; observed post-rerun evidence selected the earlier committed record and remained STALE. The untracked `diagnose-7.py` reproduced this. The fixture now separates its two tasks by 1.05 seconds so it measures ordinary sequential handoff. This is a known measurement limit; assurance/ledger were not modified to repair the collision.

`lifecycle.py learn` recorded this finding with the diagnostic and red/green evidence; `lifecycle.py retrospect --lessons 1` closed the retrospective. It remains an advisory observation, not a binding rule.

## Expected report

Nine steps across six scenarios: caught 7, false_stale 1, missed 1, changed_missed 2, reruns 8, baseline_reruns 19. Contribution: reruns_avoided 11, whole_tree_false_stale 1, affected requirements changed_listed 6, changed_missed 2, handoff_from_record 1.

The deliberately omitted config input is the known miss; whole-tree binding produces the known false STALE. Measurement is on fixtures, not agent outcomes; pruning remains report-only.

## Review corrections

The independent reviewer found an unasserted text-rendering path (High) and null-evidence handoff crash (Medium). The rendering test now compares every numeric cell in step rows, scenario totals, grand total, and contributions with hand-computed constants. A zero-text-counts mutant verifies it. A real mechanism hook produces UNVERIFIED with null evidence; its red test reproduced AttributeError, and the null-safe lookup passed the same command via redgreen green.

Initial mutations: `lifecycle.py run measure-mutations -- python3 docs/assurance/mutate-7.py` PASS, all 20 planned variants killed after confirming the edited bytes. Affected report/expectation variants and the new rendering-only variant are rerun on the corrected candidate.

`lifecycle.py run measure-records -- python3 .ai/scripts/okf.py records` exited 1 because there is no OKF bundle. This check is inapplicable in framework mode, not a PASS. `lifecycle.py` lines 743-750 explicitly skip adopter sync-check/records for framework mode. No bundle was created.

## Final gate

Final source tree `cb75486`: R1-R9 converge PASS (9 PASS, 0 FAIL, 0 MANUAL); independent review Approved; targeted mutation run PASS (seven affected/new variants killed). `lifecycle.py run measure-framework -- python3 .ai/scripts/run_tests.py -j 8`, `run measure-cli -- python3 .ai/scripts/assurance_measure.py`, and `run measure-demo-cli -- python3 .ai/scripts/assurance_demo.py` each exited 0. `stage review --ref docs/assurance/review-7.md` and `stage verify` recorded. No candidate commit, push or PR; HEAD remains 9efcfb7. Shipment awaits the user.
