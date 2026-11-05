"""Conservative automatic input scopes and explainable content-based reuse."""
from pathlib import Path
import os
import sys
import unittest
from unittest import mock
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ledger
import disk_tmp
from test_ledger import LedgerCase


class DefaultScopeTests(LedgerCase):
    def prepare_helper_check(self, command, expected):
        tests = self.repo / 'tests'
        tests.mkdir()
        (tests / 'test_helper.py').write_text(
            'import unittest, subprocess\nclass Helper(unittest.TestCase):\n'
            f' def test_helper(self):\n  self.assertEqual(subprocess.check_output({command!r}, text=True).strip(), {expected!r})\n')
        self.ok('tier', 'L1', '--reason', 'input metadata')
        self.ok('run', 'unit', '--', sys.executable, '-m', 'unittest', 'discover', '-s', 'tests')
        code, out, err = self.run_cli('reuse', 'unit')
        self.assertEqual(code, 0, out + err)

    def test_inferred_reuse_rejects_changed_executable_permissions(self):
        helper = self.repo / 'helper.py'
        helper.write_text(f'#!{sys.executable}\nprint("ok")\n' if os.name != 'nt' else
                          'from pathlib import Path\nprint("ok" if Path(__file__).stat().st_mode & 0o200 else "read-only")\n')
        helper.chmod(0o755)
        self.prepare_helper_check(['./helper.py'] if os.name != 'nt' else [sys.executable, 'helper.py'], 'ok')
        helper.chmod(0o644 if os.name != 'nt' else 0o444)
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'],
                                cwd=self.repo, capture_output=True)
        self.assertNotEqual(result.returncode, 0, 'helper execution should fail after chmod')
        code, out, err = self.run_cli('reuse', 'unit')
        self.assertEqual(code, 1, out + err)
        self.assertIn('helper.py', out + err)

    def test_inferred_reuse_rejects_retargeted_symlinks_with_identical_bytes(self):
        for name in ('left', 'right'):
            directory = self.repo / name
            directory.mkdir()
            (directory / 'helper.py').write_text('from pathlib import Path\nprint(Path(__file__).resolve().parent.name)\n')
        helper = self.repo / ('helper.py' if os.name != 'nt' else 'selected')
        if os.name == 'nt':
            disk_tmp.directory_link(helper, self.repo / 'left')
        else:
            helper.symlink_to('left/helper.py')
        command_path = 'helper.py' if os.name != 'nt' else 'selected/helper.py'
        self.prepare_helper_check([sys.executable, command_path], 'left')
        if os.name == 'nt':
            helper.rmdir()
            disk_tmp.directory_link(helper, self.repo / 'right')
        else:
            helper.unlink()
            helper.symlink_to('right/helper.py')
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'],
                                cwd=self.repo, capture_output=True)
        self.assertNotEqual(result.returncode, 0, 'helper output should change after retargeting')
        code, out, err = self.run_cli('reuse', 'unit')
        self.assertEqual(code, 1, out + err)
        self.assertIn('helper.py', out + err)

    def test_submodule_inputs_cannot_be_hashed_as_missing_files(self):
        (self.repo / 'vendor').mkdir()
        self.git('update-index', '--add', '--cacheinfo', f'160000,{self.head()},vendor')
        with self.assertRaisesRegex(ValueError, 'submodule'):
            ledger.inputs_digest(self.repo, ['**'])
        # Scopes outside the submodule still work.
        self.assertIsNotNone(ledger.inputs_digest(self.repo, ['app.py']))

    def test_input_fingerprints_use_literal_git_paths(self):
        literal = ('café.txt', 'line\nbreak.txt', 'quote".txt')
        # NUL-delimited Git transport must retain every literal spelling even
        # when the host filesystem cannot create one of those names.
        replies = [subprocess.CompletedProcess([], 0, '\0'.join(literal) + '\0', ''),
                   subprocess.CompletedProcess([], 0, '', '')]
        with mock.patch.object(ledger, '_git', side_effect=replies):
            self.assertEqual(ledger.input_paths(self.repo, ['**']), sorted(literal))
        native = literal if os.name != 'nt' else ('café.txt', 'line break.txt', "quote'.txt")
        for name in native:
            with self.subTest(name=name):
                path = self.repo / name
                path.write_text('original')
                self.assertIn(name, ledger.input_paths(self.repo, ['**']))
                before = ledger.inputs_digest(self.repo, ['**'])
                path.write_text('changed')
                self.assertNotEqual(before, ledger.inputs_digest(self.repo, ['**']))

    def test_package_scope_keeps_selected_packages_nested_under_unselected_members(self):
        parent = self.repo / 'crates/parent'
        child = parent / 'child'
        child.mkdir(parents=True)
        (child / 'lib.rs').write_text('selected source')
        metadata = {'workspace_members': ['parent', 'child'], 'packages': [
            {'id': 'parent', 'name': 'parent', 'manifest_path': str(parent / 'Cargo.toml'), 'dependencies': []},
            {'id': 'child', 'name': 'child', 'manifest_path': str(child / 'Cargo.toml'), 'dependencies': []}]}
        globs = ledger.package_inputs(self.repo, ['cargo', 'test', '-p', 'child'], metadata)
        self.assertIn('crates/parent/child/lib.rs', ledger.input_paths(self.repo, globs))

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
