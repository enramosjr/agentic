# ADR 0005: A project-local, standard-library-only kit installed by copy and merge

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §14](../0001-agentic.md#14-distribution-and-installation)

## Context

Hooks run on every tool call and must start fast and never fail because a
dependency is missing. Adopters run many languages, and many cannot or will not
add a package manager, a global install, or network access to their agent
environment. Global agent settings are personal and shared across projects.

## Decision

- All kit tooling is Python 3.9+ using only the standard library. Optional
  dependencies (cryptography, cloud SDKs, Node) are limited to the
  `deploy/authority/` source package, which is not installed into adopters.
- `install.py TARGET`, run from a separate source checkout, copies an explicit
  `KIT` list into the target: `AGENTS.md`, `CLAUDE.md`, `.ai/`, adapter files
  and skills, and `THIRD_PARTY_NOTICES.md`. The same command creates or updates.
- Installation merges rather than overwrites:
  - `AGENTS.md` has a managed block between
    `<!-- agent-governance-kit:begin/end -->`.
  - Hook settings are merged entry by entry.
  - Conflicting adopter files are kept and reported with exit 1.
  - Dirty owned paths need `--force`, which still preserves conflicts.
  - A manifest records hashes for drift detection (`--check`).
- Nothing global is modified. No commit or remote is created.

## Consequences

- Each project pins its own kit version and can be inspected and diffed.
- Upgrades are reruns of the installer. Drift is visible.
- Copies mean every project must be updated individually.
- The stdlib-only rule limits implementation choices (for example no YAML
  library and no cryptography in the core kit), so the code carries its own
  minimal parsers.

## Alternatives considered

- **A PyPI or npm package.** Rejected because it adds a package manager,
  version resolution and a network dependency to the hook path.
- **Global installation.** Rejected because it changes behavior across
  unrelated projects and makes the governing version invisible in the repo.
- **A Git submodule.** Rejected because it makes adopters manage submodules and
  cannot merge adopter hook settings.

## Evidence

`.ai/scripts/install.py` (`KIT`, `MANIFEST`, `BEGIN`/`END`), `.ai/docs/install-and-upgrade.md`,
`.ai/scripts/tests/test_install.py`, `.github/workflows/framework-parity.yml` (Python 3.9 and 3.15).

## Revisit when

Python 3.9 support is dropped, or adopters require signed release artifacts.
