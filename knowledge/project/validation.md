---
type: Development Guide
title: Governance validation and evidence reuse
description: Testing boundaries and deterministic receipt reuse for the governance tooling.
tags: [governance, validation]
status: stable
evidence: implementation-and-current-specifications
generated: { by: agent/codex, at: 2026-10-18T04:14:58Z }
sources:
  - id: agents
    resource: ../../AGENTS.md
  - id: protocol
    resource: ../../.ai/autonomous-execution.md
  - id: implementer
    resource: ../../.ai/agents/implementer.md
  - id: orchestrator
    resource: ../../.ai/agents/orchestrator.md
  - id: validator
    resource: ../../.ai/scripts/autonomy_validation.py
  - id: driver
    resource: ../../.ai/scripts/autonomy_driver.py
  - id: okf
    resource: ../../.ai/scripts/okf.py
  - id: validation-tests
    resource: ../../.ai/scripts/tests/test_autonomy_validation.py
  - id: handoff-tests
    resource: ../../.ai/scripts/tests/test_autonomy.py
  - id: readme
    resource: ../../README.md
  - id: validation-policy
    resource: ../../.ai/validation-policy.md
verified: { by: "process:python3 -m unittest discover -s .ai/scripts/tests", at: 2026-10-18T14:41:59Z }
---

# Governance validation and evidence reuse

Testing boundaries and deterministic receipt reuse for the governance tooling.

The normative Gate 4 execution rules (`AGENTS.md` §8.4) live in [.ai/validation-policy.md](../../.ai/validation-policy.md), moved verbatim from `AGENTS.md` so they load on demand; `AGENTS.md` keeps the verification table and a MUST-load pointer.

## Execution boundaries

Agents use focused checks for their owned changes. One owner runs the integrated gate on a frozen candidate. Opening or updating a draft PR does not independently trigger another gate; PR readiness, completed batches and milestone acceptance retain their required checks. Before an expensive execution, the existing evidence report identifies its criterion, input scope and changed inputs or missing covering PASS.

A batch follows the requested acceptance and may span up to three model sessions. A SAFE implementation handoff retains the same IN_PROGRESS batch, focused evidence, deferred full commands and next source action, and does not require a full gate to end the session. An independently deliverable part that passes its own acceptance and review is closed as DONE with scoped Evidence rather than held for the rest of the batch. Full validation follows implemented and reviewed batch acceptance or an explicit required readiness boundary. Delivery-stall, elapsed-time and qualification limits remain unchanged.

## Convergence and test proportionality

A task has a hard session ceiling. Its acceptance is frozen at claim time, each implementation session started with the task active increments a `Sessions` field in the work queue, and a task at three sessions must be split into separately gated tasks that start at zero or be closed. Because the count lives in the queue, relaunching the driver with larger `--max-*` flags cannot reset it. Testing is proportional: one E2E per user-visible criterion, negative controls only where failure would pass silently (one per assertion class), variants parametrized rather than multiplied into lanes, and "parity" met by the user-visible checklist rather than a one-for-one port of a prior harness. There is no manual qualification: each acceptance item names an unattended, deterministic command at claim time, and an item needing real hardware or a person is out of the batch's scope (a recorded decision or a separate BLOCKED task). An environment-dependent check that fails environmentally gets one repair, then moves to a deterministic layer over the same product code, or is dropped from the batch with the dropped scope recorded.

Mechanical limits back the rules, because prose alone did not stop earlier runs. `autonomy_driver.py` and `okf.py queue --record-session` refuse a fourth session on a task; `okf.py checkpoint` fails (not SAFE) when a task exceeds the session cap, when `status.md` exceeds 6,000 characters, or when an IN_PROGRESS task entry exceeds 3,000 characters or lists more than eight backticked acceptance commands; the driver rejects `--max-stalled` above 4; `shell_guard.py` rejects `DISPLAY=:0`/`:1` and `WAYLAND_DISPLAY` so acceptance cannot run on the user's live display. The entry-size and command caps only see what is written in the queue entry; acceptance kept in a plan or history document is bounded by the session cap instead.

Origin, measured from Codex transcripts and the branch: athenaeum PR 8 task U4 ran 54 worker sessions and about 3,060 tool calls (about 320M tokens, plus about 39M in per-action review sessions) over roughly nine hours and 219 commits. About 57% of shell calls were code reading through 250-line `repo.py read` windows; about 950 build/test/gate commands ran, about half repeats, including 41 full `clippy --all-targets --all-features` runs and 69 runs on `DISPLAY=:0`. Acceptance was a cross-product of six systems, managed and automatic modes, positive and inverted controls, and software and hardware paths. The driver's two-session stall limit did stop the run; a relaunch with `--max-stalled 20` and "no DONE fragments, no full gate until complete" wording (the PR 11 rule) continued it. Retrospective check: against PR 8's current state the new status-size check fails, while the entry-size (1,992 chars) and command (2) caps would not have fired and the session count would only start from adoption.

## Managed evidence reuse

Managed validation defaults to exact-commit receipt binding. Deterministic commands may opt into cross-commit reuse with a complete, reviewed `inputs` list of tracked repository files or directories. Git tree fingerprints include file contents, paths and modes. The whole command, effective environment, validation kind and transitive prerequisite inputs must also match. Receipt and log integrity checks remain required, and each reused receipt preserves its original `tested_candidate`.

Missing inputs, symlinks and submodules fail closed. Unknown dependencies, mutable external inputs, unverified generated artifacts, Git-HEAD-sensitive commands and exact-commit qualification retain commit binding. Model-backed commands cannot declare commit-independent inputs. Input declarations require review: fingerprints establish equivalence of the declared scope, not completeness of that scope.

Deterministic validation removes a fixed list of inherited session bookkeeping variables (`CODEX_THREAD_ID`, `SHLVL`, `_`, and the driver's request, registry, release, audit, progress and recovery keys) from both subprocess execution and receipt identity. Explicit command environment declarations still count, including those keys. All other environment inputs remain bound; model-backed validation keeps its full environment. Transitive prerequisites use the same environment policy. New receipts retain per-component hashes so mismatch reports distinguish source, command, environment, kind and dependencies without printing environment values. Legacy receipts remain hash-bound and are never upgraded by assuming equivalence. When a retained same-label PASS has an incompatible fingerprint without component hashes, the validator stops rather than silently rerunning it. Review and reconcile retained evidence separately, preserving the complete acceptance map when submitting only missing checks. Tooling updates do not hot-load into a running driver; reconcile validator versions at a safe handoff without resetting budgets.

## Verification

The managed-validation regression tests execute real subprocess assertions, submit a resume through the CLI, verify that records-only commits reuse the product check, and verify that changed fixtures, source and prerequisites rerun affected checks. A deliberately broken source assertion must fail. Existing tests also cover changed environments, tampered logs, invalidated candidates and parallel execution.

The fresh-session regression starts two separate validator processes with different thread/handoff/shell metadata and proves the product counter increments once while both the check and its dependent reuse verified PASS. Explicit session-key declarations and model-backed environment changes still execute fresh. Handoff prompt tests retain the cross-session batch instructions.

Run the governance suite with a writable, disk-backed temporary directory as described in the repository README. Successful test commands and outcomes are recorded in the bundle log after execution.
