"""Conservative test selection boundaries."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".ai" / "scripts"))
import validation_select


class SelectionTests(unittest.TestCase):
    packages = [{"name": "core", "directory": "crates/core", "dependencies": []},
                {"name": "service", "directory": "crates/service", "dependencies": ["core"]},
                {"name": "host", "directory": "crates/host", "dependencies": ["service"]}]

    def test_reverse_dependencies_and_core_expand_to_broad_baseline(self):
        result = validation_select.select(["crates/service/src/main.rs"], self.packages, core=["core"])
        self.assertEqual(result["affected_packages"], ["host", "service"])
        self.assertFalse(result["broad_baseline"])
        self.assertIn("host", result["commands"][1])
        self.assertTrue(validation_select.select(["crates/core/src/lib.rs"], self.packages, core=["core"])["broad_baseline"])
        self.assertFalse(validation_select.select(["crates/core/src/lib.rs"], self.packages)["broad_baseline"])

    def test_unknown_and_build_inputs_default_broad(self):
        for path in ("Cargo.lock", "Cargo.toml", "rust-toolchain.toml", "new-surface/file.py", "tools/helper.py"):
            self.assertTrue(validation_select.select([path], self.packages)["broad_baseline"], path)

    def test_documents_and_governance_select_applicable_checks_without_product_suite(self):
        docs = validation_select.select(["knowledge/project/example.md", "AGENTS.md"], self.packages)
        self.assertEqual(docs["commands"], validation_select.STRUCTURE)
        tooling = validation_select.select([".ai/scripts/autonomy_driver.py"], self.packages)
        self.assertIn(validation_select.GOVERNANCE, tooling["commands"])
        self.assertFalse(any(command[0] == "cargo" for command in tooling["commands"]))
        self.assertEqual(tooling["kind"], "feedback-checks")

    def test_without_packages_broad_baseline_runs_no_cargo_command(self):
        result = validation_select.select(["src/app.py"], [])
        self.assertTrue(result["broad_baseline"])
        self.assertEqual(result["commands"], [validation_select.GOVERNANCE, *validation_select.STRUCTURE])

    def test_selector_cli_uses_real_git_and_reports_non_submission(self):
        result = subprocess.run([sys.executable, str(ROOT / ".ai/scripts/validation_select.py"), "--base", "HEAD", "--full"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertTrue(value["broad_baseline"])
        has_workspace = (ROOT / "Cargo.toml").is_file()
        self.assertEqual(any(command[0] == "cargo" for command in value["commands"]), has_workspace)
        self.assertIn(validation_select.GOVERNANCE, value["commands"])
        self.assertNotIn("requirements", value)

    def test_cross_package_rename_keeps_core_in_actual_cli_selection(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "Cargo.toml").write_text("[workspace]\n")
            source = root / "crates/core/src/moved.rs"
            source.parent.mkdir(parents=True)
            source.write_text("pub fn moved() {}\n" * 10)
            for args in (["add", "."], ["-c", "user.name=test", "-c", "user.email=t@t", "commit", "-qm", "base"]):
                subprocess.run(["git", "-C", str(root), *args], check=True)
            destination = root / "crates/service/src/moved.rs"
            destination.parent.mkdir(parents=True)
            source.rename(destination)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            metadata = {"workspace_members": [p["name"] for p in self.packages], "packages": [
                {"id": p["name"], "name": p["name"], "manifest_path": str(root / p["directory"] / "Cargo.toml"),
                 "dependencies": [{"name": d} for d in p["dependencies"]]} for p in self.packages]}
            original = subprocess.check_output
            def output(argv, **kwargs):
                if argv[0] == "cargo":
                    return json.dumps(metadata).encode()
                return original(argv, cwd=root, **{k: v for k, v in kwargs.items() if k != "cwd"})
            with mock.patch.object(sys, "argv", ["validation_select", "--base", "HEAD", "--core", "core"]), \
                    mock.patch.object(subprocess, "check_output", side_effect=output), \
                    contextlib.redirect_stdout(io.StringIO()) as captured:
                self.assertEqual(validation_select.main(), 0)
            result = json.loads(captured.getvalue())
            self.assertIn("core", result["affected_packages"])
            self.assertTrue(result["broad_baseline"])


if __name__ == "__main__":
    unittest.main()
