"""C2: precision-aware mechanical evidence, approved R1–R7 acceptance."""
import dataclasses
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_assurance import Case, CAP, RECORDS, SCOPED, EXCLUDE, SCRIPTS
from test_assurance_gate import GateCase, DeltaCase
import assurance
import ledger
import lifecycle


# Disposable producers use a clock seam, never a production clock option. The
# old strftime formatter still truncates this clock, so the original bug is RED.
CLOCK = '''from datetime import datetime as _c2_datetime, timedelta as _c2_delta
class datetime(_c2_datetime):
    @classmethod
    def now(cls, tz=None):
        clock = Path(os.environ["C2_FIXTURE_CLOCK"])
        value = _c2_datetime.fromisoformat(clock.read_text().strip().replace("Z", "+00:00"))
        if os.environ.get("C2_FIXTURE_AUTO"):
            clock.write_text((value + _c2_delta(microseconds=1)).isoformat())
        return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)
'''
CHECK = '''import os
from pathlib import Path
p = Path("runs.md")
p.write_text((p.read_text() if p.exists() else "") + "x")
if os.environ.get("C2_FIXTURE_FINISH"):
    Path(os.environ["C2_FIXTURE_CLOCK"]).write_text(os.environ["C2_FIXTURE_FINISH"])
if os.environ.get("C2_FIXTURE_MUTATE"):
    Path("src/calc.py").write_text("changed during execution")
raise SystemExit(int(os.environ.get("C2_FIXTURE_EXIT", "0")))
'''


def install_clock(scripts):
    path = scripts / 'lifecycle.py'
    original = path.read_bytes()
    source = original.decode()
    marker = 'from datetime import datetime, timezone\n'
    if source.count(marker) != 1:
        raise AssertionError('clock seam needs the original single datetime import')
    changed = source.replace(marker, marker + CLOCK).encode()
    path.write_bytes(changed)
    if path.read_bytes() != changed:
        raise AssertionError('clock seam bytes were not applied')
    return original


class ClockCase(Case):
    def setUp(self):
        super().setUp()
        self.clock = Path(self.temp.name) / 'clock'
        self.set_clock('2026-10-28T01:00:00.100000Z')
        self.env['C2_FIXTURE_CLOCK'] = str(self.clock)
        self.original_lifecycle = install_clock(self.scripts)
        self.addCleanup(self.restore_clock)
        self.write('check.py', CHECK)
        self.commit('controlled clock and nondeterministic outcome fixture')

    def restore_clock(self):
        path = self.scripts / 'lifecycle.py'
        path.write_bytes(self.original_lifecycle)
        self.assertEqual(path.read_bytes(), self.original_lifecycle)

    def set_clock(self, value):
        self.clock.write_text(value)

    def start(self, tier='L1'):
        self.lc('tier', tier, '--new', '--reason', 'ordering fixture', '--kind', 'feature')

    def state(self):
        return lifecycle.load(self.root)

    @contextmanager
    def runtime_trace(self):
        path = self.scripts / 'ledger.py'
        original = path.read_bytes()
        marker = '    executable = shutil.which(argv[0]) if argv else None\n'
        trace = Path(self.temp.name) / 'runtime-times'
        addition = ('    _trace = Path(os.environ["C2_RUNTIME_TRACE"])\n'
                    '    _trace.write_text((_trace.read_text() if _trace.exists() else "")\n'
                    '                      + Path(os.environ["C2_FIXTURE_CLOCK"]).read_text() + "\\n")\n')
        self.assertEqual(original.decode().count(marker), 1)
        changed = original.decode().replace(marker, addition + marker).encode()
        path.write_bytes(changed)
        self.assertEqual(path.read_bytes(), changed)
        self.env['C2_RUNTIME_TRACE'] = str(trace)
        try:
            yield trace
        finally:
            self.env.pop('C2_RUNTIME_TRACE', None)
            path.write_bytes(original)
            self.assertEqual(path.read_bytes(), original)

    def run_outcome(self, outcome=0):
        self.env['C2_FIXTURE_EXIT'] = str(outcome)
        result = self.lc('assure', '--run', 'CALC-R1', code=0 if outcome == 0 else 1)
        entry = self.state()['ledger'][-1]
        self.assertEqual(entry['label'], 'req:CALC-R1')
        self.assertEqual(entry['exit'], outcome)
        return entry, result

    def pair(self, first, second, published=False, later='2026-10-28T01:00:00.200000Z'):
        self.start()
        old, _ = self.run_outcome(first)
        path = self.root / RECORDS / (self.state()['task'] + '.json')
        original = path.read_bytes()
        archived = path.with_name('zz-older.json')
        path.rename(archived)
        self.assertEqual(archived.read_bytes(), original)
        self.commit('publish the first execution')
        self.set_clock(later)
        self.start()
        new, _ = self.run_outcome(second)
        for key in ('argv', 'inputs', 'inputs_sha256', 'input_files', 'runtime_sha256'):
            self.assertEqual(old.get(key), new.get(key), key)
        self.assertEqual((self.root / 'runs.md').read_text(), 'xx', 'two real executions required')
        state_path = lifecycle.state_path(self.root, write=False)
        saved = state_path.read_bytes()
        if published:
            state_path.unlink()
        try:
            item = self.status('CALC-R1')
        finally:
            if published:
                state_path.write_bytes(saved)
                self.assertEqual(state_path.read_bytes(), saved)
        return item, old, new


class MechanicalOrderingEndToEndTests(ClockCase):  # R5; first regression also R1/R2
    def test_nested_restoration_failure_fails_acceptance(self):
        original = ClockCase
        def broken_case():
            nested = original()
            def fail_restore():
                raise AssertionError('deliberate nested restoration failure')
            nested.addCleanup(fail_restore)
            return nested
        result = unittest.TestResult()
        with mock.patch.dict(globals(), {'ClockCase': broken_case}):
            outer = MechanicalOrderingEndToEndTests('test_later_success_and_published_readers')
            outer.run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertFalse(result.errors, result.errors)
        self.assertTrue(result.failures, 'nested restoration failure must fail enclosing acceptance')

    def test_later_failure_wins_across_tasks(self):
        item, _, _ = self.pair(0, 3)
        self.assertEqual(item['status'], 'FAILED', 'later failing execution must win over older PASS')

    def test_later_success_and_published_readers(self):
        for published in (False, True):
            with self.subTest(published=published):
                case = ClockCase()
                case.setUp()
                try:
                    item, _, _ = case.pair(3, 0, published=published)
                    self.assertEqual(item['status'], 'VERIFIED')
                finally:
                    self.assertTrue(case.doCleanups(), 'nested fixture restoration failed')

    def test_published_reader_keeps_later_failure(self):
        item, _, _ = self.pair(0, 3, published=True)
        self.assertEqual(item['status'], 'FAILED')

    def test_rollback_only_orders_recorded_time(self):
        item, _, _ = self.pair(0, 3, later='2026-10-28T01:00:00.050000Z')
        self.assertEqual(item['status'], 'VERIFIED', 'recorded time cannot infer a clock reversal')

    def test_measurement_handoff_has_no_ordering_sleep(self):
        import assurance_measure
        self.assertFalse('time.sleep' in (SCRIPTS / 'assurance_measure.py').read_text(),
                         'handoff must exercise ordering without a sleep workaround')
        self.set_clock('2026-10-28T01:00:00.100000Z')
        pending, restored = {}, []
        original_remove = shutil.rmtree
        def hook(scripts):
            pending[scripts / 'lifecycle.py'] = install_clock(scripts)
        def restore_before_remove(directory, *args, **kwargs):
            for path, original in list(pending.items()):
                if path.is_relative_to(Path(directory)):
                    path.write_bytes(original)
                    self.assertTrue(path.read_bytes() == original, 'measurement clock restoration failed')
                    restored.append(path)
                    del pending[path]
            return original_remove(directory, *args, **kwargs)
        with mock.patch.dict(os.environ, {'C2_FIXTURE_CLOCK': str(self.clock), 'C2_FIXTURE_AUTO': '1'}), \
                mock.patch.object(shutil, 'rmtree', restore_before_remove):
            data = assurance_measure.measure(base=Path(self.temp.name), hook=hook, only=('handoff',))
        self.assertEqual(pending, {})
        self.assertEqual(len(restored), 1)
        self.assertEqual(data['failures'], [])
        self.assertEqual(data['totals'], dict(caught=1, false_stale=0, missed=0,
                                              changed_missed=0, reruns=1, baseline_reruns=2))
        self.assertEqual(data['contribution']['handoff_from_record'], 1)

    def test_measurement_restores_clock_seam_before_disposal(self):
        saved = {}
        original_install, original_remove = install_clock, shutil.rmtree
        def track(scripts):
            original = original_install(scripts)
            saved[scripts / 'lifecycle.py'] = original
            return original
        def check_before_remove(directory, *args, **kwargs):
            try:
                for path, original in saved.items():
                    if path.is_relative_to(Path(directory)):
                        self.assertTrue(path.read_bytes() == original,
                                        'measurement clock seam must be restored before disposal')
            finally:
                original_remove(directory, *args, **kwargs)
        with mock.patch.dict(globals(), {'install_clock': track}), \
                mock.patch.object(shutil, 'rmtree', check_before_remove):
            self.test_measurement_handoff_has_no_ordering_sleep()
        self.assertEqual(len(saved), 1, 'the real handoff fixture clock must be observed')

    def test_delayed_publication_keeps_later_nested_failure(self):
        case = MechanicalOrderingProducerTests()
        case.setUp()
        try:
            case.delayed_publication()
        finally:
            self.assertTrue(case.doCleanups(), 'nested fixture restoration failed')


class SelectionCase(unittest.TestCase):
    def setUp(self):
        self.obligation = assurance.parse('CALC-R1', CAP, SCOPED)

    def event(self, at, outcome=0, record='r.json', index=0, **extra):
        entry = dict(label='req:CALC-R1', argv=['python3', 'check.py'],
                     inputs=['check.py', 'src/**', EXCLUDE], at=at, exit=outcome)
        entry.update(extra)
        return assurance.Evidence(record, index, entry)

    def evaluate(self, *items, fresh=True):
        with mock.patch.object(ledger, '_entry_verdict', return_value=(fresh, 'input changed')):
            return assurance.evaluate(Path('.'), self.obligation, list(items), 'tree')

    def uncertain(self, *items, metadata=False):
        result = self.evaluate(*items)
        self.assertEqual(result['status'], 'UNVERIFIED', 'ordering uncertainty must not restore PASS')
        self.assertEqual(result['basis'], 'none')
        self.assertIsNone(result['evidence'])
        self.assertIn('ordering', result['reason'])
        self.assertIn('reconcile' if metadata else 'run', result['reason'])
        for item in items:
            if not metadata or item.entry.get('at') in (None, '', 'bad'):
                self.assertIn(item.record, result['reason'])
        return result


class MechanicalOrderingSelectionTests(SelectionCase):  # R1
    def test_latest_outcome_not_names_indices_or_enumeration(self):
        old = self.event('2026-10-28T01:00:00.100000Z', record='zz.json', index=99)
        new = self.event('2026-10-28T01:00:00.200000Z', 3, record='aa.json')
        for items in ((old, new), (new, old)):
            self.assertEqual(self.evaluate(*items)['status'], 'FAILED')
        new.entry['exit'] = None
        self.assertEqual(self.evaluate(old, new)['status'], 'FAILED')
        new.entry['exit'] = 0
        old.entry['exit'] = 3
        self.assertEqual(self.evaluate(old, new)['status'], 'VERIFIED')
        self.assertEqual(self.evaluate(old, new, fresh=False)['status'], 'STALE')

    def test_matching_precedes_order_validation(self):
        good = self.event('2026-10-28T01:00:00Z')
        for changes in ({'label': 'req:OTHER-R1'}, {'argv': ['other']},
                        {'inputs': [EXCLUDE, 'src/**', 'check.py']}):
            with self.subTest(changes=changes):
                bad = self.event(None, record='bad.json', **changes)
                self.assertEqual(self.evaluate(good, bad)['status'], 'VERIFIED')

    def test_completion_not_append_publication_order(self):
        later = self.event('2026-10-28T01:00:00.900000Z', 3, index=0)
        published_last = self.event('2026-10-28T01:00:00.100000Z', index=1)
        self.assertEqual(self.evaluate(later, published_last)['status'], 'FAILED')


class MechanicalOrderingLegacyTests(SelectionCase):  # R3
    def test_single_and_disjoint_legacy_intervals(self):
        old = self.event('2026-10-28T01:00:00Z')
        self.assertEqual(self.evaluate(old)['status'], 'VERIFIED')
        later = self.event('2026-10-28T01:00:01Z', 3)
        self.assertEqual(self.evaluate(old, later)['status'], 'FAILED')
        for digits in range(1, 7):
            early = self.event('2026-10-28T01:00:00.' + '1' * digits + 'Z')
            late = self.event('2026-10-28T01:00:00.900000Z', 3)
            self.assertEqual(self.evaluate(early, late)['status'], 'FAILED')

    def test_cross_record_overlap_has_no_filename_tiebreak(self):
        self.uncertain(self.event('2026-10-28T01:00:00Z', record='zz.json'),
                       self.event('2026-10-28T01:00:00Z', 3, record='aa.json'))

    def test_same_record_overlap_has_no_index_tiebreak(self):
        self.uncertain(self.event('2026-10-28T01:00:00.123456Z', index=0),
                       self.event('2026-10-28T01:00:00.123456Z', 3, index=1))

    def test_legacy_fractional_overlap_is_unverified(self):
        self.uncertain(self.event('2026-10-28T01:00:00Z', record='legacy.json'),
                       self.event('2026-10-28T01:00:00.500000Z', record='new.json'))

    def test_overlap_does_not_fall_back_to_a_pass(self):
        self.uncertain(self.event('2026-10-28T01:00:00Z', record='pass.json'),
                       self.event('2026-10-28T01:00:00.500000Z', 3, record='fail.json'))

    def test_all_pass_equal_bytes_and_zero_padding_stay_ambiguous(self):
        first = self.event('2026-10-28T01:00:00.100Z', record='one.json')
        same = self.event('2026-10-28T01:00:00.100Z', record='two.json')
        self.uncertain(first, same)
        same.entry['at'] = '2026-10-28T01:00:00.100000Z'
        self.uncertain(first, same)

    def test_adjacent_intervals_and_calendar_endpoint(self):
        for first, second in (
                ('2024-02-29T23:59:59.9Z', '2024-03-01T00:00:00Z'),
                ('2026-10-28T01:00:00.1Z', '2026-10-28T01:00:00.2Z'),
                ('9999-12-31T23:59:59.999998Z', '9999-12-31T23:59:59.999999Z')):
            with self.subTest(first=first):
                self.assertEqual(self.evaluate(self.event(first), self.event(second, 3))['status'], 'FAILED')

    def test_active_representation_suppresses_its_published_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            entry = self.event('2026-10-28T01:00:00Z').entry
            state = {'task': 'one', 'ledger': [entry]}
            Path(directory, 'one.json').write_text(json.dumps(state))
            items, diagnostics = assurance.evidence(Path(directory), state)
            self.assertEqual(diagnostics, [])
            self.assertEqual(len(items), 1)
            self.assertEqual(self.evaluate(*items)['status'], 'VERIFIED')


class MechanicalOrderingInvalidMetadataTests(SelectionCase):  # R4
    def test_bad_matching_time_cannot_restore_an_older_pass(self):
        for value in (None, '', 'bad', 3, [], {}, '2026-02-30T00:00:00Z',
                      '2026-10-28T24:00:00Z', '2026-10-28T01:00:00+00:00',
                      '2026-10-28T01:00:00.1234567Z', '2026-10-28T01:00:00',
                      '２０２６-10-28T01:00:00Z'):
            with self.subTest(value=value):
                good = self.event('2026-10-27T00:00:00Z', record='older.json')
                bad = self.event(value, record='bad.json')
                item = self.uncertain(good, bad, metadata=True)
                self.assertIn('bad.json', item['reason'])
                # A valid later rerun cannot dominate unknown completion time.
                self.uncertain(good, bad, self.event('2026-10-29T00:00:00Z'), metadata=True)
        missing = self.event(None, record='bad.json')
        del missing.entry['at']
        self.uncertain(missing, metadata=True)


class MechanicalOrderingProducerTests(ClockCase, DeltaCase):  # R2
    def approve(self, spec):
        self.start('L2')
        self.lc('stage', 'intent', '--ref', spec, '--approved-by', 'human:test')
        self.write('docs/plan.md', '# Plan\nCALC-R1 CALC-R2\n')
        self.lc('stage', 'plan', '--ref', 'docs/plan.md')

    def test_requirement_completion_precision(self):
        self.start()
        entry, _ = self.run_outcome()
        self.assertRegex(entry['at'], r'^2026-10-28T01:00:00\.\d{6}Z$')
        self.assertIn('input_files', entry)
        self.assertIn('runtime_sha256', entry)
        self.lc('run', 'req:CALC-R1', '--inputs', 'check.py', 'src/**', EXCLUDE,
                '--', 'python3', 'check.py')
        direct = self.state()['ledger'][-1]
        self.assertRegex(direct['at'], r'\.\d{6}Z$')
        self.assertEqual(direct['inputs'], entry['inputs'])
        self.assertEqual(direct['inputs_sha256'], entry['inputs_sha256'])
        self.assertNotIn('input_files', direct)
        self.assertNotIn('runtime_sha256', direct)
        self.lc('run', 'ordinary', '--', 'python3', '-V')
        self.assertEqual(self.state()['ledger'][-1]['at'], '2026-10-28T01:00:00Z')

    def test_completion_follows_execution_and_fingerprints_precede_it(self):
        self.start()
        self.env['C2_FIXTURE_FINISH'] = '2026-10-28T01:00:00.200000Z'
        self.env['C2_FIXTURE_MUTATE'] = '1'
        before = ledger.inputs_snapshot(self.root, ['check.py', 'src/**', EXCLUDE])
        with self.runtime_trace() as trace:
            entry, _ = self.run_outcome()
            self.assertEqual(trace.read_text().splitlines(), ['2026-10-28T01:00:00.100000Z'])
        self.assertEqual(entry['at'], self.env['C2_FIXTURE_FINISH'])
        self.assertEqual(entry['input_files'], before)
        self.assertNotEqual(entry['input_files'], ledger.inputs_snapshot(self.root, entry['inputs']))
        self.assertEqual(self.status('CALC-R1')['status'], 'STALE')

    def two_delta(self, nested=False):
        self.write('count.py', CHECK)
        second = CHECK.replace('raise SystemExit',
                    'Path(os.environ["C2_FIXTURE_CLOCK"]).write_text("2026-10-28T01:00:00.300000Z")\nraise SystemExit')
        if nested:
            second = ('import os, subprocess, sys\n'
                      'os.environ["C2_FIXTURE_EXIT"] = "3"\n'
                      'os.environ["C2_FIXTURE_FINISH"] = "2026-10-28T01:00:00.300000Z"\n'
                      'r = subprocess.run([sys.executable, ".ai/scripts/lifecycle.py", "run", "req:CALC-R1", '
                      '"--inputs", "count.py", "src/**", ' + repr(EXCLUDE) + ', '
                      '"--", "python3", "count.py"])\n'
                      'assert r.returncode == 3, r.returncode\n')
        self.write('second.py', second)
        second_block = ('- CALC-R2: Calculator MUST run the second check.\n'
                        '  - Verify: `python3 second.py`\n  - Inputs: `second.py` `src/**`\n')
        self.capability(SCOPED + second_block)
        second_pin = assurance.requirements(self.root)[0][1].block_sha256
        self.commit('two existing obligations in deterministic command order')
        spec = self.delta()
        path = self.root / spec
        source = path.read_text().replace('\n## Removed requirements',
                                          '\n' + second_block + '\n## Removed requirements', 1)
        source = source.replace('\n## Added requirements',
                                '\n- CALC-R2: sha256:' + second_pin + '\n\n## Added requirements', 1)
        source = source.replace('## Constraints',
            '- CALC-R2: `python3 second.py` passes.\n## Constraints', 1)
        path.write_text(source)
        self.approve(spec)
        self.env['C2_FIXTURE_FINISH'] = '2026-10-28T01:00:00.200000Z'
        return spec

    def test_converge_records_each_completion(self):
        spec = self.two_delta()
        with self.runtime_trace() as trace:
            result = self.lc('converge', spec)
            self.assertLess(result.stdout.index('CALC-R1 PASS'), result.stdout.index('CALC-R2 PASS'))
            self.assertEqual(trace.read_text().splitlines(), ['2026-10-28T01:00:00.100000Z',
                                                            '2026-10-28T01:00:00.200000Z'])
        entries = [e for e in self.state()['ledger'] if e['label'].startswith('req:')]
        self.assertEqual(len(entries), 2)
        times = {e['label']: e['at'] for e in entries}
        self.assertEqual(times, {'req:CALC-R1': '2026-10-28T01:00:00.200000Z',
                                 'req:CALC-R2': '2026-10-28T01:00:00.300000Z'})
        for entry in entries:
            self.assertEqual(entry['exit'], 0)
            self.assertIn('input_files', entry)
            self.assertIn('runtime_sha256', entry)
        self.assertEqual((self.root / 'runs.md').read_text(), 'xx')

    def delayed_publication(self):
        spec = self.two_delta(nested=True)
        self.lc('converge', spec)
        self.lc('merge', spec)
        entries = [e for e in self.state()['ledger'] if e['label'] == 'req:CALC-R1']
        self.assertEqual([e['exit'] for e in entries], [3, 0], 'earlier completion publishes last')
        self.assertEqual([e['at'] for e in entries], ['2026-10-28T01:00:00.300000Z',
                                                    '2026-10-28T01:00:00.200000Z'])
        self.assertEqual(entries[0]['argv'], entries[1]['argv'])
        self.assertEqual(entries[0]['inputs'], entries[1]['inputs'])
        self.assertEqual(entries[0]['inputs_sha256'], entries[1]['inputs_sha256'])
        self.assertEqual(self.status('CALC-R1')['status'], 'FAILED')
        self.assertEqual((self.root / 'runs.md').read_text(), 'xx')

    def test_mechanical_normalization_preserves_golden_content(self):
        from test_assurance_attested import normalise
        for value in ('2026-10-28T01:00:00Z', '2026-10-28T01:00:00.123456Z'):
            self.assertEqual(normalise('VERIFIED at=' + value + ' - unchanged claim'),
                             'VERIFIED at=NOW - unchanged claim')


class MechanicalOrderingCompatibilityTests(ClockCase, GateCase):  # R6
    def test_ambiguous_evidence_blocks_l2_and_l3(self):
        for tier in ('L2', 'L3'):
            with self.subTest(tier=tier):
                case = MechanicalOrderingCompatibilityTests()
                case.setUp()
                try:
                    item, _, _ = case.pair(0, 0, later='2026-10-28T01:00:00.100000Z')
                    self.assertEqual(item['status'], 'UNVERIFIED')
                    case.start(tier)  # ClockCase.start has no GateCase ordering sleep.
                    case.capability(SCOPED.replace('MUST add.', 'MUST add correctly.'))
                    case.prepare(tier)
                    before = (case.root / 'runs.md').read_text()
                    case.assert_blocked('UNVERIFIED')
                    self.assertEqual((case.root / 'runs.md').read_text(), before)
                    self.assertNotIn('verify', case.state()['stages'])
                    case.set_clock('2026-10-28T01:00:01.100000Z')
                    case.run_outcome(0)
                    self.assertEqual(case.status('CALC-R1')['status'], 'VERIFIED')
                    case.verify()
                finally:
                    self.assertTrue(case.doCleanups(), 'nested fixture restoration failed')

    def test_judgment_and_risk_cannot_resolve_mechanical_ambiguity(self):
        from test_assurance_attested import MANUAL_REQ, AttestedCase
        item, _, _ = self.pair(0, 0, later='2026-10-28T01:00:00.100000Z')
        self.assertEqual(item['status'], 'UNVERIFIED')
        self.capability(SCOPED.replace('  - Scenario',
                        '  - Accept-risk: 2999-12-31 by human:test - disclosed gap\n  - Scenario') + MANUAL_REQ)
        AttestedCase.reviewed(self, cited='CALC-R1 and CALC-R2 reviewed.')
        data, code = self.report()
        items = {r['id']: r for r in data['requirements']}
        self.assertEqual(code, 1)
        self.assertEqual(items['CALC-R1']['status'], 'UNVERIFIED')
        self.assertEqual(items['CALC-R1']['risk_acceptance']['state'], 'active')
        self.assertNotIn('attested', items['CALC-R1'])
        self.assertEqual(items['CALC-R2']['status'], 'MANUAL')
        self.assertTrue(items['CALC-R2']['attested']['judgment'])
        self.assertEqual(data['schema_version'], 1)

    def test_framework_req_writer_and_general_reuse_do_not_create_knowledge(self):
        shutil.rmtree(self.root / 'knowledge')
        self.write('.agentic.json', '{"repository_kind":"framework"}\n')
        self.commit('framework fixture without requirements')
        self.start()
        self.lc('run', 'req:CALC-R1', '--inputs', 'check.py', 'src/**',
                '--', 'python3', 'check.py')
        first = self.state()['ledger'][-1]
        self.assertRegex(first['at'], r'\.\d{6}Z$')
        self.assertEqual(first['inputs'], ['check.py', 'src/**'])
        self.assertNotIn('runtime_sha256', first)
        self.assertIn('REUSE', self.lc('reuse', 'req:CALC-R1').stdout)
        report, code = self.report()
        self.assertEqual(code, 0)
        self.assertEqual(report['requirements'], [])
        self.assertFalse((self.root / 'knowledge').exists())

    def test_governance_and_status_shapes_are_preserved(self):
        obligation = assurance.parse('CALC-R1', CAP, SCOPED)
        obligation = dataclasses.replace(obligation, governed_by={'basis': 'declared'})
        entry = {'label': 'req:CALC-R1', 'argv': ['python3', 'check.py'],
                 'inputs': obligation.evidence_globs, 'at': 'bad', 'exit': 0}
        item = assurance.evaluate(self.root, obligation, [assurance.Evidence('bad.json', 0, entry)], 'tree')
        self.assertEqual(item['status'], 'UNVERIFIED')
        self.assertEqual(item['governed_by'], {'basis': 'declared'})
        self.assertEqual(set(item), {'id', 'capability', 'status', 'basis', 'evidence', 'reason', 'governed_by'})


class MechanicalOrderingControlsTests(unittest.TestCase):  # R7, seven variants / five mechanisms
    def test_guide_states_the_bounded_contract(self):
        guide = (SCRIPTS.parent / 'lifecycle.md').read_text()
        for term in ('completion precision', 'half-open', 'six fractional', 'all-PASS',
                     'metadata reconciliation', 'clock reversal', 'no historical migration'):
            self.assertTrue(term in guide, 'missing guide contract: ' + term)

    def test_seven_confirmed_variants_fail_their_intended_guards(self):
        ambiguous = ('        identities = ", ".join(sorted(f\'{item.record}#{item.index}\' for item in matching))\n'
                     '        return result(obligation, \'UNVERIFIED\', f\'mechanical evidence ordering is ambiguous: {identities}; \'\n'
                     '                      f\'{hint} after the overlapping completion intervals\')')
        # The production spelling uses single quotes; match exact bytes below.
        ambiguous = ambiguous.replace('\", \"', "', '")
        malformed = ("        return result(obligation, 'UNVERIFIED', 'reconcile mechanical evidence ordering metadata in '\n"
                     "                      + ', '.join(sorted(invalid)) + '; a rerun alone cannot order unknown completion time')")
        precision = 'datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")'
        variants = [
            ('filename', 'assurance.py', ambiguous,
             '        newest = max(matching, key=lambda item: item.record)', 1,
             'MechanicalOrderingLegacyTests.test_cross_record_overlap_has_no_filename_tiebreak', 'ordering uncertainty'),
            ('index', 'assurance.py', ambiguous,
             '        newest = max(matching, key=lambda item: item.index)', 1,
             'MechanicalOrderingLegacyTests.test_same_record_overlap_has_no_index_tiebreak', 'ordering uncertainty'),
            ('truncation', 'lifecycle.py', precision, 'now()', 2,
             'MechanicalOrderingProducerTests.test_requirement_completion_precision', "Regex didn't match"),
            ('publication', 'lifecycle.py', "                    additions.append(requirement_entries[entry['id']])",
             "                    requirement_entries[entry['id']]['at'] = " + precision + "\n"
             "                    additions.append(requirement_entries[entry['id']])", 1,
             'MechanicalOrderingProducerTests.test_converge_records_each_completion', 'AssertionError'),
            ('legacy-point', 'assurance.py', 'return lower, lower + 10 ** (6 - len(fraction))',
             'return lower, lower + (1 if not fraction else 10 ** (6 - len(fraction)))', 1,
             'MechanicalOrderingLegacyTests.test_legacy_fractional_overlap_is_unverified', 'ordering uncertainty'),
            ('overlap-pass', 'assurance.py', ambiguous,
             "        newest = next((item for item in matching if item.entry.get('exit') == 0), newest)", 1,
             'MechanicalOrderingLegacyTests.test_overlap_does_not_fall_back_to_a_pass', 'ordering uncertainty'),
            ('malformed-pass', 'assurance.py', malformed,
             "        return evaluate(root, obligation, [item for item in matching\n"
             "                         if f'{item.record}#{item.index}' not in invalid], tree)", 1,
             'MechanicalOrderingInvalidMetadataTests.test_bad_matching_time_cannot_restore_an_older_pass', 'ordering uncertainty'),
        ]
        self.assertEqual(len(variants), 7)
        for name, filename, old, new, count, selector, criterion in variants:
            with self.subTest(variant=name), tempfile.TemporaryDirectory() as directory:
                scripts = Path(directory) / '.ai/scripts'
                shutil.copytree(SCRIPTS, scripts, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                path = scripts / filename
                original = path.read_bytes()
                source = original.decode()
                self.assertEqual(source.count(old), count, 'mutation anchor: ' + name)
                argv = [sys.executable, str(scripts / 'tests/test_assurance_ordering.py'), selector]
                def guard():
                    result = subprocess.run(argv, cwd=directory, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                                            capture_output=True, text=True, timeout=120)
                    output = result.stdout + result.stderr
                    self.assertEqual(re.findall(r'Ran (\d+) tests? in ', output), ['1'], output)
                    return result.returncode, output
                code, output = guard()
                self.assertEqual(code, 0, output)
                changed = source.replace(old, new).encode()
                self.assertNotEqual(changed, original)
                path.write_bytes(changed)
                self.assertEqual(path.read_bytes(), changed)
                try:
                    code, output = guard()
                    self.assertEqual(code, 1, output)
                    self.assertIn('FAILED (failures=', output, output)
                    self.assertNotIn('ERROR:', output, output)
                    self.assertIn(criterion, output, output)
                finally:
                    path.write_bytes(original)
                    self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
