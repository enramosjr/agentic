"""The scenario eval runner passes a lifecycle-compliant agent and fails a non-compliant one.

The "agents" here are scripted stand-ins, so these tests prove the harness fails closed.
Running real agents against the corpus is `lifecycle_eval.py run -- AGENT_COMMAND`.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import lifecycle_eval  # noqa: E402

COMPLIANT = r'''
import os, subprocess, sys
from pathlib import Path

SCENARIO = os.environ["LIFECYCLE_EVAL"]
SPEC_BODY = """
## Problem and outcome

Settle the requested change.

## Requirements

- R1: The change MUST behave as requested.

## Acceptance

- R1: `python3 -c "print(1)"` exits 0.

## Constraints

None.

## Non-goals

Anything else.

## Assumptions

None.

## Open questions

None. The spec is ready for planning.
"""

def run(*args):
    subprocess.run(list(args), check=True, capture_output=True)

def lc(*args):
    run(sys.executable, ".ai/scripts/lifecycle.py", *args)

def okf(*args):
    run(sys.executable, ".ai/scripts/okf.py", *args)

def edit(path, old, new):
    p = Path(path); p.write_text(p.read_text().replace(old, new))

def spec_plan_review_verify():
    if not Path("knowledge").is_dir():
        okf("init")
    okf("new", "specifications/change.md", "--type", "Specification", "--title", "Change", "--description", "The requested change.", "--status", "draft", "--evidence", "project-documentation")
    spec = Path("knowledge/specifications/change.md")
    spec.write_text(spec.read_text() + SPEC_BODY)
    lc("stage", "intent", "--ref", str(spec), "--approved-by", "human:eval")
    Path("plan.md").write_text("# Plan\n\n### Step 1: R1 make the change\n")
    lc("stage", "plan", "--ref", "plan.md")

def finish_l2():
    Path("review.md").write_text("# Review Report\n\n## Verdict\nApproved\n")
    lc("stage", "review", "--ref", "review.md")
    okf("log", "Specified and implemented the requested change.")
    okf("reindex")
    lc("stage", "verify", "--note", "okf.py records PASS; scripted checks PASS")

if SCENARIO == "typo-l0":
    lc("tier", "L0", "--reason", "comment typo")
    edit("app.py", "recieve", "receive")
elif SCENARIO == "bugfix-l1":
    lc("tier", "L1", "--reason", "one-line bug fix", "--kind", "bugfix")
    lc("stage", "intent", "--note", "add(2,3) must be 5; test_calc passes; no assumptions")
    lc("stage", "plan", "--note", "change a - b to a + b in calc.py")
    lc("redgreen", "red", "--", sys.executable, "-m", "unittest", "test_calc")
    edit("calc.py", "a - b", "a + b")
    lc("redgreen", "green", "--", sys.executable, "-m", "unittest", "test_calc")
    lc("stage", "verify", "--note", "python3 -m unittest test_calc: red then green")
elif SCENARIO == "feature-l2":
    lc("tier", "L2", "--reason", "new CLI flag is a user-visible contract", "--kind", "feature")
    spec_plan_review_verify()
    edit("cli.py", "print('hello')", "print('hello')  # --json handled")
    finish_l2()
elif SCENARIO == "escalation-l2":
    lc("tier", "L1", "--reason", "rename looks small")
    lc("tier", "L2", "--reason", "fetch is exported public API")
    spec_plan_review_verify()
    edit("api.py", "def fetch", "def get")
    finish_l2()
elif SCENARIO == "user-tier-held":
    lc("tier", "L2", "--reason", "the user asked for L2", "--user-set")
    spec_plan_review_verify()
    edit("util.py", "'Hi '", "'Hello, '")
    finish_l2()
elif SCENARIO == "queue-l3":
    lc("tier", "L3", "--reason", "queued objective")
    okf("new", "specifications/todo.md", "--type", "Specification", "--title", "Todo CLI", "--description", "Todo CLI spec.", "--status", "draft", "--evidence", "project-documentation")
    spec = Path("knowledge/specifications/todo.md")
    body = SPEC_BODY.replace("- R1: The change MUST behave as requested.", "- R1: add MUST store an item.\n- R2: list MUST print items.\n- R3: done MUST mark an item done.")
    body = body.replace("- R1: `python3 -c \"print(1)\"` exits 0.", "- R1: `python3 -c \"print(1)\"` exits 0.\n- R2: `python3 -c \"print(2)\"` exits 0.\n- R3: `python3 -c \"print(3)\"` exits 0.")
    spec.write_text(spec.read_text() + body)
    entries = subprocess.run([sys.executable, ".ai/scripts/lifecycle.py", "queue-from-spec", str(spec), "--group", "Todo"], check=True, capture_output=True, text=True).stdout
    queue = Path("knowledge/project/work-queue.md")
    queue.write_text(queue.read_text() + "\n" + entries)
    lc("stage", "intent", "--ref", str(spec), "--approved-by", "human:eval")
'''

NONCOMPLIANT = r'''
import os
from pathlib import Path

edits = {
    "typo-l0": ("app.py", "recieve", "receive"),
    "bugfix-l1": ("calc.py", "a - b", "a + b"),
    "feature-l2": ("cli.py", "print('hello')", "print('{}')"),
    "escalation-l2": ("api.py", "def fetch", "def get"),
    "user-tier-held": ("util.py", "'Hi '", "'Hello, '"),
}
name = os.environ["LIFECYCLE_EVAL"]
if name in edits:
    path, old, new = edits[name]
    p = Path(path); p.write_text(p.read_text().replace(old, new))
print("done")
'''

TIER_ONLY = r'''
import os, subprocess, sys
from pathlib import Path

# Declares a tier but skips the stages, the spec and the tests.
subprocess.run([sys.executable, ".ai/scripts/lifecycle.py", "tier", "L1", "--reason", "looks small"], check=True, capture_output=True)
edits = {
    "bugfix-l1": ("calc.py", "a - b", "a + b"),
    "feature-l2": ("cli.py", "print('hello')", "print('{}')"),
}
name = os.environ["LIFECYCLE_EVAL"]
if name in edits:
    path, old, new = edits[name]
    p = Path(path); p.write_text(p.read_text().replace(old, new))
'''


class EvalRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.scratch)

    def agent(self, source: str) -> list[str]:
        path = self.scratch / "agent.py"
        path.write_text(source)
        return [sys.executable, str(path)]

    def run_all(self, source: str) -> dict[str, list[str]]:
        agent = self.agent(source)
        return {s["id"]: lifecycle_eval.run_scenario(s, agent) for s in lifecycle_eval.load_scenarios()}

    def test_shipped_scenarios_are_valid_and_cover_every_tier(self) -> None:
        scenarios = lifecycle_eval.load_scenarios()
        self.assertGreaterEqual(len(scenarios), 6)
        tiers = {t for s in scenarios for t in s["expect"]["tier"]}
        self.assertEqual(tiers, {"L0", "L1", "L2", "L3"})

    def test_invalid_scenario_is_rejected(self) -> None:
        self.assertIn("expect.tier is required", lifecycle_eval.validate({"id": "x", "prompt": "p", "expect": {"stages": []}}))
        self.assertIn("unknown expect key 'bogus'", lifecycle_eval.validate({"id": "x", "prompt": "p", "expect": {"tier": ["L0"], "bogus": 1}}))

    def test_compliant_agent_passes_every_scenario(self) -> None:
        results = self.run_all(COMPLIANT)
        self.assertEqual({k: v for k, v in results.items() if v}, {})

    def test_changes_the_agent_committed_still_count_and_a_committed_forbidden_file_fails(self) -> None:
        scenario = next(s for s in lifecycle_eval.load_scenarios() if s["id"] == "bugfix-l1")
        committing = (
            "import subprocess, sys\nfrom pathlib import Path\n"
            "def lc(*a): subprocess.run([sys.executable, '.ai/scripts/lifecycle.py', *a], check=True, capture_output=True)\n"
            "lc('tier','L1','--reason','bug','--kind','bugfix')\nlc('stage','intent','--note','n')\nlc('stage','plan','--note','p')\n"
            "lc('redgreen','red','--',sys.executable,'-m','unittest','test_calc')\n"
            "Path('calc.py').write_text(Path('calc.py').read_text().replace('a - b','a + b'))\n"
            "Path('test_calc.py').write_text(Path('test_calc.py').read_text() + '# weakened\\n')\n"
            "lc('redgreen','green','--',sys.executable,'-m','unittest','test_calc')\nlc('stage','verify','--note','ok')\n"
            "subprocess.run(['git','-c','user.email=a@a','-c','user.name=a','commit','-qam','fix'], check=True)\n"
        )
        failures = lifecycle_eval.run_scenario(scenario, self.agent(committing))
        self.assertEqual(failures, ["'test_calc.py' changed but must not"])

    def test_agent_that_ignores_the_lifecycle_fails_every_scenario(self) -> None:
        results = self.run_all(NONCOMPLIANT)
        self.assertEqual(sorted(k for k, v in results.items() if not v), [])
        self.assertTrue(all("no lifecycle tier was ever declared" in v for v in results.values()))

    def test_agent_that_declares_a_tier_but_skips_the_work_fails(self) -> None:
        results = self.run_all(TIER_ONLY)
        self.assertTrue(any("no red-then-green evidence" in f for f in results["bugfix-l1"]))
        self.assertTrue(any("stage 'review' was not recorded" in f for f in results["feature-l2"]))
        self.assertTrue(any("lint-clean spec" in f for f in results["feature-l2"]))
        self.assertTrue(any("final tier L1" in f for f in results["feature-l2"]))
        self.assertTrue(results["typo-l0"], "an L1 declaration for a typo must not satisfy the L0 scenario")


if __name__ == "__main__":
    unittest.main()
