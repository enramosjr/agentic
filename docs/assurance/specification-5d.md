# Spec: static reviewer-report contract input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “approved”, responding to the specification and recommended D1-D4 approval request. L2; analyst role; Python principal engineer. Approval authorizes planning only; implementation requires separate plan approval. Acceptance commands name future checks, not results. No product tests have run for this slice.

## Problem and outcome

Maintainers have three literal Python input profiles but no profile for the existing method-selected reviewer-report consistency check. Add one explicitly adopted profile through the existing exporter, with reviewed repository inputs and controlled freshness evidence. This framework has no knowledge bundle or structured capability baseline; this standalone specification creates neither and revises no historical evidence.

## Users and scenarios

A maintainer invokes the exporter from the repository root for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py RolesAndSkills.test_reviewer_completion_report_contract
```

Proposed ID: `python-reviewer-report-contract`. The method reads two role registrations, the canonical reviewer role, lifecycle review instructions and the review skill. It checks documented section-loading strings, canonical report headings/directions and preservation instructions. Regex and shlex process text; the method neither executes extracted commands nor structurally parses TOML. Exactly one actual test execution is a future acceptance expectation, not a result inferred from method selection.

Approved ordered scope:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.claude/agents/reviewer.md
.codex/agents/reviewer.toml
.ai/agents/reviewer.md
.ai/lifecycle.md
.claude/skills/review/SKILL.md
```

The first pattern conservatively covers production eager imports and lazy-loader setup, including unused non-test descendants and future supported scripts. Extra invalidation is deliberate; this method copies no scripts. Ordered exclusion then restores the selected test module and imported helper. Each of the five document literals is a direct read. Full RolesAndSkills has broader directory/symlink reads and executes extracted show commands; those paths are outside this selection.

## Requirements

- R1: The exporter MUST register only the exact repository-root argv above as `python-reviewer-report-contract`. Full class/module, other method, discovery, option, alias and other-interpreter variants MUST remain unregistered unless already registered. The three existing profiles MUST retain their IDs, argv, ordered inputs, rationales and behavior.
- R2: The profile MUST export exactly the nine ordered patterns above before positive supplements, with a rationale for each pattern distinguishing conservative import/setup scope, test exclusion/restoration and five direct document reads. An independent source-derived oracle MUST cover selected repository reads and eager-import/lazy-setup boundaries, exclude unrelated tests/documents and require review on dependency-boundary drift. It MUST NOT infer full-class coverage, directory copying, TOML parsing or command execution from this method.
- R3: Public text/JSON export MUST preserve existing token/Inputs/rationale parity, supplement order, root/path/inventory validation, nonexecution and refusal behavior. Export MUST neither import/execute the selected test nor semantically validate its document contents, adopt Inputs or record evidence. Each missing required literal and unsafe/unsupported path or unknown command MUST refuse nonzero with a reason and no usable candidate. Existing files with nonconforming report instructions remain the selected check's responsibility.
- R4: Adoption MUST remain explicit, advisory and manual. Existing inference, full-suite coverage/refusal, matching, freshness, report schemas, gates and producer receipt exclusions MUST remain unchanged. Guide documentation MUST name the exact command/ID, static instruction/contract consistency claim, conservative invalidation and runtime/read-completeness limits. It MUST NOT claim actual review quality, report production, model adherence, independent/native review execution, hook enforcement, session authentication or VERIFIED evidence from export.
- R5: An isolated framework fixture MUST drive public export and real lifecycle run/reuse for the selected command. Independent captured unittest output MUST prove exactly one test executed and passed before exit interpretation; subtests MUST NOT count as separate tests. Recorded argv, ordered inputs and exit MUST match export, and selected repository bytes MUST remain unchanged during execution. Evidence MUST REUSE unchanged and after unrelated test/non-input document edits; it MUST RERUN after separate conformance-preserving edits to each of the five direct documents, target, disk helper, a representative production import and a new supported non-test script. The invoking framework MUST acquire no knowledge bundle. Separate missing-section, altered-report-heading and lost-preservation-instruction fixture controls MUST make the actual selected command fail while path-only export still succeeds.
- R6: A separate ordinary adopter fixture MUST explicitly adopt public export, become VERIFIED after independently proven actual one-test execution, stay VERIFIED after unrelated test/document edits, and become STALE after each direct document, target/helper, representative production import and new supported non-test script edit. Unmatched ordered declarations and command identity MUST yield UNVERIFIED under existing rules; producer receipt exclusion MUST remain effective. Seven confirmed disposable broken variants MUST be rejected: omission of each of the five direct documents, loose command matching and acceptance of zero-test execution. Each omission MUST fail the intended freshness assertion while conformance-preserving document edits leave the selected static check passing. Every control MUST confirm mutation bytes and intended failure without altering historical evidence.

## Acceptance

Proposed test classes below belong in `.ai/scripts/tests/test_assurance_inputs.py`; they do not yet exist for this slice. Missing classes, absent counts or missing end states fail acceptance. Freshness edits must preserve the target's static assertions, separating staleness from intentional report-contract failures. Independent count assertions must reject zero discovery regardless of Python's exit convention.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportProfileTests` checks exact ID/argv/root matching, variant refusal and unchanged IDs/argv/ordered inputs/rationales of all three prior profiles.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportDependencyTests` checks exact ordered scope/rationale, independent import/direct-read coverage using real ledger selection, exclusion of unrelated tests/documents, future non-test descendants and source-boundary drift sentinels.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportExportTests` checks public text/JSON parity, supplements, immutability and nonexecution, refusal for every missing required literal/unsafe boundary and successful path-only export of nonconforming existing documents.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportCompatibilityTests` checks guide scope/limitations, prior-profile preservation, unchanged inference/full suites, matching and receipt behavior through existing mechanisms.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportFrameworkEndToEndTests ReviewerReportFailureTests` checks independent actual one-test proof, byte stability, lifecycle identities and all listed framework reuse/invalidation outcomes. Failure cases separately remove Completion report loading from each registration, alter a canonical report heading, and remove a required preservation phrase separately from lifecycle and review skill: five intended static failures, each with successful path-only export.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py ReviewerReportAdopterEndToEndTests ReviewerReportControlTests` checks all listed adopter statuses, identities/receipt exclusion and all seven confirmed broken variants. Omission controls cover both registrations, canonical role, lifecycle and skill, including TOML and Markdown; they fail on missed freshness while actual selected execution still passes.

## Constraints

Use the existing literal catalog/export mechanism, Python 3.9+, standard library and unittest conventions. No new options, schemas, normalization, loader, inference, adoption automation, gates or approval authority. Tracked plus supported nonignored untracked inventory follows existing ledger rules. Executable/runtime environment, temporary storage/mount state, ignored files and external mutable data remain outside the repository-file claim. Unresolved additional reads require review and retention of current scope.

Use only `/home/enramosjr/Projects/agentic-assurance-7`, existing branch `claude/assurance-increment-7`, delivered HEAD `652a77b811cb8ac0584940a990d6f266bb4acefd`. Keep all docs/assurance artifacts ignored, local and uncommitted. Preserve 5c's closed lifecycle/evidence and original source/runtime scopes; historical results verify no fourth profile. No source edits, product tests, native/model evaluations, session registration/allocation, fixture trust grant, historical rescoring, new worktree, base refresh, knowledge bundle, commit/push/PR/merge during drafting. Human spec approval authorizes planning only; implementation requires separate plan approval.

## Non-goals

Full class/module registration; other methods; changing reviewer/role/skill/hook contracts; actual report production or review quality; native/model/session qualification; structural TOML validation; read discovery; minimum input set; reduced full gates; automatic adoption; savings claims; implementation planning before spec approval.

## Assumptions

D1-D4 below are approved decisions. Static inspection establishes candidate scope only. Controlled future fixture evidence cannot establish universal dependency completeness or runtime portability. No historical PASS or REUSE is new-profile verification.

## Open questions

None. The user approved the specification and recommended D1-D4 decisions. Ready for planning only.

## Approved decisions

The recommended defaults below are approved; alternatives are retained as decision context.

- D1: Approve only the exact method argv and ID `python-reviewer-report-contract`? Recommended: yes. Registration breadth is a human contract choice; source cannot settle it.
- D2: Approve all nine ordered patterns and extra invalidation from conservative production-script scope? Recommended: yes; alternatively require a smaller independently justified closure. Completeness is reviewed, not automatically discovered.
- D3: Approve R5-R6's framework/adopter matrix, independent one-test proof, five static-failure cases and seven confirmed controls, including omission of every direct document? Recommended: yes. This is bounded repository freshness evidence, not native/model proof.
- D4: Approve explicit advisory/manual adoption with all three profiles, inference/full suites/schemas/gates preserved and static report-instruction consistency claims only? Recommended: yes.

## Investigation evidence

Non-executing inspection only:

- `test_lifecycle_conformance.py:15-27,68-131,297-298`: root/import setup, exact five reads, regex/shlex and text assertions, broader unselected class behaviors and direct unittest entry point.
- `.claude/agents/reviewer.md:11`, `.codex/agents/reviewer.toml:6`: documented show strings include Completion report. This method checks the first extracted command; it does not execute it or validate TOML structure.
- `.ai/agents/reviewer.md` Completion report; `.ai/lifecycle.md` Stage 3: Review; `.claude/skills/review/SKILL.md:10-14`: canonical headings/directions and complete-body preservation language inspected in full pertinent sections.
- `disk_tmp.py:10-20`, `scratch.py:11-25`: scratch import, temporary-storage probe, possible cache creation/environment changes and mountinfo reads; these ambient effects are outside repository-file scope.
- `lifecycle.py:41-66,1994-1995`, `review_guard.py:23-26,629-639`, `ledger.py:10-22`: eager scratch/review_guard/ledger imports and lazy module setup. The selected method accesses no lifecycle attributes. Lazy setup does not establish execution of every lazy module body; protected wrapper construction alone does not call a producer. No additional non-script repository read was found on this path through static inspection.
- `assurance_inputs.py:17-110,153-177,185-220`: three existing literal profiles, exact command selection, path-only validation, advisory formats and limitations. No test import or document semantic parser.
- `handoff-5d.md` and authoritative leading `implementation-5c.md`: preserved delivered state and restrictions. `repo.py context --json` confirmed framework mode, expected HEAD/branch and clean tracked state from local refs only; no remote refresh.

## Draft validation

- `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5d.md` -> exit 1, only High open-questions finding for D1-D4. These remain intentional approval blockers; no other finding reported.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5d.md` -> exit 0, six requirements traced. This checks draft structure, not implementation or runtime behavior.
- `git check-ignore docs/assurance/specification-5d.md` -> exit 0, ignored path confirmed. Final `repo.py context --json` -> clean tracked state, expected branch/HEAD, local refs equal with no remote verification.
- Read-only analyst subagent independently inspected scope and recommended the same six-requirement matrix and D1-D4 decisions, including all five document omissions. The user's subsequent approval is recorded above; no product test ran. Initial analysis results above are historical drafting results, superseded by approval and subsequent validation.
