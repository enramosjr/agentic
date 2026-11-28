# ADR 0006: A fingerprinted evidence ledger with conservative reuse

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §7](../0001-agentic.md#7-evidence)

## Context

Agents write "tests pass" without running them, cite runs from before the last
edit, or rerun long suites on unchanged inputs. A "Verified" line in prose
cannot be checked. Storing full output, on the other hand, bloats records and
can capture secrets.

## Decision

- Checks run through `lifecycle.py run LABEL [--inputs GLOB…] -- CMD`: argv
  only, no shell, in a disk-backed scratch environment.
- Each ledger entry records `label`, `argv`, `exit`, `tree`, `head`,
  `duration`, `at`, `inputs` and `inputs_sha256`, plus optional input-file,
  context and runtime fingerprints. Output fields are forbidden.
- The ledger keeps at most 100 entries. Eviction of the oldest entry is
  canonical and provable.
- `lifecycle.py reuse` answers REUSE only when the recorded pass still covers
  the candidate's inputs and runtime, and RERUN otherwise. Agents MUST NOT rerun
  on REUSE.
- Scope is explicit, inferred conservatively for known Python and Cargo checks,
  taken from a reviewed profile, or the whole tree for unknown commands.
- At L2+, `stage verify` writes its note from the ledger and fails if the newest
  entry for the current tree failed.
- Bug fixes record `redgreen red` (it must fail) and `redgreen green` (it must
  pass on a changed tree).

## Consequences

- Every completion claim maps to a command, an exit code and the inputs it ran
  against.
- Long suites are not repeated after records-only commits.
- Under-declared inputs could make evidence look fresh when it is not. The
  default is therefore conservative, and profiles are reviewed declarations, not
  dependency discovery.
- The ledger shows that a command passed, not why. Review must still judge
  coverage.

## Alternatives considered

- **Trusting agent-reported results.** Rejected because this is the problem
  being solved.
- **Storing full output.** Rejected for size and secret leakage.
- **Always rerunning.** Rejected as too slow and costly.

## Evidence

`.ai/scripts/ledger.py` (`KEYS`, `OPTIONAL_KEYS`, `OUTPUT_KEYS`, `MAX_ENTRIES`),
`.ai/scripts/lifecycle.py` (`run`, `reuse`, `redgreen`), `.ai/scripts/assurance_inputs.py`,
`.ai/validation-policy.md` §Check selection and reuse.

## Revisit when

A reliable cross-language dependency tracer becomes available within the
stdlib-only constraint.
