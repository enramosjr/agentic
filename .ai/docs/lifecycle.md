# Lifecycle evidence in an adopting project

The [lifecycle contract](../lifecycle.md) defines stages and enforcement. Declare
the smallest applicable tier before implementation. Obtain the required spec
and plan approval, execute the change, review independently at L2+, synchronize
knowledge, verify, then deliver only within the user's authorization.

Run `python3 .ai/scripts/lifecycle.py analyze SPEC` before approval. It rejects
structural defects and reports manual acceptance checks. After implementation
and OKF synchronization, `python3 .ai/scripts/lifecycle.py converge SPEC` executes
the approved acceptance commands. A MANUAL entry is a disposition requiring
reviewed evidence, not an automated success. Keep failed outcomes visible.

Use `lifecycle.py run LABEL -- COMMAND` for the evidence ledger and `reuse LABEL`
before repeating checks. `okf.py sync-check`, `okf.py records` and scan-diff cover
knowledge synchronization, record integrity and added-line completeness.

Before Verify, L1–L3 tasks must close a retrospective: capture evidence-backed
observations with `lifecycle.py learn TEXT --evidence REF`, then run
`lifecycle.py retrospect --lessons 1 2`, or explicitly record
`lifecycle.py retrospect --no-new-lessons REASON`. Report the outcome when
delivering. Commit/PR and ship guards also require closure, including active
legacy tasks. Historical records without closure remain audit-valid.
Task declarations and SessionStart surface bounded advisory observations;
`lifecycle.py observations --query TEXT` retrieves them for a specific task.
Only human-approved promotions establish binding project rules.

Invoke lifecycle mutations directly, outside `lifecycle.py run`. Descendant CLI
commands inherit a repository-owner stack and refuse mutation before execution
if an ancestor run owns that repository. This protects existing convergence and
ledger evidence from the parent's stale snapshot. Read-only lifecycle inspection
and `merge --dry-run` remain available; independent fixture repositories may run
their own lifecycle commands while preserving ancestor ownership. A refused child
is recorded as a failed outer command. This is an operational guard, not a
security boundary against deliberately removed environment metadata or direct
calls to private command functions.

At L1+, committed audit records live in `knowledge/history/lifecycle/`. Run
`python3 .ai/scripts/lifecycle.py audit` to detect missing or changed stage
artifacts. Approval attribution is a recorded claim, not authentication. Include
the audit record with the change. Review and Verify must pass before a normal
commit; a local commit does not authorize a push or PR.

The adopter owns its knowledge, application tests and operational qualifications.
The kit's framework suite checks tooling behavior and installs these references
without importing any source project's knowledge corpus.

For guarded operations in another worktree, the hook selects the tool's explicit
`workdir`, then the event `cwd`, before session project hints. Relative workdirs
and edit paths use the execution directory. SessionStart retains session project
selection. Invalid explicit directories are denied. Some Codex adapters forward
only Bash command text and session `cwd`; use a direct `git -C WORKTREE commit`
so Git and the hook select the same target. The hook resolves that Git directory
without evaluating shell code; arbitrary shell directory changes are outside this
contract. The target's lifecycle and staged audit record must satisfy every gate.
