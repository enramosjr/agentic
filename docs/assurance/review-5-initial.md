# Review Report

## Verdict

Changes requested — one Medium input-validation defect remains in R4.

## Scope

Reviewed the uncommitted increment 5 slice in `/home/enramosjr/Projects/agentic-assurance-7`: new exporter, new acceptance tests and lifecycle-guide diff, against the approved specification and plan. Inspected convergence, implementation and confirmed mutation-control reports. The full framework gate remains pending as planned.

## Persona Applied

Python principal engineer. The material considerations were validation of file/inventory boundaries, import side effects and tests that assert actual execution rather than successful exit alone.

## Findings

### [Medium] Existing ignored supplemental files produce unusable scope suggestions

**Location:** [assurance_inputs.py:104](/home/enramosjr/Projects/agentic-assurance-7/.ai/scripts/assurance_inputs.py:104), particularly the required-file membership check at lines 110–113.

**Issue** — `check_paths` checks supported-inventory membership only for the catalog’s required literals. An explicitly supplied existing ignored file is accepted as a supplemental input even though `ledger.input_paths` excludes it. This is a known unsupported boundary that R4 requires the exporter to refuse.

Verified with:

```text
python3 .ai/scripts/assurance_inputs.py --json --extra-input docs/assurance/specification-5.md -- python3 -m unittest discover -s .ai/scripts/tests -p test_run_tests.py
```

The command exits 0 and emits a usable declaration and lifecycle-input array. `git check-ignore docs/assurance/specification-5.md` confirms that this existing file is ignored.

**Impact** — Adopting the suggestion does not make changes to that explicitly requested file invalidate evidence. The general ignored-file limitation does not replace R4’s refusal of this concrete, detectable unsupported input.

**Recommendation** — Validate existing literal supplements against the supported file inventory before emitting a candidate. Add a public-CLI regression for an existing ignored literal and reject other literal forms that cannot identify supported file inputs. This need not introduce general wildcard-read completeness analysis.

Pass 1 is therefore not clean. The completeness audit found no stubs, deferred critical behavior or empty-test acceptance; final Pass 2 approval awaits this bounded repair.

## Validation Reviewed

- Read `converge-5.log`: `lifecycle.py converge docs/assurance/specification-5.md` reported **7 PASS, 0 FAIL, 0 MANUAL**. No MANUAL requirements require adjudication. Convergence was not rerun.
- Read `mutations-5-final.json`: baseline passed; four applied controls were confirmed and rejected, including explicit zero-discovery count failure.
- Inspected the real framework/adopter fixture flows, handwritten four-file oracle, exact evidence assertions and read-only sentinels.
- Ran the read-only supplemental-input reproduction and `git check-ignore`; results are described above.
- Ran `lifecycle.py audit`: **PASS**.
- Ran `okf.py affected` for all three changed paths: no framework knowledge bundle, **INAPPLICABLE**, not PASS. The existing guide documents usage and limitations; no bundle initialization is appropriate.
- Retrospective closure and evidence-backed lesson 1 are reported in the implementation record.
- No source writes, evidence-producer runs, native/model evaluations or trust operations occurred during review. The full framework suite was not run; it awaits the repaired frozen candidate.

## Residual Risks

Profile completeness remains a reviewed declaration rather than automatic discovery. Runtime, temporary-storage and ignored/external-read limits remain explicit. The repaired candidate still requires focused re-review and the planned full framework gate before Verify.
