# AGENTIC design records

This directory holds AGENTIC's design documentation for maintainers, reviewers
and prospective adopters. It is framework-source material. It is not part of the
installed kit, and `install.py` does not copy it into adopter projects.

| Document | Purpose |
|----------|---------|
| [RFC 0001: AGENTIC](0001-agentic.md) | A detailed description of the framework as implemented: lifecycle, tiers, enforcement, evidence, assurance, knowledge, autonomy, trusted CI, distribution, security and conformance profiles |
| [`adr/`](adr/) | Architecture Decision Records for the choices that shape the framework |

## Authority

[`AGENTS.md`](../AGENTS.md), the documents it declares binding, and the
implementation in [`.ai/scripts/`](../.ai/scripts/) are normative. These records
explain them. When they disagree, the records are wrong and must be amended.

## Decision records

The ADRs were reconstructed from the existing implementation and history, so
each one starts as *Proposed (retroactive)*. A maintainer accepts an ADR by
changing its status to `Accepted` with the date and approver. Later decisions
get the next number. An accepted ADR is superseded, not edited: write a new ADR
and mark the old one `Superseded by ADR NNNN`.

| ADR | Decision |
|-----|----------|
| [0001](adr/0001-enforce-lifecycle-with-hooks.md) | Enforce the lifecycle with harness hooks, not instructions |
| [0002](adr/0002-one-lifecycle-four-tiers.md) | One lifecycle, right-sized by four tiers |
| [0003](adr/0003-repository-as-memory-okf.md) | The repository is the memory: an OKF v0.2 knowledge bundle |
| [0004](adr/0004-vendor-neutral-governance-source.md) | One vendor-neutral governance source with thin harness adapters |
| [0005](adr/0005-project-local-stdlib-kit.md) | A project-local, standard-library-only kit installed by copy and merge |
| [0006](adr/0006-fingerprinted-evidence-ledger.md) | A fingerprinted evidence ledger with conservative reuse |
| [0007](adr/0007-living-requirements-assurance.md) | Living requirements with mechanical assurance; judgment is never evidence |
| [0008](adr/0008-approvals-are-recorded-claims.md) | Approvals are recorded claims; authentication belongs to a separate boundary |
| [0009](adr/0009-trusted-ci-separated-environments.md) | Trusted CI as three separated environments with an independent authority |
| [0010](adr/0010-structured-tools-over-shell.md) | Structured repository tools over raw shell |
| [0011](adr/0011-supervised-autonomy-driver.md) | Unattended work only through a supervised driver with fresh sessions and circuit breakers |
| [0012](adr/0012-one-pr-per-milestone.md) | One pull request per milestone; agents never merge the default branch |
| [0013](adr/0013-framework-source-chat-only.md) | The framework source is excluded from its own artifact workflow |
| [0014](adr/0014-human-gated-learning.md) | Human-gated learning: observations are advisory, rules require promotion |
| [0015](adr/0015-native-process-runtime-parity.md) | Native process primitives for Windows and Linux parity |
| [0016](adr/0016-hash-pinned-brownfield-deltas.md) | Brownfield requirement changes as hash-pinned deltas |
| [0017](adr/0017-opt-in-bound-native-review.md) | Mechanically bound native review is opt-in |

## Adding a document

Every Markdown file in this repository must be listed in `.agentic.json`
`source_documents`, or `framework_policy.py` and CI reject it. Register a new
RFC or ADR there in the same change.
