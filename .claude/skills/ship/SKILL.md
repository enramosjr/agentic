---
name: ship
description: Use when a reviewed change is ready to deliver. Freezes the candidate on the current base, confirms gate evidence, and offers PR, keep, or discard.
---

Run lifecycle Stage 5 (Ship).

For delta intent, `lifecycle.py merge SPEC` belongs before Verify, with a completed receipt and current convergence. If target changes invalidate that evidence during candidate preparation, resolve and repeat the affected checks before shipping; do not perform the initial delta fold after commit. See `python3 .ai/scripts/okf.py show .ai/lifecycle.md --section "Brownfield deltas"` for dry-run and interruption recovery.

1. Load it: `python3 .ai/scripts/okf.py show .ai/lifecycle.md --section "Stage 5: Ship"`.
2. Merge the current default branch into the candidate, then confirm the gate evidence still covers the head (`AGENTS.md` §8.4). Hooks deny `git commit` (other than `wip:`) and PR creation until `lifecycle.py stage verify` is recorded.
3. Offer the user the PR, keep, or discard options and act only on their choice. Never merge into the default branch.
4. Close the record: `python3 .ai/scripts/lifecycle.py stage ship`.
