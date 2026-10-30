# Final5 local validation

Source tree: `d9004a92fd67d8291856395496f3652ce13569635bf75bb67e3c2c91bcf7dce1`.

Sealed baseline: 59 tests passed. Artifact bundle `/home/enramosjr/Projects/agentic/.git/okf-scratch/qualified-y18nwkhf`, SHA-256 `f1749a736f92014adea5a0ee2b44f4e6c7c1e874cb98a24a86facb3012074dde`; 143 declared KIT/test-driver inputs.

Initial mutation gate `assurance-2-mechanical-mutations-final5` exited 1: 26 valid kills and two INVALID classifications. Its `mechanical-review-mutations-2-final5.json` remains unchanged. The two helper mutants actually produced unittest assertion failures, but the original harness searched all output for setup-error strings; the assertion's giant filesystem dictionary included source text containing those strings, and the 6500-character tail omitted the traceback header.

Only those two existing sealed helper variants were rerun under corrected ignored diagnostic code, ledger `assurance-2-mechanical-helper-controls-final5`, exit 0. Every sealed file was reverified against the original variant SHA before launch; the initial report had already confirmed the exact changed helper bytes. Anchored real exception/result lines reject actual setup errors. Complete outputs are preserved. `mechanical-helper-controls-2-final5.json` proves:

* Policy/history omission fails `self.assertNotEqual(snapshot(), before)` at test line 437.
* Blanket capture exclusion fails `self.assertNotEqual(snapshot(), policy)` at test line 440.

Both executed one test, failed with `AssertionError`, and had no real import/setup error. Baseline and prior 26 valid controls were reused; no original invalid classification was rescored into PASS.

The authorized integrated gate then ran once:

```sh
python3 .ai/scripts/lifecycle.py run assurance-2-mechanical-framework-final5 -- python3 docs/assurance/capture-validation-output-2.py docs/assurance/mechanical-framework-2-final5-full.log -- python3 .ai/scripts/run_tests.py -j 8
```

Exit 1. Complete actual summary: `Ran 798 tests in 99.8s with 8 workers: FAILED (failures=1)`.

Sole failure: `test_autonomy.DriverTests.test_unfinished_background_audit_is_reaped_at_session_end`, test line 993, `self.assertTrue(not proc.exists() or proc.read_text().split()[2] == "Z")`, `AssertionError: False is not true`. Complete output is `mechanical-framework-2-final5-full.log`. All earlier final4 failure/error groups pass in this integrated run.

Read-only source diagnosis: `autonomy_driver.documentation_audit` starts a session, sends SIGKILL to its process group at cleanup, and waits only for the direct process. The test immediately checks the grandchild's terminal state. Signal dispatch plus direct-parent wait does not itself prove every descendant has reached a terminal state. Existing retained output does not establish whether this was a transient completion race or a persistent group escape. No automatic rerun or production fix was attempted by this validator.

No production, observer, scorer, historical result or acceptance assertion was changed. No native agent/model calls occurred.
