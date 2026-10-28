"""Assurance STALE demo, increment 6 (specification-6.md R1-R6)."""
import ast
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))
import disk_tmp  # noqa: F401,E402
import assurance_demo  # noqa: E402
import lifecycle  # noqa: E402

LIMIT = 'VERIFIED covers only the declared command on its declared inputs.'
STEP = re.compile(r'^STEP (\d)/6 ([A-Z]+) - ', re.M)
FORCE_ALL = ('\n_orig = evaluate\n'
             'def evaluate(*a, **k):\n'
             '    r = _orig(*a, **k)\n'
             "    r['status'] = 'VERIFIED'\n"
             "    r['reason'] = 'forced'\n"
             '    return r\n')
FORCE_STALE = FORCE_ALL.replace("    r['status'] = 'VERIFIED'\n", "    if r['status'] == 'STALE':\n        r['status'] = 'VERIFIED'\n")
NETWORK = {'socket', 'ssl', 'http', 'urllib', 'ftplib', 'smtplib', 'xmlrpc', 'requests', 'telnetlib'}


def patcher(suffix):
    def prepare(repo):
        with open(repo / '.ai/scripts/assurance.py', 'a') as handle:
            handle.write(suffix)
    return prepare


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def demo(self, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        code = assurance_demo.run(base=self.base, out=out, err=err, **kwargs)
        return code, out.getvalue(), err.getvalue()


class BuildTests(Base):  # R1
    def test_repository_has_scripts_and_capability_and_is_removed(self):
        seen = {}

        def prepare(repo):
            seen['repo'] = repo
            seen['scripts'] = {p.name for p in (repo / '.ai/scripts').glob('*.py')}
            seen['capability'] = (repo / 'knowledge/capabilities/demo.md').read_text()
        code, out, err = self.demo(prepare=prepare)
        self.assertEqual(code, 0, err)
        self.assertLessEqual({'lifecycle.py', 'assurance.py', 'okf.py'}, seen['scripts'])
        self.assertIn('DEMO-R1', seen['capability'])
        self.assertIn('- Verify:', seen['capability'])
        self.assertIn('- Inputs:', seen['capability'])
        self.assertEqual(list(self.base.iterdir()), [])

    def test_only_git_okf_and_lifecycle_are_invoked_and_steps_are_lifecycle(self):
        real = subprocess.run
        argvs = []

        def spy(argv, *a, **k):
            argvs.append(list(argv))
            return real(argv, *a, **k)
        calls = []
        with mock.patch.object(assurance_demo.subprocess, 'run', spy):
            code, _, err = self.demo(calls=calls)
        self.assertEqual(code, 0, err)
        for argv in argvs:
            self.assertTrue(argv[0] == 'git' or Path(argv[1]).name in {'okf.py', 'lifecycle.py'}, argv)
        self.assertTrue(calls)
        for call in calls:
            self.assertTrue(call.startswith('python3 .ai/scripts/lifecycle.py '), call)

    def test_removed_after_step_failure_and_after_prepare_raises(self):
        code, out, err = self.demo(prepare=patcher(FORCE_ALL))
        self.assertEqual(code, 1)
        self.assertEqual(list(self.base.iterdir()), [])

        def boom(repo):
            raise RuntimeError('prepare failed')
        with self.assertRaises(RuntimeError):
            self.demo(prepare=boom)
        self.assertEqual(list(self.base.iterdir()), [])


class SequenceTests(unittest.TestCase):  # R2
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        out, err = io.StringIO(), io.StringIO()
        cls.code = assurance_demo.run(base=Path(cls.temp.name), out=out, err=err)
        cls.out, cls.err = out.getvalue(), err.getvalue()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_six_ordered_steps_with_real_statuses(self):
        self.assertEqual(self.code, 0, self.err)
        steps = STEP.findall(self.out)
        self.assertEqual([n for n, _ in steps], list('123456'))
        self.assertEqual([s for _, s in steps], ['UNVERIFIED', 'VERIFIED', 'VERIFIED', 'STALE', 'STALE', 'VERIFIED'])

    def test_stale_step_names_the_edited_input_and_changed_lists_the_obligation(self):
        blocks = re.split(r'(?m)^STEP ', self.out)
        step4 = next(b for b in blocks if b.startswith('4/6'))
        step5 = next(b for b in blocks if b.startswith('5/6'))
        self.assertIn('src/calc.py', step4)
        self.assertIn('DEMO-R1', step5)
        self.assertIn('--changed --base HEAD', step5)


class FailClosedTests(Base):  # R3
    def test_always_verified_fails_at_step_one_and_prints_nothing_false(self):
        code, out, err = self.demo(prepare=patcher(FORCE_ALL))
        self.assertEqual(code, 1)
        self.assertIn('step 1', err)
        self.assertIn('expected UNVERIFIED, observed VERIFIED', err)
        self.assertNotIn('STEP 1/6', out)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_stale_reported_as_verified_fails_at_step_four(self):
        code, out, err = self.demo(prepare=patcher(FORCE_STALE))
        self.assertEqual(code, 1)
        self.assertIn('step 4', err)
        self.assertIn('expected STALE, observed VERIFIED', err)
        self.assertIn('STEP 3/6', out)
        self.assertNotIn('STEP 4/6', out)


class LimitSentenceTests(Base):  # R5
    def test_last_line_on_success_and_absent_on_failure(self):
        code, out, err = self.demo()
        self.assertEqual(code, 0, err)
        self.assertEqual(out.rstrip('\n').splitlines()[-1], LIMIT)
        code, out, err = self.demo(prepare=patcher(FORCE_ALL))
        self.assertEqual(code, 1)
        self.assertNotIn(LIMIT, out + err)


def snapshot():
    state = lifecycle.state_path(ROOT, write=False)
    status = subprocess.run(['git', 'status', '--porcelain=v2', '-z'], cwd=ROOT, capture_output=True, check=True).stdout
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, check=True).stdout
    return status, head, state.read_bytes() if state.exists() else None


class IsolationTests(Base):  # R4
    def test_invoking_repository_is_untouched_and_no_network_modules(self):
        before = snapshot()
        probe = ('import json, sys\n'
                 f'sys.path.insert(0, {str(SCRIPTS)!r})\n'
                 'import assurance_demo\n'
                 'code = assurance_demo.main([])\n'
                 f'names = {sorted(NETWORK)!r}\n'
                 "print('NETMODS', json.dumps(sorted({m.split('.')[0] for m in sys.modules} & set(names))))\n"
                 'sys.exit(code)\n')
        env = {**os.environ, 'TMPDIR': str(self.base), 'PYTHONDONTWRITEBYTECODE': '1'}
        result = subprocess.run([sys.executable, '-c', probe], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(snapshot(), before)
        loaded = json.loads(re.search(r'^NETMODS (.*)$', result.stdout, re.M).group(1))
        self.assertEqual(set(loaded) - {'socket'}, set(), loaded)  # scratch may pull socket transitively
        tree = ast.parse((SCRIPTS / 'assurance_demo.py').read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
        self.assertEqual(imported & NETWORK, set())
        self.assertEqual(list(self.base.iterdir()), [])


class EndToEndTests(Base):  # R6
    def test_built_script_as_subprocess(self):
        env = {**os.environ, 'TMPDIR': str(self.base), 'PYTHONDONTWRITEBYTECODE': '1'}
        result = subprocess.run([sys.executable, str(SCRIPTS / 'assurance_demo.py')], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        steps = STEP.findall(result.stdout)
        self.assertEqual([s for _, s in steps], ['UNVERIFIED', 'VERIFIED', 'VERIFIED', 'STALE', 'STALE', 'VERIFIED'])
        self.assertEqual(result.stdout.rstrip('\n').splitlines()[-1], LIMIT)
        self.assertEqual(list(self.base.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
