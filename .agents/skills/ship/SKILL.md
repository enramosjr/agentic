---
name: ship
description: Use when a reviewed change is ready to deliver. Freezes the candidate on the current base, confirms gate evidence, and follows the authorized PR, keep, or discard choice.
---

Run lifecycle Stage 5 (Ship).

For delta intent, `lifecycle.py merge SPEC` belongs before Verify, with a completed receipt and current convergence. If target changes invalidate that evidence during candidate preparation, resolve and repeat the affected checks before shipping; do not perform the initial delta fold after commit. See `python3 .ai/scripts/okf.py show .ai/lifecycle.md --section "Brownfield deltas"` for dry-run and interruption recovery.

1. Load it: `python3 .ai/scripts/okf.py show .ai/lifecycle.md --section "Stage 5: Ship"`.
2. Merge the current default branch into the candidate, then confirm the gate evidence still covers the head (`AGENTS.md` §8.4). Hooks deny `git commit` (other than `wip:`) and PR creation until `lifecycle.py stage verify` is recorded.
3. Reuse the user's existing explicit PR, keep, or discard choice within its authorized scope. If no choice exists, offer those options; ask only for missing or expanded scope. Confirm deletion. Publishing draft specifications or plans does not approve implementation. Never merge into the default branch.
4. Before external publication, inspect outgoing commits and files, remote destination, target branch and prepared PR update against that authorization. Preserve source chat references in handoffs and distinguish direct user authorization from agent-authored instructions; never manufacture a human approval claim.
5. Complete the selected local checkpoint or commit, push and PR operations, then close the record with `python3 .ai/scripts/lifecycle.py stage ship`. On failure, report completed and remaining operations with commit, branch and PR identifiers, leave delivery incomplete and do not record Ship.
6. For publication failures, follow Stage 5's denial-recovery guidance: distinguish hook, sandbox, automatic-review and Git/remote failures using actual outputs; state missing raw evidence. Do not repeat unchanged denied requests, switch routes or weaken policy. Use only the interface's supported approval or exact-action override; `/approve` is TUI-specific. Existing approval and verification gates remain enforced.
7. Include the required L1–L3 retrospective outcome and source references in delivery. Verify and delivery guards require `lifecycle.py retrospect --lessons 1 2` or `lifecycle.py retrospect --no-new-lessons REASON`; a legacy Verify record does not bypass closure. Advisory observations do not become binding rules without human approval.
