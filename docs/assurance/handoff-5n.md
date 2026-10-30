# Next slice candidate: skill frontmatter documentation input profile

Prepared at the user's request: commit/push verified5m, then prepare the next-slice handoff in a FRESH chat. Selection recommendation only; NOT an approved specification or implementation plan. Continue substantive work in the new chat, not this delivered slice's context.

## Critical checkout and delivered state

EVERY repository command MUST use explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. The saved project's default `/home/enramosjr/Projects/agentic` is a DIFFERENT checkout. Do not work there, create another worktree, switch/reset or refresh the base.

Existing branch: `claude/assurance-increment-7`. Delivered HEAD: **87b8f5fdbf86fb1a7169a7fb8cd02d066bba5e8f**, pushed to matching origin branch. Delivery ls-remote confirmed matching SHA. Later local context does no new remote check.

Read leading **Delivery complete — authoritative** in implementation-5m.md first.5m Intent/Plan/Review/Verify/Ship closed. A separate L0 serves only delivery/handoff. After context, start NEW L2 with `lifecycle.py tier L2 --new`; never reopen5m or use L0 for source edits.

Framework has NO knowledge bundle: use `python3 .ai/scripts/repo.py context --json`, never initialize invoking-framework knowledge or invent baseline/log/records PASS. okf.py handoff --prompt inapplicable. ALL docs/assurance ignored/local/UNCOMMITTED. Shared Git scratch lies under original repository; lifecycle writes may require sandbox escalation despite explicit alternate cwd.

## Preserve delivered5m and all predecessors

THIRTEEN complete delivered profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract, python-audit-doc-contract, python-analysis-convergence-doc-contract, python-stage-doc-contract, python-tier-doc-contract, python-assurance-doc-contract, python-agents-budget-contract, python-semantic-lens-doc-contract. Preserve complete entries/rationales/exports/positive siblings and all unaffected tests. Literal exporter remains manual/advisory; inference/full suites/matching/freshness/schemas/gates/producer receipt exclusions unchanged.

5m corrected converge-5m-final.log: **6 PASS / 0 FAIL / 0 MANUAL**. Actual-one/count/bytes; framework/adopter identities/freshness; FOURTEEN intended assertIn failures, SIX broken controls, FOURTEEN freshly demonstrated reached additions. Each addition absent-data failure/supplied-data exactly-one PASS/intended boundary rejection. Uncalled bodies remain conservative pins. No proof for a fourteenth profile.

Initial review Medium restoration-confirmation gap fixed: two nested callbacks now write originals and read-assert exact bytes before temp cleanup. Initial complete report review-5m-initial.md and original converge-5m.log preserved. Ignored restoration-probe-5m.py drops cleanup writes: RED failed because old guard accepted them; identical GREEN rejects in both mutation families. This is a diagnostic, not a seventh product control. Final canonical review-5m.md Approved/no findings/both passes clean; preserve unchanged.

ONE full framework PASS on source tree **f434a3b**, framework-5m.log. Actual same-host wait confirmed completion, no rerun/full-suite count inferred. Registration RED3tests/3absent-profile failures then identical GREEN. Retrospective closed BEFORE Verify/no-new-lessons; attempted reason refresh refused conflicting retry without changing original closure. Corrected evidence supplements report, observations advisory/no binding promotion. No failed lifecycle run label needed correction. Preserve5l/5k/5j/5i/5h and earlier evidence/scopes.

Delivery reran no product suite. Reuse reported runtime/environment drift, NOT REUSE/fresh PASS. Commit used preceding identity via per-command options, no Git config change. Tracked state clean after delivery. Three exact-total guards now13: AssuranceDoc4455 retains original10-entry baseline; AgentsBudget4991 retains11; SemanticLens5477 retains12. Future total13→14 changes retain every exact comparison, never blanket weaken.

## Recommended exact candidate — NOT approved

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py RolesAndSkills.test_skills_have_name_matching_directory_and_a_description
```

Suggested ID: `python-skill-frontmatter-contract`. Broader class/module/sibling registration unapproved. Fresh regex found NO candidate catalog entry/ID, but DID find ONE existing explicit refusal expectation: SemanticLensProfileTests at test_assurance_inputs.py:5492 includes this exact sibling as a negative. If approved, explicitly replace ONLY that obsolete negative with a different actual unregistered sibling (recommend RolesAndSkills.test_codex_skills_are_a_symlink_to_the_claude_skills, subject to fresh search). Do not weaken refusal assertions or change positive existing siblings. This replacement needs approval in D1/D4; unlike5m, do not presume no obsolete negative.

Selected source107–111:

```python
for path in (ROOT / ".claude/skills").rglob("SKILL.md"):
    front = text(str(path.relative_to(ROOT))).split("---")[1]
    self.assertIn(f"name: {path.parent.name}\n", front)
    self.assertRegex(front, r"description: \S")
```

ONE top-level for statement with THREE body statements; TWO assertion sites per visited file in ONE test. Read path is DYNAMIC, not seven literal text calls. Seven current supported SKILL.md paths were source-inventoried: debug, implement, onboard, plan, review, ship, spec, each under .claude/skills/<name>/SKILL.md. This does NOT prove actual iteration/read count or order. Seven observed files would imply14assertions per actual successful traversal, not14tests or a fixed canonical/nonempty skill taxonomy.

The selected loop uses rglob, no sort and no nonempty/count assertion. With no matching docs it can execute ONE passing test and ZERO assertions: distinguish from actual ZERO TESTS. Future supported matching skills are in claimed dynamic scope. Analyze ignored/unsupported inputs/symlinks/runtime glob behavior before completeness claims; ledger inventories supported files, while rglob is not a ledger query. Source scope guards cannot establish universal dependency discovery.

Extraction is ordinary `.split("---")[1]`, no maxsplit/anchors or YAML parse: between first and second separator, or suffix after sole separator; missing separator raises IndexError. A literal separator in arbitrary prose can define capture. Name requires the unanchored exact f-string substring using immediate parent directory name plus actual newline. Description regex is unanchored `description: \S` (one literal space followed by a non-whitespace character), not YAML fields/types/descriptions/skill effectiveness. Earlier name check must remain satisfied for an intended description-regex failure. Later separators/body tokens outside captured segment do not satisfy it. Inspect all current captures/occurrences before approving failure fixtures.

Method executes no skill instructions, extracted/lifecycle command, copies nothing, directly observes no lifecycle runtime attribute and qualifies no governance/native/model/session behavior. Shared module/import/class/called setup still matters. Skills are selected data, not new authorization.

## Proposed scope/oracle — NOT approved

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.claude/skills/**
```

FIVE proposed ordered patterns. Production scope conservative for eager imports/lazy/decorator setup/unused future supported descendants. Final skill subtree conservative beyond SKILL.md, includes future supported skills/non-read assets and extra invalidation. Smaller justified closure is an alternative for D2. Do not silently hardcode seven current files and miss future additions. AGENTS/lifecycle/role docs are NOT selected direct reads; predecessor fixtures retain their own inputs. Broad glob is not a required literal/nonempty check: assurance_inputs.py check_paths292–316 only enforces required literal existence. Do not add missing-tree/nonempty refusals or exporter behavior without approved scope change; test and document selected vacuity/path-only behavior.

Independent source oracle must resolve exact class/method, ROOT/.claude/skills/rglob literal, dynamic relative-path/text/str chain, split/index semantics, parent-name/newline f-string and description regex/assertion binding. Reinspect reviewed method/setup and current six-module pins, root/import/text, disk_tmp/called scratch.require_disk, lifecycle eager/lazy setup, review_guard/ledger and protected/nested decorate/class construction. Do NOT copy5m's four-read/term/analyze/Passes/14assertIn oracle,5l's encoding oracle or5k's regex-row oracle. New expected pins independent of catalog/mutated source. Prior14reached variants reference only; newly claimed reach needs bytes/absent-data failure/supplied-data exactly-one PASS/boundary rejection. Insert AST additions after docstrings/before earliest decorator. Restore and READ-CONFIRM bytes before deleting nested fixtures.

## Fresh analyst decisions before approval

Use spec skill, required read-only analyst delegation and bounded analyst/Python persona sections. Draft ignored specification-5n.md or named equivalent and present D1–D4 HERE IN THE NEW CHAT:

- D1: exact skill-frontmatter method/ID only; narrowly replace the ONE confirmed obsolete SemanticLens refusal entry if still present? Recommend yes, after fresh search of replacement sibling/other registrations.
- D2: five ordered conservative patterns (including dynamic future skill subtree/extra invalidation), independent dynamic-loop/split/f-string/regex oracle and reviewed setup pins, or smaller justified closure? Recommend five with stated inventory/ignored/external/runtime limits.
- D3: independent actual-one and observed nonempty-seven-file traversal baseline; framework/adopter identities/freshness for current docs, target/helper/production/new supported script/new matching skill/non-SKILL subtree extra invalidation; argv/ordered declarations/receipt exclusions; fresh reach; intended assertion/regex failures and broken controls derived before approval? Candidate matrix is seven name-substring and seven description-regex failures (14), plus subtree omission/loose matcher/actual-zero controls (3), SUBJECT TO ANALYST DERIVATION/HUMAN APPROVAL. Also derive a valid NEW skill case and explicit empty-matching-tree ONE-test vacuous PASS case, distinct from zero-test rejection. Do not convert this into nonempty enforcement. Resolve split/capture/all-occurrence/earlier-name isolation, count/isolation and declaration behavior BEFORE spec approval. No counts approved here.
- D4: preserve all13complete profiles/mechanisms/manual adoption; ONLY narrow obsolete negative/cardinality updates; limit claims to dynamic file presence/substring/regex extraction and declared-file freshness, excluding skill execution/YAML correctness/effectiveness/governance/native/model/session? Recommend yes. New fixture baseline13/currenttotal14; preserve existing10/11/12 baselines and exact total guards.

Then obtain explicit HUMAN SPEC approval, and SEPARATE plan approval before implementation. Nonexecuting analyze/trace allowed during drafting. If evidence changes consequential scope, resolve before approval; do not bury decisions in implementation steps.

## Restrictions and fresh-chat prompt

Initial scope is read-only source/context and ignored spec drafting only: no product tests/runtime candidate import/implementation plan/source edits/native or model evaluation/session registration/allocation/trust grants/historical rescoring/evidence modifications/new worktree/knowledge/commit/push/PR/merge/base refresh/autonomy driver. All native allocations consumed.5m delivery approval fulfilled and does not carry forward. No new candidate runtime/count/empty-tree/glob probe ran during handoff.

Suggested prompt: Read handoff-5n FIRST, then leading Delivery complete in implementation-5m. Every command explicit cwd designated existing checkout. Start freshL2 after framework context; use read-only analyst delegation to draft specification-5n and present D1–D4 in this chat. Independently derive dynamic rglob reads, split/index/f-string/regex semantics, current-file and future/empty-tree boundaries, failure/control counts, and narrow obsolete negative replacement. Await explicit SPEC then separate PLAN approval. No product/native/model/session/trust/delivery work while drafting.

## Handoff checks

check-ignore on handoff/report -> exit0/both ignored; git diff --check -> exit0; tracked status empty. Framework affected on both ignored docs -> exit1/no bundle, synchronization INAPPLICABLE, no records PASS. Local context confirms delivered HEAD/branch/equal local upstream refs/clean tracked state with remote_verified false (local-only); actual delivery ls-remote separately confirmed SHA. No candidate test/runtime probe or product suite ran during handoff. Handoff/report changes remain local/ignored/uncommitted.
