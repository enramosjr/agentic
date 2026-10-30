# Review Report

## Verdict

Changes requested — confirm restored bytes in the nested dependency and broken-control fixtures.

## Scope

Reviewed the three-file working-tree diff against approved specification-5m.md and plan-5m.md, including the literal profile, source/setup oracle, fourteen assertion-failure cases, six broken controls, framework/adopter freshness checks, predecessor preservation and guide claims.

Pass 1 identified the bounded compliance gap below. Pass 2 approval is pending its correction and delta review.

## Persona Applied

Python principal engineer. Import-time construction, independent test counts, mutation isolation and cleanup behavior informed the review.

## Findings

### [Medium] Confirm restoration before deleting nested fixtures

**Location:** `.ai/scripts/tests/test_assurance_inputs.py:5649` and `:5913`.

**Issue** — Both mutation families register `case.addCleanup(path.write_bytes, original)`, then dispose of the fixture without reading back the restored bytes. Restoration is performed but not confirmed. Specification R2 acceptance requires confirmation of bytes/restoration, and R6 explicitly requires every broken control to confirm restoration.

**Impact** — The passing nested tests do not establish the approved restoration criterion for the fourteen dependency challenges and six broken controls.

**Recommendation** — At both sites, register a cleanup callback that writes the original bytes and asserts that `path.read_bytes()` equals them before temporary-directory cleanup.

## Validation Reviewed

- Read `converge-5m.log`: R1–R6 PASS; **6 PASS, 0 FAIL, 0 MANUAL**. No MANUAL requirements require adjudication. Did not rerun convergence or unchanged product checks.
- Inspected count-first execution checks, fourteen scoped assertion mutations, six control mutations and fourteen absent-data/supplied-one-pass dependency challenges.
- Inspected preservation of the twelve predecessor entries and the two exact-total updates, retaining the original ten- and eleven-entry baselines.
- Ran `git diff --check`: exit 0.
- Ran `lifecycle.py status`: Intent and Plan complete; Review and Verify pending.
- Ran `okf.py affected` for the three changed paths: exit 1 because this framework has no knowledge bundle. Synchronization is inapplicable; no records PASS is claimed.
- Reviewed the recorded no-new-lessons retrospective and its acceptance evidence.
- Full framework gate remains pending correction and independent approval, as planned.

## Residual Risks

Declared file scope does not establish semantic-lens effectiveness or cover runtime environment, temporary storage, ignored files or external mutable data. The guide states these limits.
