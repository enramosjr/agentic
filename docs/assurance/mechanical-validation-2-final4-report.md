# Final4 local validation

Source tree: `f212b6b3ff2fc47949e2df10ac4c58a8c8ec11a8e40b3034eb63e14a9c15c4f1`.

The independently reviewed candidate passed its sealed baseline (57 tests) and killed all 25 byte-confirmed, independently sealed mutation controls. No import/setup/zero-test failure counted as a kill. Artifact bundle: `/home/enramosjr/Projects/agentic/.git/okf-scratch/qualified-216o924n`; SHA-256 `2f15dbae8aa65a9ac9561b65ca2281a410c130a921fe956c74e0c8c0bb6047f0`; 142 declared files include the valid installer template's complete KIT inputs.

Exact mutation ledger command:

```sh
python3 .ai/scripts/lifecycle.py run assurance-2-mechanical-mutations-final4 -- python3 docs/assurance/capture-validation-output-2.py docs/assurance/mechanical-review-mutations-2-final4-full.log -- python3 docs/assurance/mutate-mechanical-review-2-final4.py --ready
```

Exit 0. Reports: `mechanical-review-mutations-2-final4.json`, `mechanical-review-mutations-2-final4-summary.json`, `mechanical-review-artifact-2-final4.json`.

Exact framework ledger command:

```sh
python3 .ai/scripts/lifecycle.py run assurance-2-mechanical-framework-final4 -- python3 docs/assurance/capture-validation-output-2.py docs/assurance/mechanical-framework-2-final4-full.log -- python3 .ai/scripts/run_tests.py -j 8
```

Exit 1. Actual summary: `Ran 796 tests in 92.2s with 8 workers: FAILED (failures=16, errors=1)`. Full output is retained unchanged in `mechanical-framework-2-final4-full.log`; outer log/exit file: `mechanical-framework-2-final4.log`, `mechanical-framework-2-final4.log.exit`.

Actual failing groups:

* `test_scratch.ScratchTests.test_system_temp_symlink_is_rejected_without_fallback`: `FileExistsError` creating the test's `/tmp` symlink because setup's `okf git-setup` already created `.git/okf-scratch`.
* `test_brownfield_deltas.ReceiptRecoveryTests.test_third_state_refused`, and `MergeCliTests.test_apply_edited_spec_refused`, `test_invalid_log_destination_refused_before_receipt_or_target_write`, `test_preview_then_approved_apply_and_noop`: unchanged snapshot assertions detect review-journal/producer effects during refusal/no-op paths.
* `test_onboard.OnboardE2ETests.test_cited_drafts_validate_and_second_run_is_noop`, `test_preflight_refusal_before_initialization`, `test_reserved_index_directory_refused_without_initialization`: same review-state snapshot effect.
* `test_assurance.ExitCodeTests.test_run_with_report_flags_is_refused`: snapshot changes even though flags are rejected before the declared command runs.
* `test_worktree_hooks.WorktreeHookTests.test_invalid_explicit_workdir_denies_guarded_operation`: eight failed subtests. Invalid workdirs reach Git probes before existing workdir validation, or integer values raise uncaught `TypeError` at `review_guard.py:849`.
* `test_retrospectives.RetrospectiveTests.test_compatibility`: new early commit/PR state load raises `lesson numbers must be existing, unique and ascending`; hook exits 1 instead of emitting its deny response.

Read-only source inspection ties the snapshot failures to broad `producer` acquisition in lifecycle dispatch and OKF dispatch, before command-specific planning/refusal/no-op checks. The installer-specific equivalent was repaired before this candidate and its 49-test module passes. Existing assertions must remain strict; producer ownership should start at an actual effect, after pure preflight, and cover all subsequent writes. Mechanical workdir routing must preserve the existing explicit-workdir validation/deny behavior. The retrospective failure needs a structured hook denial for malformed state without allowing an opt-in bypass. The scratch fixture must construct its deliberately invalid scratch root before any setup that legitimately creates scratch.

No further suite run, model call, production edit, or waiver was performed by this validator. Prior evidence and all final4 output remain preserved.
