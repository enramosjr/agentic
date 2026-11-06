# Windows and Linux runtime parity

The framework uses native OS mechanisms behind the same user-facing commands and
evidence rules. Python 3.9+ and Git remain prerequisites. Codex hook configuration
uses its Windows command override; Linux retains its existing command strings.

`process_runtime.py` supplies native process identity, liveness, ancestry and
locking. Windows identity includes creation time, so an exited process or reused
PID cannot authorize ownership recovery. Windows children are suspended until
assigned to an owned kill-on-close Job and their ownership is published. Linux
continues to use process groups and kernel birth identity. Supervisors retain
independent deadlines, bounded output capture, real exit status and descendant
cleanup when their caller dies.

Lifecycle, detached checks, autonomous validation, artifact checks and native
review capture use those mechanisms. Review and Git routing preserve literal
PowerShell paths, executable names and environment selectors while rejecting
dynamic target spellings. The shell guard recognizes native PowerShell file
commands. Git namespace discovery retains supplied `safe.directory` entries but
strips configuration that could redirect the protected repository.
DOS short names and repository-root aliases use resolved repository identities;
shell directory spelling is retained while resolving traversal commands.

Evidence still records the actual declared and executed argv. On Windows, an
otherwise exact registered profile may use the active resolved Python executable;
other interpreter aliases, executables or options do not qualify. Human repair
hints use PowerShell invocation syntax; those hints do not rewrite recorded
commands. Immutable evidence and pinned compatibility snapshots retain their
hash checks.

Directory-junction tests exercise native alias escapes and retargeting without
administrator symlink privileges. Input fingerprints include native junction
targets so identical bytes at another target cannot reuse old evidence. Literal
Git transport tests retain names that the Windows filesystem itself cannot create,
alongside real native filesystem cases. Platform coverage is implemented with
equivalent assertions rather than disabling the corresponding capability.

Evaluation and autonomy tooling follow the same rule. Scenario fixtures are
written byte-exact with LF so pinned hashes hold. Behavior probes drain child
output on a thread, because Windows selectors cannot watch pipes. The live
observer locks its event file with `msvcrt`, recovery of interrupted attempts
clears read-only Git objects, and the autonomy driver retries a chat
acknowledgement that races its writer. Two evaluation tests are POSIX-only and
skip on Windows with a stated reason: hook deadline supervision uses
`signal.setitimer`, and the scripted CLI fixture is a shebang script. Tests with
short timing limits use longer limits on Windows, where interpreter startup takes
about a second.

## Verification

Use the interpreter available in the shell (`python`, `py -3`, or its full path).
Focused checks guide implementation; final parity requires the complete suite:

```text
python .ai/scripts/run_tests.py -j 4
```

Set `AGENTIC_TEST_PROGRESS=1` in the shell environment to print each test class's
start and completion during a long run. The inventory and final verdict are unchanged.
Set `AGENTIC_TEST_RESUME` to a file path to make an interrupted run resumable: classes
that already passed on exactly the same tree are skipped, and any edit reruns everything.

The `Framework parity` CI workflow runs that shared inventory on Windows and
Linux, on the supported Python floor and Python 3.15, with full repository history.
Both native Windows preflights must pass before the complete matrix starts.
The preflight retains individual failure traces and fails if any selected class fails.
Qualification fixtures write explicit UTF-8/LF bytes using APIs available on Python
3.9. Delta completion compares specification provenance through resolved paths,
including repositories opened through a directory junction or DOS short name.
The native missing-tool tests mask system-wide discovery roots after PowerShell
startup, so a hosted runner's installed launcher cannot satisfy an absent-tool case.
Detached-check fixtures wait for Windows to release inherited log handles before
removing their temporary directories; cleanup has a bounded deadline.
The installed-qualification test exercises an uncommitted upgrade and its actual
qualification commands; the installer also tests a new clone with pinned snapshots.
No platform is considered verified from startup-only checks or a submitted job.
Use completed command results for the candidate being delivered.

Default-branch required checks must use the exact successful job names from that
candidate: `Windows preflight / Python 3.9`, `Windows preflight / Python 3.15`,
`ubuntu-latest / Python 3.9`, `ubuntu-latest / Python 3.15`,
`windows-latest / Python 3.9`, and `windows-latest / Python 3.15`.
Require an up-to-date branch and retain the existing pull-request and branch-safety
rules. Record the candidate SHA, completed workflow URL, and ruleset readback in
the delivery evidence; a submitted or skipped matrix is not a passing baseline.
