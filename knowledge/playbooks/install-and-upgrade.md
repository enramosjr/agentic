---
type: Playbook
title: Bootstrap an adopter project
description: The canonical project-local installation and check procedure.
tags: []
status: stable
evidence: implementation-and-current-specifications
generated: { by: agent/gpt-6, at: 2026-10-19T19:26:24Z }
sources:
  - id: ai-scripts-install-py
    resource: ../../.ai/scripts/install.py
  - id: readme-md
    resource: ../../README.md
verified: { by: "process:python3 -m unittest discover -s .ai/scripts/tests -p test_install.py", at: 2026-10-19T21:20:27Z }
---

# Bootstrap an adopter project

## Install

Prerequisites: Python 3.9+, Git, and a local checkout of AGENTIC in a separate folder from the adopter.

```sh
git clone https://github.com/enramosjr/agentic.git /path/to/agentic
python3 /path/to/agentic/.ai/scripts/install.py TARGET
```

TARGET can be an existing Git worktree root, an existing non-Git folder, or a missing directory outside another worktree. Quote paths containing spaces. The installer creates directories and initializes Git when necessary, without commits or remotes. Installation and knowledge initialization are local to TARGET; no global agent setup is required.

Open TARGET in the chosen coding agent. Codex users must trust the local `.codex/` layer and review hooks using `/hooks`. Ask for a bounded change to begin the lifecycle. Autonomous queues remain opt-in through `python3 .ai/scripts/okf.py init --autonomous` from TARGET.

## Check and update

```sh
python3 /path/to/agentic/.ai/scripts/install.py --check TARGET
python3 /path/to/agentic/.ai/scripts/install.py TARGET
```

Check mode makes no writes and exits nonzero when bootstrap is absent or installation has drifted. The second command also updates installations using the source checkout. A matching installation reports `up to date`.

Exit 0 means success, 1 means drift/conflicts or I/O failure, and 2 means refused input. Conflicting adopter files are kept. In existing Git projects, commit/stash changing paths or use `--force` after review; this flag does not overwrite conflicts. Choose the worktree root rather than a nested folder. Repair malformed hook JSON, instruction markers, or Git metadata before retrying.

The optional `--no-knowledge` flag skips creating an adopter knowledge bundle. The primary bootstrap command creates it automatically.
