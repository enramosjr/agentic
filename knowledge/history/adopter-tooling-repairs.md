---
type: Historical Record
title: Portable adopter repair verification
description: Upstream-local provenance and validation for the targeted fixes.
tags: [tooling, validation]
status: stable
evidence: implementation-and-current-specifications
generated: { by: agent/unknown, at: 2026-10-19T22:09:10Z }
sources:
  - id: ai-readme-md
    resource: ../../.ai/README.md
  - id: ai-docs
    resource: ../../.ai/docs
  - id: ai-scripts-install-py
    resource: ../../.ai/scripts/install.py
  - id: ai-scripts-run-tests-py
    resource: ../../.ai/scripts/run_tests.py
  - id: ai-scripts-lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
  - id: ai-scripts-tests-test-install-py
    resource: ../../.ai/scripts/tests/test_install.py
  - id: ai-scripts-tests-test-lifecycle-conformance-py
    resource: ../../.ai/scripts/tests/test_lifecycle_conformance.py
  - id: ai-scripts-tests-test-learning-loop-py
    resource: ../../.ai/scripts/tests/test_learning_loop.py
  - id: ai-scripts-tests-test-brownfield-deltas-py
    resource: ../../.ai/scripts/tests/test_brownfield_deltas.py
  - id: ai-scripts-tests-test-run-tests-py
    resource: ../../.ai/scripts/tests/test_run_tests.py
  - id: ai-scripts-tests-test-ledger-py
    resource: ../../.ai/scripts/tests/test_ledger.py
  - id: ai-lifecycle-md
    resource: ../../.ai/lifecycle.md
  - id: agents-md
    resource: ../../AGENTS.md
  - id: readme-md
    resource: ../../README.md
verified: { by: "process:python3 .ai/scripts/lifecycle.py audit", at: 2026-10-19T22:10:17Z }
---

# Portable adopter repair verification

## Scope and provenance

This is a targeted fixes-only change on AGENTIC base 16d9d99. The user authorized
porting the documented portable repairs and opening an upstream PR, then explicitly
confirmed no repository replacement. Only the 13 repair paths are ported, with
bounded lifecycle evidence protection and relevant upstream usage references.
No Athenaeum application, manifest, overlay receipt, private history or session
artifact is included. Upstream's knowledge ignore rule is unchanged.

The installer normalizes source governance before export/hash, rejects malformed
source markers before writes and preserves target-only instructions. Portable
references travel inside .ai/ and their tests execute in an adopter with unrelated
README/private knowledge. Only nonnormative AGENTS introduction prose is shortened;
the 30,000-byte test and normative rules remain intact. The runner propagates
its no-bytecode policy to worker descendants.

Lifecycle run descendants inherit a stack of resolved repository owners. Dispatch
refuses state-mutating CLI operations in owned ancestor repositories before their
bodies execute. Read-only commands, merge previews and independent repositories
remain usable; independent runs retain ancestor ownership. Parent failure entries
do not erase prior convergence or ledger entries. Invalid owner metadata fails
closed. This guard is operational, not a security sandbox or generic state merge.

## Failing-first evidence

The ported installed-template, installed-documentation and runner regressions
ran against the original upstream implementation: RED, two failures and one error
across three tests. Porting the bounded implementations/references made the same
command GREEN. The nested lifecycle/independent-owner/metadata tests then ran RED
against the original lifecycle code (ten subtest failures), and GREEN after the
guard. The parser's redgreen command-list argument was accounted for by selecting
the dispatched command function's name. No assertions or skips were weakened.

## Verification and delivery

The affected installer, conformance, learning, brownfield, runner and ledger
focused suites passed through lifecycle.py run focused-repairs. Direct
`python3 .ai/scripts/lifecycle.py converge knowledge/specifications/adopter-tooling-repairs.md`
then executed the complete 548-test source suite: R6 PASS; R1-R5/R7 MANUAL;
1 PASS, 0 FAIL, 6 MANUAL. Both upstream-history commits used by the governance
preservation checks are available in this full clone. No source changed during
the gate. Installed-adopter documentation, export/check and refusal E2E paths
are exercised by that suite. OKF affected maps every repair path, and sync-check,
records and git diff --check pass.

Task-specific upstream-local OKF/audit records are the only ignored files to be
explicitly staged. The ignore rule remains unchanged. No adopter corpus,
installation manifest, application source or private history is imported.
Independent review and publication readiness are retained in the
[review](adopter-tooling-review.md). Publication is explicitly authorized; root
will confirm the resulting local commit, clean tree, pushed branch and PR URL.
