# OKF Change Log

## 2026-10-19

- Initialized OKF bundle (`okf.py init`).
- Bootstrapped the bundle (okf.py init). Added spec and plan specifications/efficiency-pass(.md, -plan.md); playbooks/run-script-tests.md (run_tests.py, disk-backed test temp); project/harness-hooks.md (Cursor loads .claude hooks too; --skip-in-cursor; lifecycle hook fast path); project/agents-md-budget.md (AGENTS.md 45,982 -> 29,871 bytes, reference moved verbatim to .ai/agents-reference.md). Evidence: test_efficiency.py (10 tests) and test_lifecycle_conformance -k AgentsBudget pass; both fail against the previous code.
- Review of efficiency-pass recorded (specifications/efficiency-pass-review.md): Approved after fixing the Medium fast-path test gap; four Low items deferred as listed. Spec status set to stable.
- Full gate on the frozen efficiency-pass candidate: 'python3 -m unittest discover -s .ai/scripts/tests' -> 497 tests, 5 errors (pre-existing FileNotFoundError on template-only knowledge docs), 179 s; 'python3 .ai/scripts/run_tests.py' -> 497 tests, the same 5 ids, 46 s; converge R1-R5 PASS; okf.py records OK.
