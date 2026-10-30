<div align="center">

# AGENTIC

**Agent Governance, Execution, Navigation, Tooling, Integration, and Coordination**

A vendor-neutral framework for governing AI software engineering, from a bounded change to a multi-session autonomous milestone.

*Right-sized process, living requirements, and verification evidence that stays tied to the code.*

</div>

Claude Code, Codex, and Cursor all work from the same rules, roles, and hooks, so switching agents does not mean switching process.

## Why AGENTIC

Most agent workflows are a set of instructions the agent is asked to follow. A long session, a compaction, or an eager model is enough to skip the spec, skip the test, or write "Verified" in a log with nothing behind it. AGENTIC treats those as failures to be blocked, not reminders to be repeated.

- **Process is enforced.** Hooks deny source edits until the agent declares a tier, and deny commits and PRs until Verify is recorded. Each stage is validated against its artifact: a lint-clean spec, a plan that cites every requirement ID, an Approved review, a passing records check.
- **Process is right-sized.** A typo does not get a spec and a feature does not get a one-line note. Four tiers (L0 to L3) scale the ceremony, and the agent must escalate the moment it finds a contract, schema, security, or dependency effect.
- **Claims need evidence.** A bug fix starts from a failing test and records red, then green. "Done" requires an end-to-end check that fails if the success criteria are unmet. Stubs, vacuous tests, and inflated verification notes are prohibited.
- **The repository is the memory.** An Open Knowledge Format bundle in `knowledge/` is the context the next agent or contributor starts from, and changes cannot be called complete until it is synchronized and logged.
- **Verification stays current.** Living requirements can declare checks and their inputs. Assurance reports distinguish current passing evidence from stale, failed, missing, or invalid evidence, and L2/L3 adopter verification blocks on affected mechanical obligations that are not satisfied.
- **Learning carries forward.** Task retrospectives preserve observations with evidence and surface relevant lessons in later sessions. Turning an observation into a binding project rule requires human approval.
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

The agent picks the lowest tier whose conditions hold, and it cannot lower a tier you set. Tiers scale the spec, plan, review, and gate breadth. They never relax the evidence rules. Test-first applies to logic and bug fixes; documentation-only changes use focused document checks.

## Quick start

AGENTIC installs its complete workflow and management kit **inside your project**. You need **Python 3.9+** and **Git**.

Get a local checkout once, in a separate folder from the projects you want to bootstrap:

```sh
git clone https://github.com/enramosjr/agentic.git /path/to/agentic
```

Then use the same command for an existing project or a new folder:

```sh
python3 /path/to/agentic/.ai/scripts/install.py TARGET
```

Replace `TARGET` with the project folder, quoting paths that contain spaces. For example:

```sh
python3 /path/to/agentic/.ai/scripts/install.py "/path/to/my project"
```

The installer creates missing folders and initializes Git when needed. For a project already in Git, choose its worktree root. It installs governance, roles, personas, stage skills, hooks for all supported agents, management scripts, and an ordinary project knowledge bundle. Existing instructions and hook settings are merged, existing knowledge is retained, and conflicting adopter files are kept and reported with a nonzero exit. No commit or Git remote is created.

Everything is local to `TARGET`, including `.ai/`, `.claude/`, `.codex/`, `.cursor/`, and `.agents/skills/`. Global agent settings remain unchanged. The source checkout's knowledge, Git history, and agent session files are excluded. Autonomous execution remains opt-in; see below.

The [distributed tooling guide](.ai/README.md) and its references travel with the
kit. Regression checks use those references rather than an adopter's application
README or private knowledge. Installed kits can be reused as templates: only the
managed governance body is exported, excluding source-only adopter instructions.

Open the target project in your coding agent. For Codex, trust the project's `.codex/` layer and review hooks with `/hooks`; installation alone does not activate that trust. Claude Code uses the local settings, subagents, and skills; Cursor uses its local hooks and the shared subagents. Other agents can follow `AGENTS.md` by instruction. Ask for a bounded change and watch the agent declare a tier.

Rerun the same installer command to update a project from your source checkout. Check an installation without changing files:

```sh
python3 /path/to/agentic/.ai/scripts/install.py --check TARGET
```

An unchanged installation reports `up to date`. Existing Git projects retain dirty-path protection: commit or stash files the installer would change, or explicitly use `--force` after reviewing them. That flag still preserves conflicting adopter files. Exit codes are 0 for success, 1 for drift/conflicts or I/O failure, and 2 for refused input.

After bootstrap, run project tooling from the target root. Every script answers `--help`.

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

Invoke state-mutating lifecycle commands directly. Wrapping them in
`lifecycle.py run` is refused within the same repository to preserve acceptance
and ledger evidence; read-only inspection and independent fixture repositories
remain supported. See the [distributed lifecycle guide](.ai/docs/lifecycle.md).

## Capabilities beyond the task checklist

### Living requirements and safe changes

Structured capabilities use stable requirement IDs and named scenarios. Changes to an existing capability are expressed as an approved delta: additions, modifications, and removals pinned to the requirement blocks being changed. `lifecycle.py merge SPEC --dry-run` previews the result; applying it checks the approved baseline, preserves unrelated requirements, and records a recoverable merge receipt. Existing prose capabilities remain supported and are not converted automatically. See [brownfield deltas](.ai/lifecycle.md#brownfield-deltas).

`lifecycle.py analyze SPEC` checks a specification before approval. After implementation, `lifecycle.py converge SPEC` executes its acceptance commands, records each outcome, and supplies the convergence evidence required for L2+ review and verification. A manual acceptance item needs reviewed evidence; it does not become an automated PASS.

### Requirement assurance and architecture checks

A capability requirement can declare a `Verify:` command and `Inputs:` globs. From an adopting project's root:

```sh
python3 .ai/scripts/lifecycle.py assure
python3 .ai/scripts/lifecycle.py assure --changed --base HEAD
python3 .ai/scripts/lifecycle.py assure --run EXPORT-R1
```

Use an actual requirement ID in place of `EXPORT-R1`. The first two commands report without running checks; the last explicitly executes the selected obligation and records evidence in an active task. Reports distinguish **VERIFIED**, **STALE**, **FAILED**, **UNVERIFIED**, **INVALID**, **MANUAL**, and **UNDECLARED**. L2/L3 adopter Verify blocks affected requirements with stale, failed, missing, or invalid mechanical evidence. Manual judgments and recorded risk acceptance remain visible and cannot waive those failures.

`Governed-by:` links a requirement to an architecture decision or other knowledge document. Pair it with a real checker to enforce a dependency boundary or another architectural constraint, and include the decision in `Inputs:` if its edits should invalidate evidence. The link declares provenance; the check and its declared inputs determine what was verified. See [assurance status](.ai/lifecycle.md#assurance-status) and [governed architecture constraints](.ai/lifecycle.md#governed-architecture-constraints).

### Reusable evidence and qualified artifacts

`lifecycle.py run` records command results with input and runtime fingerprints. `reuse` tells the agent whether a passing result still covers the candidate. Supported Python and Cargo checks have conservative inferred scopes; explicit `--inputs` and reviewed [Python input profiles](.ai/lifecycle.md#python-validation-input-profiles) support narrower declarations. Unknown commands retain a conservative whole-tree fallback. Evidence only covers the captured inputs and runtime identity.

For checks against a specific built artifact, `artifacts.py freeze` seals declared files in a separate bundle. `artifacts.py run` verifies their pinned hashes before and after execution; `variant` creates a separate, unqualified copy for mutation checks. See [qualified artifacts](.ai/docs/lifecycle.md#qualified-artifacts).

### Review provenance and completion

Ordinary independent review is part of L2+. An additional, opt-in [mechanically bound review mode](.ai/lifecycle.md#mechanically-bound-review-opt-in) supports Claude and Codex native capture: it pins the candidate, approved artifacts, convergence, evidence, and reviewer identity, and blocks recognized writers during review. Missing or mismatched capture refuses advancement. This mode requires supported native hooks and an identifiable Linux launcher; scripted adapter tests alone do not qualify native delivery. It is an operational integrity boundary, not an OS sandbox.

`lifecycle.py finish --json` consolidates completion blockers. `finish --apply` can perform supported bookkeeping and record Verify from existing passing evidence through the normal gates. It does not run application tests or supply a missing review. See [completion](.ai/docs/lifecycle.md#one-completion-operation).

### Retrospectives and approved project rules

At L1–L3, the agent closes a retrospective before Verify, selecting evidence-backed lessons or recording why there are none. `learn` captures observations; `observations --query TEXT` retrieves relevant ones for later work. Only human-approved `promote` and `retire` operations change binding project rules. See the [learning contract](.ai/docs/learning-loop.md) and [workflow](.ai/docs/learning-loop-playbook.md).

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
| `lifecycle.py` | Gate stages; analyze, converge and merge specs; report requirement assurance; record scoped evidence, reviews, retrospectives and completion |
| `okf.py` | Read, search, validate, and update the knowledge bundle; `sync-check` and `stamp verified --run` make Gate 3 mechanical; queue, checkpoint, and handoff |
| `repo.py` | Bounded file tools plus read-only `context`, actual command help and Markdown heading discovery |
| `artifacts.py` | Seal declared artifacts, verify hash-pinned acceptance inputs and create separate unqualified mutation copies |
| `assurance_inputs.py` | Export reviewed input declarations for supported Python checks without executing them or changing evidence |
| `assurance_demo.py` / `assurance_architecture_demo.py` | Exercise evidence freshness and a forbidden dependency in disposable fixture repositories |
| `validation_select.py` | Select focused validation from changed paths |
| `shell_guard.py` | Rejects shell patterns that waste tokens or bypass the structured tools |
| `autonomy_driver.py` and friends | Supervised multi-session execution and out-of-session validation |
| `lifecycle_eval.py` | Scenario evals (L0 to L3) you can run against a real agent |

**Knowledge.** The installer creates the adopter project's empty OKF v0.2 `knowledge/` bundle, keeping existing knowledge when present. The framework source declares its identity in `.agentic.json`, keeps its own documentation outside `knowledge/`, and stores lifecycle receipts in Git scratch. Its source marker and evaluation documents are not installed into adopter projects.

## Philosophy

- **Enforce, don't remind.** A rule that depends on the agent remembering it is a suggestion.
- **Evidence over claims.** Nothing is done until a check that can fail has passed.
- **Right-size everything.** Ceremony should match risk, in both directions.
- **Fresh context beats long context.** Persist state in the repository and start the next slice clean.
- **Surgical changes.** Every changed line traces to the request.
- **Vendor-neutral.** One source of truth for all agents, and hooks per harness only where a harness offers them.

## Validating AGENTIC itself

Changes under `.ai/scripts/` run the regression suite, which also checks lifecycle documents, registrations, skills, hooks, and scripted-agent evals. The parallel runner uses disk-backed scratch for workflow fixtures:

```sh
python3 .ai/scripts/lifecycle.py run governance-suite -- python3 .ai/scripts/run_tests.py -j 4
```

In a project that uses AGENTIC, `python3 .ai/scripts/okf.py records` checks that project's knowledge bundle. The suite above covers the framework only. It does not establish the correctness of your application, which keeps its own build, lint, and end-to-end commands.

Scripted-agent evaluations exercise harness mechanics. They do not establish a real model's qualification for unattended work; the real-model baseline remains on hold pending explicit qualification and supervision requirements. Installation does not authorize or launch that work.

## Attribution

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for attribution and license terms covering adapted third-party material.
