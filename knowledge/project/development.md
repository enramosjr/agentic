---
type: Development Guide
title: Framework development and validation
description: Repository-local validation and governance checks for the installed framework.
tags: []
status: stable
evidence: project-documentation
generated: { by: agent/gpt-6, at: 2026-10-19T19:28:13Z }
sources:
  - id: agents-md
    resource: ../../AGENTS.md
  - id: ai-agents-implementer-md
    resource: ../../.ai/agents/implementer.md
  - id: ai-autonomous-execution-md
    resource: ../../.ai/autonomous-execution.md
  - id: ai-lifecycle-md
    resource: ../../.ai/lifecycle.md
  - id: ai-validation-policy-md
    resource: ../../.ai/validation-policy.md
  - id: ai-scripts-lifecycle-py
    resource: ../../.ai/scripts/lifecycle.py
  - id: ai-scripts-okf-py
    resource: ../../.ai/scripts/okf.py
  - id: ai-scripts-ledger-py
    resource: ../../.ai/scripts/ledger.py
  - id: ai-scripts-scan-py
    resource: ../../.ai/scripts/scan.py
  - id: ai-scripts-tests-pressure-agent-py
    resource: ../../.ai/scripts/tests/pressure_agent.py
  - id: ai-scripts-tests-test-brownfield-deltas-py
    resource: ../../.ai/scripts/tests/test_brownfield_deltas.py
  - id: ai-scripts-tests-test-learning-loop-py
    resource: ../../.ai/scripts/tests/test_learning_loop.py
  - id: ai-scripts-tests-test-ledger-py
    resource: ../../.ai/scripts/tests/test_ledger.py
  - id: ai-scripts-tests-test-lifecycle-py
    resource: ../../.ai/scripts/tests/test_lifecycle.py
  - id: ai-scripts-tests-test-lifecycle-conformance-py
    resource: ../../.ai/scripts/tests/test_lifecycle_conformance.py
  - id: ai-scripts-tests-test-lifecycle-eval-py
    resource: ../../.ai/scripts/tests/test_lifecycle_eval.py
  - id: ai-scripts-tests-test-okf-py
    resource: ../../.ai/scripts/tests/test_okf.py
  - id: ai-scripts-tests-test-scan-diff-py
    resource: ../../.ai/scripts/tests/test_scan_diff.py
  - id: ai-scripts-tests-test-sync-check-py
    resource: ../../.ai/scripts/tests/test_sync_check.py
  - id: readme-md
    resource: ../../README.md
verified: { by: "process:python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle_conformance.py", at: 2026-10-19T21:16:44Z }
---

# Framework development and validation

## Runtime and checks

The framework uses Python 3.9+ standard-library scripts and Git. There is no separate application build or dependency installation step. The regression suite tests framework behavior and integrations, not an adopter application's correctness.

From the framework repository root:

```sh
mkdir -p .git/okf-test-tmp
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.git/okf-test-tmp" python3 -m unittest discover -s .ai/scripts/tests
```

`python3 .ai/scripts/run_tests.py` runs the same tests with one process per test class (about four times faster; see [Run the script tests](../playbooks/run-script-tests.md)). Without `TMPDIR`, test modules move fixtures to `$XDG_CACHE_HOME/okf-tests` (default `~/.cache/okf-tests`) when the system temp dir is memory-backed.

Disk-backed repository scratch is required for workflow tests; lifecycle scratch rejects `/tmp`, `/var/tmp`, and memory filesystems. Disable bytecode generation so imported fixture tests do not add untracked cache files that fail the fixture's synchronization gate. The installer slice is selected with `-p test_install.py`. Bootstrap fixtures additionally bound Git discovery so scratch directories below the framework's Git metadata represent independent projects.

## Current governance verification

The current default branch integrated during bootstrap development adds the evidence ledger, reuse checks, added-line scanning, and mechanical OKF synchronization. Its source and regression modules are listed in this document's provenance; these are upstream base changes rather than new bootstrap scope.

Use `python3 .ai/scripts/lifecycle.py run LABEL -- CMD` to record a check and `python3 .ai/scripts/lifecycle.py reuse LABEL` to determine whether its passing evidence covers the current inputs. The ledger stores status and input identity without command output. `scan-diff` checks added lines for unfinished implementation patterns. At L2 and above, Verify requires current ledger evidence.

`python3 .ai/scripts/okf.py sync-check` checks changed-file documentation coverage, fresh verification, and a log update. Use `okf.py stamp verified PATH --run CMD` to execute the cited check and stamp only when it passes. `okf.py records` checks structure, index freshness, and whitespace. These checks complement the spec acceptance commands and the actual regression suite.

The lifecycle, autonomous execution, and implementer documents define the binding execution rules. Tests cover evidence reuse and persistence, lifecycle gates and conformance, script-agent evals, spec deltas, knowledge operations, learning, added-line scanning, and synchronization. [Bootstrap delivery evidence](../history/project-bootstrap.md) records only executed outcomes for this change.
