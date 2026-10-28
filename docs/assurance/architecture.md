# Assurance initiative: target architecture and delivery plan

Version: **0.1.0-draft**, 2026-10-27. Framework base: `5f81468`.
Inputs: [assessment](assessment.md). First increment: [specification](specification.md).

Planning artifacts C through H of the initiative brief. Nothing here is implemented.

## 1. Thesis

AGENTIC does not need a new assurance subsystem. It needs its existing evidence to
**outlive the task that produced it**. The ledger already knows whether a check
still holds for the current content. What is missing is a durable link from a
stable requirement to the check that verifies it, and a reader that evaluates that
link at any later revision.

So the design adds one declaration (a verification obligation on a capability
requirement), one producer path (run obligations through the existing ledger) and
one reader (`lifecycle.py assure`). Everything else in the brief is layered on
those three, or deferred.

## 2. Model

No graph database and no new store. The graph is derived on demand from files that
are already version-controlled:

| Entity | Source of truth | Identity |
|---|---|---|
| Requirement | Structured capability block in `knowledge/capabilities/*.md` | `NS-R<n>` (stable, retired IDs reserved) |
| Verification obligation | Indented `- Verify:` and `- Inputs:` lines in that block | (requirement ID, command argv, input globs) |
| Execution evidence | Ledger entry labeled `req:NS-R<n>` in a committed lifecycle record | (record task, entry index); bound by head, per-file input hashes, environment digest |
| Spec, plan, review, approval | Stage refs and `approved_by` in the record | Body sha256 |
| Architecture constraint | A capability requirement in an architecture capability, `governed_by` an ADR (increment 3) | `NS-R<n>` |

Relationships are not stored as edges. `verified_by` is the obligation line;
`invalidates` is computed (an input changed since the evidence); `derived_from` is
the merge receipt; `approved_by` is the stage claim. Deriving rather than storing
avoids a second copy that can disagree with the files.

### Provenance classes

Every status names its basis, and only the first class can produce VERIFIED:

1. **mechanical**: a ledger entry the framework's runner wrote (exit, head, input hashes).
2. **declared**: a human-approved requirement or obligation line (authority of the approval claim).
3. **attested**: a review verdict or MANUAL citation (an agent or human judgment, reported as such).
4. **claimed**: agent notes and log text (never evidence of behavior).

An obligation whose command does not exist, a record that fails `ledger.audit`, or
evidence for a different command than the current obligation never yields VERIFIED.

## 3. Statuses and evaluation

For each capability requirement, `assure` computes one status:

| Status | Meaning | Exit effect |
|---|---|---|
| VERIFIED | Newest evidence for the current obligation passed and its inputs, environment and command are unchanged | none |
| STALE | Passing evidence exists, but an input file, the environment or (for unscoped obligations) the tree changed; names the changed files | fail |
| FAILED | The newest evidence for the current obligation failed | fail |
| UNVERIFIED | An obligation is declared but no evidence for this exact command exists | fail |
| MANUAL | The requirement declares human judgment (`- Verify: manual`) | none, listed |
| UNDECLARED | No obligation declared (all existing capabilities today) | none by default; fail with `--strict` |

**Unknown impact is not no impact.** An obligation without `Inputs:` is bound to the
whole tree, so any later commit makes it STALE. Authors earn narrower reverification
only by declaring inputs, and an under-declared input set is a review finding, the
same rule `lifecycle.py run --inputs` already lives under.

`assure --changed --base REV` answers "what must be reverified" without evidence:
obligations whose inputs intersect the diff, plus every unscoped obligation.

## 4. Integration

- **OKF**: obligations live in capabilities, so `okf.py validate` and deltas cover
  them; no new bundle section. A delta adding `Verify:` lines is an ordinary
  modification with an ordinary hash pin.
- **Lifecycle**: increment 1 is report-only. No new stage, no new gate. Increment 2
  makes `stage verify` at L2+ refuse when a requirement the change touched is
  STALE, FAILED or UNVERIFIED, reusing the existing verify refusal path.
  L0 and L1 stay unaffected, so a typo never pays for this.
- **Hooks**: unchanged. Assurance runs inside commands the hooks already govern.
- **Autonomous mode**: queue `Acceptance` remains the L3 spec. A DONE task's
  evidence becomes visible to later tasks through committed records.
- **Concurrency**: no daemon and no lock across branches. Status is computed from
  current file content, so another agent's merged change automatically stales
  dependent evidence. Records on unmerged branches are invisible until merged; that
  limit is reported, not hidden.
- **Framework source**: reads records from Git scratch, matching `record_path`.

## 5. Alternatives considered

| Alternative | Decision | Reason |
|---|---|---|
| Separate assurance ledger or graph file | Rejected | Duplicates the ledger; two stores can disagree |
| Graph database or service | Rejected | Brief non-goal; a few hundred requirements fit in files |
| Symbol-level static analysis in core | Deferred | Language-specific; optional adapters can generate `Inputs:` later |
| LLM-built requirement→test mapping (Spec Kit, TEA style) | Rejected for VERIFIED | Agent-built links are attested, not mechanical; may be added as an advisory report |
| Infer inputs from test imports | Deferred | Unsound across languages; conservative tree binding is the default |
| Store acceptance only in deltas (status quo) | Rejected | Living capability loses its verification after merge (assessment §1) |
| Make `converge` the producer | Partly | Converge serves task specs with `R<n>` IDs; obligations need stable IDs. Increment 2 may let converge record `req:` evidence for delta-operated IDs |
| Hard gate in increment 1 | Rejected | Adoption risk before false-positive rates are known |

## 6. Delivery plan

Each increment is independently verifiable and leaves AGENTIC working if later
increments never ship.

| # | Increment | Value | Depends on |
|---|---|---|---|
| 1 | Obligations, `assure` report, `assure --run`, `assure --changed` ([spec](specification.md)) | Answers questions 1–3 and 5–7 of the brief for declared requirements | — |
| 2 | Gate: L2+ `stage verify` refuses touched STALE/FAILED/UNVERIFIED requirements; converge records `req:` evidence for delta IDs | Prevents accepting work that invalidated earlier verification | 1, plus measured false-positive rate |
| 3 | Architecture constraints as capability requirements with `Governed-by: ADR` and constraint commands (e.g. import-linter, `cargo deny`) | Drift detection with no second policy system | 1 |
| 4 | Attested evidence in the report: review verdicts, MANUAL citations, approvals, time-boxed risk acceptance | Answers questions 4, 7 and 8 fully | 1 |
| 5 | Optional input adapters (Cargo reverse deps from `validation_select.py`, then others) generating narrower `Inputs:` | Less rerun cost | 1 |
| 6 | Adoption: a one-page walkthrough and a fixture demo of STALE detection | Shows the differentiator in minutes | 1 |
| 7 | Measurement (§8) and pruning | Keep only what earns its cost | 1–2 |

## 7. Risks

| Risk | Mitigation |
|---|---|
| Under-declared inputs produce false VERIFIED | Default is whole-tree binding; reviewers check `Inputs:`; increment 5 adapters; report shows the scope basis |
| Forged or hand-edited records | `ledger.audit` gate on every record read; audit detects drift, not deliberate forgery of both record and receipt (existing documented limit) |
| Flaky obligations | FAILED is reported, never retried automatically; `reuse` rules unchanged |
| Environment drift (toolchain upgrade) | Existing context digest makes evidence STALE |
| Overhead | Report-only first; reading records is file I/O; no command runs without `--run` |
| Large record histories | Read newest-first and stop per requirement; bounded by record count |
| Adoption friction from new syntax | Lines are optional; UNDECLARED is not a failure by default |
| False positives block work (increment 2) | Gate only after increment 1 data; L0/L1 exempt; touched-requirements scope |
| Over-claiming | Report states scope: a pass verifies that command on those inputs, not the requirement in general |

## 8. Verification strategy and measurement

**Testing the feature without trusting its own claims.** Unit and fixture tests in
`.ai/scripts/tests/` build temporary Git repositories and assert exact statuses for
adversarial cases: input edited, unrelated file edited, input deleted, obligation
command changed, environment changed, newer failure after older pass, malformed
record, output-bearing record, unscoped obligation after commit, retired ID. Each
test is shown to fail against a deliberately broken variant (`AGENTS.md` §8.6).

**Measuring value, within the user's zero-spend constraint.** No paid or long
campaign is planned. Two cheap sources:

1. A deterministic scenario fixture set (feature, requirement change, regression,
   stale evidence, dependency change, multi-agent handoff) that reports detection
   counts, false STALE counts and rerun counts versus a "rerun everything" baseline.
   This measures mechanism behavior, not agent outcomes.
2. The existing-run evaluation ([protocol](../evaluation/v1/specification.md)) and
   normal future development records: count accepted changes later found to have
   invalidated earlier verification. Comparison with competitors stays descriptive
   until a funded campaign is explicitly requested.

## 9. Answers to the brief's research questions

1. Existing: revision/input-bound evidence, reuse, converge, stable capability IDs,
   hash-pinned stages, audit (assessment §1).
2. Extend: ledger verdicts, `run`, capability blocks, committed records.
3. A stored graph: no. A derived view: yes, via `assure`.
4. Authoritative relationship: a line in a human-approved capability or spec.
5. Provenance: the four classes in §2, reported per status.
6. Freshness: existing per-file content and metadata hashes plus environment digest.
7. Granularity: file-level declared inputs; whole tree by default.
8. Unknown dependencies: bind to the whole tree, therefore STALE after any commit.
9. Avoiding excess runs: declared inputs and `--changed`; adapters later.
10. Architecture rules: as capability requirements with constraint commands (increment 3).
11. Concurrency: compute from content at read time; no cross-branch locking.
12. Minimum useful: increment 1.
13. Optional or deferred: gates, adapters, attested evidence, LLM gap review, dashboards.
14. Comparable: BMAD TEA trace (closest), Spec Kit converge plus extensions.
15. Demonstrable value: STALE detection of earlier verification after a later
    change, with minimal rerun scope, shown by the fixture scenarios.
16. Overhead: file reads per report; obligations run only on `--run`.
17. OKF: obligations live in capabilities; records stay in `history/lifecycle/`.
18. Hooks and commands: no hook change; one new subcommand; gate later via `stage verify`.
19. Evidence versus agent conclusions: evidence wins; a claim never upgrades a status.
20. Self-testing: adversarial fixtures and broken-variant checks (§8).

## 10. Decisions for the user

1. Approve increment 1 as specified, report-only, with no gate.
2. Confirm that measurement stays zero-spend (fixtures plus existing records).
3. Confirm the obligation syntax lives inside capability blocks rather than a
   separate file.
