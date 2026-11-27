# ADR 0017: Mechanically bound native review is opt-in

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance). Native delivery is not yet qualified.
- **Recorded:** 2026-11-27
- **RFC:** [0001 §10.2](../0001-agentic.md#102-mechanically-bound-native-review-opt-in)

## Context

Ordinary review provenance is a saved report and a recorded claim that an
independent reviewer produced it. That leaves room for the implementer to
approve its own work, or for the candidate to change during or after review. Binding
review to native harness events can close part of that gap, but it depends on
harness-specific callbacks and platform process identity that are not
universally available.

## Decision

- Ordinary review remains the default for L2+.
- `lifecycle.py review enable --adapter claude|codex …` opts a task into native
  capture. `review_native.py` hooks (SessionStart, SubagentStart/Stop, pre- and
  post-tool) bind:
  - the native session and runtime;
  - the reviewer child identity;
  - the hook configuration;
  - the candidate source (including modes, symlinks and deletions);
  - the approved spec and plan;
  - the exact convergence and the reviewed evidence.
- While a review is active, recognized edits and protected producers (lifecycle
  mutations, OKF writes, install, PR sync, artifact producers, validation) from
  every actor are refused before they take effect, even with
  `LIFECYCLE_GUARD=off` or `OKF_AUTONOMOUS=1`. Producers hold leases
  (`review_guard.py`).
- Once opted in, losing the capture or its marker refuses advancement. It never
  silently reverts to ordinary review. No timeout or fresh session grants
  approval.

## Consequences

- Where qualified, the approval is tied to a specific reviewer identity and an
  unchanged candidate.
- The feature currently requires an identifiable Linux native launcher
  (`/proc`). Synthetic callback tests validate the adapter contract but do not
  prove native delivery. Both Claude and Codex native capture must be verified
  before the feature is claimed complete.
- It is an operational integrity boundary, not an OS sandbox. Arbitrary shell
  writes and local forgery remain out of scope.
- Making it opt-in avoids breaking harnesses and platforms that cannot support
  it.

## Alternatives considered

- **Mandatory bound review.** Rejected because it is unavailable on several
  platforms and harnesses and would block all L2+ work there.
- **No binding.** Rejected as the only option because self-approval and
  candidate drift during review stay possible.

## Evidence

`.ai/scripts/review_native.py`, `.ai/scripts/review_guard.py`, `.ai/scripts/review_evidence.py`,
`.ai/lifecycle.md` §Mechanically bound review (opt-in), `.ai/scripts/tests/test_review_*.py`.

## Revisit when

Native capture is qualified on both Claude Code and Codex, or equivalent
process identity is available on Windows and macOS.
