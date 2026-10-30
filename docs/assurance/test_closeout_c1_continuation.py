"""Synthetic continuation checks; no original assurance worker is launched. R1-R6."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('c1_continuation', Path(__file__).with_name('validate-closeout-c1-continuation.py'))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def proof(item, ids, mutant=False):
    failures = []
    if mutant:
        failures = [dict(id=ids[0], type='AssertionError', message=' '.join(item['terms']),
                         frames=[dict(file=item['module'] + '.py', function=item['method'], line=item['line'],
                                      locals={'listed_ids': ['CALC-R1', 'CALC-R2', 'CALC-R3', 'CALC-R4', 'CALC-R5']})])]
    return dict(loaded=ids, started=ids, finished=ids, run=len(ids), failures=failures,
                errors=[], skips=[], unexpected=[], expected_failures=[])


class ContinuationTests(unittest.TestCase):
    def test_n08_same_fault_oracle(self):  # R3 R4: written before correction
        item = c.old.ROWS[7]
        ids = [c.old.selector(item, True)]
        c.judge(proof(item, ids, True), ids, item)
        for kind in ('missing-r4', 'wrong-line', 'error', 'empty', 'old-four-id-assumption'):
            data = proof(item, ids, True)
            frame = data['failures'][0]['frames'][0]
            if kind == 'missing-r4':
                frame['locals']['listed_ids'].remove('CALC-R4')
            elif kind == 'wrong-line':
                frame['line'] += 1
            elif kind == 'error':
                data['errors'] = ['loader error']
            elif kind == 'empty':
                data['run'] = 0
                data['started'] = []
            else:
                frame['locals']['listed_ids'].remove('CALC-R2')
            with self.subTest(kind=kind), self.assertRaises(c.old.ProofError):
                c.judge(data, ids, item)

    def test_prior_drift_rejected_without_worker(self):  # R1
        with patch.object(c, 'PRIOR_REPORT_HASH', '0' * 64), \
             patch.object(c, 'launch', side_effect=AssertionError('must not execute')):
            with self.assertRaises(c.old.ProofError):
                c.prior_audit()

    def test_original_four_rejection_controls_remain(self):  # R4
        self.assertEqual(c.old.operator_controls(), c.CONTROLS)

    def fixture(self, root):
        source = root / 'candidate'
        scripts = source / '.ai/scripts'
        scripts.mkdir(parents=True)
        (scripts / 'assurance.py').write_text("SCHEMA_VERSION = 1\ndef exit_code():\n    failing = FAILING + (('UNDECLARED',) if strict else ())\n")
        (source / '.ai/lifecycle.md').write_text('| Assurance | example\n')
        pins = {str(p.relative_to(source)): c.old.file_hash(p) for p in source.rglob('*') if p.is_file()}
        roster = {}
        for item in c.NEW_ROWS:
            roster[item['id']] = [c.old.selector(item, True)] + [c.old.selector(item) + '.test_extra_' + str(i)
                                                              for i in range(item['count'] - 1)]
        current = {'original': {'candidate': {'pins': pins, 'roster': roster}}, 'synthetic': True}
        prior = {'outcome': 'FAILED', 'product_invocations': 16, 'duration': 19.68976359300723,
                 'rows': [{'id': f'N{i:02}', 'restoration': 'qualified-control-flow' if i == 8 else 'explicit'}
                          for i in range(1, 9)]}
        def fake_worker(argv, cwd, env, timeout):
            require_mutant = '-mutant-' in argv[-1]
            item = next(r for r in c.NEW_ROWS if r['id'] in Path(argv[-1]).name)
            ids = [c.old.selector(item, True)] if require_mutant else roster[item['id']]
            c.old.write_new(Path(argv[-1]), proof(item, ids, require_mutant))
            return dict(exit=int(require_mutant), timeout=False, duration=0.001, argv=argv)
        return source, current, prior, fake_worker

    def test_six_only_campaign_reuse_and_tamper_rejection(self):  # R1-R6
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, current, prior, runner = self.fixture(root)
            with patch.object(c, 'ROOT', source), patch.object(c, 'RESULTS', root / 'results'), \
                 patch.object(c, 'guard', return_value=None), patch.object(c, 'prior_audit', return_value=prior), \
                 patch.object(c, 'launch', side_effect=runner) as calls:
                c.campaign(current)
                self.assertEqual(calls.call_count, 6)
                result = c.reuse(current)
                self.assertEqual(result['aggregate_workers'], 22)
                self.assertEqual(result['aggregate_baselines'], 30)
                self.assertEqual(len(result['aggregate_rows']), 11)
                self.assertEqual(calls.call_count, 6)
                (root / 'results/N09-baseline-tests.json').write_text('{}')
                with self.assertRaises((c.old.ProofError, KeyError)):
                    c.reuse(current)

    def test_restoration_failure_is_terminal(self):  # R4 R5
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, current, prior, runner = self.fixture(root)
            with patch.object(c, 'ROOT', source), patch.object(c, 'RESULTS', root / 'results'), \
                 patch.object(c, 'guard', return_value=None), patch.object(c, 'prior_audit', return_value=prior), \
                 patch.object(c, 'launch', side_effect=runner) as calls, \
                 patch.object(c, 'restore_copy', side_effect=c.old.ProofError('injected restore failure')):
                with self.assertRaises(c.old.ProofError):
                    c.campaign(current)
                self.assertEqual(calls.call_count, 1)
            report = json.loads((root / 'results/report.json').read_text())
            self.assertEqual(report['outcome'], 'FAILED')
            self.assertIn('injected restore failure', report['error'])
            self.assertFalse((root / 'results/.work').exists())

    def test_final_verification_and_publication_deadlines(self):  # R5
        for phase in ('verify', 'publish'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source, current, prior, runner = self.fixture(root)
                clock = [0.0]
                original_validate, original_publish = c.validate_report, c.publish
                def slow_validate(*args):
                    original_validate(*args)
                    if phase == 'verify':
                        clock[0] = 301.0
                def slow_publish(*args):
                    original_publish(*args)
                    if phase == 'publish':
                        clock[0] = 301.0
                with patch.object(c, 'ROOT', source), patch.object(c, 'RESULTS', root / 'results'), \
                     patch.object(c, 'guard', return_value=None), patch.object(c, 'prior_audit', return_value=prior), \
                     patch.object(c, 'launch', side_effect=runner), \
                     patch.object(c.time, 'monotonic', side_effect=lambda: clock[0]), \
                     patch.object(c, 'validate_report', side_effect=slow_validate), \
                     patch.object(c, 'publish', side_effect=slow_publish):
                    with self.assertRaises(c.old.ProofError):
                        c.campaign(current)
                self.assertEqual(json.loads((root / 'results/report.json').read_text())['outcome'], 'FAILED')

    def test_partial_and_failed_evidence_never_auto_restarts(self):  # R4 R6
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(c, 'RESULTS', root), patch.object(c, 'launch', side_effect=AssertionError('no retry')):
                for payload in ({}, {'outcome': 'FAILED'}):
                    (root / 'report.json').write_text(json.dumps(payload))
                    (root / 'report.sha256').write_text(c.old.file_hash(root / 'report.json'))
                    with self.assertRaises((c.old.ProofError, KeyError)):
                        c.reuse({})


if __name__ == '__main__':
    unittest.main()
