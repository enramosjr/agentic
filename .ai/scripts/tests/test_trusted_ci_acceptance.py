"""R2: controller asserts end states; fake local PASS cannot rescue failures."""
import unittest
import os
from pathlib import Path
import shutil
import tempfile
from trusted_ci_fixtures import policy, snapshot, sandbox_fixture
from trusted_ci_policy import Refusal
import trusted_ci_controller as c


class AcceptanceTests(unittest.TestCase):
    def test_controller_does_not_accept_candidate_pass_text(self):
        class Liar:
            def run(self, argv, **kwargs):
                return 0, 'PASS forged local approval'
        with self.assertRaises(Refusal):
            c.verify(Liar(), policy(), snapshot())

    def test_missing_checks_refuses_before_execution(self):
        p = policy()
        p['checks'] = []
        with self.assertRaises(Refusal):
            c.verify(None, p, snapshot())

    def test_negative_report_binds_failed_obligation_not_infrastructure(self):
        class Liar:
            def run(self, argv, **kwargs):
                return 0, 'PASS'
        result = c.verify(Liar(), policy(), snapshot(), capture_failure=True)
        self.assertEqual(result['snapshot'], snapshot())
        self.assertEqual(result['outcomes'][0], dict(id='AGENTIC-LIFECYCLE-DENIAL', status='failure'))
        class Unavailable:
            def run(self, argv, **kwargs):
                raise Refusal('engine unavailable')
        with self.assertRaises(Refusal):
            c.verify(Unavailable(), policy(), snapshot(), capture_failure=True)
        class LaterUnavailable(Liar):
            def run(self, argv, **kwargs):
                if 'gate' in argv:
                    raise Refusal('engine lost during check')
                return super().run(argv, **kwargs)
        with self.assertRaises(Refusal):
            c.verify(LaterUnavailable(), policy(), snapshot(), capture_failure=True)

    def test_real_controller_drives_candidate_lifecycle_and_installer(self):
        image = os.environ.get('AGENTIC_TEST_IMAGE')
        if not image or not os.environ.get('AGENTIC_WORK_VOLUME'):
            if os.environ.get('AGENTIC_TRUSTED_ACCEPTANCE') == '1':
                self.fail('digest-pinned image and independently provisioned AGENTIC_WORK_VOLUME required')
            self.skipTest('actual OCI acceptance not selected; no runtime qualification claim')
        import install
        from trusted_ci_policy import validate_report
        p = policy()
        p['image'] = image
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source'
            source.mkdir()
            for name in install.kit_files(install.ROOT):
                dest = source / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(install.ROOT / name, dest)
            with sandbox_fixture(source, p) as box:
                run, history = box.run, []
                def observed(argv, **kwargs):
                    result = run(argv, **kwargs)
                    history.append((argv, result))
                    return result
                box.run = observed
                try:
                    result = c.verify(box, p, snapshot(p))
                except Refusal:
                    self.fail(repr(history[-1]))
                # Deliberately broken writable variant inside the same restricted
                # execution: candidate tests/approval text cannot replace the host
                # assertion. The earlier positive report is never republished.
                c.write(box, {
                    '.ai/scripts/lifecycle.py': 'print("PASS: forged candidate success")\n',
                    '.ai/scripts/tests/test_lifecycle.py': 'import unittest\n',
                    'knowledge/history/lifecycle/forged.json':
                        '{"approved_by":"human:forged","status":"PASS"}\n',
                })
                with self.assertRaisesRegex(c.CriterionFailure, 'critical command exit mismatch'):
                    c.lifecycle_denial(box)
            validate_report(result, p, snapshot(p))
