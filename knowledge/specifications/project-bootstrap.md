---
type: Specification
title: One-command project bootstrap
description: Approved and implemented contract for installing the complete AGENTIC workflow into existing or new project folders.
tags: [spec, bootstrap, installation]
status: stable
evidence: project-documentation
generated: { by: agent/gpt-6, at: 2026-10-19T19:18:26Z }
sources:
  - id: ai-scripts-install-py
    resource: ../../.ai/scripts/install.py
  - id: ai-scripts-tests-test-install-py
    resource: ../../.ai/scripts/tests/test_install.py
  - id: readme-md
    resource: ../../README.md
verified: { by: "process:python3 .ai/scripts/lifecycle.py reuse framework-regression", at: 2026-10-19T19:43:08Z }
---

# Spec: One-command project bootstrap

## Problem and outcome

AGENTIC is a project-local workflow and management framework. The current installer already copies the complete kit and merges adopter settings, but requires an existing Git worktree root. The README instead describes manual copying. One documented command should bootstrap an existing project or a new folder.

Current behavior is evidenced by `.ai/scripts/install.py` (KIT, install, main), `.ai/scripts/tests/test_install.py`, and README.md's Install section. This document describes proposed behavior, not a delivered feature.

## Users and scenarios

- A developer installs into an existing Git project without replacing its own instructions, settings, or knowledge.
- A developer starts with an existing folder without Git or a folder that does not exist yet.
- A developer reruns the command to update or check an installation.

## Requirements

- R1: The documented bootstrap command MUST be `python3 /path/to/agentic/.ai/scripts/install.py TARGET`, using a local AGENTIC checkout, for all supported target states without manual copying or agent selection flags.
- R2: For a missing target outside an existing Git worktree, installation MUST create the directory, initialize Git, install the complete kit, and initialize the project's ordinary knowledge bundle without making a commit.
- R3: For an existing directory outside a Git worktree, installation MUST initialize Git and preserve unrelated files, existing instruction text, adopter hook settings, and existing knowledge. An uncommitted preexisting instruction or hook file in this newly initialized repository MUST be mergeable without requiring `--force`; differing plain kit files MUST retain the existing conflict policy.
- R4: For an existing Git worktree root, installation MUST retain existing merge, conflict, dirty-path, manifest, and upgrade behavior. Targets inside a different worktree root, the template itself, and file targets MUST be refused without installing framework files or initializing a nested repository.
- R5: Installation MUST put framework rules, roles, personas, skills, hooks, management scripts, and knowledge inside TARGET. It MUST leave global agent configuration untouched and exclude the template's Git history, knowledge corpus, and local agent session state.
- R6: `--check` MUST remain read-only, including for missing and non-Git targets, and return a nonzero result when installation is absent. A successful bootstrap MUST permit an unchanged rerun, a passing installer check and records check, and an installed lifecycle hook that denies an untiered source edit.

## Acceptance

- R1: `python3 -m unittest discover -s .ai/scripts/tests -p test_install.py -k BootstrapDocumentationTests` passes by checking that the documented command invokes the supported CLI, documents both folder scenarios, and replaces manual-copy setup as the primary route.
- R2: `python3 -m unittest discover -s .ai/scripts/tests -p test_install.py -k BootstrapNewFolderTests` passes against real CLI invocations, including paths with spaces, asserting the target Git root, installed manifest and kit, initialized knowledge, and no commit.
- R3: `python3 -m unittest discover -s .ai/scripts/tests -p test_install.py -k BootstrapExistingFolderTests` passes against a populated non-Git folder, asserting preserved file bytes, merged instructions and hooks, retained knowledge, and existing plain-file conflict behavior.
- R4: `python3 -m unittest discover -s .ai/scripts/tests -p test_install.py` passes, including existing installer regressions and refusal cases for existing and missing targets beneath another Git worktree, template root, and file targets with before/after filesystem assertions.
- R5: `python3 -m unittest discover -s .ai/scripts/tests -p test_install.py -k BootstrapLocalityTests` passes with isolated fake agent home directories, asserting they are unchanged and that complete kit installation excludes template knowledge, Git history, and session files.
- R6: `python3 -m unittest discover -s .ai/scripts/tests -p test_install.py -k BootstrapWorkflowTests` passes, asserting no mutations in check mode for absent and non-Git targets and, after real bootstrap, an unchanged rerun, check exit 0, records exit 0, and the actual lifecycle-hook denial response.

## Constraints

- Python 3.9+ and Git remain the prerequisites; add no runtime dependencies or global package installation.
- Preserve the current CLI flags and manifest format.
- Do not create commits, configure remotes, or install software into agent applications.
- Keep Codex's documented trust and hook review step explicit; copying project configuration does not establish that an application activated it.

## Non-goals

- Remote download-and-execute installers, package registries, and global plugins.
- Application scaffolding, project-specific build configuration, or automatic architecture discovery.
- Enabling autonomous execution by default or changing lifecycle governance.

## Assumptions

- Automatic Git initialization is the default for folders outside existing worktrees, replacing a separate user setup step.
- Bootstrap creates the ordinary empty knowledge bundle; autonomous queue initialization remains an explicit subsequent action.
- A local source checkout is acceptable; the README will include its acquisition and the single bootstrap invocation.

## Open questions

None. The spec is ready for approval before planning.
