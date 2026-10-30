# Next slice candidate: role-registration documentation input profile

Prepared at the user's request: commit/push verified5n, then prepare the next-slice handoff for a FRESH chat. Recommendation only; NOT an approved specification or implementation plan. Continue substantive work in the fresh chat.

## Critical checkout and delivered state

EVERY repository command MUST use explicit cwd `/home/enramosjr/Projects/agentic-assurance-7`. Saved project default `/home/enramosjr/Projects/agentic` is a DIFFERENT checkout. Do not work there/create another worktree/switch/reset/refresh base.

Existing branch **claude/assurance-increment-7**; delivered HEAD **02dd97586873f24a604224aa5ad186a60c4104e7**, pushed to matching origin branch. Delivery ls-remote confirmed matching SHA. Later repo context is local only, not another remote check.

Read leading **Delivery complete — authoritative** in implementation-5n.md. 5n Intent/Plan/Review/Verify/Ship closed. Separate L0 serves delivery/handoff only. After context, start NEW L2 with `lifecycle.py tier L2 --new`; never reopen5n or use L0 for source work.

Framework mode has NO knowledge bundle: `python3 .ai/scripts/repo.py context --json`, NEVER initialize invoking-framework knowledge or invent baseline/log/records PASS. okf.py handoff --prompt inapplicable. ALL docs/assurance ignored/local/UNCOMMITTED. Shared Git scratch lies under original repository; lifecycle writes may need sandbox escalation despite designated cwd.

## Preserve delivered5n and predecessors

FOURTEEN complete delivered profiles: python-runner-test, python-architecture-compatibility, python-harness-wiring, python-reviewer-report-contract, python-installer-doc-contract, python-validation-policy-contract, python-audit-doc-contract, python-analysis-convergence-doc-contract, python-stage-doc-contract, python-tier-doc-contract, python-assurance-doc-contract, python-agents-budget-contract, python-semantic-lens-doc-contract, python-skill-frontmatter-contract. Preserve all complete entries/rationales/exports/tests/positive siblings. Export remains manual/advisory; inference/full suites/matching/freshness/schemas/gates/producer receipt exclusions unchanged.

Corrected converge-5n-final.log: **6 PASS / 0 FAIL / 0 MANUAL**. Actual-one/stable bytes; separate real-forwarding traversal diagnostic observed7files/14successful assertion visits; framework/adopter identities/freshness; FOURTEEN intended assertion failures; FOURTEEN newly reached additions with absent-data failure/supplied-data exactlyONEpass/intendedboundaryreject; THREE broken controls and all semantic cases. Uncalled bodies remain conservative pins. This proves no fifteenth profile.

Initial converge-5n.log **4PASS/2FAIL** is preserved. Two fixture causes were pinned RED2tests/2failures then identicalGREEN: empty tree must remove disposable tracked skill index entries (otherwise exporter correctly refuses missing inventoried paths); omission control must target one shared freshness criterion instead of counting9subTest failures as1. Fixes restore/read-confirm bytes and restore disposable index. No exporter/selected-test change or breadth reduction. No failed lifecycle run label needed correction.

The separate omitted-observation diagnostic is test-integrity evidence, not a fourth control. Actual empty supported trees permit export and execute ONEtest/ZEROassertions; true ZEROtests rejected independently. Runtime ignored matching skill was demonstrated traversed but absent from ledger inventory. Preserve all distinctions and inventory/runtime/symlink/environment limits.

review-5n.md is unchanged canonical independent report, **Approved/no findings/both passes clean**. ONE full framework PASS on source tree **ef88e68**, framework-5n.log; actual same-host completion, suppressed output supplies no full-suite count. RegistrationRED2tests/2absent-profile failures then identicalGREEN. Retrospective closed BEFORE Verify/no-new-lessons/no binding promotion. Receipt20261029T225847Z-claude_assurance-increment-7.json; original evidence scopes retained.

Delivery reran no suite. reuse inputs-5n-framework reported runtime/environment drift, NOT REUSE/freshPASS. Commit identity supplied per command, no config change. All5m/earlier reports/evidence unchanged; no native/model/session/trust or historical rescoring.

FOUR exact current-total guards now14: AssuranceDoc4455 retains original10-entry baseline; AgentsBudget4991 retains11; SemanticLens5477 retains12; SkillFrontmatter6068 retains13. Future14→15 updates must retain all exact comparisons; new fixture compares14complete entries. No blanket weakening.

Symlink sibling remains deliberately unregistered. It is now an explicit refusal at SemanticLens5492, SKILL_FRONTMATTER_SIBLING5950, SkillFrontmatterProfileTests (including a dedicated refusal guard), and the loose control. Choosing that sibling would require explicit broader negative/control changes; this handoff recommends the other role-table method instead. Do not silently replace those5n guards.

## Recommended exact candidate — NOT approved

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py RolesAndSkills.test_every_role_in_the_selection_table_is_registered_for_claude_and_codex
```

Suggested ID: **python-role-registration-doc-contract**. Fresh structured regex search over .ai/scripts found only the method definition93 and no candidate catalog entry/ID/refusal. Fresh chat MUST reconfirm; do not presume absence. No broader RolesAndSkills class/module/sibling registration approved.

Selected source93–98:

```python
roles = set(re.findall(r"\(\.ai/agents/(\w+)\.md\)", text("AGENTS.md").split("### 2.3")[0]))
self.assertEqual(roles, {"analyst", "planner", "implementer", "reviewer", "orchestrator"})
for role in roles - {"orchestrator"}:
    self.assertTrue((ROOT / f".claude/agents/{role}.md").is_file(), role)
    self.assertTrue((ROOT / f".codex/agents/{role}.toml").is_file(), role)
```

THREE top-level statements: assignment, equality, loop; TWO loop-body assertions. One literal AGENTS text read via helper26–27. Regex scans prefix before FIRST literal `### 2.3`, using split without maxsplit/anchor; absent delimiter means whole text, not IndexError. Regex is not Markdown/table parsing; `\w+` is Python regex behavior, duplicates collapse via set, ordering unspecified. Exact equality requires five names, then four non-orchestrator roles generate eight `.is_file()` checks: source-derived expectation of NINE assertion visits within ONE test only after actual successful execution. No observed candidate runtime/count/probe occurred in handoff.

Fresh source grep finds five matching role links in AGENTS51–55, before first delimiter59. Reinspect actual prefix/all regex matches and captures before approval. Inventory lists eight current paths: .claude/agents/{analyst,implementer,planner,reviewer}.md and .codex/agents/{analyst,implementer,planner,reviewer}.toml. `is_file` checks file presence/type (and can follow symlinks); it does NOT read registration contents/parse TOML/execute agents. No .ai/agents role-document contents are direct reads. Exact role-set equality prevents empty-prefix vacuity unlike5n.

## Proposed scope and new oracle — NOT approved

Suggested SEVEN ordered patterns:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
AGENTS.md
.claude/agents/**
.codex/agents/**
```

Conservative production/import/lazy/decorator scope and two registration subtrees include unused/future supported descendants and file-byte changes even though the selected method only probes file presence. Extra invalidation requires D2 approval. Smaller explicit8registration-file closure is an alternative; do not silently choose. AGENTS is required literal; globs do NOT enforce nonempty/presence. Preserve check_paths292–316 behavior, no new exporter refusals. Missing tracked paths can fail exporter inventory validation; to isolate selected is_file failure, remove the disposable path's index entry as well, then restore bytes/index/read-confirm. Do not transfer5n empty-tree outcome: selected exact role-set equality and eight is_file checks define different failure paths.

Independent new oracle resolves exact method/class, AGENTS literal, regex/findall/set, split/index0 semantics, exact five-role set, subtraction/orchestrator exclusion, two f-string path/type/assertion bindings and order. NOT5n dynamicrglob/splitindex1/name/description oracle; NOT5m fourread/analyze/Passes oracle or5l encoding/5k row oracle. Review new method/setup pins independently, without catalog/source-under-test regeneration.

Reinspect ROOT/import/text, disk_tmp/calledscratch.require_disk, lifecycle eager/lazy, review_guard/ledger/protected/nesteddecorate/class construction. Previous14reached locations reference only; any newly claimed reach needs confirmedbytes/absentdatafailure/supplieddataexactlyONEpass/intendedboundaryreject. AST insertion afterdocstrings/beforeearliestdecorator; restore/read-confirm originals before nested fixtures deleted. Uncalled bodies remain conservative pins.

## Fresh-chat analyst decisions before approval

Use spec skill and REQUIRED read-only analyst delegation with bounded analyst/Python sections. Draft ignored specification-5o.md (or named equivalent) and present consequential D1–D4 in the FRESH chat:

- D1: Exact role-registration method/ID only; reconfirm any obsolete negatives and preserve symlink/refusal controls. Recommend exact method/ID, no negative change unless newly discovered/explicitly approved.
- D2: Seven conservative ordered patterns/extra invalidation, independent prefix/regex/set/is_file oracle and reviewed setup pins, or smaller justified closure? Recommend seven with inventory/runtime/presence-only limits.
- D3: Independent actual-one and observed prefix/five-role/eightprobe baseline; framework/adopter identities/freshness across AGENTS, eight registration paths, source/helper/production/new supported descendants; argv/ordereddeclarations/receiptexclusions; fresh reach; failure/control counts and semantic cases DERIVED BEFORE approval. Source suggests role-equality and eight is_file failure sites, but NO failure/control count approved here. Derive duplicate/absentmarker/firstmarker/outofcapture/extra-or-missing-role/earlier-equality-isolation, path-only export, missingtracked-versus-absentinventory, symlink/directory behavior and targeted byte-only extra invalidation before spec approval. Do not count arbitrary nonzero/export refusal as selected assertion failure.
- D4: Preserve all14complete profiles/mechanisms/manualadoption; only explicitly approved narrow negative/cardinality updates; claims limited to regex/set/extraction and registration-file presence plus declared freshness, excluding agent registration correctness/content/role execution/governance/native/model/session. Recommend yes. Newfixturebaseline14/currenttotal15; preserve10/11/12/13baselines/exact guards.

Explicit HUMAN SPEC approval, THEN SEPARATE PLAN approval before implementation. Nonexecuting analyze/trace allowed during drafting. Consequential unresolved scope returns to user, never hidden in a plan.

## Restrictions and fresh-chat prompt

Initial scope: read-only context/source and ignored spec drafting ONLY. No product tests/runtimecandidateimport/implementationplan/sourceedits/nativeormodelevaluation/sessionregistration/allocation/fixturetrust/historicalrescoring/evidencemodifications/newworktree/knowledge/commit/push/PR/merge/baserefresh/autonomydriver. Native allocations remain consumed.5n delivery authorization fulfilled and does not carry forward.

Suggested prompt: Read handoff-5o FIRST then authoritative Delivery complete in implementation-5n. Every command explicit designated cwd, existing checkout/branch only. After framework context start freshL2--new; required read-only analyst drafts role-registration specification and presentsD1–D4. Independently derive prefix/regex/set/pathpresence semantics, baseline observation/counts, failure/control matrices and conservative invalidation boundaries before asking SPEC approval, then separate PLANapproval. Do substantive work only in this fresh chat; preserve14profiles and all previous evidence.

## Handoff checks

check-ignore on handoff/report → exit0/both ignored; git diff --check → exit0; tracked status empty. Framework affected on both ignored docs → exit1/no bundle: synchronization INAPPLICABLE, no records PASS. Delivery ls-remote separately confirmed matching02dd97586873f24a604224aa5ad186a60c4104e7. Local context afterward reports equal local upstream refs/clean tracked state with remote_verified false (no extra remote check). No candidate runtime/import/probe/product suite ran during handoff. Handoff/report remain local/ignored/UNCOMMITTED.
