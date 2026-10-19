"""Behavioral tests for shell_guard.py. Run: python3 -m unittest discover -s .ai/scripts/tests"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import shell_guard  # noqa: E402

ROOT = Path("/work/project")

# Commands taken from real agent sessions, with the verdict the guard must reach.
BLOCKED = {
    "cat .ai/agents/implementer.md .ai/personas/rust-principal-engineer.md | head -200": "okf-read",
    "cd /work/project && ls -R .ai | head -50": "okf-list",
    "cat knowledge/concepts/domain-model.md; grep -n ADR-024 -A12 knowledge/project/decisions.md": "okf-read",
    "grep -n Progress knowledge/plans/phase-0-foundation.md | cut -c1-6000": "okf-search",
    "cd /work/project/knowledge && rg -n 'parser|renderer' --glob '!log.md' | cut -c1-220": "okf-search",
    "cd /work/project/knowledge && cat index.md plans/roadmap.md": "okf-read",
    "find knowledge -type f | sort": "okf-list",
    "sed -n 1,20p knowledge/specifications/config-format.md | tail -8": "okf-read",
    "cat app/flutter_rust_bridge.yaml crates/app-ffi/Cargo.toml": "read",
    "sed -n 28,43p .ai/scripts/okf.py": "read",
    "head -30 app/lib/main.dart": "read",
    "grep -rn app_ffi app --include=* -I 2>/dev/null | grep -v lock | head -30": "search",
    "ls -la && find . -maxdepth 2 -not -path './.git*' | head -80": "list",
    "cat > xtask/Cargo.toml <<'EOF'\n[package]\nname = \"xtask\"\nEOF": "write",
    "cat >> knowledge/playbooks/development-setup.md <<'EOF'\n## Steps\nEOF": "write",
    "sed -i 's/a/b/' crates/app-domain/src/platform.rs && cargo fmt --all": "write",
    "python3 - <<'EOF'\nimport pathlib\np = pathlib.Path('decisions.md'); p.write_text('x')\nEOF": "write",
    "echo '# SPDX' | tee app/pubspec.yaml": "write",
    "git ls-files -o --exclude-standard app/android app/lib | grep -v -E 'gradle/|\\.png' | head -80": "list",
    "git -C /work/project ls-files knowledge": "okf-list",
    "git grep -n android xtask/src": "search",
    "CARGO_TARGET_DIR=/x DISPLAY=:0 SDL_VIDEODRIVER=x11 cargo test -p app --test core_systems": "display",
    "cd /work/project && DISPLAY=:1.0 cargo xtask e2e ui-desktop restart_restores_the_place": "display",
    "env WAYLAND_DISPLAY=wayland-0 cargo run -p app": "display",
}
ALLOWED = (
    "cargo test --workspace --all-targets -- --test-threads=8 2>&1 | rg -n 'FAILED|panicked'",
    "cargo clippy --workspace --all-targets -- -D warnings 2>&1 | tail -15",
    "git status --short | head",
    "python3 .ai/scripts/okf.py show knowledge/plans/phase-0-foundation.md --body | sed -n '20,60p'",
    "python3 -m unittest discover -s .ai/scripts/tests",
    "cargo test --lib > /tmp/qview.log 2>&1; echo LIB:$?; tail -20 /tmp/qview.log",
    "flutter --version 2>&1 | head -6; which cargo-binstall; ls ~/.cargo/bin",
    "find . -name '*.orig' -delete",
    "python3 - <<'EOF'\nimport json\nprint(json.load(open('/tmp/x.json')))\nEOF",
    "cat <<'EOF' | python3 -\nprint('hi')\nEOF",
    "wc -l DISCOVERY.md",
    "rg -n 'unterminated quote",
    "python3 .ai/scripts/repo.py files 'app/**/*.kt' --limit 50",
    "python3 .ai/scripts/repo.py grep android --under xtask --glob '*.rs'",
    "git log --oneline | head -3",
    "git -C /work/project status --short",
    "xvfb-run -a cargo xtask e2e ui-desktop system-bar",
    "DISPLAY=:99 cargo test -p app --test desktop_parity",
    "DISPLAY=:10 cargo test -p app",
)


class JudgeTests(unittest.TestCase):
    def test_blocks_shell_work_that_tools_and_okf_do(self) -> None:
        for command, expected in BLOCKED.items():
            with self.subTest(command=command):
                self.assertEqual(shell_guard.judge(command, ROOT), expected)

    def test_allows_output_filtering_builds_and_okf(self) -> None:
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(shell_guard.judge(command, ROOT))

    def test_list_and_search_messages_name_a_command_that_always_exists(self) -> None:
        self.assertIn("repo.py files", shell_guard.MESSAGES["list"])
        self.assertIn("repo.py grep", shell_guard.MESSAGES["search"])


class HookProtocolTests(unittest.TestCase):
    def run_hook(self, payload: dict[str, object], **env: str) -> dict[str, object] | None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "shell_guard.py")],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": "", **env},
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def test_cursor_deny_names_the_replacement(self) -> None:
        out = self.run_hook({"command": "cat knowledge/log.md", "workspace_roots": [str(ROOT)]})
        self.assertEqual(out["permission"], "deny")
        self.assertIn("okf.py", out["agent_message"])
        self.assertEqual(self.run_hook({"command": "cargo test", "cwd": str(ROOT)}), {"permission": "allow"})

    def test_claude_code_deny_and_silent_allow(self) -> None:
        out = self.run_hook({"tool_name": "Bash", "tool_input": {"command": "head -5 src/main.rs"}, "cwd": str(ROOT)})
        decision = out["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Read (file_path, offset, limit)", decision["permissionDecisionReason"])
        self.assertIsNone(self.run_hook({"tool_name": "Bash", "tool_input": {"command": "cargo build"}, "cwd": str(ROOT)}))

    def test_disable_switch_and_bad_input_fail_open(self) -> None:
        payload = {"tool_name": "Bash", "tool_input": {"command": "cat src/main.rs"}, "cwd": str(ROOT)}
        self.assertIsNone(self.run_hook(payload, OKF_SHELL_GUARD="off"))
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "shell_guard.py")], input="not json", capture_output=True, text=True, check=False
        )
        self.assertEqual((result.returncode, result.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
