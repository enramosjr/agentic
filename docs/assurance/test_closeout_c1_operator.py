"""Synthetic operator checks only; never launches assurance classes. R1-R6."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location('c1_operator', Path(__file__).with_name('validate-closeout-c1.py'))
op = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(op)


class ProofTests(unittest.TestCase):
    def test_four_invalid_proofs_are_rejected(self):  # R3 R4 R5
        self.assertEqual(op.operator_controls(), ['empty-suite', 'unapplied-mutation',
                                                 'unrelated-error', 'restoration-failure'])

    def test_exact_execution_and_assertion_required(self):  # R2 R3
        row = op.ROWS[0]
        target = op.selector(row, True)
        failure = {'id': target, 'type': 'AssertionError', 'message': "'UNVERIFIED' != 'INVALID' : CALC-R3",
                   'frames': [{'file': 'test_assurance.py', 'function': row['method'], 'line': row['line'],
                               'locals': {'rid': 'CALC-R3'}}]}
        data = {'loaded': [target], 'started': [target], 'finished': [target], 'run': 1,
                'failures': [failure], 'errors': [], 'skips': [], 'unexpected': [], 'expected_failures': []}
        op.judge(data, [target], row)
        for change in ('wrong-line', 'wrong-method', 'wrong-meaning', 'skip', 'missing-finish', 'extra-test'):
            bad = copy.deepcopy(data)
            if change == 'wrong-line':
                bad['failures'][0]['frames'][0]['line'] += 1
            elif change == 'wrong-method':
                bad['failures'][0]['id'] = 'other'
            elif change == 'wrong-meaning':
                bad['failures'][0]['frames'][0]['locals']['rid'] = 'CALC-R4'
            elif change == 'skip':
                bad['skips'] = ['skip']
            elif change == 'missing-finish':
                bad['finished'] = []
            else:
                bad['loaded'].append('extra')
            with self.subTest(change=change), self.assertRaises(op.ProofError):
                op.judge(bad, [target], row)

    def test_baseline_requires_all_successful_methods(self):  # R2
        data = {'loaded': ['m'], 'started': ['m'], 'finished': ['m'], 'run': 1,
                'failures': [], 'errors': [], 'skips': [], 'unexpected': [], 'expected_failures': []}
        op.judge(data, ['m'])
        for field in ('errors', 'skips', 'unexpected', 'expected_failures'):
            bad = copy.deepcopy(data)
            bad[field] = ['bad']
            with self.subTest(field=field), self.assertRaises(op.ProofError):
                op.judge(bad, ['m'])

    def test_manifest_and_map_fail_closed(self):  # R1 R4
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'x').write_bytes(b'x')
            pins = op.parse_pins(op.digest(b'x') + '  x\n')
            op.check_files(root, pins)
            (root / 'x').write_bytes(b'changed')
            with self.assertRaises(op.ProofError):
                op.check_files(root, pins)
            for text in ('bad', op.digest(b'x') + '  ../x',
                         (op.digest(b'x') + '  x\n') * 2):
                with self.subTest(text=text), self.assertRaises(op.ProofError):
                    op.parse_pins(text)
        for rows in (op.ROWS[:-1], op.ROWS + [op.ROWS[0]]):
            with self.assertRaises(op.ProofError):
                op.check_rows(rows)

    def test_scoped_edit_preserves_other_functions(self):  # R3
        source = b'def a():\n    return 1\n\ndef b():\n    return 1\n'
        row = {'scope': 'a', 'old': 'return 1', 'new': 'return 2', 'path': 'x.py'}
        self.assertEqual(op.mutate(source, row), b'def a():\n    return 2\n\ndef b():\n    return 1\n')
        with self.assertRaises(op.ProofError):
            op.mutate(source, {**row, 'old': 'absent'})

    def test_static_roster_rejects_missing_and_extra_method(self):  # R1 R2
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / '.ai/scripts/tests'
            folder.mkdir(parents=True)
            for module in ('test_assurance', 'test_lifecycle_conformance'):
                text = ''
                for row in op.ROWS:
                    if row['module'] == module:
                        methods = [row['method']] + ['test_extra_' + str(i) for i in range(row['count'] - 1)]
                        text += 'class ' + row['class'] + ':\n'
                        text += ''.join('    def ' + name + '(self): return None\n' for name in methods)
                (folder / (module + '.py')).write_text(text)
            self.assertEqual(sum(map(len, op.roster(root).values())), 30)
            target = folder / 'test_lifecycle_conformance.py'
            target.write_text('class Assurance:\n    def test_other(self): return None\n')
            with self.assertRaises(op.ProofError):
                op.roster(root)

    def test_timeout_kills_owned_process(self):  # R5
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = op.run_process([sys.executable, '-c', 'import time; time.sleep(30)'],
                                    root, dict(), 0.1)
            self.assertTrue(result['timeout'])
            self.assertNotEqual(result['exit'], 0)

    def test_partial_failed_or_tampered_report_never_reused(self):  # R4 R6
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for payload in ({}, {'outcome': 'FAILED'}, {'outcome': 'MECHANICAL_PASS', 'identity': {}}):
                (root / 'report.json').write_text(json.dumps(payload))
                with self.assertRaises(op.ProofError):
                    op.reuse(root, {'candidate': 'expected'})

    def test_artifact_digest_is_checked(self):  # R6
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            op.write_new(root / 'raw.json', {'ok': True})
            pins = op.artifact_pins(root)
            op.check_files(root, pins)
            (root / 'raw.json').write_text('tampered')
            with self.assertRaises(op.ProofError):
                op.check_files(root, pins)

    def test_complete_evidence_reuse_and_drift_rejection(self):  # R1 R2 R3 R4 R6
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'candidate'
            source.mkdir()
            current = {'candidate': {'roster': {}}, 'runtime': {'synthetic': True}}
            report = dict(outcome='MECHANICAL_PASS', identity=current, rows=[], product_invocations=22,
                          duration=1, controls=['empty-suite', 'unapplied-mutation', 'unrelated-error', 'restoration-failure'])
            for row in op.ROWS:
                ids = [op.selector(row, True)] + [op.selector(row) + '.test_extra_' + str(i)
                                                for i in range(row['count'] - 1)]
                current['candidate']['roster'][row['id']] = ids
                target = source / row['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'original')
                record = dict(id=row['id'], restored=True, candidate_after=current['candidate'], path=row['path'],
                              before=op.digest(b'original'), after=op.digest(b'mutated'))
                report['rows'].append(record)
                for phase in ('baseline', 'mutant'):
                    selected = ids if phase == 'baseline' else [op.selector(row, True)]
                    data = dict(loaded=selected, started=selected, finished=selected, run=len(selected),
                                failures=[], errors=[], skips=[], unexpected=[], expected_failures=[])
                    if phase == 'mutant':
                        data['failures'] = [dict(id=selected[0], type='AssertionError', message=' '.join(row['terms']),
                                                frames=[dict(file=row['module'] + '.py', function=row['method'],
                                                             line=row['line'], locals={'rid': 'CALC-R3',
                                                                                      'listed_ids': ['CALC-R1', 'CALC-R3', 'CALC-R4', 'CALC-R5']})])]
                    prefix = row['id'] + '-' + phase
                    op.write_new(root / (prefix + '-tests.json'), data)
                    op.write_new(root / (prefix + '-process.json'), {'exit': int(phase == 'mutant'), 'timeout': False})
            report['artifacts'] = op.artifact_pins(root)
            op.write_new(root / 'report.json', report)
            (root / 'report.sha256').write_text(op.file_hash(root / 'report.json'))
            with patch.object(op, 'ROOT', source), patch.object(op, 'mutate', return_value=b'mutated'), \
                 patch.object(op, 'run_process', side_effect=AssertionError('reuse must not execute')):
                self.assertEqual(op.reuse(root, current)['outcome'], 'MECHANICAL_PASS')
                with self.assertRaises(op.ProofError):
                    op.reuse(root, {**current, 'runtime': {'changed': True}})
                (root / 'N01-baseline-tests.json').write_text('{}')
                with self.assertRaises(op.ProofError):
                    op.reuse(root, current)

    def test_campaign_propagates_restoration_failure(self):  # R4 R5
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'candidate'
            source.mkdir()
            (source / '.ai/scripts').mkdir(parents=True)
            (source / '.ai/scripts/tiny.py').write_bytes(b'x = 1\n')
            row = dict(op.ROWS[0], path='tiny.py', scope='', old='1', new='2')
            ids = ['synthetic.test']
            candidate = {'pins': {'.ai/scripts/tiny.py': op.digest(b'x = 1\n')}, 'roster': {'N01': ids}}
            def fake_worker(argv, cwd, env, timeout):
                op.write_new(Path(argv[-1]), dict(loaded=ids, started=ids, finished=ids, run=1,
                                                 failures=[], errors=[], skips=[], unexpected=[], expected_failures=[]))
                return dict(exit=0, timeout=False)
            with patch.object(op, 'ROOT', source), patch.object(op, 'RESULTS', root / 'results'), \
                 patch.object(op, 'ROWS', [row]), patch.object(op, 'candidate', return_value=candidate), \
                 patch.object(op, 'run_process', side_effect=fake_worker), \
                 patch.object(op, 'restored', side_effect=op.ProofError('injected restore failure')):
                with self.assertRaises(op.ProofError):
                    op.campaign({'candidate': candidate})
            failed = json.loads((root / 'results/report.json').read_text())
            self.assertEqual(failed['outcome'], 'FAILED')
            self.assertIn('injected restore failure', failed['error'])
            self.assertFalse((root / 'results/.work').exists())

    def test_final_verification_cannot_cross_overall_deadline(self):  # R5
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'candidate'
            (source / '.ai/scripts').mkdir(parents=True)
            (source / '.ai/scripts/tiny.py').write_bytes(b'x = 1\n')
            row = dict(op.ROWS[0], path='tiny.py', scope='', old='1', new='2')
            name = op.selector(row, True)
            candidate = {'pins': {'.ai/scripts/tiny.py': op.digest(b'x = 1\n')}, 'roster': {'N01': [name]}}
            clock = [0.0]
            def fake_worker(argv, cwd, env, timeout):
                mutant = '-mutant-' in argv[-1]
                failure = dict(id=name, type='AssertionError', message="'UNVERIFIED' != 'INVALID' : CALC-R3",
                               frames=[dict(file='test_assurance.py', function=row['method'], line=row['line'],
                                            locals={'rid': 'CALC-R3'})])
                op.write_new(Path(argv[-1]), dict(loaded=[name], started=[name], finished=[name], run=1,
                                                 failures=[failure] if mutant else [], errors=[], skips=[],
                                                 unexpected=[], expected_failures=[]))
                return dict(exit=int(mutant), timeout=False)
            def slow_verification(*args):
                clock[0] = 1201.0
            with patch.object(op, 'ROOT', source), patch.object(op, 'RESULTS', root / 'results'), \
                 patch.object(op, 'ROWS', [row]), patch.object(op, 'candidate', return_value=candidate), \
                 patch.object(op, 'run_process', side_effect=fake_worker), \
                 patch.object(op.time, 'monotonic', side_effect=lambda: clock[0]), \
                 patch.object(op, 'validate_report', side_effect=slow_verification):
                with self.assertRaises(op.ProofError):
                    op.campaign({'candidate': candidate})
            report = json.loads((root / 'results/report.json').read_text())
            self.assertEqual(report['outcome'], 'FAILED')
            self.assertGreaterEqual(report['duration'], 1201)


if __name__ == '__main__':
    unittest.main()
