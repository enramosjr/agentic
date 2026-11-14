"""R3: hostile archives, immutable execution configuration, real isolation."""
import io
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from trusted_ci_fixtures import policy, sandbox_fixture
import trusted_ci_sandbox as s
from trusted_ci_policy import Refusal


def archive(name, kind=tarfile.REGTYPE, link=''):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w') as tar:
        entry = tarfile.TarInfo(name)
        entry.type, entry.linkname = kind, link
        entry.size = 1 if kind == tarfile.REGTYPE else 0
        tar.addfile(entry, io.BytesIO(b'x') if entry.size else None)
    return raw.getvalue()


class IsolationTests(unittest.TestCase):
    def test_cleanup_reacquires_the_same_volume_reservation(self):
        calls = []
        class Box:
            runtime, name, work, created_container = 'podman', 'agentic-candidate-fixture-work', 'fixture-work', False
            def __init__(self, *args):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        def collision(argv, **kwargs):
            calls.append(argv)
            return 125, 'another owner holds the reservation'
        with patch.object(s, 'Sandbox', Box), patch.object(s, 'command', collision):
            with self.assertRaisesRegex(Refusal, 'test-owned work data cleanup failed'):
                with sandbox_fixture(Path('.'), policy()):
                    pass
        self.assertEqual(len(calls), 1)
        self.assertIn('--name', calls[0])
        self.assertEqual(calls[0][calls[0].index('--name') + 1], Box.name)

    def test_cleanup_never_erases_a_volume_that_failed_admission(self):
        class Box:
            created_container = False
            def __init__(self, *args):
                pass
            def __enter__(self):
                raise Refusal('preexisting volume was not empty')
            def __exit__(self, *args):
                pass
        with patch.object(s, 'Sandbox', Box), patch.object(s, 'command') as command:
            with self.assertRaisesRegex(Refusal, 'preexisting volume was not empty'):
                with sandbox_fixture(Path('.'), policy()):
                    pass
            command.assert_not_called()

    def test_docker_mounts_only_snapshot_without_copying_into_readonly_root(self):
        calls = []
        def runtime(argv, **kwargs):
            calls.append(argv)
            if argv[1] == 'cp':
                raise Refusal('Docker rejects copy into read-only rootfs')
            if argv[1] == 'info':
                return 0, 'linux'
            if 'stat' in argv:
                return 0, 'ext2/ext3'
            return 0, ''
        with tempfile.TemporaryDirectory() as directory, patch.object(s, 'command', runtime), \
                patch.object(s.shutil, 'which', return_value='/usr/bin/docker'):
            with s.Sandbox(Path(directory), policy(), runtime='docker', work_volume='fixture-work'):
                pass
        creation = next(c for c in calls if c[1] == 'create')
        self.assertIn('type=bind,src=' + str(Path(directory).resolve()) + ',dst=/source,readonly', creation)
        self.assertFalse(any(c[1] == 'cp' for c in calls))

    def test_archive_rejects_paths_links_and_special_files(self):
        with tempfile.TemporaryDirectory() as d:
            for data in [archive('../escape'), archive('/absolute'), archive('a\\escape'),
                         archive('repo/CON'), archive('repo/alias.'), archive('repo/line\ncommand'),
                         archive('a', tarfile.SYMTYPE, '/host'), archive('a', tarfile.LNKTYPE, 'b'),
                         archive('a', tarfile.FIFOTYPE)]:
                with self.subTest(data=data[:80]), self.assertRaises(Refusal):
                    s.extract(data, Path(d) / 'candidate', max_bytes=100)
            self.assertFalse((Path(d) / 'escape').exists())

    def test_safe_archive_extracts_bytes_under_its_new_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = s.extract(archive('repo/file.txt'), Path(directory) / 'candidate')
            self.assertEqual((root / 'file.txt').read_bytes(), b'x')

    def test_bounded_transport_does_not_print_workflow_commands(self):
        import sys
        with self.assertRaises(Refusal):
            s.command([sys.executable, '-c', 'print("x"*100000)'], limit=1000)
        code, out = s.command([sys.executable, '-c', 'print("::error::hostile")'])
        self.assertEqual(code, 0)
        self.assertIn('::error::', out)  # returned as data, never emitted to Actions

    def test_actual_container_cannot_write_controller_or_read_secret(self):
        image = os.environ.get('AGENTIC_TEST_IMAGE')
        if not image or not os.environ.get('AGENTIC_WORK_VOLUME') or not (shutil.which('docker') or shutil.which('podman')):
            if os.environ.get('AGENTIC_TRUSTED_ACCEPTANCE') == '1':
                self.fail('Linux/Docker and digest-pinned AGENTIC_TEST_IMAGE required')
            self.skipTest('actual Linux/Docker qualification unavailable; not acceptance evidence')
        p = policy()
        p['image'] = image
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'source'
            root.mkdir()
            (root / 'secret').write_text('source-data')
            with sandbox_fixture(root, p) as box:
                code, out = box.run(['python3', '-c',
                    'import os,pathlib; assert not os.environ.get("GITHUB_TOKEN"); '
                    'assert not pathlib.Path("/var/run/docker.sock").exists(); '
                    'assert not pathlib.Path("/authority").exists(); '
                    'assert os.getuid()!=0; '
                    'assert pathlib.Path("/sys/fs/cgroup/memory.max").read_text().strip()=="536870912"; '
                    'assert pathlib.Path("/sys/fs/cgroup/pids.max").read_text().strip()=="64"; '
                    'assert "eth0" not in pathlib.Path("/proc/net/dev").read_text(); '
                    'status=pathlib.Path("/proc/self/status").read_text(); '
                    'assert "NoNewPrivs:\\t1" in status; assert "Seccomp:\\t2" in status; '
                    'assert "CapEff:\\t0000000000000000" in status; '
                    'assert os.statvfs("/work").f_blocks*os.statvfs("/work").f_frsize<=256*1024*1024; '
                    'pathlib.Path("/work/ok").write_text("isolated")'], cwd='/work')
                self.assertEqual(code, 0, out)
                self.assertNotEqual(box.run(['touch', '/source/injected'], cwd='/work')[0], 0)
                self.assertEqual(box.run(['cat', '/work/ok'], cwd='/work'), (0, 'isolated'))
            self.assertFalse((root / 'injected').exists())
