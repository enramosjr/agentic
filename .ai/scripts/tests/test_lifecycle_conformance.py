"""Consistency of the lifecycle across its documents, role registrations, skills and harness hooks."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))

import lifecycle  # noqa: E402

PLACEHOLDER = re.compile(r"<|\bPATH\b|\bHEADING\b|\bNAME\b|X\.md|…|\.\.\.")
SHOW = re.compile(r"`(python3 \.ai/scripts/okf\.py show [^`]+)`")


def text(path: str) -> str:
    return (ROOT / path).read_text()


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
        self.assertEqual(names, ["debug/SKILL.md", "implement/SKILL.md", "plan/SKILL.md", "review/SKILL.md", "ship/SKILL.md", "spec/SKILL.md"])

    def test_skills_have_name_matching_directory_and_a_description(self) -> None:
        for path in (ROOT / ".claude/skills").rglob("SKILL.md"):
            front = text(str(path.relative_to(ROOT))).split("---")[1]
            self.assertIn(f"name: {path.parent.name}\n", front)
            self.assertRegex(front, r"description: \S")

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

    def test_agents_md_stays_below_its_cold_start_budget(self) -> None:
        self.assertLess(len(text("AGENTS.md").encode()), 46_000)


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
