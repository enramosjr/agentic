"""Trusted host provisioning is separate from the candidate executor."""
import backend_test_support  # Establish the explicit source-only test paths.
from pathlib import Path
import sys
import unittest

import trusted_ci_fixtures
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deploy' / 'authority'))
import disk
from trusted_ci_policy import Refusal


class Disk(unittest.TestCase):
    def test_formatter_fallback_must_be_digest_pinned(self):
        with self.assertRaises(Refusal):
            disk.WorkDisk('agentic-test', 256, formatter_image='python:latest')

    def test_requires_linux_root_and_bounded_capacity(self):
        for amount in (True, 0, -1, 2048, '256'):
            with self.assertRaises(Refusal):
                disk.WorkDisk('agentic-test', amount)
        for name in ('/dev/sda', '../other', 'shared', 'agentic-;bad'):
            with self.assertRaises(Refusal):
                disk.WorkDisk(name, 256)

    def test_cleanup_never_detaches_unowned_loop_or_volume(self):
        calls = []
        def command(argv, **kwargs):
            calls.append(argv)
            return ''
        volume = disk.WorkDisk('agentic-test', 256, runner=command)
        volume.close()
        self.assertEqual(calls, [])

    def test_failed_volume_removal_preserves_backing_for_inspection(self):
        calls = []
        def command(argv, **kwargs):
            calls.append(argv)
            if argv[:3] == ['docker', 'volume', 'rm']:
                raise Refusal('in use')
            return ''
        volume = disk.WorkDisk('agentic-test', 256, runner=command)
        volume.owned_volume = True
        volume.loop = '/dev/loop7'
        with self.assertRaises(Refusal):
            volume.close()
        self.assertEqual(calls, [['docker', 'volume', 'rm', 'agentic-test']])
        self.assertEqual(volume.loop, '/dev/loop7')


if __name__ == '__main__':
    unittest.main()
