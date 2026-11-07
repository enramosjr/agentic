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

Independent `run` and `converge` invocations may execute checks concurrently.
Result publication reloads the latest state under a per-branch process lock,
preserving other results and lifecycle updates in both scratch and audit records.
The lock is released while these checks execute. Results from a replaced task or
changed intent are refused rather than written into the new state. Atomic writes
use separate temporary files; existing receipt fields stay compatible.

## Startup and discovery

`python3 .ai/scripts/repo.py context --json` reports explicit repository identity,
local branch/upstream divergence and author/committer prerequisites without changing
configuration or contacting a remote. Local equality is not proof of remote freshness;
fetch explicitly when required. A source checkout declares
`{"repository_kind":"framework"}` in root `.agentic.json`, which is not exported
by the installer. Installed manifests or an existing knowledge bundle identify
adopters; an unconfigured checkout remains unknown. Source audit receipts stay in
Git scratch, and source verification does not initialize or require knowledge.

Use `repo.py commands TOOL [SUBCOMMAND]` for actual CLI help and `repo.py headings PATH`
for actual Markdown headings. Neither operation requires an adopter bundle.

## Qualified artifacts

`python3 .ai/scripts/artifacts.py freeze --root BUILD_ROOT --file RELATIVE_FILE`
accepts repeated `--file` arguments and returns a bundle path and manifest SHA-256.
It copies declared regular files into a separate read-only bundle. Keep that receipt.
`artifacts.py run --bundle BUNDLE --sha256 HASH -- COMMAND '{artifact:RELATIVE_FILE}'`
verifies the pinned manifest and every declared file before and after execution.
Commands must reference a declared artifact; no fallback to a rebuilt source path
is supplied. Each invocation gets a separate Cargo/`AGENTIC_BUILD_DIR` build root.

`artifacts.py variant --bundle BUNDLE --sha256 HASH` returns a separate writable
mutation copy explicitly marked unqualified. Negative controls belong there, not
in the sealed bundle. This is operational integrity checking, not a sandbox against
a process owner deliberately altering and restoring files. Only declared files are
hashed; host libraries and other undeclared runtime inputs are not qualified.
Adopter-specific OCR fixtures and assertions remain the adopter's responsibility.

## Scoped evidence reuse

`lifecycle.py run` supplies conservative defaults for Python unittest/framework
checks and standard Cargo checks. Cargo package checks use offline locked metadata
to include selected packages, transitive workspace dependencies, all manifests and
shared root inputs. Unrelated package implementation files can then retain PASS.
Formatting tracks Rust/configuration inputs. Dynamic Python test dependencies use
the repository-wide scope rather than guessed imports. `--inputs` remains the
explicit override; unknown commands or unsupported external inputs retain the
exact-tree fallback. Generated lifecycle receipts are excluded from inferred inputs.

Inferred receipts include file fingerprints covering bytes, permission modes and
symlink targets, plus a hash of runtime/environment
identity; environment values are not written to the ledger. Committing identical
tested bytes does not invalidate input-scoped evidence. Changed files are named
where a snapshot exists; legacy receipts keep their digest format and conservative
diagnostics. Runtime dependencies outside the captured inputs still require the
project's qualification policy. No inference authorizes skipping a required lane.
Scopes containing Git submodules are refused because their contents are not captured;
record those checks in the submodule repository separately. A failed lane remains a
verification blocker across unrelated edits while its scoped inputs are current.

## One completion operation

`python3 .ai/scripts/lifecycle.py finish --json --tests TEST_PATH...` reports stage,
review, retrospective, traceability, convergence, evidence, source-scan and adopter
knowledge blockers together. It runs integrity checks, not application tests or
reviewer sessions, and does not change state by default.

`finish --apply` can record Verify only through the existing gates and current PASS
evidence. For adopter metadata, repeated `--bind knowledge/PATH=EVIDENCE_LABEL`
bindings explicitly associate updated documents with existing input-scoped evidence.
All bindings are validated before writes. Sources must be covered, and runtime
claims require their original check binding. The operation stamps metadata and logs
the reused evidence; it never writes body prose, approval, requirement citations or
new runtime claims. Missing independent review and qualification remain blockers.

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

## Delivery authorization and denial recovery

Local stage completion is not protected-branch merge authorization. See
[trusted CI](trusted-ci.md) for independently controlled critical acceptance,
separate App credentials and host-enforced approval. Installed integration remains
unverified until effective controls and real hosted denial cases are qualified.

Follow [Stage 5](../lifecycle.md#stage-5-ship) using the user's existing explicit
delivery choice within its authorized scope. Offer PR, keep or discard only when
the choice is missing; ask for approval when the payload, destination or side
effects expand that scope. Confirm deletion. Publishing draft specifications or
plans does not approve implementation.

Before external publication, inspect the exact outgoing commits and files, remote
destination, target branch and prepared PR update against the authorization.
Handoffs must preserve source chat references and distinguish direct user
authorization from agent-authored instructions. Quote authorization with its
source as evidence; an agent-authored handoff is not direct user approval and
must not become a manufactured human approval claim.

Use actual outputs to distinguish repository-hook refusal, sandbox restriction,
automatic-review denial and Git/remote failure. Quote the denying layer's
rationale when available; state the evidence limit when raw decisions are
missing. Do not infer an internal reviewer cause from an agent's summary alone.
After explicit denial, do not repeat an unchanged request, switch execution
routes or weaken policy. Direct the user to their interface's supported approval
or exact-action override mechanism if available; retry only through that supported
recovery and within its scope. Codex TUI `/approve` is TUI-specific, so check the
desktop interface rather than assuming an equivalent exists. The
[official Auto-review documentation](https://learn.chatgpt.com/docs/sandboxing/auto-review)
describes these boundaries.

Record `lifecycle.py stage ship` only after the selected local checkpoint or
commit, push and PR operations succeed. If delivery stops partway, leave it
incomplete, keep Ship open and report completed and remaining operations with
commit, branch and PR identifiers. A successful push does not complete a failed
PR update. Spec/plan approval, Review, Verify, retrospective and the prohibition
on default-branch merges remain in force.

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
