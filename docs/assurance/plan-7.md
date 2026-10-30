# Plan: Measurement of the assurance mechanism (increment 7)

Spec: specification-7.md (0.1.0-draft, approved, R1-R9). Tier L2, kind feature. Branch `claude/assurance-increment-7` at `9efcfb7` (main, includes increments 1, 4, 6).
Persona: Python (advisory). Untracked working file: the repository holds no documents and `docs/` is gitignored. Framework source has no `knowledge/`.

## Findings that shape the design

- `assurance_demo.py` already provides `Session` (runs argv in the throwaway repo, strips `GIT_*` and lifecycle env, `git`, `tool`, `lifecycle`, `write`), `DemoFailure`, `_base()` (disk-backed temp dir or `~/.cache/okf-tests`, via `scratch.require_disk`), `build()` (copies `HERE.glob('*.py')`, `git init`, `okf.py init`, `sync-ignore`, commits, `tier L1 --new`), SIGTERM handler (`sys.exit(143)` so `finally` runs `shutil.rmtree`). `tests/test_assurance_demo.py` is the pattern for cleanup, isolation (`TMPDIR` pointed at a disk-backed test dir) and fail-closed hooks (`prepare`).
- `assure --json` items carry `id, status, evidence{record,head,at,exit}, reason`; `assure --run IDS` exits 1 when a check fails (so use `ok=(0, 1)`); `assure --changed --base HEAD` lists obligations whose `Inputs:` match files changed from HEAD (committed diff plus untracked), and lists whole-tree obligations always.
- A requirement with no `Inputs:` binds the whole tree (Markdown and `knowledge/` exempt, as in `tree_hash`), so any other edit makes it STALE: the known false STALE. Editing a capability block does not touch any `Inputs:`, so `--changed` does not list it: expect `changed_missed` 1 for the requirement-change step, a real finding the report must show.
- Records publish when evidence is recorded; a committed record is read by a later task after `git add -A`, `git commit` and `lifecycle.py tier L1 --new` (`test_assurance.py` `test_evidence_from_earlier_committed_record`).
- The `Case` fixture in `test_assurance.py` copies `SCRIPTS.glob('*.py')` into a temp repo, so a new module in `.ai/scripts/` is picked up automatically. `test_lifecycle_conformance.Assurance` already checks the `## Assurance status` section.

## Design decisions

**D-a. Module layout.** New `.ai/scripts/assurance_measure.py`, stdlib only. It imports `Session`, `DemoFailure`, `_base` and `HERE` from `assurance_demo` (no change to that file) and nothing from `assurance`, `lifecycle` or `ledger`, so the oracle cannot share code with the mechanism it measures. Public API: `run(base=None, hook=None, only=None, out=None, err=None) -> int` and `measure(...) -> dict` (the data), `main(argv)` with `--json`. `hook(scripts_dir: Path)` edits the copied scripts after the copy and before the scenario's fixture commit (R8). `only` is a tuple of scenario names used by tests for speed; the CLI runs all six.

**D-b. Scenario data.** Frozen dataclasses `Req(id, verify_flags, inputs, reads)` (`inputs=None` means whole tree; `reads` is the true-read file tuple), `Step(title, setup, change, affected, expect, after)`, `Scenario(name, reqs, steps)`. All files are tiny: `src/calc.py`, `src/lib.py`, `docs/guide.txt`, `config.ini`, `notes.txt`, plus a generated `checks/<req>.py` per requirement that reads exactly its `reads` (a missing file raises, so exit nonzero) and exits 3 if any read file contains `broken`. A scoped requirement declares `Inputs:` as its check script plus its declared files. Capability file `knowledge/capabilities/measure.md`, namespace `MEAS`, is generated from the scenario so the data is the single source.

| Scenario | Requirements (reads; declared Inputs) | Steps (change -> affected, expected caught/false_stale/missed) |
|---|---|---|
| feature | R1 calc (calc, lib; same), R2 docs (guide; same) | edit `src/calc.py` and add `src/feature.py` -> {R1}: 1/0/0 |
| requirement-change | R1, R2 as above | edit R1's `Verify:` to add `--strict` -> explicit {R1}: 1/0/0; `changed_missed` 1 |
| regression | R1, R2 | write `broken` into `src/calc.py` -> {R1}: 1/0/0, after rerun R1 FAILED |
| stale-evidence | R1, R2 | edit `notes.txt` -> {}: 0/0/0; then edit `docs/guide.txt` -> {R2}: 1/0/0 |
| dependency | R1 (calc, lib; same), R3 cfg (config, lib; check script and lib only) | edit `src/lib.py` -> {R1, R3}: 2/0/0; edit `config.ini` -> {R3}: 0/0/1 (undeclared dependency, `changed_missed` 1); setup adds whole-tree R4 (reads guide; no Inputs) and records it, then edit `notes.txt` -> {}: 0/1/0 |
| handoff | R1, R2 | setup records, commits and starts `tier L1 --new`; edit `src/calc.py` -> {R1}: 1/0/0, evidence record committed |

Affected for file-edit steps is computed by the harness as `{r.id for r in reqs if set(r.reads) & changed_files}` from the scenario data; a requirement-change step gives `affected` explicitly. The expected counts above are hand-written constants in the data, not computed.

**D-c. Step protocol.** Per scenario: build the repo (reuse `build` with the scenario's files via its `prepare` hook, plus the user hook), `assure --run` all declared requirements, commit (`git add -A`, `git commit`). Per step: optional setup (then rerun anything it adds and commit); apply the change; observe `assure --json` (flagged = status in STALE/FAILED/UNVERIFIED) and `assure --json --changed --base HEAD` (listed ids); compute the metrics of R3 (`baseline_reruns` = results whose status is not UNDECLARED, INVALID or MANUAL); rerun the flagged ids (`ok=(0, 1)`), observe again, and compare each flagged id's status with `after` (default VERIFIED); commit; compare counts with `expect`. Any mismatch is recorded as a failure line `scenario/step: metric expected X observed Y` and makes the exit code 1; the run continues so one report shows every difference.

**D-d. Report.** `measure()` returns `{schema_version: 1, scenarios: [{name, steps: [{title, affected, flagged, caught, false_stale, missed, changed_missed, reruns, baseline_reruns}]}], totals, contribution, failures}`. Lists are sorted id lists in JSON and counts in text. `contribution` = `reruns_avoided` (sum of baseline minus reruns), `whole_tree_false_stale` (false_stale ids whose requirement has `inputs=None`), `changed_listed` and `changed_missed` (sums), `handoff_from_record` (caught requirements in handoff steps whose `evidence.record` is tracked by `git ls-files`). Text: aligned rows, totals, a `contribution:` block, the closing sentence, then `FAIL` lines when present (the sentence is still last on success; on failure it is omitted, as `assurance_demo` omits its limit sentence). Nothing prints a path, time or hash.

**D-e. Failure and exit codes.** `DemoFailure` from a command (an unexpected exit, missing JSON) is exit 1 with `assurance_measure: <reason>` on stderr. `_base()` failing is exit 2 with one line. `finally` always removes the temp dir; the SIGTERM handler mirrors the demo.

**D-f. Documentation.** One sentence in `## Assurance status` next to the demo sentence, and the term `assurance_measure.py` added to `test_lifecycle_conformance.Assurance` (R9).

## Steps (test-first; each ends with a failing-closed check)

0. **Lifecycle setup.** Tier L2 declared, intent recorded (approved by `human:enramosjr`). Record `stage plan --ref docs/assurance/plan-7.md`. Check: `git status` clean; `git diff --stat -- .ai/scripts` empty.
1. **Red tests** in new `.ai/scripts/tests/test_assurance_measure.py`, with classes named in the Acceptance filters and docstrings citing R ids: `ScenarioTests` (R1: six names, statuses via `assure --json`, invoking repo snapshot unchanged), `OracleTests` (R2: affected equals true-reads intersection per step; a missing true-read file fails its check script; source of `assurance_measure.py` has no `import assurance`/`lifecycle`/`ledger`), `MetricTests` (R3: exact key set; hand-computed counts for one step per scenario, including `changed_missed` 1 for requirement-change and dependency S2), `RerunTests` (R4), `ExpectationTests` (R5: clean run exits 0; hook turning STALE into VERIFIED exits 1 naming `missed`; hook making every requirement STALE exits 1 naming `false_stale`), `ReportTests` (R6), `ReportOnlyTests` (R7), `CleanupTests` (R8: success, forced failure, SIGTERM via subprocess with `TMPDIR` set, non-disk-backed base exits 2). A class-level cached full `measure()` run feeds the read-only classes so the suite runs the six scenarios a bounded number of times. Check: `lifecycle.py redgreen red -- python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py` fails with an import error; `test_assurance_demo.py` passes as baseline.
2. **Scenario data and oracle** (R1, R2): dataclasses, fixture and check-script generation, `affected()` helper. Check: `-k OracleTests` green.
3. **Harness** (R1, R3, R4, R8): build via `assurance_demo`, step protocol of D-c, metrics, cleanup, hook and `only`. Check: `-k ScenarioTests`, `-k MetricTests`, `-k RerunTests` green.
4. **Expectations and report** (R5, R6, R8): constants checked, failure lines, text and JSON, `main` with `--json`, exit codes. Check: `-k ExpectationTests`, `-k ReportTests`, `-k CleanupTests` green.
5. **Documentation** (R9): the `.ai/lifecycle.md` sentence and conformance term. Check: `test_lifecycle_conformance.py -k Assurance` passes.
6. **Mutation proof** (AGENTS.md §8.6). Scratchpad `mutate.py` (as in increment 4): copy `.ai/scripts` to a scratch dir, apply one replacement with an exact-count check, run the class there; each must make its class fail and the unmutated tree must pass.

   | Class | Broken variant |
   |---|---|
   | OracleTests | derive `affected` from `inputs`; drop the missing-file raise in a check script |
   | MetricTests | swap `caught` and `false_stale`; count VERIFIED as flagged; `baseline_reruns` counts only scoped requirements; `changed_missed` taken against `flagged` |
   | RerunTests | skip the rerun; skip the post-rerun status comparison |
   | ExpectationTests | always exit 0; compare only `missed`; mechanism hooks as in R5 |
   | ReportTests | drop the closing sentence; add a timestamp; `schema_version` 2; `reruns_avoided` off by one |
   | ScenarioTests | run five scenarios; write a file into the invoking repo |
   | CleanupTests | skip `rmtree`; drop the SIGTERM handler; return 1 instead of 2 for a bad base |
   | ReportOnlyTests | none needed beyond the unchanged-files assertions: check the assertion by editing `assurance.py` in the scratch copy |

7. **Validate and verify.** Retrospective (`lifecycle.py learn` / `retrospect`), independent review with the `reviewer` subagent (save its report untracked as `docs/assurance/review-7.md`), `stage review --ref`, `lifecycle.py converge docs/assurance/specification-7.md`, the full suite through `lifecycle.py run`, `python3 .ai/scripts/assurance_measure.py` once on the final tree, then `stage verify`. Then ask the user before committing.

## Requirement map

| Req | Steps | Check that fails closed |
|---|---|---|
| R1 | 1, 3 | `-k ScenarioTests` |
| R2 | 1, 2 | `-k OracleTests` |
| R3 | 1, 3 | `-k MetricTests` |
| R4 | 1, 3 | `-k RerunTests` |
| R5 | 1, 4 | `-k ExpectationTests` (real mechanism hooks) |
| R6 | 1, 4 | `-k ReportTests` |
| R7 | 1, 7 | `-k ReportOnlyTests`; `test_assurance.py` and `test_assurance_attested.py` unmodified |
| R8 | 1, 3, 4 | `-k CleanupTests` |
| R9 | 5 | `test_lifecycle_conformance.py -k Assurance` |

## Validation commands

Run each through `lifecycle.py run LABEL -- CMD`, with `lifecycle.py reuse` before repeating.

- Focused loop: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_measure.py -k <Class>` for each class; `... -p test_assurance_demo.py`; `... -p test_assurance.py`.
- Once, when edits are complete: `... -p test_assurance_attested.py`; `... -p test_lifecycle_conformance.py`; `python3 .ai/scripts/run_tests.py`; `python3 .ai/scripts/assurance_measure.py`; `python3 .ai/scripts/assurance_demo.py`.
- Then `lifecycle.py stage verify`. `lifecycle_eval.py run` is not required: no tier or stage rule changes.

## Risks

- Runtime: six repositories with about ten commands each; mitigated by one cached run per test class group and the `only` parameter. If the full run exceeds about a minute, report it rather than trimming scenarios silently.
- Circular oracle: avoided by the true-reads map and the no-import assertion; the expected counts are hand-written constants.
- Whole-tree timing: tree hash includes untracked files; every step commits after rerun so the next step's `--changed --base HEAD` sees only its own edit. A leftover untracked file would show as a false STALE; `OracleTests` asserts a clean tree between steps.
- `changed_missed` for requirement edits is a finding, not a defect of the harness; it is reported, not asserted as failure in R5 (which names only caught, false_stale and missed).
- Importing the demo's private `_base`: acceptable inside one package of scripts; the demo's tests keep guarding its behavior.

## Decisions

None open. The user settled D1-D5 of the handoff on 2026-10-28 (new script; independent hand-written oracle; rerun-everything baseline; report-only pruning; no real-usage scan).
