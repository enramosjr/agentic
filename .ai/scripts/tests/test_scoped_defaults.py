"""Conservative automatic input scopes and explainable content-based reuse."""
from pathlib import Path
import sys
import unittest
from unittest import mock
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ledger
from test_ledger import LedgerCase


class DefaultScopeTests(LedgerCase):
    def test_known_commands_get_scopes_unknown_commands_do_not(self):
        self.assertEqual(ledger.default_inputs(['cargo', 'fmt', '--all', '--', '--check'])[0], 'cargo-format')
        self.assertEqual(ledger.default_inputs([sys.executable, '-m', 'unittest', 'discover'])[1], ['**'])
        self.assertIsNone(ledger.default_inputs(['custom-check', '--anything']))

    def test_standard_check_reuses_identical_content_after_commit_and_names_changed_file(self):
        tests = self.repo / 'tests'
        tests.mkdir()
        (tests / 'test_app.py').write_text(
            'import unittest, subprocess, sys\n'
            'class App(unittest.TestCase):\n'
            ' def test_output(self):\n'
            '  self.assertEqual(subprocess.check_output([sys.executable,"app.py"],text=True).strip(),"hi")\n')
        self.ok('tier', 'L1', '--reason', 'automatic scopes')
        self.ok('run', 'unit', '--', sys.executable, '-m', 'unittest', 'discover', '-s', 'tests')
        self.assertTrue(self.entries()[-1]['inputs'])
        self.git('add', '-A')
        self.git('commit', '-qm', 'same tested bytes')
        self.assertEqual(self.run_cli('reuse', 'unit')[0], 0)
        (self.repo / 'app.py').write_text("print('changed')\n")
        code, out, err = self.run_cli('reuse', 'unit')
        self.assertEqual(code, 1)
        self.assertIn('app.py', out + err)

    def test_unknown_check_keeps_exact_tree_fallback(self):
        self.ok('tier', 'L1', '--reason', 'unknown scope')
        self.ok('run', 'unknown', '--', sys.executable, '-c', 'pass')
        self.assertEqual(self.entries()[-1]['inputs'], [])
        (self.repo / 'changed.txt').write_text('changed')
        self.assertNotEqual(self.run_cli('reuse', 'unknown')[0], 0)

    def test_failed_input_inventory_cannot_be_fingerprinted_as_an_empty_repository(self):
        failed = subprocess.CompletedProcess(['git', 'ls-files'], 128, '', 'fatal: index is corrupt')
        with mock.patch.object(ledger, '_git', return_value=failed):
            with self.assertRaisesRegex(ValueError, 'input inventory'):
                ledger.inputs_digest(self.repo, ['**'])

    def test_package_scope_covers_dependencies_and_all_manifests_but_not_unrelated_code(self):
        metadata = {'workspace_members': ['a', 'b', 'c'], 'packages': [
            {'id': 'a', 'name': 'a', 'manifest_path': str(self.repo / 'crates/a/Cargo.toml'), 'dependencies': [{'name': 'b'}]},
            {'id': 'b', 'name': 'b', 'manifest_path': str(self.repo / 'crates/b/Cargo.toml'), 'dependencies': []},
            {'id': 'c', 'name': 'c', 'manifest_path': str(self.repo / 'crates/c/Cargo.toml'), 'dependencies': []}]}
        for package in ('a', 'b', 'c'):
            directory = self.repo / 'crates' / package
            directory.mkdir(parents=True)
            (directory / 'Cargo.toml').write_text(package)
            (directory / 'lib.rs').write_text(package)
        globs = ledger.package_inputs(self.repo, ['cargo', 'test', '-p', 'a'], metadata)
        paths = ledger.input_paths(self.repo, globs)
        self.assertIn('crates/a/lib.rs', paths)
        self.assertIn('crates/b/lib.rs', paths)
        self.assertIn('crates/c/Cargo.toml', paths)
        self.assertNotIn('crates/c/lib.rs', paths)


if __name__ == '__main__':
    unittest.main()
