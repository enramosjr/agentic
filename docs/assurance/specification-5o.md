# Spec: optional role-registration documentation input profile (5o)

Draft for human review, 2026-10-29 America/Chicago. NOT approved. L2; analyst role; Python principal engineer. No implementation plan or source change is authorized. New lifecycle task; delivered 5n is closed.

## Problem and outcome

The assurance initiative's recovered objective is durable requirement-to-check evidence that can be evaluated after later changes, with conservative unknown impact and explicit evidence limits. Historical architecture at `4031aab:docs/assurance/architecture.md` sections 1, 6 and 8 sets out seven areas: obligations/reporting, enforcement/delta evidence, architecture constraints, attestation/risk, optional input adapters, adoption/demo, and measurement/pruning. It is historical draft context, not a newly approved milestone acceptance baseline.

Current implementation surfaces exist for all seven areas: assurance.py, lifecycle.py, assurance_architecture_demo.py, assurance_demo.py, assurance_measure.py, assurance_inputs.py and lifecycle guide. Inspection establishes implementation presence, not a new runtime PASS or complete initiative audit. Existing delivery/evidence records retain their original source/environment scopes. Native/model qualification is a separate effort and remains restricted.

The approved original input-profile scope is reusable inspected declarations for selected Python checks, not all-test coverage or automatic dependency completeness (specification-5.md lines 8–12, 25–27, 53–63). Fourteen profiles are delivered through 5n (implementation-5n.md leading delivery update). Profile count is not an initiative completion criterion. No approved finite remaining-work/initiative closeout baseline has been recovered. Do not label the whole initiative complete on this slice's acceptance results.

Known limits remain visible: under-declared inputs can miss real changes; ambient/ignored/external data is outside file-inventory coverage; unmerged records are invisible; audit detects drift rather than deliberate forgery; approvals are claims. The measurement fixture avoids same-second record ordering with a delay, rather than repairing that mechanism (implementation-7.md lines 19–29; assurance_measure.py lines 148–152). Fixture rerun reductions do not establish production reliability or project-wide savings. Some are deliberate design limits; their milestone disposition requires explicit closure criteria rather than silent acceptance or assumed implementation obligations.

If approved as useful additional scope, 5o adds one maintained profile for an existing exact command. It does not complete or replace an initiative-level gap/closure assessment.

## Users and scenarios

A framework maintainer explicitly requests a declaration for:

`python3 .ai/scripts/tests/test_lifecycle_conformance.py RolesAndSkills.test_every_role_in_the_selection_table_is_registered_for_claude_and_codex`

Proposed ID: `python-role-registration-doc-contract`. Search of .ai/scripts found only the method definition at test_lifecycle_conformance.py:93; no catalog entry or obsolete negative for this candidate was found. No broader class/module/sibling is included.

## Requirements

- R1: The catalog MUST add exactly the ID and argv above, with per-pattern rationale and the seven ordered patterns below, preserving all fourteen complete predecessor profiles and their exports. The command MUST remain explicitly adopted/manual and unknown variants MUST refuse with no usable declaration.
- R2: An independent source-derived oracle MUST validate the selected method, class, ROOT/text helper and relevant setup/import/decorator boundaries. It MUST distinguish declared conservative production/registration scope from reached behavior and reject newly reached repository data outside the reviewed declaration. No claim of complete static dependency inference is permitted.
- R3: The public exporter MUST emit matching read-only text/JSON, exact argv, ordered declaration and lifecycle input tokens, supplemental ordering and limitations without importing/executing the target or creating evidence. Existing path/inventory refusals MUST remain unchanged; successful export alone MUST NOT imply role-set correctness or registration existence.
- R4: Framework and ordinary-adopter fixtures MUST run the actual selected command as exactly ONE test on unchanged selected bytes, establish the separately observed prefix/five-role/eight-probe baseline, and assert existing REUSE/RERUN and VERIFIED/STALE/UNVERIFIED identities across every declared dependency category. Diagnostics MUST forward real checks rather than replacing successful assertions with logging.
- R5: Failure and semantic verification MUST distinguish the NINE intended current-fixture assertion failures, fourteen freshly reached dependency challenges, and every semantic case below. Export refusal, import error, syntax error, earlier equality failure and arbitrary nonzero exit MUST NOT substitute for the intended reached assertion failure. Every altered fixture MUST restore and read-confirm bytes and disposable index state before cleanup.
- R6: Acceptance MUST reject THREE independent broken-control families containing FIVE variants: actual zero-test execution, three omitted required scopes, and loosened exact-command matching. Documentation and compatibility checks MUST preserve all prior profiles, full-suite breadth, matching/freshness/schema/gate/receipt behavior, four exact current-total guards and the existing unregistered symlink sibling refusals. Documentation MUST limit this profile to extraction, set equality, registration-file presence and declared freshness, and MUST NOT claim overall initiative completion.

## Declared input boundary

Recommended conservative declaration, in order:

1. `.ai/scripts/**`
2. `!.ai/scripts/tests/**`
3. `.ai/scripts/tests/test_lifecycle_conformance.py`
4. `.ai/scripts/tests/disk_tmp.py`
5. `AGENTS.md`
6. `.claude/agents/**`
7. `.codex/agents/**`

Production scope includes import setup, lazy/decorator/class construction and future supported descendants conservatively; it is not an assertion that every function body runs. Registration subtrees intentionally stale evidence for byte-only edits and supported new unused descendants, although the selected method only calls is_file on eight paths. Alternative: replace the last two subtree patterns with the eight current literal registration files (thirteen ordered patterns total), sacrificing automatic coverage of future registration descendants and making all eight required literals. This consequential tradeoff requires D2 approval.

Supported inventory means tracked and nonignored untracked files under existing ledger semantics. Globs do not require nonempty registration trees. Missing tracked selected paths can trigger exporter refusal; deleting the corresponding disposable index entry distinguishes genuinely absent inventory from broken tracked inventory. AGENTS.md is a required literal. Ignored files, symlink targets and runtime/platform configuration do not become covered by this profile merely because the selected command can see them.

## Independent semantic and proof matrix

Source at test_lifecycle_conformance.py:93–98 performs THREE top-level statements: role extraction, equality, loop. It reads AGENTS.md once via text at 26–27. It applies `split("### 2.3")[0]`, then Python regex `\(\.ai/agents/(\w+)\.md\)`, then set conversion. This is not Markdown/table parsing. No maxsplit or heading anchor is present. No delimiter means the whole text; first literal occurrence wins; later occurrences are irrelevant. Duplicates collapse; ordering is unspecified; regex word captures include Unicode word characters. Current five captures are AGENTS.md:51–55, before delimiter:59.

Equality requires exactly analyst/planner/implementer/reviewer/orchestrator. The loop subtracts orchestrator, then checks .claude/agents/{role}.md before .codex/agents/{role}.toml for each role. Role iteration order is not promised. The current source therefore predicts ONE test and NINE successful assertion visits: one equality plus eight is_file checks. No candidate execution or observed count is claimed in this draft.

| Case family | Required outcome and attribution |
| --- | --- |
| Current baseline | Actual public argv ONE test/pass; separate forwarding observation confirms five captures/five distinct names, equality then both checks for each of four roles; no orchestrator probe; stable bytes. |
| Nine intended failures | One missing-role equality failure after removing all captures of one role; eight independent missing-path failures (four roles times two harnesses), preserving five-role equality and removing disposable index entries as needed so export succeeds and the precise is_file assertion is reached. |
| Extraction/set | Duplicate capture leaves five-role set and pass; missing and extra distinct roles fail equality; link-like prose/comments before marker still count; invalid capture spelling/non-word names do not match; Unicode word extra capture is recognized and fails equality; changing role-document contents has no direct read effect. |
| Delimiter | No marker uses whole text and can pass; a valid extra role after the original marker is ignored until marker removal; an earlier literal marker truncates the capture region; first of multiple markers governs. Do not expect IndexError. |
| Ordering/isolation | Exact equality is required before any registration check; extra/missing-role fixtures demonstrate no path probes. Path-failure cases retain equality and isolate one missing path regardless of role iteration order. |
| Presence/type/content | Arbitrary contents in existing eight files pass selected presence checks; byte-only edits still stale declared evidence. A directory at one required registration path fails its is_file check. No orchestrator registration file is required; adding one is conservative extra invalidation under the proposed globs. No agent/TOML/content correctness claim. |
| Symlinks/boundaries | is_file can follow a symlink to a file; dangling links/directories fail selected checks. Separately test exporter handling of contained, escaping and unsupported targets using existing containment/inventory rules; do not infer target-byte freshness or symlink support from selected is_file success. No symlink-sibling registration. |
| Inventory/runtime | Missing tracked path refusal is not one of the eight selected failures. Absent-from-inventory required path can export under globs then fail selected assertion. Existing ignored registration files can satisfy runtime presence while absent from inventory; demonstrate and state the coverage limit. Empty supported registration trees cannot pass the selected method. |
| Public export separation | With supported AGENTS and inventory, assertion-failing document bytes or absent registration inventory can still yield a path-only declaration; a missing/ignored AGENTS literal refuses. Export performs no conformance validation. |
| Freshness | Framework REUSE/adopter retained freshness for known unrelated supported edits; RERUN/STALE for AGENTS, each of eight registration paths, selected source, helper, production representative, new supported production and each registration-subtree descendant; byte-only presence-preserving edits and unused-file additions demonstrate intentional extra invalidation. Exact command and ordered-declaration changes cannot match old evidence; producer receipt exclusion is preserved. |

Fourteen proposed fresh reach challenges: module setup in selected conformance module, disk_tmp, scratch, lifecycle, review_guard and ledger; RolesAndSkills class construction; selected method; text helper; scratch.require_disk; lifecycle.lazy; review_guard.protected; its nested decorate; a newly imported excluded helper. Each MUST independently confirm injected bytes, absent-data failure on actual execution, supplied-data exactly-ONE-test PASS, and intended out-of-declaration boundary rejection. Pin/setup review MUST be independent of catalog/source-under-test regeneration. Insertions respect docstrings/decorators. If static or runtime evidence disproves reach, do not silently reuse predecessor evidence or drop the challenge: return the changed proof boundary for approval. Uncalled bodies remain conservative pins only.

Three control families contain FIVE independently rejected variants: establish an actual empty suite and reject zero executed tests (one); separately omit AGENTS.md, the Claude subtree and the Codex subtree from the proposed profile, apply assertion-preserving edits, prove the selected test still passes and require the shared coverage/freshness guard to fail (three); loosen matching and require the preserved unregistered symlink sibling to be rejected (one). Independently check actual failure counts; omission controls must not assume multiple subTest failures count as one. A loader _FailedTest does not establish zero execution.

## Acceptance

These are proposed NEW acceptance classes in existing test_assurance_inputs.py, not existing tests or PASS claims. Every command must fail when its named class is absent. No command below is authorized to execute during drafting.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py RoleRegistrationProfileTests` checks the literal exact profile, ordered patterns/rationales, fourteen complete baseline entries and exports, fifteenth current total, refusal variants and preserved symlink negatives.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py RoleRegistrationDependencyTests` checks the independently reviewed prefix/regex/set/path/helper/setup oracle and fourteen fresh reach challenges with all three required outcomes and restoration.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py RoleRegistrationExportTests` drives public text/JSON export, supplements, sentinels/no execution, unchanged evidence, invalid boundaries and path-only versus conformance distinction.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py RoleRegistrationFrameworkTests RoleRegistrationAdopterTests` asserts public argv/count/stable bytes and separate real-forwarding observation, every declared-category freshness case, unrelated edit, identity mismatch, and receipt exclusion without creating an invoking-framework bundle.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py RoleRegistrationFailureTests` checks all nine intended assertion failures and every extraction/delimiter/isolation/presence/symlink/inventory semantic row, including exact failure attribution and restore/read-confirm evidence.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py RoleRegistrationControlTests RoleRegistrationCompatibilityTests` rejects all three broken controls, checks bounded guide statements and all fourteen predecessors/four total guards/original historical baselines, and confirms unchanged full-suite/inference/matching/freshness/schema/gate/receipt behavior.

## Constraints

Retain designated checkout /home/enramosjr/Projects/agentic-assurance-7, branch claude/assurance-increment-7, delivered HEAD 02dd97586873f24a604224aa5ad186a60c4104e7. Framework mode has no knowledge bundle. Working draft stays ignored/local/uncommitted. Preserve all canonical 5n and earlier evidence without rescoring or modifying it.

If separately approved for implementation later, preserve selected conformance source/assertions and exporter algorithms. Only new literal profile/test/guide work and the four explicit total14→15 comparisons are proposed. Preserve historical10/11/12/13 baseline entry checks; new fixture preserves all14 complete current entries. No obsolete negative replacement is currently justified. Python3.9+/stdlib conventions apply.

## Non-goals

Implementation planning or source edits in this task; all-test profile coverage; automatic adoption, dependency completeness or reduced required gates; role-registration content correctness, TOML validation or agent execution; native/model/session/trust work or new allocations; historical rescoring; worktrees/base refresh; knowledge initialization; commit/push/PR/merge; declaring the overall assurance initiative finished.

## Assumptions

The proposed seven-pattern declaration is a recommendation, not approval. The selected source predicts counts; future actual observation must establish them. Existing evidence remains historical and scoped, not fresh verification for this draft. Recovered architecture provides the initiative's direction but does not supply an approved final closure/disposition for every current limit.

## Open questions

- Overall scope: should the next approval prioritize a read-only initiative-level reconciliation of all seven areas, accepted limitations and finite exit criteria, or authorize optional 5o first? Recommend reconciliation before more profile expansion. Current records do not establish that the fifteenth profile is necessary to finish the initiative.
- D1 — Candidate: approve only the exact role-registration method and proposed ID? Recommend yes if 5o is chosen; preserve existing negatives.
- D2 — Boundary: seven conservative ordered patterns with intentional byte-only/unused-descendant invalidation, or thirteen patterns with eight literal registration paths? Recommend seven, with the inventory/runtime/presence limits above.
- D3 — Proof: approve the specified actual-one/nine-assertion expected baseline, NINE intended failures, FOURTEEN independently re-proved reach challenges, THREE rejected control families/FIVE variants and all semantic/freshness rows? Recommend yes; none is a runtime result yet. An alternative THIRTEEN intended failures exercises missing-role equality once per each of five roles plus eight path failures; it adds symmetric equality coverage rather than additional assertion sites.
- D4 — Compatibility and claims: preserve all fourteen profiles and prior evidence, original10/11/12/13 baselines and four exact total guards, manual adoption and narrow presence/freshness claims? Recommend yes; no whole-initiative completion claim.

Explicit human SPEC approval is required before Intent can be recorded or planning can begin. A separate PLAN approval is required before implementation. No approval is inferred from receiving this draft or prior delivery authorization.

## Draft evidence and scope

Read-only independent analyst consulted. Source inspections: conformance26–27/93–98, AGENTS51–59, disk_tmp10–20, lifecycle44–66, review_guard25–26, assurance_inputs307–331, lifecycle assurance179–208/272–305, assurance367–498, assurance_demo144–175, assurance_measure148–152. Prior records: handoff-5o, implementation-5n leading delivery; original specification-5; implementation-3/5/7; architecture/assessment at4031aab. No candidate imports, tests, runtime probes or source changes occurred. No fresh product PASS is claimed.

Draft consistency: `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5o.md` exits1 with the sole High open-questions finding; this is an unresolved human decision gate, not approval. `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5o.md` exits0/six requirements traced. `git check-ignore docs/assurance/specification-5o.md` exits0/names draft; `git diff --check` exits0; `git status --short` empty. No lifecycle stage is recorded. Retrospective/Review/Verify/Ship have not been performed for proposed5o. No invoking-framework knowledge baseline/log/records PASS is created or claimed.
