# Spec: Skill-frontmatter documentation input profile

Status: Approved by human:enramosjr on 2026-10-29: “Approve the 5n specification and recommended D1–D4. Draft the implementation plan for separate approval before making source changes.” This is not an implementation plan or runtime evidence.

## Problem and outcome

The advisory literal input exporter has thirteen delivered profiles but no exact profile for the existing skill-name/description documentation check. Add one bounded profile so callers can explicitly adopt conservative repository-file freshness declarations for that command. This framework has no knowledge bundle or structured capability baseline; this standalone spec initializes neither.

## Users and scenarios

A caller requests a suggestion for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py RolesAndSkills.test_skills_have_name_matching_directory_and_a_description
```

Proposed ID: `python-skill-frontmatter-contract`. The caller inspects the returned declaration and manually adopts it. Framework and disposable-adopter checks establish execution identity, ordered declarations and freshness. Future supported matching skill files remain in scope without enumerating a fixed taxonomy.

Inspected source test_lifecycle_conformance.py:107–111 is one top-level for using dynamic rglob, with three body statements: a relative-path/str/text read and split assignment, assertIn, then assertRegex. `text` at26–27 calls `(ROOT / path).read_text()`. Seven currently inventoried skill files (debug, implement, onboard, plan, review, ship, spec) each have separators at1/4, name at2 and description at3; full-file search found no additional name:/description:/--- occurrences. This is source inventory, not observed traversal. A successful observed seven-file traversal implies fourteen assertion-site visits within ONE test, not fourteen tests.

## Requirements

- R1: The catalog MUST add only the exact command above as python-skill-frontmatter-contract. Class/module selectors, alternate executable/path spellings, appended options and unregistered siblings MUST retain refusal. The sole obsolete SemanticLens refusal for this newly registered method MUST be replaced only with the confirmed unregistered RolesAndSkills.test_codex_skills_are_a_symlink_to_the_claude_skills sibling; refusal assertions and positive siblings MUST remain intact.
- R2: The profile MUST return exactly the five ordered inputs below, each with a rationale. An independent source oracle MUST bind exact class/method, ROOT/.claude/skills/rglob literal, dynamic relative-path/str/text read, split/index operation, parent-name/newline f-string, assertion order and description regex to reviewed expectations independent of catalog or mutated-source regeneration. Reviewed method/setup fingerprints MUST cover six setup modules and reject the fourteen freshly demonstrated reached additions below. Uncalled bodies MUST remain conservative pins, not claimed executed dependencies.
- R3: Public text/JSON export MUST preserve token/Inputs/rationale parity, supplement order, root/path/inventory validation, immutability, nonexecution and refusal behavior. Export MUST NOT import/execute the candidate, adopt Inputs or record evidence. Missing required literals and unsafe/unsupported paths MUST refuse with a reason and no usable candidate. Assertion-failing existing skill data MUST remain exportable. The subtree glob MUST permit no matches; no missing-tree or nonempty-skill refusal may be added. New supported matching skills and non-SKILL subtree assets MUST be selected under existing inventory rules.
- R4: All thirteen complete predecessor profiles, rationales, exports, positive siblings and unaffected tests MUST remain preserved. The new fixture MUST compare against the thirteen-profile delivered baseline at87b8f5fdbf86fb1a7169a7fb8cd02d066bba5e8f. Only the confirmed obsolete negative and three predecessor current-total comparisons13→14 may change among predecessor assertions; original10/11/12-entry baselines and exact per-entry/export comparisons MUST remain. Guide claims MUST describe dynamic string checks, conservative extra invalidation, manual adoption and completeness limits without implying VERIFIED evidence.
- R5: Isolated framework verification MUST independently establish exactly one passing selected test and observed traversal of all seven current files, with two successful assertion-site visits per file and stable selected bytes. Unchanged evidence and unrelated-test/non-input-document edits MUST REUSE. Separate assertion-preserving edits to EACH current skill, target, helper, representative production script, new supported script, new matching skill and non-SKILL subtree asset MUST RERUN. Framework MUST acquire no knowledge bundle. The fourteen intended failures and semantic cases below MUST establish their specific count/assertion/error outcomes, rather than accept arbitrary nonzero results.
- R6: An ordinary adopter MUST explicitly adopt public export, become VERIFIED after independently proven actual one-test execution, remain VERIFIED after unrelated-test/non-input-document edits, and become STALE after separate assertion-preserving changes to EACH current skill, target/helper, representative production script and supported additions listed in R5. Unmatched ordered declarations and argv identity MUST yield UNVERIFIED under existing rules; producer receipt exclusions MUST remain effective. The three broken controls below MUST be rejected at their intended boundary. Every mutation family MUST confirm modified bytes, restore originals and read-confirm exact bytes before nested fixture deletion.

Proposed ordered inputs:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.claude/skills/**
```

Production scope includes eager imports, lazy/decorator construction, unused non-test descendants and future supported scripts. Skill scope includes future matching documents and non-read assets. These deliberate extra invalidations require D2 approval. Exclude tests before restoring selected module/helper. AGENTS/lifecycle/role documents are not new direct reads; predecessor compatibility fixtures retain their inputs.

## Acceptance

Proposed selectors below do not yet exist. No acceptance command may run during drafting; missing classes, counts or end states fail acceptance after implementation. Independent review and the required full framework gate follow implementation.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py SkillFrontmatterProfileTests` checks exact registration/root/argv, refusal variants, narrow negative replacement and thirteen complete predecessor comparisons; absent/misregistered profile or weakened refusal fails.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py SkillFrontmatterDependencyTests` checks exact order/rationales, independent ledger selection, dynamic-loop/source/setup oracle and fourteen freshly demonstrated reached additions. Every addition requires confirmed bytes, absent-data execution failure, supplied-data exactly-one-test PASS and intended boundary rejection. Prior evidence proves none for this selector.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py SkillFrontmatterExportTests` checks formats/extras, immutability/nonexecution, every required literal/path refusal, new supported matching skill/non-SKILL selection, empty-tree export and path-only export of existing assertion-failing skill data.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py SkillFrontmatterCompatibilityTests` checks complete thirteen-entry baseline preservation, three retained exact-total guards, narrow negative replacement and guide limits; any altered predecessor or mechanism fails. Existing AssuranceDoc, AgentsBudget and SemanticLens original10/11/12 baselines and per-entry/export comparisons remain exact; blanket weakening is forbidden.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py SkillFrontmatterFrameworkEndToEndTests SkillFrontmatterFailureTests` proves actual-one/current traversal/bytes, framework identity/freshness, fourteen intended failures and semantic cases below; omitted execution, empty current baseline, missing invalidation or wrong failure boundary fails.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py SkillFrontmatterAdopterEndToEndTests SkillFrontmatterControlTests` proves adopter states/identities/ordered declarations/receipt exclusions and rejects three confirmed broken controls, with independent actual-zero evidence and restoration readbacks.

## Assertion-failure matrix

Exactly fourteen independent disposable current-file variants: for each of debug, implement, onboard, plan, review, ship and spec:

1. Alter its sole captured exact `name: <immediate-parent-name>\n` substring while preserving description. Require ONE selected test and intended assertIn failure.
2. Remove/alter every captured `description: \S` match while preserving the earlier exact name. Current inspection finds one per file. Require ONE selected test and intended assertRegex failure.

Confirm original/changed bytes, capture boundaries and all occurrences; preserve all earlier predicates. Missing-marker IndexError, alternate capture, collateral earlier assertion, import/setup/CLI failure or zero execution do not count. Selected source stays unchanged. Export remains path-only. Restore and read-confirm originals. Iteration order is unspecified. If source/capture/count/isolation differs, return for scope review rather than silently change approved breadth.

## Semantic cases

Disposable cases MUST establish the existing behavior, without strengthening it:

- A valid newly added supported matching skill is traversed and passes using its own immediate parent name; addition invalidates preceding evidence.
- Removing all matching skill files permits export and executes exactly ONE passing selected test with ZERO assertion-site visits. Both absent subtree and existing empty subtree retain this behavior. This differs from zero tests executed.
- A sole literal `---` captures its suffix; valid name/description there can pass. Arbitrary text before the first separator need not be YAML/frontmatter.
- With multiple separators, only split segment index1 supplies checks; tokens confined to a later segment cannot satisfy capture. No separator raises IndexError, not an intended assertion failure.
- Missing exact name plus valid description fails earlier assertIn. Valid name plus missing regex match fails assertRegex. Name requires immediate parent and actual trailing newline; a missing newline or different parent fails.
- Name and description checks are unanchored: preceding non-field text does not disqualify matching substrings. Description is literal `description: ` immediately followed by a non-whitespace character; extra whitespace immediately after that one space fails when no other match remains. These are substring/regex checks, not YAML fields/types or skill effectiveness.

These cases supplement the fourteen current-document failures and are not additional broken controls. `.split("---")[1]` has no maxsplit/anchor/YAML parser: segment between first and second separator, or suffix after sole separator. No nonempty assertion exists.

## Fresh reached-dependency challenges

Exactly fourteen proposed locations, each introducing a read of excluded fixture data:

1. Module setup in test_lifecycle_conformance.py.
2. Module setup in disk_tmp.py.
3. Module setup in scratch.py.
4. Module setup in lifecycle.py.
5. Module setup in review_guard.py.
6. Module setup in ledger.py.
7. RolesAndSkills class construction.
8. Selected skill-frontmatter method body.
9. Called text helper.
10. Called scratch.require_disk body.
11. Called lifecycle.lazy body.
12. Called review_guard.protected body.
13. Its called nested decorate body.
14. New excluded test-helper import introduced into selected module setup.

Each MUST independently prove confirmed bytes, absent excluded-data failure attributable to that data, supplied-data exactly ONE passing selected test and intended source/setup boundary rejection. Predecessor reach results prove none here. AST body insertion goes after docstrings and BEFORE the first statement's earliest decorator. Restore and read-confirm bytes before deleting nested fixtures. Uncalled producer/sibling bodies remain conservative pins only; no lifecycle runtime-attribute oracle is part of selected assertions.

## Broken controls

Exactly three independently restored controls:

1. Omit `.claude/skills/**` from suggested declaration; confirm an assertion-preserving skill edit still passes the selected test, then require the freshness guard to reject missing coverage.
2. Loosen exact argv matching; require refusal guard to reject the actual unregistered symlink sibling.
3. Run an actual empty unittest suite ignoring the selector; independently confirm `Ran 0 tests` BEFORE interpreting Python-dependent exit, then require execution-count rejection. A loader _FailedTest is insufficient.

The legitimate empty-matching-tree ONE-test PASS is a separate semantic case. Controls require confirmed mutation bytes, intended rejection and restoration, not arbitrary failures.

## Constraints

EVERY repository command uses explicit cwd /home/enramosjr/Projects/agentic-assurance-7. Retain branch claude/assurance-increment-7 and delivered HEAD87b8f5fdbf86fb1a7169a7fb8cd02d066bba5e8f; no base refresh/new worktree/switch/reset. ALL docs/assurance remain ignored/local/UNCOMMITTED. Preserve 5m and predecessor canonical evidence and scopes.

Python3.9+, stdlib/unittest and existing exporter only. Inference, full suites, matching, freshness, schemas, gates, receipt exclusions and manual/advisory adoption stay unchanged. Runtime rglob is not ledger inventory. Existing supported tracked/nonignored-untracked inventory and containment checks do not establish universal ignored/external/symlink/runtime completeness. Runtime executable/environment and temporary storage/mount assumptions remain outside declared repository-file completeness. Unresolved reads require review and retaining current scope.

Framework has no invoking knowledge bundle: synchronize existing guide without knowledge initialization or invented baseline/log/records PASS. The initial spec-drafting restriction on an implementation plan is fulfilled by explicit human SPEC approval and authorization to draft the plan. Until separate PLAN approval: no product tests/runtime candidate import/source edits, native/model evaluation/session registration/allocation/trust grants, historical rescoring/evidence edits, commit/push/PR/merge or autonomy driver. Native allocations remain consumed; 5m delivery authority is fulfilled and does not carry forward.

Preserve thirteen complete profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract, python-audit-doc-contract, python-analysis-convergence-doc-contract, python-stage-doc-contract, python-tier-doc-contract, python-assurance-doc-contract, python-agents-budget-contract, python-semantic-lens-doc-contract.

## Non-goals

Broader registration; YAML parsing; mandatory/nonempty taxonomy; altered selected assertions; skill execution/correctness/effectiveness; actual lifecycle analysis/review/governance/enforcement; native/model/session qualification; general dependency discovery; automatic adoption; reduced full gates or savings claims; planning before explicit SPEC approval or implementation before separate PLAN approval.

## Assumptions

D1–D4 below are approved, including fourteen intended failures, fourteen freshly required reached additions, three controls and semantic cases. Source inventory is not runtime traversal/count evidence; these remain acceptance obligations, not observed results. Python persona considerations materially shaping this draft: import-time/called-helper/decorator reach, dynamic filesystem enumeration, independent count-first proof and exact-byte restoration.

## Open questions

None. The user explicitly approved the specification and recommended D1–D4. Ready for planning; implementation requires separate PLAN approval.

## Approved decisions

The user approved the recommended defaults below; alternatives remain decision context, not unresolved scope.

- D1: Approve exact method/ID and ONLY the confirmed obsolete SemanticLens negative replacement with the actual unregistered symlink sibling? Recommended: yes. Source evidence cannot authorize registration.
- D2: Approve five ordered conservative patterns, extra invalidation for supported future/non-read subtree content, independent dynamic oracle, six reviewed setup modules and fourteen fresh reach challenges? Recommended: yes, retaining explicit inventory/runtime limits; alternative is smaller independently justified closure.
- D3: Approve actual-one/observed seven-file baseline, framework/adopter identities/freshness/ordered declarations/receipt exclusions, fourteen intended failures, three broken controls and all semantic cases including empty-tree vacuity? Recommended: yes; no nonempty enforcement. Breadth/count changes require scope review.
- D4: Preserve thirteen complete predecessors/mechanisms with ONLY narrow negative/cardinality updates and bounded dynamic substring/regex/freshness claims? Recommended: yes.

HUMAN SPEC approval received in this chat; SEPARATE PLAN approval is required before implementation.

## Investigation evidence

Read handoff-5n first, then authoritative Delivery complete in implementation-5m. Local-only context confirms framework, delivered HEAD/branch/equal upstream refs/clean tracked state; remote_verified false, no new remote check. New L2 declared with --new after sandbox escalation for shared Git scratch.

Required read-only analyst independently inspected source107–111/text26–27, current seven documents/captures/all occurrences, unique obsolete refusal5492 and unregistered replacement100. Setup inspected: target19–20; disk_tmp11–18; lifecycle44–65; review_guard ledger import25/protected629/nesteddecorate631 and lifecycle decorator sites1011/1209/1321. Parent independently inspected exporter292–316/319–343 and ledger73–91/146–157. No product execution or candidate import.

## Draft validation

- `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5n.md` → exit1, only High open-questions for pending D1–D4. This is an honest approval blocker, not a passing analysis or recorded Intent approval.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5n.md` → exit0, six requirements traced; no acceptance executed.
- `git check-ignore docs/assurance/specification-5n.md` → exit0, ignored/local/uncommitted.
- `git diff --check` and `git status --short --untracked-files=no` → exit0, no tracked changes.

No implementation plan drafted. Retrospective and subsequent lifecycle stages remain pending future approved work.
