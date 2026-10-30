# Increment 2 real-agent qualification and bounded evaluation

2026-10-28. Source candidate a491524, source HEAD unchanged. No tracked files, source commits, pushes, PRs or merges changed during this work.

## Authorization and scope

The user explicitly authorized qualification of installed Claude 2.1.312 and two bounded fixture cells through the existing Pro subscription, including transmission of copied kit/fixture content to Anthropic and consumption of subscription quota. No paid API billing, extra model probes, retries or fallback were authorized or performed.

`run-real-agent-2.py` removes inherited API-key/token/base-URL/provider overrides without printing values, then requires effective auth to be loggedIn, claude.ai, firstParty, pro. Sanitized auth evidence is operator-2/effective-auth.json.

## Operator qualification

The ignored isolated operator at operator-2/.ai/evals/checks/live_observer.py differs from the tracked observer only by installed CLI version pin, explicit inclusion of the existing installed governance hooks in supported --settings, and no-model native debug capture. Full operator.diff and qualification.json identify source/operator SHA256. No native model, effective-effort, reviewer-identity or mutation assertions were relaxed.

No-model initialization passed. Native debug confirms lifecycle SessionStart exited 0 and supplied the router. Explicit --settings supplies installed edit/shell guards despite the ephemeral untrusted-project permissions warning. Local native-style guard probes both emitted permissionDecision=deny; these are explicitly local probes, not a claim that native PreToolUse fired. Copied parser contract tests reject missing reviewer model identity. The initial local probe harness incorrectly expected exit 2; it was corrected to the existing exit-0 structured-denial protocol and passed.

Frozen configuration SHA256: `20f5f2977901bebde6b4babb7aacabc21e7b596b70e2023cbf1db991055dca97`.

## Frozen source provenance

To satisfy unchanged evaluator clean-input qualification without committing the user checkout, the wrapper created a disposable fixture Git baseline from exact current KIT bytes via copy2, hash-verified each before launch, and retained its manifest in operator-2/frozen-copy.json. A separate audit confirmed identical file contents AND modes against the source worktree (operator-2/frozen-copy-audit.json). Its disposable commit is evidence provenance only, not source delivery. Original lifecycle evidence encloses execution on a491524.

## Commands and outcomes

- `lifecycle.py run assurance-2-operator-preflight-explicit -- python3 docs/assurance/qualify-operator-2.py` → PASS, no model requested.
- `lifecycle.py run assurance-2-operator-contract -- python3 docs/assurance/prove-operator-2.py` → PASS after harness protocol repair.
- `lifecycle.py run assurance-2-frozen-copy -- python3 docs/assurance/audit-frozen-copy-2.py` → PASS.
- `lifecycle.py run assurance-2-real-agent -- python3 docs/assurance/run-real-agent-2.py` → FAIL, source a491524. Exact expanded evaluator argv is operator-2/evaluation-command.json.
- Two cells only: feature-l2 FAIL; control-delta FAIL; 0 PASS, 2 FAIL, 0 ERROR. Actual observed model claude-sonnet-5-5, medium effort, CLI 2.1.312; no reviewers launched because both stopped earlier. Charged agent time 64.57142000400927 seconds within 600; timeout 300 per cell, total wall allocation 660.
- `lifecycle.py run assurance-2-real-results -- python3 .ai/scripts/lifecycle_eval.py results-check docs/assurance/real-agent-2.json --require-real` → PASS. This proves qualified real-result integrity, not passing behavior.

## Root cause of both cell failures

Retained native session logs show actual Write tool permission refusals, not failure to recognize upfront spec approval and not a refusal by the new assurance gate:

- feature-l2: Write to knowledge/specifications/cli-json-flag.md was refused as a sensitive file. The agent had declared L2, initialized the bundle and created a spec stub via okf.py new, but could not fill in its body. No intent, plan, implementation or Verify followed.
- control-delta: Write to knowledge/history/named-greeting-plan.md was refused as a sensitive file. The agent had analyzed the supplied delta and recorded human:eval intent approval, but could not write the plan. No implementation, reviewer, convergence or Verify followed.

Both denials state that permission-prompts=none leaves no approval surface and prohibit retries/workarounds. Both agents stopped honestly. All fixture paths sit beneath .git/okf-scratch, suggesting native sensitive-path classification of the ancestor .git directory; that explanation is an inference, while the sensitive-file refusals themselves are directly recorded.

Bounded final messages, tool errors and exact native transcript paths are saved in real-agent-2-diagnosis.json. Original native logs remain in ~/.claude/projects under their session IDs; evaluator process output was cleaned up by its normal lifecycle. No extra model run was used for diagnosis. The actual two-cell FAIL must not be presented as a behavioral PASS or used to claim completed Verify.
