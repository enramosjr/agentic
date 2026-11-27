# ADR 0016: Brownfield requirement changes as hash-pinned deltas

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §6.5](../0001-agentic.md#65-structured-capabilities-and-brownfield-deltas)

## Context

Most real work changes existing behavior. Rewriting a whole capability document
for each change loses unrelated requirements, invites silent edits and collides
with concurrent work. Without stable IDs, evidence and review cannot be tied to
a specific requirement over time.

## Decision

- Structured capabilities have a unique uppercase `namespace` and stable
  requirement IDs (`EXPORT-R1`) with named scenarios. IDs are never reused.
  Retired IDs stay reserved through retained deltas and receipts.
- A delta targets one capability and pins each requirement it operates on by the
  SHA-256 of its complete block, or by `absent` for additions. It then lists
  Added, Modified and Removed requirements. Removals state a MUST retirement
  behavior and a reason.
- `merge SPEC --dry-run` previews the change. `merge SPEC` requires the approved,
  unedited delta and a passing audit. It publishes a pending receipt, applies
  only the operated blocks, then logs, reindexes and completes the receipt.
  Re-running is idempotent, and a third state refuses.
- Prose capabilities and legacy whole-feature specs remain valid and are never
  converted automatically. `okf.py onboard` produces only draft, cited
  inventories without capability claims.

## Consequences

- Concurrent deltas on unrelated requirements merge cleanly. A stale pin names
  the conflicting ID.
- Interrupted merges recover without duplicate bookkeeping.
- Authors must compute block hashes, which the tooling assists with and
  validates.
- The audit detects drift, not deliberate forgery of both artifact and receipt.

## Alternatives considered

- **Whole-document replacement.** Rejected because it loses unrelated changes
  and hides edits.
- **Line-based patches.** Rejected because they break on unrelated reflow and
  are not requirement-addressed.
- **Automatic prose-to-structure conversion.** Rejected because it would invent
  requirements without human approval.

## Evidence

`.ai/scripts/brownfield.py`, `.ai/scripts/lifecycle.py` (`merge`), `.ai/lifecycle.md`
§Brownfield deltas, `.ai/agents/analyst.md` §Spec structure,
`.ai/scripts/tests/test_brownfield_deltas.py`, `.ai/evals/lifecycle/16-control-delta.json`.

## Revisit when

Adopters need deltas spanning multiple capabilities atomically.
