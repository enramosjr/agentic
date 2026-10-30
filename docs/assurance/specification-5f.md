# Spec: static validation-policy documentation input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “Approved. Proceed with the implementation plan for 5f using the recommended D1–D4 decisions.” L2; analyst role; Python principal engineer. Acceptance commands name future checks, not execution results. Human specification approval authorizes planning only; a separately approved plan is required before implementation.

## Problem and outcome

Maintainers have five delivered literal Python input profiles but no profile for the existing method-selected validation-policy documentation check. Add one explicitly adopted profile through the existing exporter, with reviewed repository inputs and controlled freshness evidence. Framework mode has no knowledge bundle or structured capability baseline; this standalone specification creates neither and revises no historical evidence.

## Users and scenarios

A maintainer invokes the exporter from the repository root for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Relocation.test_agents_md_points_to_the_policy_and_the_policy_keeps_its_must_rules
```

Proposed ID: `python-validation-policy-contract`. The method reads `AGENTS.md` and `.ai/validation-policy.md`. It requires `.ai/validation-policy.md` and `MUST load it by section` in AGENTS, then requires each of these strings in the policy and absent from AGENTS:

1. `MUST NOT rerun an unchanged failing check`
2. `` `--max` below 300 s is a violation ``
3. `MUST be split before work continues`
4. `MUST NOT satisfy §8.1 by adding tests whose only purpose is more evidence`

These are literal, case-sensitive text assertions. They do not execute extracted commands or prove that the rules are followed. Exactly one actual passing test is a future acceptance expectation, not a result inferred from method selection.

Approved ordered scope:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
AGENTS.md
.ai/validation-policy.md
```

The first pattern conservatively covers production eager imports and lazy-loader/decorator setup, including unused non-test descendants and future supported scripts. Extra invalidation is deliberate; this method copies no scripts. Ordered exclusion restores only the selected test module and imported helper. The final two literals are direct text reads. Root AGENTS is explicit despite general Markdown freshness exemptions. Unselected methods, classes and module-wide execution are outside this exact-method claim.

## Requirements

- R1: The exporter MUST register only the exact repository-root argv above as `python-validation-policy-contract`. Class/module, sibling, discovery, option, alias and other-interpreter variants MUST remain unregistered unless already registered. All five delivered profiles MUST retain their IDs, argv, ordered inputs, rationales and behavior.
- R2: The profile MUST export exactly the six ordered patterns above before positive supplements, with per-pattern rationales distinguishing conservative import/setup scope, test exclusion/restoration and direct text reads. An independent source-derived oracle MUST cover the selected method, direct reads, called text helper, eager initialization, called require_disk, lazy setup and protected/decorate construction. It MUST require review on boundary drift and reject confirmed reachable excluded additions. Unrelated tests/documents MUST remain excluded. Conservative pins MUST NOT imply universal read discovery, script copying or reachability of uncalled wrapped producer bodies.
- R3: Public text/JSON export MUST preserve existing token/Inputs/rationale parity, supplement order, root/path/inventory validation, nonexecution and refusal behavior. Export MUST neither import/execute the selected test nor validate document assertions, adopt Inputs or record evidence. Missing required literals and unsafe/unsupported paths or unknown commands MUST refuse nonzero with a reason and no usable candidate. Existing documents with failing assertions MUST remain exportable through path-only validation.
- R4: Adoption MUST remain explicit, advisory and manual. Existing inference, full suites, matching, freshness, schemas, gates and producer receipt exclusions MUST remain unchanged. The guide MUST name the exact command/ID, literal text-placement claim, conservative invalidation and runtime/read-completeness limits. It MUST NOT claim actual reuse/wait/batch enforcement, native hooks, agent/model behavior, dynamic governance, session qualification or VERIFIED evidence from export.
- R5: An isolated framework fixture MUST drive public export and real lifecycle run/reuse. Independent captured unittest output MUST prove exactly one test executed and passed before exit interpretation; subtests MUST NOT count as separate tests. Recorded argv, ordered inputs and exit MUST match export; selected repository bytes MUST remain unchanged during execution. Evidence MUST REUSE unchanged and after unrelated-test/non-input-document edits; it MUST RERUN after separate assertion-preserving edits to each direct document, target, disk helper, representative production import and new supported non-test script. Edits MUST restore original bytes. The invoking framework MUST acquire no knowledge bundle. Ten separate static-failure fixtures MUST make the actual command fail while export succeeds: remove either required AGENTS token, remove each of four policy strings, and insert each forbidden string into AGENTS. Each removal MUST remove every occurrence of that token in its respective file, confirm changed bytes and establish the intended assertion failure.
- R6: A separate ordinary adopter fixture MUST explicitly adopt public export, become VERIFIED after independently proven actual one-test execution, remain VERIFIED after unrelated-test/non-input-document edits, and become STALE after each direct-document, target/helper, representative production import and new supported non-test script edit. Unmatched ordered declarations and argv identity MUST yield UNVERIFIED under existing rules; receipt exclusion MUST remain effective. Four confirmed disposable broken controls MUST be rejected: omission of AGENTS, omission of policy, loose command matching and acceptance of actual zero-test execution. Each omission MUST fail its intended freshness assertion while assertion-preserving edits leave the selected check passing. The zero control MUST ignore the selector in an actual empty disposable suite, independently confirm Ran 0 tests, and reject count before version-dependent exit interpretation. A missing method yielding one loader failure is insufficient. Every control MUST confirm mutation bytes and its intended failure without altering historical evidence.

## Acceptance

Proposed classes below belong in `.ai/scripts/tests/test_assurance_inputs.py`; they do not yet exist. Missing classes, counts or end states fail acceptance. These commands MUST NOT execute during initial drafting. Boundary guards are conservative review guards, not general dependency discovery.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py ValidationPolicyProfileTests` checks exact ID/argv/root matching, variant refusal and unchanged IDs/argv/ordered inputs/rationales of all five prior profiles.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py ValidationPolicyDependencyTests` checks ordered scope/rationales, independent actual ledger selection, direct-read/import/called-body boundaries, unrelated exclusions and future supported non-test descendants. Each reachable mutation MUST first fail actual selected execution with its excluded data absent, then pass exactly one test with that data supplied, before intended dependency-review rejection. Cover selected method, text helper, imported excluded helper and justified eager/called setup paths; derive the final variants from source rather than copying 5e's count. Confirm bytes; insert AST body changes after docstrings and before the earliest decorator of the first statement. Uncalled bodies may be pinned conservatively but MUST NOT be described as reached.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py ValidationPolicyExportTests` checks public formats, supplements, immutability/nonexecution, every missing required literal and unsafe boundary, and path-only export of existing documents that fail selected assertions.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py ValidationPolicyCompatibilityTests` checks guide claim/limitations and preservation of five profiles, inference/full suites, matching, schemas, gates and receipts through existing mechanisms.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py ValidationPolicyFrameworkEndToEndTests ValidationPolicyFailureTests` checks independent actual one-test proof, byte stability, identities and each framework freshness outcome, separately from ten confirmed static assertion failures.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py ValidationPolicyAdopterEndToEndTests ValidationPolicyControlTests` checks every adopter state/identity and receipt exclusion plus four confirmed broken controls, including both direct-document omissions and independent actual-zero rejection.

## Constraints

Use the existing literal catalog/export mechanism, Python 3.9+, standard library and unittest conventions. No new options, schemas, normalization, loader, inference, adoption automation, gates or approval authority. Inventory follows existing tracked/supported nonignored-untracked ledger rules. Executable/runtime environment, temporary storage/mount state, ignored files and external mutable data remain outside repository-file claims. Unresolved additional reads require review and retention of current scope.

Use only `/home/enramosjr/Projects/agentic-assurance-7`, branch `claude/assurance-increment-7`, delivered HEAD `4b89221b6f1c416303452abd57fb4fb15816b2b3`. Keep docs/assurance artifacts ignored/local/uncommitted. Preserve all 5e and earlier records and original source/runtime scopes; historical results verify no sixth profile. During drafting: no source edits, product tests, implementation plan, native/model evaluations, session registration/allocation, fixture trust grants, historical rescoring/evidence modification, new worktree, base refresh, knowledge bundle, commit/push/PR/merge or autonomy driver. Prior delivery authorization is fulfilled.

## Non-goals

Class/module/sibling registration; changing selected assertions or governance contracts; actual policy compliance/enforcement; executing extracted commands; native/model/session qualification; general read discovery; minimum input set; reduced full gates; automatic adoption; savings claims; planning before spec approval.

## Assumptions

D1-D4 below are approved decisions. Static inspection establishes candidate scope only. Controlled future fixture evidence cannot establish universal dependency completeness or runtime portability. Framework mode has no capability baseline to merge or bundle to initialize. Historical PASS/REUSE is no sixth-profile verification.

## Open questions

None. The user approved the specification and recommended D1-D4. Ready for planning only.

## Approved decisions

The recommended defaults below are approved; alternatives remain as decision context.

- D1: Approve the exact method and ID above, select another candidate or stop expansion? Recommended: approve this candidate only; registration scope is a human contract choice.
- D2: Approve six ordered patterns with conservative extra production invalidation, or require a smaller independently justified closure? Recommended: six with stated limits, explicitly including root AGENTS.
- D3: Approve R2/R5/R6's source-derived boundary controls, independent actual one-test proof, framework/adopter freshness/identity matrix, ten static failures and four omission/matching/count controls? Recommended: yes. Future evidence remains bounded to repository freshness and literal assertions.
- D4: Approve explicit advisory/manual adoption, preservation of all five profiles and existing inference/suites/schemas/gates, and static text-placement claims only? Recommended: yes.

## Investigation evidence

Nonexecuting inspection only:

- `test_lifecycle_conformance.py:15-27,134-146`: root/import setup, called text helper, two direct reads, exact assertions. Other methods inspect broader files and execute commands; those paths are not inherited.
- `disk_tmp.py:10-20`, `scratch.py:11-26`: eager disk helper and called storage/mount validation; possible environment/cache mutation is outside repository-file scope.
- `lifecycle.py:41-66,1011,1209,1321,1994-1995`, `review_guard.py:23-26,629-639`, `ledger.py:10-22`: eager imports/initialization, lazy setup and protected/decorate construction. The selected method accesses no lifecycle attributes and calls no wrapped producers.
- `assurance_inputs.py:17-105,128-214,222-250`: five literal entries, exact argv match, path-only validation and advisory formats/limits.
- `test_assurance_inputs.py:1585-1690`: prior fixed setup/method pins and reachable mutation mechanism inspected as reference only, not new-profile evidence.
- `.ai/validation-policy.md:11,15,28,33` contains the four strings; `AGENTS.md:234` has the policy reference/loading instruction. No extracted command executed.
- `handoff-5f.md` and leading `implementation-5e.md` preserve delivery scope. Local context confirms framework mode, expected branch/HEAD and clean tracked status, without remote verification. New L2 declared after context loading; no stage approval recorded.

## Draft validation

- `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5f.md` -> exit 1, only High open-questions finding for D1-D4. These intentional approval blockers remain unresolved; no other finding reported.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5f.md` -> exit 0, six requirements traced. This is structural evidence only.
- `git check-ignore docs/assurance/specification-5f.md` -> exit 0, ignored path confirmed. Final context -> expected branch/HEAD and clean tracked status, using local refs only.
- Read-only analyst subagent independently confirmed the two-read boundary, eager/called/lazy/protected setup, six-pattern conservative scope, ten static failures and four omission/matching/count controls. Python persona considerations affecting the draft were import-time effects, called-helper closure and independent actual test-count proof. No product tests, source edits or implementation plan occurred.
