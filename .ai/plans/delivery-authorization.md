# Implementation Plan: Authorized delivery and denial recovery

## Objective

Apply the exact instruction changes proposed in the user-approved
[delivery specification](../specifications/delivery-authorization.md). L2;
persona None, because implementation changes Markdown only.

## Success criteria

- R1: Reuse existing explicit delivery choices within scope; publishing drafts does not approve implementation.
- R2: Inspect outgoing payload, destination, branch and PR update; preserve authorization provenance in handoffs.
- R3: Distinguish evidenced failure layers and use supported denial recovery without unchanged retries or bypasses.
- R4: Close Ship after selected delivery succeeds; report partial publication as incomplete.
- R5: Keep the three instruction surfaces consistent, preserve gates and pass the framework suite.

## Current state

The Stage 5 section of `.ai/lifecycle.md` and
`.claude/skills/ship/SKILL.md` ask for a delivery choice unconditionally. The
skill closes the record without explicitly requiring successful publication.
`.ai/docs/lifecycle.md` describes evidence and authorization but lacks denial
recovery guidance.

`.ai/scripts/install.py` exports the canonical `.claude/skills` files to
`.agents/skills` through a symlink or copy. No separate Codex or Cursor ship
skill exists. `.ai/scripts/tests/test_install.py` covers byte-equal installation
and both skill distribution modes.

`.agentic.json` and `repo.py context --json` identify this checkout as a framework.
`okf.py affected` refuses because there is no knowledge bundle; do not create one.
The pre-edit `git diff --check` baseline passed in the lifecycle ledger as
`documentation-baseline`.

## Proposed approach

Change only `.ai/lifecycle.md`, `.claude/skills/ship/SKILL.md` and
`.ai/docs/lifecycle.md`, alongside specification and plan artifacts. Keep the
lifecycle contract authoritative, the skill concise and the distributed reference
consistent. No hook, gate, policy, schema, dependency or application changes.

## Boundaries and invariants

Preserve spec/plan approval, independent Review, Verify, retrospective and
default-branch merge restrictions. Permission covers only its authorized payload,
destination and side effects. An agent-authored handoff is provenance evidence,
not direct user approval. Never claim external acceptance or publication without
observing it. Do not switch execution routes or weaken policy after denial.
Identify /approve as TUI-specific. Preserve unrelated candidate preparation and
evidence-reuse instructions.

## Implementation steps

### Step 1: Delivery scope and completion are explicit

File: `.ai/lifecycle.md`, Stage 5. Requirements: R1, R2, R4, R5.

Replace unconditional delivery-choice prompting with reuse of an existing
explicit choice, asking for missing or expanded scope. Separate draft publication
from implementation approval. Add outgoing payload/destination/branch/PR preflight
and handoff provenance. Require selected operations to succeed before Ship and
report partial delivery with identifiers.

Check: independent review of authorized existing-PR publication, changed
destination, draft publication and successful-push/failed-PR scenarios.

### Step 2: Denials receive supported recovery guidance

File: `.ai/lifecycle.md`, adjacent Ship guidance. Requirements: R2, R3, R5.

Distinguish hook refusal, sandbox restriction, automatic-review denial and
Git/remote failure using actual outputs. State missing raw evidence. Use the
interface's supported approval or exact-action mechanism; qualify TUI /approve.
Exclude unchanged denial retries, alternate routes and policy weakening.

Check: independent review rejects invented reviewer causes, retry loops,
bypasses and universal TUI instructions.

### Step 3: Canonical skill and distributed reference agree

Files: `.claude/skills/ship/SKILL.md`, `.ai/docs/lifecycle.md`.
Requirements: R1, R2, R3, R4, R5.

Update the skill description and steps; add delivery/recovery guidance to the
reference. Preserve the local-commit versus publication-authorization distinction.
Do not create duplicate harness-specific skill files.

Check: compare all three instruction surfaces and run installer regressions
within the required framework suite.

### Step 4: Frozen documentation is reviewed and verified

Requirements: R1, R2, R3, R4, R5.

After edits and documentation synchronization, run convergence once. Delegate
independent two-pass review with the spec, plan, full diff, convergence and other
evidence. The report must disposition MANUAL R1–R4 and confirm that enforcement
rules did not change. Close the retrospective and record Verify after approval.
Keep a local checkpoint unless publication is separately authorized.

Check: Approved canonical review report and passing verification evidence.

## Testing strategy

Documentation is exempt from test-first red/green under AGENTS.md §8.6; the task
kind is docs. Add no tests that merely mirror prose. Scenario review covers
R1–R4. Run the existing full framework suite once through R5 convergence, including
installer and scripted-agent checks. It is not external push verification.

No tier/stage enforcement rule changes are planned. If implementation changes
those rules, the required real-agent lifecycle evaluation becomes applicable.

## Validation commands

After freezing edits:

```text
python3 .ai/scripts/lifecycle.py run delivery-diff -- git diff --check
python3 .ai/scripts/lifecycle.py converge .ai/specifications/delivery-authorization.md
python3 .ai/scripts/lifecycle.py scan-diff
python3 .ai/scripts/lifecycle.py audit
```

Convergence runs the approved R5 command:

```text
python3 -m unittest discover -s .ai/scripts/tests
```

Do not run that suite separately and repeat it through convergence. Use the
validation policy's background waiting mechanism. Before repeating a check,
consult `lifecycle.py reuse` and reuse valid evidence.

## OKF impact

Update the distributed workflow reference; keep framework receipts and the full
independent review in Git scratch. Preserve the approved spec body. Record the
missing-bundle result from `okf.py affected`; do not initialize knowledge.

## Risks and mitigations

- External reviewer behavior: claim correction of instructions only, without promising future acceptance.
- Authorization weakening: preserve exact scope and provenance requirements.
- Instruction drift: review all three surfaces; use canonical skill export.
- Premature completion: leave delivery incomplete on selected-operation failure.

## Out of scope

ISARS publication, K-202 implementation, Codex configuration, hook changes,
policy overrides and default-branch merges.

## Open decisions

None. The plan applies the approved proposed wording without additional behavior choices.
