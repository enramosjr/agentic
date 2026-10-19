"""Consistency of the lifecycle across its documents, role registrations, skills and harness hooks."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))

import disk_tmp  # noqa: E402,F401
import lifecycle  # noqa: E402

PLACEHOLDER = re.compile(r"<|\bPATH\b|\bHEADING\b|\bNAME\b|X\.md|…|\.\.\.")
SHOW = re.compile(r"`(python3 \.ai/scripts/okf\.py show [^`]+)`")


def text(path: str) -> str:
    return (ROOT / path).read_text()


class Distribution(unittest.TestCase):
    def test_eval_and_installer_share_one_kit_list(self) -> None:  # installer R1
        import install
        import lifecycle_eval
        expected = ("AGENTS.md", "CLAUDE.md", ".ai/", ".claude/agents/", ".claude/skills/", ".claude/settings.json", ".codex/agents/", ".codex/hooks.json", ".cursor/hooks.json", ".agents/skills", "THIRD_PARTY_NOTICES.md")
        self.assertEqual(install.KIT, expected)
        self.assertIs(lifecycle_eval.COPY, install.KIT)
        names = install.plain_files(ROOT)
        self.assertTrue(names)
        for name in names:
            self.assertFalse(name.startswith(("knowledge/", ".claude/worktrees/")), name)
            self.assertNotIn("__pycache__", name)
            self.assertFalse(name.endswith(".pyc"), name)
            self.assertNotEqual(name, ".ai/install-manifest.json")
        with tempfile.TemporaryDirectory() as directory:
            source, work = Path(directory) / "template", Path(directory) / "eval"
            work.mkdir()
            sentinels = (".claude/worktrees/nested/private", ".claude/settings.local.json", ".ai/__pycache__/bad.pyc", ".ai/install-manifest.json")
            for name in (*sentinels, ".ai/scripts/keep.py", ".ai/tests/test.py", ".ai/evals/test.json", ".claude/skills/plan/SKILL.md"):
                p = source / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("fixture")
            self.assertTrue(set(sentinels).isdisjoint(install.kit_files(source)))
            with patch.object(lifecycle_eval, "ROOT", source):
                lifecycle_eval.prepare({"id": "distribution", "prompt": "Inspect the copied kit.",
                                        "expect": {"tier": ["L0"]}}, work)
            self.assertTrue((work / ".ai/scripts/keep.py").is_file())
            for name in (*sentinels, ".ai/tests/test.py", ".ai/evals/test.json"):
                self.assertFalse((work / name).exists(), name)

    def test_readme_and_playbook_document_the_installer(self) -> None:  # installer R12
        self.assertIn(".ai/scripts/install.py", text("README.md").split("## Quick start", 1)[1].split("\n## ", 1)[0])
        playbook = text("knowledge/playbooks/install-and-upgrade.md")
        for term in ("--check", "--force", "--no-knowledge", "conflict", "/hooks"):
            self.assertIn(term, playbook)
        self.assertRegex(text(".ai/VERSION"), r"^\d+\.\d+\.\d+\n$")


class RolesAndSkills(unittest.TestCase):
    def test_every_role_in_the_selection_table_is_registered_for_claude_and_codex(self) -> None:
        roles = set(re.findall(r"\(\.ai/agents/(\w+)\.md\)", text("AGENTS.md").split("### 2.3")[0]))
        self.assertEqual(roles, {"analyst", "planner", "implementer", "reviewer", "orchestrator"})
        for role in roles - {"orchestrator"}:
            self.assertTrue((ROOT / f".claude/agents/{role}.md").is_file(), role)
            self.assertTrue((ROOT / f".codex/agents/{role}.toml").is_file(), role)

    def test_codex_skills_are_a_symlink_to_the_claude_skills(self) -> None:
        link = ROOT / ".agents/skills"
        self.assertTrue(link.is_symlink(), ".agents/skills must be a symlink so there is one copy")
        self.assertEqual(link.resolve(), (ROOT / ".claude/skills").resolve())
        names = sorted(str(p.relative_to(link)) for p in link.rglob("SKILL.md"))
        self.assertEqual(names, ["debug/SKILL.md", "implement/SKILL.md", "onboard/SKILL.md", "plan/SKILL.md", "review/SKILL.md", "ship/SKILL.md", "spec/SKILL.md"])

    def test_skills_have_name_matching_directory_and_a_description(self) -> None:
        for path in (ROOT / ".claude/skills").rglob("SKILL.md"):
            front = text(str(path.relative_to(ROOT))).split("---")[1]
            self.assertIn(f"name: {path.parent.name}\n", front)
            self.assertRegex(front, r"description: \S")

    def test_semantic_lens_in_analyst_reviewer_and_skills(self) -> None:  # spec-analysis-convergence R7
        analyst, reviewer = text(".ai/agents/analyst.md"), text(".ai/agents/reviewer.md")
        for term in ("missing scenarios", "error paths", "contradictions", "terminology drift"):
            self.assertIn(term, analyst, term)
            self.assertIn(term, reviewer, term)
        self.assertIn("lifecycle.py analyze", analyst)
        self.assertIn("lifecycle.py analyze", text(".claude/skills/spec/SKILL.md"))
        passes = reviewer.split("## Passes", 1)[1].split("\n## ", 1)[0]
        for path, body in ((".ai/agents/reviewer.md#Passes", passes), (".claude/skills/review/SKILL.md", text(".claude/skills/review/SKILL.md"))):
            self.assertIn("lifecycle.py converge", body, path)
            self.assertIn("## Validation Reviewed", body, path)

    def test_every_documented_okf_show_command_resolves(self) -> None:
        sources = [*(ROOT / ".claude").rglob("*.md"), *(ROOT / ".codex/agents").glob("*.toml"), *(ROOT / ".ai").rglob("*.md"), ROOT / "AGENTS.md"]
        commands = {c for path in sources for c in SHOW.findall(path.read_text()) if not PLACEHOLDER.search(c)}
        self.assertGreater(len(commands), 10)
        for command in sorted(commands):
            result = subprocess.run(shlex.split(command), cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"{command}\n{result.stderr}")


class Relocation(unittest.TestCase):
    def test_agents_md_points_to_the_policy_and_the_policy_keeps_its_must_rules(self) -> None:
        agents, policy = text("AGENTS.md"), text(".ai/validation-policy.md")
        self.assertIn(".ai/validation-policy.md", agents)
        self.assertIn("MUST load it by section", agents)
        for rule in (
            "MUST NOT rerun an unchanged failing check",
            "`--max` below 300 s is a violation",
            "MUST be split before work continues",
            "MUST NOT satisfy §8.1 by adding tests whose only purpose is more evidence",
        ):
            self.assertIn(rule, policy)
            self.assertNotIn(rule, agents)



class AgentsBudget(unittest.TestCase):  # efficiency-pass R5
    BASELINES = ("9e13fce", "cc75e1a")  # AGENTS.md before reference material moved to .ai/agents-reference.md.
    NORMATIVE = re.compile(r"\b(?:MUST|SHOULD|MAY)\b")

    def baseline(self) -> str:
        bodies = []
        for rev in self.BASELINES:
            shown = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:AGENTS.md"], capture_output=True, text=True)
            if shown.returncode:
                self.skipTest(f"commit {rev} is not in this clone")
            bodies.append(shown.stdout)
        return "\n".join(bodies)

    @staticmethod
    def flat(body: str) -> str:
        return re.sub(r"\s+", " ", body)

    def test_agents_md_stays_below_its_cold_start_budget(self) -> None:
        self.assertLess(len(text("AGENTS.md").encode()), 30_000)

    def test_every_heading_survives(self) -> None:
        current = text("AGENTS.md").splitlines()
        for line in self.baseline().splitlines():
            if re.match(r"#{1,3} ", line):
                self.assertIn(line, current)

    def test_every_normative_sentence_survives_in_agents_md_or_a_linked_ai_doc(self) -> None:
        agents = text("AGENTS.md")
        linked = sorted(p for p in set(re.findall(r"\.ai/[\w./-]+\.md", agents)) if (ROOT / p).is_file())
        self.assertIn(".ai/agents-reference.md", linked)
        corpus = self.flat("\n".join([agents, *(text(path) for path in linked)]))
        missing = []
        for line in self.baseline().splitlines():
            line = re.sub(r"^\s*(?:>\s*)?(?:[-*]|\d+\.)?\s*", "", line)
            for sentence in re.split(r"(?<=\.)\s+", line):
                if self.NORMATIVE.search(sentence) and self.flat(sentence).strip() not in corpus:
                    missing.append(sentence)
        self.assertEqual(missing, [])


class Tiers(unittest.TestCase):
    def test_tier_definitions_agree_across_agents_lifecycle_and_script(self) -> None:
        for tier in lifecycle.TIERS:
            self.assertIn(f"**{tier}**", text("AGENTS.md"))
            self.assertRegex(text(".ai/lifecycle.md"), rf"\| {tier} ")
        self.assertEqual(set(lifecycle.REQUIRED), set(lifecycle.TIERS))

    def test_every_stage_the_script_gates_is_described_in_the_lifecycle(self) -> None:
        doc = text(".ai/lifecycle.md")
        for heading in ("Stage 0: Intent", "Stage 1: Plan", "Stage 3: Review", "Stage 4: Verify and sync", "Stage 5: Ship"):
            self.assertIn(f"## {heading}\n", doc)
        self.assertEqual(set(lifecycle.STAGES), {"intent", "plan", "review", "verify", "ship"})

    def test_the_committed_audit_record_is_documented(self) -> None:
        for path in (".ai/lifecycle.md", "knowledge/project/lifecycle.md"):
            self.assertIn("knowledge/history/lifecycle/", text(path), path)
            self.assertIn("lifecycle.py audit", text(path), path)

    def test_analyze_and_converge_are_documented(self) -> None:  # spec-analysis-convergence R8
        for path in (".ai/lifecycle.md", "knowledge/project/lifecycle.md", ".ai/validation-policy.md"):
            self.assertIn("lifecycle.py analyze", text(path), path)
            self.assertIn("lifecycle.py converge", text(path), path)
        self.assertIn("cites a passing converge run of an identical command on the current tree", text(".ai/validation-policy.md"))


class MechanicalDocs(unittest.TestCase):
    """Mechanical governance checks (ledger, reuse, scan-diff, sync-check) are documented and stdlib-only."""

    LIFECYCLE_COMMANDS = ("run", "reuse", "scan-diff")
    OKF_COMMANDS = ("sync-check",)
    STDLIB = {"__future__", "fnmatch", "hashlib", "json", "re", "shlex", "subprocess", "sys", "time", "pathlib", "typing"}

    def test_new_commands_documented_in_agents_and_lifecycle(self) -> None:  # mechanical-governance R32
        for command in self.LIFECYCLE_COMMANDS:
            result = subprocess.run([sys.executable, str(SCRIPTS / "lifecycle.py"), command, "--help"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"lifecycle.py {command} is not a subcommand: {result.stderr}")
        for command in self.OKF_COMMANDS:
            result = subprocess.run([sys.executable, str(SCRIPTS / "okf.py"), command, "--help"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"okf.py {command} is not a subcommand: {result.stderr}")
        for path in ("AGENTS.md", ".ai/lifecycle.md"):
            doc = text(path)
            for command in self.LIFECYCLE_COMMANDS:
                self.assertIn(f"lifecycle.py {command}", doc, f"{path} must document lifecycle.py {command}")
            for command in self.OKF_COMMANDS:
                self.assertIn(f"okf.py {command}", doc, f"{path} must document okf.py {command}")
            self.assertIn("stamp verified", doc, path)
            self.assertIn("--run", doc, path)
        agents = text("AGENTS.md")
        self.assertRegex(agents, r"(?s)### 8\.4.*lifecycle\.py reuse.*### 8\.5")
        self.assertRegex(agents, r"(?s)### 3\.1.*lifecycle\.py run.*## 4\.")

    def test_new_code_imports_only_stdlib(self) -> None:  # mechanical-governance R33
        for name in ("ledger.py", "scan.py"):
            source = text(f".ai/scripts/{name}")
            self.assertIn("sys.dont_write_bytecode = True", source, name)
            modules = set(re.findall(r"^(?:import|from) ([A-Za-z_][A-Za-z0-9_]*)", source, re.M))
            self.assertLessEqual(modules, self.STDLIB, f"{name} imports outside the standard library: {modules - self.STDLIB}")
        okf_source = text(".ai/scripts/okf.py")
        for module in ("ledger", "scan"):  # Tests copy okf.py into repositories that hold a fixed script subset.
            self.assertNotRegex(okf_source, rf"^(?:import|from) {module}\b", module)


class HarnessWiring(unittest.TestCase):
    def hooks(self, path: str) -> dict:
        return json.loads(text(path))["hooks"]

    def commands(self, entries: list) -> str:
        return json.dumps(entries)

    def test_claude_gates_edits_commits_and_session_start(self) -> None:
        hooks = self.hooks(".claude/settings.json")
        pre = [e for e in hooks["PreToolUse"] if "lifecycle.py" in self.commands([e])]
        self.assertTrue(any("Edit" in e["matcher"] and "Write" in e["matcher"] for e in pre))
        self.assertTrue(any(e["matcher"] == "Bash" for e in pre))
        self.assertIn("lifecycle.py", self.commands(hooks["SessionStart"]))

    def test_codex_gates_edits_commits_and_session_start(self) -> None:
        hooks = self.hooks(".codex/hooks.json")
        pre = [e for e in hooks["PreToolUse"] if "lifecycle.py" in self.commands([e])]
        self.assertTrue(any("apply_patch" in e["matcher"] for e in pre))
        self.assertTrue(any(e["matcher"] == "Bash" for e in pre))
        self.assertIn("lifecycle.py", self.commands(hooks["SessionStart"]))

    def test_cursor_gates_edits_shell_and_session_start(self) -> None:
        hooks = self.hooks(".cursor/hooks.json")
        for event in ("preToolUse", "beforeShellExecution", "sessionStart"):
            self.assertIn("lifecycle.py", self.commands(hooks[event]), event)


if __name__ == "__main__":
    unittest.main()
