# Spec: Attested evidence in the assurance report (increment 4)

Version: **0.1.0-draft**, 2026-10-27. Framework base: `cddca3f` (increment 1 merged). Tier: L2, kind feature.
Context: architecture §2 (provenance classes), §6 row 4. Untracked working file: the repository holds no documents.

## Problem and outcome

`lifecycle.py assure` reports MANUAL requirements as "human judgment" with no link to any judgment actually made, and has no place to record a known gap with an expiry. Reviewers cite manual checks only for task-spec ids, so a capability requirement `NS-R<n>` marked `Verify: manual` stays an unexplained MANUAL forever.

When this ships, the report shows, for a MANUAL requirement, the newest Approved review that cited it (with review hash, time and the record's claimed approver), and shows a time-boxed risk acceptance beside a STALE, FAILED or UNVERIFIED requirement. Both are labeled as judgment. Neither changes any status, `basis` value or exit code. Only mechanical evidence produces VERIFIED; a claim never upgrades a status.

## Users and scenarios

- A reviewer approves a change whose requirement CALC-R2 is `Verify: manual`, cites `CALC-R2` in `## Validation Reviewed`, and later `assure` shows who judged it, when, and on which review.
- A maintainer knowingly ships with CALC-R1 STALE and adds an `Accept-risk:` line with an expiry; `assure` shows it as active, then as expired after the date, still STALE.
- A later reader audits a report and must be able to tell measured evidence from judgment.

## Requirements

- R1: `assure` MUST report, for a MANUAL requirement `NS-R<n>`, its newest attestation: a lifecycle record (committed or active) with an object-valued, `ledger.audit`-clean ledger whose `review` stage has a `ref` that exists, whose `ref_hash` equals the recorded `sha256`, whose first `## Verdict` line starts with "approved" (case-insensitive), and whose `## Validation Reviewed` section cites `NS-R<n>` with the word-boundary rule of `converge_problem`. Newest is by the review stage `at`.
- R2: An attestation MUST NOT be honored, and MUST NOT affect output other than a non-failing note, when the record is unreadable or fails ledger audit, the review report is changed since recording, the verdict is not Approved, or the id is not cited. A missing review report leaves no observable citation: it is silently not honored and produces no note, so output stays byte-identical for repositories whose records point at gitignored or removed paths. Notes MUST NOT be diagnostics and MUST NOT change the exit code.
- R3: A citation MAY pin the requirement text as `NS-R<n>@<hex>` (at least 12 hex characters, a prefix of `brownfield.sha(block.raw)`). A matching pin MUST be honored; a mismatching pin MUST NOT be honored and MUST yield a note "requirement changed since attestation"; an unpinned citation MUST be honored with `pinned: false` and a reason stating it is not bound to requirement text.
- R4: An attestation MUST be labeled as judgment. In JSON the requirement gains an `attested` object, present only when an attestation exists, with `basis: "attested"`, `judgment: true`, `record`, `review` (repo-relative ref), `review_sha256`, `at`, `intent_approved_by` (the record's intent `approved_by`, or null; a claim, not authenticated), `pinned` and `reason` (for an unpinned citation, that it is not bound to requirement text; null when pinned). In text output it is an indented line that starts with `judgment (attested, not verified):` and does not repeat the requirement id.
- R5: Attestation MUST attach only to MANUAL requirements. A cited FAILED, STALE, UNVERIFIED, INVALID, VERIFIED or UNDECLARED requirement MUST keep its status and gain no `attested` key. No requirement's status MAY become VERIFIED through attestation, and the top-level `basis` MUST never be `attested` (a MANUAL requirement stays `declared`).
- R6: A requirement block MAY declare `- Accept-risk: YYYY-MM-DD by human:<id>|decision:<ADR> - <reason>` before its first scenario, at most once. A malformed date, a missing or malformed `by`, an empty reason, a duplicate, or a line after a scenario MUST make that requirement INVALID with the reason named, the same fail-closed treatment as `Verify:` and `Inputs:`.
- R7: For a STALE, FAILED or UNVERIFIED requirement with a valid `Accept-risk:` line, `assure` MUST report `risk_acceptance` `{basis: "declared", until, by, reason, state}`, with `state` `active` while `until` is on or after the current UTC date and `expired` after. The status stays unchanged in both states. The `by` value MUST be rendered as a claim. On other statuses the line is ignored and no key is added.
- R8: Exit codes MUST be identical with and without attested or risk-acceptance input, except the INVALID of R6; `--strict`, `--changed` and `--json` behavior and `summary` counts MUST be unchanged, and `--changed` MUST show attestation and risk acceptance only for the requirements it lists.
- R9: With no attestation citation and no `Accept-risk:` line, JSON and text output MUST be byte-identical to the output before this change, and `schema_version` MUST stay 1. The report MUST remain read-only, and `stage`, hooks, gates and `okf.py validate` outcomes MUST be unchanged.

## Acceptance

- R1: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_attested.py -k SourceTests` passes (an Approved review citing CALC-R2 yields the `attested` object with the review hash and time; the newest of two wins; works from a committed record and from the active state).
- R2: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_attested.py -k FailClosedTests` passes (an edited report, a "Changes requested" verdict, an uncited id and a ledger-audit-failing record each give no `attested`, only a note, and an unchanged exit code; a deleted report gives no `attested`, no note and output byte-identical to the no-input output).
- R3: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_attested.py -k PinTests` passes (match, mismatch after editing the block, unpinned label).
- R4: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_attested.py -k LabelTests` passes (exact nine-key JSON set, `basis` inside the object is attested, `intent_approved_by` null and present, text line prefix, id not repeated).
- R5: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_attested.py -k NoUpgradeTests` passes (an Approved review citing a FAILED, a STALE and a VERIFIED requirement changes nothing; MANUAL stays MANUAL with top-level basis declared).
- R6: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_attested.py -k RiskSyntaxTests` passes (valid forms, and each malformed form listed in R6 gives INVALID with a reason).
- R7: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_attested.py -k RiskSemanticsTests` passes (a future date is active, a past date is expired, status unchanged in both, ignored on MANUAL and VERIFIED).
- R8: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_attested.py -k ExitCodeTests` passes (the exit code and `summary` of one fixture compared with and without attested and risk input; `--changed` filtering).
- R9: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance.py` passes unmodified, and `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_attested.py -k CompatibilityTests` passes (byte-identical output for input-free fixtures; no files written; `schema_version` 1).

Each new test class is shown to fail against a deliberately broken variant before acceptance (`AGENTS.md` §8.6).

## Constraints

- Standard library only, Python 3.9+. Report-only: no new gate, hook, stage or `okf.py` rule, and no `stage verify` change; `assure --run` is untouched.
- No existing outcome changes for repositories without the new inputs (R9). Existing test key sets stay valid because the new keys are conditional.
- Semantics of the review hash, verdict and citation matching MUST equal `ref_hash`, `read_verdict` and the `converge_problem` regex; the implementation MUST NOT create an import cycle (`assurance.py` imports neither lifecycle nor its state).
- Records are read with the same integrity rules as ledger evidence; the report is computed from file content at read time.
- Framework source: no `knowledge/` and no new committed documents; `docs/` stays untracked. Editing the existing shipped `.ai/lifecycle.md` and its conformance test is allowed (as in increments 1 and 6).

## Non-goals

- Authenticating approvers or granting authority; `by`, `approved_by` and review verdicts stay recorded claims.
- Any gate on attestation, or a status for "attested" requirements.
- Attestation for non-MANUAL requirements, LLM-generated links, or claimed material (agent notes, log text).
- A separate approvals listing, a risk register, renewal or automatic expiry actions, or a cap on the expiry window.
- A new store, a CLI to write attestations or risk lines, or changes to `converge` for capability ids.

## Assumptions

- Replaces "what stable key links an attestation to NS-R<n>?": a reviewer cites the capability id in `## Validation Reviewed` of an Approved review report that a lifecycle record's `review` stage references. It reuses the existing review and citation machinery; task ids `R<n>` never collide with capability ids.
- Replaces "does an attestation bind to the requirement text?": an optional pin, `NS-R<n>@<12+ hex>`, a prefix of `brownfield.sha(block.raw)`. Unpinned is honored but labeled. Editing a block, including adding an `Accept-risk:` line, invalidates pinned attestations of it, which is intended.
- Replaces "what is risk acceptance?": an in-block `Accept-risk:` line with an expiry date and an unauthenticated `by` claim, with no cap. Today is the UTC date; tests use far-past and far-future dates, so no clock injection is needed. It documents a known gap and never hides or downgrades a status.
- Replaces "may attested evidence change status or exit codes?": no, except that malformed `Accept-risk:` syntax is INVALID.
- Replaces "how much of approvals is shown?": only the record's intent `approved_by`, as a claim, on each attestation.
- Only the newest attestation per requirement is reported. A review report absent from the working tree (for example scratch paths in framework source) is not honored and gives no note.

## Open questions

None.
