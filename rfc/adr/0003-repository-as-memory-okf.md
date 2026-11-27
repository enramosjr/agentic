# ADR 0003: The repository is the memory: an OKF v0.2 knowledge bundle

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §9](../0001-agentic.md#9-the-knowledge-bundle-okf)

## Context

Conversation context is temporary. It is compacted, discarded, or held by a
different vendor's agent. Requirements, decisions and progress that live only in
chat are lost, and every new session pays to rediscover them. Ad-hoc files
(`PLAN.md`, `STATUS.md`, `docs/`) drift and have no machine-checkable structure.

## Decision

Adopter projects keep a single knowledge bundle in `knowledge/` using the public
Open Knowledge Format v0.2 layout and frontmatter rules. The bundle is the
canonical home for capabilities, specifications, architecture, ADRs, playbooks,
history, the work queue and the recovery checkpoint.

- All bundle operations go through `okf.py`: `context`, `show`, `search`,
  `affected`, `new`, `set`, `stamp`, `log`, `validate`, `records`,
  `sync-check`, `handoff` and others.
- A code change is not complete until the bundle is synchronized and
  `knowledge/log.md` has an entry. `sync-check` makes this mechanical: changed
  files must be covered by a changed document whose `verified` postdates the
  change.
- Parallel root planning files and `docs/` trees are prohibited.
- `stamp verified --run CMD` runs the check itself, so a stamp cannot claim more
  than the check proved.

## Consequences

- A fresh session resumes from `okf.py handoff` or `okf.py context` instead of
  from conversation history.
- Using a public format lets other tools read the knowledge.
- Documentation upkeep becomes a gate, which adds cost to every behavioral
  change. `sync-ignore` exists for paths that genuinely need no document.
- Per-entry merge drivers (`okf.py git-setup`) are needed so that parallel
  branches do not conflict on log, index, queue and status files.

## Alternatives considered

- **Free-form Markdown docs.** Rejected because they cannot be validated or
  mapped to sources.
- **An external wiki or issue tracker.** Rejected because it is not versioned
  with the code and not available offline to the agent.
- **Vendor memory features.** Rejected because they are not portable across
  harnesses ([ADR 0004](0004-vendor-neutral-governance-source.md)).

## Evidence

`.ai/scripts/okf.py`, `AGENTS.md` §1, §3, §4, `.ai/agents-reference.md` §Bundle layout,
§Frontmatter, §Trigger matrix, `.ai/autonomous-execution.md` §9.1.

## Revisit when

OKF publishes a version incompatible with v0.2, or adopters need a bundle split
across repositories.
