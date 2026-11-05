---
name: spec
description: Use before planning or coding any new or changed behavior, contract, or ambiguous request (lifecycle tier L1 and above). Clarifies the request and writes a testable spec with acceptance criteria.
---

Run lifecycle Stage 0 (Intent).

For an existing capability, use stable namespaced IDs and a delta with target metadata, Added/Modified/Removed requirements and an approval-bound `## Target baseline` mirror/pins. Inspect the contract with `python3 .ai/scripts/okf.py show .ai/lifecycle.md --section "Brownfield deltas"`. An unstructured legacy capability needs an explicitly drafted and approved baseline first; do not infer or convert it automatically.

1. Declare the tier and persona: `python3 .ai/scripts/lifecycle.py tier L2 --reason "<why>" --kind feature` (`AGENTS.md` §2.5).
2. Load the stage: `python3 .ai/scripts/okf.py show .ai/lifecycle.md --section "Stage 0: Intent"` and the role: `python3 .ai/scripts/okf.py show .ai/agents/analyst.md --section Contract --section Process --section "Spec structure"`.
3. At L1 write the three-line intent note and record it with `lifecycle.py stage intent --note "<goal; success check; assumptions>"`. At L2 and above delegate to the `analyst` subagent, relay its batched questions with recommended defaults to the user, and persist the spec with `okf.py new specifications/<slug>.md --type Specification --status draft --evidence project-documentation ...`.
4. Run `lifecycle.py analyze knowledge/specifications/<slug>.md` and fix every Critical or High finding, then `lifecycle.py trace knowledge/specifications/<slug>.md`, then after the user approves it, `lifecycle.py stage intent --ref <spec> --approved-by human:<id>`. The approval MUST come from a user message.
5. Do not plan or edit code until the stage is recorded.
