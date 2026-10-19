# AGENTS.md Reference (loaded on demand)

This material moved here verbatim from `AGENTS.md` so that sessions pay for it only when they need it. It is as binding as `AGENTS.md`; the words MUST, SHOULD and MAY carry the `AGENTS.md` BCP 14 meaning. Load by section: `python3 .ai/scripts/okf.py show .ai/agents-reference.md --outline`.

## Subagents

In Claude Code and Cursor the analyst, planner, and reviewer run read-only by tool restriction. Codex custom agents cannot set a sandbox, so their read-only rule is an instruction only, and Codex spawns subagents only when asked: name the role in the prompt (for example "have reviewer check this diff").

## Bundle layout

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

## Script commands

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
| Run the script test suite in parallel, printing only failures and a summary (`.ai/scripts/run_tests.py`) | `run_tests.py [-j N] [-s DIR]` |
| Create the work queue and status checkpoint | `init --autonomous` |
| Task states (READY computed from dependencies) and what to start next | `queue [--next] [--state S] [--limit N] [--json]` |
| Move DONE and CANCELLED tasks to the archive | `queue --archive` |
| Is the repository resumable right now? | `checkpoint [--json]` (exit 1 when unsafe) |
| Resume material from repository state | `handoff` (digest), `handoff --prompt [--role orchestrator]` (fresh-session prompt), `handoff --task ID` (worker brief) |
| Run the queue as fresh agent sessions (`.ai/scripts/autonomy_driver.py`) | `autonomy_driver.py [--role orchestrator] -- AGENT_COMMAND` |
| Merge parallel branches' log, index, queue and status without conflicts (once per clone) | `git-setup` |
| Keep agent PRs mergeable after base-branch merges (`.ai/scripts/pr_sync.py`) | `pr_sync.py [--dry-run]` |
| Declare the tier, record and gate lifecycle stages, record red/green evidence (`.ai/scripts/lifecycle.py`) | `lifecycle.py tier L0\|L1\|L2\|L3 --reason T [--kind K]`, `stage NAME [--ref P] [--note T] [--approved-by A]`, `gate TARGET`, `status`, `redgreen red\|green -- CMD`, `analyze SPEC`, `converge SPEC` |
| Check spec → plan → tests coverage, and turn a spec into work-queue entries | `lifecycle.py trace SPEC [--plan P] [--tests PATH…]`, `lifecycle.py queue-from-spec SPEC [--group G]` |
| Run the lifecycle scenario evals against a real agent (`.ai/scripts/lifecycle_eval.py`) | `lifecycle_eval.py list\|check\|run [--scenario ID] -- AGENT_COMMAND` |

Path conventions follow the OKF SPEC (§6.1, §6.2): links and path fields are either URLs, bundle-relative paths beginning with `/`, or paths relative to the containing document. `new --source` and `affected` take **repo-relative** paths and convert them for you. Set `OKF_ACTOR` (e.g. `agent/<model-id>`) so `generated.by` is attributed. `stamp verified` records only the actor you pass, so stamp only after the cited command actually ran and passed (§8.5). Tests: `python3 -m unittest discover -s .ai/scripts/tests`, or the same tests in parallel with `python3 .ai/scripts/run_tests.py`.

## Harness tools

| Need | Claude Code | Cursor | Codex | Never |
|------|-------------|--------|-------|-------|
| Read a file or line range | `Read` (`offset`, `limit`) | `Read` | `python3 .ai/scripts/repo.py read PATH [--lines A-B]` | `cat`, `head`, `tail`, `sed -n`, `awk`, whole-file `repo.py grep '^'` |
| Search contents | `python3 .ai/scripts/repo.py grep PATTERN [--regex] [-i] [--glob G] [--under DIR] [--count]` | `Grep` | `repo.py grep …` | `grep`, `rg`, `git grep` |
| Find files | `python3 .ai/scripts/repo.py files 'GLOB'… [--under DIR] [--depth N]` | `Glob` | `repo.py files …` | `ls`, `find`, `tree`, `git ls-files` |
| Create or edit a file | `Write`, `Edit` | `Write`, `StrReplace` | `apply_patch` | heredocs, `sed -i`, `tee`, `echo >`, Python scripts that write files |

`repo.py` respects `.gitignore`, skips binaries, and caps output (`--limit`; `read` prints at most 250 numbered lines and names the next range). Read source by range: find the lines with `repo.py grep`, then read only those. Shell is for running things: builds, tests, git, `okf.py`, and `repo.py`. Piping a command's output through `head`, `tail`, or `rg` is fine.

`.ai/scripts/shell_guard.py` runs before every shell command (`.claude/settings.json` for Claude Code, `.cursor/hooks.json` for Cursor, `.codex/hooks.json` for Codex, which loads project hooks only from a trusted `.codex/` layer and after review with `/hooks`). Cursor also loads `.claude/settings.json` hooks by default; those entries pass `--skip-in-cursor` so each check runs once. It rejects the "Never" column above, and any shell read of `knowledge/` or `.ai/**.md`, with a message naming the replacement. Paths outside the project and under `/tmp` are allowed. If the named tool does not exist in your session, use the `repo.py` / `okf.py` command from the message.

## Trigger matrix

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

## Frontmatter

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

## Startup

Startup is not a completion audit: `handoff` checks actionable queue/Git readiness and reports the full checkpoint NOT AUDITED. Resolve task eligibility, required acceptance and genuine overlapping/unowned writes before affected implementation. Whole-corpus documentation checks and unrelated record repairs do not block source dispatch; the driver runs a read-only diagnostic alongside the worker. Full checkpoint/OKF validation remains mandatory at actual handoff and sign-off.

## E2E minimums

| Claim | Minimum acceptable E2E |
|-------|------------------------|
| CLI command works | Invoke the built command with realistic arguments; assert exit status, output, and resulting side effects |
| HTTP/RPC endpoint works | Call the running service; assert status, response body, and persisted state |
| UI flow works | Drive the UI through the flow (browser or device automation); assert the visible end state |
| Library/package works | Install the built artifact into a clean environment and exercise its public API |
| Data migration works | Run the migration against representative data; assert schema and data afterward, and rollback if supported |
| Deployment/installer works | Deploy or install into a clean target; assert the installed system reaches its expected running state |

## Autonomous execution

**Driver supervision and run controls** live in [`.ai/autonomous-execution.md`](autonomous-execution.md) §9.12. Load that section before launching or monitoring `autonomy_driver.py`, and as the orchestrator. Its binding core:

- The chat that launches a driver keeps its turn open and relays the child's public progress at phase changes and at least once per minute, using the read → visible commentary → `ack` sequence of `.ai/scripts/autonomy_progress.py`. The parent MUST NOT renew acknowledgements in a loop or before posting; a driver child (`OKF_AUTONOMOUS=1`) MUST NOT acknowledge itself or start a nested driver. `--headless` requires an explicit user choice. If the relay stops, the parent MUST say monitoring ended.
- Unattended implementation runs only through `autonomy_driver.py`, never as an unbounded interactive conversation. Circuit-breaker stops override keep-going instructions; agents MUST NOT auto-restart to bypass them.
- Full validation is submitted with `autonomy_validation.py submit` and runs outside the model session; no model stays open merely to wait. Full-gate processes MUST NOT be launched under the model process group. SAFE and validation PASS do not alone authorize DONE.
- Dispatch before paperwork: record task, owner, worktree and next check, start the work, and persist records at the next real boundary.

The repository is the memory. Each session works one bounded batch of related requirements (or one orchestrator batch round), ends with a safe checkpoint (`okf.py checkpoint`), and the next session starts with a fresh context. `.ai/scripts/autonomy_driver.py` runs those sessions with the required progress/acknowledgement paths (see the playbook); terminal-only `--headless` requires an explicit user choice.

**Deliver usable flows in batches.** Select flows from the repository's objective, current roadmap/delivery plan, acceptance and queue. Project-specific priorities belong in project knowledge and task briefs. An empty queue requires a minimal first-flow claim followed by implementation in the same session (§9.11), not a mandatory planner, full-corpus inventory or bootstrap-only checkpoint/commit. Expand the remaining scope alongside disjoint worker work and finish records at actual handoff. The generated handoff already supplies objective and ready tasks; do not fetch it again or reload whole policies without missing/changed context. Preserve canonical requirement IDs, acceptance criteria and prerequisite gates. Plan dependency waves, assign disjoint files and shared integration surfaces, and run independent lanes in parallel where dependencies and resources allow. A downstream batch member can use a reviewed, integrated prerequisite after focused acceptance checks; that work remains provisional until the full integrated batch gate passes. External dependencies must already be DONE. Run the full expensive required suite once per integrated batch (§8.4), then attach that evidence to its individual requirements.

**Milestones are the PR basis: exactly one PR per milestone.** All work for a milestone, including its tasks, fixes, tests, OKF updates and execution-state records, is committed or merged into the same milestone branch and PR targeting the default branch. Agents MUST reuse that PR across tasks and sessions and MUST NOT open a PR per task, subtask, worker, slice, or run-state update. Title it `M<N>: <Title>`, for example `M1: Headless foundation and core contracts`, with a title describing the overall milestone scope. Task branches and worktrees are internal implementation units, not PR units. The milestone PR MUST remain a draft until the entire milestone and its exit criteria pass review and validation on the integrated head (§9.9). The queue and status have one writer on the run branch, and that state is included in the milestone branch before readiness. Combine branches only by merging; `okf.py git-setup` and `pr_sync.py` keep shared bundle files and milestone PRs mergeable.

The milestone PR body MUST list every feature/task in the milestone as a Markdown checklist item (`- [ ] <feature/task>`), including pending and blocked work. An item MUST be marked complete (`- [x]`) only after its work is integrated into the milestone branch and passes review and required validation. Update the body as items are completed; reopen the checkbox if further work is needed (§9.9).
