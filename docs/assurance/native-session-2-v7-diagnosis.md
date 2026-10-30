# Native session visibility: diagnosis and correction

L2 bugfix, Python principal engineer, continuing the approved R1–R8 mechanical-review spec and plan. No native campaign is authorized in this task; the user requested diagnosis, a fix and preparation only.

## Confirmed cause

V6 retained a native SessionStart registration but `review status` showed no sessions. Status and enable/restart both called `review_guard.stopped` on the captured host PID from inside a sandboxed command. The installed Codex sandbox uses a separate PID namespace. Host PID invisibility was misclassified as host death.

The model-free installed-sandbox diagnostic `python3 docs/assurance/diagnose-native-session-2-v7.py` confirmed this: PID725255/birth43257452 remained alive outside, while inside the sandbox its `/proc` identity was absent and stopped returned true. Host namespace pid:[4026531836], command namespace pid:[4026533058]. Exact argv/output is preserved in native-session-2-v7-visibility.json. This used a plain Python sleeping process and the local `codex sandbox` helper, not an agent, model request, authentication query or native qualification attempt. Official sandbox context: https://learn.chatgpt.com/docs/agent-approvals-security and https://learn.chatgpt.com/docs/developer-commands.

## Bounded correction

Status lists complete observed runtime/configuration registrations and explicitly reports `runtime_liveness: not_assessed`. Pending enable/restart require captured positive integer PID, nonempty birth identity and matching configuration, without trying to prove host liveness from a different PID namespace. Registrations, including stale ones, may be selectable but cannot approve anything. Actual native start/completion still require matching observed host ancestry/runtime/configuration, session/task, reviewer identity, candidate pins and canonical output.

Producer, borrower, process-group and recovery lifetime checks are unchanged. The guard's stopped function is unchanged. There is no runtime heartbeat, environment attestation, parent-authored report substitution, permission expansion or scorer/observer relaxation.

The independent planner and reviewer confirmed this fits the approved registration-versus-qualification contract. A positive sandbox-visible host-PID requirement would fail on the diagnosed environment and is not required by the approved spec. The implementation review is Approved, retained whole in implementation-2-review-enforcement-review-native-visibility.md.

## Local evidence

`lifecycle.py redgreen red -- python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py -k inaccessible_host` recorded both old-filter failures. GREEN passed after correction. One intermediate GREEN and activation run failed because an overbroad test mock also marked its own producer lease dead; the mock was scoped to the simulated host identity, with producer checks unchanged. Those failures remain recorded.

`lifecycle.py run assurance-2-native-visibility-activation -- python3 -m unittest discover -s .ai/scripts/tests -p test_review_enforcement.py -k ActivationTests` passed 7 tests. Later explicit stage Review/Verify denial assertions are covered by the final sealed candidate checks, reported separately.

`lifecycle.py run assurance-2-native-visibility-sandbox -- python3 docs/assurance/verify-native-session-workflow-2-v7.py` PASS: actual sandboxed lifecycle CLI discovers the registration and enables a pending request, then refuses Review and Verify without actual reviewer events. Exact outputs and proof limits are retained in native-session-2-v7-workflow.json. The callback registration is synthetic with a real live host process; this is a local workflow test, not a real-agent capture PASS.

Diff check PASS. Framework has no knowledge bundle: okf affected reports no bundle and is INAPPLICABLE, not PASS; no bundle was initialized. Lesson2 records the confirmed namespace finding as advisory evidence. The prior retrospective closure is immutable: trying to add lesson2 to it was refused and preserved; existing lesson1 closure was retained rather than resetting the task and its approvals.

Current frozen product tree: b0a6231f497622bd2243ab5118fae636860f33ec2f3529a949ed3f19c7ca7bf7. Final9 sealed baseline **66 tests PASS**; **37/37 byte-confirmed controls killed**, no INVALID/survivor, including restoring either sandbox liveness predicate and omitting runtime/configuration validation. Artifact qualified-24yc_r7g SHA25635ffd3da8180cde3172a726feca3fb19632e63a66623ea7f92fc9f6cdd430709 declares143KITinputs. Current convergence **8 PASS/0 FAIL/0 MANUAL**. Full framework final9 **805 tests PASS in97.9seconds with8workers**, exact retained full output mechanical-framework-2-final9-full.log. Audit and diff checks PASS. No unchanged product gate was repeated after this PASS.

Actual Codex native qualification and overall feature Verify/Ship remain pending. Historical Claude PASS and all Codex ERROR results remain unchanged. Claude's old native execution remains scoped to its original source; the changed common status/activation implementation has local coverage for both adapters and does not make that old run a current-KIT native PASS.
