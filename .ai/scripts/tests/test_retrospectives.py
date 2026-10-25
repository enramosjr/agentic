"""Required retrospective acceptance checks, R1–R7, through the lifecycle CLI."""
import copy
import json
import shutil
import subprocess
import sys
import unittest
from unittest import mock

import test_learning_loop as fixtures
from test_lifecycle import LifecycleCase, SCRIPTS
import learning
import lifecycle


class RetrospectiveTests(LifecycleCase):
    def setUp(self):
        super().setUp()
        shutil.copytree(SCRIPTS, self.repo / '.ai/scripts', ignore=shutil.ignore_patterns('tests', '__pycache__'))
        result = self.command('okf.py', 'init')
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.repo / 'knowledge/project/sync-ignore').write_text('*.py\n*.md\n')

    command = fixtures.LearningLoopTests.command
    start = fixtures.LearningLoopTests.start
    durable = fixtures.LearningLoopTests.durable
    capture = fixtures.LearningLoopTests.capture
    promote = fixtures.LearningLoopTests.promote
    rewrite_rules = fixtures.LearningLoopTests.rewrite_rules

    def test_required_gate(self):
        # R1: closure independently gates Verify, commit and Ship, including legacy Verify.
        self.start()
        self.ok('stage', 'intent', '--note', 'gate test')
        self.ok('stage', 'plan', '--note', 'verify closure')
        self.fails('stage', 'verify', '--note', 'focused tests passed', message='retrospect')
        path, state = self.durable()
        self.assertNotIn('verify', state['stages'])
        state['stages']['verify'] = {'level': 'L1', 'at': lifecycle.now()}
        lifecycle.save(self.repo, state)
        self.fails('stage', 'ship', '--note', 'delivery', message='retrospect')
        self.assertIn('retrospect', self.hook({'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
                         'tool_input': {'command': 'git commit -am done'}, 'cwd': str(self.repo)}))
        for tier in ('L1', 'L2', 'L3'):
            self.start(tier)
            state = lifecycle.load(self.repo)
            state['stages'] = {s: {'level': tier, 'at': lifecycle.now(), 'ref': 'spec.md'}
                               for s in ('intent', 'plan', 'review', 'verify')}
            for target in ('verify', 'commit', 'ship'):
                self.assertIn('retrospect', lifecycle.gate_problem(state, target))
            self.ok('learn', 'captured alone', '--evidence', 'test passed')
            state['lessons'] = lifecycle.load(self.repo)['lessons']
            self.assertIn('retrospect', lifecycle.gate_problem(state, 'commit'))
            self.ok('retrospect', '--no-new-lessons', 'No reusable finding in this task.')
            state['retrospective'] = lifecycle.load(self.repo)['retrospective']
            self.assertIsNone(lifecycle.gate_problem(state, 'commit'))
        self.start('L0')
        self.assertIsNone(lifecycle.gate_problem(lifecycle.load(self.repo), 'commit'))

    def test_evidence(self):
        # R2: active task numbers and nonblank evidence, never executed.
        self.start()
        self.ok('learn', 'without evidence')
        self.fails('retrospect', '--lessons', '1', message='evidence')
        self.fails('retrospect', '--lessons', '2', message='lesson')
        self.fails('retrospect', '--no-new-lessons', ' ', message='nonblank')
        self.ok('learn', 'inert lesson', '--evidence', '$(touch forbidden)')
        self.ok('retrospect', '--lessons', '2')
        self.assertEqual(self.durable()[1]['retrospective']['lessons'], [2])
        self.assertFalse((self.repo / 'forbidden').exists())

    def test_durability(self):
        # R3: stale scratch, idempotent retry and conflicting closure.
        self.start()
        stale = copy.deepcopy(lifecycle.load(self.repo))
        real_write = lifecycle.write_atomic
        def interrupted(path, data):
            if path == lifecycle.state_path(self.repo):
                raise OSError('scratch failure')
            real_write(path, data)
        with mock.patch.object(lifecycle, 'write_atomic', side_effect=interrupted):
            code, out, _ = self.run_cli('retrospect', '--no-new-lessons', 'No new learning.')
        self.assertEqual(code, 1)
        self.assertNotIn('retrospective recorded', out)
        lifecycle.save(self.repo, stale)
        before = self.durable()[1]['retrospective']
        self.ok('retrospect', '--no-new-lessons', 'No new learning.')
        self.assertEqual(self.durable()[1]['retrospective'], before)
        self.fails('retrospect', '--no-new-lessons', 'different reason', message='conflict')

    def test_retrieval(self):
        # R4: lexical relevance, fallback, provenance, bounds and no writes.
        self.start()
        for n in range(7):
            self.ok('learn', f'lesson {n}', '--evidence', 'CLI passing')
        self.ok('learn', 'unicode ' + 'é' * 5000, '--evidence', 'large')
        self.ok('learn', 'scratch restoration matters', '--evidence', 'recovery passed')
        path, _ = self.durable()
        before = path.read_bytes()
        output = self.ok('observations', '--query', 'scratch restoration')
        self.assertLessEqual(len(output.encode('utf-8')), 8192)
        self.assertIn('scratch restoration matters', output)
        self.assertIn(str(path.relative_to(self.repo)) + '#9', output)
        self.assertIn('recovery passed', output)
        self.assertLessEqual(output.count('Source:'), 5)
        self.assertIn('recent fallback', self.ok('observations', '--query', 'unmatched'))
        self.assertIn('Omitted', self.ok('observations'))
        self.assertEqual(before, path.read_bytes())
        self.assertIn('scratch restoration matters', self.ok('tier', 'L1', '--new', '--reason', 'scratch restoration'))
        # Multiple records: overlap beats recency; equal timestamps use stable references.
        template = json.loads(before)
        references = []
        for task, at in (('rank-a', '2002-01-01T00:00:00Z'), ('rank-b', '2002-01-01T00:00:00Z'),
                         ('rank-c', '2003-01-01T00:00:00Z')):
            entry = dict(template['lessons'][0], number=1, text='rankfixture',
                         sha256=learning.text_hash('rankfixture'), at=at)
            row = dict(template, task=task, lessons=[entry])
            target = path.parent / (task + '.json')
            target.write_text(json.dumps(row))
            references.append(str(target.relative_to(self.repo)) + '#1')
        first = self.ok('observations', '--query', 'rankfixture')
        self.assertEqual(first, self.ok('observations', '--query', 'rankfixture'))
        self.assertLess(first.index(references[2]), first.index(references[0]))
        self.assertLess(first.index(references[0]), first.index(references[1]))

    def test_authority(self):
        # R5: advisory context does not promote observations or alter approved rules.
        self.start()
        self.ok('learn', 'Avoid missing evidence', '--evidence', 'test:42')
        self.ok('retrospect', '--lessons', '1')
        self.assertIn('advisory', self.ok('observations'))
        self.assertFalse((self.repo / 'knowledge/project/rules.md').exists())
        self.fails('promote', str(self.durable()[0].relative_to(self.repo))+'#1', message='human:')

    def test_compatibility(self):
        # R6: absent closure legacy-valid, malformed closure fails with attributable diagnostics.
        self.start()
        self.capture('legacy observation')
        path, record = self.durable()
        self.ok('audit')
        self.promote(str(path.relative_to(self.repo))+'#1')
        for bad in (None, {}, {'outcome': 'unknown', 'at': lifecycle.now()},
                    {'outcome': 'observations', 'at': lifecycle.now(), 'lessons': [True]}):
            path.write_text(json.dumps(dict(record, retrospective=bad)))
            self.fails('audit', str(path), message='retrospective')
        output = self.ok('observations')
        self.assertIn(path.name, output)
        context = lifecycle.project_rules_context(self.repo)
        self.assertIn('Approved project rules', context)
        output = self.hook({'hook_event_name': 'SessionStart', 'cwd': str(self.repo)})
        self.assertIn('Approved project rules', output)
        self.assertIn(path.name, output)
        for command in ('git commit -am done', 'gh pr create --title done'):
            output = self.hook({'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
                                'tool_input': {'command': command}, 'cwd': str(self.repo)})
            self.assertTrue(self.denied(output), output)
            self.assertIn('retrospective', output)
        output = self.hook(self.edit())
        self.assertTrue(self.denied(output), output)

    def test_installed_flow(self):
        # R7: real kit installation, with adopter-owned state rather than imported knowledge.
        target = self.repo / 'adopter'
        target.mkdir()
        subprocess.run(['git', 'init', '-q', str(target)], check=True)
        result = subprocess.run([sys.executable, str(SCRIPTS / 'install.py'), str(target)],
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((target / 'knowledge/project/rules.md').exists())
        self.assertFalse((target / 'knowledge/specifications/required-retrospectives.md').exists())
        self.assertFalse((target / 'knowledge/history/lifecycle').exists())
        self.assertIn('retrospect', (target / '.ai/lifecycle.md').read_text())
        self.repo = target
        self.git('add', '-A')
        self.git('commit', '-qm', 'installed kit')
        for argv in (('tier', 'L1', '--new', '--reason', 'installed packaging'),
                     ('stage', 'intent', '--note', 'prove installed gate'),
                     ('stage', 'plan', '--note', 'close and retrieve')):
            result = self.command('lifecycle.py', *argv)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = self.command('lifecycle.py', 'stage', 'verify', '--note', 'installed checks')
        self.assertEqual(result.returncode, 1)
        self.assertIn('retrospect', result.stderr + result.stdout)
        result = self.command('lifecycle.py', 'learn', 'packaging pitfall', '--evidence', 'installed CLI passed')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.command('lifecycle.py', 'retrospect', '--lessons', '1')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.command('lifecycle.py', 'stage', 'verify', '--note', 'installed closure and gate PASS')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = self.command('lifecycle.py', 'tier', 'L1', '--new', '--reason', 'packaging')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('packaging pitfall', result.stdout)
        for env in ({}, {'LIFECYCLE_GUARD': 'off'}, {'OKF_AUTONOMOUS': '1'}):
            result = self.command('lifecycle.py', 'hook', input=json.dumps({'hook_event_name': 'SessionStart', 'cwd': str(self.repo)}), env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('packaging pitfall', result.stdout)
            self.assertIn('advisory', result.stdout)
            self.assertIn('observations --query', result.stdout)


if __name__ == '__main__':
    unittest.main()
