"""Installer contract R1–R12: real repositories, CLI outcomes and preserved bytes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import contextlib
import io
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))
import install


class InstallerCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.template, self.target = base / "template", base / "adopter with spaces"
        self.template.mkdir()
        for name in install.KIT:
            source, dest = ROOT / name, self.template / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                dest.symlink_to(os.readlink(source))
            elif source.is_dir():
                shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(source, dest)
        self.target.mkdir()
        self.git("init", "-q")
        self.write("src/app.py", "print('ours')\n")
        self.commit()

    def git(self, *args):
        return subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@test", *args],
                              cwd=self.target, capture_output=True, text=True, check=True).stdout

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")

    def write(self, name, data, template=False):
        path = (self.template if template else self.target) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        return path

    def run_install(self, *flags, code=0):
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run([sys.executable, str(self.template / ".ai/scripts/install.py"), *flags, str(self.target)],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def manifest(self):
        return json.loads((self.target / ".ai/install-manifest.json").read_bytes())

    def snapshot(self):
        return {str(p.relative_to(self.target)): ("link", os.readlink(p)) if p.is_symlink() else
                (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
                for p in self.target.rglob("*") if (p.is_file() or p.is_symlink()) and ".git" not in p.relative_to(self.target).parts}

    def installed(self):
        self.run_install()
        self.commit()


def tree_state(root):
    """Include directories and Git metadata when proving a command made no writes."""
    return {str(p.relative_to(root)): ("link", os.readlink(p)) if p.is_symlink() else
            ("dir",) if p.is_dir() else (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
            for p in root.rglob("*")}


class BootstrapCase(InstallerCase):
    def setUp(self):
        super().setUp()
        self.target = self.target.parent / "new project with spaces"
        # Fixtures live under the outer repo's .git scratch. Treat each fixture
        # as an independent project while still discovering its own repositories.
        environment = patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(Path(self.temp.name).parent)})
        environment.start()
        self.addCleanup(environment.stop)

    def assert_bootstrapped(self):
        self.assertEqual(Path(self.git("rev-parse", "--show-toplevel").strip()).resolve(), self.target)
        head = subprocess.run(["git", "-C", str(self.target), "rev-parse", "--verify", "HEAD"], capture_output=True)
        self.assertNotEqual(head.returncode, 0, "bootstrap must not create a commit")
        self.assertEqual(self.git("remote"), "")
        self.manifest()
        for name in install.plain_files(self.template):
            self.assertEqual((self.target / name).read_bytes(), (self.template / name).read_bytes(), name)
        self.assertTrue((self.target / "knowledge/index.md").is_file())
        self.assertFalse((self.target / "knowledge/project/work-queue.md").exists())


class BootstrapNewFolderTests(BootstrapCase):
    # R2: real CLI bootstrap, including missing parent directories.
    def test_missing_and_empty_folder(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                self.target = self.target.parent / ("empty project" if existing else "missing parent/new project")
                if existing:
                    self.target.mkdir(parents=True)
                self.run_install()
                self.assert_bootstrapped()


class BootstrapExistingFolderTests(BootstrapCase):
    # R3: preserve adopter bytes and merge existing untracked instructions/hooks.
    def test_populated_non_git_folder(self):
        app = self.write("src/app.py", b"application\x00\xff")
        self.write("AGENTS.md", "# Adopter instructions\n")
        self.write("CLAUDE.md", "# Adopter Claude instructions\n")
        for name in install.HOOK_FILES:
            hook = {"command": "adopter-command"}
            entry = hook if name == ".cursor/hooks.json" else {"hooks": [hook]}
            self.write(name, json.dumps({"custom": "keep", "hooks": {"adopter-event": [entry]}}))
        subprocess.run([sys.executable, str(self.template / ".ai/scripts/okf.py"), "--bundle",
                        str(self.target / "knowledge"), "init"], check=True, capture_output=True)
        self.write("knowledge/private.txt", b"project knowledge\xff")
        knowledge = tree_state(self.target / "knowledge")
        self.run_install()
        self.assertEqual(app.read_bytes(), b"application\x00\xff")
        self.assertEqual(tree_state(self.target / "knowledge"), knowledge)
        self.assertTrue((self.target / "AGENTS.md").read_text().startswith("# Adopter instructions\n"))
        self.assertEqual((self.target / "CLAUDE.md").read_text(), "# Adopter Claude instructions\n\n@AGENTS.md\n")
        for name in install.HOOK_FILES:
            data = json.loads((self.target / name).read_bytes())
            self.assertEqual(data["custom"], "keep")
            self.assertIn("adopter-command", install.commands(data, name == ".cursor/hooks.json"))
            self.assertTrue(set(install.commands(json.loads((self.template / name).read_bytes()),
                                                name == ".cursor/hooks.json")).issubset(
                install.commands(data, name == ".cursor/hooks.json")))
        self.assert_bootstrapped()

    def test_plain_file_conflict_keeps_adopter_copy(self):
        self.write(".ai/VERSION", "adopter-owned\n")
        self.assertIn("conflict: .ai/VERSION", self.run_install(code=1))
        self.assertEqual((self.target / ".ai/VERSION").read_text(), "adopter-owned\n")
        self.assertNotIn(".ai/VERSION", self.manifest()["files"])

    def test_invalid_inputs_refuse_before_git_initialization(self):
        for name, content in ((".claude/settings.json", "{broken"), ("AGENTS.md", install.BEGIN)):
            with self.subTest(name=name):
                path = self.write(name, content)
                before = tree_state(self.target)
                self.run_install(code=2)
                self.assertEqual(tree_state(self.target), before)
                self.assertFalse((self.target / ".git").exists())
                path.unlink()


class BootstrapLocalityTests(BootstrapCase):
    # R5: home/config directories and template-private state never become kit files.
    def test_complete_kit_is_project_local(self):
        private = ("knowledge/private.txt", ".claude/settings.local.json", ".claude/projects/session.json",
                   ".codex/sessions/session.json", ".cursor/session.json")
        for name in private:
            self.write(name, "template-private", template=True)
        subprocess.run(["git", "init", "-q", str(self.template)], check=True, capture_output=True)
        self.write(".git/template-private", "history marker", template=True)
        home = self.target.parent / "isolated home"
        for name in (".codex/config.toml", ".claude/settings.json", ".cursor/settings.json"):
            path = home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("global sentinel")
        before = tree_state(home)
        with patch.dict(os.environ, {"HOME": str(home), "CODEX_HOME": str(home / ".codex"),
                                    "CLAUDE_CONFIG_DIR": str(home / ".claude"),
                                    "XDG_CONFIG_HOME": str(home / ".config")}):
            self.run_install()
        self.assertEqual(tree_state(home), before)
        self.assert_bootstrapped()
        for name in (*private, ".git/template-private"):
            self.assertFalse((self.target / name).exists(), name)
        for name in (*install.HOOK_FILES, "AGENTS.md", "CLAUDE.md", ".agents/skills/spec/SKILL.md"):
            self.assertTrue((self.target / name).is_file(), name)


class BootstrapWorkflowTests(BootstrapCase):
    # R6: read-only checks and the actual installed enforcement/records path.
    def test_check_missing_and_non_git_is_read_only(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    self.write("src/app.py", "adopter bytes")
                before = tree_state(self.target.parent)
                self.assertIn("not installed", self.run_install("--check", code=1))
                self.assertEqual(tree_state(self.target.parent), before)

    def test_bootstrap_repeat_check_records_and_hook(self):
        self.run_install()
        before = tree_state(self.target)
        self.assertIn("up to date", self.run_install())
        self.run_install("--check")
        self.assertEqual(tree_state(self.target), before)
        result = subprocess.run([sys.executable, ".ai/scripts/okf.py", "records"], cwd=self.target,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        env = {k: v for k, v in os.environ.items() if k not in ("LIFECYCLE_GUARD", "OKF_AUTONOMOUS")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Edit",
                   "tool_input": {"file_path": str(self.target / "src/app.py")}, "cwd": str(self.target)}
        result = subprocess.run([sys.executable, ".ai/scripts/lifecycle.py", "hook"], cwd=self.target,
                                input=json.dumps(payload), capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_nested_targets_and_file_refuse_without_mutation(self):
        parent = self.target.parent / "parent repo"
        parent.mkdir()
        subprocess.run(["git", "init", "-q", str(parent)], check=True, capture_output=True)
        (parent / "existing").mkdir()
        (parent / "file").write_text("keep")
        for target in (parent / "existing", parent / "missing/deep", parent / "file", parent / "file/child"):
            with self.subTest(target=target):
                self.target = target
                before = tree_state(parent)
                self.run_install(code=2)
                self.assertEqual(tree_state(parent), before)

    def test_bare_and_invalid_repository_metadata_refuse(self):
        for bare in (False, True):
            with self.subTest(bare=bare):
                self.target = self.target.parent / ("bare project" if bare else "invalid project")
                if bare:
                    subprocess.run(["git", "init", "--bare", "-q", str(self.target)], check=True, capture_output=True)
                else:
                    self.write(".git", "invalid git metadata\n")
                before = tree_state(self.target)
                self.run_install(code=2)
                self.assertEqual(tree_state(self.target), before)


class BootstrapDocumentationTests(BootstrapCase):
    # R1: execute the documented route, rather than only testing matching prose.
    def test_documented_command_bootstraps_both_folder_states(self):
        readme = (ROOT / "README.md").read_text()
        section = readme.split("## Quick start\n", 1)[1].split("\n## ", 1)[0]
        command = "python3 /path/to/agentic/.ai/scripts/install.py TARGET"
        self.assertIn(command, section)
        self.assertIn("existing", section.lower())
        self.assertIn("new", section.lower())
        self.assertNotIn("1. Copy", section)
        for existing in (False, True):
            with self.subTest(existing=existing):
                self.target = self.target.parent / ("documented existing" if existing else "documented new")
                if existing:
                    self.target.mkdir()
                args = [sys.executable, str(self.template / ".ai/scripts/install.py"), str(self.target)]
                result = subprocess.run(args, capture_output=True, text=True,
                                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assert_bootstrapped()


class CopyTests(InstallerCase):
    # R2
    def test_files_copied_byte_equal_with_modes_and_skills_symlink(self):
        self.write(".ai/sample", b"\x00sample\xff", template=True).chmod(0o751)
        self.run_install()
        self.assertEqual((self.target / ".ai/sample").read_bytes(), b"\x00sample\xff")
        self.assertEqual((self.target / ".ai/sample").stat().st_mode & 0o777, 0o751)
        self.assertTrue((self.target / ".agents/skills").is_symlink())
        self.assertEqual((self.target / ".agents/skills").resolve(), self.target / ".claude/skills")
        for name in install.plain_files(self.template):
            self.assertEqual((self.target / name).read_bytes(), (self.template / name).read_bytes(), name)

    def test_symlink_oserror_falls_back_to_copy_recorded_in_manifest(self):
        with patch.object(install.os, "symlink", side_effect=OSError("unsupported")), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install.main([str(self.target)], template=self.template), 0)
        self.assertEqual(self.manifest()["skills_link"], "copy")
        self.assertFalse((self.target / ".agents/skills").is_symlink())
        for p in (self.template / ".claude/skills").rglob("*"):
            if p.is_file():
                self.assertEqual((self.target / ".agents/skills" / p.relative_to(self.template / ".claude/skills")).read_bytes(), p.read_bytes())
        self.run_install("--check")


class HookMergeTests(InstallerCase):
    # R3
    def merge(self, adopter, kit, previous=(), flat=False):
        return install.merge_hooks(adopter, kit, previous, flat=flat)

    def test_nested_merge_keeps_adopter_keys_and_groups(self):
        ours = {"permissions": {"allow": ["ours"]}, "hooks": {"Edit": [{"matcher": "x", "hooks": [{"command": "ours"}]}]}}
        kit = {"hooks": {"Edit": [{"matcher": "x", "hooks": [{"command": "kit"}]}]}}
        merged = self.merge(ours, kit)
        self.assertEqual(list(merged), ["permissions", "hooks"])
        self.assertEqual(merged["permissions"], ours["permissions"])
        self.assertEqual([h["command"] for h in merged["hooks"]["Edit"][0]["hooks"]], ["ours", "kit"])

    def test_nested_dedup_by_matcher_and_command(self):
        kit = {"hooks": {"Edit": [{"hooks": [{"command": "kit"}]}, {"matcher": "x", "hooks": [{"command": "kit"}]}]}}
        self.assertEqual(self.merge(kit, kit), kit)
        self.assertEqual(len(self.merge({"hooks": {}}, kit)["hooks"]["Edit"]), 2)

    def test_cursor_flat_merge_dedup_and_version_kept(self):
        ours = {"version": 9, "hooks": {"edit": [{"command": "kit", "matcher": "x"}, {"command": "ours"}]}}
        kit = {"version": 1, "hooks": {"edit": [{"command": "kit", "matcher": "x"}, {"command": "kit", "matcher": "y"}]}}
        merged = self.merge(ours, kit, flat=True)
        self.assertEqual(merged["version"], 9)
        self.assertEqual(len(merged["hooks"]["edit"]), 3)

    def test_absent_file_created_from_kit(self):
        self.run_install()
        for name in install.HOOK_FILES:
            self.assertEqual(json.loads((self.target / name).read_bytes()), json.loads((self.template / name).read_bytes()))

    def test_upgrade_removes_dropped_kit_entries_only(self):
        ours = {"hooks": {"edit": [{"command": "old"}, {"command": "ours"}]}}
        kit = {"hooks": {"edit": [{"command": "new"}]}}
        self.assertEqual(self.merge(ours, kit, ["old"], flat=True)["hooks"]["edit"], [{"command": "ours"}, {"command": "new"}])
        nested = {"hooks": {"Edit": [{"hooks": [{"command": "old"}, {"command": "ours"}]}]}}
        new = {"hooks": {"Edit": [{"hooks": [{"command": "new"}]}]}}
        self.assertEqual(self.merge(nested, new, ["old"])["hooks"]["Edit"][0]["hooks"], [{"command": "ours"}, {"command": "new"}])

    def test_unchanged_file_not_rewritten(self):
        self.installed()
        before = self.snapshot()
        self.assertIn("up to date", self.run_install())
        self.assertEqual(before, self.snapshot())

    def test_prompt_hook_preserved_through_install_upgrade_and_check(self):
        # R3: adopter hooks need not be command hooks.
        prompt = {"type": "prompt", "prompt": "Check the response"}
        self.write(".claude/settings.json", json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [prompt]}]}}))
        self.commit()
        self.run_install()
        self.commit()
        path = self.template / ".claude/settings.json"
        data = json.loads(path.read_bytes())
        data["hooks"]["PreToolUse"][0]["hooks"].pop(0)
        path.write_text(json.dumps(data))
        self.run_install()
        hooks = json.loads((self.target / ".claude/settings.json").read_bytes())["hooks"]["PreToolUse"][0]["hooks"]
        self.assertEqual(hooks[0], prompt)
        self.run_install("--check")
        before = self.snapshot()
        self.assertIn("up to date", self.run_install())
        self.assertEqual(before, self.snapshot())


class InstructionsTests(InstallerCase):
    # R4
    def test_absent_agents_md_gets_block_only(self):
        self.run_install()
        self.assertEqual((self.target / "AGENTS.md").read_bytes(), install.BEGIN + b"\n" + (self.template / "AGENTS.md").read_bytes() + install.END + b"\n")

    def test_existing_agents_md_bytes_kept_and_block_appended(self):
        self.write("AGENTS.md", b"# Ours\r\n\xff")
        self.commit()
        self.run_install()
        self.assertTrue((self.target / "AGENTS.md").read_bytes().startswith(b"# Ours\r\n\xff\n\n"))

    def test_block_replaced_in_place_on_upgrade(self):
        self.installed()
        path = self.target / "AGENTS.md"
        self.write("AGENTS.md", b"prefix\n" + path.read_bytes() + b"suffix\n")
        self.commit()
        self.write("AGENTS.md", "# New template\n", template=True)
        self.run_install()
        self.assertEqual(path.read_bytes(), b"prefix\n" + install.BEGIN + b"\n# New template\n" + install.END + b"\nsuffix\n")

    def test_claude_md_import_added_once(self):
        self.write("CLAUDE.md", "# Ours\n")
        self.commit()
        self.run_install()
        self.run_install()
        self.assertEqual((self.target / "CLAUDE.md").read_bytes(), b"# Ours\n\n@AGENTS.md\n")


class ManifestTests(InstallerCase):
    # R5
    def test_manifest_fields_format_and_template_version(self):
        head = self.git("rev-parse", "HEAD")
        self.run_install()
        data = self.manifest()
        self.assertEqual(set(data), {"format", "template_version", "files", "hooks", "agents_block", "skills_link"})
        self.assertEqual(data["format"], 1)
        self.assertEqual(data["template_version"], (self.template / ".ai/VERSION").read_text().strip())
        self.assertEqual(data["agents_block"], hashlib.sha256((self.template / "AGENTS.md").read_bytes()).hexdigest())
        self.assertEqual((self.target / ".ai/install-manifest.json").read_text(), json.dumps(data, indent=2, sort_keys=True) + "\n")
        for name, digest in data["files"].items():
            self.assertEqual(digest, hashlib.sha256((self.target / name).read_bytes()).hexdigest())
        self.assertEqual(head, self.git("rev-parse", "HEAD"))


class UpgradeTests(InstallerCase):
    # R7
    def new_version(self):
        self.write(".ai/VERSION", "0.2.0\n", template=True)

    def test_unedited_file_updated_to_new_template(self):
        self.installed()
        self.new_version()
        self.run_install()
        self.assertEqual((self.target / ".ai/VERSION").read_text(), "0.2.0\n")

    def test_edited_file_kept_reported_conflict_exit_1(self):
        self.installed()
        old = self.manifest()["files"][".ai/VERSION"]
        self.write(".ai/VERSION", "ours\n")
        self.new_version()
        out = self.run_install("--force", code=1)
        self.assertIn("conflict: .ai/VERSION (kept adopter copy)", out)
        self.assertEqual((self.target / ".ai/VERSION").read_text(), "ours\n")
        self.assertEqual(self.manifest()["files"][".ai/VERSION"], old)
        self.assertEqual(self.manifest()["template_version"], "0.2.0")

    def test_preexisting_differing_file_is_conflict(self):
        self.write(".ai/VERSION", "ours\n")
        self.commit()
        self.run_install(code=1)
        self.assertNotIn(".ai/VERSION", self.manifest()["files"])

    def test_missing_recorded_file_restored(self):
        self.installed()
        (self.target / ".ai/VERSION").unlink()
        self.commit()
        self.run_install()
        self.assertEqual((self.target / ".ai/VERSION").read_bytes(), (self.template / ".ai/VERSION").read_bytes())

    def test_dropped_kit_file_deleted_when_unedited(self):
        self.write(".ai/dropped", "old", template=True)
        self.installed()
        (self.template / ".ai/dropped").unlink()
        self.new_version()
        self.run_install()
        self.assertFalse((self.target / ".ai/dropped").exists())
        self.assertNotIn(".ai/dropped", self.manifest()["files"])

    def test_dropped_edited_file_keeps_hash_and_other_updates_proceed(self):
        # R7: deletion conflicts must not suppress independent updates.
        self.write(".ai/dropped", "old", template=True)
        self.installed()
        old = self.manifest()["files"][".ai/dropped"]
        self.write(".ai/dropped", "ours")
        self.commit()
        (self.template / ".ai/dropped").unlink()
        self.new_version()
        self.assertIn("conflict: .ai/dropped", self.run_install(code=1))
        self.assertEqual((self.target / ".ai/dropped").read_text(), "ours")
        self.assertEqual(self.manifest()["files"][".ai/dropped"], old)
        self.assertEqual((self.target / ".ai/VERSION").read_text(), "0.2.0\n")

    def copy_install(self):
        self.write(".claude/skills/obsolete/SKILL.md", "old skill", template=True)
        with patch.object(install.os, "symlink", side_effect=OSError("unsupported")), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install.main([str(self.target)], template=self.template), 0)
        self.commit()

    def test_dropped_fallback_skill_removed_and_check_detects_before_upgrade(self):
        # R2/R7/R8: fallback is an owned copy, including removed files.
        self.copy_install()
        (self.template / ".claude/skills/obsolete/SKILL.md").unlink()
        self.assertIn("drift: .agents/skills/obsolete/SKILL.md", self.run_install("--check", code=1))
        self.run_install()
        self.assertFalse((self.target / ".agents/skills/obsolete/SKILL.md").exists())
        self.run_install("--check")

    def test_dropped_edited_fallback_skill_kept_and_reported_repeatedly(self):
        # R7: preserve alias edits even when its canonical kit path was deleted.
        self.copy_install()
        self.write(".agents/skills/obsolete/SKILL.md", "ours")
        self.commit()
        (self.template / ".claude/skills/obsolete/SKILL.md").unlink()
        for _ in range(2):
            self.assertIn("conflict: .agents/skills/obsolete/SKILL.md", self.run_install(code=1))
            self.assertEqual((self.target / ".agents/skills/obsolete/SKILL.md").read_text(), "ours")
        self.assertIn("drift: .agents/skills/obsolete/SKILL.md", self.run_install("--check", code=1))


class CheckTests(InstallerCase):
    # R8
    def test_clean_install_exits_0_and_writes_nothing(self):
        self.installed()
        before = self.snapshot()
        self.run_install("--check")
        self.assertEqual(before, self.snapshot())

    def test_drift_missing_hooks_block_and_outdated_each_exit_1(self):
        self.installed()
        changes = [(".ai/VERSION", "changed", "drift: .ai/VERSION"),
                   (".claude/settings.json", "{}", "hooks: .claude/settings.json"),
                   ("AGENTS.md", "# gone", "agents-block: AGENTS.md")]
        for name, content, expected in changes:
            with self.subTest(name=name):
                path = self.target / name
                original = path.read_bytes()
                self.write(name, content)
                before = self.snapshot()
                self.assertIn(expected, self.run_install("--check", code=1))
                self.assertEqual(before, self.snapshot())
                path.write_bytes(original)
        (self.target / ".ai/VERSION").unlink()
        self.assertIn("missing: .ai/VERSION", self.run_install("--check", code=1))
        self.write(".ai/VERSION", "0.10.0\n", template=True)
        self.assertIn("outdated: 0.1.0 < 0.10.0", self.run_install("--check", code=1))

    def test_no_manifest_reports_not_installed(self):
        before = self.snapshot()
        self.assertIn("not installed", self.run_install("--check", code=1))
        self.assertEqual(before, self.snapshot())

    def test_wrong_skills_mode_reports_drift_without_writes(self):
        # R8: a copied tree in place of the recorded link is drift, not bad usage.
        self.installed()
        (self.target / ".agents/skills").unlink()
        shutil.copytree(self.target / ".claude/skills", self.target / ".agents/skills")
        before = self.snapshot()
        self.assertIn("drift: .agents/skills", self.run_install("--check", code=1))
        self.assertEqual(before, self.snapshot())


class KnowledgeTests(InstallerCase):
    # R9
    def test_init_runs_when_index_missing_and_skipped_with_flag(self):
        self.run_install("--no-knowledge")
        self.assertFalse((self.target / "knowledge").exists())
        self.run_install()
        self.assertTrue((self.target / "knowledge/index.md").is_file())


class RefusalTests(InstallerCase):
    # R10
    def refuses(self, *flags):
        before, status = self.snapshot(), self.git("status", "--porcelain")
        self.run_install(*flags, code=2)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(status, self.git("status", "--porcelain"))

    def test_not_git_toplevel(self):
        self.target = self.target / "src"
        self.refuses()

    def test_target_is_template_root(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / "install.py"), str(ROOT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("template", result.stderr)

    def test_unparseable_or_non_object_hook_json(self):
        for name in (*install.HOOK_FILES, ".ai/install-manifest.json"):
            for body in ("{broken", "[]", '{"hooks": []}'):
                with self.subTest(name=name, body=body):
                    self.write(name, body)
                    self.refuses("--force")
                    (self.target / name).unlink()

    def test_invalid_manifest_schema_refuses_without_traceback(self):
        # R10: malformed state must fail before any target mutation.
        for data in ({}, {"format": 1, "files": {}, "hooks": {}, "template_version": 1}):
            self.write(".ai/install-manifest.json", json.dumps(data))
            self.refuses("--force")

    def test_malformed_agents_markers(self):
        for body in (install.BEGIN, install.BEGIN + b"\n" + install.END + b"\n" + install.BEGIN + b"\n" + install.END):
            self.write("AGENTS.md", body)
            self.refuses("--force")

    def test_dirty_target_refused_and_force_proceeds(self):
        self.write("AGENTS.md", "# Ours\n")
        self.refuses()
        self.run_install("--force")
        before = self.snapshot()
        self.assertIn("up to date", self.run_install())
        self.assertEqual(before, self.snapshot())

    def test_staged_unstaged_and_unrelated_paths(self):
        # R10: dirty checks apply only to actual writes, including deletions.
        self.installed()
        self.write("src/app.py", "unrelated dirty")
        self.run_install()
        for staged in (False, True):
            with self.subTest(staged=staged):
                self.write(".ai/VERSION", "ours")
                if staged:
                    self.git("add", ".ai/VERSION")
                # A conflicting path is kept, so it alone is not a changing path.
                self.run_install(code=1)
                self.git("reset", "--hard", "HEAD")
                (self.target / ".ai/VERSION").unlink()
                if staged:
                    self.git("add", ".ai/VERSION")
                self.refuses()
                self.git("reset", "--hard", "HEAD")


class InstallE2ETests(InstallerCase):
    # R6, R11
    def test_install_into_existing_repo(self):
        self.write("AGENTS.md", "# Ours\n")
        self.write(".claude/settings.json", json.dumps({"permissions": {"allow": ["ours"]}, "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"command": "ours"}]}]}}))
        self.commit()
        self.run_install()
        data = json.loads((self.target / ".claude/settings.json").read_bytes())
        self.assertEqual(data["permissions"], {"allow": ["ours"]})
        self.assertEqual(data["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "ours")
        for name in install.HOOK_FILES:
            body = (self.target / name).read_text()
            self.assertIn("shell_guard.py", body)
            self.assertIn("lifecycle.py", body)
        body = (self.target / "AGENTS.md").read_bytes()
        self.assertTrue(body.startswith(b"# Ours\n"))
        self.assertEqual(body.count(install.BEGIN), 1)
        self.commit()
        before = self.snapshot()
        self.assertIn("up to date", self.run_install())
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_installed_hooks_deny_untiered_source_edit_and_records_pass(self):
        self.installed()
        env = {k: v for k, v in os.environ.items() if k not in ("LIFECYCLE_GUARD", "OKF_AUTONOMOUS")}
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": {"file_path": str(self.target / "src/app.py")}, "cwd": str(self.target)}
        result = subprocess.run([sys.executable, ".ai/scripts/lifecycle.py", "hook"], cwd=self.target, input=json.dumps(payload), capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"deny"', result.stdout)
        result = subprocess.run([sys.executable, ".ai/scripts/okf.py", "records"], cwd=self.target, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
