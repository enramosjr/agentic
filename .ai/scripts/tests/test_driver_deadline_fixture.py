"""Controls for observing the real CLI deadline without counting preflight."""
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

import disk_tmp
import driver_deadline_fixture


class DeadlineObserverTests(unittest.TestCase):
    def command(self, body): return [sys.executable, '-u', '-c', body]

    def test_startup_is_separate_but_activity_cannot_extend_run_bound(self):
        body = 'import time,sys; time.sleep(.3); print("driver: Disk-backed scratch: fixture", file=sys.stderr, flush=True)'
        started = time.monotonic()
        with driver_deadline_fixture.observe(self.command(body), dict(os.environ), 10, 1) as (result, elapsed):
            self.assertEqual(result.returncode, 0)
            self.assertLess(elapsed, 1)
        self.assertGreaterEqual(time.monotonic() - started, .3)
        busy = ('import time,sys; print("driver: Disk-backed scratch: fixture", file=sys.stderr, flush=True); '
                'exec("for i in range(20):\\n print(i, file=sys.stderr, flush=True); time.sleep(.1)")')
        with self.assertRaisesRegex(AssertionError, 'run deadline'):
            with driver_deadline_fixture.observe(self.command(busy), dict(os.environ), 10, .2): pass

    def test_missing_or_duplicate_marker_never_passes(self):
        for body in ['print("no marker")', 'import sys; print("driver: Disk-backed scratch: one\\ndriver: Disk-backed scratch: two", file=sys.stderr)']:
            with self.subTest(body=body), self.assertRaises(AssertionError):
                with driver_deadline_fixture.observe(self.command(body), dict(os.environ), 10, 1): pass

    def test_late_start_followed_by_immediate_exit_still_fails_startup_watchdog(self):
        original = driver_deadline_fixture.process_runtime.ProcessTree.start
        def delayed_return(tree, *args, **kwargs):
            child = original(tree, *args, **kwargs)
            child.wait(timeout=10)
            time.sleep(.2)
            return child
        body = 'import sys; print("driver: Disk-backed scratch: late", file=sys.stderr, flush=True)'
        with patch.object(driver_deadline_fixture.process_runtime.ProcessTree, 'start', delayed_return), \
             self.assertRaisesRegex(AssertionError, 'startup watchdog'):
            with driver_deadline_fixture.observe(self.command(body), dict(os.environ), .1, 1): pass


if __name__ == '__main__': unittest.main()
