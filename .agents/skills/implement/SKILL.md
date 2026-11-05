---
name: implement
description: Use when executing an approved plan or making a bounded code change. Enforces test-first work, minimal edits, focused checks, and OKF sync.
---

Run lifecycle Stage 2 (Implement) and Stage 4 (Verify and sync).

1. Confirm the gate: `python3 .ai/scripts/lifecycle.py gate implement`. Hooks deny source edits until it passes.
2. Load the role: `python3 .ai/scripts/okf.py show .ai/agents/implementer.md --section Contract --section Execution` and the test rules: `python3 .ai/scripts/okf.py show AGENTS.md --section "8.6 Test-first and root cause"`.
3. Work on an isolated branch or worktree at L2 and above.
4. Start every bug fix from a failing reproduction: `lifecycle.py redgreen red -- <test command>`. After the fix: `lifecycle.py redgreen green -- <same command>`. Write new logic test-first.
5. Run the narrowest focused check per step. Run the slice E2E once when the slice is complete (§8.4).
6. Finish with `okf.py affected`, the needed doc updates, and `okf.py log`. At L1–L3 close a retrospective with `lifecycle.py retrospect --lessons 1 2` for captured lessons with nonblank evidence, or `lifecycle.py retrospect --no-new-lessons REASON`. Then run `lifecycle.py stage verify --note "<commands and outcomes>"` after review (L2). Report the retrospective outcome at delivery; retrieved observations remain advisory.
