# Distributed AGENTIC tooling

This directory carries the project-local governance kit. Its documentation travels
with the scripts; the application's README and knowledge corpus remain independent.

## Quick start

Install into an existing project or a new folder from a separate source checkout:

```sh
python3 /path/to/agentic/.ai/scripts/install.py TARGET
```

Choose the target Git worktree root and quote paths containing spaces. Python 3.9+
and Git are required. The installer creates missing folders and Git metadata when
needed. It does not create a commit or configure a remote. An installed kit can
also be used as the source: only its managed governance body is exported.

## References

- [Install and upgrade](docs/install-and-upgrade.md): drift, conflicts and hooks.
- [Lifecycle](docs/lifecycle.md): stages, checks and committed audit evidence.
- [Learning contract](docs/learning-loop.md) and [workflow](docs/learning-loop-playbook.md).
- [Brownfield deltas](lifecycle.md#brownfield-deltas): approval-bound requirement changes.

Scripted-agent evaluations prove harness mechanics; they do not establish a real
model's qualification. A real-model baseline remains on hold until the project's
explicit qualification and supervision requirements are met. Installation does
not launch that qualification or authorize autonomous execution.

Run framework regression tests with disk-backed scratch via
`python3 .ai/scripts/lifecycle.py run governance-suite -- python3 .ai/scripts/run_tests.py -j 4`.
Application validation remains the adopting project's responsibility.
