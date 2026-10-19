# Agent Governance & OKF Synchronization Protocol

This document establishes the mandatory governance standards, workflow gates, evidence rules, and persona/agent selection protocols for all AI agents (coding assistants, autonomous subagents, and human-agent pair programmers) operating within this repository.

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in BCP 14 ([RFC 2119](https://www.rfc-editor.org/rfc/rfc2119), [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174)) when, and only when, they appear in all capitals, as shown here. The same words in lowercase carry their ordinary English meaning and are not normative. The "Behavioral Guidelines" at the end of this document are written as plain-language guidance and are outside this convention.

**Start here:** pick the lifecycle tier (§2.5), then follow `.ai/lifecycle.md` for the stages that tier requires: Intent, Plan, Implement, Review, Verify & Sync, Ship.

**Reference material** lives verbatim in [`.ai/agents-reference.md`](.ai/agents-reference.md) and is as binding as this file. When a rule below names a section, load it: `python3 .ai/scripts/okf.py show .ai/agents-reference.md --section HEADING`.

---

## 1. Core Mandate: Open Knowledge Format (OKF) Synchronization

All AI agents working on this project MUST ensure that the Open Knowledge Format corpus (`knowledge/`) remains synchronized with any code, specification, architecture, or workflow changes introduced during execution.

### Rationale & Purpose
The OKF corpus (`knowledge/`) is the machine-readable, persistent knowledge graph of the repository. It serves as the primary context for future AI agents and human contributors. When codebase changes occur without corresponding OKF updates, agent drift and knowledge decay occur.

- **Requirement**: Any agent change that alters functionality, contracts, specifications, dependencies, or architectural patterns MUST update the corresponding OKF document(s) and append a log entry to `knowledge/log.md`.
- **Scope**: Code changes are not considered complete until OKF synchronization is verified and updated where relevant.
- **Bootstrap**: If `knowledge/index.md` does not exist yet, create the bundle with `python3 .ai/scripts/okf.py init` before the first OKF update.

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

The analyst, planner, implementer, and reviewer are also registered as subagents in `.claude/agents/` (read by Claude Code and Cursor) and `.codex/agents/` (read by Codex). Delegated analysis, planning, and review SHOULD use them. Per-harness behavior (read-only enforcement, Codex spawning): section `Subagents`.

### 2.3 Operational Loading Rules

1. **Context Identification**: Upon receiving a task or operating on files, identify the applicable task role and language persona.
2. **Selective Segment Loading**: Agents MUST NOT read a whole persona or role file. Run `python3 .ai/scripts/okf.py show .ai/personas/<persona>.md --outline --depth 2`, then load only the pertinent sections with `--section HEADING` (repeatable). Load role files in `.ai/agents/` the same way.
3. **Multi-Stack Tasks**: For tasks spanning several languages, use one primary persona for the area that dominates implementation risk and apply others only within their files.

### 2.4 Persona Contract (single source of truth)

This section is the only place persona selection and authority are defined. The agent role files do not restate it.

- **Selection**: A persona is selected by explicit instruction (`Persona: .ai/personas/go-principal-engineer.md`, `Use persona: go-principal-engineer`, or a plain request) or automatically from the §2.1 table, which this document authorizes. A bare name resolves to `.ai/personas/<name>.md`. When selecting automatically, agents MUST state the persona and why before starting.
- **Role**: A persona is advisory. It supplies language pitfalls, validation commands, and a review checklist. It MUST NOT change the requested outcome, override acceptance criteria or the approved plan, expand scope, force a pattern, or turn preferences into requirements or defects.
- **Application**: Load the outline, then only the sections relevant to the task (§2.3). Agents SHOULD NOT apply every item to every task.
- **Precedence** (highest first): explicit user instructions, acceptance criteria, the approved plan, repository and directory instructions (including human-approved project rules in `knowledge/project/rules.md`), executable code/config/schemas/tests, project knowledge, the persona, existing repository conventions, general engineering judgment, personal preference. A review finding MUST rest on a source above the persona. Lessons alone are observations; promotion and retirement MUST have human approval.
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
- **Enforcement.** Agents MUST declare the tier with `lifecycle.py tier` and record each required stage with `lifecycle.py stage` as it completes; `stage` validates the artifact (a lint-clean spec, a plan that cites every requirement ID, an Approved review verdict, a passing `okf.py records`, and, at L2+, a current passing `lifecycle.py converge` run). The same script runs as a hook in Claude Code, Codex and Cursor: it denies source edits until a tier is declared and the stages that tier requires are recorded, denies `git commit` (other than `wip:`) and PR creation until Verify is recorded, requires the committed audit record (`knowledge/history/lifecycle/`) in such commits, and injects the router at session start. Markdown and `knowledge/` edits are exempt. `LIFECYCLE_GUARD=off` disables it, and autonomous driver sessions (`OKF_AUTONOMOUS=1`) are gated by the work queue instead. Approvals are recorded claims: `--approved-by human:<id>` MUST come from a user message, and `decision:<ADR>` only under §9.7. The hook raises the cost of skipping a stage; it cannot prove that a human approved.

---

## 3. OKF Structure Overview

The OKF bundle resides in `knowledge/` (OKF v0.2 layout; `okf.py init` creates it): `index.md`, `log.md`, and the sections `project/`, `capabilities/`, `specifications/`, `history/`, `concepts/`, `playbooks/`, plus the §9 work queue and status under `project/`. What each holds and when it changes: `.ai/agents-reference.md` section `Bundle layout`.

### 3.1 OKF Tooling (`.ai/scripts/okf.py`) — Script First

Any OKF operation the script covers MUST go through it instead of reading, grepping, or hand-editing `knowledge/`. It is deterministic, stdlib-only (Python 3.9+), and prints compact output. Read a full document only when you need its prose. The command for each need: section `Script commands`, or `okf.py --help`.

**When a command fails**, its error is one line and names the fix (a missing doc lists close matches; `affected` outside git asks for explicit paths). Correct the invocation and rerun; you MUST NOT fall back to reading or grepping `knowledge/` by hand.

**Allowed field values and `validate` rules** are printed by `okf.py --help`; per-command options by `okf.py COMMAND --help`. Agents MUST NOT grep or read `okf.py` source to learn them.

**Files the script does not cover** (source code, configuration, tests, and OKF body prose): use the harness's own tools and MUST NOT use the shell. They take structured arguments and return bounded, line-numbered output, so there is no command to compose. Read with `Read`, search with `Grep`, find with `Glob`, edit with `Write`/`Edit`/`StrReplace`/`apply_patch`; never `cat`, `head`, `tail`, `sed`, `awk`, `grep`, `rg`, `ls`, `find`, heredocs, or `echo >` (full map: section `Harness tools`).

Claude Code has no `Glob` or `Grep` tool and Codex has no file-read tool, so `repo.py` fills those gaps (`python3 .ai/scripts/repo.py read|grep|files`). Agents MUST use it in any harness that lacks those tools.

**Enforcement.** `.ai/scripts/shell_guard.py` blocks those commands before they run and names the replacement. When a command is blocked, switch to the named tool or script; you MUST NOT rephrase the command to slip past the guard (`git ls-files`, `git grep`, or a Python one-liner doing the same job). A human MAY disable it by launching the agent with `OKF_SHELL_GUARD=off`.

---

## 4. OKF Relevance Trigger Matrix

`okf.py affected` is the first-pass detector: it maps changed files to the docs that cite them in `sources` and lists changed files no doc covers. Agents MUST also check their changes against this matrix, which covers changes that `sources` mappings cannot see: user-visible behavior → `capabilities/`; public contracts → `specifications/`; architecture, boundaries, build, toolchain, dependencies → `project/` (and `playbooks/` for setup); operational procedures → `playbooks/`; domain models → `concepts/`; delivered milestones → `history/`; any OKF update → a `log.md` entry. Full matrix: section `Trigger matrix`.

Vendored code or submodules that carry their own OKF bundle SHOULD have behavior changes recorded in that bundle; this bundle tracks only the integration boundary.

---

## 5. OKF Document Standards & Evidence Hierarchy

### 5.1 Required YAML Frontmatter (OKF v0.2)

Reserved `index.md` and `log.md` files carry no concept frontmatter (the bundle root `index.md` only `okf_version`); every other document needs YAML frontmatter with a non-empty `type`. `okf.py new` writes the recommended fields and `okf.py validate` checks them. Per-file rules, the field template, and actor string formats: section `Frontmatter`.

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

1. **Discovery & persona**: `okf.py context`, then `show --section` on target docs; load the matching persona and role.
2. **In-flight impact**: track code, spec, and architecture changes; apply the persona to them.
3. **OKF sync**: evaluate the trigger matrix, update `knowledge/`, append a `log.md` entry.
4. **Verification & sign-off**: run the build and tests; verify OKF links, frontmatter, and evidence.

### Gate 1: Pre-Task Discovery & Persona Selection
Before making edits, select the lifecycle tier (§2.5) and run the stages it requires. Then:
0. When a work queue exists (§9), use `okf.py handoff` first; it states the checkpoint, active task, and next step and replaces the broad `context` inventory. Reuse a harness-supplied handoff for the current branch/HEAD instead of rereading it. A worker given an `okf.py handoff --task` brief skips both: the brief replaces them.
1. When neither handoff nor worker brief is available, run `okf.py context` once. Then load only missing task-specific docs with `okf.py show PATH [PATH…] [--section …]`. Reuse existing acceptance, dependency and ownership material; do not reread the global catalog or rewrite a batch plan before source work. You MUST NOT `ls`, `find`, or `cat` your way around `knowledge/` or `.ai/`.
2. Identify the active file context and load the corresponding persona from `.ai/personas/` and task role from `.ai/agents/` (Planner, Implementer, or Reviewer) by outline and section, as in §2.3.

Startup is not a completion audit; what startup must resolve and what waits for sign-off: section `Startup`.

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

An E2E drives the claimed surface the way its user does (built CLI, running service, UI automation, installed artifact, migrated data, clean deployment) and asserts the end state, not just that it started. Minimum per claim type: section `E2E minimums`.

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
| `.ai/scripts/**` | `python3 -m unittest discover -s .ai/scripts/tests` (`python3 .ai/scripts/run_tests.py` runs the same tests in parallel) |
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

Before launching or monitoring `autonomy_driver.py`, as the orchestrator, or when planning or shipping a milestone, agents MUST load section `Autonomous execution` of `.ai/agents-reference.md` (driver supervision, batch delivery, and one PR per milestone) and `.ai/autonomous-execution.md` §9.12. Unattended implementation runs only through `autonomy_driver.py`.

**Interactive sessions reset context per slice.** When a slice is delivered (its PR opened or the user names the next slice), start the next slice in a fresh conversation from `okf.py handoff --prompt`, not by continuing the same thread; compaction is not a reset. Hand long gates to a subagent or a background `wait_check.py` job so no large-context model polls them (§8.4).
When `knowledge/project/work-queue.md` exists, long-running work follows [`.ai/autonomous-execution.md`](.ai/autonomous-execution.md) (its sections keep the §9.x numbers cited across `.ai/`). Load it by section only when you run the loop yourself (solo or orchestrator); a worker or reviewer with an `okf.py handoff --task` brief skips it.

Agents MAY push branches and MUST NOT merge into the default branch.

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
