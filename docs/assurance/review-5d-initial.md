# Review Report

## Verdict

Changes requested — R2’s dependency-boundary drift check does not cover added import-time dependencies or reads.

## Scope

Working-tree changes to `.ai/scripts/assurance_inputs.py`, `.ai/scripts/tests/test_assurance_inputs.py` and `.ai/lifecycle.md`, against approved specification-5d.md and plan-5d.md. Pass 1 found the issue below; final quality approval remains pending its correction.

## Persona Applied

Python principal engineer. Import-time effects and the distinction between source coverage and runtime execution materially informed this finding.

## Findings

**High — Guard added import-time dependencies and repository reads.** In `.ai/scripts/tests/test_assurance_inputs.py:1112–1123`, the dependency oracle checks only that existing import/setup substrings remain present. The fixed hash at lines 1104–1108 protects the selected method body, not module initialization or imported-helper setup. Adding a top-level repository read or another imported test helper can preserve every sentinel and the method hash while introducing an input excluded by the profile. For example, an added module-level read of compatibility fixture data can execute successfully without entering the independent oracle. This leaves the approved R2 requirement to flag dependency-boundary drift unenforced. Add a reviewed boundary check covering module/helper initialization and demonstrate that a confirmed added dependency/read fails the dependency acceptance check for the intended reason.

## Validation Reviewed

- Read `converge-5d.log`: `python3 .ai/scripts/lifecycle.py converge docs/assurance/specification-5d.md` reported **6 PASS / 0 FAIL / 0 MANUAL**. No MANUAL requirement IDs exist. These results were reused without rerunning acceptance.
- Inspected all new acceptance classes, five document-failure cases, seven confirmed controls, public exporter behavior and selected-method source.
- Read implementation report’s registration/documentation RED/GREEN evidence and closed retrospective.
- Ran `python3 .ai/scripts/lifecycle.py audit` → PASS.
- Ran `okf.py affected` for the three changed paths → exit 1, no bundle. Framework-mode knowledge synchronization is inapplicable; lifecycle guide documentation is updated.
- Completeness audit identified the missing R2 assertion above. No stubs or deferred production behavior were found.
- No product tests, native operations or mutations were performed during review. The frozen full framework gate remains pending as planned.

## Residual Risks

Correcting the dependency assertion changes acceptance inputs; current convergence must be refreshed before re-review and Verify. Repository-file evidence remains limited to the declared static scope and does not establish actual review behavior or runtime dependency completeness.
