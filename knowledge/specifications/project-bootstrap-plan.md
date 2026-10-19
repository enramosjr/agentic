---
type: Implementation Plan
title: Project bootstrap implementation plan
description: Implementation and validation sequence for the approved project-local bootstrap specification.
tags: []
status: stable
evidence: project-documentation
generated: { by: agent/gpt-6, at: 2026-10-19T19:22:42Z }
sources:
  - id: ai-scripts-install-py
    resource: ../../.ai/scripts/install.py
  - id: ai-scripts-tests-test-install-py
    resource: ../../.ai/scripts/tests/test_install.py
  - id: readme-md
    resource: ../../README.md
verified: { by: "process:python3 -m unittest discover -s .ai/scripts/tests -p test_install.py", at: 2026-10-19T21:17:24Z }
---

# Implementation Plan: One-command project bootstrap

## Objective

Implement the approved project-bootstrap.md spec: one project-local installer command for existing and new folders. The user approved the spec and authorized planning and implementation in the same message.

## Success criteria

R1–R6 pass their acceptance commands. Existing Git projects retain their protections; missing and non-Git targets bootstrap without manual copying, global agent changes, commits, or remotes.

## Current state

The planner inspected `.ai/scripts/install.py` (KIT, install, dirty_paths, main), `.ai/scripts/tests/test_install.py` (InstallerCase, refusal and E2E tests), and README.md's Install section. The installer requires an existing Git root at lines 195–200, then plans safe writes, merges instructions/hooks, preserves conflicting plain files, and initializes knowledge. README currently describes manual copying. `okf.py affected` maps all three files to the approved spec.

## Proposed approach

Classify the target using its nearest existing ancestor before writes. Recognize an existing Git root, refuse descendants of worktrees and invalid Git metadata, or prepare to initialize an independent project. Defer mkdir and Git initialization until existing preflight validation succeeds and check mode has returned. Skip the dirty-path check only for this invocation's newly initialized repository; retain merge/conflict behavior. Preserve CLI flags and manifest format.

## Boundaries and invariants

Use stdlib Python 3.9+ and argument-vector subprocesses. Do not infer permission to initialize from arbitrary Git execution errors. Preserve existing application files, knowledge, instruction text, settings, and plain-file conflicts. Do not create commits, configure remotes, copy template knowledge/history/session state, or write global configuration. Codex trust remains an application activation step.

## Implementation steps

### Step 1: Target preparation and preservation (R2, R3, R4, R6)

Write failing BootstrapNewFolderTests, BootstrapExistingFolderTests and bootstrap refusal/check cases in `.ai/scripts/tests/test_install.py`. Cover missing nested paths with spaces, populated non-Git folders, unrelated bytes, merged hooks/instructions, preserved knowledge and plain-file conflicts. Include file/template/nested-worktree refusal and malformed inputs before mutation. Change `install.py` to classify targets read-only, preserve existing Git safeguards, and initialize Git only after preflight. Verify through actual CLI subprocesses and the installer regression suite.

### Step 2: Local installed workflow (R2, R5, R6)

Write BootstrapLocalityTests and BootstrapWorkflowTests before implementation. Assert isolated home/config directories unchanged; complete project kit installed; template knowledge, history and session sentinels excluded; no commit or remote. Exercise immediate rerun, read-only check for missing/non-Git targets, installed records, and actual lifecycle-hook denial. Reuse existing install logic rather than add a second installer.

### Step 3: Single documented route (R1, R5, R6)

Write BootstrapDocumentationTests, then replace README manual copying with checkout acquisition and `python3 /path/to/agentic/.ai/scripts/install.py TARGET`. Document existing/new folders, automatic Git initialization, local integrations, safe reruns, check mode, prerequisites, and Codex trust. Update installer help. No autonomous queue by default.

### Step 4: Sync, independent review, and verification (R1–R6)

Run affected, add installation capability/playbook and evidence history, append the log, run convergence, and delegate independent review against the approved spec and plan. Resolve findings. Freeze against the current default branch before the full gate. Record review and verify evidence and leave the reviewed branch available for delivery.

## Testing strategy

Tests use real Git repositories and subprocess entry points with byte/state preservation assertions. New behavior must fail on the original installer. Existing installer regressions protect upgrades, manifests, hooks, instructions, dirty paths, and conflict semantics. Snapshot checks include Git metadata for read-only/refusal cases. Acceptance class selectors must match actual tests, not report zero tests.

## Validation commands

- Baseline/focused: `TMPDIR="$PWD/.git/okf-test-tmp" python3 -m unittest discover -s .ai/scripts/tests -p test_install.py`.
- Slice acceptance: `python3 .ai/scripts/lifecycle.py converge knowledge/specifications/project-bootstrap.md` runs all six approved acceptance commands with repository-local scratch.
- Full gate once on the frozen candidate: `TMPDIR="$PWD/.git/okf-test-tmp" python3 -m unittest discover -s .ai/scripts/tests`.
- Records: `python3 .ai/scripts/okf.py affected` and `python3 .ai/scripts/okf.py records`.

Baseline: default system-temporary fixtures caused the preexisting hook E2E to fail; scratch.py explicitly rejects `/tmp`. The documented repository-local TMPDIR resolved it: all 36 installer tests passed. No source repair was required.

## OKF impact

Retain approved spec unchanged. Add a project-bootstrap capability, installation playbook, and delivery history with sources and exact executed evidence; append log entries using okf.py. Update indexes through tooling. Include lifecycle audit records.

## Risks and mitigations

Nearest-ancestor probing and negative tests prevent accidental nested repositories. Invocation-local Git initialization state limits the dirty-check exception. Preflight validates inputs before target creation. Isolated home snapshots and template sentinels verify locality and exclusions.

## Out of scope

Remote execution, package publishing, application scaffolding, global installation, and enabling autonomous operation by default.

## Open decisions

None. The plan is ready for implementation.
