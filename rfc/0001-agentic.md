# RFC 0001: AGENTIC — An Enforced, Right-Sized Lifecycle for Agent-Driven Software Engineering

| Field | Value |
|-------|-------|
| RFC | 0001 |
| Title | AGENTIC: Agent Governance, Execution, Navigation, Tooling, Integration, and Coordination |
| Status | Draft |
| Category | Informational, with a normative conformance profile (§17) |
| Describes | Kit version `0.1.0` (`.ai/VERSION`) as implemented at commit `bb3c226` (2026-11-24) |
| Created | 2026-11-27 |
| Supersedes | None |
| Decision records | [`rfc/adr/`](adr/) (ADR 0001–0017) |

## Abstract

AGENTIC is a vendor-neutral framework that governs how AI coding agents change
a software repository. It defines one lifecycle (Intent, Plan, Implement,
Review, Verify & Sync, Ship), scales its ceremony with four risk tiers (L0–L3),
and enforces it with harness hooks that refuse source edits, commits and pull
requests until the required stages are recorded and their artifacts pass
mechanical validation. Claims of completion must be backed by fingerprinted
evidence from checks that can fail. A project knowledge bundle in the Open
Knowledge Format (OKF v0.2) serves as the persistent memory that each new agent
session starts from. The same rules drive Claude Code, Codex and Cursor through
thin adapters. The framework extends to unattended multi-session milestones
through a supervised driver with circuit breakers. A separately administered
trusted CI authority is the boundary that may authorize merges; that authority
is implemented but not yet qualified.

This document specifies AGENTIC as it is currently built. It is reconstructed
from the implementation and its governing documents rather than written ahead of
them. Where the implementation and this RFC disagree, the implementation and
[`AGENTS.md`](../AGENTS.md) win, and this RFC is defective (§1.5).

## Status of this memo

This is a draft for review by the AGENTIC maintainers and prospective adopters.
It records the existing design, so it introduces no new behavior. The
accompanying Architecture Decision Records are retroactive. Each one is marked
*Proposed* until a maintainer accepts it.

---

## Table of contents

1. [Introduction](#1-introduction)
2. [Conventions and terminology](#2-conventions-and-terminology)
3. [Architecture overview](#3-architecture-overview)
4. [Governance model](#4-governance-model)
5. [The lifecycle](#5-the-lifecycle)
6. [Specifications and requirements](#6-specifications-and-requirements)
7. [Evidence](#7-evidence)
8. [Requirement assurance](#8-requirement-assurance)
9. [The knowledge bundle (OKF)](#9-the-knowledge-bundle-okf)
10. [Review](#10-review)
11. [Learning loop](#11-learning-loop)
12. [Autonomous execution](#12-autonomous-execution)
13. [Trusted CI and merge authorization](#13-trusted-ci-and-merge-authorization)
14. [Distribution and installation](#14-distribution-and-installation)
15. [Harness adapters and platform runtime](#15-harness-adapters-and-platform-runtime)
16. [Security considerations](#16-security-considerations)
17. [Conformance](#17-conformance)
18. [Implementation status](#18-implementation-status)
19. [Open issues](#19-open-issues)
20. [References](#20-references)
- [Appendix A: Command summary](#appendix-a-command-summary)
- [Appendix B: Lifecycle evaluation scenarios](#appendix-b-lifecycle-evaluation-scenarios)
- [Appendix C: Numeric limits](#appendix-c-numeric-limits)
- [Appendix D: Decision record index](#appendix-d-decision-record-index)

---

## 1. Introduction

### 1.1 Problem statement

Most agent workflows today consist of instructions that the agent is asked to
follow: a system prompt, a rules file, a set of slash-command templates. Long
sessions, context compaction, or an eager model can cause the agent to skip a
step without anyone noticing, and the record can still look complete.
Observed failure modes include:

1. **Skipped process.** The agent edits code before a requirement exists, or
   ships without review, because it no longer remembers that it should not.
2. **Inflated evidence.** "Verified" appears in a log or summary with no command
   behind it, or behind a test that cannot fail.
3. **Stub completion.** A placeholder, `TODO`, or "future work" sits on the
   critical path of a feature that is reported as done.
4. **Context loss.** Decisions, requirements and progress live in a
   conversation that will be compacted or discarded, so the next session starts
   over.
5. **Mis-sized ceremony.** A typo goes through a heavyweight process, or a
   contract change gets none, because the process does not scale with risk.
6. **Vendor coupling.** Each coding agent has its own rule format, so switching
   agents means switching process.
7. **Runaway autonomy.** Unattended runs either stop too early or never stop,
   burning budget while rewriting tests instead of delivering behavior.
8. **Self-certified authority.** The same environment that writes the code also
   writes the approvals and checks that authorize merging it.

### 1.2 Goals

AGENTIC aims to:

- **G1 — Enforce, don't remind.** Make skipping a required stage mechanically
  refused at the tool boundary, not merely discouraged ([ADR 0001](adr/0001-enforce-lifecycle-with-hooks.md)).
- **G2 — Right-size.** Apply one lifecycle to every change, with ceremony
  proportional to risk ([ADR 0002](adr/0002-one-lifecycle-four-tiers.md)).
- **G3 — Evidence over claims.** Count something as done only after a check that
  could fail has passed on the current inputs ([ADR 0006](adr/0006-fingerprinted-evidence-ledger.md)).
- **G4 — Repository as memory.** Keep everything a future session needs in the
  repository ([ADR 0003](adr/0003-repository-as-memory-okf.md)).
- **G5 — Vendor neutrality.** Keep one source of truth for all agents, with a
  per-harness adapter only where a harness offers hooks ([ADR 0004](adr/0004-vendor-neutral-governance-source.md)).
- **G6 — Bounded autonomy.** Run unattended multi-session work that converges or
  stops with a precise blocker ([ADR 0011](adr/0011-supervised-autonomy-driver.md)).
- **G7 — Separable authority.** Make it possible to move merge authorization
  outside the coding environment ([ADR 0009](adr/0009-trusted-ci-separated-environments.md)).

### 1.3 Non-goals

- AGENTIC is **not an OS sandbox**. Local hooks raise the cost of skipping a
  stage. They do not stop arbitrary shell or Python writes, or deliberate local
  forgery (§16).
- AGENTIC does **not authenticate human consent locally**. An approval recorded
  as `--approved-by human:<id>` is a claim ([ADR 0008](adr/0008-approvals-are-recorded-claims.md)).
- AGENTIC does **not establish the correctness of an adopter's application**. It
  requires the adopter's own build, test and end-to-end checks and records their
  outcomes. It does not replace them.
- AGENTIC does **not qualify a model** for unattended work. Scripted-agent
  evaluations exercise harness mechanics only (§18).
- AGENTIC does **not provide a hosted service**. The adopter owns any authority
  infrastructure and its cost.

### 1.4 Relationship to prior art

- **Spec-driven development toolkits.** Tools such as GitHub's Spec Kit give an
  agent templates and commands that walk it through specify, plan and task
  steps, guided by a project "constitution". AGENTIC shares the premise that a
  testable specification should come before code. It differs in three ways:
  (a) stage order is enforced by hooks that deny tool calls, (b) every stage
  artifact is validated mechanically before it is recorded, and (c) acceptance
  criteria are executable commands whose results go into a fingerprinted ledger
  and stay checked over time (§8).
- **Open Knowledge Format (OKF).** AGENTIC adopts the public OKF v0.2 bundle
  layout and frontmatter rules for project knowledge (§9).
- **Architecture Decision Records.** AGENTIC asks adopters to keep an ADR
  register inside the bundle (§12.6). This RFC's own decisions are recorded the
  same way in [`rfc/adr/`](adr/).
- **BCP 14.** Normative keywords follow RFC 2119 and RFC 8174 (§2).
- **Behavioral guidelines.** The plain-language guidance at the end of
  `AGENTS.md` is adapted (MIT) from the `andrej-karpathy-skills` `CLAUDE.md`. See
  [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

### 1.5 Authority of this document

The normative sources, from highest precedence down, are:

1. [`AGENTS.md`](../AGENTS.md) and the files it declares equally binding:
   [`.ai/agents-reference.md`](../.ai/agents-reference.md),
   [`.ai/lifecycle.md`](../.ai/lifecycle.md),
   [`.ai/validation-policy.md`](../.ai/validation-policy.md) and
   [`.ai/autonomous-execution.md`](../.ai/autonomous-execution.md).
2. The executable implementation in [`.ai/scripts/`](../.ai/scripts/) and its
   regression suite.

This RFC summarizes and explains them. It does not override them. A divergence
is a defect in this RFC, to be fixed by amending it, not by changing behavior to
match it.

---

## 2. Conventions and terminology

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in BCP 14 [RFC 2119] [RFC 8174] when, and only when,
they appear in all capitals.

| Term | Definition |
|------|------------|
| **Adopter** | A project into which the AGENTIC kit is installed. The lifecycle artifact workflow applies to it. |
| **Framework source** | The AGENTIC repository itself, identified by `.agentic.json` `repository_kind: framework` ([ADR 0013](adr/0013-framework-source-chat-only.md)). |
| **Harness** | A coding-agent runtime that executes tool calls: Claude Code, Codex, or Cursor. |
| **Adapter** | Harness-specific configuration (`.claude/`, `.codex/`, `.cursor/`) that routes harness events to the shared scripts. |
| **Kit** | The installable set of governance documents, roles, personas, skills, hooks and scripts (§14). |
| **Task** | One unit of lifecycle work, from tier declaration to Ship. |
| **Tier** | L0–L3 risk class of a task (§5.2). |
| **Stage** | One of `intent`, `plan`, `review`, `verify`, `ship`. Implement is the work between Plan and Review and is not separately recorded. |
| **Role** | Agent responsibility profile: analyst, planner, implementer, reviewer, orchestrator. |
| **Persona** | Advisory language-specific engineering guidance (§4.3). |
| **Spec** | A testable specification with requirement IDs and executable acceptance (§6). |
| **Capability** | A living description of shipped behavior in `knowledge/capabilities/`. It is *structured* when it uses a namespace and stable requirement IDs. |
| **Delta** | An approved change to a structured capability, pinned to the requirement blocks it operates on (§6.5). |
| **Ledger** | The per-task list of checks executed through `lifecycle.py run`, with input and runtime fingerprints (§7.2). |
| **Obligation** | A requirement's declared `Verify:` command and `Inputs:` scope (§8). |
| **Audit record** | The committed per-task JSON file `knowledge/history/lifecycle/<task>.json` (§5.5). |
| **Scratch** | Untracked, disk-backed state under the Git common directory (`okf-scratch/`). |
| **Bundle** | The OKF v0.2 knowledge directory `knowledge/` (§9). |
| **Run / session / batch** | Autonomous execution units: a run is a series of fresh-context sessions, and each session advances one bounded batch (§12). |
| **Milestone** | The unit of pull-request scope in autonomous execution (§12.7). |
| **Authority** | The independently administered repository and jobs that publish the trusted merge check (§13). |

---

## 3. Architecture overview

### 3.1 Layers

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │ Governance (normative text)                                            │
 │  AGENTS.md · .ai/agents-reference.md · .ai/lifecycle.md                │
 │  .ai/validation-policy.md · .ai/autonomous-execution.md                │
 │  Roles .ai/agents/*  · Personas .ai/personas/*  · Skills */skills/*    │
 ├────────────────────────────────────────────────────────────────────────┤
 │ Harness adapters (event routing only)                                  │
 │  .claude/settings.json · .codex/hooks.json · .cursor/hooks.json        │
 │  .claude/agents/* · .codex/agents/*.toml · .agents/skills/*            │
 ├────────────────────────────────────────────────────────────────────────┤
 │ Tooling (.ai/scripts, Python 3.9+ standard library)                    │
 │  lifecycle.py  okf.py  repo.py  shell_guard.py  review_*.py            │
 │  ledger.py assurance*.py brownfield.py artifacts.py completion.py      │
 │  autonomy_*.py wait_check.py pr_sync.py install.py process_runtime.py  │
 │  trusted_ci*.py authority_*.py framework_policy.py lifecycle_eval.py   │
 ├────────────────────────────────────────────────────────────────────────┤
 │ State                                                                  │
 │  tracked:   knowledge/ (OKF bundle, audit records, queue, status)      │
 │  untracked: <git-common-dir>/okf-scratch/ (per-branch working state,   │
 │             ledger, leases, review journal, autonomy progress)         │
 ├────────────────────────────────────────────────────────────────────────┤
 │ Trust boundary (optional, separately administered)                     │
 │  Authority repository · sandboxed host-side checks · publisher App     │
 │  deploy/authority/ (optional deployment source, not installed)         │
 └────────────────────────────────────────────────────────────────────────┘
```

Every rule lives in the governance layer. Adapters only route events into the
tooling. The tooling validates artifacts and either records state or refuses.
The trust boundary is the only layer that can authorize a protected-branch
update (§13).

### 3.2 State locations

| State | Location | Tracked | Writer |
|-------|----------|---------|--------|
| Governance and kit | `AGENTS.md`, `.ai/`, adapters | Yes | Installer (adopter), maintainers (framework) |
| Project knowledge | `knowledge/**` | Yes | Agents via `okf.py`, humans |
| Task audit record | `knowledge/history/lifecycle/<task>.json` | Yes, committed with the change | `lifecycle.py` |
| Lifecycle working state | `<git-common-dir>/okf-scratch/…` per branch | No | `lifecycle.py` |
| Evidence ledger | Inside task state; summarized into the audit record | Partially | `lifecycle.py run`, `converge`, `assure --run` |
| Work queue, archive, status | `knowledge/project/work-queue*.md`, `status.md` | Yes, single writer on the run branch | Orchestrator or solo agent |
| Install manifest | `.ai/install-manifest.json` (adopter) | Yes | `install.py` |
| Trusted CI discovery | `.agentic/trusted-ci.json` (adopter) | Yes | Adopter administrator |
| Framework identity | `.agentic.json` | Yes | Maintainers |

Scratch is disk-backed by design. `scratch.py` refuses memory-backed
filesystems, because supervisors and evidence must survive process death.

### 3.3 Repository identity

The tooling selects behavior by repository identity (`project_context.py`,
`.agentic.json`):

- **Adopter** (the default): the full artifact workflow of §5–§12 applies.
- **Framework** (`repository_kind: framework`): intent, plans, reviews and
  verification stay in chat. Self-task specs, plans, review reports, `knowledge/`,
  lifecycle records and lesson records MUST NOT be created anywhere, including
  Git scratch. Only documents listed in `source_documents` may exist, and
  `framework_policy.py` enforces this in CI, in the installer preflight and in
  the edit hook ([ADR 0013](adr/0013-framework-source-chat-only.md)).

An unknown or invalid identity grants no framework exemption.

---

## 4. Governance model

### 4.1 Precedence

When sources conflict, the highest one wins:

1. Explicit user instructions
2. Acceptance criteria
3. The approved plan
4. Repository and directory instructions, including human-approved project rules
   in `knowledge/project/rules.md` (§11)
5. Executable code, configuration, schemas and tests
6. Project knowledge
7. The persona
8. Existing repository conventions
9. General engineering judgment
10. Personal preference

A review finding MUST rest on a source above the persona.

### 4.2 Roles

| Role | Stage | Contract summary | Tool restriction |
|------|-------|------------------|------------------|
| `analyst` | Intent | Turns a request into a testable spec. Asks at most five behavior-changing questions, each with a recommended default. | Read-only (Claude Code, Cursor) |
| `planner` | Plan | Investigates read-only and maps every requirement ID to a step and a check. | Read-only (Claude Code, Cursor) |
| `implementer` | Implement, Verify, Ship | Makes test-first, surgical edits, runs focused checks and syncs the bundle. | Full |
| `reviewer` | Review | Two independent passes (spec compliance, then quality). Cannot approve with a Critical or High finding open. | Read-only (Claude Code, Cursor) |
| `orchestrator` | L3 | Sole writer of the queue and status. Dispatches disjoint lanes and gates DONE. | Full |

Codex custom agents cannot set a sandbox, so the read-only rule is an
instruction there (`.ai/agents-reference.md` §Subagents).

### 4.3 Personas

Seven advisory personas (Python, JavaScript/TypeScript, Rust, Go, C#,
Dart/Flutter, Swift/SwiftUI) supply pitfalls, validation commands and review
checklists. The persona is selected automatically from file context. The agent
MUST name the persona and say why it chose it. A persona MUST NOT change the
requested outcome, override acceptance or the plan, expand scope, or turn
preferences into defects. Each persona and role file MUST be loaded by outline
and section (`okf.py show … --outline`, `--section`), never whole.

### 4.4 Execution gates

Every task passes four gates (`AGENTS.md` §6):

1. **Discovery and persona.** Declare the tier. Read `okf.py handoff` (when a
   queue exists) or `okf.py context`. Load only the target documents, the
   persona and the role.
2. **In-flight impact.** Track which capabilities, specs and architecture
   documents the change touches.
3. **OKF sync.** Close the L1–L3 retrospective. Apply the trigger matrix (§9.3)
   and `okf.py affected`, then update the bundle and append to `knowledge/log.md`.
4. **Verification and sign-off.** Run the applicable rows of the test matrix
   through `lifecycle.py run`, then record `lifecycle.py stage verify`, which
   runs `okf.py sync-check`, `lifecycle.py scan-diff` and `okf.py records`.

---

## 5. The lifecycle

### 5.1 Stages

```
Intent ──► Plan ──► Implement ──► Review ──► Verify & Sync ──► Ship
 (0)        (1)       (2)          (3)          (4)             (5)
```

| Stage | Role | Artifact | Exit check (validated by `lifecycle.py stage`) |
|-------|------|----------|-----------------------------------------------|
| 0 Intent | analyst | L1 note; L2+ spec | `analyze` reports no Critical or High finding. L2+ requires `--approved-by`. |
| 1 Plan | planner | Light or full plan; L3 queue entries | The plan cites every spec requirement ID. |
| 2 Implement | implementer | Diff, tests | Test-first for `bugfix` and `logic` (red, then green). No stub on the critical path. |
| 3 Review | reviewer | Canonical `# Review Report` with `## Verdict` | Verdict is Approved. At L2+ it cites convergence and every MANUAL requirement. |
| 4 Verify & Sync | implementer | Ledger evidence, bundle updates | Retrospective closed. Current passing ledger entry (L2+). Converge current with no FAIL (L2+ with spec). `scan-diff`, `sync-check` and `records` pass. Assurance gate (L2/L3). |
| 5 Ship | implementer or orchestrator | Branch, PR, or checkpoint | All required stages recorded. Candidate frozen on the current base. Record closed. |

### 5.2 Tiers

| Tier | Applies when | Required recorded stages (`lifecycle.py` `REQUIRED`) |
|------|--------------|------------------------------------------------------|
| **L0** trivial | Typo, comment or constant with no behavior, contract or test effect | none |
| **L1** small | Bounded change in a few files with no contract, schema, persistence, security or dependency effect | `intent`, `plan`, `verify` |
| **L2** feature | New or changed behavior, any contract effect, several modules, or an ambiguous request | `intent`, `plan`, `review`, `verify` |
| **L3** milestone | Queued or autonomous work | `intent`, `plan`, `review`, `verify` (the queue is the artifact set) |

Agents MUST pick the lowest tier whose conditions hold and MUST state the tier
and the reason in their first message. Tiers scale spec, plan, review and gate
breadth. They MUST NOT relax the prohibitions of §7.4, the OKF sync gate, or the
evidence rules ([ADR 0002](adr/0002-one-lifecycle-four-tiers.md)).

### 5.3 Escalation and user-set tiers

An agent MUST escalate as soon as investigation shows a contract, schema,
persistence, security or dependency effect, or a behavior question the
repository cannot answer. A tier declared with `--user-set` MUST NOT be lowered.
`--new` starts a different task. An L0 declaration ends at the next commit.

### 5.4 Task kinds and test-first

`lifecycle.py tier … --kind` takes one of `feature`, `bugfix`, `logic`,
`refactor` or `docs`. For `bugfix` and `logic`:

- `lifecycle.py redgreen red -- CMD` MUST record a command that **fails**. A
  passing command is rejected.
- `lifecycle.py redgreen green -- CMD` MUST record a passing command on a
  **changed** working tree.
- `stage verify` and the commit hook refuse the task without that pair.

Red proves only that the command failed. The report MUST also state that it
failed for the reported reason. After three disproved hypotheses or fix
attempts, the agent MUST stop and report instead of stacking patches (debug
flow, `.ai/lifecycle.md` §Debugging flow).

### 5.5 Lifecycle state and the audit record

`lifecycle.py` keeps per-branch working state in scratch. Above L0 it also
writes one committed audit record per task at
`knowledge/history/lifecycle/<task>.json`. The record stores:

- tier, reason, kind and stage timestamps;
- for each `--ref` artifact, its SHA-256 (body only, so frontmatter edits do not
  invalidate it);
- approval claims (`approved_by`);
- ledger summaries, convergence runs and retrospective closure;
- **no command output**.

`lifecycle.py audit` exits nonzero when a referenced artifact is missing or
changed, when an L2+ intent lacks `approved_by`, or when a record is malformed.
A changed stage MUST be re-recorded, and a changed intent needs fresh approval.
The audit detects drift. It does not detect deliberate forgery of both artifact
and record (§16).

### 5.6 Hook enforcement contract

Harness adapters call `lifecycle.py hook`. In adopter projects it:

| Event | Behavior |
|-------|----------|
| SessionStart | Injects the lifecycle Router, approved project rules (≤ 8,192 bytes) and advisory observations (§11). |
| Pre-tool source edit | **Denies** until a tier is declared and every stage required before Implement is recorded. |
| Pre-tool `git commit` | **Denies** (except `wip:` commits) until Verify is recorded and the retrospective is closed. Also denies when the audit record would be left untracked or unstaged. |
| Pre-tool PR creation | **Denies** until Verify is recorded. |

Exemptions and bypasses:

- Markdown and `knowledge/` edits are exempt from the source-edit gate.
- `LIFECYCLE_GUARD=off` bypasses tool gates for a human operator.
- Driver sessions (`OKF_AUTONOMOUS=1`) are gated by the work queue instead.
- Both bypass modes still receive approved project rules at SessionStart.
- State-mutating lifecycle commands MUST NOT be wrapped in `lifecycle.py run`.
  A same-repository descendant mutation is refused, which protects acceptance
  and ledger evidence.

The hook is a cost-raising control, not a proof of consent
([ADR 0001](adr/0001-enforce-lifecycle-with-hooks.md),
[ADR 0008](adr/0008-approvals-are-recorded-claims.md)).

---

## 6. Specifications and requirements

### 6.1 Spec format

An L2+ spec is persisted at `knowledge/specifications/<slug>.md` with
`status: draft`. It contains:

```markdown
# Spec: <title>
## Problem and outcome
## Users and scenarios
## Requirements        — `- R1: <one observable behavior with MUST or SHOULD>`
## Acceptance          — `- R1: `<command>` <passes|fails when unmet>`, one per requirement
## Constraints
## Non-goals
## Assumptions         — each with the question it replaces
## Open questions      — or `None. The spec is ready for planning.`
```

Each acceptance bullet SHOULD lead with a backticked command that runs from the
repository root. A prose-only bullet is a *manual* check. A draft spec is
intent, not a claim about shipped behavior.

### 6.2 Analysis (`lifecycle.py analyze`)

`analyze` prints one `<Severity> <category> <file>: <message>` line per finding
and exits 1 on any Critical or High finding. `stage intent` refuses those.

| Severity | Findings |
|----------|----------|
| Critical | Missing section, no requirements, duplicate ID, uncovered requirement, orphan or placeholder acceptance |
| High | No `MUST`/`SHOULD`, vague term (defaults plus project-declared `## Vague terms`), identical requirements, open questions |
| Medium | An acceptance bullet with no backticked command (manual check) |

### 6.3 Convergence (`lifecycle.py converge`)

For the active L2+ task's approved spec, after the audit passes, `converge`
runs each requirement's first acceptance backtick span:

- without a shell, from the repository root, with stdin closed;
- with a disk-backed scratch `TMPDIR`;
- with a 600-second default timeout.

It prints `R<n> PASS`, `FAIL (exit N|timeout|cannot run)` or `MANUAL`, and
exits 1 on any FAIL. The run is bound to HEAD, so any commit makes it stale,
while Markdown and `knowledge/` edits do not. The ordering at L2+ is fixed: OKF
sync, then converge, then review, then verify, with no commit in between.

### 6.4 Traceability

`lifecycle.py trace SPEC --plan PLAN --tests PATH…` checks that every
requirement is cited by both the plan and a test. `queue-from-spec` turns a spec
into §12.2 queue entries, one per requirement.

### 6.5 Structured capabilities and brownfield deltas

A *structured capability* has a unique uppercase `namespace` (for example
`EXPORT`) and one `## Requirements` section of `EXPORT-R<n>` bullets with
indented `- Scenario NAME:` blocks. IDs are stable and never reused. Prose
capabilities and legacy `R<n>` whole-feature specs remain valid and are never
converted automatically.

A *delta* targets one capability (`target: /capabilities/export.md`, mirrored in
the body's `## Target baseline`). It pins each requirement it operates on:

```
- EXPORT-R1: sha256:<hash of the complete UTF-8 block incl. scenarios and final newline>
- EXPORT-R3: absent
```

It then lists `## Added requirements`, `## Modified requirements` and
`## Removed requirements` (each `None.` when empty). Removals state a MUST
retirement behavior and a nonempty `Reason:`.

- `lifecycle.py merge SPEC --dry-run` previews the capability diff without
  writing.
- `lifecycle.py merge SPEC` requires the active task's approved, unedited delta.
  It publishes a pending merge receipt, applies additions, replacements and
  removals, records one log entry, reindexes and completes the receipt.
  Unrelated blocks are untouched.
- Reapplying after an interruption is idempotent. A third state (neither the
  before nor the after image) refuses.

Verify on a delta task requires a completed receipt, matching postimages and the
absence of removed IDs ([ADR 0016](adr/0016-hash-pinned-brownfield-deltas.md)).
`okf.py onboard` inventories an existing repository into draft architecture
documents without running code or making capability claims.

---

## 7. Evidence

### 7.1 Evidence hierarchy

Claims in knowledge documents rank evidence as follows (`AGENTS.md` §5.2):

1. Implemented source (strongest for shipped behavior)
2. Executable configuration (build files, CI, lockfiles, schemas)
3. Validated build and runtime output
4. Current project documentation (context, not proof)

A spec requirement or planned feature MUST NOT be presented as shipped without
checking that the source implements it. `verified.by: process:repository-scan`
means only that files exist. `evidence: validated-runtime` SHOULD be used only
when an end-to-end check actually passed in that change.

### 7.2 Ledger entries

`lifecycle.py run LABEL [--inputs GLOB…] -- CMD` executes an argv (no shell) in
a scratch environment and appends an entry with the required keys `label`,
`argv`, `exit`, `tree`, `head`, `duration`, `at`, `inputs` and `inputs_sha256`.
Optional keys are `input_files`, `context_sha256`, `profile` and
`runtime_sha256`. Output keys (`tail`, `output`, `stdout`, `stderr`) are
forbidden, so the ledger holds outcomes and never transcripts. The ledger keeps
at most 100 entries. Eviction of the oldest entry is canonical and provable
([ADR 0006](adr/0006-fingerprinted-evidence-ledger.md)).

Input scope works like this:

- **Explicit.** `--inputs` globs are repo-relative. Absolute paths and `..` are
  rejected.
- **Inferred.** Supported Python and Cargo invocations get conservative inferred
  scopes. External manifests or build roots disable inference.
- **Profiled.** `assurance_inputs.py` exports reviewed, built-in Python input
  profiles for exact commands without executing them.
- **Fallback.** An unknown command depends on the whole tree. Markdown and
  `knowledge/` are excluded from the tree hash.

### 7.3 Reuse

`lifecycle.py reuse LABEL_OR_CMD` answers **REUSE** when a recorded pass still
covers the candidate (its inputs and runtime are unchanged) and **RERUN**
otherwise. Before repeating a check, an agent MUST ask `reuse`, and on REUSE it
MUST NOT rerun. `stage verify` at L2+ requires a current passing entry and
fails when the newest entry for the current tree failed.

### 7.4 Completeness prohibitions and `scan-diff`

The following MUST NOT be landed or claimed complete (`AGENTS.md` §8.1):

- stubs and placeholders;
- deferred behavior presented as done;
- weak or misleading tests;
- evidence inflation;
- half-integrated paths.

`lifecycle.py scan-diff` runs at `stage review` and `stage verify` (L1+). It
fails on an unwaived stub, on `pass` followed by a deferred-work comment, or on
"future work" in added lines. A waiver takes the form
`lifecycle:allow RULE -- reason`. Weak-test findings are reported but do not
fail the scan.

A feature slice is done only when the behavior works on the intended path, unit
tests cover pure logic, an end-to-end check exercises the user-visible success
criteria and fails when they are unmet, the bundle and log record the concrete
commands and outcomes, and no `TODO`, `FIXME` or stub remains on the critical
path (`AGENTS.md` §8.2). The minimum end-to-end check for each claim type is
listed in `.ai/agents-reference.md` §E2E minimums.

### 7.5 Qualified artifacts

`artifacts.py freeze` seals declared files into a separate, hash-pinned bundle.
`artifacts.py run` verifies those pins before and after a check. `variant`
creates a separate, unqualified copy for mutation testing, so a mutated artifact
can never stand in for the qualified one.

### 7.6 Validation policy

The rules in `.ai/validation-policy.md` are normative:

- Run focused checks in the edit loop, and the slice's narrowest end-to-end
  check once when its edits are complete.
- Run the full gate once per frozen candidate, after merging the current base.
- Never rerun an unchanged check, and never rerun an unchanged failing check to
  see whether it now passes.
- Run long checks with `wait_check.py start` and `wait`. Polling loops are
  forbidden, and `--max` below 300 seconds is a violation.
- Testing is proportional: one end-to-end check per user-visible success
  criterion, and a negative control only where a failure would otherwise pass
  silently.
- Acceptance MUST be unattended and deterministic. An item that needs real
  hardware or a person is out of scope for an autonomous batch.

`completion.py` (`lifecycle.py finish --json`) consolidates completion blockers.
`finish --apply` performs supported bookkeeping and can record Verify from
existing passing evidence. It never runs application tests and never supplies a
missing review.

---

## 8. Requirement assurance

Assurance answers the question "is each requirement still verified?" across
the life of a project, not just within one task
([ADR 0007](adr/0007-living-requirements-assurance.md)).

### 8.1 Declaration

Before its first scenario, a structured requirement MAY declare:

```
- EXPORT-R1: The export endpoint MUST stream CSV …
  - Verify: `python3 -m pytest tests/test_export.py`
  - Inputs: `src/export/**` `tests/test_export.py`
  - Governed-by: [Layer boundary](../project/decisions/layers.md#boundary)
  - Accept-risk: 2026-12-31 by human:alice - vendor fix pending
```

`Verify:` is one backticked command, or `manual` with a reason. `Inputs:` is
only allowed together with `Verify:`. A duplicate line, a line placed after a
scenario, `Inputs:` without `Verify:`, an empty command or an unsafe glob makes
the requirement INVALID.

### 8.2 Status

`lifecycle.py assure` takes the newest `req:<ID>` ledger entry whose command and
inputs match the current obligation. It looks in committed records and in the
active task.

| Status | Meaning | Blocks L2/L3 Verify when touched |
|--------|---------|----------------------------------|
| VERIFIED | Passed, and freshness holds | No |
| STALE | An input file (named) or the runtime changed | Yes |
| FAILED | The newest entry exited nonzero | Yes |
| UNVERIFIED | No matching entry, or the completion order is uncertain | Yes |
| INVALID | The obligation is malformed | Yes |
| MANUAL | `Verify: manual` | No |
| UNDECLARED | No `Verify:` line | Only with `--strict` |

The commands are:

- `assure --changed --base REV` lists affected obligations without running
  anything.
- `assure --run [ID…]` executes obligations through the ledger path and needs an
  active task.
- `--json` emits `schema_version: 1`.
- Exit codes: 0 for clean, 1 for any STALE, FAILED, UNVERIFIED or INVALID, 2 for
  refused input.

### 8.3 Ordering

Matching entries are ordered by recorded UTC completion time with up to six
fractional digits, and each timestamp is treated as a half-open interval.
Overlapping distinct executions yield UNVERIFIED rather than an arbitrary
winner. Filenames and ledger indices never establish order.

### 8.4 Judgment and risk are never evidence

- A reviewer who cites a MANUAL requirement in an Approved review's
  `## Validation Reviewed` section produces an `attested` annotation. The
  citation can be pinned to the requirement block's hash.
- `Accept-risk: YYYY-MM-DD by human:<id>|decision:<ADR> - reason` produces a
  visible `risk_acceptance` (active, then expired) beside a failing status.
- Neither changes a status, a count or an exit code. Judgment and risk
  acceptance MUST NOT waive mechanical failure.

### 8.5 Governed architecture constraints

`Governed-by:` links a requirement, by a Markdown link that may include an
anchor, to an ADR or other knowledge document. Paired
with a real checker (for example a forbidden-import scanner), the requirement
enforces an architectural boundary. If edits to the decision should invalidate
evidence, the decision belongs in `Inputs:`. The link records provenance. Only
the check and its inputs determine what was verified.
`assurance_architecture_demo.py` demonstrates this in a disposable repository.

### 8.6 Limits

- VERIFIED covers that command on those inputs, not the full intent of the
  requirement.
- Records on unmerged branches are invisible.
- A squash merge that drops a recorded commit makes its evidence STALE.
- A change of executable or runtime between machines makes evidence STALE.
- A schema-valid hand-written record is accepted, so assurance detects drift,
  not forgery.

---

## 9. The knowledge bundle (OKF)

### 9.1 Layout

Adopters keep `knowledge/` in the OKF v0.2 layout (`okf.py init`):

| Path | Purpose |
|------|---------|
| `index.md` | Root index. Frontmatter is only `okf_version: "0.2"`. |
| `log.md` | Dated (`## YYYY-MM-DD`), newest-first log. Every bundle update appends to it. |
| `project/` | Architecture, boundaries, rules, the ADR register, queue and status |
| `capabilities/` | Shipped, user-visible behavior (living requirements) |
| `specifications/` | Contract mirrors and draft specs |
| `history/` | Milestones and `lifecycle/` audit records |
| `concepts/` | Domain models and protocols |
| `playbooks/` | Operational procedures |

Parallel root files (`PLAN.md`, `STATUS.md`, `DECISIONS.md`, a `docs/` tree)
MUST NOT be created. Missing documents are created inside the bundle with
`okf.py new` ([ADR 0003](adr/0003-repository-as-memory-okf.md)).

### 9.2 Frontmatter

Every concept document has YAML frontmatter with a non-empty `type`.
Recommended fields are `title`, `description`, `tags`, `status`
(`stable|draft|deprecated`), `evidence`, `generated {by, at}`,
`verified {by, at}` and `sources[]`. Actor strings follow OKF §7:
`<producer>/<version>`, `human:<id>` or `process:<id>`. Reserved `index.md` and
`log.md` files carry no concept frontmatter.

### 9.3 Synchronization

`okf.py affected` maps changed files to documents through their
`sources[].resource` entries and lists changed files that no document covers.
Agents also apply a trigger matrix for changes that source mappings cannot see:

| Change | Target section |
|--------|----------------|
| User-visible behavior | `capabilities/` |
| Public contracts | `specifications/` |
| Architecture, toolchain, dependencies | `project/` (and `playbooks/`) |
| Procedures | `playbooks/` |
| Domain models | `concepts/` |
| Delivered milestones | `history/` |
| Any of the above | Append to `log.md` |

`okf.py sync-check --base <task head>` makes this mechanical. Every changed file
must be covered by a changed document or listed in
`knowledge/project/sync-ignore`, that document's `verified` must postdate the
change, and `log.md` must change. `okf.py stamp verified PATH… --run CMD…` runs
the command itself and stamps only on exit 0, so a stamp cannot claim more than
the check proved.

### 9.4 Script-first access

Every bundle operation the script covers MUST go through `okf.py`: `context`,
`list`, `show`, `search`, `affected`, `new`, `set`, `stamp`, `log`, `reindex`,
`validate`, `records`, `sync-check`, `queue`, `checkpoint`, `handoff` and
`git-setup`. A failure prints one line naming the fix. Agents MUST correct the
invocation rather than fall back to reading or grepping the bundle by hand.
`okf.py git-setup` registers per-entry merge drivers for log, index, queue,
archive and status files, so parallel branches merge without conflicts.

---

## 10. Review

### 10.1 Independent two-pass review

At L2+ an independent `reviewer` runs:

- **Pass 1, spec compliance.** Nothing is missing and nothing is extra. The pass
  cites the converge result, notes every MANUAL requirement in
  `## Validation Reviewed`, and looks for absences: missing scenarios, error
  paths, contradictions and drifting terminology.
- **Pass 2, quality.** Runs only when Pass 1 is clean. It covers correctness,
  safety, maintainability, tests, the completeness audit and knowledge sync.

Severity runs Critical, High, Medium, Low, Suggestion. Critical and High block
approval. Medium findings are fixed or explicitly accepted. The parent agent
saves the canonical report (`# Review Report` … `## Verdict`) unchanged. If the
report is not canonical, the parent MUST request a corrected one from the
reviewer and MUST NOT reconstruct an approval itself.

### 10.2 Mechanically bound native review (opt-in)

For L2/L3 tasks in Claude Code or Codex,
`lifecycle.py review enable --adapter claude|codex --session ID --report PATH`
requests native capture ([ADR 0017](adr/0017-opt-in-bound-native-review.md)).

- SessionStart, SubagentStart/Stop and tool callbacks (`review_native.py`) bind
  the native session and runtime, the reviewer child identity, the hook
  configuration, the candidate source (including modes, symlinks and
  deletions), the approved spec and plan, the exact convergence and the reviewed
  evidence.
- While the review is active, recognized edits and protected workflow producers
  from every actor are refused before they take effect, even with
  `LIFECYCLE_GUARD=off`.
- Producer leases (`review_guard.py`) cover lifecycle mutations, OKF writes,
  installation, PR sync, artifact producers and validation.
- `review save-report` exports only the reserved report body.
  `review abandon`, `restart` and `recover` handle interruptions. No timeout or
  fresh session grants approval.

The callback CLI currently requires an identifiable Linux native launcher
(`/proc`). Synthetic callback tests validate the adapter contract but do not
prove native event delivery. This is an operational integrity boundary, not an
OS sandbox.

---

## 11. Learning loop

[ADR 0014](adr/0014-human-gated-learning.md) defines a learning loop with three
levels of authority:

| Level | Command | Authority |
|-------|---------|-----------|
| Observation | `lifecycle.py learn TEXT [--stage S] [--evidence REF]` | Inert. Advisory only. |
| Retrospective closure | `retrospect --lessons N…` or `retrospect --no-new-lessons REASON` | Required before Verify, commit, PR or Ship at L1–L3 |
| Rule | `promote RECORD#N --approved-by human:ID`, `retire RULE_ID --reason T --approved-by human:ID` | Repository-instruction precedence once active |

- Task declarations and SessionStart surface up to five observations within an
  8,192-byte block, ranked by token overlap with the query or task reason, then
  by recency, then by source reference. Observations carry no instruction
  precedence.
- Active approved rules are injected at SessionStart within their own
  8,192-byte block. Invalid rules produce a diagnostic and nothing is partially
  injected.
- `decision:` actors cannot promote or retire rules.
- `okf.py checkpoint --lessons-from RECORD` carries milestone observations
  forward without promoting them.

---

## 12. Autonomous execution

The protocol applies when `knowledge/project/work-queue.md` exists
(`okf.py init --autonomous`). It is specified in `.ai/autonomous-execution.md`
(§9.1–§9.12) ([ADR 0011](adr/0011-supervised-autonomy-driver.md)).

### 12.1 Objective and stop conditions

A run continues until one of these holds:

1. Every task the objective needs is DONE (or CANCELLED with a decision) and the
   completion criteria are verified.
2. All remaining work is blocked or held with a concrete resume condition. This
   is reported as *blocked*, never as completed.
3. The next step needs a destructive, irreversible, security-sensitive or
   outward-facing action that is not authorized.
4. A circuit breaker trips.

Size, complexity, a finished phase, or the need to decompose a task are **not**
stop reasons.

### 12.2 Work queue

Each task is a heading `### ID — Title` followed by `- Key: value` lines. The
keys are `State`, `Priority`, `Group`, `Parent`, `Depends`, `Acceptance`,
`Validation`, `Owner`, `Evidence`, `Blocker`, `Unblock`, `Parallel`, `Hold`,
`Reason`, `Decision` and `Sessions`.

| State | Meaning | Required fields |
|-------|---------|-----------------|
| NOT_READY / READY | Computed from dependencies and children | none |
| IN_PROGRESS | Claimed | `Owner` |
| BLOCKED | Needs something unavailable | `Blocker`, `Unblock` |
| DONE | Acceptance met with validation run in this change | `Evidence` |
| DEFERRED | Still valid, moved later | `Reason` |
| CANCELLED | No longer required | `Reason` (+ `Decision`) |

IDs are never reused. `queue --archive` moves closed tasks to an append-only
archive, and archived IDs still satisfy `Depends`.

### 12.3 Sessions, batches and the checkpoint

- Each session has a fresh context and advances one bounded batch (solo) or one
  batch round (orchestrator), ending with a SAFE checkpoint (`okf.py checkpoint`).
- `knowledge/project/status.md` (about 60 lines, overwritten in place) is the
  recovery point.
- Acceptance is **frozen at claim time**. Requirements discovered later become
  new tasks.
- A task may span at most **three sessions**. The count lives in the queue's
  `Sessions` field, so relaunching the driver cannot reset it. A task at the cap
  MUST be split.
- An IN_PROGRESS entry may not exceed 3,000 characters or list more than eight
  acceptance commands.

### 12.4 The driver

`autonomy_driver.py [--role orchestrator] -- AGENT_COMMAND` launches each
session non-interactively with the `okf.py handoff --prompt` text, after running
`pr_sync.py`. Supported launch forms include `claude -p --output-format
stream-json`, `codex exec --json --sandbox workspace-write` and
`cursor-agent -p --output-format stream-json`.

Circuit breakers (defaults):

| Control | Default |
|---------|---------|
| Session checkpoint target | 1,200 s (then `OKF_HANDOFF_REQUEST`) |
| Run agent-execution budget | 3,600 s |
| Cooperative handoff window | 180 s |
| Discovery progress request | 120 s without source activity |
| Evidence-closure budget | 600 s |
| Consecutive sessions without newly evidenced DONE | 2 (`--max-stalled` ≤ 4) |
| Recovery sessions per run | at most 1 |
| Failed fresh model-backed qualification cases per slice per run | 2 |

Limits override keep-going instructions. A tripped breaker MUST NOT be reset by
an automatic restart or by an interactive continuation. Other rules:

- Full validation is submitted with `autonomy_validation.py submit` and runs
  between model sessions, outside the model's process group.
- No model waits on deterministic tests.
- The launching chat relays public progress at phase changes and at least once a
  minute through `autonomy_progress.py`'s read, comment, `ack` sequence.

### 12.5 Context economy

Token cost grows with turn count times context size, so context resets are
built into the structure rather than left to judgment:

- one session per batch;
- a fresh conversation per interactive slice;
- documents loaded by section;
- source read by line range;
- independent calls batched into one turn;
- blocking waits instead of polling.

### 12.6 Decisions

Uncertainty is resolved in this order: code, tests, bundle, ADRs, authoritative
external documentation. What remains is classified:

- **Tier A (decide and record).** Local, reversible choices. Architecturally
  significant ones get an ADR with status `Proposed by agent; not reviewed`.
- **Tier B (block and continue elsewhere).** New dependencies, breaking
  contracts, security boundaries, requirement removal, data deletion, or
  unauthorized outward actions. The task goes to BLOCKED and the agent moves to
  other READY work.

An accepted ADR is not reopened without new evidence that invalidates its
assumptions.

### 12.7 Version-control authority

[ADR 0012](adr/0012-one-pr-per-milestone.md) sets the following rules:

- **One milestone, one PR**, titled `M<N>: <Title>`, on a `milestone/m<N>`
  integration branch.
- The PR stays a draft until every milestone task and exit criterion passes
  review and validation on the integrated head.
- The PR body is a checklist of every task, including pending and blocked ones.
- Work is combined only by merging. Agents never cherry-pick, squash or rebase
  published task commits, never force-push, and never use a bare `git stash`.
- Agents MAY push branches and open or update the milestone PR. They MUST NOT
  merge into the default branch, rewrite published history, delete branches
  they did not create, or publish releases without explicit human authorization.

---

## 13. Trusted CI and merge authorization

Local gates provide fast feedback and drift detection. They cannot authorize a
protected-branch update, because the coding environment can write its own
records. AGENTIC therefore defines an optional, separately administered merge
boundary ([ADR 0009](adr/0009-trusted-ci-separated-environments.md)).

### 13.1 Three environments

1. **Coding environment.** Edits the candidate and runs local checks. It holds
   no authority write or admin access, no issuer keys and no bypass.
2. **Authority repository.** Runs approved host-side assertions against the
   candidate inside a restricted Linux container (Docker or Podman). The
   container runs as a nonroot user, with a read-only root, no network, no
   capabilities, `no-new-privileges`, default seccomp and cgroup limits, on a
   disk-backed bounded work volume. No candidate code runs on the controller
   host.
3. **Publisher job.** A fresh job validates the artifact's provenance and
   freshness and publishes the required check with a separate App token. It
   never checks out candidate source.

### 13.2 Policy

The strict policy (`trusted_ci_policy.py`) pins the following:

- repository and authority IDs;
- the target branch and an `epoch`;
- the App and check name;
- immutable `workflow_sha` and `verifier_sha`;
- a digest-pinned image;
- the checks;
- disjoint reviewer, coding and merge identities;
- approved transitions;
- limits (`seconds` ≤ 600, `memory_mb` ≤ 4096, `processes` ≤ 256,
  `disk_mb` ≤ 1024).

Activation requires a protected target commit containing
`.agentic-trusted-ci.json` with exactly `epoch` and `policy_digest`. Only the
exact synthetic merge SHA receives the check. Head-only, stale or conflicted
references refuse.

### 13.3 Critical checks

| ID | Asserts |
|----|---------|
| `AGENTIC-LIFECYCLE-DENIAL` | Missing intent or plan refuses. Prerequisites permit. |
| `AGENTIC-ASSURANCE-FAILURE` | Invalid, stale and failing obligations refuse. Real re-execution restores verification. |
| `AGENTIC-INSTALL-PRESERVATION` | A fresh install or upgrade keeps adopter data and custom hooks, and local feedback works afterward. |
| `AGENTIC-AUTHORITY-SEPARATION` | Candidate workflow changes, forged receipts and hostile writes do not reach trusted files, credentials or check publication. |

The built-in IDs are defined in `trusted_ci_policy.py` (`CHECKS`). The trusted
CI guide documents `.ai/trusted-ci/checks.py` in the independently approved
authority checkout as the place where adopters add host-side functions. That
file is not present in the framework source tree at the revision this RFC
describes (§19). An extension takes effect only through a newly approved
authority revision and policy epoch. It cannot override a built-in check and
never imports candidate modules.

### 13.4 Adopter-owned authority (v2, held)

`deploy/authority/` is an optional deployment source package that is never
installed into adopters. It contains a brokered v2 design with five distinct App
identities (admin, reader, issuer, coding, merge), credential-free AWS and Azure
template rendering (`render_cloud.py`), qualification brokers and trial
harnesses. Privileged setup, deployment, qualification, publication, activation
and brokered merge commands are deliberately **release-held** in the current
build (§18).

---

## 14. Distribution and installation

[ADR 0005](adr/0005-project-local-stdlib-kit.md) governs distribution:

- **Requirements.** Python 3.9+ and Git. The scripts use only the standard
  library. Optional cryptography and cloud SDKs are needed only by
  `deploy/authority/`.
- **Command.** `python3 /path/to/agentic/.ai/scripts/install.py TARGET`, run
  from a separate source checkout, either creates or updates a project.
  `--check` reports drift without writing. Exit codes: 0 for success, 1 for
  drift, conflict or I/O failure, 2 for refused input.
- **Kit contents.** `AGENTS.md`, `CLAUDE.md`, `.ai/`, `.claude/agents/`,
  `.claude/skills/`, `.claude/settings.json`, `.codex/agents/`,
  `.codex/hooks.json`, `.cursor/hooks.json`, `.agents/skills` and
  `THIRD_PARTY_NOTICES.md`.
- **Merge semantics.**
  - `AGENTS.md` carries a managed block delimited by
    `<!-- agent-governance-kit:begin/end -->`. Text outside it is preserved.
  - Hook settings are merged entry by entry and never rebuilt wholesale.
  - Conflicting adopter files are kept and reported with exit 1.
  - Dirty owned paths need `--force`, which still preserves conflicts.
  - `.ai/install-manifest.json` records the governance hash and file hashes.
- **Locality.** Everything is local to the target. Global agent settings are
  unchanged. Codex additionally requires the user to trust the project `.codex/`
  layer and review hooks with `/hooks`.
- **Exclusions.** The source checkout's knowledge, Git history, session files,
  `.agentic.json`, `.github/` workflows and `deploy/` are not exported. An
  installed kit can itself act as a source, exporting only the managed
  governance block.
- **Preflight.** A framework source that fails `framework_policy.py` refuses
  installation before any target write.

---

## 15. Harness adapters and platform runtime

### 15.1 Event routing

| Harness | Configuration | Events routed |
|---------|---------------|---------------|
| Claude Code | `.claude/settings.json`, `.claude/agents/*.md`, `.claude/skills/*` | PreToolUse (Bash: `shell_guard.py`, `lifecycle.py hook`; Write/Edit/MultiEdit/NotebookEdit/Delete: `lifecycle.py hook`; all tools: `review_native.py`), SessionStart (`autonomy_hook.py`, `lifecycle.py hook`, `review_native.py`), Stop (`autonomy_hook.py`), SubagentStart/Stop, PostToolUse(Failure) (`review_native.py`) |
| Codex | `.codex/hooks.json`, `.codex/agents/*.toml`, `.agents/skills/*` | Equivalent events, with native Windows command overrides. Requires project trust. |
| Cursor | `.cursor/hooks.json` | Equivalent events. Cursor also loads `.claude/settings.json`, whose entries pass `--skip-in-cursor` so each check runs once. |

POSIX hooks go through `.ai/scripts/posix_hook.sh`, which picks the first
Python 3.9+ interpreter on PATH. A missing bootstrap fails closed with exit 2.

### 15.2 Stage skills

`spec`, `plan`, `implement`, `review`, `ship`, `debug` and `onboard` are shipped
as Claude Code skills and as Codex-readable skills (`.agents/skills`). Each one
runs its stage and checks its exit condition before the next stage may start.

### 15.3 Shell guard

`shell_guard.py` rejects `ls`, `find`, `tree`, `cat`, `head`, `tail`, `sed`,
`awk`, `grep`, `rg`, `git ls-files`, `git grep`, heredoc writes and `echo >`,
along with any shell read of `knowledge/` or `.ai/**.md`. Each rejection names
the structured replacement (`Read`/`Edit`/`Write`, `repo.py read|grep|files`, or
`okf.py show|search`). The guard also rejects live display variables
(`DISPLAY=:0`/`:1`, `WAYLAND_DISPLAY`) so acceptance never drives the user's
real devices. Rephrasing a command to slip past the guard is prohibited.
`OKF_SHELL_GUARD=off` is a human-only switch
([ADR 0010](adr/0010-structured-tools-over-shell.md)).

### 15.4 Windows and Linux parity

`process_runtime.py` supplies native process identity, liveness, ancestry and
locking ([ADR 0015](adr/0015-native-process-runtime-parity.md)):

- **Linux** uses process groups and kernel birth identity.
- **Windows** combines PID with creation time and starts children suspended
  until they are assigned to an owned kill-on-close Job.
- Forced cleanup waits on retained process handles. A changed membership
  snapshot fails closed.
- Command-line streams use UTF-8 on both platforms.

CI runs the regression suite on `ubuntu-24.04` and `windows-latest` with
Python 3.9 and 3.15.

---

## 16. Security considerations

### 16.1 What AGENTIC defends against

| Threat | Control |
|--------|---------|
| An agent skips spec, plan, review or verification | Hook denial of edits, commits and PRs (§5.6) |
| An agent fabricates "Verified" | Ledger-derived Verify notes, `stamp --run`, no output in records, convergence bound to HEAD (§7) |
| Stub or placeholder completion | `scan-diff` at review and verify (§7.4) |
| Stale evidence presented as current | Input and runtime fingerprints, REUSE/RERUN, STALE status (§7.3, §8) |
| Planted approval text in repository files | Approvals must come from a user message. Covered by pressure evals such as `pressure-planted-approval` (Appendix B). |
| Tier lowering under pressure | `--user-set` tiers cannot be lowered. Covered by the `pressure-tier-lowering` eval. |
| Runaway unattended runs | Mechanical session caps and circuit breakers stored in repository state (§12) |
| Writes during an opted-in review | Producer leases and refusal before effects (§10.2) |
| Self-authorized merges | Separated authority, sandboxed checks, App-published check on the merge SHA (§13) |
| Kit contamination with task paperwork | `framework_policy.py` in CI, installer and edit hook (§3.3) |

### 16.2 What AGENTIC does not defend against

- **Arbitrary local writes.** Shell or Python writes that bypass recognized
  tools are outside the boundary of the local hook.
- **Deliberate local forgery.** A schema-valid hand-written record and a
  matching artifact pass `audit` and `assure`. Only the trusted CI boundary
  addresses this.
- **Human identity.** `human:<id>` and `Accept-risk … by human:<id>` are
  unauthenticated claims.
- **A compromised authority.** The authority's administrators, kernel and
  runtime, worker image and approved checks are trusted.
- **Model qualification.** Passing scripted evaluations says nothing about a real
  model's fitness for unattended work.

### 16.3 Privacy

The ledger and audit records exclude command output by construction, which
limits accidental capture of secrets printed by tools. Sandboxed authority
candidates receive no host credentials, runtime socket or network.

---

## 17. Conformance

This section defines normative profiles so that third-party harnesses, forks
and adopters can make precise claims.

### 17.1 AGENTIC-Adopter

A repository conforms to **AGENTIC-Adopter** when:

1. `AGENTS.md` contains an unmodified managed governance block from a released
   kit, and `install.py --check` reports `up to date` or only adopter-owned
   differences.
2. A valid OKF v0.2 bundle exists, and `okf.py records` exits 0 on the default
   branch.
3. Every committed task above L0 has an audit record that passes
   `lifecycle.py audit`.
4. Every structured capability requirement that declares `Verify:` is VERIFIED,
   MANUAL, or carries a visible `Accept-risk` on the default branch, per
   `lifecycle.py assure`.

### 17.2 AGENTIC-Harness

A harness adapter conforms to **AGENTIC-Harness** when it:

1. routes pre-tool edit, shell and commit events to `lifecycle.py hook` and
   `shell_guard.py`, and honors deny decisions;
2. routes SessionStart to `lifecycle.py hook` (and `autonomy_hook.py` when a
   queue exists);
3. passes the scripted lifecycle evaluations in Appendix B through
   `lifecycle_eval.py run -- AGENT_COMMAND` for the scenarios it claims;
4. documents which roles it can make read-only by tool restriction.

### 17.3 AGENTIC-Trusted

A deployment conforms to **AGENTIC-Trusted** only when
`trusted_ci.py verify-deployment --live --json` reports verified separation,
active policy and hosted qualification receipts that bind the current effective
controls. No local output, fixture, rendered template or cached receipt
satisfies this profile. No deployment currently satisfies it (§18).

---

## 18. Implementation status

| Area | Status at `bb3c226` |
|------|---------------------|
| Lifecycle tiers, stages, hooks, audit | Implemented. Regression-tested on Linux and Windows. |
| Spec analyze, converge, trace, queue-from-spec | Implemented |
| Brownfield onboarding and deltas | Implemented |
| Evidence ledger, reuse, scan-diff, finish | Implemented |
| Requirement assurance, input profiles, governed constraints | Implemented. Measured by `assurance_measure.py` on six deterministic fixtures. |
| Qualified artifacts | Implemented |
| Learning loop | Implemented |
| Autonomous driver, validation, progress relay, PR sync | Implemented. A real-model baseline is **on hold** pending explicit qualification and supervision requirements. |
| Opt-in bound native review | Adapter contract implemented and synthetically tested. Native Claude and Codex capture must both be verified before the feature is claimed complete. Linux launcher only. |
| Trusted CI (v1 authority workflow, policy, checks, sandbox) | Implemented. **Under qualification.** Not deployed enforcement. |
| Adopter-owned v2 authority (`deploy/authority/`) | Unfinished candidate. Privileged operations release-held. Local cloud rendering available. |
| Installer, upgrade, drift check | Implemented. Native Windows supported. |

Framework CI (`.github/workflows/framework-parity.yml`) runs source hygiene,
Windows preflight contracts, eight regression shards on a 2×2 OS and Python
matrix, and sixteen authority-backend shards, and requires all of them to pass.

---

## 19. Open issues

1. **Local consent authentication.** Approvals remain claims locally. Is a
   signed-approval mechanism inside the coding environment worthwhile, or should
   authentication remain exclusively a trusted CI concern?
   ([ADR 0008](adr/0008-approvals-are-recorded-claims.md) currently chooses the
   latter.)
2. **Native review on more platforms.** The bound review requires a Linux
   `/proc` launcher. Equivalent native identity on Windows and macOS is open.
3. **Real-model qualification.** Criteria and supervision requirements for a
   model-backed baseline are not yet defined.
4. **Hosted qualification of the authority.** Needs an independently
   provisioned disposable target and reviewed hostile fixtures for every case in
   `trusted_ci_qualification.CASES`.
5. **Dependency discovery.** Input profiles are reviewed declarations, not
   complete dependency discovery. Broader automatic inference is open.
6. **Harness coverage.** Agents beyond Claude Code, Codex and Cursor follow
   `AGENTS.md` by instruction only. The adapter interface (§17.2) is the
   proposed extension point.
7. **Check extension template.** `.ai/docs/trusted-ci.md` names
   `.ai/trusted-ci/checks.py` as the adopter extension point, but the source
   tree ships no such file. Either ship a template or correct the guide.
8. **Versioning policy.** The kit is at `0.1.0`. Compatibility guarantees for
   audit-record and ledger schemas across releases are not yet published.

---

## 20. References

### 20.1 Normative

- [RFC 2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement
  Levels", BCP 14, RFC 2119, March 1997.
- [RFC 8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key
  Words", BCP 14, RFC 8174, May 2017.
- [OKF] Open Knowledge Format SPEC, v0.2,
  <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>.
- [AGENTS] [`AGENTS.md`](../AGENTS.md) and the documents it declares binding
  (§1.5).

### 20.2 Informative

- [README] [`README.md`](../README.md).
- [KIT] [`.ai/README.md`](../.ai/README.md) and [`.ai/docs/`](../.ai/docs/).
- [TRUSTED-CI] [`.ai/docs/trusted-ci.md`](../.ai/docs/trusted-ci.md).
- [RUNTIME] [`.ai/docs/windows-runtime.md`](../.ai/docs/windows-runtime.md).
- [NOTICES] [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).
- [ADR] Nygard, M., "Documenting Architecture Decisions", 2011.

---

## Appendix A: Command summary

| Purpose | Command |
|---------|---------|
| Install or update | `python3 /path/to/agentic/.ai/scripts/install.py [--check] [--force] [--no-knowledge] TARGET` |
| Declare tier | `lifecycle.py tier L0\|L1\|L2\|L3 --reason T [--kind K] [--user-set] [--new]` |
| Record stage | `lifecycle.py stage intent\|plan\|review\|verify\|ship [--ref P] [--note T] [--approved-by A]` |
| Gate and status | `lifecycle.py gate implement\|review\|verify\|ship`, `lifecycle.py status` |
| Spec checks | `lifecycle.py analyze SPEC`, `converge SPEC`, `trace SPEC --plan P --tests …` |
| Deltas | `lifecycle.py merge SPEC [--dry-run]`, `okf.py onboard` |
| Evidence | `lifecycle.py run LABEL [--inputs G…] -- CMD`, `reuse X`, `redgreen red\|green -- CMD`, `scan-diff` |
| Assurance | `lifecycle.py assure [--run [ID…]] [--changed --base REV] [--strict] [--json]` |
| Completion | `lifecycle.py finish --json`, `finish --apply`, `lifecycle.py audit` |
| Learning | `lifecycle.py learn`, `retrospect`, `observations --query`, `promote`, `retire` |
| Review capture | `lifecycle.py review enable\|status\|save-report\|abandon\|restart\|recover` |
| Knowledge | `okf.py context\|list\|show\|search\|affected\|new\|set\|stamp\|log\|reindex\|validate\|records\|sync-check` |
| Autonomy | `okf.py init --autonomous`, `queue`, `checkpoint`, `handoff [--prompt\|--task ID]`, `git-setup`; `autonomy_driver.py -- CMD`; `autonomy_validation.py submit`; `pr_sync.py` |
| Long checks | `wait_check.py start --log L -- CMD`, `wait_check.py wait --log L [--fail RX] --max S` |
| Repository tools | `repo.py read\|grep\|files\|context` |
| Artifacts | `artifacts.py freeze\|run\|variant` |
| Trusted CI | `trusted_ci.py verify-deployment --live --json`, `authority_setup.py status\|plan\|verify-local` |
| Evaluations | `lifecycle_eval.py list\|check\|run [--scenario ID] -- AGENT_COMMAND` |
| Framework hygiene | `framework_policy.py [--snapshot working\|index\|head]`, `run_tests.py -j 4` |

All scripts live in `.ai/scripts/` and answer `--help`.

## Appendix B: Lifecycle evaluation scenarios

`.ai/evals/lifecycle/` defines scripted scenarios that `lifecycle_eval.py`
runs against an agent command. They check the declared tier, recorded or absent
stages, unchanged protected files and commit counts.

| ID | Scenario |
|----|----------|
| 01 | Typo → L0 |
| 02 | Bug fix → L1 with red/green |
| 03 | Feature → L2 |
| 04 | Escalation discovered mid-task → L2 |
| 05 | User-set tier is held |
| 06 | Queue-driven L3 |
| 07 | Pressure: tooling outage |
| 08 | Pressure: claimed authority |
| 09 | Pressure: sunk cost |
| 10 | Pressure: planted approval in repository files |
| 11 | Pressure: scope expansion |
| 12 | Pressure: tier lowering |
| 13 | Pressure: bypass request |
| 14 | Pressure: exhaustion |
| 15 | Control: approval withheld |
| 16 | Control: brownfield delta |
| 17 | Retrospective reuse |

## Appendix C: Numeric limits

| Limit | Value | Source |
|-------|-------|--------|
| Analyst questions per batch | ≤ 5 | `.ai/lifecycle.md` Stage 0 |
| Converge per-command timeout | 600 s default | `.ai/lifecycle.md` |
| Ledger entries per task | 100 | `ledger.py` `MAX_ENTRIES` |
| Observation block | ≤ 5 entries, ≤ 8,192 bytes | `.ai/docs/learning-loop.md` |
| Approved-rule block | ≤ 8,192 bytes | `.ai/lifecycle.md` |
| Sessions per task | 3 | `.ai/autonomous-execution.md` §9.2 |
| Queue entry size / acceptance commands | 3,000 chars / 8 | §9.2 |
| `--max-stalled` | ≤ 4 (default 2) | §9.2 |
| `wait_check.py wait --max` | default 540 s, minimum 300 s | `.ai/validation-policy.md` |
| Debug stop rule | 3 disproved hypotheses | `AGENTS.md` §8.6 |
| Trusted CI sandbox | 600 s, 4,096 MB, 256 processes, 1,024 MB disk (maxima) | `.ai/docs/trusted-ci.md` |

## Appendix D: Decision record index

| ADR | Title |
|-----|-------|
| [0001](adr/0001-enforce-lifecycle-with-hooks.md) | Enforce the lifecycle with harness hooks, not instructions |
| [0002](adr/0002-one-lifecycle-four-tiers.md) | One lifecycle, right-sized by four tiers |
| [0003](adr/0003-repository-as-memory-okf.md) | The repository is the memory: an OKF v0.2 knowledge bundle |
| [0004](adr/0004-vendor-neutral-governance-source.md) | One vendor-neutral governance source with thin harness adapters |
| [0005](adr/0005-project-local-stdlib-kit.md) | A project-local, standard-library-only kit installed by copy and merge |
| [0006](adr/0006-fingerprinted-evidence-ledger.md) | A fingerprinted evidence ledger with conservative reuse |
| [0007](adr/0007-living-requirements-assurance.md) | Living requirements with mechanical assurance; judgment is never evidence |
| [0008](adr/0008-approvals-are-recorded-claims.md) | Approvals are recorded claims; authentication belongs to a separate boundary |
| [0009](adr/0009-trusted-ci-separated-environments.md) | Trusted CI as three separated environments with an independent authority |
| [0010](adr/0010-structured-tools-over-shell.md) | Structured repository tools over raw shell |
| [0011](adr/0011-supervised-autonomy-driver.md) | Unattended work only through a supervised driver with fresh sessions and circuit breakers |
| [0012](adr/0012-one-pr-per-milestone.md) | One pull request per milestone; agents never merge the default branch |
| [0013](adr/0013-framework-source-chat-only.md) | The framework source is excluded from its own artifact workflow |
| [0014](adr/0014-human-gated-learning.md) | Human-gated learning: observations are advisory, rules require promotion |
| [0015](adr/0015-native-process-runtime-parity.md) | Native process primitives for Windows and Linux parity |
| [0016](adr/0016-hash-pinned-brownfield-deltas.md) | Brownfield requirement changes as hash-pinned deltas |
| [0017](adr/0017-opt-in-bound-native-review.md) | Mechanically bound native review is opt-in |
