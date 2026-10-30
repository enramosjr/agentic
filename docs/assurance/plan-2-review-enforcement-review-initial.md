# Review Report

## Verdict

Changes requested — two implementation-readiness blockers remain.

## Scope

Read-only review of proposed `plan-2-review-enforcement.md` against approved supplement R1–R8 and the relevant lifecycle, OKF, completion, producer, hook-registration, and native-capability evidence. No implementation review or stage recording performed.

## Persona Applied

Python principal engineer: lock ownership, subprocess boundaries, provenance, and failure-closed artifact handling.

## Findings

- **High — report export can invalidate its own reviewed candidate.** Plan lines 49–51 exclude generated lifecycle receipts and the reserved report path, but include other Markdown. A report exported inside `knowledge/` requires frontmatter and index/log bookkeeping; `okf.py:2390–2413` creates the document and reindexes. Those administrative changes would alter the reviewed pins, while omitting them would fail adopter validation. Choose an explicit protocol before implementation: prepare administration before capture, apply a narrowly checked administrative delta afterward, or restrict supported destinations appropriately. Do not blanket-exclude knowledge indexes/logs. Add an adopter export → valid OKF records → Review → Verify test, alongside rejection of unrelated knowledge changes.

- **High — the proposed lock order does not resolve existing nested producer paths.** Plan lines 63 and 75 require guard-before-state ordering and guards at producer functions, but `lifecycle.py:1881–1883` already holds `state_lock` around handlers. Those handlers can invoke child OKF producers (`save`, lines 260–263; `completion.py:158–178`) or call another stage directly. Same-process lease reuse alone does not define these cross-process cases. Specify lease ownership/release and transaction boundaries for these paths, including how native callbacks and recovery avoid waiting for state while a live producer awaits the guard. Add barrier tests covering nested child producers, native events, and recovery; the outcome must be refusal or completion without deadlock or accidental lease release.

## Validation Reviewed

Read the approved supplement, proposed plan, installed Codex capability report, hook configurations, and relevant implementation paths. The reported trace covers eight requirements; it does not resolve the design gaps above.

Ran `okf.py affected` for proposed paths: no framework knowledge bundle exists, so bundle synchronization is inapplicable rather than PASS. No tests, model calls, source edits, or broad gates were run.

## Residual Risks

Trusted native activation and actual report delivery for both adapters remain required verification prerequisites. Codex schema/discovery with `trustStatus: untrusted` is correctly distinguished from working capture and must remain insufficient for qualification.

Prior failed evaluations remain failed. This review grants no implementation, external-execution, or delivery authorization.
