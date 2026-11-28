# ADR 0013: The framework source is excluded from its own artifact workflow

- **Status:** Proposed (retroactive record of implemented behavior; pending maintainer acceptance)
- **Recorded:** 2026-11-27
- **RFC:** [0001 §3.3](../0001-agentic.md#33-repository-identity)

## Context

AGENTIC builds tooling for other projects. Early history shows the framework
running its own adopter workflow on itself: specs, plans, review reports,
lifecycle records and a `knowledge/` bundle. That task paperwork then leaked into
the distributed kit and into adopters, and it confused "documentation of the
product" with "records of one change to the product" (see commits such as
`Delete knowledge/history/lifecycle directory` and
`Keep framework task plans and specifications local`).

## Decision

- Repository identity is explicit: `.agentic.json` `repository_kind: framework`.
  An unknown or invalid identity grants no exemption.
- In framework source, intent, plans, reviews and verification stay **in
  chat**. Agents MUST NOT create self-task specs, plans, review or verification
  reports, `knowledge/`, lifecycle records or lesson records anywhere, including
  ignored paths and Git scratch. Agents do not invoke artifact-producing
  lifecycle stages. Checks are run directly.
- `.agentic.json` `source_documents` is an explicit inventory of maintained
  product documents. Any other document, a `knowledge/` or `docs/` tree, or
  lifecycle JSON is refused.
- `framework_policy.py` enforces this in three places: CI
  (`--snapshot head`), the installer preflight, and the edit hook.
- Correctness, test-first work, independent review and explicit publication
  authorization still apply to framework changes.

## Consequences

- The distributed kit contains only product assets, and installs start with an
  empty adopter bundle.
- The framework does not "dogfood" its artifact workflow on itself. Its
  regression suite and scripted evaluations exercise that workflow in fixture
  repositories instead.
- Adding a maintained document (such as this RFC and its ADRs) requires
  registering it in `source_documents`.
- Design records live outside `knowledge/` and outside the installed `KIT`, in
  `rfc/`.

## Alternatives considered

- **Dogfooding the full workflow.** Rejected because it contaminates the kit and
  confuses product documentation with task records.
- **`.gitignore`-based exclusion.** Rejected because ignored files still leak
  through scratch and installer copies, and policy needs to fail closed.

## Evidence

`.agentic.json`, `.ai/scripts/framework_policy.py` (`FORBIDDEN`, `GUIDANCE`, `validate`,
`edit_problem`), `.ai/scripts/project_context.py`, `.ai/agents-reference.md` §Framework source,
`.ai/docs/install-and-upgrade.md` §Framework source hygiene, `.github/workflows/framework-parity.yml`
(`source_hygiene`), `.ai/scripts/tests/test_framework_policy.py`.

## Revisit when

The framework splits into separately versioned packages that could each adopt
the workflow without contaminating the distributed kit.
