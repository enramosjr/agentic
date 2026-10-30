# Active-review root-help denial: diagnosis and local correction

L2 bugfix, Python principal engineer. The user authorized diagnosis/fix, required preserving v7 PASS, and prohibited another native attempt without approval. No attempt preparation or native execution is included in this task.

## Confirmed cause

V7's strict qualification PASS is unchanged. During its active interval, the parent called `python3 .ai/scripts/lifecycle.py --help`. The actual CLI's argparse root help exits before dispatch, producer admission and state locks. The shared hook/native classifier instead used `--help` as a lifecycle verb; unknown verbs are conservatively writers, causing this false denial.

The existing v7 candidate and its original immutable native evidence remain scoped to source b0a6231f497622bd2243ab5118fae636860f33ec2f3529a949ed3f19c7ca7bf7. The help correction is a later source candidate, not a retrospective change to the tested native source.

## Minimal correction

The shared classifier now recognizes only a complete three-token, literal Python invocation of `.ai/scripts/lifecycle.py` or this installed module's absolute lifecycle path, ending in exactly `--help` or `-h`. Normal Python executable names/paths and harmless quoting work. Interpreter options, extra operands, other scripts, compound commands, redirection, substitutions and multiline forms retain the existing classifier. A help token in an argument value or in a check command never exempts its producer. Other CLI help forms are outside this narrow exception.

No general READERS expansion, blanket help search, native lease exception, callback identity change, recovery change or report/candidate qualification relaxation was introduced. Actual read-only help acquires no writer lease or invocation ID and changes no protected state. Existing recognized mutations remain frozen.

## Test-first and review evidence

`lifecycle.py redgreen red -- python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py -k root_help_is_read_only` reproduced the old classifier returning True. The same command recorded GREEN after correction. The regression drives lifecycle hook, native Pre/Post handling for Bash/exec_command without invocation IDs, and the actual CLI during an active interval, asserting unchanged journal, lifecycle state and candidate pins.

`lifecycle.py run assurance-2-help-boundaries -- python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py -k help_flag_cannot` PASS. Chained recognized writers, attached/separate redirection, help used as stage/run data, interpreter options, alternate script paths, multiline and substitution cases remain denied. The subsequent trailing-newline case is included in the frozen candidate's full focused/acceptance validation.

Independent implementation review Approved, saved whole in implementation-2-review-enforcement-review-root-help.md and recorded. Diff check PASS; scan-diff reports0critical and6 helper-based H2 flags already reviewed in the broader implementation. Integration documentation is updated in `.ai/lifecycle.md`.

Framework knowledge synchronization remains INAPPLICABLE: okf affected reports no bundle, and no knowledge bundle was initialized. The existing immutable retrospective closure for lesson1 was retained/reconfirmed. The help-specific finding is recorded in this report.

## Completion evidence

Frozen corrected candidate:3956d6137128443aaf5e0c4082ed9d4ff82f342091c76d818fdc6769246e6afd. Final10 sealed focused baseline **68 tests PASS**, **39/39 byte-confirmed sealed controls killed**, no INVALID/survivor.143declaredKITfiles, artifact qualified-sp1dk82n SHA256fe2fcdd5eb9ac87a368b0c0073d202b0928d84e1ec54cb1cb82574be236853c0. Current convergence **8 PASS/0 FAIL/0 MANUAL**. Full framework final10 **807 tests PASS in98.6seconds with8workers**, retained complete output mechanical-framework-2-final10-full.log. Audit/diff PASS, independent review Approved. No unchanged check was repeated after this passing candidate.

The before/after preservation check confirms **17/17 original v7 evidence files unchanged** in byte hash, mode and size; changed[]. See native-codex-v7-help-fix-preservation-before.json and -after.json, before-manifest SHA2569dba9366522cee39ba48de18b1adffcda2251902f93b2a09159128d99d6c6df7. The files include the original result/reports/logs, raw stream/events and native capture/qualified/report receipts. Historical native PASS/ERROR outcomes are not rescored. No new native attempt, model call, trust overlay, attempt preparation, source delivery or commit occurred. Current native qualification is not claimed for the later corrected candidate; v7 remains scoped to its original source. The requested diagnosis and local fix are complete.
