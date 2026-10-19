# Agent Governance Template

A starting point for repositories where AI coding agents do real engineering work, and where that work has to be sized, reviewed, verified, and remembered. It turns an AI development lifecycle into something the repository enforces: shared rules, task roles, language personas, a machine-readable knowledge bundle, and hooks that stop an agent from skipping a stage.

The template contains governance and developer tooling; add your application's source, build configuration, and acceptance tests to make it your own. Its small knowledge bundle records the governance tooling's own contracts, not application capabilities.

## What it gives you

- **An enforced lifecycle.** Every task moves through Intent, Plan, Implement, Review, Verify & Sync, and Ship. The agent declares a tier (**L0** trivial, **L1** small, **L2** feature, **L3** queued or autonomous) and runs only the ceremony that tier needs. Stages are validated and recorded, and hooks in Claude Code, Codex, and Cursor deny source edits and commits that skip a required one.
- **Evidence over claims.** A bug fix starts from a failing test and records red, then green. "Done" requires a passing end-to-end check for the changed slice, not a script that merely exists. Stubs, vacuous tests, and unverified "Verified" log lines are prohibited.
- **Living project knowledge.** The `knowledge/` bundle (Open Knowledge Format v0.2) is the persistent context for the next agent or contributor. Changes to behavior, contracts, or architecture must update it and append to its log; `okf.py` validates structure, links, and index freshness.
- **Specialized roles and personas.** Analyst, planner, implementer, reviewer, and orchestrator roles, registered as subagents for Claude Code, Cursor, and Codex, plus advisory personas for Python, JavaScript/TypeScript, Rust, Go, C#, Dart/Flutter, and Swift/SwiftUI.
- **Optional autonomous execution.** A work queue, recovery checkpoints, and a supervised driver run multi-session work against frozen acceptance criteria, with one pull request per milestone.
- **Token-frugal tooling.** Agents read Markdown by section with `okf.py show` and inspect source through bounded `repo.py` commands, while a shell guard rejects wasteful or unsafe access patterns.

## Quick start

Requirements: **Python 3.9+** and **Git**. The bundled Python tooling uses the standard library.

1. Copy this repository into a new project, or clone it to explore the template:

   ```sh
   git clone https://github.com/enramosjr/agent-governance-template.git
   cd agent-governance-template
   ```

2. Read [AGENTS.md](AGENTS.md), the shared authority for agent behavior, evidence, validation, and knowledge updates.
3. In the project adopting this template, initialize its knowledge bundle:

   ```sh
   python3 .ai/scripts/okf.py init
   ```

   Populate it with that project's architecture, capabilities, setup, and contracts; retain the tooling validation guide while it applies.

4. Ask your coding agent to make a bounded change. It states its persona and tier, then follows the lifecycle for that tier.

Run tooling from the repository root. Discover commands with `python3 .ai/scripts/okf.py --help`, `python3 .ai/scripts/lifecycle.py --help`, and `python3 .ai/scripts/repo.py --help`.

## The lifecycle

```
Intent -> Plan -> Implement -> Review -> Verify & Sync -> Ship
```

| Tier | Applies when | Ceremony |
| --- | --- | --- |
| **L0** trivial | Typo, comment, or constant with no behavior effect | Implement, focused check, `okf.py affected` |
| **L1** small | Bounded change, no contract, schema, security, or dependency effect | Short intent note, light plan, test-first for logic and bugs, self-review |
| **L2** feature | New behavior, contract effect, several modules, or ambiguity | Approved spec, full plan, isolated branch, independent review, slice E2E |
| **L3** milestone | Queued or autonomous work | The queue is the artifact set; the reviewer gates DONE |

The agent picks the lowest tier whose conditions hold and escalates as soon as it finds a contract, schema, persistence, security, or dependency effect. Tiers scale the spec, plan, review, and gate breadth; they never relax the evidence rules.

Enforcement is mechanical:

```sh
python3 .ai/scripts/lifecycle.py tier L2 --reason "new export endpoint"
python3 .ai/scripts/lifecycle.py stage intent --ref specs/export.md --approved-by human:<id>
python3 .ai/scripts/lifecycle.py redgreen red -- <your test command>
python3 .ai/scripts/lifecycle.py status
```

`stage` validates the artifact (a lint-clean spec, a plan citing every requirement ID, an Approved review, a passing `okf.py records`). Approvals are recorded claims, and `--approved-by human:<id>` must come from a user message. `LIFECYCLE_GUARD=off` disables the hooks. Full stage detail is in [.ai/lifecycle.md](.ai/lifecycle.md) and [AGENTS.md §2.5](AGENTS.md).

## What's included

| Path | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Governance, lifecycle tiers, evidence hierarchy, validation gates, and OKF synchronization rules |
| [CLAUDE.md](CLAUDE.md) | Imports the shared instructions for Claude Code |
| [.ai/lifecycle.md](.ai/lifecycle.md) | The end-to-end lifecycle, stage exit checks, and the debugging flow |
| [.ai/validation-policy.md](.ai/validation-policy.md) | Gate 4 execution rules, loaded on demand to keep `AGENTS.md` small |
| [.ai/agents/](.ai/agents/) | Analyst, planner, implementer, reviewer, and orchestrator role definitions |
| [.ai/personas/](.ai/personas/) | Advisory engineering guidance per language |
| [.ai/scripts/](.ai/scripts/) | Knowledge management (`okf.py`), lifecycle enforcement (`lifecycle.py`), bounded inspection (`repo.py`), shell guard, validation, and autonomous workflow tools |
| [.ai/evals/lifecycle/](.ai/evals/lifecycle/) | Scenario evals (L0 to L3) run with `lifecycle_eval.py run -- AGENT_COMMAND` |
| [.claude/](.claude/) | Claude Code hooks, subagents, and stage skills (`spec`, `plan`, `implement`, `review`, `debug`, `ship`) |
| [.codex/](.codex/) | Codex hooks and subagents |
| [.cursor/hooks.json](.cursor/hooks.json) | Cursor shell-guard and lifecycle hooks |
| [.agents/skills/](.agents/skills/) | Symlink to `.claude/skills/`, so Codex reads the same stage skills (checkouts without symlink support need a copy) |
| [.ai/autonomous-execution.md](.ai/autonomous-execution.md) | Optional work queue, recovery checkpoints, and supervised driver workflow |

## Working with coding agents

[AGENTS.md](AGENTS.md) is the shared entry point. Claude Code imports it through `CLAUDE.md`; Claude Code, Cursor, and Codex have shell-guard and lifecycle hooks configured in their respective directories (Codex asks you to trust `.codex/` and review the hooks with `/hooks` first). In other agent environments, make sure the agent loads `AGENTS.md` and follows the repository's tool instructions.

Roles describe the work being performed: analysis clarifies, planning investigates, implementation makes changes, review evaluates evidence, and orchestration manages queued work. Personas are advisory; the requested outcome and repository contracts take precedence.

The four execution gates run inside the lifecycle: **Discover** (load context and the relevant role and persona sections), **Implement** (focused changes, tracking impact), **Synchronize** (update affected knowledge and log it), and **Verify** (run applicable checks and report concrete evidence). See [AGENTS.md §3.1](AGENTS.md#31-okf-tooling-aiscriptsokfpy--script-first) for exact tool mappings.

## Maintaining project knowledge

In an adopting project, the `knowledge/` bundle holds architecture and development context, capabilities, specifications, concepts, playbooks, and history. Useful commands:

```sh
# Discover project context and document structure.
python3 .ai/scripts/okf.py context
python3 .ai/scripts/okf.py list
python3 .ai/scripts/okf.py show index.md --outline --depth 2

# Map working-tree changes to documents that cite their sources.
python3 .ai/scripts/okf.py affected

# After updating affected documents, record and validate the change.
python3 .ai/scripts/okf.py log "Describe the knowledge update and exact verification results."
python3 .ai/scripts/okf.py records
```

Use `new`, `set`, and `stamp` for document metadata; use your editor for body prose. Set `OKF_ACTOR` to attribute generated records. Record verification only after the named command passes. `records` checks bundle structure, links, index freshness, and Git diff whitespace; application-specific tests are a separate requirement.

## Optional autonomous workflow

For queued execution across agent sessions, start with:

```sh
python3 .ai/scripts/okf.py init --autonomous
python3 .ai/scripts/okf.py handoff
```

This adds a work queue and recovery checkpoint. Define the project's objective, acceptance criteria, and tasks first; `lifecycle.py queue-from-spec` can turn a spec's requirements into queue entries. Read the [autonomous execution protocol](.ai/autonomous-execution.md), especially §9.12, before using `autonomy_driver.py`; it defines supervision, progress reporting, validation, and stop conditions. Setup alone does not start an autonomous agent.

## Validation

In an adopting project, check its knowledge records with `python3 .ai/scripts/okf.py records`.

When changing `.ai/scripts/`, run the regression suite, which also checks lifecycle documents, registrations, skills, hooks, and scripted-agent evals. Its workflow tests need temporary fixtures outside system temporary storage, because the scratch policy rejects `/tmp`. On a disk-backed checkout:

```sh
mkdir -p .git/okf-test-tmp
TMPDIR="$PWD/.git/okf-test-tmp" python3 -m unittest discover -s .ai/scripts/tests
```

Add your application's own build, lint, unit, and end-to-end commands as it develops, and document them in project knowledge. The governance tooling tests do not establish application correctness.

## Attribution

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for attribution and license terms covering adapted third-party material.
