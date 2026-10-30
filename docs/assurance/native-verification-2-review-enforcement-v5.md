# Environment-corrected native verification proposal: v5

The authorized v4 pair ran exactly once and both remain ERROR. Claude stopped during startup. Codex passed normal temporary trust preflight for 15 handlers, produced eight parent callbacks, then could not execute commands. No reviewer, convergence or Verify ran. Reported charges were 0.351767 seconds for Claude and 16.225783 for Codex, **16.57755 aggregate agent-seconds**, with zero final reservations. Preserve mechanical-native-2-v4-report.json and all v4 raw data/results unchanged.

## Root cause and local correction

The evaluator sets TMPDIR/TMP/TEMP before launch. Relocating fixture Git metadata then turns `.git` into a pointer file, invalidating those inherited `.git/okf-scratch` paths. The launcher now recomputes scratch after checking relocated Git identity, verifies the retained destination, refreshes only those three variables and records their paths. Production code, permissions, trust policy, observer and scoring are unchanged.

The real-Git regression first failed on the exact stale-versus-relocated path. It now verifies all three existing directories and launches fresh plain Python to prove temporary allocation uses the new location without fallback. Final declared-file evidence: **10 tests PASS, 3/3 confirmed safety mutants rejected**, SHA256 `e1456dd39be6748ef402e26f067705a84ecdf58c2127f0aba7e35ebad099cb30`. The refresh-omission mutant fails that exact regression. Independent review Approved is preserved whole in native-proposal-review-2-review-enforcement-v5.md.

Fresh namespace operator-2-mechanical-native-v5 is frozen and audited in native-proposal-final5-verification.json. Its delta/live check snapshots and actual clean fixture setup pass before finalization. Unique campaign IDs end in v5. No additional Claude/Codex/app-server process or model inference ran during these local corrections. Native reviewer capture remains unverified.

## Requested authorization

Request one new Claude control-delta attempt and one new Codex control-delta attempt, subscription-only Anthropic/OpenAI copied KIT/fixture payload, using the same invocation-local project and exact frozen-handler trust policy. Limits remain 300 seconds per attempt, **600 aggregate agent-seconds and one 660-second campaign deadline** including auth/preflight/result checks. No retries, fallback, paid API, dangerous trust bypass or persistent global trust edits. Runtime preflight must pass before inference; all prior failures remain unchanged.

After fresh explicit approval, run once from `/home/enramosjr/Projects/agentic-assurance-7`:

```text
python3 .ai/scripts/lifecycle.py run assurance-2-real-agent --timeout 670 -- python3 docs/assurance/run-native-2-review-enforcement.py --authorized-allocation-and-scoped-trust
```

The v4 authorization prohibited retries. Its remaining numeric allowance does not authorize this new pair. No v5 native attempt or temporary trust overlay has run. No source commit, push, PR, merge, Verify or Ship is authorized by this proposal.

## V5 execution authorization

The user explicitly approved the prepared v5 Claude/Codex pair under the same 600 agent-second and 660-second campaign limits, using subscription quota and temporary fixture-hook trust. This grants the exact guarded v5 entrypoint once. No retry, fallback, additional campaign or delivery permission is added.
