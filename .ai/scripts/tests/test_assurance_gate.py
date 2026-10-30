"""Assurance increment 2: R1-R8, real CLI completion and evidence boundaries."""
import shutil
import subprocess
import time
from unittest import mock

from test_assurance import Case, CAP, SCOPED, EXCLUDE, SCRIPTS
import assurance
import lifecycle

SPEC = 'docs/task.md'
COMMAND = 'python3 -c "raise SystemExit(0)"'


class GateCase(Case):
    def start(self, tier='L2'):
        if hasattr(self, '_started'):
            time.sleep(max(0, 1.05 - (time.monotonic() - self._started)))
        self.lc('tier', tier, '--new', '--reason', 'gate fixture', '--kind', 'feature')
        self._started = time.monotonic()

    def prepare(self, tier='L2', spec=SPEC):
        if tier == 'L1':
            self.lc('stage', 'intent', '--note', 'fixture; assert success; no assumptions')
            self.lc('stage', 'plan', '--note', 'fixture')
            self.lc('run', 'passing', '--', 'python3', '-V')
            self.lc('stage', 'review', '--note', 'self reviewed')
        else:
            if spec == SPEC:
                self.write(spec, '# Task\n\n## Requirements\n- R1: Tool MUST pass.\n'
                           f'## Acceptance\n- R1: `{COMMAND}` passes.\n'
                           '## Non-goals\nOther work.\n## Open questions\nNone.\n')
            self.write('docs/plan.md', '# Plan\nR1 CALC-R1 CALC-R2 CALC-R3\n')
            self.write('docs/review.md', '## Verdict\nApproved\n## Validation Reviewed\nCALC-R1 All commands.\n')
            self.lc('stage', 'intent', '--ref', spec, '--approved-by', 'human:test')
            self.lc('stage', 'plan', '--ref', 'docs/plan.md')
            self.lc('converge', spec)
            if spec != SPEC:
                self.lc('merge', spec)
            self.lc('stage', 'review', '--ref', 'docs/review.md')
        self.lc('retrospect', '--no-new-lessons', 'fixture')

    def verify(self, code=0):
        if (self.root / 'knowledge').is_dir():
            self.cli('okf.py', 'log', 'Fixture checks recorded.')
        result = self.lc('stage', 'verify', '--note', 'fixture checks passed', code=code)
        state = lifecycle.load(self.root)
        self.assertEqual('verify' in state['stages'], code == 0, result.stdout + result.stderr)
        return result

    def assert_blocked(self, status):
        before = len(self.req_entries())
        result = self.verify(1)
        self.assertIn('CALC-R1', result.stderr)
        self.assertIn(status, result.stderr)
        self.assertIn('assure --run CALC-R1', result.stderr)
        self.assertEqual(len(self.req_entries()), before)


class GateStatusTests(GateCase):  # R1
    def test_unverified_blocks_l2_and_l3_without_running(self):
        for tier in ('L2', 'L3'):
            with self.subTest(tier=tier):
                self.start(tier)
                self.write('src/calc.py', 'ok, changed\n')
                self.prepare(tier)
                self.assert_blocked('UNVERIFIED')

    def test_stale_then_explicit_rerun_allows_verify(self):
        self.start()
        self.lc('assure', '--run')
        self.write('src/calc.py', 'ok, changed\n')
        self.prepare()
        self.assert_blocked('STALE')
        self.lc('assure', '--run', 'CALC-R1')
        self.verify()

    def test_failed_blocks(self):
        self.start()
        self.write('src/calc.py', 'broken\n')
        self.lc('assure', '--run', code=1)
        self.prepare()
        self.assert_blocked('FAILED')

    def test_invalid_blocks_with_repair_hint(self):
        self.start()
        self.capability(SCOPED.replace('`python3 check.py`', 'bad command'))
        self.prepare()
        self.assert_blocked('INVALID')


class GatePolicyTests(GateCase):  # R4
    def test_fresh_manual_and_undeclared_pass(self):
        self.start()
        self.capability(SCOPED + '- CALC-R2: Appearance MUST be reviewed.\n'
                        '  - Verify: manual - reviewer judgment\n'
                        '- CALC-R3: Dates MUST be preserved.\n')
        self.lc('assure', '--run')
        self.prepare()
        self.verify()

    def test_risk_and_attestation_never_waive(self):
        self.start()
        for date in ('2000-01-01', '2999-01-01'):
            with self.subTest(date=date):
                self.capability(SCOPED.replace('  - Scenario',
                    f'  - Accept-risk: {date} by human:test - accepted\n  - Scenario'))
                self.prepare()
                self.assert_blocked('UNVERIFIED')


class CompatibilityTests(GateCase):  # R5
    def test_l1_keeps_existing_behavior(self):
        self.start('L1')
        self.write('src/calc.py', 'changed\n')
        self.prepare('L1')
        self.verify()

    def test_no_bundle_and_no_requirements(self):
        self.capability('')
        self.start()
        self.prepare()
        self.verify()
        shutil.rmtree(self.root / 'knowledge')
        self.write('.agentic.json', '{"repository_kind":"framework"}\n')
        self.start()
        self.prepare()
        self.verify()
        self.assertFalse((self.root / 'knowledge').exists())

    def test_existing_prerequisites_remain_required(self):
        self.start()
        self.verify(1)


class TouchedScopeTests(GateCase):  # R2
    def selected(self):
        return {o.id for o in assurance.touched(self.root, lifecycle.load(self.root)['head'],
                                                assurance.requirements(self.root)[0])}

    def test_all_path_states_and_task_start_baseline(self):
        self.start()
        self.assertEqual(self.selected(), set())
        self.write('src/calc.py', 'ok, edited\n')
        self.assertEqual(self.selected(), {'CALC-R1'})
        self.git('add', 'src/calc.py')
        self.assertEqual(self.selected(), {'CALC-R1'})
        self.git('restore', '--staged', '--worktree', 'src/calc.py')
        self.write('src/new\nfile.py', 'ok\n')
        self.assertEqual(self.selected(), {'CALC-R1'})
        (self.root / 'src/new\nfile.py').unlink()
        (self.root / 'src/calc.py').unlink()
        self.assertEqual(self.selected(), {'CALC-R1'})
        self.git('restore', 'src/calc.py')
        self.git('mv', 'check.py', 'renamed.py')
        self.assertEqual(self.selected(), {'CALC-R1'})
        self.git('restore', '--staged', '--worktree', 'check.py')
        (self.root / 'renamed.py').unlink()
        self.write('src/calc.py', 'ok, later commit\n')
        self.commit('later task commit')
        self.assertEqual(self.selected(), {'CALC-R1'})
        self.prepare()
        self.assert_blocked('UNVERIFIED')

    def test_blocks_unrelated_and_ordered_exclusions(self):
        scoped = SCOPED.replace('`src/**`', '`src/**` `!src/skip*`')
        self.capability(scoped +
                        '- CALC-R2: Other MUST pass.\n  - Verify: `python3 -V`\n  - Inputs: `other/**`\n')
        self.commit('scopes')
        self.start()
        self.write('src/skip.py', 'excluded\n')
        self.write('notes.txt', 'unrelated\n')
        self.assertEqual(self.selected(), set())
        self.capability(scoped.replace('`python3 check.py`', '`python3 check.py --new`'))
        self.assertEqual(self.selected(), {'CALC-R1'})
        self.prepare()
        self.assert_blocked('UNVERIFIED')

    def test_prose_edit_reuses_fresh_evidence(self):
        self.start()
        self.lc('assure', '--run')
        self.capability(SCOPED.replace('MUST add', 'MUST calculate sums'))
        self.assertEqual(self.selected(), {'CALC-R1'})
        self.prepare()
        self.verify()

    def test_whole_tree_is_conservative(self):
        self.capability(SCOPED.replace('  - Inputs: `check.py` `src/**`\n', ''))
        self.commit('whole tree')
        self.start()
        self.lc('assure', '--run')
        self.write('notes.txt', 'unrelated edit\n')
        self.assertEqual(self.selected(), {'CALC-R1'})
        self.prepare()
        self.assert_blocked('STALE')

    def test_unchanged_crlf_blocks_are_not_touched(self):
        path = self.root / CAP
        path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        self.commit('CRLF capability')
        self.start()
        self.assertEqual(self.selected(), set())
        self.prepare()
        self.verify()


class GateFailureTests(GateCase):  # R3
    def test_bad_baseline_refuses_instead_of_skipping(self):
        self.start()
        self.prepare()
        state = lifecycle.load(self.root)
        state['head'] = 'not-a-commit'
        lifecycle.save(self.root, state)
        result = self.verify(1)
        self.assertIn('assurance', result.stderr)
        self.assertIn('baseline', result.stderr)

    def test_git_errors_are_not_empty_selection(self):
        self.start()
        original = assurance._git
        def broken(root, *args, **kwargs):
            if args[0] == 'diff':
                return subprocess.CompletedProcess(args, 1, '', 'broken diff')
            return original(root, *args, **kwargs)
        with mock.patch.object(assurance, '_git', side_effect=broken):
            with self.assertRaisesRegex(ValueError, 'broken diff'):
                assurance.touched(self.root, lifecycle.load(self.root)['head'],
                                  assurance.requirements(self.root)[0])

    def test_malformed_evidence_does_not_disappear(self):
        self.start()
        self.write('src/calc.py', 'ok, edited\n')
        self.prepare()
        self.write('knowledge/history/lifecycle/bad.json', '{')
        result = self.verify(1)
        self.assertIn('bad.json', result.stderr)

    def test_capability_diagnostic_refuses(self):
        self.start()
        self.prepare()
        self.write('knowledge/capabilities/bad.md', '---\ntype: Capability\nnamespace: BAD\n---\n'
                   '## Requirements\n- BAD-R1: Tool MUST pass.\n- BAD-R1: Tool MUST fail.\n')
        result = self.verify(1)
        self.assertIn('assurance', result.stderr)
        self.assertIn('bad.md', result.stderr)


class DeltaCase(GateCase):
    def setUp(self):
        super().setUp()
        self.write('count.py', 'from pathlib import Path\n'
                   'p = Path("runs.md")\np.write_text(p.read_text() + "x" if p.exists() else "x")\n')
        self.commit('counter')

    def delta(self, kind='modified', command='python3 count.py', acceptance=None, scoped=True):
        rid = 'CALC-R2' if kind == 'added' else 'CALC-R1'
        old = assurance.requirements(self.root)[0][0].block_sha256
        pin = 'absent' if kind == 'added' else 'sha256:' + old
        block = f'- {rid}: Calculator MUST count executions.\n'
        if kind == 'removed':
            block = f'- {rid}: Calculator MUST retire addition. Reason: obsolete.\n'
        elif command == 'manual':
            block += '  - Verify: manual - reviewer judgment\n'
        elif command:
            block += f'  - Verify: `{command}`\n'
            if scoped:
                block += '  - Inputs: `count.py` `src/**`\n'
        sections = ''.join(f'## {title} requirements\n\n{block if title.lower() == kind else "None."}\n\n'
                           for title in ('Added', 'Modified', 'Removed'))
        self._delta_number = getattr(self, '_delta_number', 0) + 1
        path = f'knowledge/specifications/delta-{self._delta_number}.md'
        self.write(path, '---\ntype: Specification\nstatus: draft\ntarget: /capabilities/calc.md\n---\n'
                   '# Change\n## Target baseline\nTarget: /capabilities/calc.md\n'
                   f'- {rid}: {pin}\n\n' + sections +
                   f'## Acceptance\n- {rid}: `{acceptance or command or COMMAND}` passes.\n'
                   '## Constraints\nNone.\n## Non-goals\nOther work.\n'
                   '## Assumptions\nNone.\n## Open questions\nNone.\n')
        self.cli('okf.py', 'reindex')
        return path

    def approve_delta(self, spec):
        self.start()
        self.lc('stage', 'intent', '--ref', spec, '--approved-by', 'human:test')
        self.write('docs/plan.md', '# Plan\nCALC-R1 CALC-R2\n')
        self.lc('stage', 'plan', '--ref', 'docs/plan.md')

    def req_entries(self):
        return [e for e in lifecycle.load(self.root).get('ledger', []) if e['label'].startswith('req:')]


class DeltaEvidenceTests(DeltaCase):  # R6
    def test_nested_run_evidence_survives_converge_publication(self):
        self.write('count.py', 'import subprocess, sys\n'
                   'subprocess.run([sys.executable, ".ai/scripts/lifecycle.py", "run", "inner", "--", '
                   '"python3", "-V"], check=True)\n')
        spec = self.delta()
        self.approve_delta(spec)
        self.lc('converge', spec)
        self.assertEqual([e['label'] for e in lifecycle.load(self.root)['ledger']],
                         ['inner', 'converge:CALC-R1', 'req:CALC-R1'])

    def test_matching_add_and_modify_execute_once_and_verify(self):
        for kind in ('modified', 'added'):
            with self.subTest(kind=kind):
                spec = self.delta(kind)
                self.start()
                before = (self.root / 'runs.md').read_text() if (self.root / 'runs.md').exists() else ''
                self.prepare(spec=spec)
                rid = 'CALC-R2' if kind == 'added' else 'CALC-R1'
                entries = [e for e in lifecycle.load(self.root)['ledger'] if e['label'] == 'req:' + rid]
                self.assertEqual(len(entries), 1)
                [entry] = entries
                self.assertEqual(entry['argv'], ['python3', 'count.py'])
                self.assertEqual(entry['inputs'], ['count.py', 'src/**', EXCLUDE])
                self.assertEqual(set(entry['input_files']), {'count.py', 'src/calc.py'})
                self.assertTrue(entry['runtime_sha256'])
                self.assertEqual(entry['exit'], 0)
                self.assertEqual((self.root / 'runs.md').read_text(), before + 'x')
                self.assertEqual(self.status(rid)['status'], 'VERIFIED')
                if kind == 'modified':
                    self.assertIn('Scenario add', (self.root / CAP).read_text())
                self.verify()

    def test_whole_tree_evidence_uses_existing_contract(self):
        spec = self.delta(scoped=False)
        self.start()
        self.prepare(spec=spec)
        [entry] = [e for e in self.req_entries() if e['label'] == 'req:CALC-R1']
        self.assertEqual(entry['inputs'], [])
        self.assertEqual(self.status('CALC-R1')['status'], 'VERIFIED')
        self.verify()

    def test_operated_id_selected_even_if_task_baseline_already_contains_block(self):
        spec = self.delta()
        self.start()
        self.prepare(spec=spec)
        state = lifecycle.load(self.root)
        self.commit('merged delta')
        state['head'] = self.git('rev-parse', 'HEAD').strip()
        state['ledger'] = [e for e in state['ledger'] if not e['label'].startswith('req:')]
        lifecycle.save(self.root, state)
        self.lc('converge', spec)
        state = lifecycle.load(self.root)
        state['ledger'] = [e for e in state['ledger'] if not e['label'].startswith('req:')]
        lifecycle.save(self.root, state)
        self.assert_blocked('UNVERIFIED')


class EvidenceBoundaryTests(DeltaCase):  # R7
    def test_later_completed_failure_outranks_nested_pass(self):
        self.write('count.py', 'from pathlib import Path\nimport subprocess, sys, time\n'
                   'p = Path("nested.md")\n'
                   'if p.exists():\n    raise SystemExit(0)\n'
                   'p.write_text("nested")\ntime.sleep(1.1)\n'
                   'subprocess.run([sys.executable, ".ai/scripts/lifecycle.py", "run", "req:CALC-R1", '
                   '"--inputs", "count.py", "src/**", "' + EXCLUDE + '", "--", '
                   '"python3", "count.py"], check=True)\ntime.sleep(1.1)\nraise SystemExit(3)\n')
        spec = self.delta()
        self.approve_delta(spec)
        self.lc('converge', spec, code=1)
        self.lc('merge', spec)
        self.assertEqual([e['exit'] for e in self.req_entries()], [0, 3])
        self.assertEqual(self.status('CALC-R1')['status'], 'FAILED')

    def test_different_command_and_removed_id_do_not_produce_evidence(self):
        spec = self.delta(acceptance=COMMAND)
        self.approve_delta(spec)
        self.lc('converge', spec)
        self.assertEqual(self.req_entries(), [])
        self.lc('merge', spec)
        self.write('docs/review.md', '## Verdict\nApproved\n')
        self.lc('stage', 'review', '--ref', 'docs/review.md')
        self.lc('retrospect', '--no-new-lessons', 'fixture')
        self.assert_blocked('UNVERIFIED')
        spec = self.delta(kind='removed', acceptance=COMMAND)
        self.start()
        self.prepare(spec=spec)
        self.assertEqual(lifecycle.load(self.root)['ledger'][-1]['label'], 'converge:CALC-R1')
        self.assertEqual(assurance.requirements(self.root)[0], [])
        self.verify()

    def test_manual_undeclared_invalid_and_legacy_do_not_map(self):
        for command in ('manual', '', 'broken `command'):
            with self.subTest(command=command):
                spec = self.delta(command=command, acceptance=COMMAND)
                self.approve_delta(spec)
                self.lc('converge', spec)
                self.assertEqual(self.req_entries(), [])
        self.start()
        self.prepare()
        self.assertEqual(self.req_entries(), [])

    def test_failed_unlaunchable_and_timeout_never_pass(self):
        for command in ('python3 -c "raise SystemExit(3)"', 'no-such-assurance-command',
                        'python3 -c "import time; time.sleep(2)"'):
            with self.subTest(command=command):
                spec = self.delta(command=command)
                self.approve_delta(spec)
                self.lc('converge', spec, '--timeout', '1', code=1)
                [entry] = self.req_entries()
                self.assertNotEqual(entry['exit'], 0)
                self.lc('merge', spec)
                self.assertEqual(self.status('CALC-R1')['status'], 'FAILED')

    def test_self_modified_inputs_are_stale(self):
        for scoped in (True, False):
            with self.subTest(scoped=scoped):
                self.write('count.py', 'from pathlib import Path\nPath("src/calc.py").write_text("changed")\n')
                self.write('src/calc.py', 'ok\n')
                spec = self.delta(scoped=scoped)
                self.approve_delta(spec)
                self.lc('converge', spec)
                self.lc('merge', spec)
                self.assertEqual(self.status('CALC-R1')['status'], 'STALE')


class DocumentationTests(Case):  # R8
    def test_guide_describes_gate_and_evidence_limits(self):
        text = (SCRIPTS.parent / 'lifecycle.md').read_text()
        for phrase in ('task-start', 'assurance gate', 'prose-only', 'exact', 'assure --run',
                       'whole tree', 'unmerged', 'under-declared'):
            self.assertIn(phrase, text)
