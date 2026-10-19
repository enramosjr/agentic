"""Efficiency-pass spec R1-R4 (knowledge/specifications/efficiency-pass.md)."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent
ROOT = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))

import disk_tmp  # noqa: E402,F401
import scratch  # noqa: E402

HEAVY = re.compile(r"\|\s+(okf|brownfield|learning)\s*$", re.M)


class Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    @staticmethod
    def clean_env() -> dict:
        return {k: v for k, v in os.environ.items() if k not in ("LIFECYCLE_GUARD", "OKF_AUTONOMOUS", "OKF_SHELL_GUARD")}

    def run_script(self, args: list, payload: dict, *flags: str, **env: str) -> subprocess.CompletedProcess:
        environment = self.clean_env()
        environment.update(CLAUDE_PROJECT_DIR="", **env)
        result = subprocess.run([sys.executable, *flags, *args], input=json.dumps(payload), cwd=self.repo,
                                capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def cursor_shell(self, command: str) -> dict:
        return {"hook_event_name": "preToolUse", "tool_name": "Shell", "tool_input": {"command": command},
                "cursor_version": "1", "workspace_roots": [str(self.repo)]}

    def claude_shell(self, command: str) -> dict:
        return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(self.repo)}


class DiskTmp(unittest.TestCase):  # R1
    PROBE = ("import sys; sys.path[:0] = [{tests!r}, {scripts!r}]; import disk_tmp, scratch, tempfile; "
             "from pathlib import Path; scratch.require_disk(Path(tempfile.mkdtemp())); print(tempfile.gettempdir())")

    def probe(self, tmpdir: str) -> str:
        code = self.PROBE.format(tests=str(TESTS), scripts=str(SCRIPTS))
        env = {**os.environ, "TMPDIR": tmpdir}
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd="/")
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_rejected_system_temp_moves_to_disk_outside_any_repository(self) -> None:
        chosen = self.probe("/tmp")
        self.assertFalse(chosen.startswith("/tmp"), chosen)
        scratch.require_disk(Path(chosen))
        outside = subprocess.run(["git", "-C", chosen, "rev-parse", "--git-dir"], capture_output=True, text=True)
        self.assertNotEqual(outside.returncode, 0, f"{chosen} is inside a git repository")

    def test_accepted_temp_is_left_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as accepted:
            self.assertEqual(self.probe(accepted), str(Path(accepted)))


class HookDedupe(Fixture):  # R2
    GUARD = [str(SCRIPTS / "shell_guard.py"), "--skip-in-cursor"]
    LIFECYCLE = [str(SCRIPTS / "lifecycle.py"), "hook", "--skip-in-cursor"]

    def with_cursor_hooks(self) -> None:
        (self.repo / ".cursor").mkdir()
        (self.repo / ".cursor/hooks.json").write_text('{"version": 1, "hooks": {}}')

    def test_flagged_hooks_stand_down_under_cursor_when_cursor_hooks_exist(self) -> None:
        self.with_cursor_hooks()
        self.assertEqual(self.run_script(self.GUARD, self.cursor_shell("cat README.md")).stdout, "")
        self.assertEqual(self.run_script(self.LIFECYCLE, self.cursor_shell('git commit -m "feat: x"')).stdout, "")
        session = {"hook_event_name": "sessionStart", "cursor_version": "1", "workspace_roots": [str(self.repo)]}
        self.assertEqual(self.run_script(self.LIFECYCLE, session).stdout, "")

    def denied(self, output: str) -> bool:
        decision = json.loads(output)
        return "deny" in (decision.get("permission"), decision.get("hookSpecificOutput", {}).get("permissionDecision"))

    def test_flagged_hooks_still_decide_for_claude_code(self) -> None:
        self.with_cursor_hooks()
        self.assertTrue(self.denied(self.run_script(self.GUARD, self.claude_shell("cat README.md")).stdout))
        self.assertTrue(self.denied(self.run_script(self.LIFECYCLE, self.claude_shell('git commit -m "feat: x"')).stdout))

    def test_flagged_hooks_still_decide_under_cursor_without_cursor_hooks(self) -> None:
        self.assertTrue(self.denied(self.run_script(self.GUARD, self.cursor_shell("cat README.md")).stdout))
        self.assertTrue(self.denied(self.run_script(self.LIFECYCLE, self.cursor_shell('git commit -m "feat: x"')).stdout))

    def test_only_the_claude_registrations_carry_the_flag(self) -> None:
        def commands(path: str) -> list:
            found = []
            def walk(node: object) -> None:
                if isinstance(node, dict):
                    found.extend([node["command"]] if isinstance(node.get("command"), str) else [])
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)
            walk(json.loads((ROOT / path).read_text()))
            return found
        claude = commands(".claude/settings.json")
        gated = [c for c in claude if "shell_guard.py" in c or "lifecycle.py" in c]
        self.assertEqual(len(gated), 4)
        self.assertTrue(all(c.endswith("--skip-in-cursor") for c in gated), gated)
        self.assertTrue(all("--skip-in-cursor" not in c for c in claude if "autonomy_hook.py" in c))
        for other in (".cursor/hooks.json", ".codex/hooks.json"):
            self.assertTrue(all("--skip-in-cursor" not in c for c in commands(other)), other)


class HookFastPath(Fixture):  # R3
    LIFECYCLE = [str(SCRIPTS / "lifecycle.py"), "hook"]

    def test_ordinary_shell_commands_skip_heavy_imports(self) -> None:
        cursor = {"hook_event_name": "beforeShellExecution", "command": "ls -la", "cursor_version": "1",
                  "workspace_roots": [str(self.repo)]}
        result = self.run_script(self.LIFECYCLE, cursor, "-X", "importtime")
        self.assertEqual(json.loads(result.stdout), {"permission": "allow"})
        self.assertNotRegex(result.stderr, HEAVY)
        result = self.run_script(self.LIFECYCLE, self.claude_shell("pytest -q"), "-X", "importtime")
        self.assertEqual(result.stdout, "")
        self.assertNotRegex(result.stderr, HEAVY)

    def test_an_active_task_does_not_load_heavy_modules_for_ordinary_commands(self) -> None:
        for args in (("tier", "L1", "--reason", "fixture"), ("stage", "intent", "--note", "goal; check; none")):
            step = subprocess.run([sys.executable, str(SCRIPTS / "lifecycle.py"), *args], cwd=self.repo, capture_output=True, text=True)
            self.assertEqual(step.returncode, 0, step.stderr)
        self.assertTrue(list((self.repo / "knowledge/history/lifecycle").glob("*.json")), "the audit record makes load() use learning")
        probe = ("import io, json, sys; sys.path.insert(0, {scripts!r}); import lifecycle; "
                 "sys.stdin = io.StringIO(sys.argv[1]); lifecycle.main(['hook']); "
                 "print(json.dumps([type(sys.modules[m]).__name__ for m in ('okf', 'brownfield', 'learning')]), file=sys.stderr)")
        payload = json.dumps({"hook_event_name": "beforeShellExecution", "command": "ls -la", "cursor_version": "1",
                              "workspace_roots": [str(self.repo)]})
        result = subprocess.run([sys.executable, "-c", probe.format(scripts=str(SCRIPTS)), payload], cwd=self.repo,
                                capture_output=True, text=True, env={**self.clean_env(), "CLAUDE_PROJECT_DIR": ""})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"permission": "allow"})
        self.assertEqual(json.loads(result.stderr.strip().splitlines()[-1]), ["_LazyModule"] * 3)

    def test_commits_and_pull_requests_are_still_gated(self) -> None:
        for command in ('git commit -m "feat: x"', "gh pr create --fill"):
            cursor = {"hook_event_name": "beforeShellExecution", "command": command, "cursor_version": "1",
                      "workspace_roots": [str(self.repo)]}
            decision = json.loads(self.run_script(self.LIFECYCLE, cursor).stdout)
            self.assertEqual(decision["permission"], "deny", command)
            self.assertIn("No active lifecycle tier", decision["agent_message"])


class Runner(unittest.TestCase):  # R4
    MODULES = {
        "test_alpha.py": """
            import unittest
            class Mixed(unittest.TestCase):
                def test_pass(self): pass
                def test_fail(self): self.assertEqual(1, 2)
                @unittest.skip("not here")
                def test_skip(self): pass
            class Broken(unittest.TestCase):
                def test_error(self): raise RuntimeError("boom")
                def test_pass(self): print("noise on stdout")
            """,
        "test_beta.py": """
            import unittest
            class Fine(unittest.TestCase):
                def test_one(self): pass
                def test_two(self): pass
            """,
        "test_gamma.py": "import does_not_exist_anywhere\n",
    }

    def fixture(self, names: tuple) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name in names:
            (Path(tmp.name) / name).write_text(textwrap.dedent(self.MODULES[name]))
        return Path(tmp.name)

    def discover_count(self, start: Path) -> int:
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(start)], capture_output=True, text=True)
        return int(re.search(r"^Ran (\d+) tests?", result.stderr, re.M).group(1))

    def runner(self, start: Path) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), "-j", "2", "-s", str(start)],
                              capture_output=True, text=True, cwd=ROOT)

    def test_failures_errors_and_import_errors_are_named_and_counted(self) -> None:
        start = self.fixture(("test_alpha.py", "test_beta.py", "test_gamma.py"))
        result = self.runner(start)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, output)
        for test_id in ("test_alpha.Mixed.test_fail", "test_alpha.Broken.test_error", "test_gamma"):
            self.assertIn(test_id, output)
        self.assertIn("boom", output)
        self.assertRegex(output, rf"(?m)^Ran {self.discover_count(start)} tests\b")

    def test_a_passing_suite_exits_zero_with_the_same_count(self) -> None:
        start = self.fixture(("test_beta.py",))
        result = self.runner(start)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, rf"(?m)^Ran {self.discover_count(start)} tests\b.*\bOK\b")


if __name__ == "__main__":
    unittest.main()
