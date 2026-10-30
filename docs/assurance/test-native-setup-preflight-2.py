"""Exercise exact operator check closure and real fixture setup; no agent launches."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('prepared_setup', ROOT / 'docs/assurance/prepare-native-2-review-enforcement.py')
preparer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparer)


class SetupPreflightTests(unittest.TestCase):
    def checks(self, destination, *, delta):
        destination.mkdir()
        source = ROOT / 'docs/assurance/operator-2-report-contract/.ai/evals/checks'
        for name in ('live_observer.py', 'behavior.py', 'live.json', *(['delta.json'] if delta else [])):
            shutil.copy2(source / name, destination / name)

    def test_missing_delta_refuses_before_setup_processes(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.checks(base / 'checks', delta=False)
            with self.assertRaisesRegex(Exception, "unknown operator check ID 'delta'") as failure:
                preparer.preflight_setup(ROOT / 'docs/assurance/operator-2-mechanical-native-v3/frozen-source',
                    base / 'checks', base / 'preflight')
            self.assertEqual(type(failure.exception).__name__, 'EvalError')
            self.assertEqual(type(failure.exception).__module__, 'frozen_setup_preflight')
            self.assertFalse((base / 'preflight/repo').exists())

    def test_complete_closure_reaches_real_clean_fixture_setup(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.checks(base / 'checks', delta=True)
            result = preparer.preflight_setup(ROOT / 'docs/assurance/operator-2-mechanical-native-v3/frozen-source',
                base / 'checks', base / 'preflight')
            self.assertEqual(result['checks'], ['delta'])
            self.assertEqual(result['adapter'], ['live'])
            self.assertEqual(result['setup'], 'PASS')
            self.assertEqual(result['agent_processes'], 0)
            self.assertEqual(result['model_calls'], 0)
            self.assertTrue(result['setup_processes'])
            self.assertTrue((Path(result['fixture']) / 'knowledge/index.md').is_file())


if __name__ == '__main__':
    unittest.main()
