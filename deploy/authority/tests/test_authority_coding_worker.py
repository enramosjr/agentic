"""Managed worker command/protocol fixtures; never container qualification."""
import backend_test_support
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_authority_codex_harness import configured
from trusted_ci_policy import Refusal
import authority_release
import coding_worker


class CodingWorkerContracts(unittest.TestCase):
    def test_export_removes_stopped_candidate_and_reads_only_owned_readonly_volume(self):
        with tempfile.TemporaryDirectory() as temporary:
            box = coding_worker.CodingSandbox(configured(), 'agentic-fixture', Path(temporary))
            box.container_id, box.created_container = 'e' * 64, True
            calls = []
            exporter = 'f' * 64
            def command(argv, **kwargs):
                calls.append(argv)
                if argv[1] == 'create': return 0, exporter
                if argv[1] == 'inspect':
                    if argv[-1] == 'e' * 64:
                        return 0, json.dumps(dict(Id='e' * 64, State=dict(Running=False, Status='exited')))
                    return 0, json.dumps(dict(Id=exporter, Config=dict(User='65534:65534', Image=box.resources['coding_image']),
                        HostConfig=dict(ReadonlyRootfs=True, Privileged=False, NetworkMode='none'),
                        Mounts=[dict(Type='volume', Name=box.work, Destination='/work', RW=False)]))
                return 0, ''
            source = Path(temporary) / 'source'
            source.mkdir()
            (source / 'exact.bin').write_bytes(b'\x00\xffstopped export')
            archive = coding_worker.export_tree(source)
            capture_entered = []
            def guard():
                if any(c[1] == 'create' for c in calls):
                    self.assertTrue(capture_entered, 'export authorization ran before its cleanup timer')
            def capture(argv, observed_guard, remove):
                capture_entered.append(True)
                observed_guard()
                return archive
            with patch.object(coding_worker.sandbox, 'command', side_effect=command), \
                 patch.object(coding_worker, 'capture_export', side_effect=capture) as captured:
                self.assertEqual(box._export(guard), archive)
            self.assertFalse(box.created_container)
            create = next(c for c in calls if c[1] == 'create')
            self.assertIn('agentic-fixture:/work:nocopy,ro', create)
            self.assertNotIn(str(Path(temporary)), ' '.join(create))
            self.assertEqual(create[-4:], [box.resources['coding_image'], '-I', '/opt/agentic/deploy/authority/coding_stdio.py', '--export'])
            self.assertEqual(captured.call_args.args[0], ['docker', 'start', '--attach', exporter])
            self.assertEqual(calls[-1], ['docker', 'rm', '--force', exporter])

    def test_parent_attach_is_fixed_and_stop_confirms_immutable_container_is_not_running(self):
        with tempfile.TemporaryDirectory() as temporary:
            box = coding_worker.CodingSandbox(configured(), 'agentic-fixture', Path(temporary))
            box.container_id, box.created_container = 'e' * 64, True
            calls = []
            def command(argv, **kwargs):
                calls.append(argv)
                if argv[1] == 'inspect':
                    return 0, json.dumps(dict(Id='e' * 64, State=dict(Running=False, Status='exited')))
                return 0, ''
            with patch.object(box, 'inspect'), patch.object(coding_worker.subprocess, 'Popen') as launch:
                box._attach()
                argv = launch.call_args.args[0]
                self.assertEqual(argv[-4:], ['python3', '-I', '/opt/agentic/deploy/authority/coding_stdio.py', '--stdio'])
                self.assertIn('e' * 64, argv)
                self.assertNotIn('GITHUB_TOKEN', launch.call_args.kwargs['env'])
            with patch.object(coding_worker.sandbox, 'command', side_effect=command):
                box.stop()
                self.assertTrue(box.stopped)
                with self.assertRaises(Refusal): box.run(['true'])
            self.assertEqual(calls[0], ['docker', 'stop', '--time', '0', 'e' * 64])

    def test_export_refuses_scandir_errors_instead_of_partial_deletions(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(coding_worker.os, 'scandir', side_effect=PermissionError('synthetic unreadable subtree')):
                with self.assertRaises((OSError, Refusal)): coding_worker.export_tree(Path(temporary))

    def test_admitted_worker_exec_and_cleanup_use_captured_container_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            box = coding_worker.CodingSandbox(configured(), 'agentic-fixture', Path(temporary))
            box.container_id = 'e' * 64
            box.created_container = True
            calls = []
            def command(argv, **kwargs):
                calls.append(argv)
                return 0, ''
            with patch.object(coding_worker.sandbox, 'command', side_effect=command):
                box.run(['true'])
                box.close()
            self.assertIn('e' * 64, calls[0])
            self.assertEqual(calls[1], ['docker', 'rm', '--force', 'e' * 64])

    def test_worker_container_has_only_owned_work_and_relay_mounts(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for runtime in ('docker', 'podman'):
                box = coding_worker.CodingSandbox(configured(), 'agentic-fixture', directory, runtime)
                args = box.create_arguments()
                with self.subTest(runtime=runtime):
                    self.assertEqual(args[:2], [runtime, 'create'])
                    for flag in ('--read-only', '--network=none', '--cap-drop=ALL',
                                 '--security-opt=no-new-privileges', '--user=65534:65534', '--log-driver=none'):
                        self.assertIn(flag, args)
                    self.assertIn('agentic-fixture:/work:nocopy', args)
                    self.assertIn('type=bind,src=' + str(directory.resolve()) + ',dst=/run/agentic-model,readonly', args)
                    self.assertTrue(any(a.startswith('--tmpfs=/home/agentic:') for a in args))
                    self.assertEqual(args[-4], configured()['resources']['coding_image'])
                    self.assertFalse(any('/source' in a or 'docker.sock' in a or '/authority' in a for a in args))

    def test_worker_public_execution_is_held_before_engine_or_disk(self):
        with tempfile.TemporaryDirectory() as temporary:
            box = coding_worker.CodingSandbox(configured(), 'agentic-fixture', Path(temporary), 'docker')
            with self.assertRaises(authority_release.Held): box.__enter__()

    def test_exporter_reads_exact_bytes_modes_and_rejects_links(self):
        import submission
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'project'
            root.mkdir()
            (root / 'result.bin').write_bytes(b'\x00\xffexact edited bytes\n')
            raw = coding_worker.export_tree(root)
            files = submission.read_export(raw)
            self.assertEqual(files['result.bin']['content'], b'\x00\xffexact edited bytes\n')
            try: (root / 'escape').symlink_to(Path(temporary))
            except OSError: return  # Actual link test is also required on POSIX.
            with self.assertRaises(Refusal): coding_worker.export_tree(root)

    def test_bootstrap_materializes_only_validated_source_under_fresh_workspace(self):
        import submission
        with tempfile.TemporaryDirectory() as temporary:
            source, destination = Path(temporary) / 'source', Path(temporary) / 'project'
            source.mkdir()
            (source / 'source.txt').write_bytes(b'approved initial snapshot')
            raw = coding_worker.export_tree(source)
            coding_worker.materialize(raw, destination)
            self.assertEqual((destination / 'source.txt').read_bytes(), b'approved initial snapshot')
            with self.assertRaises(Refusal): coding_worker.materialize(raw, destination)
            self.assertEqual(submission.read_export(coding_worker.export_tree(destination))['source.txt']['content'],
                             b'approved initial snapshot')


if __name__ == '__main__': unittest.main()
