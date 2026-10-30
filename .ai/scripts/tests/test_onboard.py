"""Gap 3 R11: onboarding inventories evidence without executing repository code."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import okf


class OnboardE2ETests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        scripts = self.root / '.ai/scripts'
        scripts.mkdir(parents=True)
        shutil.copy2(SCRIPTS / 'okf.py', scripts / 'okf.py')
        shutil.copy2(SCRIPTS / 'learning.py', scripts / 'learning.py')
        for name in ('review_guard.py', 'scratch.py', 'ledger.py'):
            shutil.copy2(SCRIPTS / name, scripts / name)
        self.command = [sys.executable, str(scripts / 'okf.py')]
        self.git('init', '-q')
        self.write('alpha/main.py', 'open("SENTINEL", "w").write("bad")\n')
        self.write('beta/code.py', 'raise RuntimeError("do not execute")\n')
        self.write('pyproject.toml', '[project]\nname="fixture"\n')
        self.write('tests/test_fail.py', 'assert False\n')
        self.write('tests/test_pass.py', 'assert True\n')
        self.write('alpha/file with spaces.py', '# fact\n')
        self.write('.gitignore', 'ignored.py\n')
        self.write('binary.py', b'\0\xff')
        (self.root / 'outside.py').symlink_to('/etc/hosts')
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')
        self.write('ignored.py', 'raise RuntimeError()')
        self.write('untracked.py', 'raise RuntimeError()')

    def write(self, path, text):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode() if isinstance(text, str) else text)

    def git(self, *args):
        subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=self.root,
                       capture_output=True, check=True)

    def cli(self, *args, code=0):
        result = subprocess.run([*self.command, *args], cwd=self.root,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def snapshot(self, *, protected=False):
        files = {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                 for p in self.root.rglob('*') if p.is_file() and not p.is_symlink()}
        if protected:
            from review_test_support import closed_coordination_snapshot
            return closed_coordination_snapshot(self.root, files)
        return files

    def test_cited_drafts_validate_and_second_run_is_noop(self):
        self.cli('onboard')
        bundle = self.root / 'knowledge'
        for path in ('project/architecture.md', 'capabilities/repository-inventory.md'):
            doc = okf.load_doc(bundle, bundle / path)
            self.assertEqual(doc.meta['status'], 'draft')
            self.assertEqual(doc.meta['evidence'], 'project-documentation')
            self.assertNotIn('verified', doc.meta)
            self.assertNotIn('## Requirements', doc.body)
            self.assertIn('alpha/main.py', doc.body)
            self.assertIn('beta/code.py', doc.body)
            for excluded in ('ignored.py', 'untracked.py', 'binary.py', 'outside.py', '.ai/scripts'):
                self.assertNotIn(excluded, doc.body)
            for source in doc.meta['sources']:
                self.assertIn(source['id'], doc.body)
                self.assertTrue((doc.path.parent / source['resource']).is_file())
        self.assertFalse((self.root / 'SENTINEL').exists())
        self.cli('validate')
        before = self.snapshot(protected=True)
        self.cli('onboard')
        self.assertEqual(before, self.snapshot(protected=True))

    def test_existing_one_document_kept_byte_equal(self):
        existing = b'---\ntype: Architecture\n---\n# Ours\n'
        self.write('knowledge/project/architecture.md', existing)
        self.cli('onboard')
        self.assertEqual((self.root / 'knowledge/project/architecture.md').read_bytes(), existing)
        self.assertTrue((self.root / 'knowledge/capabilities/repository-inventory.md').exists())

    def test_preflight_refusal_before_initialization(self):
        (self.root / 'knowledge/capabilities/repository-inventory.md').mkdir(parents=True)
        before = self.snapshot(protected=True)
        self.cli('onboard', code=1)
        self.assertEqual(before, self.snapshot(protected=True))
        self.assertFalse((self.root / 'knowledge/index.md').exists())

    def test_reserved_index_directory_refused_without_initialization(self):
        (self.root / 'knowledge/index.md').mkdir(parents=True)
        before = self.snapshot(protected=True)
        self.cli('onboard', code=1)
        self.assertEqual(before, self.snapshot(protected=True))
        self.assertFalse((self.root / 'knowledge/log.md').exists())

    def test_empty_categories_are_not_inferred(self):
        for path in self.root.iterdir():
            if path.name not in ('.git', '.ai'):
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        self.git('add', '-A')
        self.git('commit', '-qm', 'empty source inventory')
        self.cli('onboard')
        text = (self.root / 'knowledge/project/architecture.md').read_text()
        self.assertIn('No candidates found.', text)
        self.assertNotIn('MUST', text)


if __name__ == '__main__':
    unittest.main()
