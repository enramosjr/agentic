# Increment 5 investigation — Python validation inputs

## Implementation closeout — authoritative

Increment 5 is implemented, independently Approved and formally verified, uncommitted on source tree b52be33 at unchanged HEAD 5a0ee96. Seven requirement checks, all four confirmed source controls and the once-per-candidate full framework gate pass; retrospective closed with observation 1. See implementation-5.md and handoff-5.md. Historical drafting/planning checkpoints below are superseded. No native/model evaluation, trust grant or source delivery occurred.

## Approval and planning update — authoritative

The user explicitly approved the revised Python defaults and specification and requested an implementation plan for approval before coding. specification-5.md now records D1–D5 as approved, with no open questions. Spec analyze and trace both exit 0; Intent is recorded with human:enramosjr and lifecycle audit exits 0. The full plan is saved as plan-5.md; `lifecycle.py trace docs/assurance/specification-5.md --plan docs/assurance/plan-5.md` exits 0 with seven requirements traced. The plan has no open design decisions but awaits human approval, and its lifecycle stage is not recorded. Current status: Intent complete; Plan/Review/Verify pending. Source remains clean; documents remain ignored/uncommitted. No product tests, imports of target code, native/model evaluations or implementation ran. Historical drafting-state notes below are superseded by this update.

Revised drafting checkpoint, 2026-10-28 America/Chicago. The user explicitly requested Python framework code and actual validation commands, dropped the earlier adopter-language scope and requested decisions before implementation. Earlier unapproved increment 5 recommendations are superseded by specification-5.md.

## Source and authorization

All repository commands target `/home/enramosjr/Projects/agentic-assurance-7`, branch `claude/assurance-increment-7`, HEAD `5a0ee96136997772e89e978001441dfd7f1261aa`. Fresh `repo.py context --json` confirms clean tracked source, framework mode and equal local/upstream refs; this is not new remote verification. No new worktree was created. The authoritative delivery updates in handoff-3.md and implementation-3.md remain unchanged.

The existing increment 5 lifecycle remains L2 feature, no completed stages. Its original reason already describes an optional input-adapter contract; the revision changes the draft, not a previously approved spec. No human approval is inferred from the request to redraft. Spec skill and analyst role apply; read-only analyst delegation was reused. Python persona materially directs explicit input-boundary validation, public CLI verification, stdlib/Python 3.9 compatibility and no import-time side effects in the exporter.

No implementation, test suite, native/model evaluation, import probe, fixture trust operation, evidence rescoring, commit, push, PR or merge was performed. Only source inspection and document consistency commands are appropriate at this point.

## Actual Python command surfaces

- `README.md:170`: documents `python3 -m unittest discover -s .ai/scripts/tests` with bytecode/temp environment settings. Those settings remain execution conditions, not argv profile guesses.
- `.ai/scripts/run_tests.py:1-5,24,36-45,75-93`: parallel runner uses unittest discovery and then one subprocess per class. Default discovery root is `.ai/scripts/tests`; `-j` controls worker concurrency, not test coverage. Calling `groups` to inspect coverage would import tests, so the proposed exporter must not call it.
- `docs/assurance/implementation-3.md:54` and delivery checkpoint: the completed full framework gate used `python3 .ai/scripts/run_tests.py -j 8`. Its prior PASS remains scoped to its original source/environment; it has not been rerun for drafting.
- `.ai/scripts/tests/test_assurance_architecture.py:331-332`: has `unittest.main()`, so its existing direct-script class acceptance commands execute tests.
- `.ai/scripts/tests/test_run_tests.py:1-33`: defines `RunnerTests` but has no main entry point. Direct execution of that file is not a valid check. The proposed pilot instead uses the focused discovery form `python3 -m unittest discover -s .ai/scripts/tests -p test_run_tests.py`. This exact focused invocation is proposed, not claimed to have run historically or in this task.
- `.ai/scripts/ledger.py:55-70` and `.ai/scripts/lifecycle.py:994-1008`: existing defaults infer explicit broad `**` for unittest and the parallel runner. Unknown commands retain existing no-inference behavior. The new exporter need not change those defaults.

## Concrete read dependencies

| Source inspected | Repository dependencies and scope implication |
| --- | --- |
| `.ai/scripts/tests/test_run_tests.py:9,25-29` | Imports disk_tmp; executes run_tests.py by path in a generated temporary test suite. Import-only closure misses the subprocess script. |
| `.ai/scripts/tests/disk_tmp.py:10-20` | Imports scratch and configures temporary storage, potentially creating a fallback directory on import. The exporter must inspect files without importing this helper. |
| `.ai/scripts/scratch.py:11-25` | Reads runtime mount/temp state. A repository-file scope does not certify environment or platform portability. |
| `.ai/scripts/tests/test_assurance.py:29-41` | Fixture copies every top-level script before initializing an adopter repository. Narrowing to imported assurance/ledger modules omits actual copied inputs. |
| `.ai/scripts/tests/test_assurance_architecture.py:303-319` | Watches all script bytes, launches the architecture demo and checks `.ai/lifecycle.md`; non-code inputs affect the test. |
| `.ai/scripts/tests/test_lifecycle_conformance.py:26-65,68-75,125-145` | Reads docs, roles, skills, hook/registration and distribution files. Governance checks are not Python-only input sets. |

The pilot's candidate repository inputs are test_run_tests.py, disk_tmp.py, scratch.py and run_tests.py, using their full repo-relative paths. The actual selected test writes its child tests/helpers into temporary storage. This supports an inspectable first profile; it is not a proof of arbitrary file-read completeness.

## Existing evidence and file inventory semantics

- `.ai/scripts/ledger.py:32-48,73-91`: repo-relative ordered input globs; positive patterns add matches and negative patterns remove them. Git inventory includes tracked and untracked nonignored paths; arbitrary ignored/external data is not covered. In particular fnmatch semantics are not a portable filesystem-glob or Python import resolver.
- `.ai/scripts/assurance.py:63-64,113-138,378-390`: explicit Inputs, automatic existing receipt exclusion, exact argv and ordered input identity. Suggestion output is not evidence. Omitted Inputs and explicit `**` have different current scope/freshness semantics.
- `.ai/lifecycle.md:181-205`: existing declarations, statuses, explicit execution, evidence matching, report and gate contracts. No new framework capability bundle is needed to use lifecycle `run --inputs` and `reuse`.
- `.ai/validation-policy.md:17-27`: focused checks during work, broad gate at the frozen boundary, reuse on unchanged inputs. Exporting a focused scope does not authorize skipping a required gate or claiming a focused run covers the full suite.

## Recommended model and tradeoff

Use maintained command-to-input profiles with exact argv, ordered globs and read-dependency rationale. Export existing lifecycle input argv and optional Inputs declaration. Start with one pilot, retain broad full-suite commands, refuse unknown/unreviewed scopes, and keep application explicit. Profile completeness remains a review responsibility. This trades automatic discovery for reusable source-backed declarations and adds profile-maintenance cost; the user must approve that tradeoff.

No initial all-tests catalog, AST completeness claim, runtime tracing, generic language adapter, new trust schema, automatic inference change or measured project-wide speedup is proposed. The full suite's discovery and governance reads explain why a broad baseline remains necessary.

## Draft consistency checkpoint

Seven proposed requirements have seven future executable acceptance commands. No future acceptance test has been created or run. `python3 .ai/scripts/lifecycle.py trace docs/assurance/specification-5.md` exited 0: seven requirements traced. `python3 .ai/scripts/lifecycle.py analyze docs/assurance/specification-5.md` exited 1 with the sole High open-questions finding, requiring D1–D5 to be settled. Those decisions intentionally prevent Intent approval; they cannot be resolved by silently selecting defaults. No other finding was reported.

`git check-ignore docs/assurance/specification-5.md docs/assurance/investigation-5.md` exited 0 and named both ignored paths. `git status --short --branch` shows no tracked changes. No lifecycle stage was recorded or product verification rerun. Drafting is complete for user review; planning and implementation remain unauthorized pending decisions and approvals.
