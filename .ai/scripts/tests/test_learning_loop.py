"""Gap 6 contract tests: optional observations and human-approved project rules."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from test_lifecycle import LifecycleCase, SCRIPTS
import lifecycle
import okf
import learning


class LearningLoopTests(LifecycleCase):
    def setUp(self):
        super().setUp()
        shutil.copytree(SCRIPTS, self.repo / '.ai/scripts', ignore=shutil.ignore_patterns('tests', '__pycache__'))
        result = self.command('okf.py', 'init')
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.repo / 'knowledge/project/sync-ignore').write_text('*.py\n*.md\n')

    def command(self, script, *args, input=None, env=None):
        return subprocess.run([sys.executable, str(self.repo / '.ai/scripts' / script), *args],
                              cwd=self.repo, input=input, text=True, capture_output=True,
                              timeout=30, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', **(env or {})})

    def start(self, tier='L1'):
        self.ok('tier', tier, '--new', '--reason', 'learning fixture')
        return lifecycle.load(self.repo)

    def durable(self):
        state = lifecycle.load(self.repo)
        path = lifecycle.record_path(self.repo, state)
        return path, json.loads(path.read_text())

    def capture(self, text='When a check fails, inspect its cause.'):
        self.ok('learn', text)
        path, record = self.durable()
        return path.relative_to(self.repo).as_posix() + '#' + str(len(record['lessons']))

    def test_capture_contract(self):
        # R1: stage-independent at every durable tier; no text/evidence execution.
        self.fails('learn', 'lesson', message='active')
        self.start('L0')
        self.fails('learn', 'lesson', message='L0')
        for tier in ('L1', 'L2', 'L3'):
            self.start(tier)
            for stage in lifecycle.STAGES:
                self.ok('learn', '  inert $(touch forbidden)\n`code`  ', '--stage', stage,
                        '--evidence', '$(touch forbidden)')
            self.assertEqual(len(self.durable()[1]['lessons']), len(lifecycle.STAGES))
        self.fails('learn', ' \n ', message='blank')
        result = self.command('lifecycle.py', 'learn', 'x', '--stage', 'invalid')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.repo / 'forbidden').exists())
        state = lifecycle.load(self.repo)
        state['done'] = True
        lifecycle.save(self.repo, state)
        self.fails('learn', 'lesson', message='active')

    def test_stable_lesson_identity(self):
        # R2: exact UTF-8 text, stable one-based numbering, duplicate wording retained.
        self.start()
        text = '  When café fails, inspect.\n  '
        for n in (1, 2):
            output = self.ok('learn', text, '--stage', 'plan', '--evidence', 'issue:42')
            path, record = self.durable()
            lesson = record['lessons'][n-1]
            self.assertIn(path.relative_to(self.repo).as_posix() + f'#{n}', output)
            self.assertEqual(lesson['number'], n)
            self.assertEqual(lesson['text'], text)
            self.assertEqual(lesson['sha256'], hashlib.sha256(text.encode('utf-8')).hexdigest())
            self.assertEqual((lesson['stage'], lesson['evidence']), ('plan', 'issue:42'))
            self.assertRegex(lesson['at'], r'^\d{4}-\d\d-\d\dT.*Z$')
        self.ok('audit')

    def test_durable_recovery(self):
        # R3: stale saves and interrupted scratch publication cannot remove observations.
        self.start()
        stale = copy.deepcopy(lifecycle.load(self.repo))
        self.capture('first')
        lifecycle.save(self.repo, stale)
        self.assertEqual(len(self.durable()[1]['lessons']), 1)
        real_write = lifecycle.write_atomic
        def interrupted(path, data):
            if path == lifecycle.state_path(self.repo):
                raise OSError('injected scratch failure')
            return real_write(path, data)
        with mock.patch.object(lifecycle, 'write_atomic', side_effect=interrupted):
            code, out, err = self.run_cli('learn', 'second')
        self.assertEqual(code, 1, err)
        self.assertNotIn('recorded lesson', out)
        self.assertEqual([x['text'] for x in lifecycle.load(self.repo)['lessons']], ['first', 'second'])
        self.ok('stage', 'intent', '--note', 'preserve lessons')
        path, record = self.durable()
        conflict = copy.deepcopy(record)
        conflict['lessons'][0]['text'] = 'conflict'
        conflict['lessons'][0]['sha256'] = hashlib.sha256(b'conflict').hexdigest()
        lifecycle.state_path(self.repo).write_text(json.dumps(conflict))
        before = path.read_bytes()
        self.fails('learn', 'third', message='conflict')
        self.assertEqual(path.read_bytes(), before)
        lifecycle.state_path(self.repo).write_text(json.dumps(record))
        with mock.patch.object(lifecycle, 'write_atomic', side_effect=OSError('write failure')):
            code, out, _ = self.run_cli('learn', 'third')
        self.assertEqual(code, 1)
        self.assertEqual(path.read_bytes(), before)

    def test_verify_reminder(self):
        # R4: successful Verify reminds; failed gates still fail; no lesson prerequisite.
        for tier in ('L2', 'L3'):
            self.start(tier)
            self.fails('stage', 'verify', '--note', 'not ready', message='intent')
            self.ok('stage', 'intent', '--ref', 'spec.md', '--approved-by', 'human:fixture')
            self.ok('stage', 'plan', '--ref', 'plan.md')
            self.ok('stage', 'review', '--ref', 'review.md')
            self.converge_green()
            output = self.ok('stage', 'verify', '--note', 'fixture acceptance passed')
            self.assertIn('Optional', output)
            self.assertIn('learn', output)
            self.assertIn('verify', self.durable()[1]['stages'])
            self.capture()
            self.assertNotIn('Optional', self.ok('stage', 'verify', '--note', 'same fixture'))

    def test_learning_audit(self):
        # R10: legacy valid; malformed present lesson metadata fails closed.
        self.start()
        self.ok('audit')
        self.capture()
        path, record = self.durable()
        self.ok('audit')
        for value in (None, {}, [None], [dict(record['lessons'][0], number=2)],
                      [dict(record['lessons'][0], sha256='0'*64)]):
            damaged = dict(record, lessons=value)
            path.write_text(json.dumps(damaged))
            self.fails('audit', str(path), message='lesson')
        path.write_text(json.dumps(record))

        self.promote()
        valid = learning.read_rules(self.repo)
        rule = valid['rules'][0]
        for damaged in (dict(valid, rules=[rule, rule]),
                        dict(valid, rules=[dict(rule, status='unknown')]),
                        dict(valid, rules=[dict(rule, number=True)]),
                        dict(valid, rules=[dict(rule, approved_by='decision:ADR')]),
                        dict(valid, rules=[dict(rule, at='yesterday')]),
                        dict(valid, rules=[dict(rule, sha256='0'*64)])):
            self.rewrite_rules(damaged)
            self.assertNotEqual(self.command('okf.py', 'validate').returncode, 0)
        self.rewrite_rules(valid)

    def promote(self, ref=None):
        ref = ref or self.capture()
        output = self.ok('promote', ref, '--approved-by', 'human:fixture')
        rule = learning.read_rules(self.repo)['rules'][-1]
        self.assertIn(rule['id'], output)
        return rule

    def rewrite_rules(self, data):
        path = self.repo / 'knowledge/project/rules.md'
        okf.write_text(path, learning.replace_payload(path.read_text(), data))

    def test_promotion_approval(self):
        # R5: only anchored human claims; never implicit or ADR-based consent.
        self.start()
        ref = self.capture()
        for actor in (None, '', 'human:', 'decision:ADR1', 'human:x trailing', ' human:x', 'human:x\n'):
            args = ['promote', ref] + ([] if actor is None else ['--approved-by', actor])
            self.fails(*args, message='human:')
            self.assertFalse((self.repo / 'knowledge/project/rules.md').exists())
        self.promote(ref)
        self.assertEqual(self.command('okf.py', 'validate').returncode, 0)

    def test_promotion_identity(self):
        # R6: source-bound identity; duplicate retries and unsafe references fail safely.
        self.start()
        ref = self.capture('  exact café\n```\n[not a link](missing)  ')
        rule = self.promote(ref)
        path = self.repo / 'knowledge/project/rules.md'
        before = path.read_bytes()
        log = (self.repo / 'knowledge/log.md').read_bytes()
        self.promote(ref)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual((self.repo / 'knowledge/log.md').read_bytes(), log)
        self.assertEqual(rule['text'], self.durable()[1]['lessons'][0]['text'])
        record_path, record = self.durable()
        record['lessons'][0]['text'] = 'altered'
        record['lessons'][0]['sha256'] = learning.text_hash('altered')
        record_path.write_text(json.dumps(record))
        self.fails('promote', ref, '--approved-by', 'human:fixture', message='source')
        for unsafe in ('../outside.json#1', 'knowledge/history/lifecycle/../../other.json#1', ref.replace('#1', '#0')):
            result = self.command('lifecycle.py', 'promote', unsafe, '--approved-by', 'human:fixture')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_bytes(), before)
        outside = self.repo / 'outside.json'
        outside.write_text(json.dumps(record))
        link = record_path.parent / 'escape.json'
        link.symlink_to(outside)
        self.assertNotEqual(self.command('lifecycle.py', 'promote', str(link)+'#1', '--approved-by', 'human:fixture').returncode, 0)

    def test_rules_budget(self):
        # R7: complete block, exactly 8192 bytes, multibyte and refusal without mutation.
        self.start()
        ref = self.capture('a')
        self.promote(ref)
        data = learning.read_rules(self.repo)
        overhead = len(learning.render_active(data).encode('utf-8')) - 1
        size = 8192 - overhead
        path, record = self.durable()
        original_record = copy.deepcopy(record)
        original_rules = (self.repo / 'knowledge/project/rules.md').read_bytes()
        for extra in (0, 1):
            text = 'é' * (size // 2) + 'a' * (size % 2 + extra)
            record['lessons'][0].update(text=text, sha256=learning.text_hash(text))
            path.write_text(json.dumps(record))
            (self.repo / 'knowledge/project/rules.md').unlink()
            result = self.command('lifecycle.py', 'promote', ref, '--approved-by', 'human:fixture')
            self.assertEqual(result.returncode, extra, result.stderr)
            if not extra:
                self.assertEqual(len(learning.render_active(learning.read_rules(self.repo)).encode('utf-8')), 8192)
            else:
                self.assertFalse((self.repo / 'knowledge/project/rules.md').exists())
        path.write_text(json.dumps(original_record))
        (self.repo / 'knowledge/project/rules.md').write_bytes(original_rules)
        second = self.capture('large ' + 'é' * 5000)
        self.fails('promote', second, '--approved-by', 'human:fixture', message='8192')
        self.assertEqual((self.repo / 'knowledge/project/rules.md').read_bytes(), original_rules)

    def test_retirement(self):
        # R9: reason and human approval; immutable provenance and retry metadata.
        self.start()
        rule = self.promote()
        for args in ([], ['--approved-by', 'decision:ADR'], ['--approved-by', 'human:fixture', '--reason', ' ']):
            result = self.command('lifecycle.py', 'retire', rule['id'], *args)
            self.assertNotEqual(result.returncode, 0)
        self.ok('retire', rule['id'], '--reason', 'obsolete', '--approved-by', 'human:fixture')
        retired = learning.read_rules(self.repo)['rules'][0]
        for field in ('id', 'text', 'source', 'number', 'sha256', 'at', 'approved_by'):
            self.assertEqual(retired[field], rule[field])
        self.assertEqual(retired['status'], 'retired')
        before = (self.repo / 'knowledge/log.md').read_bytes()
        self.ok('retire', rule['id'], '--reason', 'obsolete', '--approved-by', 'human:fixture')
        self.assertEqual((self.repo / 'knowledge/log.md').read_bytes(), before)
        self.fails('retire', rule['id'], '--reason', 'changed', '--approved-by', 'human:fixture', message='conflict')
        self.assertNotIn(rule['text'], learning.render_active(learning.read_rules(self.repo)))

    def test_publication_retries(self):
        # R6 R9 R14: fail after rule/log publication, repair bookkeeping exactly once.
        self.start()
        ref = self.capture()
        with mock.patch.object(okf, 'append_log', side_effect=OSError('log write failure')):
            code, _, _ = self.run_cli('promote', ref, '--approved-by', 'human:fixture')
        self.assertEqual(code, 1)
        rule = learning.read_rules(self.repo)['rules'][0]
        self.promote(ref)
        marker = f'<!-- learning-loop:promote:{rule["id"]} -->'
        self.assertEqual((self.repo / 'knowledge/log.md').read_text().count(marker), 1)
        with mock.patch.object(okf, 'reindex', side_effect=OSError('index failure')):
            code, _, _ = self.run_cli('retire', rule['id'], '--reason', 'old', '--approved-by', 'human:fixture')
        self.assertEqual(code, 1)
        self.ok('retire', rule['id'], '--reason', 'old', '--approved-by', 'human:fixture')
        self.assertEqual((self.repo / 'knowledge/log.md').read_text().count(f'<!-- learning-loop:retire:{rule["id"]} -->'), 1)

    def test_session_start_rules(self):
        # R8: real hook adapters, no partial rule set on malformed/oversized input.
        self.start()
        payload = {'hook_event_name': 'SessionStart', 'cwd': str(self.repo)}
        baseline = self.command('lifecycle.py', 'hook', input=json.dumps(payload)).stdout
        rule = self.promote()
        for cursor in (False, True):
            result = self.command('lifecycle.py', 'hook', input=json.dumps(payload),)
            context = json.loads(result.stdout)['hookSpecificOutput']['additionalContext']
            if cursor:
                result = self.command('lifecycle.py', 'hook', input=json.dumps(dict(payload, hook_event_name='sessionStart', cursor_version='test')))
                context = json.loads(result.stdout)['additional_context']
            self.assertEqual(context.count(rule['text']), 1)
        data = learning.read_rules(self.repo)
        for damaged in ({'version': 99, 'rules': []}, dict(data, rules=[dict(rule, text='x'*9000, sha256=learning.text_hash('x'*9000))])):
            self.rewrite_rules(damaged)
            output = self.command('lifecycle.py', 'hook', input=json.dumps(payload)).stdout
            context = json.loads(output)['hookSpecificOutput']['additionalContext']
            self.assertIn('rules unavailable', context)
            self.assertNotIn(rule['text'], context)
        (self.repo / 'knowledge/project/rules.md').unlink()
        self.assertEqual(self.command('lifecycle.py', 'hook', input=json.dumps(payload)).stdout, baseline)
        self.test_bypassed_and_malformed_rule_context()
        self.test_malformed_rule_frontmatter()

    def test_rule_sources(self):
        # R11: absent record warns; existing corrupt/mismatched provenance errors.
        self.start()
        self.promote()
        path, record = self.durable()
        path.unlink()
        result = self.command('okf.py', 'validate', '--json')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        issues = json.loads(result.stdout)
        self.assertTrue(any(x['level'] == 'warning' and 'source record' in x['message'] for x in issues))
        self.assertEqual(self.command('okf.py', 'validate', '--strict').returncode, 1)
        path.write_text(json.dumps(dict(record, lessons=[])))
        self.assertEqual(self.command('okf.py', 'validate').returncode, 1)
        record['lessons'][0]['sha256'] = '0'*64
        path.write_text(json.dumps(record))
        self.assertEqual(self.command('okf.py', 'validate').returncode, 1)

    def test_checkpoint_retro(self):
        # R12: selection, deduplication, JSON/text parity, retired promotions stay promoted.
        self.start()
        first = self.capture('first record')
        rule = self.promote(first)
        self.ok('retire', rule['id'], '--reason', 'old', '--approved-by', 'human:fixture')
        unpromoted = self.capture('unpromoted first')
        self.start()
        second = self.capture('second record')
        self.start()
        self.capture('unrelated')
        paths = [first.split('#')[0], second.split('#')[0], './'+first.split('#')[0]]
        args = [item for path in paths for item in ('--lessons-from', path)]
        result = self.command('okf.py', 'checkpoint', '--json', *args)
        data = json.loads(result.stdout)
        self.assertEqual([x['reference'] for x in data['lessons']], [unpromoted, second])
        text = self.command('okf.py', 'checkpoint', *args).stdout
        for row in data['lessons']:
            self.assertIn(row['reference'], text)
            self.assertIn(row['text'], text)
        ordinary = json.loads(self.command('okf.py', 'checkpoint', '--json').stdout)
        self.assertNotIn('lessons', ordinary)
        self.assertEqual(data['safe'], ordinary['safe'])
        self.assertNotEqual(self.command('okf.py', 'checkpoint', '--lessons-from', 'missing').returncode, 0)
        self.test_malformed_selected_record()

    def test_orchestrator_retro_contract(self):
        # R13: actual checkpoint selection plus standing milestone-close instructions.
        for name in ('agents/orchestrator.md', 'autonomous-execution.md'):
            text = (SCRIPTS.parent / name).read_text()
            self.assertIn('--lessons-from', text)
            self.assertIn('unpromoted', text)
        self.test_checkpoint_retro()

    def test_malformed_selected_record(self):
        # R12: a safety failure must not conceal accepting a malformed selected record.
        self.start()
        ref = self.capture()
        path, record = self.durable()
        record['stages'] = {'intent': None}
        path.write_text(json.dumps(record))
        with self.assertRaises(learning.LearningError):
            learning.retrospective(self.repo, [ref.split('#')[0]])

    def test_bypassed_and_malformed_rule_context(self):
        # R8: autonomous/disabled guards still receive rules; malformed OKF cannot inject.
        self.start()
        rule = self.promote()
        payload = json.dumps({'hook_event_name': 'SessionStart', 'cwd': str(self.repo)})
        for env in ({'OKF_AUTONOMOUS': '1'}, {'LIFECYCLE_GUARD': 'off'}):
            result = self.command('lifecycle.py', 'hook', input=payload, env=env)
            self.assertIn(rule['text'], result.stdout)
            edit = json.dumps(self.edit())
            self.assertEqual(self.command('lifecycle.py', 'hook', input=edit, env=env).stdout, '')
    def test_malformed_rule_frontmatter(self):
        # R8 R14: malformed metadata invalidates even a schema-valid JSON payload.
        self.start()
        rule = self.promote()
        payload = json.dumps({'hook_event_name': 'SessionStart', 'cwd': str(self.repo)})
        path = self.repo / 'knowledge/project/rules.md'
        raw = path.read_text()
        for text in (raw.split('---\n', 2)[2], raw.replace('type: Development Guide', 'type: [broken')):
            path.write_text(text)
            output = self.command('lifecycle.py', 'hook', input=payload).stdout
            self.assertIn('rules unavailable', output)
            self.assertNotIn(rule['text'], output)

    def test_documented_contract(self):
        # R14: precedence, workflow, valid operation records, exact-once logging.
        root = SCRIPTS.parents[1]
        agents = (root / 'AGENTS.md').read_text()
        self.assertIn('approved project rules', agents)
        for name in ('knowledge/capabilities/learning-loop.md', 'knowledge/playbooks/learning-loop.md'):
            text = (root / name).read_text()
            for phrase in ('learn', 'promote', 'retire', '--lessons-from', '8,192'):
                self.assertIn(phrase, text)
        self.start()
        ref = self.capture()
        rule = self.promote(ref)
        self.promote(ref)
        self.assertEqual((self.repo / 'knowledge/log.md').read_text().count(f'<!-- learning-loop:promote:{rule["id"]} -->'), 1)
        self.assertEqual(self.command('okf.py', 'records').returncode, 0)

    def connected_flow(self):
        tier = self.command('lifecycle.py', 'tier', 'L1', '--new', '--reason', 'connected fixture')
        self.assertEqual(tier.returncode, 0, tier.stderr)
        text = 'When café changes, verify exact output.'
        result = self.command('lifecycle.py', 'learn', text)
        self.assertEqual(result.returncode, 0, result.stderr)
        ref = result.stdout.strip().removeprefix('recorded lesson ')
        source, record, lesson = learning.lesson_reference(self.repo, ref)
        self.assertEqual(lesson['text'], text)
        self.assertEqual(lesson['sha256'], learning.text_hash(text))
        self.assertEqual(self.command('lifecycle.py', 'audit', source).returncode, 0)
        result = self.command('lifecycle.py', 'promote', ref, '--approved-by', 'human:fixture')
        self.assertEqual(result.returncode, 0, result.stderr)
        rule = learning.read_rules(self.repo)['rules'][0]
        payload = json.dumps({'hook_event_name': 'SessionStart', 'cwd': str(self.repo)})
        def context():
            output = self.command('lifecycle.py', 'hook', input=payload)
            self.assertEqual(output.returncode, 0, output.stderr)
            return json.loads(output.stdout)['hookSpecificOutput']['additionalContext']
        self.assertEqual(context().count(text), 1)
        retired = self.command('lifecycle.py', 'retire', rule['id'], '--reason', 'superseded', '--approved-by', 'human:fixture')
        self.assertEqual(retired.returncode, 0, retired.stderr)
        self.assertNotIn(text, context())
        self.assertEqual(learning.read_rules(self.repo)['rules'][0]['status'], 'retired')
        result = self.command('lifecycle.py', 'learn', 'unpromoted observation')
        self.assertEqual(result.returncode, 0, result.stderr)
        retro = json.loads(self.command('okf.py', 'checkpoint', '--json', '--lessons-from', source).stdout)
        self.assertEqual([x['text'] for x in retro['lessons']], ['unpromoted observation'])
        records = self.command('okf.py', 'records')
        self.assertEqual(records.returncode, 0, records.stdout + records.stderr)

    def test_connected_cli_flow(self):
        # R1-R14: public subprocess flow, independent of in-process mocks.
        self.connected_flow()

    def test_installed_learning_flow(self):
        # R1-R14: shipped kit, no copied template knowledge, then adopter-owned rules.
        target = self.repo / 'adopter'
        target.mkdir()
        subprocess.run(['git', 'init', '-q', str(target)], check=True)
        installed = subprocess.run([sys.executable, str(SCRIPTS / 'install.py'), str(target)],
                                   text=True, capture_output=True, timeout=45)
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.assertTrue((target / '.ai/scripts/learning.py').is_file())
        self.assertFalse((target / 'knowledge/project/rules.md').exists())
        self.assertFalse((target / 'knowledge/specifications/learning-loop.md').exists())
        self.repo = target
        self.connected_flow()


if __name__ == '__main__':
    unittest.main()
