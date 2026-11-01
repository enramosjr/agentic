# Spec: Authorized delivery and approval-denial recovery

Status: Draft; requires human approval before changing workflow instructions.

## Problem and outcome

The ISARS chat “M2b / K-202 specification and full plan”
(`01a1939e-4cb1-7b31-8d0e-9f2d4ce1160d`) reports repeated automatic-review
rejections when publishing documentation commit `150cbda` to `enramosjr/isars`,
branch `codex/isars-m1`, and updating draft PR #5. The initial task arrived through
an agent-authored handoff. The user subsequently authorized the exact commit,
repository, branch and PR update directly, then reiterated that authorization.
The agent continued reporting rejection. The chat export omits the raw reviewer
decisions and denied tool requests, so the reviewer's internal cause is unverified.

Read-only local checks on 2026-10-31 confirmed HEAD
`150cbda4ecd3955f00ac291992a24807c728e1f9` and one commit ahead of the local
upstream ref. They did not contact GitHub or establish current remote state.

The preceding ISARS chat “M2a-r: K-201 closure specification and…”
(`01a19329-9e7e-7d01-bb86-2532f403df3a`) reports a separate failure:
recording Ship before committing removed the active tier and blocked the normal
commit. It subsequently reports successful publication of `b4bb60d`.

The reusable instructions currently ask for a delivery choice unconditionally
in [Stage 5](../lifecycle.md#stage-5-ship) and the
[ship skill](../../.claude/skills/ship/SKILL.md). Neither explains recovery from
automatic-review denial. The lifecycle hook guards commits and PR creation;
the review guard can also refuse pushes while a review freezes writers. These
are distinct from Codex's external approval reviewer; no raw hook failure for the
blocked publication is present in the inspected chat export.

The outcome is delivery guidance that preserves explicit user choices,
distinguishes approval boundaries, reports evidenced blockers and closes Ship
after delivery. It cannot guarantee an external reviewer accepts an action.

## Users and scenarios

Agents delivering work; users publishing draft specifications without approving
implementation; agents handing work to a fresh chat; and users recovering from
an automatic-review denial.

## Requirements

- R1: Ship guidance MUST reuse an existing explicit delivery choice within its authorized scope. It MUST ask only when the choice is missing or the proposed destination, payload or side effects exceed that scope. Publishing draft specifications or plans MUST NOT imply implementation approval.
- R2: Before external publication, guidance MUST require inspecting outgoing commits and files, the remote destination and target branch, and the prepared PR update. Handoffs MUST preserve the source chat reference and distinguish direct user authorization from agent-authored instructions; they MUST NOT manufacture human approval claims.
- R3: Failure guidance MUST distinguish repository-hook refusal, sandbox restriction, automatic-review denial and Git/remote failure using available outputs. Missing raw decisions MUST be reported as an evidence limit. An explicit denial MUST NOT trigger unchanged repeated requests, alternate execution routes or policy bypass. Guidance MUST direct the user to a supported approval or exact-action override mechanism available in their interface; TUI `/approve` MUST be identified as TUI-specific.
- R4: Ship guidance MUST record Ship only after the selected delivery operations succeed. If commit, push or PR publication stops partway, the agent MUST report completed and remaining operations with relevant commit, branch and PR identifiers without claiming delivery complete.
- R5: The lifecycle contract, ship skill and distributed lifecycle reference MUST agree on R1–R4. Existing spec/plan approval, Review, Verify, retrospective and default-branch merge restrictions MUST remain enforced.

## Acceptance

- R1: Independent review rejects guidance that asks again after the exact publication was authorized, or treats draft publication as implementation approval. Review both an authorized existing-PR update and a changed-destination scenario.
- R2: Independent review rejects a publication scenario that omits outgoing payload or destination inspection, and a handoff that attributes agent-authored text to the user.
- R3: Independent review rejects unsupported claims about hidden reviewer rationale, identical denial retry loops, bypass suggestions or presentation of the TUI /approve command as universally available. Review the ISARS transcript evidence and the official Auto-review documentation.
- R4: Independent review rejects guidance that closes Ship before selected commit/push/PR completion, or reports a failed PR update as complete after a successful push.
- R5: `python3 -m unittest discover -s .ai/scripts/tests` passes; independent review confirms agreement across the three documents and preservation of existing gates. This suite is repository regression evidence, not proof that external auto-review accepts publication.

R1–R4 are manual document-review checks. They do not claim runtime or external
approval-system verification.

## Constraints

Change workflow documentation only. Preserve sandboxing, approval policy, hooks
and lifecycle enforcement. Never merge into the default branch. Do not claim an
external approval-system repair or successful publication without observing it.

Official [Auto-review documentation](https://learn.chatgpt.com/docs/sandboxing/auto-review)
states that reviewers receive a compact transcript and exact request, explicit
denials prohibit workarounds, and the TUI offers `/approve` for a narrow retry.
The desktop recovery UI must be checked rather than inferred from TUI behavior.

## Non-goals

Changing Codex policy or configuration; bypassing a denial; implementing K-202;
publishing the ISARS commit as part of this workflow correction; changing gate
code; treating agent-authored handoffs as direct user authorization.

## Assumptions

“Remedy it in the workflow here” means correcting this repository's reusable
delivery instructions. An external reviewer defect may remain outside this
repository's control.

## Open questions

None. The spec is ready for approval.

## Proposed instruction wording for review

Replace the unconditional delivery-choice instruction with:

> Use the user's existing explicit delivery choice within its authorized scope.
> If no choice exists, offer PR, keep or discard; confirm deletion. Publishing
> draft specifications or plans does not approve their implementation.

Add publication preflight and provenance guidance:

> Inspect the exact outgoing commits and files, remote destination, branch and
> prepared PR update before publication. Preserve source chat references in
> handoffs; quote authorization as evidence without presenting agent-authored
> instructions as user approval. Ask only for missing or expanded scope.

Add denial recovery guidance:

> Identify the denying layer and quote its rationale when available. If raw
> decisions are unavailable, state that limit. Do not repeat an unchanged denied
> action, switch execution routes or weaken policy. Use the interface's supported
> approval or exact-action override when available; `/approve` is TUI-specific.

Clarify closing order:

> After the selected commit, push and PR operations succeed, record
> `lifecycle.py stage ship`. If delivery stops partway, report what succeeded,
> what remains and the relevant identifiers; leave delivery incomplete.
