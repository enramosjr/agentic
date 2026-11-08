"""Internal upload child isolation, without Actions credentials or a live call."""
import backend_test_support
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from trusted_ci_policy import Refusal
import artifact_uploader
import merge_receipts


class UploadChildContracts(unittest.TestCase):
    def environment(self):
        return dict(os.environ, ACTIONS_RUNTIME_TOKEN='SYNTHETIC-ARTIFACT-CAP',
            ACTIONS_RESULTS_URL='https://results-receiver.actions.githubusercontent.com',
            GITHUB_TOKEN='MUST-NOT-INHERIT', AGENTIC_MERGE_KEY='MUST-NOT-INHERIT',
            NODE_OPTIONS='--require attacker.js', HTTPS_PROXY='https://attacker.invalid')

    def test_child_has_only_artifact_capability_and_private_ack(self):
        observed = []
        def run(argv, **kwargs):
            observed.append((argv, kwargs))
            value = json.loads(kwargs['input'])
            Path(value['ack']).write_text('{"artifact_id":321}')
            return subprocess.CompletedProcess(argv, 0)
        uploader = artifact_uploader.NodeUploader(str(Path(sys.executable).resolve()), self.environment())
        with patch.object(artifact_uploader.subprocess, 'run', side_effect=run):
            self.assertEqual(uploader('agentic-merge-' + '1' * 32 + '-s1-a1-dispatch', b'{}'), 321)
        argv, options = observed[0]
        self.assertEqual(argv[-1], str(Path(artifact_uploader.__file__).parent / 'artifact_upload/cli.mjs'))
        self.assertEqual(options['timeout'], 30)
        self.assertEqual(options['stdout'], subprocess.DEVNULL)
        self.assertEqual(options['stderr'], subprocess.DEVNULL)
        self.assertEqual(options['env']['ACTIONS_RUNTIME_TOKEN'], 'SYNTHETIC-ARTIFACT-CAP')
        for key in ('GITHUB_TOKEN', 'AGENTIC_MERGE_KEY', 'NODE_OPTIONS', 'HTTPS_PROXY', 'HOME', 'USERPROFILE'):
            self.assertNotIn(key, options['env'])
        self.assertFalse(Path(json.loads(options['input'])['ack']).parent.exists())

    def test_missing_or_foreign_runtime_fails_before_child(self):
        for change in ({'ACTIONS_RUNTIME_TOKEN': ''}, {'ACTIONS_RESULTS_URL': 'https://attacker.invalid'},
                       {'ACTIONS_RESULTS_URL': 'http://results-receiver.actions.githubusercontent.com'}):
            with self.subTest(change=change), patch.object(artifact_uploader.subprocess, 'run') as child:
                with self.assertRaises(Refusal):
                    artifact_uploader.NodeUploader(str(Path(sys.executable).resolve()),
                                                    dict(self.environment(), **change))
                child.assert_not_called()

    def test_every_broker_receipt_kind_reaches_the_isolated_upload_child(self):
        observed = []
        def run(argv, **kwargs):
            value = json.loads(kwargs['input'])
            observed.append(value['name'])
            Path(value['ack']).write_text('{"artifact_id":321}')
            return subprocess.CompletedProcess(argv, 0)
        uploader = artifact_uploader.NodeUploader(str(Path(sys.executable).resolve()), self.environment())
        with patch.object(artifact_uploader.subprocess, 'run', side_effect=run):
            for kind in merge_receipts.KINDS:
                name = 'agentic-merge-' + '1' * 32 + '-s1-a1-' + kind
                with self.subTest(kind=kind): self.assertEqual(uploader(name, b'{}'), 321)
        self.assertEqual(len(observed), len(merge_receipts.KINDS))
        with patch.object(artifact_uploader.subprocess, 'run') as child:
            for suffix in ('not-submitted-extra', 'unknown', 'dispatch/../../secret'):
                with self.subTest(suffix=suffix), self.assertRaises(Refusal):
                    uploader('agentic-merge-' + '1' * 32 + '-s1-a1-' + suffix, b'{}')
            child.assert_not_called()

    def test_child_failure_timeout_and_missing_ack_are_not_retried(self):
        uploader = artifact_uploader.NodeUploader(str(Path(sys.executable).resolve()), self.environment())
        for result in (subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0),
                       subprocess.TimeoutExpired(['node'], 30)):
            with self.subTest(result=type(result).__name__):
                with patch.object(artifact_uploader.subprocess, 'run',
                    **({'side_effect': result} if isinstance(result, Exception) else {'return_value': result})) as child:
                    with self.assertRaises(Refusal):
                        uploader('agentic-merge-' + '1' * 32 + '-s1-a1-dispatch', b'{}')
                    self.assertEqual(child.call_count, 1)

    def test_closed_producer_documents_reach_only_the_artifact_child(self):
        names = ['evidence-7-1', 'controls-7-1', 'task-' + 'a' * 32 + '-1',
                 'task-ready-' + 'a' * 32 + '-1', 'task-controls-' + 'a' * 32 + '-1',
                 'model-lease-' + 'a' * 32 + '-1', 'qualification-1']
        names += [role + '-' + purpose + '-1' for role in ('proof', 'final-proof', 'credential-proof')
                  for purpose in ('admin', 'reader', 'issuer', 'coding', 'merge')]
        names += ['credential-proof-model_vault-1', 'credential-proof-model_delivery-1']
        observed = []
        def run(argv, **kwargs):
            value = json.loads(kwargs['input'])
            observed.append(value['name'])
            Path(value['ack']).write_text('{"artifact_id":321}')
            self.assertNotIn('AGENTIC_MERGE_KEY', kwargs['env'])
            self.assertNotIn('GITHUB_TOKEN', kwargs['env'])
            return subprocess.CompletedProcess(argv, 0)
        uploader = artifact_uploader.NodeUploader(str(Path(sys.executable).resolve()), self.environment())
        with patch.object(artifact_uploader.subprocess, 'run', side_effect=run):
            for name in names:
                with self.subTest(name=name): self.assertEqual(uploader(name, b'{}'), 321)
        self.assertEqual(observed, names)

    @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
    def test_real_cli_refuses_without_runtime_capability_without_sdk_network(self):
        cli = Path(__file__).resolve().parents[1] / 'artifact_upload/cli.mjs'
        result = subprocess.run(['node', str(cli)], input=b'{}', capture_output=True,
            env={k: v for k, v in os.environ.items() if k in ('PATH', 'SystemRoot', 'SYSTEMROOT')}, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout + result.stderr, b'')


if __name__ == '__main__':
    unittest.main()
