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
