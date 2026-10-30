# Final9 local validation

Frozen product tree: `b0a6231f497622bd2243ab5118fae636860f33ec2f3529a949ed3f19c7ca7bf7`.

Sealed focused baseline: **66 tests PASS**. All **37 confirmed sealed mutation controls killed**, comprising the prior 33 controls plus restored sandbox-local status liveness filtering, restored enable/restart liveness filtering, omitted captured-runtime identity checks, and omitted configuration equality checks. The enable-filter mutant fails at the actual enable-success call with the expected erroneous ReviewError; it is classified only by that exact semantic traceback. Import/setup/zero-test failures are not kills.

143 declared KIT/driver files. Artifact `/home/enramosjr/Projects/agentic/.git/okf-scratch/qualified-24yc_r7g`; manifest SHA-256 `35ffd3da8180cde3172a726feca3fb19632e63a66623ea7f92fc9f6cdd430709`.

```sh
python3 .ai/scripts/lifecycle.py run assurance-2-mechanical-mutations-final9 -- python3 docs/assurance/capture-validation-output-2.py docs/assurance/mechanical-review-mutations-2-final9-full.log -- python3 docs/assurance/mutate-mechanical-review-2-final9.py --ready
```

Exit 0. Full result and summary: `mechanical-review-mutations-2-final9.json`, `mechanical-review-mutations-2-final9-summary.json`; every variant's complete output is referenced and retained separately.

After independent Approved review and explicit frozen-candidate GO:

```sh
python3 .ai/scripts/lifecycle.py run assurance-2-mechanical-framework-final9 -- python3 docs/assurance/capture-validation-output-2.py docs/assurance/mechanical-framework-2-final9-full.log -- python3 .ai/scripts/run_tests.py -j 8
```

Exit 0. Actual retained output: **Ran 805 tests in 97.9s with 8 workers: OK**. Outer log/exit and full output remain under the `mechanical-framework-2-final9` prefix. Prior fullgate reuse returned RERUN because source inputs changed; only one fullgate ran for this candidate. Root independently owns requirement convergence.

Subsequent authorization covered preparation only. Fresh Codex v7 namespace, source/operator/binary pins, exact namespace-only runner equivalence, actual current-KIT delta/live setup and unused markers are audited in `native-codex-v7-preparation-report.json`. No native CLI/app-server/model process, campaign, inference, source edit or delivery action was launched by this final9 validation/preparation work. Historical failures and Claude's original-source PASS remain preserved.
