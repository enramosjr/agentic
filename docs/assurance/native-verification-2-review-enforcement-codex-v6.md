# Codex-only native qualification proposal: v6

## Result motivating this proposal

The approved v5 pair ran once: Claude qualified PASS, Codex ERROR, 131.58858792600222 aggregate agent-seconds and zero final reservations, within the approved 600/660 limits. Preserve mechanical-native-2-v5-report.json and all original results. Claude captured an actual native read-only reviewer, preserved its canonical report and completed Verify on source a9e58f5. Codex stopped before opt-in because the source Git guard could not establish ownership of the fixture's separate Git directory. No Codex reviewer or Verify ran. Unused v5 quota permits no retry.

## Correction and evidence scope

Current source 5d42a15c9fb995ce09703be0121c5b31e6dd387e93d8733b8cc7dd34f0189516 uses a sanitized physical checkout witness while retaining foreign metadata and independent index/object/common checks. The regression was RED then GREEN. Independent technical review Approved; 63 focused tests PASS, 33/33 sealed semantic mutation controls killed, 802 framework tests PASS, R1–R8 convergence PASS. Evidence is in mechanical-validation-2-final8-report.md. The previous Claude PASS remains bound to its original source; claude-scope-comparison-2-final8.json records exact differences and unchanged native components. This proposal does not relabel it as a current-KIT Claude PASS.

The operator supplies the fixture's isolated `codex/named-greeting` branch before SessionStart or lifecycle state exists. It requires a clean fixture and checks unchanged HEAD, tree, staged index and commit count before/after metadata relocation. It records this preparation and tells the agent to continue on that branch. This satisfies the existing isolated-implementation requirement; the unchanged control-delta scenario does not require agent-driven branch creation. The native attempt therefore cannot establish sandboxed agent-driven Git metadata mutation. Deterministic source tests cover normal branch routing and active-review denial.

Normal `workspace-write`, `never` approvals and temporary exact fixture-handler hash trust remain unchanged. Codex protects Git metadata in this sandbox; supplying isolation beforehand avoids a permission expansion. See [OpenAI's sandbox documentation](https://learn.chatgpt.com/docs/agent-approvals-security). No named permission override or dangerous trust bypass is introduced.

## Requested allocation

One fresh Codex control-delta attempt on subscription quota, using installed Codex 0.162.1 and gpt-6.1-sol, with the copied KIT/fixture sent to OpenAI. Allow invocation-local project and exact frozen-handler hash trust. Limit **300 aggregate agent-seconds and one 330-second campaign deadline**, including authentication, trust discovery and result checks. One attempt only; no retries, fallback, paid API billing or persistent global trust/configuration edits. Required native discovery/trust checks must succeed before inference. No Claude attempt is requested.

Preparation, local tests and independent review do not authorize execution. No source commit, push, PR, merge, Verify or Ship is authorized by this proposal.

## Frozen proposal and local evidence

Fresh namespace `operator-2-mechanical-codex-v6` contains the frozen current source, operator, commands, binary hashes and actual selected delta/live clean-fixture setup receipt. Eight prebranch/allocation tests PASS; three byte-confirmed sealed broken variants were killed. Declared artifact SHA256: 42ca3012fd86b44fee14d30715455a13e396cbd2e22e6914d0ff54c4ef847300. Independent two-pass review Approved is retained whole in native-proposal-review-2-mechanical-codex-v6.md. No native preflight, model process or temporary trust overlay ran during preparation.

After fresh explicit approval, execute exactly once from `/home/enramosjr/Projects/agentic-assurance-7`:

```text
python3 .ai/scripts/lifecycle.py run assurance-2-real-agent --timeout 340 -- python3 docs/assurance/run-native-2-mechanical-codex-v6.py --authorized-allocation-and-scoped-trust
```

The 340-second supervisor encloses the runner's stricter 330-second aggregate campaign limit. The frozen runner rejects drift or prior attempts. The v5 grant is consumed and cannot authorize this command.

Final local evidence is collected in native-codex-v6-local-validation-report.md and native-codex-v6-preparation-report.json. The existing ten preparation/trust policy tests also PASS on sealed current generic inputs. Two existing setup regressions PASS with their unchanged archived-v3 fixture dependency closure; these are separate from the fresh current-v6 actual delta/live setup PASS. The report states these scopes explicitly. Fresh namespace pins and unused-attempt audit PASS. Overall Verify remains pending actual Codex qualification.

## Execution authorization

The user explicitly approved: "Approved. Run the prepared Codex-only v6 attempt using subscription quota and temporary fixture-hook trust, within the 300 agent-second and 330-second campaign limits." This grants the exact guarded command once. It adds no retry, fallback, second attempt or delivery permission. The missing real Codex native capture/Verify qualification is the acceptance gap; the new source and operator inputs are frozen separately from failed v5. Before execution, `lifecycle.py reuse assurance-2-real-agent` returned RERUN because the last run exited 1.

## Execution result: authorization consumed

The exact command ran once and ended ERROR, charged57.78371272300137agentseconds/finalreserved0 within300/330limits. The agent stopped on an empty observed-session list from review status before enabling mechanical review. Parent native registration/callbacks were retained, but no reviewer or Verify occurred. See mechanical-native-2-codex-v6-report.md/.json. No retry or remaining allocation is authorized by this proposal.
