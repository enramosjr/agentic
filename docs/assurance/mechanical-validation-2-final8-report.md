# Final8 local validation

Approved source tree: `5d42a15c9fb995ce09703be0121c5b31e6dd387e93d8733b8cc7dd34f0189516`.

Sealed baseline: 63 tests passed. All 33 independently byte-confirmed, sealed controls were killed by their semantic assertions, including the five new physical-witness/foreign-owner/index-object/common-directory/clean-environment controls. No import/setup/zero-test failure counted. Each complete output is separately retained in `mechanical-final8-qualified-*.log` and referenced by the report.

Artifact: `/home/enramosjr/Projects/agentic/.git/okf-scratch/qualified-vnqr2qye`; manifest SHA-256 `8d0099d9d87f21d278c42a50eb00b2c11c43eb9e173573e0a250de935d0cf6ff`; 143 declared KIT/driver inputs.

```sh
python3 .ai/scripts/lifecycle.py run assurance-2-mechanical-mutations-final8 -- python3 docs/assurance/capture-validation-output-2.py docs/assurance/mechanical-review-mutations-2-final8-full.log -- python3 docs/assurance/mutate-mechanical-review-2-final8.py --ready
```

Exit 0. Evidence: `mechanical-review-mutations-2-final8.json`, `mechanical-review-mutations-2-final8-summary.json`, `mechanical-review-artifact-2-final8.json`.

```sh
python3 .ai/scripts/lifecycle.py run assurance-2-mechanical-framework-final8 -- python3 docs/assurance/capture-validation-output-2.py docs/assurance/mechanical-framework-2-final8-full.log -- python3 .ai/scripts/run_tests.py -j 8
```

Exit 0. Actual retained output: `Ran 802 tests in 99.4s with 8 workers: OK`. Full output, outer log and exit file use the `mechanical-framework-2-final8` prefix.

The old Claude PASS remains bound to `a9e58f56be695f860d87a470fdf18b038e698c18a5982703bab939b088e7f409` and its exact frozen v5 operator. The complete source/mode comparison is `claude-scope-comparison-2-final8.json`. Only `.ai/lifecycle.md`, `.ai/scripts/review_guard.py`, and `.ai/scripts/tests/test_review_enforcement.py` differ. Within the guard, only `absolute_git_directory` (added) and `git_operation_roots` (changed) differ; other guard functions are byte-identical. Native adapter, deployed hook configurations, scorer and tracked observer bytes/modes are unchanged. This comparison supports a bounded scope decision; it does not retag old Claude execution as a current-KIT PASS or override conservative ledger reuse.

All earlier results remain intact. No production edits, native/appserver queries, model calls, delivery actions, or automatic retry were performed by this validator.
