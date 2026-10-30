# Spec: static installer-documentation input profile

Approved by human:enramosjr in this chat on 2026-10-29 America/Chicago: “Approved. Proceed with the implementation plan for 5e using the recommended D1–D4 decisions.” L2; analyst role; Python principal engineer. Specification and recommended D1-D4 are approved; implementation requires a separately approved plan. Acceptance commands name future checks, not execution results. No product tests have run for this slice.

## Problem and outcome

Maintainers have four literal Python input profiles but no profile for the existing method-selected installer-documentation check. Add one explicitly adopted profile through the existing exporter, with reviewed repository inputs and controlled freshness evidence. This framework has no knowledge bundle or structured capability baseline; this standalone specification creates neither and revises no historical evidence.

## Users and scenarios

A maintainer invokes the exporter from the repository root for exactly:

```text
python3 .ai/scripts/tests/test_lifecycle_conformance.py Distribution.test_readme_and_playbook_document_the_installer
```

Proposed ID: `python-installer-doc-contract`. The method checks `.ai/scripts/install.py` within the README's Quick start section; five playbook text terms (`--check`, `--force`, `--no-knowledge`, `conflict`, `/hooks`); and VERSION using `assertRegex` with `r"^\d+\.\d+\.\d+\n$"`. This is the actual Python regex, not full semantic-version validation or a promise of exactly one final newline. It does not execute documentation commands or the installer. Exactly one actual passing test is a future acceptance expectation, not a result inferred from method selection.

Approved ordered scope:

```text
.ai/scripts/**
!.ai/scripts/tests/**
.ai/scripts/tests/test_lifecycle_conformance.py
.ai/scripts/tests/disk_tmp.py
.ai/README.md
.ai/docs/install-and-upgrade.md
.ai/VERSION
```

The first pattern conservatively covers production eager imports and lazy-loader setup, including unused non-test descendants and future supported scripts. Extra invalidation is deliberate; this method copies no scripts. Ordered exclusion then restores the selected test module and imported helper. The final three literals are direct reads; VERSION is a non-Markdown text input. The unselected sibling Distribution method imports installer/evaluator code, inventories real kit files and prepares fixture distribution files. Those behaviors do not belong to this exact-method claim.

## Requirements

- R1: The exporter MUST register only the exact repository-root argv above as `python-installer-doc-contract`. Full class/module, sibling method, discovery, option, alias and other-interpreter variants MUST remain unregistered unless already registered. All four delivered profiles MUST retain their IDs, argv, ordered inputs, rationales and behavior.
- R2: The profile MUST export exactly the seven ordered patterns above before positive supplements, with a rationale for each pattern distinguishing conservative import/setup scope, test exclusion/restoration and the three direct text reads. An independent source-derived oracle MUST cover the selected method, direct reads, called `text(path)` body, eager initialization, called `require_disk`, lazy-loader setup and protected-wrapper construction. It MUST require review on dependency-boundary drift and prove rejection of confirmed reachable additions, rather than relying only on positive sentinels. Unrelated tests/documents MUST remain excluded. Conservative scope MUST NOT imply copied scripts, execution of unselected methods or universal read discovery.
- R3: Public text/JSON export MUST preserve existing token/Inputs/rationale parity, supplement order, root/path/inventory validation, nonexecution and refusal behavior. Export MUST neither import/execute the selected test nor semantically validate documentation or VERSION contents, adopt Inputs or record evidence. Each missing required literal and unsafe/unsupported path or unknown command MUST refuse nonzero with a reason and no usable candidate. Existing files with failing text/format assertions remain the selected check's responsibility.
- R4: Adoption MUST remain explicit, advisory and manual. Existing inference, full-suite coverage/refusal, matching, freshness, report schemas, gates and producer receipt exclusions MUST remain unchanged. Guide documentation MUST name the exact command/ID, static documentation-token and numeric-version-regex claim, conservative invalidation and runtime/read-completeness limits. It MUST NOT claim installation/upgrade behavior, real conflict/drift handling, hook/trust activation, semantic-version compatibility, native/model/session qualification or VERIFIED evidence from export.
- R5: An isolated framework fixture MUST drive public export and real lifecycle run/reuse for the selected command. Independent captured unittest output MUST prove exactly one test executed and passed before exit interpretation; subtests MUST NOT count as separate tests. Recorded argv, ordered inputs and exit MUST match export, and selected repository bytes MUST remain unchanged during execution. Evidence MUST REUSE unchanged and after unrelated test/non-input document edits; it MUST RERUN after separate conformance-preserving edits to each of the three direct text inputs, target, disk helper, a representative production import and a new supported non-test script. VERSION freshness edits MUST use another matching numeric version and restore original bytes; format failure is separate. The invoking framework MUST acquire no knowledge bundle. Seven separate static-failure fixtures MUST make the actual selected command fail while path-only export still succeeds: remove the installer path token from Quick start, remove each of the five playbook terms independently, and replace VERSION with nonmatching text.
- R6: A separate ordinary adopter fixture MUST explicitly adopt public export, become VERIFIED after independently proven actual one-test execution, stay VERIFIED after unrelated test/document edits, and become STALE after each direct text input, target/helper, representative production import and new supported non-test script edit. Unmatched ordered declarations and command identity MUST yield UNVERIFIED under existing rules; producer receipt exclusion MUST remain effective. Five confirmed disposable broken variants MUST be rejected: omission of each of the three direct text inputs, loose command matching and acceptance of zero-test execution. Each omission MUST fail the intended freshness assertion while conformance-preserving edits leave the actual selected check passing. The zero-test control MUST ignore the selector in a disposable actual empty suite, independently confirm `Ran 0 tests`, and fail on count before interpreting the version-dependent exit status; an absent exact method yielding one loader failure is insufficient. Every control MUST confirm mutation bytes and its intended failure without altering historical evidence.

## Acceptance

Proposed classes below belong in `.ai/scripts/tests/test_assurance_inputs.py`; they do not yet exist for this slice. Missing classes, missing counts or missing end states fail acceptance. These commands MUST NOT execute during initial specification drafting. Boundary guards are conservative review guards, not general dependency discovery.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py InstallerDocProfileTests` checks exact ID/argv/root matching, variant refusal and unchanged IDs/argv/ordered inputs/rationales of all four prior profiles.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py InstallerDocDependencyTests` checks exact ordered scope/rationales, independent actual ledger selection, source-derived direct-read/import/called-body boundaries, unrelated exclusions and future supported non-test descendants. Confirmed variants MUST add reachable excluded reads/imports in the selected method, `text(path)`, imported helper and production initialization/called-helper boundaries; the selected command must still pass, but dependency review must fail for the intended reason. The final variant set must be justified against the inspected closure, including called and lazy/protected setup bodies, rather than copied by count from 5d.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py InstallerDocExportTests` checks public text/JSON parity, supplements, immutability and nonexecution, refusal for every missing required literal/unsafe boundary, and successful path-only export of existing nonconforming documentation/VERSION.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py InstallerDocCompatibilityTests` checks guide scope/limitations, preservation of all four profiles and unchanged inference/full suites, matching, schemas, gates and receipt behavior through existing mechanisms.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py InstallerDocFrameworkEndToEndTests InstallerDocFailureTests` checks independent actual one-test proof, byte stability, lifecycle identities and every framework reuse/invalidation outcome above, including valid-version freshness separately from seven intentional static failures. Remove all occurrences of each selected playbook term in its separate disposable fixture so another occurrence cannot mask the intended assertion failure. A valid VERSION freshness example is `0.1.1\n`.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py InstallerDocAdopterEndToEndTests InstallerDocControlTests` checks every adopter status/identity and receipt exclusion above plus five confirmed broken variants, including omission of VERSION as well as both Markdown inputs and independent actual-zero rejection.

## Constraints

Use the existing literal catalog/export mechanism, Python 3.9+, standard library and unittest conventions. No new options, schemas, normalization, loader, inference, adoption automation, gates or approval authority. Tracked plus supported nonignored untracked inventory follows existing ledger rules. Executable/runtime environment, temporary storage/mount state, ignored files and external mutable data remain outside the repository-file claim. Unresolved additional reads require review and retention of current scope.

Use only `/home/enramosjr/Projects/agentic-assurance-7`, existing branch `claude/assurance-increment-7`, delivered HEAD `bd34de90f4eb84c5be19d306418404e61a6985e5`. Keep all docs/assurance artifacts ignored, local and uncommitted. Preserve 5d's closed lifecycle, historical evidence and original source/runtime scopes; historical results verify no fifth profile. During drafting: no source edits, product tests, implementation plan, native/model evaluations, session registration/allocation, fixture trust grant, historical rescoring/evidence modification, new worktree, base refresh, knowledge bundle, commit/push/PR/merge or autonomy driver. Human spec approval authorizes planning only; implementation requires separately approved plan. Prior delivery authorization is fulfilled.

## Non-goals

Full class/module registration; other methods; changing installer/docs/VERSION contracts; running installation/upgrade or proving artifact compatibility; real conflict/drift behavior; hook/trust activation; native/model/session qualification; general read discovery; minimum input set; reduced full gates; automatic adoption; savings claims; implementation planning before spec approval.

## Assumptions

D1-D4 below are approved decisions. Static inspection establishes candidate scope only. Controlled future fixture evidence cannot establish universal dependency completeness or runtime portability. No historical PASS or REUSE is new-profile verification. Framework mode has no capability baseline to merge and no OKF bundle to initialize.

## Open questions

None. The user approved the specification and recommended D1-D4. Ready for planning only.

## Approved decisions

The recommended defaults below are approved; alternatives are retained as decision context.

- D1: Approve this exact method and ID `python-installer-doc-contract`, select another candidate, or stop expansion? Recommended: approve this candidate only. Registration breadth is a human contract choice.
- D2: Approve the seven ordered patterns and extra invalidation from conservative production-script scope, or require a smaller independently justified closure? Recommended: seven, with the stated limitations. Completeness is reviewed, not automatically discovered.
- D3: Approve R5-R6's framework/adopter matrix, independent one-test proof, seven static failures, five confirmed controls and the R2 reachable-boundary controls? Recommended: yes. This acceptance breadth is a scope decision and yields bounded repository freshness evidence only.
- D4: Approve explicit advisory/manual adoption, preservation of all four profiles/inference/suites/schemas/gates and static documentation/regex claims only? Recommended: yes.

## Investigation evidence

Nonexecuting inspection only:

- `test_lifecycle_conformance.py:15-27,30-65,297-298`: root/import setup, called text helper, exact three reads/assertions, broader unselected sibling behavior and direct unittest entry point.
- `.ai/README.md:6-17`, `.ai/docs/install-and-upgrade.md:1-27`, `.ai/VERSION`: current documentation tokens and current `0.1.0` version line inspected. No extracted command executed.
- `disk_tmp.py:10-20`, `scratch.py:11-25`, `lifecycle.py:41-66,1994-1995`, `review_guard.py:23-26,629-639`, `ledger.py:10-22`: analyst inspected eager scratch/review_guard/ledger imports, temporary-storage/mount effects, lazy setup and protected construction. Selected method accesses no lifecycle attributes. No additional non-script repository read was found through this static inspection; it is not universal proof.
- `assurance_inputs.py:17-88,146-197,205-240`: four literal profiles, exact argv matching, path-only validation and advisory public formats/limitations.
- `test_assurance_inputs.py:1107-1199`: delivered 5d method/setup/called-body guards and eight confirmed reachable variants are historical reference only; they do not establish this new boundary or verify this candidate.
- `handoff-5e.md` and authoritative leading `implementation-5d.md`: delivered state and restrictions preserved. `repo.py context --json` confirmed framework mode, expected HEAD/branch and clean tracked state using local refs only; no remote verification or refresh.

## Draft validation

- `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5e.md` -> exit 1, only High open-questions finding for D1-D4. These are intentional human-approval blockers, not resolved assumptions. No other finding reported.
- `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5e.md` -> exit 0, six requirements traced. This validates structure only, not implementation or runtime behavior.
- `git check-ignore docs/assurance/specification-5e.md` -> exit 0, ignored path confirmed. Final `repo.py context --json` -> expected HEAD/branch, clean tracked state and local refs equal; no remote verification.
- Read-only analyst subagent independently confirmed the selected read/import/setup boundary and recommended six requirements, seven static failures, five controls and D1-D4. Python persona materially informed import-time effects, called-body coverage, actual regex semantics and independent test-count proof. No product tests, implementation plan or source edits occurred.
