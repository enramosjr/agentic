<div align="center">

# AGENTIC

**Agent Governance, Execution, Navigation, Tooling, Integration, and Coordination**

A vendor-neutral framework for governing, orchestrating, and standardizing autonomous AI software engineering workflows.

*Right-sized process for your coding agent, enforced by the repository instead of requested in a prompt.*

</div>

Claude Code, Codex, and Cursor all work from the same rules, roles, and hooks, so switching agents does not mean switching process.

## Why AGENTIC

Most agent workflows are a set of instructions the agent is asked to follow. A long session, a compaction, or an eager model is enough to skip the spec, skip the test, or write "Verified" in a log with nothing behind it. AGENTIC treats those as failures to be blocked, not reminders to be repeated.

- **Process is enforced.** Hooks deny source edits until the agent declares a tier, and deny commits and PRs until Verify is recorded. Each stage is validated against its artifact: a lint-clean spec, a plan that cites every requirement ID, an Approved review, a passing records check.
- **Process is right-sized.** A typo does not get a spec and a feature does not get a one-line note. Four tiers (L0 to L3) scale the ceremony, and the agent must escalate the moment it finds a contract, schema, security, or dependency effect.
- **Claims need evidence.** A bug fix starts from a failing test and records red, then green. "Done" requires an end-to-end check that fails if the success criteria are unmet. Stubs, vacuous tests, and inflated verification notes are prohibited.
- **The repository is the memory.** An Open Knowledge Format bundle in `knowledge/` is the context the next agent or contributor starts from, and changes cannot be called complete until it is synchronized and logged.
- **It scales to unattended work.** A work queue, recovery checkpoints, and a supervised driver run multi-session milestones against frozen acceptance criteria, one pull request per milestone.

## How it works

You ask your agent for something. Before it touches code, it states the persona it is applying and the tier it chose, with the reason, and declares the tier:

```sh
python3 .ai/scripts/lifecycle.py tier L2 --reason "new export endpoint" --kind feature
```

From there it moves through the lifecycle, recording each stage as it completes:

```
Intent -> Plan -> Implement -> Review -> Verify & Sync -> Ship
```

An analyst turns the request into a testable spec and asks the questions that change behavior. You approve it. A planner investigates read-only and maps every requirement to a step and a check. An implementer writes the failing test first, then the smallest change that passes. A separate reviewer checks spec compliance, then quality, and cannot approve with a Critical or High finding open. Finally the agent finds the knowledge documents the change affects, updates them, logs the exact commands that passed, and only then ships.

If it tries to skip a stage, the hook says no and names the missing one. Approvals are recorded claims, and `--approved-by human:<id>` must come from a user message you actually sent.

## Choose your process

| You want to... | Tier | What happens |
| --- | --- | --- |
| Fix a typo, comment, or constant | **L0** | Edit, run a focused check, run `okf.py affected`. |
| Make a bounded change or fix a bug | **L1** | Three-line intent note, light plan, failing test first, self-review, focused checks. |
| Add or change behavior or a contract | **L2** | Approved spec, full plan, isolated branch, independent review, slice E2E, then the full gate once. |
| Run queued or autonomous work | **L3** | The queue is the artifact set: frozen acceptance criteria, a batch plan, and a reviewer who gates DONE. |

The agent picks the lowest tier whose conditions hold, and it cannot lower a tier you set. Tiers scale the spec, plan, review, and gate breadth. They never relax the evidence rules.

## Install

AGENTIC is files in your repository, plus stdlib-only Python scripts that read them. You need **Python 3.9+** and **Git**.

1. Copy `AGENTS.md`, `CLAUDE.md`, and `.ai/` into your project, plus the directory for each agent you use:

   | Agent | Copy | Notes |
   | --- | --- | --- |
   | Claude Code | `.claude/` | Hooks, subagents, and the stage skills. `CLAUDE.md` imports `AGENTS.md`. |
   | Codex | `.codex/`, `.agents/skills/` | Trust the `.codex/` layer and review hooks with `/hooks`. `.agents/skills/` is a symlink to `.claude/skills/`. |
   | Cursor | `.cursor/hooks.json`, `.claude/agents/` | Cursor reads the subagents from `.claude/agents/`. |
   | Anything else | `AGENTS.md` | Have the agent load it and follow its tool instructions. Without hooks, enforcement is by instruction only. |

2. Create the knowledge bundle, or keep the one you have:

   ```sh
   python3 .ai/scripts/okf.py init
   ```

3. Ask your agent for a bounded change and watch it declare a tier.

Run tooling from the repository root. Every script answers `--help`.

## The basic workflow

In Claude Code the stage skills are available as commands, and Codex reads the same skills. Each one runs its stage and checks its exit condition before the next may start.

1. **`spec`** clarifies the request and writes a testable spec with acceptance criteria.
2. **`plan`** produces a light or full plan whose steps trace to spec requirements.
3. **`implement`** executes the plan test-first, with minimal edits and focused checks.
4. **`review`** runs the independent two-pass review and the completeness audit.
5. **`ship`** freezes the candidate on the current base, confirms the evidence, and offers a PR, keep, or discard.
6. **`debug`** is used whenever something fails: reproduce, isolate, hypothesize, pin, fix. After three disproved hypotheses it stops and reports instead of stacking patches.

Check where you are at any point:

```sh
python3 .ai/scripts/lifecycle.py status
```

## Autonomous execution

For milestone-sized work that outlives a single conversation:

```sh
python3 .ai/scripts/okf.py init --autonomous
python3 .ai/scripts/lifecycle.py queue-from-spec specs/export.md
python3 .ai/scripts/okf.py handoff
```

The work queue and recovery checkpoint make the repository resumable. Each session takes one bounded batch, ends at a safe checkpoint, and the next one starts with fresh context. Full validation runs outside the model session, so nothing sits open polling it. Work lands as exactly one pull request per milestone, kept in draft until the whole milestone passes review and validation on the integrated head.

Read the [autonomous execution protocol](.ai/autonomous-execution.md), especially §9.12, before launching `autonomy_driver.py`. It defines supervision, progress reporting, and the circuit-breaker stops that override keep-going instructions.

## What's inside

**Governance.** [AGENTS.md](AGENTS.md) is the single authority: normative rules, the evidence hierarchy, execution gates, and persona precedence. [.ai/lifecycle.md](.ai/lifecycle.md) holds stage detail and exit checks, and [.ai/validation-policy.md](.ai/validation-policy.md) holds the rules for when to run which checks.

**Roles.** [Analyst, planner, implementer, reviewer, and orchestrator](.ai/agents/), registered as subagents for Claude Code, Cursor, and Codex. Analyst, planner, and reviewer are read-only by tool restriction where the harness supports it.

**Personas.** [Advisory language guidance](.ai/personas/) for Python, JavaScript/TypeScript, Rust, Go, C#, Dart/Flutter, and Swift/SwiftUI. A persona supplies pitfalls and review checklists and never overrides your request or the acceptance criteria.

**Tooling** in [.ai/scripts/](.ai/scripts/):

| Script | Purpose |
| --- | --- |
| `lifecycle.py` | Declare tiers, record and gate stages, record red/green evidence, trace spec to plan to tests |
| `okf.py` | Read, search, validate, and update the knowledge bundle; queue, checkpoint, and handoff |
| `repo.py` | Bounded read, grep, and file listing for harnesses without those tools |
| `shell_guard.py` | Rejects shell patterns that waste tokens or bypass the structured tools |
| `autonomy_driver.py` and friends | Supervised multi-session execution and out-of-session validation |
| `lifecycle_eval.py` | Scenario evals (L0 to L3) you can run against a real agent |

**Knowledge.** [knowledge/](knowledge/) is this repository's own OKF v0.2 bundle, documenting the governance tooling's contracts. Yours will document your project.

## Philosophy

- **Enforce, don't remind.** A rule that depends on the agent remembering it is a suggestion.
- **Evidence over claims.** Nothing is done until a check that can fail has passed.
- **Right-size everything.** Ceremony should match risk, in both directions.
- **Fresh context beats long context.** Persist state in the repository and start the next slice clean.
- **Surgical changes.** Every changed line traces to the request.
- **Vendor-neutral.** One source of truth for all agents, and hooks per harness only where a harness offers them.

## Validating AGENTIC itself

Changes under `.ai/scripts/` run the regression suite, which also checks lifecycle documents, registrations, skills, hooks, and scripted-agent evals. Its workflow tests need fixtures outside system temporary storage, because the scratch policy rejects `/tmp`:

```sh
mkdir -p .git/okf-test-tmp
TMPDIR="$PWD/.git/okf-test-tmp" python3 -m unittest discover -s .ai/scripts/tests
```

Changes under `knowledge/` run `python3 .ai/scripts/okf.py records`. These checks cover the framework and its records. They do not establish the correctness of your application, which keeps its own build, lint, and end-to-end commands.

## Attribution

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for attribution and license terms covering adapted third-party material.
