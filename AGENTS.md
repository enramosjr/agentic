# Agent Governance & OKF Synchronization Protocol

This document establishes the mandatory governance standards, workflow gates, evidence rules, and persona/agent selection protocols for all AI agents (coding assistants, autonomous subagents, and human-agent pair programmers) operating within this repository.

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in BCP 14 ([RFC 2119](https://www.rfc-editor.org/rfc/rfc2119), [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174)) when, and only when, they appear in all capitals, as shown here. The same words in lowercase carry their ordinary English meaning and are not normative. The "Behavioral Guidelines" at the end of this document are written as plain-language guidance and are outside this convention.

**Start here:** pick the lifecycle tier (§2.5), then follow `.ai/lifecycle.md` for the stages that tier requires: Intent, Plan, Implement, Review, Verify & Sync, Ship.

---

## 1. Core Mandate: Open Knowledge Format (OKF) Synchronization

All AI agents working on this project MUST ensure that the Open Knowledge Format corpus (`knowledge/`) remains synchronized with any code, specification, architecture, or workflow changes introduced during execution.

### Rationale & Purpose
The OKF corpus (`knowledge/`) is the machine-readable, persistent knowledge graph of the repository. It serves as the primary context for future AI agents and human contributors. When codebase changes occur without corresponding OKF updates, agent drift and knowledge decay occur.

- **Requirement**: Any agent change that alters functionality, contracts, specifications, dependencies, or architectural patterns MUST update the corresponding OKF document(s) and append a log entry to `knowledge/log.md`.
- **Scope**: Code changes are not considered complete until OKF synchronization is verified and updated where relevant.
- **Bootstrap**: If `knowledge/` does not exist yet, create it with `python3 .ai/scripts/okf.py init` before the first OKF update.

---

## 2. Mandatory Persona & Agent Context Selection (`.ai/` Integration)

All AI agents working on this codebase MUST automatically detect the active language, file context, and task role, check the `.ai/` directory, and apply the corresponding principal engineering persona and agent guidelines. This document is the repository-level authorization for automatic persona selection referenced by the agent role files.

### 2.1 Language & Domain Persona Mapping

When inspecting, editing, or reviewing files, agents MUST load the matching persona from `.ai/personas/`:

| File Context / Extension | Target Language / Surface | Persona File |
|--------------------------|---------------------------|--------------|
| `.rs`, `Cargo.toml` | Rust | [`.ai/personas/rust-principal-engineer.md`](.ai/personas/rust-principal-engineer.md) |
| `.py`, `.pyi`, `.ipynb`, `pyproject.toml` | Python | [`.ai/personas/python-principal-engineer.md`](.ai/personas/python-principal-engineer.md) |
| `.js`, `.mjs`, `.cjs`, `.ts`, `.mts`, `.cts`, `.jsx`, `.tsx`, `package.json`, `tsconfig.json` | JavaScript & TypeScript | [`.ai/personas/javascript-typescript-principal-engineer.md`](.ai/personas/javascript-typescript-principal-engineer.md) |
| `.go`, `go.mod` | Go | [`.ai/personas/go-principal-engineer.md`](.ai/personas/go-principal-engineer.md) |
| `.cs`, `.csproj`, `.sln` | C# | [`.ai/personas/csharp-principal-engineer.md`](.ai/personas/csharp-principal-engineer.md) |
| `.dart`, `pubspec.yaml` | Dart & Flutter | [`.ai/personas/dart-flutter-principal-engineer.md`](.ai/personas/dart-flutter-principal-engineer.md) |
| `.swift`, `Package.swift` | Swift & SwiftUI | [`.ai/personas/swift-swiftui-principal-engineer.md`](.ai/personas/swift-swiftui-principal-engineer.md) |
| Any other language or surface | No dedicated persona | Follow the repository's existing conventions and the agent role file alone. |

### 2.2 Task Role & Agent Selection

Depending on the operational stage of the task, agents MUST align with the appropriate role definition in `.ai/agents/`:

| Task Stage / Workflow | Agent Role File | Core Focus |
|-----------------------|-----------------|------------|
| Clarifying a request into a testable spec before planning (tier L1+, §2.5) | [`.ai/agents/analyst.md`](.ai/agents/analyst.md) | Behavior-changing questions, requirements, acceptance criteria |
| Planning, codebase investigation, and architectural design | [`.ai/agents/planner.md`](.ai/agents/planner.md) | Read-only discovery, factual trade-offs, implementation-ready plans |
| Plan execution, coding, refactoring, bug fixes, test implementation | [`.ai/agents/implementer.md`](.ai/agents/implementer.md) | Surgical edits, minimal code, task plan execution, validation |
| Reviewing plans, designs, diffs, or completed work | [`.ai/agents/reviewer.md`](.ai/agents/reviewer.md) | Evidence-based findings, severity, validation quality |
| Managing the work queue, dispatching and integrating tasks in autonomous mode (§9) | [`.ai/agents/orchestrator.md`](.ai/agents/orchestrator.md) | Task selection, delegation, integration, checkpoints |

The analyst, planner, implementer, and reviewer are also registered as subagents in `.claude/agents/` (read by Claude Code and Cursor) and `.codex/agents/` (read by Codex). Delegated analysis, planning, and review SHOULD use them. In Claude Code and Cursor the analyst, planner, and reviewer run read-only by tool restriction. Codex custom agents cannot set a sandbox, so their read-only rule is an instruction only, and Codex spawns subagents only when asked: name the role in the prompt (for example "have reviewer check this diff").

### 2.3 Operational Loading Rules

1. **Context Identification**: Upon receiving a task or operating on files, identify the applicable task role and language persona.
2. **Selective Segment Loading**: Agents MUST NOT read a whole persona or role file. Run `python3 .ai/scripts/okf.py show .ai/personas/<persona>.md --outline --depth 2`, then load only the pertinent sections with `--section HEADING` (repeatable). Load role files in `.ai/agents/` the same way.
3. **Multi-Stack Tasks**: For tasks spanning several languages, use one primary persona for the area that dominates implementation risk and apply others only within their files.

### 2.4 Persona Contract (single source of truth)

This section is the only place persona selection and authority are defined. The agent role files do not restate it.

- **Selection**: A persona is selected by explicit instruction (`Persona: .ai/personas/go-principal-engineer.md`, `Use persona: go-principal-engineer`, or a plain request) or automatically from the §2.1 table, which this document authorizes. A bare name resolves to `.ai/personas/<name>.md`. When selecting automatically, agents MUST state the persona and why before starting.
- **Role**: A persona is advisory. It supplies language pitfalls, validation commands, and a review checklist. It MUST NOT change the requested outcome, override acceptance criteria or the approved plan, expand scope, force a pattern, or turn preferences into requirements or defects.
- **Application**: Load the outline, then only the sections relevant to the task (§2.3). Agents SHOULD NOT apply every item to every task.
- **Precedence** (highest first): explicit user instructions, acceptance criteria, the approved plan, repository and directory instructions, executable code/config/schemas/tests, project knowledge, the persona, existing repository conventions, general engineering judgment, personal preference. A review finding MUST rest on a source above the persona.
- **Multiple personas**: One primary persona governs; secondary personas apply only inside their own files. Agents MUST NOT combine personas merely because several technologies are present.
- **Reporting**: Name the persona used (or `None`) and only the considerations that materially changed the result.

### 2.5 Lifecycle & Right-Sizing (single source of truth)

Every task, from a one-line prompt to an autonomous milestone, follows one lifecycle: **Intent → Plan → Implement → Review → Verify & Sync → Ship**. Stage detail lives in [`.ai/lifecycle.md`](.ai/lifecycle.md); load it by section (§2.3). The stages and artifacts are the same at every size. The tier sets how much ceremony each stage gets, not whether it exists.

| Tier | Applies when | Required |
|------|--------------|----------|
| **L0** trivial | A typo, comment, or constant change with no behavior, contract, or test effect | Implement, focused check if one exists, `okf.py affected` |
| **L1** small | A bounded change in a few files with no contract, schema, persistence, security, or dependency effect | Three-line intent note, light plan, test-first for logic and bug fixes, self-review, focused checks |
| **L2** feature | New or changed behavior, any contract effect, several modules, or an ambiguous request | Approved spec, full plan, isolated branch, independent review, slice E2E, then the full gate once |
| **L3** milestone | Queued or autonomous work (§9) | The queue is the artifact set: objective and frozen `Acceptance` are the spec, the batch plan is the plan, and the reviewer gates DONE |

- Agents MUST state the tier and its reason in the first message, next to the persona. They MUST choose the lowest tier whose conditions hold.
- Agents MUST escalate as soon as investigation shows a contract, schema, persistence, security, or dependency effect, or a behavior question the repository cannot answer. Agents MUST NOT lower a tier the user set.
- At L2 and above, agents MUST NOT start Implement while the spec has an unresolved question that changes behavior. With a human, the user approves the spec and plan. At L3, open decisions resolve by tier (§9.7).
- Tiers scale the spec, plan, review, and gate breadth. They MUST NOT relax §8.1, Gate 3, or the evidence rules.
- **Enforcement.** Agents MUST declare the tier with `lifecycle.py tier` and record each required stage with `lifecycle.py stage` as it completes; `stage` validates the artifact (a lint-clean spec, a plan that cites every requirement ID, an Approved review verdict, a passing `okf.py records`). The same script runs as a hook in Claude Code, Codex and Cursor: it denies source edits until a tier is declared and the stages that tier requires are recorded, denies `git commit` (other than `wip:`) and PR creation until Verify is recorded, and injects the router at session start. Markdown and `knowledge/` edits are exempt. `LIFECYCLE_GUARD=off` disables it, and autonomous driver sessions (`OKF_AUTONOMOUS=1`) are gated by the work queue instead. Approvals are recorded claims: `--approved-by human:<id>` MUST come from a user message, and `decision:<ADR>` only under §9.7. The hook raises the cost of skipping a stage; it cannot prove that a human approved.

---

## 3. OKF Structure Overview

The OKF bundle resides in the `knowledge/` directory and follows the OKF v0.2 layout. `okf.py init` creates the root files and the standard sections below:

| Path | Purpose | Update Trigger |
|------|---------|----------------|
| `knowledge/index.md` | Entry point & root index for the OKF bundle | Adding or removing root bundle sections |
| `knowledge/log.md` | Chronological log of all OKF updates | **Mandatory on every OKF update** |
| `knowledge/project/` | Architecture, development setup, evidence rules, boundaries | Architectural shifts, directory re-organizations, boundary/policy updates |
| `knowledge/capabilities/` | What the product does: features and user-visible behavior | Adding, modifying, or deprecating capabilities |
| `knowledge/specifications/` | Normalized views of product contracts | Updating product contracts or implementation guidance |
| `knowledge/history/` | Dated implementation arc and delivery milestones | Updating implementation history or milestones |
| `knowledge/concepts/` | Domain concepts, data models, or protocol definitions | Introducing new core domain models or protocol definitions |
| `knowledge/playbooks/` | Operational, setup, and troubleshooting playbooks | Adding or revising developer or deployment operational guides |
| `knowledge/project/work-queue.md` | Execution state of planned tasks (§9); created by `okf.py init --autonomous` | Claiming, completing, blocking, or decomposing a task |
| `knowledge/project/status.md` | Recovery checkpoint a fresh agent resumes from (§9) | Every checkpoint; overwritten in place |
| `knowledge/project/work-queue-archive.md` | Closed tasks moved out of the queue (§9.3); written by `okf.py queue --archive` | Closing tasks |

### 3.1 OKF Tooling (`.ai/scripts/okf.py`) — Script First

Any OKF operation the script covers MUST go through it instead of reading, grepping, or hand-editing `knowledge/`. It is deterministic, stdlib-only (Python 3.9+), and prints compact output. Read a full document only when you need its prose.

| Need | Command (`python3 .ai/scripts/okf.py …`) |
|------|------------------------------------------|
| Discover context when no queue handoff/worker brief is available | `context [--log N]` |
| Create the bundle skeleton | `init` |
| Discover docs (one line each) | `list [--type T] [--tag T] [--status S] [--under DIR] [--long]` |
| Read cheaply (several docs per call) | `show PATH [PATH…]` (frontmatter + outline with line numbers), `--outline --depth N`, `--section HEADING`, `--lines A-B`, `--meta`, `--body` |
| Load a persona, role file, or any repo `.md` selectively (no bundle needed) | `show .ai/personas/X.md --outline --depth 2`, then `show … --section HEADING` |
| Find text across the bundle (skips `log.md`) | `search PATTERN [--regex 'a\|b'] [--under DIR\|FILE] [--count] [--include-log] [--limit N]` |
| Which docs a change affects | `affected [PATHS…]` (default: git changes vs `HEAD`; matches `sources[].resource`) |
| New concept doc with full frontmatter | `new PATH --type T --title X --description D [--tags a,b] [--source path[=Title]]…` |
| Edit frontmatter in place | `set PATH key=value…`, `stamp verified PATH… --by "process:<command>"` |
| Log entry (dated, newest-first) | `log "message" [--date YYYY-MM-DD]` |
| Regenerate `index.md` listings | `reindex [--check]` (only rewrites the `okf:index` marker block) |
| Gate 4 structural check | `validate [--strict] [--json]` (exit 1 on errors) |
| Commit-boundary records gate (validate errors + `reindex --check` + `git diff --check`) in one call | `records [--base REV]` |
| Run a long check without model polling (`.ai/scripts/wait_check.py`) | `wait_check.py start --log LOG -- CMD`, then `wait_check.py wait --log LOG [--fail RX] [--done RX] --max SECONDS` |
| Create the work queue and status checkpoint | `init --autonomous` |
| Task states (READY computed from dependencies) and what to start next | `queue [--next] [--state S] [--limit N] [--json]` |
| Move DONE and CANCELLED tasks to the archive | `queue --archive` |
| Is the repository resumable right now? | `checkpoint [--json]` (exit 1 when unsafe) |
| Resume material from repository state | `handoff` (digest), `handoff --prompt [--role orchestrator]` (fresh-session prompt), `handoff --task ID` (worker brief) |
| Run the queue as fresh agent sessions (`.ai/scripts/autonomy_driver.py`) | `autonomy_driver.py [--role orchestrator] -- AGENT_COMMAND` |
| Merge parallel branches' log, index, queue and status without conflicts (once per clone) | `git-setup` |
| Keep agent PRs mergeable after base-branch merges (`.ai/scripts/pr_sync.py`) | `pr_sync.py [--dry-run]` |
| Declare the tier, record and gate lifecycle stages, record red/green evidence (`.ai/scripts/lifecycle.py`) | `lifecycle.py tier L0\|L1\|L2\|L3 --reason T [--kind K]`, `stage NAME [--ref P] [--note T] [--approved-by A]`, `gate TARGET`, `status`, `redgreen red\|green -- CMD` |
| Check spec → plan → tests coverage, and turn a spec into work-queue entries | `lifecycle.py trace SPEC [--plan P] [--tests PATH…]`, `lifecycle.py queue-from-spec SPEC [--group G]` |
| Run the lifecycle scenario evals against a real agent (`.ai/scripts/lifecycle_eval.py`) | `lifecycle_eval.py list\|check\|run [--scenario ID] -- AGENT_COMMAND` |

Path conventions follow the OKF SPEC (§6.1, §6.2): links and path fields are either URLs, bundle-relative paths beginning with `/`, or paths relative to the containing document. `new --source` and `affected` take **repo-relative** paths and convert them for you. Set `OKF_ACTOR` (e.g. `agent/<model-id>`) so `generated.by` is attributed. `stamp verified` records only the actor you pass, so stamp only after the cited command actually ran and passed (§8.5). Tests: `python3 -m unittest discover -s .ai/scripts/tests`.

**When a command fails**, its error is one line and names the fix (a missing doc lists close matches; `affected` outside git asks for explicit paths). Correct the invocation and rerun; you MUST NOT fall back to reading or grepping `knowledge/` by hand.

**Allowed field values and `validate` rules** are printed by `okf.py --help`; per-command options by `okf.py COMMAND --help`. Agents MUST NOT grep or read `okf.py` source to learn them.

**Files the script does not cover** (source code, configuration, tests, and OKF body prose): use the harness's own tools and MUST NOT use the shell. They take structured arguments and return bounded, line-numbered output, so there is no command to compose.

| Need | Claude Code | Cursor | Codex | Never |
|------|-------------|--------|-------|-------|
| Read a file or line range | `Read` (`offset`, `limit`) | `Read` | `python3 .ai/scripts/repo.py read PATH [--lines A-B]` | `cat`, `head`, `tail`, `sed -n`, `awk`, whole-file `repo.py grep '^'` |
| Search contents | `python3 .ai/scripts/repo.py grep PATTERN [--regex] [-i] [--glob G] [--under DIR] [--count]` | `Grep` | `repo.py grep …` | `grep`, `rg`, `git grep` |
| Find files | `python3 .ai/scripts/repo.py files 'GLOB'… [--under DIR] [--depth N]` | `Glob` | `repo.py files …` | `ls`, `find`, `tree`, `git ls-files` |
| Create or edit a file | `Write`, `Edit` | `Write`, `StrReplace` | `apply_patch` | heredocs, `sed -i`, `tee`, `echo >`, Python scripts that write files |

Claude Code has no `Glob` or `Grep` tool and Codex has no file-read tool, so `repo.py` fills those gaps: it respects `.gitignore`, skips binaries, and caps output (`--limit`; `read` prints at most 250 numbered lines and names the next range). Agents MUST use it in any harness that lacks those tools. Read source by range: find the lines with `repo.py grep`, then read only those. Shell is for running things: builds, tests, git, `okf.py`, and `repo.py`. Piping a command's output through `head`, `tail`, or `rg` is fine.

**Enforcement.** `.ai/scripts/shell_guard.py` runs before every shell command (`.claude/settings.json` for Claude Code, `.cursor/hooks.json` for Cursor, `.codex/hooks.json` for Codex, which loads project hooks only from a trusted `.codex/` layer and after review with `/hooks`). It rejects the "Never" column above, and any shell read of `knowledge/` or `.ai/**.md`, with a message naming the replacement. Paths outside the project and under `/tmp` are allowed. When a command is blocked, switch to the named tool or script; you MUST NOT rephrase the command to slip past the guard (`git ls-files`, `git grep`, or a Python one-liner doing the same job). If the named tool does not exist in your session, use the `repo.py` / `okf.py` command from the message. A human MAY disable it by launching the agent with `OKF_SHELL_GUARD=off`.

---

## 4. OKF Relevance Trigger Matrix

`okf.py affected` is the first-pass detector: it maps changed files to the docs that cite them in `sources` and lists changed files no doc covers. Agents MUST also check their changes against this matrix, which covers changes that `sources` mappings cannot see:

| Category of Change | Typical Workspace Paths | Required OKF Action | OKF Target Section |
|--------------------|-------------------------|---------------------|--------------------|
| **User-visible behavior** | Feature code, UI, CLI commands, endpoints | Add or update the capability doc | `knowledge/capabilities/` |
| **Public contracts** | API definitions, schemas, wire formats, config formats, exported interfaces | Update the specification mirror | `knowledge/specifications/` |
| **Architecture & boundaries** | New, moved, or removed modules, packages, services; dependency direction | Update architecture and boundary docs | `knowledge/project/` |
| **Build, toolchain, dependencies** | Build files, lockfiles, CI configuration, developer scripts | Update the development guide and setup playbooks | `knowledge/project/`, `knowledge/playbooks/` |
| **Operational procedures** | Deployment, release, migration, troubleshooting steps | Add or revise the playbook | `knowledge/playbooks/` |
| **Domain models** | Core entities, data models, protocols | Add or update the concept doc | `knowledge/concepts/` |
| **Delivered milestones** | A completed, verified feature slice | Record the milestone | `knowledge/history/` |
| **Any OKF update** | `knowledge/**` | Append change entry | `knowledge/log.md` |

Vendored code or submodules that carry their own OKF bundle SHOULD have behavior changes recorded in that bundle; this bundle tracks only the integration boundary.

---

## 5. OKF Document Standards & Evidence Hierarchy

### 5.1 Required YAML Frontmatter (OKF v0.2)

Follow the public [OKF SPEC](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) for reserved files and concept frontmatter:

| File | Frontmatter rule |
|------|------------------|
| Bundle-root `knowledge/index.md` | MAY contain **only** `okf_version: "0.2"` (SPEC §8 / §12) |
| Any other `index.md` | **No** frontmatter (directory listing body only) (SPEC §8) |
| Any `log.md` | **No** frontmatter; date headings `## YYYY-MM-DD`, newest first (SPEC §9) |
| All other `.md` concept documents | **Required** parseable YAML frontmatter with non-empty `type` (SPEC §4 / §11) |

Concept documents SHOULD also carry the recommended and project-extension fields:

```yaml
---
type: Architecture | Capability | Specification Mirror | Concept | Historical Record | Playbook | Development Guide | Product Boundary
title: Short Descriptive Title
description: One sentence summary of the knowledge document.
tags: [tag1, tag2, tag3]
status: stable | draft | deprecated
evidence: implementation-and-current-specifications | project-documentation | validated-runtime
generated: { by: "agent-name/model-id", at: 2026-07-27T00:00:00Z }
verified: { by: "process:test-suite", at: 2026-07-27T00:00:00Z }
sources:
  - id: source-identifier
    resource: ../../src/module/file.ext
    title: Human-readable source description
---
```

`type` values are producer-defined, not centrally registered (SPEC §4.1). `evidence` is a repository extension key; consumers MUST tolerate unknown keys (SPEC §4.1). `verified` may be a single `{ by, at }` map or a list of them (SPEC §5.2). Actor strings in `generated.by` / `verified.by` follow SPEC §7: `<producer>/<version>` for agents and tools, `human:<id>` for people (required for human-authored or human-confirmed content), `process:<id>` for automated processes.

### 5.2 Strict Evidence Hierarchy
Claims in OKF documents MUST adhere to this evidence hierarchy:

1. **Implemented source** (application and library code, scripts) — Strongest evidence for shipped behavior.
2. **Executable configuration** (build files, CI configuration, lockfiles, schemas, infrastructure definitions) — Strong evidence for toolchain and build behavior.
3. **Validated build/runtime output** (test runs, built artifacts, deployment or runtime logs) — Verification evidence.
4. **Current project documentation** — Useful context, but not proof of behavior without source or runtime validation.

> **Rule**: Agents MUST NOT upgrade a spec requirement or planned feature into a release claim without verifying source code implementation.

---

## 6. Mandatory Agent Execution Gates

Every agent executing a task in this repository MUST pass through the following 4 gates:

```
  ┌─────────────────────────────────────────────────────────────┐
  │ Gate 1: Pre-Task Discovery & Persona Selection              │
  │ • okf.py context, then show --section on target OKF docs    │
  │ • Detect file context & load relevant .ai/ persona/agent    │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Gate 2: In-Flight Impact Evaluation                         │
  │ • Track code, spec, and architectural modifications         │
  │ • Apply loaded persona guidelines to code changes           │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Gate 3: OKF Synchronization Gate                            │
  │ • Evaluate relevance trigger matrix                         │
  │ • Update/create knowledge/ documents                        │
  │ • Append update log entry to knowledge/log.md               │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ Gate 4: Final Verification & Sign-Off                       │
  │ • Run the repository's build and test commands              │
  │ • Verify OKF links, YAML frontmatter, and evidence integrity│
  └─────────────────────────────────────────────────────────────┘
```

### Gate 1: Pre-Task Discovery & Persona Selection
Before making edits, select the lifecycle tier (§2.5) and run the stages it requires. Then:
0. When a work queue exists (§9), use `okf.py handoff` first; it states the checkpoint, active task, and next step and replaces the broad `context` inventory. Reuse a harness-supplied handoff for the current branch/HEAD instead of rereading it. A worker given an `okf.py handoff --task` brief skips both: the brief replaces them.
1. When neither handoff nor worker brief is available, run `okf.py context` once. Then load only missing task-specific docs with `okf.py show PATH [PATH…] [--section …]`. Reuse existing acceptance, dependency and ownership material; do not reread the global catalog or rewrite a batch plan before source work. You MUST NOT `ls`, `find`, or `cat` your way around `knowledge/` or `.ai/`.
2. Identify the active file context and load the corresponding persona from `.ai/personas/` and task role from `.ai/agents/` (Planner, Implementer, or Reviewer) by outline and section, as in §2.3.

Startup is not a completion audit: `handoff` checks actionable queue/Git readiness and reports the full checkpoint NOT AUDITED. Resolve task eligibility, required acceptance and genuine overlapping/unowned writes before affected implementation. Whole-corpus documentation checks and unrelated record repairs do not block source dispatch; the driver runs a read-only diagnostic alongside the worker. Full checkpoint/OKF validation remains mandatory at actual handoff and sign-off.

### Gate 2: In-Flight Impact Evaluation
As you modify source, configuration, scripts, or specification files:
1. Identify which OKF capabilities, specs, architectural docs, or history items are affected by your changes.
2. Apply the loaded persona's engineering philosophy, type guidelines, and code quality standards to all changes.

### Gate 3: OKF Synchronization Gate (Pre-Completion Check)
Before presenting a task as completed or ready for review, ask:
1. *Did my changes alter product capabilities, specs, architecture, or project history?*
2. *Is the OKF corpus (`knowledge/`) up-to-date with this change?*

Run `okf.py affected` to list docs whose sources your change touches, plus changed files no doc covers.

If the corpus is not up to date, perform the following actions:
- Create or update the necessary `.md` files in `knowledge/` (`okf.py new` / `set` / `stamp`; `reindex` runs automatically after `new` and `set`).
- Ensure concept documents have complete YAML frontmatter (`type`, recommended trust/provenance fields, and repo `evidence` / `sources`). You MUST NOT add concept frontmatter to reserved `index.md` / `log.md` files.
- Append a dated entry to `knowledge/log.md` describing what knowledge was added, updated, or verified (`okf.py log "…"`).

### Gate 4: Final Verification & Sign-Off
Record the result with `lifecycle.py stage verify --note "<commands and outcomes>"` once the checks below pass (it reruns `okf.py records`). Verify that:
- Relevant builds succeed using the repository's own build commands.
- **Applicable end-to-end tests for the changed slice actually pass** (not merely that a script exists). See §8.
- All relative file links inside updated OKF documents resolve correctly (`okf.py validate` exits 0; it also checks frontmatter, log ordering, index freshness, and evidence claims).
- No unverified or speculative claims are presented as shipped functionality.
- OKF `verified` / log entries name the **exact commands and outcomes** used as evidence (e.g. `<test command>` → PASS), never “assumed green” or “to be verified later.”

---

## 7. Enforcement & Failure Remediation

If an agent or automated check detects that OKF is out of sync with current implementation:
1. The agent MUST NOT ignore the discrepancy.
2. The agent MUST treat stale or missing OKF documentation as a build/completion blocker.
3. The agent MUST update the affected OKF files, append a log entry in `knowledge/log.md`, and explain the documentation fix in the task summary.

---

## 8. Completeness & Testing Mandate (No Partial Slices)

Work that **looks** done — scripts, playbooks, “Verified …” log lines — while the real path fails, or that is backed by tests that pass without asserting the actual success criteria, is **forbidden**.

### 8.1 Absolute prohibitions

Agents MUST NOT land or claim complete any of the following:

| Forbidden | Examples |
|-----------|----------|
| Stubs / placeholders | `todo!()`, `unimplemented!()`, `pass # TODO`, `throw new NotImplementedException()`, empty function bodies that compile but do nothing |
| Deferred behavior presented as done | “future work”, “will wire later” left in the critical path of a claimed feature |
| Weak or misleading tests | Asserting “process started” or “file exists” while calling that an end-to-end test |
| Evidence inflation | Writing OKF/log “Verified …” without a command that failed closed on the real success criteria |
| Half-integrated paths | Interactive prompts on a path that must run non-interactively in CI; cleanup code that references uninitialized state |

If a slice cannot be finished in the current task, the agent MUST NOT merge the half: it MUST either complete it with tests, or leave it uncommitted / behind an explicit unfinished branch, and MUST NOT document it as working.

### 8.2 Definition of done for a feature slice

A slice is done only when **all** of the following hold:

1. **Behavior works** on the intended path (CLI, service, UI, library, or package — whichever the feature claims).
2. **Unit tests** cover pure logic where it exists. Absence of unit-testable logic is fine; absence of *any* verification is not.
3. **End-to-end test** exercises the user-visible success criteria and **fails if those criteria are unmet**.
4. **OKF + `knowledge/log.md`** describe what was verified with concrete commands and outcomes.
5. No `TODO`/`FIXME`/stub remains on the critical path of that slice.

### 8.3 What counts as a real E2E

| Claim | Minimum acceptable E2E |
|-------|------------------------|
| CLI command works | Invoke the built command with realistic arguments; assert exit status, output, and resulting side effects |
| HTTP/RPC endpoint works | Call the running service; assert status, response body, and persisted state |
| UI flow works | Drive the UI through the flow (browser or device automation); assert the visible end state |
| Library/package works | Install the built artifact into a clean environment and exercise its public API |
| Data migration works | Run the migration against representative data; assert schema and data afterward, and rollback if supported |
| Deployment/installer works | Deploy or install into a clean target; assert the installed system reaches its expected running state |

Smoke checks that only prove startup MAY be used as additional diagnostics but MUST NOT be the sole proof for a behavioral claim.

### 8.4 Gate 4 test matrix (agents MUST run applicable rows)

Before sign-off, agents MUST run every row that intersects the change, using the repository's actual commands (build files, package scripts, CI configuration):

**Execution rules (normative, loaded on demand).** The rules for when to run focused versus full checks, batch sizing, test proportionality, evidence reuse, and waiting on long checks live verbatim in [`.ai/validation-policy.md`](.ai/validation-policy.md). Agents MUST load it by section (`python3 .ai/scripts/okf.py show .ai/validation-policy.md --outline`, then `--section`) before the first Gate 4 run of a task and before launching or repeating any check that takes minutes. The binding core: run focused checks in the loop and the slice's narrowest E2E once when its edits are complete; run the full gate once per frozen candidate; never rerun an unchanged check; defer batch-level suites to one validator on the integrated head.

| Touched area | Required verification |
|--------------|----------------------|
| Pure logic | Unit tests for the affected modules |
| Public interfaces, schemas, integrations | Integration or contract tests |
| User-visible flows | The applicable E2E from §8.3 |
| Build, packaging, dependencies | Clean build, and artifact installation where applicable |
| `knowledge/**` | `python3 .ai/scripts/okf.py records` exits 0 (includes `validate`) |
| `.ai/scripts/**` | `python3 -m unittest discover -s .ai/scripts/tests` |
| Lifecycle, role, skill, or hook changes | The same suite (it checks documents, registrations, skills, hooks, and runs `lifecycle_eval.py` against scripted agents); `lifecycle_eval.py run -- AGENT_COMMAND` on a real agent when the change alters tier or stage rules |

If the environment cannot run a required verification (missing hardware, privileges, services, or artifacts), the agent MUST say so explicitly, MUST NOT invent a PASS, and MUST NOT upgrade OKF evidence beyond what ran.

### 8.5 OKF evidence language

- `evidence: validated-runtime` SHOULD be used only when an E2E in §8.3 actually passed in this change.
- `verified.by: process:repository-scan` means files exist — **not** that the feature works. Agents MUST NOT use scan-only verification to close behavioral claims.
- Log entries MUST quote failing-closed tests (e.g. `<test command>` → PASS) or state blockers honestly.

### 8.6 Test-first and root cause

These rules decide when a test is written and when a cause is established. They add no tests beyond §8.4 proportionality.

- A bug fix MUST start from a failing test or reproduction command that fails for the reported reason. Record it with `lifecycle.py redgreen red -- CMD` (it rejects a command that passes), fix, then `lifecycle.py redgreen green -- CMD` (it rejects an unchanged working tree); `lifecycle.py stage verify` and the commit hook refuse a `--kind bugfix` or `--kind logic` task without that pair. The report records red, then green. If no automated reproduction is possible, the agent MUST say so, name the substitute evidence, and MUST NOT claim the bug verified fixed.
- New or changed pure logic SHOULD be written test-first. When a test is written after the code, it MUST be shown to fail against the pre-change code or one deliberately broken variant, so a vacuous pass is ruled out.
- An agent MUST identify the cause of a failure before changing code to fix it. After three disproved hypotheses or fix attempts it MUST stop, question the design or the assumed surface, and report the evidence and the decision needed. It MUST NOT stack patches.
- Exempt: L0 changes, documentation, configuration with no test harness, and refactors already guarded by passing tests. State the exemption in the report.

---

## 9. Autonomous Execution Protocol

**Driver supervision and run controls** live in [`.ai/autonomous-execution.md`](.ai/autonomous-execution.md) §9.12. Load that section before launching or monitoring `autonomy_driver.py`, and as the orchestrator. Its binding core:

- The chat that launches a driver keeps its turn open and relays the child's public progress at phase changes and at least once per minute, using the read → visible commentary → `ack` sequence of `.ai/scripts/autonomy_progress.py`. The parent MUST NOT renew acknowledgements in a loop or before posting; a driver child (`OKF_AUTONOMOUS=1`) MUST NOT acknowledge itself or start a nested driver. `--headless` requires an explicit user choice. If the relay stops, the parent MUST say monitoring ended.
- Unattended implementation runs only through `autonomy_driver.py`, never as an unbounded interactive conversation. Circuit-breaker stops override keep-going instructions; agents MUST NOT auto-restart to bypass them.
- Full validation is submitted with `autonomy_validation.py submit` and runs outside the model session; no model stays open merely to wait. Full-gate processes MUST NOT be launched under the model process group. SAFE and validation PASS do not alone authorize DONE.
- Dispatch before paperwork: record task, owner, worktree and next check, start the work, and persist records at the next real boundary.

**Interactive sessions reset context per slice.** When a slice is delivered (its PR opened or the user names the next slice), start the next slice in a fresh conversation from `okf.py handoff --prompt`, not by continuing the same thread; compaction is not a reset. Hand long gates to a subagent or a background `wait_check.py` job so no large-context model polls them (§8.4).
When `knowledge/project/work-queue.md` exists, long-running work follows the Autonomous Execution Protocol in [`.ai/autonomous-execution.md`](.ai/autonomous-execution.md). Its sections keep the §9.x numbers cited across `.ai/`. Load it by section (`okf.py show .ai/autonomous-execution.md --outline`, then `--section`) only when you run the loop yourself: in solo mode, or as the orchestrator. Workers and reviewers that receive an `okf.py handoff --task` brief skip it.

The repository is the memory. Each session works one bounded batch of related requirements (or one orchestrator batch round), ends with a safe checkpoint (`okf.py checkpoint`), and the next session starts with a fresh context. `.ai/scripts/autonomy_driver.py` runs those sessions with the required progress/acknowledgement paths (see the playbook); terminal-only `--headless` requires an explicit user choice. Agents MAY push branches and MUST NOT merge into the default branch.

**Deliver usable flows in batches.** Select flows from the repository's objective, current roadmap/delivery plan, acceptance and queue. Project-specific priorities belong in project knowledge and task briefs. An empty queue requires a minimal first-flow claim followed by implementation in the same session (§9.11), not a mandatory planner, full-corpus inventory or bootstrap-only checkpoint/commit. Expand the remaining scope alongside disjoint worker work and finish records at actual handoff. The generated handoff already supplies objective and ready tasks; do not fetch it again or reload whole policies without missing/changed context. Preserve canonical requirement IDs, acceptance criteria and prerequisite gates. Plan dependency waves, assign disjoint files and shared integration surfaces, and run independent lanes in parallel where dependencies and resources allow. A downstream batch member can use a reviewed, integrated prerequisite after focused acceptance checks; that work remains provisional until the full integrated batch gate passes. External dependencies must already be DONE. Run the full expensive required suite once per integrated batch (§8.4), then attach that evidence to its individual requirements.

**Milestones are the PR basis: exactly one PR per milestone.** All work for a milestone, including its tasks, fixes, tests, OKF updates and execution-state records, is committed or merged into the same milestone branch and PR targeting the default branch. Agents MUST reuse that PR across tasks and sessions and MUST NOT open a PR per task, subtask, worker, slice, or run-state update. Title it `M<N>: <Title>`, for example `M1: Headless foundation and core contracts`, with a title describing the overall milestone scope. Task branches and worktrees are internal implementation units, not PR units. The milestone PR MUST remain a draft until the entire milestone and its exit criteria pass review and validation on the integrated head (§9.9). The queue and status have one writer on the run branch, and that state is included in the milestone branch before readiness. Combine branches only by merging; `okf.py git-setup` and `pr_sync.py` keep shared bundle files and milestone PRs mergeable.

The milestone PR body MUST list every feature/task in the milestone as a Markdown checklist item (`- [ ] <feature/task>`), including pending and blocked work. An item MUST be marked complete (`- [x]`) only after its work is integrated into the milestone branch and passes review and required validation. Update the body as items are completed; reopen the checkbox if further work is needed (§9.9).

---

# Behavioral Guidelines

> Adapted from the [`CLAUDE.md`](https://github.com/forrestchang/andrej-karpathy-skills/blob/main/CLAUDE.md) in [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) (MIT License), which is derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing (at L2 and above, the analyst role and Stage 0 of §2.5 make this operational):
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
