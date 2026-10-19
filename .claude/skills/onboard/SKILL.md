---
name: onboard
description: Build draft architecture and capability context for an existing repository from cited implementation evidence, after scaffolding its tracked-file inventory.
---

Use when the user requests brownfield onboarding. Run `python3 .ai/scripts/okf.py onboard` in the installed repository. It keeps existing documents and creates only absent draft inventories; it executes no repository code. Candidate paths do not establish runtime architecture, passing tests or shipped behavior.

Inspect the cited source/configuration and tests with the repository's bounded file tools. Draft architecture and capability prose with claim-level citations to `sources[].resource`; distinguish observed implementation from documentation and unexecuted tests. Keep `status: draft` and `evidence: project-documentation` until stronger evidence exists. Preserve adopter-authored content; propose changes to existing documents within the user's request.

Request human approval before establishing structured living requirements or calling onboarding complete. Use a capability namespace and `## Requirements` with stable namespaced IDs only for an explicitly drafted, approved baseline. Do not invent requirements from filenames or automatically convert legacy prose.

For subsequent changes, load the delta contract with `python3 .ai/scripts/okf.py show .ai/lifecycle.md --section "Brownfield deltas"`. Keep unchanged scenarios, approve the delta and plan before coding, preview the merge, apply before Verify, and retain the spec and lifecycle receipt as history.
