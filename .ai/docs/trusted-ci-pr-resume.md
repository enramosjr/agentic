# Trusted CI draft PR checkpoint

Status: Unfinished adopter-owned authority implementation on `codex/trusted-ci`.
This is a work-in-progress checkpoint for resumption, not release or enforcement
approval. Do not mark this PR ready or merge it from the local slice evidence.

## Direct publication authorization

In Codex chat `01a1bd45-9c44-7652-b614-7bef9451fe33`, the user explicitly said:

> Commit and raise a PR for this. We aren't done, but we can resume off of the PR in the future.

This authorizes the checkpoint commit, branch push and draft PR. It does not lift
the existing privileged/live-operation or merge holds. The original continuation
came from chat `01a1b685-3eb5-7000-a610-b478fa214a8c`; its handoff is historical.
These agent-written notes are not additional human approvals.

## Resume from these sources

1. Read the [current checkpoint](trusted-ci-task-controls-local.md), especially its
   finite remaining delivery groups and evidence limits.
2. Use the approved [adopter-owned spec](trusted-ci-adopter-owned-spec.md) and
   [plan](trusted-ci-adopter-owned-plan.md), including fresh brokered merges.
3. Consult [integration decisions](trusted-ci-adopter-integration.md), the
   [implementation status](trusted-ci-implementation-status.md) and
   [bounded local review](trusted-ci-task-controls-review.md). The review does not
   approve the full feature.
4. Audit the remaining executable producer graph before adding new components.
   The v2 workflow still has seven credential consumers only; the task/admin
   backend path now exists locally, but the complete workflow does not.

## Evidence and next work

Implementation checkpoint commit: `9164aca`. The fetched default branch was
`76b48ab` (PR #30). An attempted base merge found conflicts in `AGENTS.md`,
`.ai/docs/install-and-upgrade.md`, `.ai/scripts/tests/test_autonomy.py`,
`.ai/scripts/tests/test_qualification_gate.py` and
`.github/workflows/framework-parity.yml`. The uncommitted merge was aborted;
the implementation checkpoint and unrelated files were preserved.

Base integration is unfinished. The newer base also introduces a framework
source-document inventory and chat-only task-artifact policy, which this historical
checkpoint predates. Resolve that migration without losing the approved spec,
plan, review and continuation context. Do not register task paperwork as maintained
product docs merely to bypass the newer hygiene policy. The draft PR may show merge
conflicts and must remain a draft until base integration and verification finish.

The local backend aggregate and optional-crypto service checks passed at source
tree fingerprint `9281b9e` before this checkpoint's base integration. Installed
client, extracted-runtime and fresh task-controls regressions have RED/GREEN
evidence. These are local fixture results, not deployed qualification. Git scratch
receipts live in the original checkout and are not portable PR artifacts; exact
commands and outcomes are recorded in the current checkpoint.

The inherited framework gate timed out. Its lifecycle exit was `None`, supervisor
marker was 1, and suite output stayed empty. No full-framework aggregate PASS or
full-spec convergence exists. Check current input coverage before reusing any
receipt, especially after integrating a newer base. Do not run duplicate gates.

Remaining work: connect the producer graph; finish native onboarding and installed
remote routing; complete trial qualification and independent human review;
coordinate status/repair/upgrade/destroy and cloud promotion; then review and
verify the full integrated candidate. Unimplemented remote CLI commands explicitly
refuse, even if release holds were hypothetically lifted.

No trusted bootstrap context, cloud test accounts or live qualification are
available. Privileged setup, real credentials, cloud resources, GitHub authority
mutations, publication/activation/enforcement and actual merges remain held.
Publishing this source checkpoint does not authorize those operations.

Preserve the unrelated `.ai/docs/posix-hook-python-{spec,plan}.md` files and
`.worktrees/posix-hook-python`. They are excluded from this checkpoint.
