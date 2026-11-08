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

## Framework source hygiene

Framework maintainers validate source with `python .ai/scripts/framework_policy.py`
before distribution. An explicit framework source must contain only its maintained
document inventory from `.agentic.json`; unregistered task paperwork or a self
knowledge bundle refuses installation before creating or changing the target.
This inventory is source metadata and is not exported to adopters. Reusable roles,
skills and test fixtures remain source assets; adopter lifecycle/OKF creation is
unchanged. AGENTIC's own planning and review stay in chat, not task files.
Use `--snapshot index` to inspect staged source and `--snapshot head` to inspect
the committed tree, each against its own document inventory. Framework publication
uses an ordinary checkout/index and the checked-out HEAD/current branch; pushes
must name an explicit remote and refspec. Unchecked refs and alternate Git
namespaces refuse rather than validating different content. Check out the branch
you intend to publish first. These restrictions do not change adopter governance.

## Native Windows and Codex

Install Python 3.9+ and Git for Windows. The Codex hooks use `commandWindows`
overrides with built-in Windows PowerShell; Bash and a `python3` alias are not
required. The launcher checks PATH, then standard Git for Windows and python.org
installation locations (including the Python install manager's pythoncore folders).
The launcher also honors `PYTHONHOME` for a custom Python installation.
For custom installation locations, add Python and Git to PATH before starting
Codex. Restart Codex after installing tools or changing PATH.

For interactive commands in these docs, use `python` or `py -3` in place of
`python3`, for example `python .ai/scripts/lifecycle.py status`. If neither is
on PATH, invoke the installed python.exe by its full path using PowerShell's `&`.
CLI entry points also discover standard Git for Windows installations when the
desktop PATH omits Git. Windows CLI streams use UTF-8, including redirected
output on older Python versions. Environment changes remain process-local.
Human repair hints use the running Python executable with PowerShell quoting.

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

The installer compares Windows read-only state rather than unsupported POSIX
permission bits. Repeated install/check is stable, and an authorized update can
replace an owned read-only file while retaining its original state if replacement
fails. Managed governance text uses canonical LF; adopter bytes outside the
managed block remain unchanged.

Pinned compatibility snapshots are protected by a narrow `.gitattributes` rule
in both source and installed projects, including `--no-knowledge` installs.
For a legacy framework checkout whose Git newline conversion changed those
snapshots, run `python .ai/scripts/tests/restore_baselines.py`. It verifies the
committed independent hashes and Git identities before repairing only newline
conversion. Other edits are refused; pins are never regenerated or weakened.

Framework maintainers edit canonical stage skills under `.claude/skills/`, then
run `python .ai/scripts/install.py --sync-source-skills`. This refreshes the
generated `.agents/skills/` directory without requiring native symlink privileges.
Use `--sync-source-skills --check` for a read-only drift check. Source synchronization
requires the framework marker and refuses unexpected aliases escaping the checkout.
Adopter installation still chooses a supported directory link or exact copies.

See [cross-platform runtime and verification](windows-runtime.md) for process,
review and full-gate contracts.

The installed [README](../README.md) and references are part of .ai/ and are
copied with the kit. They do not require the source project's root README or
knowledge documents. A successful installation followed by --check reports
`up to date`. Exit 2 refuses invalid inputs; exit 1 reports drift, conflicts or
I/O failure. No installation creates a commit or starts an autonomous driver.
