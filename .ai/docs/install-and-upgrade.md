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

All scripts, roles, skills and hook settings are project-local. Codex requires
trusting the project's .codex layer and reviewing hooks with `/hooks`; copying
files does not activate trust. Global agent settings remain unchanged.

The installed [README](../README.md) and references are part of .ai/ and are
copied with the kit. They do not require the source project's root README or
knowledge documents. A successful installation followed by --check reports
`up to date`. Exit 2 refuses invalid inputs; exit 1 reports drift, conflicts or
I/O failure. No installation creates a commit or starts an autonomous driver.
