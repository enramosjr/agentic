# Assurance initiative: current state and competitive assessment

Version: **0.1.0-draft**, 2026-10-27. Framework base: `5f81468`.
Companion documents: [architecture](architecture.md), [increment 1 spec](specification.md).

This is research output (planning artifacts A and B of the initiative brief). It
describes what exists and what competitors document. It makes no claim that any
proposed capability is implemented.

## 1. Current state (from source at `5f81468`)

Classification: **F** functional and enforced, **P** partial, **D** functional but
disconnected from related systems, **C** convention or documentation only, **A** absent.

| Capability | State | Where | Observation |
|---|---|---|---|
| Tier declaration and stage gates | F | `lifecycle.py` `cmd_tier`, `gate_problem`, `cmd_hook` | Hooks deny edits, commits and PRs per tier in Claude Code, Codex and Cursor |
| Stage artifact pinning | F | `lifecycle.py` `ref_hash`, `audit_problems` | Body sha256 of spec, plan and review; audit fails on later edits |
| Requirement IDs | P | `REQ_LINE` (`R<n>`), `brownfield.ID` (`NS-R<n>`) | `R<n>` is local to one spec; only structured capabilities have stable IDs |
| Spec lint and coverage | F | `lifecycle.py analyze`, `trace` | `trace` is textual: an ID cited in a plan or test file counts as covered |
| Requirement acceptance execution | D | `lifecycle.py converge` | Runs one command per requirement for the active task only; its ledger entries carry **no inputs**, so they are bound to the exact tree |
| Execution evidence ledger | F | `ledger.py`, `lifecycle.py run` | Exit, tree, head, per-file input hashes, environment/runtime digest; no output stored; locked append |
| Evidence freshness and reuse | F (task-scoped) | `ledger._entry_verdict`, `lifecycle.py reuse` | Revision-, content-, metadata- and environment-sensitive; no inputs means exact-tree only |
| Conservative unknown impact | F | `ledger.default_inputs`, `validation_select.py` | Workspace tests default to `**`; unknown packages widen; external paths refuse inference |
| Living requirements | F | `brownfield.py`, `lifecycle.py merge` | Delta specs with hash-pinned target baselines, receipts, retired-ID reservation |
| Requirement → verification after merge | **A** | `.ai/lifecycle.md` Brownfield deltas | "Acceptance commands stay in the delta and are executed only by converge": the living capability loses its verification obligation |
| Cross-task evidence status | **A** | — | Committed records keep ledgers and converge results, but nothing reads them after the task closes |
| File → knowledge impact | P | `okf.py affected`, `sync-check` | Maps changed files to whole documents via `sources`, not to requirement IDs |
| Change → check impact | P | `validation_select.py` | Cargo reverse dependencies only; other ecosystems use conservative full sets |
| Sealed acceptance inputs | F | `artifacts.py` | Hash-pinned declared files and mutation copies |
| Review and approval provenance | P | stage `approved_by` (`human:`, `decision:`), review `## Verdict` | Recorded claims, explicitly not authenticated; review findings are not structured data |
| Stub and weak-test detection | F | `scan.py`, `lifecycle.py scan-diff` | Added-line patterns; weak tests informational |
| Architecture constraints | C | personas, `knowledge/project/rules.md`, ADR convention | Human-approved rules are injected as prose; nothing mechanically checks them |
| Completion consolidation | F | `completion.py`, `lifecycle.py finish` | Diagnoses blockers from existing evidence |
| Autonomous execution and recovery | F | `autonomy_driver.py`, `okf.py checkpoint`, `handoff` | Queue states, checkpoints, out-of-session validation |
| Assurance report | **A** | — | No artifact answers "which requirements are verified at HEAD and why" |

### Reuse opportunities

1. `ledger._entry_verdict` already decides whether one piece of evidence still holds
   at the current content. A cross-task status is this function applied per
   requirement over committed records. No second ledger is needed.
2. `lifecycle.py run` already produces content-bound evidence. A requirement
   obligation run through it gains every existing guarantee (locking, no output,
   environment digest, submodule refusal).
3. Structured capability blocks already have stable IDs, scenarios and
   hash-pinned modification. A requirement's verification obligation fits as one
   more indented line, so deltas carry it without changes to merge semantics.
4. Committed records (`knowledge/history/lifecycle/*.json`) are already the
   version-controlled evidence store. Framework source keeps them in Git scratch.

### Constraints found

- Framework source has no `knowledge/` bundle by design, so a capability-based
  feature is dogfooded through fixtures, not on the framework's own requirements.
- `R<n>` IDs are reused by every whole-feature spec. Durable assurance must key on
  `NS-R<n>` capability IDs; whole-feature specs stay task-scoped.
- Approvals are claims (`AGENTS.md` §2.5). Assurance must report them as claims.
- The user declined paid or long fresh-run evaluation campaigns
  ([evaluation protocol](../evaluation/v1/specification.md)). Validation of this
  initiative uses deterministic fixtures and existing records unless that changes.

## 2. Competitive analysis

Sources are public documentation read on 2026-10-27. **Confirmed** means stated in
the project's own docs or repository; **inferred** means from third-party write-ups
or absence of documentation. No competitor tool was installed or run.

| Concern | GitHub Spec Kit | BMAD Method + TEA | OpenSpec | Kiro | AGENTIC today |
|---|---|---|---|---|---|
| Spec management | Confirmed: spec, plan, tasks, constitution | Confirmed: PRD, architecture, stories | Confirmed: proposal → apply → archive, ADDED requirement sections | Confirmed: EARS requirements, design, tasks | Specs, deltas, living capabilities |
| Spec-to-code gap check | Confirmed: `/speckit.converge` grades missing/partial/contradicts/unrequested, appends tasks; "not a diff tool", no history | Confirmed: TEA trace maps requirements to tests | Confirmed: `/opsx:verify` exists; behavior undocumented on README | Confirmed: property-based tests derived from requirements | `converge` runs declared commands; no LLM gap review |
| Who builds the trace | Agent | Agent; CLI validates the matrix and arithmetic (confirmed) | Agent | Agent | Author declares commands; tooling executes |
| Release gate | Extension-dependent (SpecAssay Check refuses silent gaps, confirmed) | Confirmed: PASS/CONCERNS/FAIL thresholds by priority, filed waivers with expiry | Inferred: process gating only | Inferred: review-gated | Stage gates; no requirement-level gate |
| Evidence bound to revision | Not documented | Confirmed: CLI snapshots inputs and Git revision; other-commit live results excluded | Not documented | Not documented | Ledger binds head, tree, per-file hashes, environment |
| Invalidation after later change | Not documented | Not documented beyond "current-revision failure caps at CONCERNS" | Not documented | Not documented | Within a task only |
| Enforcement | Extension hooks with priorities (confirmed) | Opt-in reviewer gates (confirmed) | Inferred: none | Agent hooks (confirmed) | Harness hooks deny edits/commits/PRs |
| Portability | Many agents (confirmed) | Claude Code, Codex and others (confirmed) | Many agents (confirmed) | Kiro IDE/CLI only | Claude Code, Codex, Cursor; others by instruction |

Research context: recent papers report that binding agent evidence to code units
with freshness checks improves task success, on one benchmark and one model
([ECK, arXiv 2608.16295](https://arxiv.org/pdf/2608.16295)), and that deterministic
phase gates catch "implementation with no registered verifying test" in a single
case study ([arXiv 2606.26924](https://arxiv.org/pdf/2606.26924)). Neither is a
product AGENTIC competes with; both support the direction, weakly.

### Conclusions

1. **The directive's positioning is partly outdated.** Spec Kit now has a
   convergence step, and BMAD TEA already has requirement-to-evidence tracing with
   revision snapshots, thresholds and waivers. "Traceability" and "release gate"
   alone close gaps; they do not differentiate.
2. **Defensible differentiator:** evidence that is (a) produced by the framework's
   own runner rather than an agent-built matrix, (b) bound to the exact inputs it
   depends on, and (c) re-evaluated against later changes, so the framework can say
   which earlier verification a new change invalidated and what minimum set must
   rerun. No reviewed competitor documents (c). AGENTIC already has (a) and (b)
   inside a task.
3. **Gaps to close, not differentiate:** an LLM gap review like Spec Kit `converge`
   (AGENTIC's reviewer covers this by convention), priority-weighted gates and
   time-boxed waivers like TEA. These are candidates for later increments.
4. **Claims to avoid:** "only framework with traceability", "proves correctness",
   or any reliability claim before the measurements in the architecture document
   §8 exist.

### Sources

- [Spec Kit June 2026 newsletter](https://github.com/github/spec-kit/blob/main/newsletters/2026-June.md)
- [SpecAssay Check extension submission](https://github.com/github/spec-kit/issues/4850)
- [BMAD TEA repository](https://github.com/bmad-code-org/bmad-method-test-architecture-enterprise),
  [run-trace guide](https://bmad-code-org.github.io/bmad-method-test-architecture-enterprise/how-to/workflows/run-trace/),
  [tea-trace CLI](https://bmad-code-org.github.io/bmad-method-test-architecture-enterprise/reference/tea-trace-cli/)
- [BMAD-METHOD releases](https://github.com/bmad-code-org/BMAD-METHOD/releases)
- [OpenSpec repository](https://github.com/Fission-AI/OpenSpec)
- [Kiro spec correctness](https://kiro.dev/docs/specs/correctness/)
- Third-party comparisons, lower weight: [Augment](https://www.augmentcode.com/tools/best-spec-driven-development-tools),
  [Particula](https://particula.tech/blog/spec-driven-development-tools-spec-kit-vs-kiro-vs-tessl)

Limits: versions and dates in third-party sources conflict; Spec Kit's latest
release number could not be confirmed. BMAD TEA's gate computation may be partly
model-driven; its docs do not say. A hands-on comparison was not performed.
