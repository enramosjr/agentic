---
type: Historical Record
title: Unified project bootstrap delivery
description: Implementation and executed validation evidence for project-local bootstrap.
tags: []
status: stable
evidence: validated-runtime
generated: { by: agent/gpt-6, at: 2026-10-19T19:26:24Z }
sources:
  - id: ai-scripts-install-py
    resource: ../../.ai/scripts/install.py
  - id: ai-scripts-tests-test-install-py
    resource: ../../.ai/scripts/tests/test_install.py
  - id: readme-md
    resource: ../../README.md
verified: { by: "process:python3 .ai/scripts/lifecycle.py reuse framework-regression", at: 2026-10-19T19:43:08Z }
---

# Unified project bootstrap delivery

## Change

The existing installer now classifies targets before writes, bootstraps missing/non-Git folders after validation, and retains existing Git-project protections. The README documents one project-local invocation. New real-CLI tests cover missing parents, populated directories, preserved settings/knowledge, conflicts, read-only checks, global isolation, repeatability, installed records, hook denial, and unsafe targets.

## Execution evidence

- Original installer baseline: `TMPDIR="$PWD/.git/okf-test-tmp" python3 -m unittest discover -s .ai/scripts/tests -p test_install.py` → PASS (36 tests).
- New tests against the original installer: `python3 .ai/scripts/lifecycle.py redgreen red -- python3 -m unittest discover -s .ai/scripts/tests -p test_install.py -k Bootstrap` → recorded failure; new/non-Git targets were rejected by the existing Git-root prerequisite and the canonical README command was absent.
- After implementation and fixture isolation: `TMPDIR="$PWD/.git/okf-test-tmp" python3 .ai/scripts/lifecycle.py redgreen green -- python3 -m unittest discover -s .ai/scripts/tests -p test_install.py -k Bootstrap` → PASS, recorded green.
- `python3 .ai/scripts/install.py --help` → PASS, describes existing/new targets and read-only checks.
- `python3 .ai/scripts/lifecycle.py scan-diff` → PASS (0 findings) on the initial candidate.
- Current-base `python3 .ai/scripts/lifecycle.py run bootstrap-slice -- python3 -m unittest discover -s .ai/scripts/tests -p test_install.py` → PASS (exit 0). This includes the original regressions and new bootstrap tests, including bare/invalid metadata refusal.
- `python3 .ai/scripts/lifecycle.py converge knowledge/specifications/project-bootstrap.md` → R1 PASS, R2 PASS, R3 PASS, R4 PASS, R5 PASS, R6 PASS; 6 PASS, 0 FAIL, 0 MANUAL.
- `python3 .ai/scripts/lifecycle.py trace knowledge/specifications/project-bootstrap.md --plan knowledge/specifications/project-bootstrap-plan.md --tests .ai/scripts/tests/test_install.py` → PASS (6 requirements traced).
- `python3 .ai/scripts/lifecycle.py audit` → PASS (approved artifact bodies unchanged).
- `python3 .ai/scripts/lifecycle.py run syntax --inputs .ai/scripts/install.py .ai/scripts/tests/test_install.py -- python3 -m py_compile .ai/scripts/install.py .ai/scripts/tests/test_install.py` → PASS (exit 0).
- `python3 .ai/scripts/okf.py records` and `python3 .ai/scripts/okf.py sync-check --base 9e13fce` → PASS after documentation synchronization.

The source branch was updated from 9e13fce to current origin/main 4ad1a0d before final qualification. This brought in upstream evidence-ledger, stub scanning, and synchronization checks; those are base changes, not bootstrap behavior. Final qualification evidence is appended after execution.

## Full-gate diagnosis and documentation repair

The first `lifecycle.py run framework-regression` executed all 528 tests and failed with five documentation errors and one fixture synchronization failure. Existing tests expected absent framework knowledge (learning guides, lifecycle guide, installation playbook, baseline approval note) and a README Quick start section. The learning verification fixture generated an undocumented bytecode cache. These were present in the current base's test/documentation relationship; the bootstrap runtime tests passed.

Restored those source-cited documentation views without establishing an unapproved structured capability baseline. The installation playbook now uses the existing `install-and-upgrade.md` path. Renamed the canonical README section Quick start and adjusted only the matching bootstrap documentation test selector. Added `PYTHONDONTWRITEBYTECODE=1` to documented framework validation, preventing fixture artifacts without ignoring code or weakening tests. The installer runtime logic did not change after its first approved review.

Focused diagnosis and repair evidence (all commands used repository-local TMPDIR):

- `python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle.py` → PASS, 59 tests.
- `python3 -m unittest discover -s .ai/scripts/tests -p test_ledger.py` → PASS, 14 tests.
- `python3 -m unittest discover -s .ai/scripts/tests -p test_learning_loop.py` → reproduced missing guide and bytecode sync failure.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .ai/scripts/tests -p test_learning_loop.py -k test_verify_reminder` → PASS, establishing the environment cause.
- After restoration, `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .ai/scripts/tests -p test_learning_loop.py` → PASS, 20 tests.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle_conformance.py` → PASS, 18 tests.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .ai/scripts/tests -p test_brownfield_deltas.py -k DocumentationTests` → PASS, 2 tests.

This documentation repair was required to pass the repository's existing completion gate. It adds no application or installer behavior beyond the approved bootstrap scope. Original red/green and review evidence remains recorded; final acceptance and review are refreshed for the corrected documentation candidate.

## Final qualification

- Corrected-candidate `PYTHONDONTWRITEBYTECODE=1 python3 .ai/scripts/lifecycle.py converge knowledge/specifications/project-bootstrap.md` → PASS: R1–R6; 6 PASS, 0 FAIL, 0 MANUAL.
- Independent review and incremental documentation review → Approved, no findings. See [the review report](project-bootstrap-review.md).
- `PYTHONDONTWRITEBYTECODE=1 python3 .ai/scripts/lifecycle.py run framework-regression --inputs ".ai/**" README.md AGENTS.md CLAUDE.md ".claude/**" ".codex/**" ".cursor/**" ".agents/**" THIRD_PARTY_NOTICES.md knowledge/playbooks/install-and-upgrade.md knowledge/project/lifecycle.md knowledge/project/aidlc-roadmap.md knowledge/capabilities/learning-loop.md knowledge/playbooks/learning-loop.md -- python3 -m unittest discover -s .ai/scripts/tests` → PASS (exit 0), full 528-test suite on the corrected candidate (tree 8037016, base 4ad1a0d).

The full gate supplies disk-backed scratch through lifecycle.py. Bytecode generation is disabled to keep fixture caches out of fixture synchronization. No product code, test assertions, or test selection was weakened to obtain this pass. Final documentation metadata and lifecycle verification are recorded after this result; they do not alter the tested installer, tests, README, or conformance-document inputs.

## Delivery state

Implementation is reviewed and qualified on `codex/project-bootstrap`. The user authorized committing the verified candidate and opening a pull request. The delivery commit and pull request are reported in the accompanying chat; no merge into the default branch is authorized.

## Fixture notes

Workflow fixtures use repository-local disk scratch because lifecycle scratch rejects system temporary storage. Bootstrap fixtures set a Git discovery ceiling at their scratch parent so new non-Git projects are independent of the enclosing repository's Git metadata. Existing/new nested-worktree refusal cases still discover the fixture's actual worktree. No production Git safeguards are disabled by tests.
