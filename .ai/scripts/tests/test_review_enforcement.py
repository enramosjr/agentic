"""Mechanical review R1-R8: leases, native capture and advancement boundaries."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from test_assurance import Case
import review_guard as guard


class GuardCase(Case):
    def journal(self):
        return guard.read(self.root)

    def observed(self, adapter='claude', session='parent'):
        guard.observe_session(self.root, adapter, {'session_id': session,
            'hook_event_name': 'SessionStart', 'cwd': str(self.root)})

    def enabled(self, adapter='claude'):
        self.observed(adapter)
        guard.enable(self.root, 'task', adapter, 'parent', 'docs/pending.md')

    def started(self, adapter='claude'):
        self.enabled(adapter)
        guard.start(self.root, 'task', adapter, 'parent', 'child', 'reviewer',
                    {'source': 'frozen', 'converge': {'at': 'before'}}, [{'entry': 'reviewed'}])


REPORT = ('# Review Report\n\n## Verdict\n\nApproved\n\n## Scope\n\nTask.\n\n'
          '## Persona Applied\n\nPython.\n\n## Findings\n\nNone.\n\n'
          '## Validation Reviewed\n\nR1 passed.\n\n## Residual Risks\n\nNone.\n')


class NativeCase(GuardCase):
    def prepare_native(self, adapter, *, enable=True):
        import review_native as native
        self.native = native
        self.adapter = adapter
        config = '.claude/settings.json' if adapter == 'claude' else '.codex/hooks.json'
        hooks = {event: [{'hooks': [{'type': 'command', 'command':
                  f'python3 .ai/scripts/review_native.py hook --adapter {adapter}'}]}]
                 for event in ('SessionStart', 'SubagentStart', 'SubagentStop', 'PreToolUse', 'PostToolUse')}
        self.write(config, json.dumps({'hooks': hooks}))
        self.write('docs/spec.md', '# Task\n\n## Requirements\n- R1: Tool MUST pass.\n'
                   '## Acceptance\n- R1: `python3 -V` passes.\n'
                   '## Non-goals\nOther work.\n## Open questions\nNone.\n')
        self.write('docs/plan.md', '# Plan\nR1: implement and check.\n')
        self.lc('tier', 'L2', '--reason', 'native fixture')
        self.lc('stage', 'intent', '--ref', 'docs/spec.md', '--approved-by', 'human:test')
        self.lc('stage', 'plan', '--ref', 'docs/plan.md')
        self.lc('converge', 'docs/spec.md')
        self.event('SessionStart')
        if enable:
            self.lc('review', 'enable', '--adapter', adapter, '--session', 'parent',
                    '--report', 'knowledge/history/reviews/native.md')

    def event(self, name, **extra):
        payload = {'hook_event_name': name, 'session_id': 'parent', 'cwd': str(self.root), **extra}
        # Synthetic native callbacks test the adapter contract, not real runtime delivery.
        return self.native.handle(self.root, self.adapter, payload, guard.identity())


    def exercise_capture(self, adapter):
        import lifecycle
        self.prepare_native(adapter)
        self.cli('okf.py', 'records')
        before = self.git('status', '--porcelain')
        self.event('SubagentStart', agent_id='child', agent_type='reviewer')
        self.lc('run', 'blocked', '--', 'python3', '-V', code=1)
        self.event('SubagentStop', agent_id='child', agent_type='reviewer', last_assistant_message=REPORT)
        self.assertEqual(self.git('status', '--porcelain'), before)
        path = self.root / 'knowledge/history/reviews/native.md'
        metadata = self.native.metadata(path.read_text())
        self.lc('review', 'save-report')
        self.assertEqual(self.native.metadata(path.read_text()), metadata)
        self.assertEqual(lifecycle.ref_hash(path), guard.report_hash(REPORT))
        self.cli('okf.py', 'records')
        self.lc('stage', 'review', '--ref', str(path.relative_to(self.root)))
        self.lc('run', 'validation', '--', 'python3', '-V')
        self.assertIsNone(guard.evidence_problem(self.root, lifecycle.load(self.root)))


class ActivationTests(NativeCase):  # R1
    def native_command(self, action, **extra):
        from contextlib import redirect_stdout
        import argparse
        import io
        from unittest import mock
        import lifecycle
        output = io.StringIO()
        report = extra.pop('report', 'knowledge/history/reviews/native.md')
        args = argparse.Namespace(action=action, adapter='codex', session='parent', report=report, **extra)
        with mock.patch.object(lifecycle, 'repo_root', return_value=self.root), redirect_stdout(output):
            code = self.native.command(args)
        return code, output.getvalue()

    def test_inaccessible_host_registration_remains_discoverable_without_alive_claim(self):
        from unittest import mock
        self.prepare_native('codex', enable=False)
        # Native hooks see the host PID; the command's PID namespace may not.
        with mock.patch.object(guard, 'stopped', return_value=True):
            code, output = self.native_command('status')
        value = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(value['observed_sessions'], [{'adapter': 'codex', 'session': 'parent'}])
        self.assertEqual(value['runtime_liveness'], 'not_assessed')
        self.assertIsNone(value['phase'])

    def test_inaccessible_host_allows_only_pending_enable_and_restart(self):
        from unittest import mock
        import lifecycle
        self.prepare_native('codex', enable=False)
        runtime = {'pid': 2147483646, 'birth': 'host-namespace-birth'}
        self.native.handle(self.root, 'codex', {'hook_event_name': 'SessionStart',
            'session_id': 'parent', 'cwd': str(self.root)}, runtime)
        original_stopped = guard.stopped
        # Only the registered host is invisible; the local producer lease is live.
        with mock.patch.object(guard, 'stopped', side_effect=lambda process:
                               True if process == runtime else original_stopped(process)):
            self.assertEqual(self.native_command('enable')[0], 0)
            self.native_command('abandon', reason='fresh retry requires new capture')
            self.assertEqual(self.native_command('restart',
                report='knowledge/history/reviews/restarted.md')[0], 0)
        state = lifecycle.load(self.root)
        self.assertNotIn('review', state['stages'])
        self.assertNotIn('verify', state['stages'])
        self.assertIsNotNone(self.native.problem(self.root, state))
        self.assertIsNone(self.journal()['interval'])
        self.lc('stage', 'review', '--ref', 'knowledge/history/reviews/restarted.md', code=1)
        self.lc('stage', 'verify', code=1)

    def test_pending_activation_still_requires_complete_observed_identity_and_configuration(self):
        self.prepare_native('codex', enable=False)
        observed = self.journal()['sessions']['codex:parent']
        variants = [None, {}, {'pid': 0, 'birth': 'birth'}, {'pid': '123', 'birth': 'birth'},
                    {'pid': True, 'birth': 'birth'}, {'pid': os.getpid(), 'birth': None}]
        for runtime in variants:
            with self.subTest(runtime=runtime):
                with guard.transaction(self.root) as value:
                    value['sessions']['codex:parent'] = {**observed, 'runtime': runtime}
                with self.assertRaises(guard.ReviewError):
                    self.native_command('enable')
        with guard.transaction(self.root) as value:
            value['sessions']['codex:parent'] = {**observed, 'configuration': 'different'}
        with self.assertRaisesRegex(guard.ReviewError, 'configuration'):
            self.native_command('enable')
        with guard.transaction(self.root) as value:
            value['sessions'].clear()
        with self.assertRaisesRegex(guard.ReviewError, 'not observed'):
            self.native_command('enable')

    def test_missing_journal_before_capture_cannot_become_legacy_review(self):
        self.prepare_native('claude')
        (guard.directory(self.root) / 'journal.json').unlink()
        self.write('knowledge/history/reviews/native.md', REPORT)
        result = self.lc('stage', 'review', '--ref', 'knowledge/history/reviews/native.md', code=1)
        self.assertIn('journal', result.stderr)

    def test_cli_parent_report_cannot_substitute_for_native_capture(self):
        import lifecycle
        self.prepare_native('claude')
        self.write('knowledge/history/reviews/native.md', REPORT)
        result = self.lc('stage', 'review', '--ref', 'knowledge/history/reviews/native.md', code=1)
        self.assertIn('mechanical', result.stderr)
        self.assertNotIn('review', lifecycle.load(self.root)['stages'])
    def test_enable_requires_observed_session_and_supported_adapter(self):
        with self.assertRaisesRegex(guard.ReviewError, 'observed'):
            guard.enable(self.root, 'task', 'claude', 'invented', 'docs/pending.md')
        with self.assertRaisesRegex(guard.ReviewError, 'adapter'):
            guard.observe_session(self.root, 'other', {'session_id': 'parent'})
        self.enabled()
        self.assertEqual(self.journal()['request']['phase'], 'awaiting-native-review')
        self.assertIsNotNone(guard.qualification_problem(self.root, 'task', {}, REPORT))

    def test_missing_native_identity_cannot_register(self):
        with self.assertRaises(guard.ReviewError):
            guard.observe_session(self.root, 'codex', {'cwd': str(self.root)})


class IntervalTests(NativeCase):  # R2
    def test_concurrent_native_starts_have_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        self.enabled()
        ready = threading.Barrier(2)
        def attempt(child):
            ready.wait(timeout=5)
            try:
                guard.start(self.root, 'task', 'claude', 'parent', child, 'reviewer', {}, [])
                return 'started'
            except guard.ReviewError:
                return 'refused'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, ['one', 'two']))
        self.assertEqual(sorted(outcomes), ['refused', 'started'])
    def test_replaced_native_host_cannot_complete_original_review(self):
        self.prepare_native('codex')
        self.event('SubagentStart', agent_id='child', agent_type='reviewer')
        replaced = {'pid': os.getpid(), 'birth': 'different-birth'}
        payload = {'hook_event_name': 'SessionStart', 'session_id': 'parent', 'cwd': str(self.root)}
        with self.assertRaisesRegex(guard.ReviewError, 'runtime'):
            self.native.handle(self.root, 'codex', payload, replaced)
        payload.update(hook_event_name='SubagentStop', agent_id='child', agent_type='reviewer',
                       last_assistant_message=REPORT)
        with self.assertRaises(guard.ReviewError):
            self.native.handle(self.root, 'codex', payload, replaced)
        self.assertEqual(guard.read(self.root)['interval']['phase'], 'active')
    def test_start_binds_identity_and_pins_without_workspace_effects(self):
        self.enabled('codex')
        before = self.git('status', '--porcelain')
        pins = {'source': 'frozen'}
        guard.start(self.root, 'task', 'codex', 'parent', 'child', 'reviewer', pins, [])
        self.assertEqual(self.git('status', '--porcelain'), before)
        interval = self.journal()['interval']
        self.assertEqual(interval['pins'], pins)
        self.assertEqual(interval['child'], 'child')
        with self.assertRaisesRegex(guard.ReviewError, 'overlap'):
            guard.start(self.root, 'task', 'codex', 'parent', 'other', 'reviewer', pins, [])

    def test_live_writer_prevents_start(self):
        self.enabled()
        with guard.producer(self.root):
            with self.assertRaisesRegex(guard.ReviewError, 'producer'):
                guard.start(self.root, 'task', 'claude', 'parent', 'child', 'reviewer', {}, [])


class CaptureTests(NativeCase):  # R4
    def test_claude_cli_capture(self):
        self.exercise_capture('claude')

    def test_codex_cli_capture(self):
        self.exercise_capture('codex')

    def test_both_adapters_capture_complete_actual_body(self):
        for adapter in ('claude', 'codex'):
            with self.subTest(adapter=adapter):
                self.observed(adapter, adapter)
                guard.enable(self.root, adapter, adapter, adapter, f'docs/{adapter}.md')
                pins = {'source': 'same'}
                guard.start(self.root, adapter, adapter, adapter, 'child', 'reviewer', pins, [])
                guard.stop(self.root, adapter, adapter, adapter, 'child', REPORT, pins)
                self.assertEqual(self.journal()['interval']['report'], REPORT)
                self.assertIsNone(guard.qualification_problem(self.root, adapter, pins, REPORT))

    def test_malformed_or_changed_completion_never_qualifies(self):
        self.started()
        with self.assertRaisesRegex(guard.ReviewError, 'canonical'):
            guard.stop(self.root, 'task', 'claude', 'parent', 'child', 'Approved',
                       {'source': 'frozen', 'converge': {'at': 'before'}})
        self.assertEqual(self.journal()['interval']['phase'], 'failed')
        self.assertIsNotNone(guard.qualification_problem(self.root, 'task', {}, 'Approved'))


class PreservationTests(NativeCase):  # R5
    def test_cli_rejects_modified_saved_body_and_metadata(self):
        self.exercise_capture('claude')
        path = self.root / 'knowledge/history/reviews/native.md'
        original = path.read_text()
        header = self.native.metadata(original)
        path.write_text(header + '\n\nParent summary\n' + REPORT)
        self.lc('stage', 'review', '--ref', str(path.relative_to(self.root)), code=1)
        self.lc('review', 'save-report', code=1)
        path.write_text(original.replace('type: Review', 'type: Other'))
        self.assertIn('report_metadata', self.lc('review', 'save-report', code=1).stderr)
    def test_exact_body_hash_semantics_and_parent_reconstruction_rejected(self):
        self.started()
        pins = self.journal()['interval']['pins']
        guard.stop(self.root, 'task', 'claude', 'parent', 'child', REPORT, pins)
        self.assertIsNone(guard.qualification_problem(self.root, 'task', pins,
                                                     '---\ntype: Review\n---\n' + REPORT))
        for changed in ('prefix\n' + REPORT, REPORT.replace('Approved', 'Changes requested'),
                        '# Review Report\n\n## Verdict\nApproved\n'):
            self.assertIsNotNone(guard.qualification_problem(self.root, 'task', pins, changed))


class FreshnessTests(NativeCase):  # R6
    def test_commit_global_config_and_effective_target_env_refuse(self):
        import review_native
        for command in ('git -c core.worktree=/other commit -am test',
                        'git --config-env=core.worktree=TARGET commit -am test'):
            self.assertFalse(review_native.full_index_commit(command), command)
        self.assertFalse(review_native.full_index_commit('git commit -m test',
            {'GIT_INDEX_FILE': '/other/index'}))

    def test_commit_environment_config_cannot_select_another_tree(self):
        import review_native
        values = {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.worktree',
                  'GIT_CONFIG_VALUE_0': '/other'}
        self.assertFalse(review_native.full_index_commit('git commit -am test', values))
        self.assertFalse(review_native.full_index_commit(
            'env GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.worktree GIT_CONFIG_VALUE_0=/other git commit -am test'))
        self.assertFalse(review_native.full_index_commit('git commit -am test',
            {'GIT_CONFIG_PARAMETERS': "'core.worktree'='/other'"}))

    def test_missing_capture_cannot_bypass_commit_or_pr_after_verify(self):
        self.exercise_capture('codex')
        self.lc('retrospect', '--no-new-lessons', 'fixture')
        self.lc('stage', 'verify')
        base = guard.directory(self.root)
        (base / 'journal.json').unlink()
        (base.parent.parent / 'review-expectations' / (base.name + '.json')).unlink()
        for command in ('git commit -m reviewed', 'gh pr create --title reviewed'):
            event = {'hook_event_name': 'PreToolUse', 'cwd': str(self.root), 'tool_name': 'Bash',
                     'tool_input': {'command': command}}
            result = subprocess.run([sys.executable, str(self.scripts / 'lifecycle.py'), 'hook'],
                cwd=self.root, env={**self.env, 'LIFECYCLE_GUARD': 'off', 'OKF_AUTONOMOUS': '1'},
                input=json.dumps(event), capture_output=True, text=True, timeout=10)
            self.assertIn('mechanical', result.stdout)
            self.assertIn('deny', result.stdout)

    def test_missing_journal_after_native_review_cannot_verify_as_legacy(self):
        import lifecycle
        self.exercise_capture('codex')
        self.lc('retrospect', '--no-new-lessons', 'fixture')
        base = guard.directory(self.root)
        (base / 'journal.json').unlink()
        (base.parent.parent / 'review-expectations' / (base.name + '.json')).unlink(missing_ok=True)
        result = self.lc('stage', 'verify', code=1)
        self.assertIn('mechanical', result.stderr)
        self.assertNotIn('verify', lifecycle.load(self.root)['stages'])

    def test_partial_commit_hook_cannot_bypass_the_reviewed_full_index(self):
        self.exercise_capture('claude')
        self.lc('retrospect', '--no-new-lessons', 'fixture')
        self.lc('stage', 'verify')
        self.git('add', '-A')
        for command in ('git commit --only src/calc.py -m partial',
                        'git commit src/calc.py -m partial', 'git commit -ompartial src/calc.py',
                        'git commit --fixup=reword:HEAD', 'git commit --unknown-tree-selection',
                        f'git -c core.worktree={self.root} commit -am alternative'):
            event = {'hook_event_name': 'PreToolUse', 'cwd': str(self.root), 'tool_name': 'Bash',
                     'tool_input': {'command': command}}
            result = subprocess.run([sys.executable, str(self.scripts / 'lifecycle.py'), 'hook'],
                cwd=self.root, env=self.env, input=json.dumps(event), capture_output=True, text=True, timeout=10)
            self.assertIn('full index', result.stdout)
        event['tool_input'] = {'command': 'git commit -m selected',
                               'env': {'GIT_INDEX_FILE': str(self.root / '.git/index')}}
        result = subprocess.run([sys.executable, str(self.scripts / 'lifecycle.py'), 'hook'],
            cwd=self.root, env=self.env, input=json.dumps(event), capture_output=True, text=True, timeout=10)
        self.assertIn('full index', result.stdout)

    def test_publication_chain_and_archive_corruption_refuse(self):
        self.started()
        pins = self.journal()['interval']['pins']
        guard.stop(self.root, 'task', 'claude', 'parent', 'child', REPORT, pins)
        state = {'task': 'task', 'ledger': [{'entry': 'reviewed'}]}
        guard.append_evidence(self.root, state, [{'entry': 'new'}], lambda value: None)
        interval = self.journal()['interval']
        base = guard.directory(self.root) / 'captures' / interval['id']
        path = base / 'publication.json'
        original = guard.document(path)
        for key, value in [('evicted', [{'entry': 'not-oldest'}]), ('sequence', 3),
                           ('previous', 'rewritten'), ('expected', 'rewritten')]:
            changed = json.loads(json.dumps(original))
            changed['completed'][0][key] = value
            guard.atomic(path, changed)
            self.assertIsNotNone(guard.evidence_problem(self.root, state), key)
        guard.atomic(path, original)
        archive = guard.document(base / 'capture.json')
        archive['archive'][0]['entry'] = 'rewritten'
        guard.atomic(base / 'capture.json', archive)
        self.assertIn('archive', guard.evidence_problem(self.root, state))

    def test_stale_index_cannot_deliver_different_reviewed_mode(self):
        self.exercise_capture('claude')
        self.lc('retrospect', '--no-new-lessons', 'fixture')
        self.lc('stage', 'verify')
        self.git('add', '-A')
        self.git('update-index', '--chmod=+x', 'src/calc.py')
        result = self.lc('gate', 'commit', code=1)
        self.assertIn('index', result.stdout)

    def test_same_timestamp_convergence_rerun_invalidates_review(self):
        self.prepare_native('claude')
        self.lc('retrospect', '--no-new-lessons', 'fixture')
        code = ('import lifecycle; lifecycle.now=lambda:"2026-10-28T00:00:00Z"; '
                'raise SystemExit(lifecycle.main(["converge","docs/spec.md"]))')
        def converge():
            result = subprocess.run([sys.executable, '-c', code], cwd=self.root,
                env={**self.env, 'PYTHONPATH': str(self.scripts)},
                capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        converge()
        self.event('SubagentStart', agent_id='child', agent_type='reviewer')
        self.event('SubagentStop', agent_id='child', agent_type='reviewer', last_assistant_message=REPORT)
        self.lc('review', 'save-report')
        self.lc('stage', 'review', '--ref', 'knowledge/history/reviews/native.md')
        converge()
        result = self.lc('gate', 'verify', code=1)
        self.assertIn('converge', result.stdout)

    def test_default_broad_validation_refresh_reaches_verify_without_rereview(self):
        import lifecycle
        self.prepare_native('codex')
        # The unittest actually asserts product state; default input inference is broad.
        # Creating the fixture is a candidate change, so convergence must precede capture again.
        self.write('test_fixture.py', 'import unittest\nfrom pathlib import Path\n'
                   'class Fixture(unittest.TestCase):\n'
                   ' def test_value(self):\n'
                   '  self.assertEqual(Path("src/calc.py").read_text(), "ok\\n")\n')
        self.capability('- CALC-R1: Tool MUST pass.\n'
                        '  - Verify: `python3 -m unittest test_fixture`\n'
                        '  - Inputs: `**`\n')
        self.lc('converge', 'docs/spec.md')
        self.lc('run', 'before', '--', 'python3', '-m', 'unittest', 'test_fixture')
        original = lifecycle.load(self.root)['ledger'][-1]
        self.assertIn('**', original['inputs'])
        self.assertIn('!knowledge/history/lifecycle/**', original['inputs'])
        self.lc('assure', '--run', 'CALC-R1')
        # Populate the boundary with schema-valid fixture receipts, retaining the
        # real broad validation/requirement receipts. This is synthetic history.
        with guard.producer(self.root), lifecycle.state_lock(self.root):
            state = lifecycle.load(self.root)
            actual = state['ledger']
            padding = [{**original, 'label': f'fixture-{n}'} for n in range(100 - len(actual))]
            state['ledger'] = padding + actual
            lifecycle.save(self.root, state)
        self.event('SubagentStart', agent_id='child', agent_type='reviewer')
        self.event('SubagentStop', agent_id='child', agent_type='reviewer', last_assistant_message=REPORT)
        interval = guard.read(self.root)['interval']['id']
        self.lc('review', 'save-report')
        self.lc('reuse', 'before', code=1)
        status = json.loads(self.lc('assure', '--json', code=1).stdout)
        self.assertEqual(status['requirements'][0]['status'], 'STALE')
        self.lc('stage', 'review', '--ref', 'knowledge/history/reviews/native.md')
        self.lc('run', 'after', '--', 'python3', '-m', 'unittest', 'test_fixture')
        self.lc('assure', '--run', 'CALC-R1')
        children = [subprocess.Popen([sys.executable, str(self.scripts / 'lifecycle.py'), 'run',
                    f'parallel-{n}', '--', 'python3', '-V'], cwd=self.root, env=self.env,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for n in range(2)]
        for child in children:
            stdout, stderr = child.communicate(timeout=15)
            self.assertEqual(child.returncode, 0, stdout + stderr)
        self.lc('retrospect', '--no-new-lessons', 'fixture validation complete')
        self.lc('stage', 'verify')
        state = lifecycle.load(self.root)
        self.assertIn('verify', state['stages'])
        self.assertEqual(guard.read(self.root)['interval']['id'], interval)
        self.assertIsNone(guard.evidence_problem(self.root, state))
        self.assertEqual(len(state['ledger']), 100)
        self.assertEqual(len(guard.read(self.root)['interval']['archive']), 100)
        self.assertTrue({'parallel-0', 'parallel-1'} <= {entry['label'] for entry in state['ledger']})
        self.write('src/calc.py', 'changed after Verify\n')
        for command in ('git commit -m reviewed', 'gh pr create --title reviewed'):
            event = {'hook_event_name': 'PreToolUse', 'cwd': str(self.root),
                     'tool_name': 'Bash', 'tool_input': {'command': command}}
            result = subprocess.run([sys.executable, str(self.scripts / 'lifecycle.py'), 'hook'],
                cwd=self.root, env={**self.env, 'LIFECYCLE_GUARD': 'off', 'OKF_AUTONOMOUS': '1'},
                input=json.dumps(event), capture_output=True, text=True, timeout=10)
            self.assertIn('candidate changed', result.stdout)
        self.lc('gate', 'commit', code=1)
        self.assertIn('candidate changed', self.lc('status', code=1).stdout)
        completion = json.loads(self.lc('finish', '--json', '--tests', 'test_fixture.py', code=1).stdout)
        self.assertFalse(completion['verified'])
        self.assertTrue(any('mechanical review' in blocker for blocker in completion['blockers']))
        self.lc('stage', 'ship', code=1)

    def test_bounded_append_proof_preserves_archive_and_rejects_rewrites(self):
        import ledger
        self.enabled()
        entries = [{'entry': n} for n in range(ledger.MAX_ENTRIES)]
        pins = {'source': 'frozen'}
        guard.start(self.root, 'task', 'claude', 'parent', 'child', 'reviewer', pins, entries)
        guard.stop(self.root, 'task', 'claude', 'parent', 'child', REPORT, pins)
        state = {'task': 'task', 'ledger': entries[:]}
        def publish(value):
            guard.atomic(self.root / 'state.json', value)
        guard.append_evidence(self.root, state, [{'entry': 100}], publish)
        self.assertEqual(state['ledger'], [{'entry': n} for n in range(1, 101)])
        self.assertEqual(self.journal()['interval']['archive'], entries)
        self.assertIsNone(guard.evidence_problem(self.root, state))
        state['ledger'][3]['entry'] = 'rewritten'
        self.assertIn('ledger', guard.evidence_problem(self.root, state))

    def test_unrecorded_append_is_not_inferred_from_suffix(self):
        self.started()
        pins = self.journal()['interval']['pins']
        guard.stop(self.root, 'task', 'claude', 'parent', 'child', REPORT, pins)
        self.assertIsNotNone(guard.evidence_problem(self.root,
            {'task': 'task', 'ledger': [{'entry': 'reviewed'}, {'entry': 'unrecorded'}]}))

    def test_exact_convergence_or_source_drift_refuses(self):
        self.started()
        pins = self.journal()['interval']['pins']
        guard.stop(self.root, 'task', 'claude', 'parent', 'child', REPORT, pins)
        for changed in ({**pins, 'source': 'new'}, {**pins, 'converge': {'at': 'after'}}):
            self.assertIn('changed', guard.qualification_problem(self.root, 'task', changed, REPORT))


class CompatibilityTests(NativeCase):  # R8
    def test_snapshot_exception_preserves_policy_captures_and_live_grants(self):
        from review_test_support import closed_coordination_snapshot
        def snapshot():
            return closed_coordination_snapshot(self.root, {
                str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file() and not path.is_symlink()})
        before = snapshot()
        with guard.producer(self.root):
            with self.assertRaisesRegex(AssertionError, 'live or unresolved'):
                snapshot()
        self.assertEqual(snapshot(), before)
        with guard.transaction(self.root) as value:
            value['history'].append({'outcome': 'unexpected-review-history'})
        self.assertNotEqual(snapshot(), before)
        policy = snapshot()
        guard.atomic(guard.directory(self.root) / 'captures/unexpected.json', {'captured': 'unexpected'})
        self.assertNotEqual(snapshot(), policy)

    def test_guard_namespace_rejects_system_temp_symlinks_before_writes(self):
        root = self.root.parent / 'git-only'
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        (root / '.git/okf-scratch').symlink_to('/tmp', target_is_directory=True)
        with self.assertRaisesRegex(guard.ReviewError, 'outside system temporary'):
            guard.directory(root)
        with self.assertRaisesRegex(guard.ReviewError, 'outside system temporary'):
            with guard.producer(root):
                self.fail('guard ownership followed a scratch symlink into system temp')

    def test_undeclared_task_delivery_hooks_keep_legacy_behavior(self):
        for bypass in (False, True):
            event = {'hook_event_name': 'PreToolUse', 'cwd': str(self.root), 'tool_name': 'Bash',
                     'tool_input': {'command': 'git commit -m ordinary'}}
            env = dict(self.env)
            if bypass:
                env['LIFECYCLE_GUARD'] = 'off'
            else:
                env.pop('LIFECYCLE_GUARD', None)
                env.pop('OKF_AUTONOMOUS', None)
            result = subprocess.run([sys.executable, str(self.scripts / 'lifecycle.py'), 'hook'],
                cwd=self.root, env=env, input=json.dumps(event), capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip() == '', bypass, result.stdout)

    def test_launch_shim_does_not_repeat_product_python_startup(self):
        marker = self.root / 'startup-count'
        self.write('sitecustomize.py', 'import os\nfrom pathlib import Path\n'
            'p=Path(os.environ["STARTUP_MARKER"])\n'
            'p.write_text(str((int(p.read_text()) if p.exists() else 0)+1))\n')
        with guard.producer(self.root):
            result = guard.run(self.root, [sys.executable, '-c', 'print("product")'],
                cwd=self.root, env={**self.env, 'PYTHONPATH': str(self.root), 'STARTUP_MARKER': str(marker)},
                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'product\n')
        self.assertEqual(marker.read_text(), '1')

    def test_windows_lifetime_probe_never_sends_a_signal(self):
        from unittest import mock
        with mock.patch.object(guard.os, 'name', 'nt'), mock.patch.object(guard.os, 'kill',
                side_effect=AssertionError('a Windows lifetime probe must never signal the owner')):
            self.assertFalse(guard.stopped({'pid': 123, 'birth': None}))

    def test_both_deployed_hook_families_and_docs_declare_the_contract(self):
        import review_native
        source = Path(__file__).resolve().parents[3]
        for adapter in ('claude', 'codex'):
            self.assertTrue(review_native.configuration(source, adapter))
        lifecycle_doc = (source / '.ai/lifecycle.md').read_text()
        for term in ('Mechanically bound review (opt-in)', 'review save-report', 'review recover',
                     'Synthetic callback tests', 'Historical failed evaluations remain failed'):
            self.assertIn(term, lifecycle_doc)

    def test_legacy_task_has_no_mechanical_claim_or_new_block(self):
        self.assertIsNone(guard.qualification_problem(self.root, 'legacy', {}, 'old report'))
        with guard.producer(self.root):
            self.assertIsNone(guard.active_problem(self.journal()))


class ReadOnlyTests(NativeCase):  # R3
    def test_root_help_is_read_only_through_active_hooks_and_actual_cli(self):
        import lifecycle
        self.prepare_native('codex')
        self.event('SubagentStart', agent_id='child', agent_type='reviewer')
        before = self.journal()
        state = lifecycle.load(self.root)
        pins = self.native.candidate(self.root, state)
        for flag in ('--help', '-h'):
            command = f'python3 .ai/scripts/lifecycle.py {flag}'
            self.assertFalse(guard.command_mutates(command))
            for tool in ('Bash', 'exec_command'):
                event = {'hook_event_name': 'PreToolUse', 'cwd': str(self.root),
                         'tool_name': tool, 'tool_input': {'command': command}}
                hook = subprocess.run([sys.executable, str(self.scripts / 'lifecycle.py'), 'hook'],
                    cwd=self.root, env=self.env, input=json.dumps(event),
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(hook.returncode, 0, hook.stderr)
                self.assertEqual(hook.stdout.strip(), '')
                # A reader needs no invocation ID and must acquire no writer lease.
                self.event('PreToolUse', tool_name=tool, tool_input={'command': command})
                self.event('PostToolUse', tool_name=tool, tool_input={'command': command})
            self.assertIn('usage:', self.lc(flag).stdout)
        for executable in ('python', 'python3.11', '/usr/bin/python3'):
            self.assertFalse(guard.command_mutates(f'{executable} ".ai/scripts/lifecycle.py" --help'))
        absolute = str(Path(guard.__file__).with_name('lifecycle.py'))
        self.assertFalse(guard.command_mutates(f'python3 "{absolute}" -h'))
        self.assertEqual(self.journal(), before)
        self.assertEqual(lifecycle.load(self.root), state)
        self.assertEqual(self.native.candidate(self.root, state), pins)

    def test_help_flag_cannot_exempt_mixed_commands_values_or_redirection(self):
        self.prepare_native('codex')
        self.event('SubagentStart', agent_id='child', agent_type='reviewer')
        commands = (
            'python3 .ai/scripts/lifecycle.py --help && git rm notes.txt',
            'python3 .ai/scripts/lifecycle.py --help; python3 .ai/scripts/lifecycle.py converge docs/spec.md',
            'python3 .ai/scripts/lifecycle.py --help > notes.txt',
            'python3 .ai/scripts/lifecycle.py --help>notes.txt',
            'python3 .ai/scripts/lifecycle.py stage verify --note=--help',
            'python3 .ai/scripts/lifecycle.py run probe -- python3 check.py --help',
            'python3 .ai/scripts/lifecycle.py learn --help-as-data',
            'python3 -u .ai/scripts/lifecycle.py --help',
            'env X=1 python3 .ai/scripts/lifecycle.py --help',
            'python3 other/lifecycle.py --help',
            'python3 .ai/scripts/lifecycle.py --help\npython3 .ai/scripts/lifecycle.py converge docs/spec.md',
            'python3 .ai/scripts/lifecycle.py --help\n',
            'python3 .ai/scripts/lifecycle.py --help$(python3 .ai/scripts/lifecycle.py converge docs/spec.md)',
            'python3 .ai/scripts/lifecycle.py --help`python3 .ai/scripts/lifecycle.py converge docs/spec.md`',
        )
        before = self.journal()
        for n, command in enumerate(commands):
            with self.subTest(command=command):
                self.assertTrue(guard.command_mutates(command))
                with self.assertRaisesRegex(guard.ReviewError, 'active review'):
                    self.event('PreToolUse', tool_name='Bash', tool_input={'command': command},
                               tool_use_id=f'help-writer-{n}')
        self.assertEqual(self.journal(), before)

    def separated_checkout(self):
        root, metadata = self.root.parent / 'separated', self.root.parent / 'git-metadata'
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        subprocess.run(['git', '-C', str(root), 'init', '-q', '--separate-git-dir', str(metadata)], check=True)
        self.assertTrue((root / '.git').is_file())
        config = subprocess.run(['git', '-C', str(root), 'config', '--get', 'core.worktree'], capture_output=True)
        self.assertEqual(config.returncode, 1)
        return root, metadata

    def test_separated_checkout_owns_metadata_and_still_freezes(self):
        root, metadata = self.separated_checkout()
        source = root / 'source.txt'
        source.write_text('unchanged')
        subprocess.run(['git', '-C', str(root), 'add', 'source.txt'], check=True)
        event = {'hook_event_name': 'PreToolUse', 'cwd': str(root), 'tool_name': 'Bash',
                 'tool_input': {'command': 'git switch -c allowed'}}
        self.assertEqual(guard.operation_roots(event), [root.resolve()])
        def hook():
            result = subprocess.run([sys.executable, str(self.scripts / 'lifecycle.py'), 'hook'],
                cwd=root, env=self.env, input=json.dumps(event), capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout
        self.assertEqual(hook().strip(), '')
        subprocess.run(['git', '-C', str(root), 'switch', '-c', 'allowed'], check=True, capture_output=True)
        before = ((root / '.git').read_bytes(), (metadata / 'HEAD').read_bytes(),
                  (metadata / 'index').read_bytes(), source.read_bytes())
        with guard.transaction(root) as value:
            value['interval'] = {'phase': 'active', 'task': 'separated-review'}
        event['tool_input']['command'] = 'git switch -c blocked'
        self.assertIn('active review', hook())
        self.assertEqual(before, ((root / '.git').read_bytes(), (metadata / 'HEAD').read_bytes(),
                                  (metadata / 'index').read_bytes(), source.read_bytes()))

    def test_physical_witness_cannot_admit_foreign_metadata_selectors(self):
        from unittest import mock
        _, metadata = self.separated_checkout()
        variants = [
            (f'git --git-dir={metadata} --work-tree={self.root} switch -c foreign', {}),
            (f'env GIT_DIR={metadata} GIT_WORK_TREE={self.root} git switch -c foreign', {}),
            ('git switch -c foreign', {'GIT_DIR': str(metadata), 'GIT_WORK_TREE': str(self.root)})]
        for command, environment in variants:
            with self.subTest(command=command), mock.patch.dict(os.environ, environment), mock.patch.object(
                    guard, 'metadata_owners', side_effect=guard.ReviewError('foreign owner checked')) as owner:
                with self.assertRaisesRegex(guard.ReviewError, 'foreign owner checked'):
                    guard.operation_roots({'cwd': str(self.root), 'tool_name': 'Bash',
                        'tool_input': {'command': command}})
                owner.assert_called_once_with(metadata.resolve())

    def test_own_witness_keeps_foreign_index_object_and_common_checks(self):
        from unittest import mock
        other = self.root.parent / 'foreign'
        subprocess.run(['git', 'init', '-q', str(other)], check=True)
        for variable, path, shared in [('GIT_INDEX_FILE', other / '.git/index', False),
                                      ('GIT_OBJECT_DIRECTORY', other / '.git/objects', True),
                                      ('GIT_COMMON_DIR', other / '.git', True)]:
            with self.subTest(variable=variable), mock.patch.object(guard, 'metadata_owners',
                    side_effect=guard.ReviewError('foreign override checked')) as owner:
                with self.assertRaisesRegex(guard.ReviewError, 'foreign override checked'):
                    guard.operation_roots({'cwd': str(self.root), 'tool_name': 'Bash', 'tool_input': {
                        'command': 'git add source.txt', 'env': {variable: str(path)}}})
                owner.assert_called_once_with(path.resolve(), shared=shared)

    def test_malformed_physical_git_directory_witness_refuses(self):
        from unittest import mock
        original = guard.git_probe
        for answer in ([], ['relative'], ['/one', '/two']):
            def probe(invocation, arguments):
                if invocation['prefix'] == ['-C', str(self.root)] and arguments == ['rev-parse', '--absolute-git-dir']:
                    return answer
                return original(invocation, arguments)
            with self.subTest(answer=answer), mock.patch.object(guard, 'git_probe', side_effect=probe):
                with self.assertRaisesRegex(guard.ReviewError, 'Git directory identity'):
                    guard.operation_roots({'cwd': str(self.root), 'tool_name': 'Bash',
                        'tool_input': {'command': 'git switch -c invalid'}})

    def test_unsupported_env_wrapper_never_silently_hides_git(self):
        for command in ('env -i git -C /other restore file',
                        'env --unset=NAME git -C /other restore file'):
            self.assertTrue(guard.command_mutates(command))
            with self.assertRaisesRegex(guard.ReviewError, 'wrapper'):
                guard.operation_roots({'cwd': str(self.root), 'tool_name': 'Bash',
                    'tool_input': {'command': command}})

    def test_relative_git_selectors_follow_git_directory_order(self):
        nested = self.root / 'nested'
        nested.mkdir()
        target = nested / 'selected'
        subprocess.run(['git', 'init', '-q', str(target)], check=True)
        command = 'git --work-tree=selected -C nested --git-dir=selected/.git rm file'
        data = {'cwd': str(self.root), 'tool_name': 'Bash', 'tool_input': {'command': command}}
        self.assertEqual(guard.operation_roots(data), [target.resolve()])

    def test_git_segments_keep_their_own_selectors_and_classify_the_verb(self):
        first, second = self.root / 'first', self.root / 'second'
        for target in (first, second):
            subprocess.run(['git', 'init', '-q', str(target)], check=True)
        command = 'git -C first add file && git -C second rm file'
        data = {'cwd': str(self.root), 'tool_name': 'Bash', 'tool_input': {'command': command}}
        self.assertEqual(guard.operation_roots(data), sorted([first.resolve(), second.resolve()]))
        self.assertFalse(guard.command_mutates('git log --grep=commit -- add'))

    def test_common_git_file_writers_refuse_during_review(self):
        self.prepare_native('claude')
        self.event('SubagentStart', agent_id='child', agent_type='reviewer')
        for n, command in enumerate(('git mv src/calc.py src/moved.py', 'git restore src/calc.py',
                                      'git clean -fd', 'git apply change.patch')):
            with self.assertRaisesRegex(guard.ReviewError, 'active review'):
                self.event('PreToolUse', tool_name='Bash', tool_input={'command': command}, tool_use_id=f'git-write-{n}')

    def test_git_environment_cannot_redirect_the_guard_namespace(self):
        from unittest import mock
        self.started()
        other = self.root.parent / 'metadata'
        other.mkdir()
        subprocess.run(['git', 'init', '-q', str(other)], check=True)
        with mock.patch.dict(os.environ, {'GIT_DIR': str(other / '.git'), 'GIT_WORK_TREE': str(other)}):
            with self.assertRaisesRegex(guard.ReviewError, 'active review'):
                with guard.producer(self.root):
                    self.fail('a Git environment override bypassed the physical worktree guard')

    def test_explicit_git_and_environment_selectors_cannot_hide_active_target(self):
        self.prepare_native('claude')
        other = self.root.parent / 'selected'
        other.mkdir()
        subprocess.run(['git', 'init', '-q', str(other)], check=True)
        with guard.transaction(other) as value:
            value['interval'] = {'phase': 'active', 'task': 'other'}
        commands = (f'git --git-dir={other}/.git --work-tree={other} rm src/calc.py',
                    f'git --git-dir {other}/.git --work-tree {other} rm src/calc.py',
                    f'env GIT_DIR={other}/.git GIT_WORK_TREE={other} git rm src/calc.py')
        for n, command in enumerate(commands):
            with self.assertRaisesRegex(guard.ReviewError, 'active review'):
                self.event('PreToolUse', tool_name='Bash', tool_input={'command': command}, tool_use_id=f'selector-{n}')

    def test_driver_filename_operands_keep_the_native_mutation_lease(self):
        self.prepare_native('codex')
        for n, command in enumerate(('git rm .ai/scripts/autonomy_driver.py',
                                      'git add .ai/scripts/autonomy_driver.py',
                                      'python-other .ai/scripts/autonomy_driver.py')):
            tool = {'tool_name': 'Bash', 'tool_input': {'command': command}, 'tool_use_id': f'operand-{n}'}
            self.event('PreToolUse', **tool)
            self.assertTrue(guard.read(self.root)['writers'])
            with self.assertRaisesRegex(guard.ReviewError, 'producer'):
                self.event('SubagentStart', agent_id='child', agent_type='reviewer')
            self.event('PostToolUse', **tool)

    def test_nested_git_directory_targets_freeze_the_actual_worktree(self):
        self.prepare_native('claude')
        other = self.root.parent / 'independent'
        other.mkdir()
        subprocess.run(['git', 'init', '-q', str(other)], check=True)
        with guard.transaction(other) as value:
            value['interval'] = {'phase': 'active', 'task': 'other'}
        for command in (f'git -C {self.root} -C ../independent reset --hard',):
            with self.assertRaisesRegex(guard.ReviewError, 'active review'):
                self.event('PreToolUse', tool_name='Bash', tool_input={'command': command}, tool_use_id='nested-git')
        with self.assertRaisesRegex(guard.ReviewError, 'Git target cannot be established'):
            self.event('PreToolUse', tool_name='Bash',
                tool_input={'command': f'git -C{other} rm src/calc.py'}, tool_use_id='invalid-compact-git')

    def test_driver_launch_does_not_hold_a_whole_session_native_lease(self):
        self.prepare_native('codex')
        tool = {'tool_name': 'Bash', 'tool_input': {'command': 'python3 .ai/scripts/autonomy_driver.py'},
                'tool_use_id': 'driver-session'}
        self.event('PreToolUse', **tool)
        self.assertFalse(guard.read(self.root)['writers'])
        self.event('SubagentStart', agent_id='child', agent_type='reviewer')
        with self.assertRaisesRegex(guard.ReviewError, 'active review'):
            self.event('PreToolUse', **tool)

    def test_active_review_allows_independent_fixture_and_git_scratch(self):
        import scratch
        self.prepare_native('claude')
        other = self.root.parent / 'independent'
        other.mkdir()
        subprocess.run(['git', 'init', '-q', str(other)], check=True)
        self.event('SubagentStart', agent_id='child', agent_type='reviewer')
        for n, path in enumerate([other / 'fixture.md', scratch.directory(self.root) / 'temporary.md']):
            tool = {'tool_name': 'Write', 'tool_input': {'file_path': str(path)}, 'tool_use_id': f'other-{n}'}
            self.event('PreToolUse', **tool)
            path.write_text('separate fixture output')
            self.event('PostToolUse', **tool)
        self.event('SubagentStop', agent_id='child', agent_type='reviewer', last_assistant_message=REPORT)
        self.lc('review', 'save-report')
        self.lc('stage', 'review', '--ref', 'knowledge/history/reviews/native.md')

    def test_markdown_delete_and_wrapped_writer_hooks_ignore_legacy_bypass(self):
        with guard.transaction(self.root) as journal:
            journal['interval'] = {'phase': 'active', 'task': 'task'}
        for tool, tool_input in [('Write', {'file_path': str(self.root / 'notes.md')}),
                                 ('Delete', {'file_path': str(self.root / 'check.py')}),
                                 ('Bash', {'command': 'env X=1 python3 .ai/scripts/lifecycle.py converge docs/s.md'})]:
            event = {'hook_event_name': 'PreToolUse', 'cwd': str(self.root),
                     'tool_name': tool, 'tool_input': tool_input}
            result = subprocess.run([sys.executable, str(self.scripts / 'lifecycle.py'), 'hook'],
                cwd=self.root, env={**self.env, 'LIFECYCLE_GUARD': 'off', 'OKF_AUTONOMOUS': '1'},
                input=json.dumps(event), capture_output=True, text=True, timeout=10)
            self.assertIn('active review', result.stdout)

    def test_public_workflow_producers_refuse_direct_python_calls(self):
        import artifacts
        import autonomy_validation
        import completion
        import install
        import okf
        import pr_sync
        with guard.transaction(self.root) as journal:
            journal['interval'] = {'phase': 'active', 'task': 'task'}
        calls = [lambda: okf.reindex(self.root / 'knowledge'),
                 lambda: okf.record_session(self.root / 'knowledge'),
                 lambda: okf.archive_closed(self.root / 'knowledge'),
                 lambda: okf.write_text(self.root / 'knowledge/new.md', 'Unexpected'),
                 lambda: install.install(self.root, Path(__file__).resolve().parents[3]),
                 lambda: pr_sync.sync(self.root / 'knowledge'),
                 lambda: artifacts.freeze(self.root, self.root, ['check.py']),
                 lambda: autonomy_validation.register(self.root / 'registry', self.root, self.root),
                 lambda: autonomy_validation.run(self.root / 'absent', self.root, 0, 0, None, None),
                 lambda: autonomy_validation.execute({}, 1, self.root / 'unexpected.log', self.root, {}, 1, None),
                 lambda: completion.apply_bindings(self.root, {}, [])]
        before = self.git('status', '--porcelain')
        for call in calls:
            with self.subTest(call=call), self.assertRaisesRegex(guard.ReviewError, 'active review'):
                call()
        self.assertEqual(self.git('status', '--porcelain'), before)

    def test_direct_lifecycle_and_okf_producers_have_no_effects(self):
        self.task()
        with guard.transaction(self.root) as journal:
            journal['interval'] = {'phase': 'active', 'task': 'task'}
        before = self.git('status', '--porcelain')
        result = self.lc('run', 'forbidden', '--', 'python3', '-c',
                         "open('unexpected','w').write('bad')", code=1)
        self.assertIn('active review', result.stderr)
        self.cli('okf.py', 'log', 'Unexpected', code=1)
        self.assertFalse((self.root / 'unexpected').exists())
        self.assertEqual(self.git('status', '--porcelain'), before)
        self.cli('okf.py', 'records')

    def test_active_review_refuses_writer_before_effects(self):
        with guard.transaction(self.root) as journal:
            journal['interval'] = {'phase': 'active', 'task': 'task'}
        marker = self.root / 'writer.txt'
        with self.assertRaisesRegex(guard.ReviewError, 'active review'):
            with guard.producer(self.root):
                marker.write_text('unexpected')
        self.assertFalse(marker.exists())

    def test_nested_owner_cannot_release_outer_lease(self):
        with guard.producer(self.root):
            original = self.journal()['writers']
            self.assertEqual(len(original), 1)
            with guard.producer(self.root):
                self.assertEqual(self.journal()['writers'], original)
            self.assertEqual(self.journal()['writers'], original)
        self.assertEqual(self.journal()['writers'], {})

    def test_child_borrows_without_guard_lock(self):
        code = ('import pathlib,review_guard as g; '
                'r=pathlib.Path.cwd(); '
                'exec("with g.producer(r):\\n pathlib.Path(\'child.txt\').write_text(\'done\')")')
        with guard.producer(self.root):
            with guard.lock(self.root):
                result = subprocess.run([sys.executable, '-c', code], cwd=self.root,
                                        env={**os.environ, 'PYTHONPATH': str(self.scripts)},
                                        capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(self.journal()['writers']), 1)
        self.assertEqual((self.root / 'child.txt').read_text(), 'done')

    def test_invalid_same_root_descriptor_refuses(self):
        with guard.producer(self.root):
            descriptor = json.loads(os.environ[guard.LEASE_ENV])
            descriptor['nonce'] = 'wrong'
            result = subprocess.run([sys.executable, '-c',
                'import pathlib,review_guard as g; exec("with g.producer(pathlib.Path.cwd()):\\n pass")'],
                cwd=self.root, env={**os.environ, 'PYTHONPATH': str(self.scripts),
                                   guard.LEASE_ENV: json.dumps(descriptor)},
                capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('inherited', result.stderr)


class RecoveryTests(NativeCase):  # R7
    def test_dead_native_host_is_not_invocation_terminal_proof(self):
        self.prepare_native('codex')
        host = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        runtime = guard.identity(host.pid)
        tool = {'hook_event_name': 'PreToolUse', 'session_id': 'parent', 'cwd': str(self.root),
                'tool_name': 'Write', 'tool_input': {'file_path': str(self.root / 'notes.md')},
                'tool_use_id': 'lost-native-post'}
        try:
            self.native.native_tool(self.root, 'codex', tool, runtime)
        finally:
            host.kill()
            host.wait(timeout=5)
        with self.assertRaisesRegex(guard.ReviewError, 'terminal'):
            guard.recover_writers(self.root)
        self.native.native_tool(self.root, 'codex', {**tool, 'hook_event_name': 'PostToolUse'}, runtime)
        guard.recover_writers(self.root)

    def test_plain_command_group_survives_supervisor_loss_without_unlocking(self):
        import signal
        import time
        self.prepare_native('codex')
        for with_descendant in (False, True):
            marker = guard.directory(self.root) / f'plain-{with_descendant}.json'
            child_script = 'import time; time.sleep(60)'
            code = ('import os,time,pathlib,subprocess,sys,json\n'
                    'pids=[os.getpid()]\n' +
                    (f'pids.append(subprocess.Popen([sys.executable,"-c",{child_script!r}]).pid)\n'
                     if with_descendant else '') +
                    f'pathlib.Path({str(marker)!r}).write_text(json.dumps(pids))\n'
                    'time.sleep(60)\n')
            owner = subprocess.Popen([sys.executable, str(self.scripts / 'lifecycle.py'), 'run',
                'plain-child', '--', sys.executable, '-c', code], cwd=self.root, env=self.env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            pids = []
            try:
                deadline = time.monotonic() + 10
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(marker.exists())
                pids = json.loads(marker.read_text())
                owner.kill()
                owner.wait(timeout=5)
                if with_descendant:
                    os.kill(pids[0], signal.SIGKILL)
                with self.assertRaisesRegex(guard.ReviewError, 'producer|borrower'):
                    guard.recover_writers(self.root)
            finally:
                if owner.poll() is None:
                    owner.kill()
                    owner.wait(timeout=5)
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            deadline = time.monotonic() + 5
            while any(not guard.stopped(guard.identity(pid)) for pid in pids) and time.monotonic() < deadline:
                time.sleep(.01)
            guard.recover_writers(self.root)
        self.event('SubagentStart', agent_id='new-reviewer', agent_type='reviewer')

    def test_explicit_recovery_does_not_lease_itself(self):
        self.prepare_native('codex')
        tool = {'tool_name': 'Bash', 'tool_input': {'command': 'python3 .ai/scripts/lifecycle.py review recover'},
                'tool_use_id': 'recover-self'}
        self.event('PreToolUse', **tool)
        self.lc('review', 'recover')
        self.event('PostToolUse', **tool)
        self.assertFalse(guard.read(self.root)['writers'])

    def test_dead_owner_cannot_release_a_live_borrower(self):
        import signal
        import time
        child_code = ('import pathlib,time,review_guard as g; '
            'exec("with g.producer(pathlib.Path.cwd()):\\n '
            'pathlib.Path(\'borrower-entered\').write_text(\'yes\'); time.sleep(60)")')
        parent_code = ('import os,pathlib,subprocess,sys,time,review_guard as g\n'
            'with g.producer(pathlib.Path.cwd()):\n'
            f' child=subprocess.Popen([sys.executable,"-c",{child_code!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n'
            ' pathlib.Path("borrower-pid").write_text(str(child.pid))\n'
            ' deadline=time.monotonic()+5\n'
            ' while not pathlib.Path("borrower-entered").exists() and time.monotonic()<deadline: time.sleep(.01)\n'
            ' os._exit(17)\n')
        parent = subprocess.run([sys.executable, '-c', parent_code], cwd=self.root,
            env={**self.env, 'PYTHONPATH': str(self.scripts)}, capture_output=True, text=True, timeout=10)
        self.assertEqual(parent.returncode, 17, parent.stderr)
        child_pid = int((self.root / 'borrower-pid').read_text())
        try:
            self.assertTrue((self.root / 'borrower-entered').exists())
            with self.assertRaisesRegex(guard.ReviewError, 'borrower'):
                guard.recover_writers(self.root)
        finally:
            os.kill(child_pid, signal.SIGKILL)
        deadline = time.monotonic() + 5
        while not guard.stopped(guard.identity(child_pid)) and time.monotonic() < deadline:
            time.sleep(.01)
        guard.recover_writers(self.root)
        self.assertFalse(guard.read(self.root)['writers'])

    def test_abandoned_native_child_identity_cannot_be_reused(self):
        self.prepare_native('claude')
        self.event('SubagentStart', agent_id='old-child', agent_type='reviewer')
        self.lc('review', 'abandon', '--reason', 'old invocation')
        self.lc('review', 'restart', '--report', 'knowledge/history/reviews/new.md')
        with self.assertRaisesRegex(guard.ReviewError, 'reus'):
            self.event('SubagentStart', agent_id='old-child', agent_type='reviewer')

    def test_native_hook_exit_never_releases_outstanding_invocation(self):
        self.prepare_native('codex')
        tool = {'tool_name': 'Write', 'tool_input': {'file_path': str(self.root / 'notes.md')},
                'tool_use_id': 'invocation'}
        self.event('PreToolUse', **tool)
        with self.assertRaisesRegex(guard.ReviewError, 'producer'):
            self.event('SubagentStart', agent_id='child', agent_type='reviewer')
        self.assertTrue(guard.read(self.root)['writers'])
        with self.assertRaisesRegex(guard.ReviewError, 'live'):
            guard.recover_writers(self.root)
        self.event('PostToolUse', **tool)
        self.event('SubagentStart', agent_id='child', agent_type='reviewer')
        self.lc('review', 'abandon', '--reason', 'fixture interrupted')
        with self.assertRaises(guard.ReviewError):
            self.event('SubagentStop', agent_id='child', agent_type='reviewer', last_assistant_message=REPORT)
        self.event('SessionStart', session_id='new-parent')
        self.lc('review', 'restart', '--session', 'new-parent',
                '--report', 'knowledge/history/reviews/restarted.md')
        self.event('SubagentStart', session_id='new-parent', agent_id='new-child', agent_type='reviewer')
        self.event('SubagentStop', session_id='new-parent', agent_id='new-child', agent_type='reviewer', last_assistant_message=REPORT)
        self.lc('review', 'save-report')
        self.lc('stage', 'review', '--ref', 'knowledge/history/reviews/restarted.md')
        self.assertTrue(any(h['outcome'] == 'abandoned' for h in guard.read(self.root)['history']))

    def test_interrupted_append_recovery_accepts_only_previous_or_expected(self):
        self.started()
        pins = self.journal()['interval']['pins']
        guard.stop(self.root, 'task', 'claude', 'parent', 'child', REPORT, pins)
        state = {'task': 'task', 'ledger': [{'entry': 'reviewed'}]}
        def fail_before_publication(value):
            raise RuntimeError('interrupted')
        with self.assertRaises(RuntimeError):
            guard.append_evidence(self.root, state, [{'entry': 'new'}], fail_before_publication)
        self.assertIn('interrupted', guard.evidence_problem(self.root, state))
        guard.recover_publication(self.root, state)
        self.assertIsNone(guard.evidence_problem(self.root, state))
        with self.assertRaises(RuntimeError):
            guard.append_evidence(self.root, state, [{'entry': 'aborted'}], fail_before_publication)
        state['ledger'].pop()
        guard.recover_publication(self.root, state)
        self.assertIsNone(guard.evidence_problem(self.root, state))
        with self.assertRaises(RuntimeError):
            guard.append_evidence(self.root, state, [{'entry': 'third'}], fail_before_publication)
        state['ledger'] = [{'entry': 'third-state'}]
        with self.assertRaisesRegex(guard.ReviewError, 'third state'):
            guard.recover_publication(self.root, state)

    def test_owner_exit_does_not_authorize_live_borrower_release(self):
        code = ('import pathlib,time,review_guard as g; '
                'exec("with g.producer(pathlib.Path.cwd()):\\n '
                'pathlib.Path(\'entered\').write_text(\'yes\'); time.sleep(60)")')
        child = None
        try:
            with guard.producer(self.root):
                child = subprocess.Popen([sys.executable, '-c', code], cwd=self.root,
                    env={**os.environ, 'PYTHONPATH': str(self.scripts)},
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                import time
                deadline = time.monotonic() + 10
                while not (self.root / 'entered').exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue((self.root / 'entered').exists())
            self.assertEqual(len(self.journal()['writers']), 1)
            with self.assertRaisesRegex(guard.ReviewError, 'producer'):
                guard.recover_writers(self.root)
        finally:
            if child is not None:
                child.kill()
                child.communicate(timeout=10)
        guard.recover_writers(self.root)
        self.assertEqual(self.journal()['writers'], {})

    def test_exception_releases_quiescent_owner(self):
        with self.assertRaisesRegex(ValueError, 'fixture'):
            with guard.producer(self.root):
                raise ValueError('fixture')
        self.assertEqual(self.journal()['writers'], {})


if __name__ == '__main__':
    unittest.main()
