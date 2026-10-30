# Corrected Codex-only native qualification proposal: v7

## Diagnosis and correction

V6 remains ERROR: charged57.78371272300137agentseconds, no reviewer/Verify. Its native hook registered a host PID, but review status and pending enable/restart tested that PID from a different sandbox PID namespace. The local command could not see the live host process and misclassified it as stopped. Original results and raw evidence are preserved unchanged.

The model-free installed Codex sandbox diagnostic confirms the namespace mismatch, and the actual sandboxed workflow regression now discovers the registration, enables a pending request, and refuses Review/Verify without native reviewer capture. These tests use a real live host process plus synthetic registration, not model inference or actual native qualification. See native-session-2-v7-diagnosis.md, native-session-2-v7-visibility.json and native-session-2-v7-workflow.json.

Current source tree b0a6231f497622bd2243ab5118fae636860f33ec2f3529a949ed3f19c7ca7bf7 lists complete observed runtime/configuration registrations with `runtime_liveness: not_assessed`. Pending enable/restart require captured identity and matching configuration, without a sandbox-local host-liveness claim. Stale registrations may be selectable but cannot qualify without actual matched native reviewer start/completion, host birth identity, configuration/task, candidate pins and preserved canonical output. Those qualification checks and producer/borrower/group recovery lifetime rules are unchanged.

Independent implementation review Approved. RED/GREEN recorded. Final9 local validation: **66 focused tests PASS, 37/37 sealed byte-confirmed controls killed, 805 framework tests PASS in97.9seconds**, convergence **8 PASS/0 FAIL/0 MANUAL**, lifecycle audit/diff checks PASS. Sealed143-KIT-input artifact SHA25635ffd3da8180cde3172a726feca3fb19632e63a66623ea7f92fc9f6cdd430709. The review body is retained whole in implementation-2-review-enforcement-review-native-visibility.md. Framework no-bundle knowledge checks remain INAPPLICABLE; no bundle was created.

Claude's v5 PASS remains bound to its original source a9e58f5; it is not relabeled as current-KIT execution. This proposal requests only Codex. All prior errors remain unchanged; no scorer, observer, report hashing, sandbox permissions or trust acceptance is relaxed.

## Proposed execution scope

Prepare one fresh Codex control-delta attempt using installed Codex0.162.1, gpt-6.1-sol/medium, ChatGPT subscription quota, copied KIT/fixture payload to OpenAI and normal invocation-local project/exact frozen-handler hash trust. **300 aggregate agent-seconds and one330-second campaign deadline**, including authentication, trust discovery and result checks. One attempt only, no retry, fallback, paid API billing or persistent global trust/config edits.

Preserve v6's operator-created isolated `codex/named-greeting` branch before SessionStart/task state, checking unchanged HEAD/tree/index/history/cleanliness. Keep workspace-write/never and external raw/Git capture retention. This qualifies operation on supplied isolation, not agent-driven branch creation. Runtime discovery/trust must pass before inference.

The user authorized preparation and explicitly prohibited running until approval. No native campaign, model inference, temporary hook-trust overlay, source commit, push, PR, merge, Verify or Ship is authorized by preparation.

## Frozen operator and future command

Fresh namespace `operator-2-mechanical-codex-v7` is frozen on the current product candidate. Actual selected delta/live clean-fixture setup and source/operator/binary/command pin audits PASS. No started marker/result exists. Full preparation evidence: native-codex-v7-preparation-report.json. The runner differs from the reviewed v6 runner only in its namespace literal: restoring that literal gives identical bytes and normalized AST. Prior sealed8/10/2 operator-policy evidence remains explicitly scoped to the old manifests; unchanged policy/operator inputs plus new current product gates and actual current fixture setup support this preparation, without claiming those old broad manifests are current.

Runner SHA256880f01541f531e1284c01f53a4208bba03dce0a3c81485af29936ca76d2aad2e; launcher unchanged27dbdbf20df2f2481f2bb8feeb5f7c1a6572c3615e85f5282bf26360d5425c21; planned commands41fba09ee05ebf8ffe3066d8185e623b8b03007c55b83b2c97474a594bd247c1; preparation7a1f0dd9875568d26874866c134143a7feb60cdaa95ba05e816eff23b9298380.

Only after fresh explicit approval, execute exactly once from `/home/enramosjr/Projects/agentic-assurance-7`:

```text
python3 .ai/scripts/lifecycle.py run assurance-2-real-agent --timeout 340 -- python3 docs/assurance/run-native-2-mechanical-codex-v7.py --authorized-allocation-and-scoped-trust
```

The340second outer supervisor encloses the stricter330second aggregate campaign limit. The unused numeric budget of v6 grants no retry. This command has NOT run.

Independent final operator review is Approved, saved whole in native-proposal-review-2-mechanical-codex-v7.md. Preparation and review are complete; the only pending prerequisite for this one attempt is fresh explicit human allocation and scoped temporary fixture-hook trust approval. Existing implementation approval does not need to be requested again. No native preflight/model inference/attempt has run during v7 preparation.

## Execution authorization

The user explicitly approved: "Approved. Run the prepared Codex-only v7 attempt using subscription quota and temporary fixture-hook trust, within the 300 agent-second and 330-second campaign limits." This grants the exact guarded command once, with no retry, fallback, second attempt or delivery permission. The missing real Codex native capture/Verify qualification is the acceptance gap; source/operator inputs changed from v6 and are frozen separately. `lifecycle.py reuse assurance-2-real-agent` returned RERUN because the last run exited1. Earlier preparation-only restrictions are superseded only for this authorized attempt.

## Execution result: qualified PASS, grant consumed

The exact command ran once and exited0. The unchanged strict control-delta scorer/results-check reports1PASS/qualifiedtrue on sourceb0a6231. Charged159.8329127790057agentseconds, elapsed160.61777571501443attemptseconds, finalreserved0 within300agent/330campaign limits. Actual native reviewer start/completion and saved/captured/receipt report body hashes match; fixture Review and Verify completed. Report mechanical-native-2-codex-v7-report.md/.json retains raw evidence and full pins. No retry, fallback or source delivery occurred. A conservative denial of lifecycle.py --help during the active interval is retained as an observed reader limitation; the passing campaign is not a claim that every read-only command works. The isolated fixture also recorded stage Ship without a commit/push/PR; this is not delivery of the framework worktree.
