@AGENTS.md

## Claude Code specifics

The shell guard (`.ai/scripts/shell_guard.py`) denies `ls`, `find`, `cat`, `head`, `tail`, `sed`, `grep`, `rg`, heredocs and `echo >` for exploration and edits. Do not try them first.

- Read files with `Read` (`file_path`, `offset`, `limit`); edit with `Edit` and `Write`.
- Search and list with `python3 .ai/scripts/repo.py grep PATTERN [PATH ...] [--regex|-E] [-i] [-A/-B/-C N] [--count] [--glob G] [--under DIR]` and `repo.py files GLOB [--under DIR] [--depth N]`. Alternation needs `--regex` (or `-E`).
- Run `repo.py` and the other scripts from the repository root, or by absolute path. A relative `.ai/scripts/...` path breaks after a `cd`.
- A fresh worktree has no lifecycle tier: run `python3 .ai/scripts/lifecycle.py tier L0|L1|L2|L3 --reason TEXT` before the first source edit or commit. Resolving files git lists as conflicted needs no tier.
- Waiting: use `run_in_background` or `Monitor`, not a foreground `sleep`.
- Git commits need `user.name` and `user.email`; if `git commit` reports an unknown identity, tell the user instead of setting one.
