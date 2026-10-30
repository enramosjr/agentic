# Corrected native verification proposal: v4

The authorized v3 pair ran exactly once. Both attempts remain ERROR in setup because the prepared checks directory omitted `delta.json`. Each recorded zero charged/reserved agent-seconds, no agent launch intent/supervision and no observed model/reviewer/trust preflight. The only native CLI activity was the approved first-party subscription authentication status check. See mechanical-native-2-v3-report.json and the immutable v3 result files. Nothing was rescored or retried.

## Local correction and proof

The copied immutable checks now include `delta.json`. Preparation must exercise the actual selected `control-delta` check snapshot, live adapter snapshot and real clean fixture setup before it can finalize. The v4 `setup-preflight.json` reports delta/live present and setup PASS, with no agent/model process.

The result checker now validates exactly one settled control-delta/repeat-1 attempt per expected adapter and zero reserved time, then calls unchanged `results-check --require-real`. The erroneous full-baseline `--campaign-complete` flag was removed: the requested pair is a bounded selection, not a 16-scenario baseline. No original behavior check, observer, scorer or native-qualification requirement changed.

Independent technical review Approved is preserved whole in native-proposal-review-2-review-enforcement-v4.md. Two setup regressions pass, including reproducing the original missing-delta error before any fixture process. The declared-file policy artifact `472a2e9cb90da939a8bb93022736a09b9cd7f408dc002cc254060439f4f09805` passed ten tests and killed both confirmed safety controls. Final frozen pins/commands/unused markers passed audit in native-proposal-final4-verification.json. Native execution remains UNVERIFIED.

## Requested retry authorization

Fresh namespace: `operator-2-mechanical-native-v4`. Source remains the previously validated `a9e58f56be695f860d87a470fdf18b038e698c18a5982703bab939b088e7f409`; no product change or new broad gate was needed.

Request two new control-delta attempts, one Claude and one Codex, using the same Anthropic/OpenAI subscription-only fixture/KIT payload and invocation-local trust scope described in native-verification-2-review-enforcement.md. Limits remain 300 seconds per attempt, 600 aggregate agent-seconds and one 660-second campaign deadline including auth/prechecks/result checks. No retries, fallback, paid API, dangerous trust bypass or persistent global trust changes. Version/auth/normal exact-handler trust preflight must succeed before inference. Raw streams and Git receipts remain external from their first write, surviving timeout cleanup.

After fresh explicit approval, run once from `/home/enramosjr/Projects/agentic-assurance-7`:

```text
python3 .ai/scripts/lifecycle.py run assurance-2-real-agent --timeout 670 -- python3 docs/assurance/run-native-2-review-enforcement.py --authorized-allocation-and-scoped-trust
```

The previous approval explicitly prohibited retries, so zero charged time does not authorize this corrected pair. No v4 native attempt or trust overlay has run. No source commit, push, PR, merge, Verify or Ship is authorized by this proposal.

## V4 execution authorization

The user explicitly approved the corrected Claude/Codex pair under the same 600 agent-second and 660-second campaign limits, using subscription quota and temporary fixture-hook trust. This authorizes the exact v4 guarded entrypoint once. No additional retry, fallback, campaign expansion or delivery permission is added.
