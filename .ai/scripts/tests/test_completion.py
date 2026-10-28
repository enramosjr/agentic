"""Completion consolidates blockers and never fabricates evidence or approval."""
import json
import shutil
import shlex
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lifecycle
import completion
from test_lifecycle import LifecycleCase


class CompletionTests(LifecycleCase):
    def test_sync_check_errors_are_completion_blockers(self):
        self.prepare_adopter()
        real_okf = completion.okf
        for output in ('', '{"violations": []}'):
            with self.subTest(output=output):
                def failing_okf(root, *args):
                    if args[0] == 'sync-check':
                        return subprocess.CompletedProcess(args, 1, output, 'inventory unavailable')
                    return real_okf(root, *args)
                with mock.patch.object(completion, 'okf', side_effect=failing_okf):
                    data = completion.report(self.repo, lifecycle.load(self.repo), [])
                self.assertFalse(data['ready_for_verify'])
                self.assertTrue(any('inventory unavailable' in b for b in data['blockers']), data)

    def finish(self, *args):
        code, out, err = self.run_cli('finish', '--json', *args)
        self.assertTrue(out.startswith('{'), out + err)
        return code, json.loads(out)

    def test_all_missing_gates_are_reported_together(self):
        self.ok('tier', 'L2', '--reason', 'missing gates')
        code, data = self.finish()
        self.assertEqual(code, 1)
        for text in ('intent', 'plan', 'review', 'retrospective'):
            self.assertTrue(any(text in b for b in data['blockers']), data)
        self.assertFalse(data['verified'])

    def prepare_adopter(self):
        scripts = Path(__file__).resolve().parents[1]
        shutil.copytree(scripts, self.repo / '.ai/scripts', ignore=shutil.ignore_patterns('tests', '__pycache__'))
        def okf(*argv):
            result = subprocess.run([sys.executable, str(self.repo / '.ai/scripts/okf.py'), *argv],
                                    cwd=self.repo, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        okf('init')
        okf('new', 'capabilities/greeting.md', '--type', 'Capability', '--title', 'Greeting',
            '--description', 'Greeting behavior', '--source', 'app.py')
        self.git('add', '-A')
        self.git('commit', '-qm', 'adopter baseline')
        self.ok('tier', 'L1', '--reason', 'greeting change')
        self.ok('stage', 'intent', '--note', 'change greeting; check actual output; local fixture')
        self.ok('stage', 'plan', '--note', 'change and verify')
        (self.repo / 'app.py').write_text("print('hello')\n")
        doc = self.repo / 'knowledge/capabilities/greeting.md'
        doc.write_text(doc.read_text() + '\nThe greeting prints hello.\n')
        self.ok('run', 'greeting', '--inputs', 'app.py', '--', sys.executable, '-c',
                'import subprocess,sys; assert subprocess.check_output([sys.executable,"app.py"],text=True).strip()=="hello"')
        self.ok('retrospect', '--no-new-lessons', 'fixture')
        return doc, okf

    def test_adopter_metadata_is_refreshed_only_with_explicit_scoped_evidence(self):
        self.prepare_adopter()
        code, data = self.finish()
        self.assertEqual(code, 1)
        self.assertTrue(any('knowledge' in b for b in data['blockers']))
        code, data = self.finish('--apply', '--bind', 'knowledge/capabilities/greeting.md=greeting')
        self.assertEqual(code, 0, data)
        self.assertTrue(data['verified'])
        self.assertEqual(len(lifecycle.load(self.repo)['ledger']), 1)
        self.assertTrue(data['actions'])

    def test_runtime_claim_cannot_be_renewed_by_reassigning_a_label(self):
        doc, okf = self.prepare_adopter()
        okf('set', 'capabilities/greeting.md', 'evidence=validated-runtime',
            'verified={by: "process:python3 .ai/scripts/lifecycle.py reuse greeting", at: "2026-10-27T00:00:00Z"}')
        (self.repo / 'app.py').write_text("print('broken greeting')\n")
        self.ok('run', 'greeting', '--inputs', 'app.py', '--', sys.executable, '-c', 'assert 1 == 1')
        before = doc.read_bytes()
        code, out, err = self.run_cli('finish', '--json', '--apply', '--bind',
                                     'knowledge/capabilities/greeting.md=greeting')
        self.assertEqual(code, 1, out + err)
        self.assertIn('original', out + err)
        self.assertEqual(doc.read_bytes(), before)

    def test_exact_runtime_command_binding_remains_reusable(self):
        doc, okf = self.prepare_adopter()
        command = lifecycle.load(self.repo)['ledger'][-1]['argv']
        okf('stamp', 'verified', 'capabilities/greeting.md', '--run', *command)
        okf('set', 'capabilities/greeting.md', 'evidence=validated-runtime')
        code, data = self.finish('--apply', '--bind', 'knowledge/capabilities/greeting.md=greeting')
        self.assertEqual(code, 0, data)
        result = subprocess.run([sys.executable, str(self.repo / '.ai/scripts/okf.py'),
                                 'show', 'capabilities/greeting.md', '--meta', '--json'],
                                cwd=self.repo, capture_output=True, text=True, check=True)
        tokens = shlex.split(json.loads(result.stdout)['meta']['verified']['by'].removeprefix('process:'))
        self.assertEqual(shlex.split(tokens[tokens.index('reuse') + 1]), command)

    def test_read_only_report_then_apply_existing_evidence_without_rerun(self):
        (self.repo / '.agentic.json').write_text('{"repository_kind":"framework"}')
        self.ok('tier', 'L1', '--reason', 'source completion')
        self.ok('stage', 'intent', '--note', 'goal; assert counter; no new tests on finish')
        self.ok('stage', 'plan', '--note', 'record and reuse')
        counter = self.repo / '.git' / 'counter'
        self.ok('run', 'check', '--', sys.executable, '-c',
                f'from pathlib import Path; p=Path({str(counter)!r}); p.write_text(str(int(p.read_text())+1) if p.exists() else "1")')
        self.ok('retrospect', '--no-new-lessons', 'fixture')
        before = lifecycle.load(self.repo)
        code, data = self.finish()
        self.assertEqual(code, 0, data)
        self.assertFalse(data['verified'])
        self.assertEqual(lifecycle.load(self.repo), before)
        code, data = self.finish('--apply')
        self.assertEqual(code, 0, data)
        self.assertTrue(data['verified'])
        self.assertEqual(counter.read_text(), '1')
        self.assertEqual(len(lifecycle.load(self.repo)['ledger']), 1)
        self.assertFalse((self.repo / 'knowledge').exists())

    def test_apply_cannot_invent_review_or_green_evidence(self):
        self.ok('tier', 'L2', '--reason', 'not approved')
        code, data = self.finish('--apply')
        self.assertEqual(code, 1)
        self.assertNotIn('review', lifecycle.load(self.repo)['stages'])
        self.assertNotIn('verify', lifecycle.load(self.repo)['stages'])
        self.assertFalse(data['verified'])


if __name__ == '__main__':
    unittest.main()
