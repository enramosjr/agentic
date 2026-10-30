# Spec: assurance gate and delta convergence evidence

Approved by human:enramosjr, 2026-10-28. L2; Python principal engineer. All recommended policies approved in chat. Implementation requires an approved plan.

## Problem and outcome

L2/L3 Verify currently has no assurance gate. Delta convergence records task evidence without making matching evidence available to living capability requirements. Increment 2 adds the gate and exact-match evidence reuse proposed in architecture §6 (`git show 4031aab:docs/assurance/architecture.md`).

Increment 7 measured caught 7, false_stale 1, missed 1, changed_missed 2 and reruns 8 versus 19 on fixtures. These are mechanism counts, not a production false-positive rate. Its implementation, Approved review, retrospective and Verify remain intact; unchanged gates are not rerun.

## Users and scenarios

Maintainers and agents completing L2/L3 adopter tasks change inputs, edit requirement blocks, or add/modify/remove requirements through approved deltas. Verify identifies blocking obligations; users explicitly rerun them and retry. Framework development continues without a knowledge bundle.

## Requirements

- R1: L2/L3 `stage verify` MUST refuse touched current requirements with STALE, FAILED, UNVERIFIED or INVALID status, name each blocking ID/status and remediation, and record no Verify on refusal. It MUST NOT run obligation commands automatically.
- R2: Touched requirements MUST include current obligations whose inputs intersect changes from recorded task-start HEAD through the working tree, added/modified requirement blocks, and current IDs operated on by the approved delta. Selection MUST include staged, unstaged, untracked, deleted and renamed input paths and conservative whole-tree obligations. Removed IDs MUST not require verification after a valid completed delta merge.
- R3: The gate MUST refuse when the starting commit cannot resolve, changed paths cannot be determined, or capability/evidence diagnostics prevent evaluation. It MUST NOT substitute an empty selection, HEAD or HEAD^ silently.
- R4: VERIFIED, MANUAL and UNDECLARED MUST not block this gate. Accept-risk declarations and attested approvals MUST not waive a failing mechanical status or upgrade it to VERIFIED.
- R5: L0/L1 and repositories without a knowledge bundle or structured requirements MUST retain existing Verify behavior without creating a bundle. Existing Verify prerequisites MUST remain required.
- R6: Converge MUST publish `req:<stable-ID>` evidence for an approved delta add/modify only when executed acceptance argv exactly matches the rendered replacement block's valid mechanical Verify argv. It MUST use that obligation's exact evidence scope and existing freshness/integrity rules, preserve convergence results and `converge:<ID>` evidence, and run the command once.
- R7: Converge MUST NOT manufacture requirement evidence for removals, manual/undeclared/invalid obligations, different acceptance commands or whole-feature R-number specs. Failed, unlaunchable or input-changing executions MUST never yield passing fresh requirement evidence.
- R8: The lifecycle guide MUST describe the gate, task-start baseline, whole-tree cost, explicit rerun path, delta evidence conditions and remaining input-declaration/record-visibility limits. Existing assure status meanings, schema version 1, exits, risk semantics and changed-report behavior MUST remain compatible.

## Acceptance

The following test classes are proposed NEW classes in `.ai/scripts/tests/test_assurance_gate.py`. Tests exercise actual CLI paths in temporary Git repositories and assert exit outcomes and recorded state; they do not exist yet.

- R1: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_gate.py -k GateStatusTests` asserts each blocking status, refusal state, named remediation, and explicit rerun then successful Verify.
- R2: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_gate.py -k TouchedScopeTests` asserts task-start selection across later commits, requirement-only edits, delta operations, all specified path states, exclusions, unrelated scopes and whole-tree obligations.
- R3: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_gate.py -k GateFailureTests` asserts baseline/Git/parsing failures refuse without recording Verify or running obligations.
- R4: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_gate.py -k GatePolicyTests` asserts passing/nonblocking statuses and no active/expired risk or attestation bypass.
- R5: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_gate.py -k CompatibilityTests` asserts L1/framework/no-requirements behavior, no created bundle, and existing Verify prerequisites.
- R6: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_gate.py -k DeltaEvidenceTests` drives approved add/modify convergence and merge, asserts one execution, exact labels/argv/scopes and resulting VERIFIED status.
- R7: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_gate.py -k EvidenceBoundaryTests` asserts every excluded mapping, command failure, missing executable and inputs modified during execution cannot yield passing fresh requirement evidence.
- R8: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_gate.py -k DocumentationTests` asserts guide statements; the final framework gate also runs existing assurance and attestation compatibility tests.

## Constraints

Standard library only, Python 3.9+. Reuse assurance, ledger, delta model and Verify refusal path. No new stage, hook, daemon, store or automatic obligation execution. Preserve increment 7 changes and evidence. Working documents remain ignored under docs/assurance; no knowledge bundle, commit, push, PR or merge authorized. A full implementation plan follows spec approval.

## Non-goals

Increments 3/5, dependency inference, requirement-ID migration, risk waivers, second-precision ordering repair, pruning and production-rate claims. Do not change `assure --changed`; gate selection augments its input-path behavior.

## Assumptions

User-approved policy (2026-10-28): changed prose is selected but may reuse fresh passing mechanical evidence when Verify and Inputs are unchanged. Review judges whether the command still covers that prose; rerunning alone does not prove coverage.

## Open questions

None. The user approved the default L2/L3 gate; task-start HEAD with input, block and delta scope; fresh evidence reuse for prose-only edits; nonblocking MANUAL/UNDECLARED and informational Accept-risk; and exact-match delta convergence evidence, otherwise explicit assure --run.

## Investigation evidence

- `.ai/scripts/lifecycle.py:722` Verify path; `:617` stored task-start HEAD; `:1235` converge evidence labels; `:1257` delta merge prerequisite.
- `.ai/scripts/assurance.py:361` changed selector covers input paths, not requirement-block comparison; `:326` command/scope evidence matching.
- `.ai/scripts/brownfield.py:288` rendered delta replacement blocks.
- `.ai/scripts/tests/test_assurance_attested.py:637` risk acceptance does not change exit/summary.
- `docs/assurance/implementation-7.md`, `review-7.md`, `converge-7-final.log` and `framework-7.log`: preserved measurement verification at tree cb75486.
