# Spec: Portable installed-kit qualification and safe hook upgrades

## Problem and outcome

The controlled disposable ISARS qualification reports 57 failures in four
source-linked groups. Fix historical Git assumptions, installed AGENTS marker
overhead, tracked-only preservation snapshots and redundant legacy hook matchers
without weakening tests or losing adopter content. The source evidence and exact
failed-run inventory are in
[the recovery dossier](../../docs/assurance/isars-qualification-recovery.md).

Authorization is the user's direct instruction in this chat: “Continue. Fix the
four remaining qualification issues without weakening tests or discarding adopter
content. Keep live ISARS unchanged and do not retry publication.” The requirements
below express those authorized outcomes; the plan supplies bounded engineering
choices. This does not authorize live adoption or publication.

## Users and scenarios

Maintainers installing or updating the kit; developers running distributed tests
before committing installation changes; and agents qualifying an isolated adopter
without framework Git history or live hook activation.

## Requirements

- R1: Historical assurance comparisons MUST use bundled immutable baselines with original revision/path/hash provenance and work without framework Git history. Existing profile comparisons, exact-command restrictions and mutant checks MUST remain enforced. Missing or corrupted baseline data MUST fail closed; tests MUST NOT regenerate the oracle from current production profiles.
- R2: Canonical AGENTS and its marker-wrapped installed form MUST remain strictly below 30,000 UTF-8 bytes. The existing strict assertion MUST remain unchanged. Source shortening MUST preserve headings, normative requirements and meaning; adopter content outside managed markers MUST remain unchanged.
- R3: Protection snapshots MUST include nonignored installed additions while still protecting tracked files, including tracked ignored files. They MUST detect content changes and disappearance without staging or committing the installation. Existing preservation assertions MUST remain enforced.
- R4: The installer MUST eliminate the redundant legacy managed matcher when the desired matcher is its strict superset of validated literal tool names. Migration MUST require the same event, a manifest-owned command, identical complete single-hook lists and identical non-matcher group metadata. It MUST preserve coverage and be idempotent even if the expanded group already exists. Unknown regexes, non-subsets, custom options, mixed/adopter/prompt hooks and unrelated groups MUST remain unchanged; hook configuration MUST NOT be rebuilt wholesale.
- R5: An installed-artifact E2E MUST drive the supported installer in a history-free disposable adopter, keep additions uncommitted, exercise all four repairs and assert representative adopter preservation and install/check idempotence. The frozen installed candidate MUST pass the applicable complete framework suite with full output and exact exit capture.
- R6: The repair MUST retain historical failed evidence, preserve test strength, leave live ISARS unchanged, avoid publication retries, force, policy weakening and default-branch merges, and keep framework records outside a new knowledge bundle.

## Acceptance

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py InstalledBaselineTests` passes (new class), including history-free comparison, provenance, missing/corrupt fixtures and changed-current-profile controls. Existing compatibility/mutation assertions remain enabled.
- R2: `python3 .ai/scripts/tests/test_install.py InstructionsTests` passes, including a new actual marker-wrapped budget assertion. Review verifies the original strict budget, headings and normative clauses remain intact.
- R3: `python3 .ai/scripts/tests/test_assurance_measure.py ReportOnlyTests` passes, including new untracked content/change/disappearance controls and unchanged Git index checks; tracked protection remains required.
- R4: `python3 .ai/scripts/tests/test_install.py HookMergeTests` passes, including legacy-to-expanded migration, already-present expanded matcher, repeat updates and preservation controls for options, mixed hooks, prompts, regexes and non-subsets. The existing source HookDedupe assertion remains unchanged.
- R5: `python3 .ai/scripts/tests/test_installed_qualification.py` passes (new E2E). The complete installed-candidate suite subsequently passes once with full output/exit retention; no skips or exclusions are added to conceal failures.
- R6: Independent review compares the full diff, before/after inventories and actual evidence; rejects live writes, publication attempts, weaker thresholds/assertions, current-data-generated oracles, lost adopter content or unsupported success claims.

## Constraints

Use existing Python stdlib tooling and installer boundaries. Preserve manifest
format, default conflict behavior, permissions and all nonredundant adopter data.
Literal matcher inclusion is a finite token-set operation, never general regex
inclusion. Only a complete single canonical managed hook group can migrate.
Preserve the compatibility-sensitive numbered Stage 5 paragraph and its tests.
This is framework mode: do not create knowledge/. Historical failures stay intact.

## Non-goals

Live ISARS adoption; publication/PR edits; K-202; hook activation; global settings;
general regex normalization; importing framework Git history into adopters;
staging installed files to satisfy tests; broad governance cleanup.

## Assumptions

The direct instruction to fix these four observed issues authorizes their bounded
repairs and necessary regression validation. Oracle fixtures are extracted from
the same previously referenced revisions, with HEAD references pinned to the
pre-change source commit 43091ae42693646b25f09110d0e860b4f0560b99.

## Open questions

None. The conservative migration and preservation conditions bound the requested repairs.
