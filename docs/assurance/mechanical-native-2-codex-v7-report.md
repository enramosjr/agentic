# Codex v7 execution result

The explicitly approved command executed **once**, outer exit **0**, on frozen product tree `b0a6231f497622bd2243ab5118fae636860f33ec2f3529a949ed3f19c7ca7bf7`:

```sh
python3 .ai/scripts/lifecycle.py run assurance-2-real-agent --timeout 340 -- python3 docs/assurance/run-native-2-mechanical-codex-v7.py --authorized-allocation-and-scoped-trust
```

Actual strict result: **control-delta PASS, 1/1**, qualification true. The guarded `results-check --require-real` passed. Attempt `6356d9263be143c3abd7e8e3fd1e028c` completed with agent exit 0 and no failure reasons. This selected scenario is not the complete evaluator baseline or overall delivery authorization.

Charged agent time: **159.8329127790057 seconds**; elapsed attempt time: 160.61777571501443 seconds. The attempt initially reserved 300 seconds; final outstanding reservation is **0**. Effective evaluator limits were 300 agent-seconds / 324 wall-seconds, shrunk within the approved 330-second aggregate campaign envelope.

Actual parent session: `01a184d0-1dea-75c0-8f49-ba318f86911f`. Actual native reviewer child: `01a184d1-6481-74e3-aa7f-8754d9402bca`. Observed callbacks: SessionStart 1, PreToolUse 98, PostToolUse 97, SubagentStart 1, SubagentStop 1, Stop 1. Native configuration preflight retained 15 exact handlers and configuration SHA-256 `284deecf85f27373d91aa53619f74e5fbac9954c51aa162afda2b1c50cd9a561`.

Completed interval: `8eca8c82b94a4c8b83fadcd9a69f1bc8`. Native capture SHA-256 `962fa5e5d01bb9e66c340d6c4b961b847f9921cdf34b20285ad8ad8aa8983a47`; immutable completion SHA-256 `2c1df53f638cf1c39c55ef5621f9c314f4cfe9e63731e0208c6926e45829fadd`.

Captured canonical body, exported saved report and native Review receipt all hash to **`69d61a9e8c19adf77a963a87a6ef56b08f634c91323c7e1980a7f8cd157b2ade`**. The retained qualified final state includes L2 Verify at `2026-10-28T23:22:20Z`, citing passing app tests, records and both convergence requirements on fixture tree `0916fc292c66cb3134c19982496e245a12e1ac3e322bb56879fce3b845a12e91`. Full captured source/artifact/convergence/session pins are retained in the structured report and journal.

The native stream also records the active-review guard denying the parent's `python3 .ai/scripts/lifecycle.py --help` command during the reviewer interval. This conservative denial is an observed reader-availability limitation, not a strict result failure; the run does not establish that every reader is available during review. The denial was preserved without bypass, repair or rescore.

The native agent later recorded a Ship stage in the isolated evaluation fixture. That is fixture lifecycle administration, not delivery of the shared source worktree. The source worktree was not committed, pushed, merged or given a PR by this execution.

Exact evidence:

* `mechanical-native-2-codex-v7-report.json`: actual status, settled budgets, final message, raw paths, report-hash comparison and complete captured pins.
* `operator-2-mechanical-codex-v7/codex-results.json`: unchanged strict evaluator result/provenance.
* `operator-2-mechanical-codex-v7/retained/codex/qualified-final-state.json`: native Review/Verify receipt.
* `operator-2-mechanical-codex-v7/retained/codex/mechanical-capture/`: original journal, exported report and lifecycle state.
* `operator-2-mechanical-codex-v7/retained/codex/live-capture/`: original native stream, events and preflight.
* `mechanical-native-2-codex-v7.log` and `.log.exit`: complete outer stdout/stderr and exit.

No retry, fallback, additional native query, source/operator/scorer edit, persistent trust change or delivery action followed execution. Claude's earlier original-source PASS and all historical failed attempts remain unchanged. Overall lifecycle Verify/Ship is left to the parent task.
