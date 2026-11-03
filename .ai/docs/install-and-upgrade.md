# Install and upgrade the local kit

From a separate source checkout, run
`python3 /path/to/agentic/.ai/scripts/install.py TARGET`. The same command supports
an existing project and a new folder. Use the Git worktree root as TARGET.

Run the source installer's `--check TARGET` to detect drift without writes. Rerun
without --check to update. `--force` permits changes to dirty owned paths; it does
not overwrite an adopter conflict. Conflicting plain files are kept and reported
with exit 1. Commit, stash or explicitly reconcile changing paths before retrying.
Use `--no-knowledge` to suppress creation of the target knowledge bundle. Existing
knowledge is retained in either mode; source knowledge is never imported.

An installed source exports only the shared AGENTS.md managed block, excluding
its adopter instructions outside that block. Malformed source markers refuse
before target writes. Target instructions outside a valid block remain in place.
The manifest records the normalized governance hash and installed file hashes.

For nested hook upgrades, a prior manifest-owned command's literal tool-name
matcher can expand to the kit's strict superset without retaining redundant
dispatch. This applies only to identical complete single-command hook lists and
identical other group metadata in the same event. An already present identical
expanded group is retained once. Custom options, mixed or prompt hooks, unknown
regexes, non-subset matchers and unowned commands are preserved. Flat hooks retain
their existing merge rules; configuration is never rebuilt wholesale.

All scripts, roles, skills and hook settings are project-local. Codex requires
trusting the project's .codex layer and reviewing hooks with `/hooks`; copying
files does not activate trust. Global agent settings remain unchanged.

## Native Windows and Codex

Install Python 3.9+ and Git for Windows. The Codex hooks use `commandWindows`
overrides with built-in Windows PowerShell; Bash and a `python3` alias are not
required. The launcher checks PATH, then standard Git for Windows and python.org
installation locations (including the Python install manager's pythoncore folders).
For custom installation locations, add Python and Git to PATH before starting
Codex. Restart Codex after installing tools or changing PATH.

For interactive commands in these docs, use `python` or `py -3` in place of
`python3`, for example `python .ai/scripts/lifecycle.py status`. If neither is
on PATH, invoke the installed python.exe by its full path using PowerShell's `&`.
The hook launcher's PATH changes apply only to the hook and its child processes.

Run `python -m unittest discover -s .ai/scripts/tests -p test_windows_hooks.py`
in the framework source checkout to verify native launch, JSON forwarding and
real policy decisions from paths containing spaces and nested directories.
These native tests require Windows; on other platforms they are skipped.

Upgrades add Windows overrides to prior manifest-owned commands without changing
adopter timeouts or unrelated hooks. An existing custom `commandWindows` value
is retained. After updating, restart the Codex session and use `/hooks` to review
and trust the changed hooks. Test SessionStart and a shell operation in the new
session. A policy denial naming a lifecycle stage or replacement tool is expected
enforcement; a launch error is not. If Git reports dubious ownership, resolve
trust for that specific repository in the owning user's environment; do not
disable ownership checks globally.

The installed [README](../README.md) and references are part of .ai/ and are
copied with the kit. They do not require the source project's root README or
knowledge documents. A successful installation followed by --check reports
`up to date`. Exit 2 refuses invalid inputs; exit 1 reports drift, conflicts or
I/O failure. No installation creates a commit or starts an autonomous driver.
