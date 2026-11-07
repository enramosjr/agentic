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
Forced Windows cleanup retains member process handles before requesting
termination and waits for those handles before certifying closure. A changed
membership snapshot fails closed. A zero Job active count alone is not a process
termination witness; see Microsoft's [TerminateProcess completion semantics](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess).
Review-record reads retry brief Windows sharing denials for a bounded interval;
an unreadable or invalid record still blocks recovery.

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

CLI standard streams use UTF-8 on both platforms, including when the invoking
environment selects a legacy encoding. This keeps captured document bodies and
Unicode diagnostic paths consistent with the tools' UTF-8 subprocess decoding.

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
Cross-platform parser fixtures isolate the modules' platform view without changing
`pathlib`'s host OS. Process-metadata tests wait for the child to report readiness
before asserting its actual parent, birth identity, and exact argument spelling.
Synthetic launcher fixtures also control the current process birth, so their
ancestry checks do not depend on host uptime.
Recovery policy tests advance their clock only after the real child publishes
readiness; separate CLI tests retain actual deadline and process-tree assertions.
Concurrency tests use peer readiness rather than assuming startup overlaps a short
sleep. Child completion checks include birth identity, so a reused PID cannot
falsely report a surviving owned child.
Cancellation timing starts at the observed child failure, excluding interpreter
startup. Chat fixtures renew acknowledgements until a heartbeat and real child
output are observed, then test acknowledgement loss with the actual lease unchanged.
Detached-check fixtures observe the actual command before killing a live check,
and retain supervisor birth identity for cleanup. Recovery fixtures wait for the
registered wrapper and borrower receipt to finish, rather than treating command
exit alone as permission to recover a still-live owner.
Autonomy recovery fixtures publish child birth identities atomically; a recycled
PID does not count as the previous child surviving. Interruption/charge tests
wait for actual agent readiness before killing the campaign owner, with separate
startup allowance and unchanged no-relaunch/full-reservation charge assertions.
Windows source snapshots retry only Git diff's observed `mmap failed: Invalid
argument` exit 128, at most three reads. Each retry executes Git again; a failed
snapshot never counts as progress. Persistent mapping failures, other errors and
mutating commands still fail normally, retaining their diagnostics. Git for
Windows' [mapping adapter](https://github.com/git-for-windows/git/blob/main/compat/win32mmap.c)
reports native mapping failures as `EINVAL`; concurrent file publication is one
possible trigger, rather than a proven diagnosis for every such error.
Background diff/status snapshots and advisory audits disable Git's optional index
refresh, preventing readers from contending with a worker's `git add`. Mandatory
writer locks remain required. This follows Git's documented
[background-operation locking guidance](https://git-scm.com/docs/git).

The installer creates relative skill links with native separators and compares
their normalized target spelling. Scratch checks resolve dangling junctions on
Python 3.9 before accepting a disk location. Evaluation supervisors publish a
timeout result even when their deadline expires before launch authorization.

## Verification

Use the interpreter available in the shell (`python`, `py -3`, or its full path).
Focused tests guide repairs. Run an individual bounded segment locally with:

```text
python .ai/scripts/run_tests.py -j 4 --shard 1/8
```

Set `AGENTIC_TEST_PROGRESS=1` in the shell environment to print each test class's
start and completion during a long run. The inventory and final verdict are unchanged.
`--shard I/N` selects test methods deterministically, so large classes are divided
too. The union of shards 1 through N is the full inventory, with each test assigned
once. Invalid or empty shards, worker crashes and executed-count mismatches fail.
Preflights and segments run independently; the final summary waits for both.
Set `AGENTIC_TEST_RESUME` to a file path to make an interrupted run resumable: classes
that already passed on the same tree and shard are skipped; changed inputs or a
different shard invalidate that evidence.

The `Framework parity` CI workflow runs eight parallel segments for each Windows
and Linux / Python 3.9 and 3.15 variant, with full repository history. Each regression
segment has a 15-minute job limit. Repair feedback uses the failing tests or segment;
the integrated gate is the complete segmented matrix on a frozen candidate.
Both native Windows preflights must pass before Qualification succeeds.
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

The always-run `Qualification` summary succeeds only when both preflights and all
32 regression segments succeed. Failed, canceled, missing or skipped dependencies
prevent a green summary. Default-branch required checks use the successful names
`Qualification`, `Windows preflight / Python 3.9` and `Windows preflight / Python 3.15`.
Require an up-to-date branch and retain the existing pull-request and branch-safety
rules. Record the candidate SHA, completed workflow URL, and ruleset readback in
the delivery evidence; a submitted or skipped matrix is not a passing baseline.
