"""Pure orchestration trust-policy controls; never starts a CLI or model."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import shutil
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parents[1] / '.ai/scripts'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher = load('native_proposal', BASE / 'native-launch-2-review-enforcement.py')
runner = load('native_runner', BASE / 'run-native-2-review-enforcement.py')


class TrustPolicyTests(unittest.TestCase):
    def setUp(self):
        self.source = '/fixture/.codex/hooks.json'
        self.hook = {'sourcePath': self.source, 'eventName': 'sessionStart',
            'handlerType': 'command', 'command': 'python3 frozen.py', 'matcher': None,
            'async': False, 'timeoutSec': 10, 'statusMessage': None, 'additionalContextLimit': None,
            'enabled': True, 'key': 'fixture:session_start:0:0', 'currentHash': 'sha256:' + 'a' * 64,
            'trustStatus': 'untrusted'}
        self.expected = {self.source: {('sessionStart', 'command', 'python3 frozen.py',
            None, False, 10, None, None)}}
        self.preflight = {'_hooks': {'data': [{'errors': [], 'hooks': [self.hook]}]},
                         '_configuration': {'hooks': {'state': {}}}}

    def test_trust_requires_exact_native_definitions_and_actual_trusted_reply(self):
        selected = launcher.selected_handlers(self.preflight, self.expected)
        self.assertEqual(selected, [(self.hook['key'], self.hook['currentHash'])])
        with self.assertRaisesRegex(ValueError, 'trust unavailable'):
            launcher.selected_handlers(self.preflight, self.expected, trusted=True)
        self.hook['trustStatus'] = 'trusted'
        self.assertEqual(launcher.selected_handlers(self.preflight, self.expected, trusted=True), selected)

    def test_unknown_changed_disabled_and_malformed_handlers_refuse(self):
        for key, value in [('command', 'python3 different.py'), ('sourcePath', '/other/config'),
                           ('enabled', False), ('currentHash', 'invented'), ('key', None)]:
            changed = copy.deepcopy(self.preflight)
            changed['_hooks']['data'][0]['hooks'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                launcher.selected_handlers(changed, self.expected)

    def test_overlay_preserves_existing_state_without_editing_discovery(self):
        observer = mock.Mock()
        observer.toml.side_effect = repr
        self.preflight['_configuration']['hooks']['state']['old'] = {'trusted_hash': 'old'}
        original = copy.deepcopy(self.preflight)
        flags, selected = launcher.trust_overlay(observer, self.preflight, self.expected)
        self.assertEqual(flags[0], '-c')
        self.assertTrue(flags[1].startswith('hooks.state='))
        state = observer.toml.call_args.args[0]
        self.assertEqual(state['old'], {'trusted_hash': 'old'})
        self.assertEqual(state[selected[0][0]]['trusted_hash'], selected[0][1])
        self.assertEqual(self.preflight, original)

    def test_no_authorization_never_reads_manifest_or_starts_process(self):
        with mock.patch.dict(launcher.os.environ, {}, clear=True), mock.patch.object(
                launcher.subprocess, 'run', side_effect=AssertionError('native process launched')):
            with self.assertRaisesRegex(ValueError, 'fresh explicit allocation'):
                launcher.main()
        with mock.patch.object(sys, 'argv', ['proposal']), mock.patch.object(
                runner.subprocess, 'run', side_effect=AssertionError('native process launched')):
            with self.assertRaisesRegex(ValueError, 'fresh explicit two-attempt'):
                runner.main()

    def test_raw_capture_survives_evaluator_attempt_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / 'attempt/repo'
            root.mkdir(parents=True)
            journal = root / '.git/okf-scratch/review/identity'
            journal.mkdir(parents=True)
            (journal / 'journal.json').write_text('{"raw":"capture"}')
            live = root.parent / 'live-capture'
            live.mkdir()
            (live / 'events.jsonl').write_text('actual raw event\n')
            namespace = base / 'operator'
            namespace.mkdir()
            guard = mock.Mock()
            guard.directory.return_value = journal
            guard.read.return_value = {}
            lifecycle = mock.Mock()
            lifecycle.load.return_value = None
            with mock.patch.dict(sys.modules, {'review_guard': guard,
                    'lifecycle': lifecycle, 'review_native': mock.Mock()}), mock.patch.object(
                    launcher, '__file__', str(namespace / 'native-launch.py')):
                launcher.retain_mechanical(root, 'codex', require_success=False)
            shutil.rmtree(root.parent)
            retained = namespace / 'retained/codex'
            self.assertEqual((retained / 'mechanical-capture/journal/journal.json').read_text(),
                             '{"raw":"capture"}')
            self.assertEqual((retained / 'live-capture/events.jsonl').read_text(), 'actual raw event\n')
            self.assertFalse((retained / 'qualified-final-state.json').exists())
            root.mkdir(parents=True)
            journal.mkdir(parents=True)
            (journal / 'journal.json').write_text('malformed raw journal')
            lifecycle.load.side_effect = ValueError('bad lifecycle state')
            guard.read.side_effect = ValueError('bad mechanical journal')
            refused_namespace = base / 'refused-operator'
            refused_namespace.mkdir()
            with mock.patch.dict(sys.modules, {'review_guard': guard, 'lifecycle': lifecycle,
                    'review_native': mock.Mock()}), mock.patch.object(launcher, '__file__',
                    str(refused_namespace / 'native-launch.py')):
                with self.assertRaisesRegex(ValueError, 'raw capture retained'):
                    launcher.retain_mechanical(root, 'codex', require_success=True)
            shutil.rmtree(root.parent)
            refused = refused_namespace / 'retained/codex/mechanical-capture'
            self.assertEqual((refused / 'journal/journal.json').read_text(), 'malformed raw journal')
            self.assertIn('bad lifecycle state', (refused / 'capture-errors.json').read_text())

    def test_git_receipts_are_external_before_native_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / 'attempt/repo'
            root.mkdir(parents=True)
            def git(*args):
                return subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                    text=True, check=True).stdout.strip()
            git('init', '-q')
            (root / 'source.txt').write_text('fixture')
            git('add', '-A')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid', 'commit', '-qm', 'fixture')
            head = git('rev-parse', 'HEAD')
            namespace = base / 'operator'
            namespace.mkdir()
            guard = mock.Mock()
            guard.read.return_value = {'writers': {}, 'request': None, 'interval': None}
            old_temporary = root / '.git/okf-scratch'
            old_temporary.mkdir()
            stale = {name: str(old_temporary) for name in ('TMPDIR', 'TMP', 'TEMP')}
            with mock.patch.dict(sys.modules, {'review_guard': guard}), mock.patch.object(
                    launcher, '__file__', str(namespace / 'native-launch.py')), mock.patch.dict(os.environ, stale):
                retained = launcher.prepare_capture_storage(root, 'codex')
                expected = retained / 'git-metadata/okf-scratch'
                for name in stale:
                    self.assertEqual(Path(os.environ[name]), expected)
                    self.assertTrue(Path(os.environ[name]).is_dir())
                probe = subprocess.run([sys.executable, '-c',
                    'import os,tempfile;from pathlib import Path;'
                    'd=tempfile.TemporaryDirectory();'
                    'assert Path(d.name).parent==Path(os.environ["TMPDIR"]), "temporary fallback"'],
                    cwd=root, capture_output=True, text=True)
                self.assertEqual(probe.returncode, 0, probe.stdout + probe.stderr)
            self.assertEqual(git('rev-parse', 'HEAD'), head)
            metadata = Path(git('rev-parse', '--absolute-git-dir'))
            self.assertEqual(metadata, retained / 'git-metadata')
            receipt = metadata / 'okf-scratch/native-raw.json'
            receipt.parent.mkdir(exist_ok=True)
            receipt.write_text('actual durable raw receipt')
            shutil.rmtree(root.parent)
            self.assertEqual(receipt.read_text(), 'actual durable raw receipt')

    def test_stream_capture_survives_sigkill_and_attempt_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            attempt = base / 'attempt'
            attempt.mkdir()
            capture = base / 'external-capture'
            capture.mkdir()
            program = (
                "import importlib.util,sys;from pathlib import Path;from types import SimpleNamespace;"
                "s=importlib.util.spec_from_file_location('proposal',sys.argv[1]);"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                "m.stream_native(SimpleNamespace(LIMIT=1048576),[sys.executable,'-c',"
                "\"import time;print('raw-ready',flush=True);time.sleep(60)\"],Path.cwd(),Path(sys.argv[2]),'')")
            child = subprocess.Popen([sys.executable, '-c', program, str(BASE / 'native-launch-2-review-enforcement.py'),
                str(capture)], cwd=attempt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            try:
                raw = capture / 'native-stream.jsonl'
                deadline = time.monotonic() + 3
                while not raw.exists() or b'raw-ready' not in raw.read_bytes():
                    self.assertIsNone(child.poll())
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(.01)
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=3)
                shutil.rmtree(attempt)
                self.assertIn(b'raw-ready', raw.read_bytes())
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=3)
                child.stdout.close()
                child.stderr.close()

    def test_changed_pinned_command_bytes_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'planned-commands.json'
            path.write_text('{"attempts":2}')
            expected = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'mode': oct(path.stat().st_mode & 0o7777)}
            runner.check_pin(path, expected)
            path.write_text('{"attempts":20}')
            with self.assertRaisesRegex(ValueError, 'prepared bytes/mode changed'):
                runner.check_pin(path, expected)

    def test_aggregate_deadline_bounds_and_shrinks_both_attempts(self):
        with tempfile.TemporaryDirectory() as temporary:
            namespace = Path(temporary)
            report = {'files': {}, 'operator_inputs': {}, 'frozen_source': temporary,
                      'binaries': {agent: {'path': '/frozen/' + agent} for agent in ('claude', 'codex')}}
            (namespace / 'preparation.json').write_text(json.dumps(report))
            commands = {agent: ['python3', 'evaluator.py', '--agent-id', agent,
                '--max-wall-seconds', '330', '--timeout', '300', '--max-agent-seconds', '300']
                for agent in ('claude', 'codex')}
            (namespace / 'planned-commands.json').write_text(json.dumps(commands))
            auth = {'loggedIn': True, 'authMethod': 'claude.ai', 'apiProvider': 'firstParty', 'subscriptionType': 'pro'}
            with mock.patch.object(sys, 'argv', ['proposal', '--authorized-allocation-and-scoped-trust']), \
                    mock.patch.object(runner, 'NAMESPACE', namespace), mock.patch.object(runner, 'check_pin'), \
                    mock.patch.object(runner, 'check_selected_campaign'), \
                    mock.patch.object(runner.os, 'getpgrp', return_value=os.getpid()), \
                    mock.patch.object(runner.signal, 'signal'), mock.patch.object(runner.signal, 'setitimer') as timer, \
                    mock.patch.object(runner.time, 'monotonic', side_effect=[0, 5, 10, 11, 400, 410, 411, 650]), \
                    mock.patch.object(runner.subprocess, 'run', return_value=SimpleNamespace(
                        returncode=0, stdout=json.dumps(auth))) as execute:
                self.assertEqual(runner.main(), 0)
            timer.assert_called_once_with(signal.ITIMER_REAL, 660)
            calls = execute.call_args_list
            self.assertEqual(len(calls), 5)
            self.assertEqual(calls[0].kwargs['timeout'], 15)
            second = calls[3].args[0]
            self.assertEqual(second[second.index('--max-wall-seconds') + 1], '245')
            self.assertEqual(second[second.index('--timeout') + 1], '245')
            self.assertEqual(second[second.index('--max-agent-seconds') + 1], '245')
            self.assertEqual(calls[4].kwargs['timeout'], 10)
            self.assertNotIn('--campaign-complete', calls[4].args[0])
            self.assertEqual(commands['codex'][commands['codex'].index('--max-wall-seconds') + 1], '330')

    def test_selected_campaign_scope_is_settled_and_never_expands_to_baseline(self):
        valid = {'matrix': [{'scenario_id': 'control-delta', 'repeat_index': 1, 'outcome': 'completed'}],
            'attempts': [{'scenario_id': 'control-delta', 'repeat_index': 1, 'outcome': 'completed', 'status': 'PASS'}],
            'totals': {'complete': True}, 'budget': {'reserved_seconds': 0},
            'provenance': {'agent': {'id': 'claude'}}}
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'results.json'
            path.write_text(json.dumps(valid))
            runner.check_selected_campaign(path, 'claude')
            variants = []
            for field, key, value in [('matrix', 'scenario_id', 'feature-l2'), ('matrix', 'repeat_index', 2),
                                      ('attempts', 'outcome', 'running'), ('attempts', 'status', 'NOT_RUN')]:
                changed = copy.deepcopy(valid)
                changed[field][0][key] = value
                variants.append(changed)
            extra = copy.deepcopy(valid)
            extra['attempts'].append(copy.deepcopy(extra['attempts'][0]))
            variants.append(extra)
            reserved = copy.deepcopy(valid)
            reserved['budget']['reserved_seconds'] = 1
            variants.append(reserved)
            for changed in variants:
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, 'one-cell scope'):
                    runner.check_selected_campaign(path, 'claude')


if __name__ == '__main__':
    unittest.main()
