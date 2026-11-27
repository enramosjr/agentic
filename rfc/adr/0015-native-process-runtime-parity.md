# ADR 0015: Native process primitives for Windows and Linux parity

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §15.4](../0001-agentic.md#154-windows-and-linux-parity)

## Context

Supervisors, detached checks, validation jobs, leases and review capture all
depend on knowing whether a process is alive, who owns it and whether its
descendants are gone. POSIX process groups do not exist on Windows. PIDs are
reused, so a bare PID cannot safely authorize recovery of ownership. Many
adopters and maintainers work on native Windows.

## Decision

- `process_runtime.py` is the single source of process identity, liveness,
  ancestry and locking.
- **Linux** uses process groups and kernel birth identity.
- **Windows** identity includes creation time. Children start suspended until
  they are assigned to an owned kill-on-close Job and their ownership is
  published. Forced cleanup keeps member handles and waits on them. A zero Job
  count alone is not treated as proof of termination, and a changed membership
  snapshot fails closed.
- Command-line streams use UTF-8 on both platforms. Recorded argv is never
  rewritten. Human hints use PowerShell syntax on Windows.
- Hooks have POSIX (`posix_hook.sh`) and native Windows launchers.
- CI runs the regression suite on Ubuntu and Windows with Python 3.9 and 3.15.

## Consequences

- One set of commands and evidence rules works on both platforms.
- Recovery cannot be authorized by an exited process or a reused PID.
- There is substantial platform-specific code and test surface (sharded CI).
- Opt-in bound native review still needs a Linux `/proc` launcher, so that
  parity gap remains open ([ADR 0017](0017-opt-in-bound-native-review.md)).

## Alternatives considered

- **Linux-only support** (WSL on Windows). Rejected because native Windows Codex
  and Claude Code users would be unsupported.
- **PID-only bookkeeping.** Rejected because PID reuse makes it unsafe.
- **Third-party process libraries.** Rejected under the stdlib-only constraint
  ([ADR 0005](0005-project-local-stdlib-kit.md)).

## Evidence

`.ai/scripts/process_runtime.py`, `.ai/scripts/posix_hook.sh`, `.ai/docs/windows-runtime.md`,
`.ai/scripts/tests/test_windows_*.py`, `.github/workflows/framework-parity.yml`.

## Revisit when

macOS-native support is required, or the minimum Python version gains
equivalent cross-platform primitives.
