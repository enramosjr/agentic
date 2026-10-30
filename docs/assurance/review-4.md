# Review: attested evidence in the assurance report (increment 4)

Independent review by the `reviewer` subagent of the uncommitted change on `claude/assurance-increment-4` (base `055b62f`). Saved by the implementer; the subagent has no write tool.

## Verdict

Approved

No Blocker or Major findings.

## Findings

- Nit: the symlink case of the review-ref traversal guard (`_review_target`) was untested. Addressed: `test_refs_outside_the_repository_are_skipped` now also covers a symlink inside the repository that points outside it.
- Nit: a record whose `review` stage is malformed, or whose JSON is unreadable, gives no note (the existing diagnostic covers an unreadable file). Accepted as the reading of R2 for unreadable records; pinned by `test_unreadable_record_contributes_nothing`.
- Nit: attestations are ordered by a string comparison of `at`, which is correct for the `Z`-suffixed timestamps stages write. Accepted.

## Validation Reviewed

- R1: SourceTests (active state, committed record, newest by stage time).
- R2: FailClosedTests (edited, verdict, audit, uncited, deleted silent, out-of-repo and symlink refs, unreadable record, note suppression).
- R3: PinTests.
- R4: LabelTests (nine-key set, text prefix, id not repeated).
- R5: NoUpgradeTests.
- R6: RiskSyntaxTests.
- R7: RiskSemanticsTests.
- R8: ExitCodeTests.
- R9: CompatibilityTests against the golden captured from the unmodified scripts.
- Parity and import graph: test_review_evidence.py.
- Mutation proof: 28 broken variants caught (one equivalent variant replaced).
