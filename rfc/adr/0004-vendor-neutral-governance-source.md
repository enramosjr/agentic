# ADR 0004: One vendor-neutral governance source with thin harness adapters

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §4, §15](../0001-agentic.md#15-harness-adapters-and-platform-runtime)

## Context

Claude Code, Codex and Cursor each have their own rule files, subagent formats,
skill locations and hook schemas. Maintaining a separate process for each one
guarantees drift, and it makes switching agents mean switching process.

## Decision

- `AGENTS.md` is the single normative authority. The documents it declares
  binding (`.ai/agents-reference.md`, `.ai/lifecycle.md`,
  `.ai/validation-policy.md`, `.ai/autonomous-execution.md`) hold detail that is
  loaded on demand by section.
- Roles (`.ai/agents/`) and personas (`.ai/personas/`) are written once.
- Harness adapters contain only routing: `.claude/settings.json`,
  `.codex/hooks.json` and `.cursor/hooks.json` call the same scripts.
  `.claude/agents/` and `.codex/agents/*.toml` register the same roles, and
  `.claude/skills/` and `.agents/skills/` expose the same stage skills.
- `CLAUDE.md` imports `AGENTS.md` (`@AGENTS.md`) and adds only harness-specific
  tool notes.
- Cursor also reads `.claude/settings.json`, so those entries pass
  `--skip-in-cursor` to avoid running each check twice.
- Where a harness cannot enforce something (Codex subagents cannot be sandboxed
  read-only), the rule becomes an instruction and the weakness is documented.

## Consequences

- Switching agents keeps the same process, artifacts and records.
- Conformance tests check that registrations, skills and hook declarations stay
  aligned across adapters.
- Enforcement strength varies by harness, and the RFC states this rather than
  hiding it.
- A new harness needs only an adapter (RFC §17.2), not new rules.

## Alternatives considered

- **Per-vendor rule sets.** Rejected because they drift.
- **Supporting a single vendor.** Rejected because it locks adopters in.
- **Generating adapters from a schema at install time.** Not chosen, because
  static adapters are reviewable and diffable, and conformance tests catch
  drift.

## Evidence

`AGENTS.md` §2, `CLAUDE.md`, `.ai/agents-reference.md` §Subagents, §Harness tools,
`.ai/scripts/tests/test_lifecycle_conformance.py` (`HarnessWiring`, `RolesAndSkills`),
`.ai/scripts/tests/test_posix_hooks.py`, `.ai/scripts/tests/test_windows_hooks.py`.

## Revisit when

A cross-vendor hook or agent-definition standard emerges.
