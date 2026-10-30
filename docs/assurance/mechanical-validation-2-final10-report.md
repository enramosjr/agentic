# Final10 root-help local validation

Approved frozen product tree: `3956d6137128443aaf5e0c4082ed9d4ff82f342091c76d818fdc6769246e6afd`.

Sealed full focused baseline: **68 tests PASS**. All **39 byte-confirmed sealed mutation controls killed**, including removal of the exact literal root-help exemption and a blanket `--help`/`-h` writer bypass. Assertions reject mixed commands, flag values, redirection, command substitution, interpreter options, unknown script paths and multiline/trailing-newline forms. All earlier 37 controls remain passing; setup/import/zero-test failures are not kills.

143 declared KIT/driver files. Artifact `/home/enramosjr/Projects/agentic/.git/okf-scratch/qualified-sp1dk82n`; manifest SHA-256 `fe2fcdd5eb9ac87a368b0c0073d202b0928d84e1ec54cb1cb82574be236853c0`.

```sh
python3 .ai/scripts/lifecycle.py run assurance-2-mechanical-mutations-final10 -- python3 docs/assurance/capture-validation-output-2.py docs/assurance/mechanical-review-mutations-2-final10-full.log -- python3 docs/assurance/mutate-mechanical-review-2-final10.py --ready
```

Exit 0. Complete results, per-variant logs and summary remain in the `mechanical-review-mutations-2-final10` evidence files.

After independent Approved review and root's frozen-candidate GO:

```sh
python3 .ai/scripts/lifecycle.py run assurance-2-mechanical-framework-final10 -- python3 docs/assurance/capture-validation-output-2.py docs/assurance/mechanical-framework-2-final10-full.log -- python3 .ai/scripts/run_tests.py -j 8
```

Exit 0. Actual full output: **Ran 807 tests in 98.6s with 8 workers: OK**. Prior final9 gate reuse returned RERUN because source inputs changed. Only one full framework gate ran for this candidate; root owns separate convergence.

```sh
python3 docs/assurance/preserve-native-codex-v7-help-fix.py after
```

Exit 0: **17/17 original v7 evidence files have identical SHA-256, modes and sizes**, no changes. The after-manifest binds before-manifest SHA-256 `9dba9366522cee39ba48de18b1adffcda2251902f93b2a09159128d99d6c6df7`. Both manifests preserve exact UTC comparison timestamps. Original qualified v7 report/result, outer log/exit, raw stream/events/preflight, canonical saved report, state, journal and capture/completion/publication receipts remain untouched.

Structured summary `mechanical-validation-2-final10-report.json` records current source identity, actual counts, precise ledger commands/timestamps/durations and preservation comparison timestamp. No native/app-server/model query or attempt, new attempt preparation, product source edit, historical evidence change or delivery action was performed by this validator. The local help fix does not retag original v7 native execution as a new current-source run.
