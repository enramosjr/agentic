---
type: Capability
title: Project-local bootstrap
description: Install the complete AGENTIC workflow into existing or new project folders.
tags: []
status: stable
evidence: implementation-and-current-specifications
generated: { by: agent/gpt-6, at: 2026-10-19T19:26:24Z }
sources:
  - id: ai-scripts-install-py
    resource: ../../.ai/scripts/install.py
  - id: ai-scripts-tests-test-install-py
    resource: ../../.ai/scripts/tests/test_install.py
  - id: readme-md
    resource: ../../README.md
verified: { by: "process:python3 .ai/scripts/lifecycle.py reuse framework-regression", at: 2026-10-19T19:43:08Z }
---

# Project-local bootstrap

## Behavior

`python3 /path/to/agentic/.ai/scripts/install.py TARGET` installs the complete workflow and management kit inside TARGET. Missing directories are created and non-Git folders get a new repository without a commit or remote. Existing Git targets must be worktree roots; nested targets, bare repositories, malformed metadata, and file targets are refused.

The installer preflights framework version, manifest, hook JSON, instruction markers, and destination safety before creating a project. It merges instructions and hooks, retains existing knowledge, and preserves conflicting adopter-owned plain files with exit 1. Existing Git projects keep dirty-path protection; only repositories created in the current invocation skip that check.

Framework roles, personas, skills, hooks, governance, and management tooling remain project-local. Framework knowledge, Git history, session state, and global agent configuration are excluded. The default knowledge skeleton does not enable autonomous execution. Codex still requires project trust and hook review.

`--check` is read-only, including missing/non-Git targets. A completed installation can be rerun unchanged and checked using the same source checkout. CLI flags and format-1 ownership manifests retain their existing meanings.

## Requirements and evidence

This capability implements R1–R6 in [the approved bootstrap specification](../specifications/project-bootstrap.md). Acceptance runs exercise the public CLI, compare adopter bytes and global snapshots, verify installed records, and assert actual lifecycle-hook denial. Exact command outcomes are recorded in [delivery evidence](../history/project-bootstrap.md).
