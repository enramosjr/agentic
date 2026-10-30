# Codex native capability scoping — no-model evidence

2026-10-28. Source candidate 6ad08d1 remains unchanged. This is scoping evidence, not implementation, native reviewer capture qualification, or a real-agent evaluation.

## Executed local check

`python3 .ai/scripts/lifecycle.py run assurance-2-codex-capability-scope -- python3 docs/assurance/scope-codex-capability-2.py` → PASS on 6ad08d1.

The installed CLI locally generated experimental JSON schemas and ran a bounded app-server process. Its native initialization response identifies Codex Desktop/0.162.1. The only JSON-RPC requests were initialize, hooks/list and config/read. No thread/start, thread/resume, turn/start, model/list, provider inference or model execution was requested. The process terminated after those reads. Analytics were explicitly disabled; no global configuration was edited.

## Verified runtime/config surface

- The installed strict-config parser accepted ephemeral SubagentStart and SubagentStop command-hook overrides.
- Native hooks/list returned both `subagentStart` and `subagentStop`, `handlerType: command`, `enabled: true`, `source: sessionFlags`, with an empty error list.
- Both registrations also report `trustStatus: untrusted`. No hook-trust bypass or persistent project/user trust modification was used. Enabled/listed status is not proof that a future event will execute successfully under trust policy.
- Generated HookEventName schema includes subagentStart and subagentStop.
- Generated ThreadReadResponse Thread schema exposes parentThreadId, agentRole, model, reasoningEffort and cliVersion. Model and effort are nullable and explicitly described as configured/latest persisted values, **not per-turn execution telemetry**. They must not silently become proof of an executed reviewer's actual model/effort.

## Unverified boundaries

No native subagent was created, so this check does not prove actual start/stop firing, populated agent_id/agent_type, last_assistant_message, agent_transcript_path, complete report delivery, or active reviewer identity. No existing unrelated user thread was inspected. Native thread/read metadata and transcript retrieval were not called, because no scoped child thread existed.

The [official hooks documentation](https://learn.chatgpt.com/docs/hooks) describes the start/stop payload fields and nullable final-message/transcript references; the [app-server documentation](https://learn.chatgpt.com/docs/app-server) describes read-only discovery/metadata methods. Those documented contracts are distinct from this installed-runtime schema/config acceptance evidence. Payload and event-fire coverage requires separately authorized real evaluation; transcript wire format must not be treated as stable merely because a path is provided.

## Evidence

- codex-capability-scope-2/summary.json: compact native event/config acceptance and ThreadRead field schemas.
- codex-capability-scope-2/requests.json and responses.json: exact bounded protocol traffic.
- codex-capability-scope-2/command.json: ephemeral config overrides; no trust bypass.
- codex-capability-scope-2/schema/: generated installed-runtime protocol schema bundle.
- codex-capability-scope-2/report.json and schema-facts.json: full static/runtime facts.
- codex-capability-scope-2/app-server.stderr and schema-generation.log: local process diagnostics.

No broad suite, real-agent cell, new worktree, source edit or delivery action was performed.
