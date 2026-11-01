# Implementation Plan: Portable adopter qualification without lost content

## Objective

Implement the [four requested repairs](../specifications/adopter-qualification-fixes.md)
without weaker tests, discarded adopter content, live ISARS changes or publication.
L2 Python bugfix; the user's direct repair instruction authorizes this bounded plan.

## Success criteria

- R1: Immutable historical comparisons work without framework Git history and fail on corrupted/missing oracles and changed actual profiles.
- R2: Source and marker-wrapped AGENTS meet the unchanged strict 30,000-byte limit; headings, normative clauses and adopter bytes survive.
- R3: Protection includes tracked and nonignored untracked installed files and detects mutation/deletion without staging.
- R4: The known managed matcher expansion yields one canonical registration while custom and unsupported shapes are preserved.
- R5: A real history-free, uncommitted adopter install passes connected checks and one complete installed-copy suite with full capture.
- R6: Evidence is truthful, historical failures remain, and live ISARS, publication and policy are untouched.

## Current state

The controlled installed suite failed with 57 records: 35 Git-baseline lookups,
20 AGENTS-budget/preflight failures, one tracked-only inventory assumption and
one retained old/expanded matcher pair. Complete evidence is in
`.git/okf-scratch/isars-workflow-adoption-rehearsal/evidence/`.

`test_assurance_inputs.py` reads baseline profiles from invoking HEAD and fixed
framework revisions, plus four historical lifecycle texts. Installation copies
files, not framework history. `test_assurance_measure.snapshot` inventories only
tracked files. The source AGENTS body is 29,950 bytes and markers add 70 bytes.
`install.merge_hooks` currently deduplicates exact matcher/command pairs and its
manifest owns commands rather than full previous hook objects.

## Proposed approach

Bundle independently verified pre-change raw baseline data and hashes; replace
only the Git acquisition portions of existing tests, retaining every comparison
and mutant check. Pin symbolic HEAD to pre-change commit 43091ae42693646b25f09110d0e860b4f0560b99.
Keep production changes to conservative nested-hook migration and shortening the
first nonnormative AGENTS sentence. Strengthen protection inventory to cached plus
nonignored untracked paths. Add connected installed-artifact regression coverage.

## Boundaries and invariants

No live ISARS writes, fetch, installation, commit, push or PR edits. No force,
policy weakening, guard disabling or default-branch merge. Preserve existing
manifest format, conflict and dirty-path refusals, adopter permissions, prompts,
custom hook options, instructions, application files and knowledge. Do not import
framework history or stage installation files to make tests pass. Preserve the
numbered Stage 5 paragraph and original strict budget/source hook assertions.

## Implementation steps

### Step 1: Immutable historical oracles are portable

R1, R5. Ownership: baseline implementer owns `test_assurance_inputs.py`, new
`compatibility_baselines.py` and new `tests/fixtures/qualification-baselines/` data.

Write `InstalledBaselineTests` first, demonstrating failure of representative
existing history-dependent comparisons in an installed, history-free target.
Extract exact data from every referenced pre-change revision/path, retaining
revision, Git blob identity and content SHA-256; verify against Git objects before
persisting. A raw-source container is acceptable and preserves original AST
parsing/comparisons. Replace only Git acquisition with a fail-closed fixture loader.
Never regenerate an oracle from current production code at test time.

Check missing/corrupt data refusal, profile mutation failure and representative
profile/paragraph comparisons; keep all existing compatibility/mutant assertions.

### Step 2: Marker-wrapped governance fits the same byte budget

R2, R5. Ownership: installer implementer owns `AGENTS.md` and installer tests.

Write an actual-install `InstructionsTests` budget case first; record RED at
30,020 bytes. Shorten only the first nonnormative introduction enough to save at
least 21 bytes. Keep headings and normative clauses verbatim and preserve custom
outside-marker content. Measure actual installed bytes, not an excluded subset.

Check original `AgentsBudget` and new installed strict budget plus export tests.

### Step 3: Protection covers uncommitted installation additions

R3, R5. Ownership: parent owns `test_assurance_measure.py`.

Add `ReportOnlyTests` controls first with tracked, tracked-ignored, nonignored
untracked and ignored-untracked fixture files. Assert the first three are covered,
the ignored-untracked file stays excluded, and mutation/deletion of an installed
addition changes the snapshot without changing the Git index. Keep existing
protected-file assertions. Use the union inventory
`git ls-files -z --cached --others --exclude-standard`, retaining bytes/link checks.

### Step 4: Safe matcher expansion avoids redundant dispatch

R4, R5. Ownership: installer implementer owns `install.py` and `test_install.py`.

Write actual legacy Write-to-Write-plus-Delete migration tests first. Require same
event, manifest-owned command, identical complete single command hook lists and
all other group metadata. Validate both matchers as finite literal tool-name
alternations; require a strict subset. Promote only an eligible redundant group;
if the desired identical expanded group is already present, keep one canonical
group. Preserve caller objects and event coverage.

Add preservation controls for unmanifested commands, regexes, non-subsets, changed
metadata/options, mixed/prompt hooks and unrelated groups. Keep every prior merger
test and the strict source HookDedupe assertion. No wholesale hook rebuilding.

### Step 5: A connected history-free adopter proves the repairs

R1–R6. Ownership: parent owns new `test_installed_qualification.py` and integration.

Create a real independent adopter Git repository with application/knowledge data,
outside-marker AGENTS text, permissions, prompts and an eligible old matcher.
Drive the supported installer; keep additions untracked. Assert representative
baseline compatibility, strict marker-wrapped canonical budget, inclusion of
installed additions, single migrated registration, preserved custom content and
successful read-only repeated check. Do not invoke recursive full discovery from
this E2E; only targeted installed checks are allowed inside it.

### Step 6: Freeze and qualify the actual installed artifact

R1–R6. Ownership: one validator owns the long gate; parent owns documents/evidence.

After focused checks and synchronization, run approved-spec convergence once.
Use its class checks rather than repeating them separately. Create a fresh
disposable target from pinned ISARS state; install the frozen source candidate,
binding source HEAD plus complete changed-file hashes and installed manifest.
Remove clone remotes and assert isolation/preservation. Do not install into live.

Run one complete suite on the installed target, using target-local scratch, normal
test-session cleanup, exclusive lock, retained session and complete stdout/stderr
capture. Keep exact argv, environment changes, exit, counts and log/artifact hashes.
Do not separately repeat an unchanged full framework suite: focused source checks
plus this integrated installed-copy full run cover both contexts. Recheck all
qualified input hashes and live/adopter inventories after the gate.

Obtain independent two-pass review against the spec and MANUAL R6. Close this new
task's retrospective after final results. Record Verify only when required checks
actually pass. Keep local artifacts; no publication operation is selected.

## Testing strategy

Record bugfix red/green using failing-closed new regression tests before repairs.
Validate historical fixture provenance against original Git objects; corruption
and actual-catalog divergence must fail. Use negative controls for missing/new
files and custom hook shapes. Never skip adopter failures, substitute current
profiles as expected values, raise thresholds or relax source hook counts.

Focused checks are new test methods/representative prior comparisons during
iteration. Convergence runs the broader acceptance classes once after completion.
The final installed full suite is the single integrated gate, not an edit loop.

## Validation commands

Set `PYTHONDONTWRITEBYTECODE=1`. Existing CLI forms with new classes/files named
in the spec:

```text
python3 .ai/scripts/tests/test_assurance_inputs.py InstalledBaselineTests
python3 .ai/scripts/tests/test_install.py InstructionsTests HookMergeTests
python3 .ai/scripts/tests/test_assurance_measure.py ReportOnlyTests
python3 .ai/scripts/tests/test_lifecycle_conformance.py AgentsBudget
python3 .ai/scripts/tests/test_installed_qualification.py
python3 .ai/scripts/lifecycle.py analyze .ai/specifications/adopter-qualification-fixes.md
python3 .ai/scripts/lifecycle.py trace .ai/specifications/adopter-qualification-fixes.md --plan .ai/plans/adopter-qualification-fixes.md
python3 .ai/scripts/okf.py affected
python3 .ai/scripts/lifecycle.py audit
```

Final gate from frozen installed target:

```text
python3 -m unittest discover -s .ai/scripts/tests -v
```

Record checks via lifecycle ledger; full child output is captured before lifecycle
tail truncation. Use supported supervisor and exclusive lock in one retained
session. Consult reuse before a repeat and justify changed inputs. Ambiguous
process state never authorizes relaunch. Load validation long-check rules first.

## OKF impact

Framework mode: record expected missing-bundle affected result; do not initialize
knowledge/. Update `.ai/docs/install-and-upgrade.md` with narrow migration and
preservation conditions, these spec/plan artifacts and qualification dossiers.
Keep full raw evidence/reviews in Git scratch and historical failed runs intact.

## Risks and mitigations

- Self-referential oracles: pre-change revisions, exact hashes and corruption controls.
- Lost custom hook behavior: strict single-group equality and literal subset eligibility.
- Budget content loss: only source introductory prose changes; normative/adopter text preserved.
- Volatile snapshot data: respect ignored-untracked boundaries while retaining tracked files.
- Different qualified payload: freeze and revalidate candidate/manifest hashes around the run.
- Duplicate or truncated execution: one validator, lock, retained session and full file capture.

## Out of scope

Live adoption, publication, K-202, PR edits, default-branch merge, global settings,
arbitrary regex normalization, imported framework history and staged adopter data.

## Open decisions

None. Ineligible custom groups are preserved rather than broadened or removed.
