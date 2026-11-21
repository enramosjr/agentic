"""Real local pipe supervision, without an OCI or model-qualification claim."""
import backend_test_support
import io
import subprocess
import sys
import tarfile
import threading
import time
import unittest

from test_authority_codex_harness import configured
from trusted_ci_policy import Refusal


WORKER = '''import hashlib,json,sys,time
header=json.loads(sys.stdin.buffer.readline())
source=sys.stdin.buffer.read(header['source_bytes'])
assert hashlib.sha256(source).hexdigest()==header['source_sha256']
print(json.dumps(dict(kind='worker-ready',source_sha256=header['source_sha256'])),flush=True)
for expected in ['initialize','initialized','thread/start','turn/start']:
 value=json.loads(sys.stdin.buffer.readline())
 assert value['method']==expected
 if expected=='initialize': result={}
 elif expected=='thread/start': result={'thread':{'id':'thread-fixture'}}
 elif expected=='turn/start': result={'turn':{'id':'turn-fixture'}}
 else: continue
 print(json.dumps(dict(id=value['id'],result=result)),flush=True)
print(json.dumps(dict(method='turn/completed',params=dict(threadId='thread-fixture',turn=dict(id='turn-fixture',status='completed',error=None)))),flush=True)
assert sys.stdin.buffer.read()==b''
'''


class CodingTransportContracts(unittest.TestCase):
    def test_binary_export_capture_is_exact_and_deadline_outlives_blocked_guard(self):
        import coding_transport
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode='w') as archive:
            item = tarfile.TarInfo('exact.bin')
            item.size = 3
            archive.addfile(item, io.BytesIO(b'\x00\xff\x01'))
        expected = raw.getvalue()
        stopped = threading.Event()
        argv = [sys.executable, '-I', '-c', 'import sys;sys.stdout.buffer.write(bytes.fromhex(' + repr(expected.hex()) + '))']
        actual = coding_transport.capture_export(argv, lambda: None, stopped.set)
        self.assertEqual(actual, expected)
        self.assertTrue(stopped.is_set())
        stopped.clear()
        calls = [0]
        def guard():
            calls[0] += 1
            if calls[0] > 1: self.assertTrue(stopped.wait(2), 'export deadline hidden by guard')
        with self.assertRaises(Refusal):
            coding_transport.capture_export([sys.executable, '-I', '-c', 'import time;time.sleep(60)'],
                guard, stopped.set, seconds=.3)
        self.assertTrue(stopped.is_set())

    def test_real_protocol_and_silent_transport_both_stop_the_owned_container(self):
        import coding_transport
        source = io.BytesIO()
        with tarfile.open(fileobj=source, mode='w'): pass
        outer = self
        class Box:
            process = None
            stops = 0
            def __init__(self): self.stopped = threading.Event()
            def _attach(self):
                self.process = subprocess.Popen([sys.executable, '-I', '-c', self.script],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
                return self.process
            def stop(self):
                self.stops += 1
                if self.process.poll() is None: self.process.kill()
                self.stopped.set()
        box = Box()
        box.script = WORKER
        result = coding_transport._conversation(box, configured(), source.getvalue(), 'agentic-task.' + 'c' * 64,
            'Approved fixture task', int(time.time()) + 30, guard=lambda: None)
        self.assertEqual(result['turn_id'], 'turn-fixture')
        self.assertFalse(result['model_execution_qualified'])
        self.assertEqual(box.stops, 1)
        self.assertIsNotNone(box.process.poll())
        for failure in ('silent', 'cancelled', 'guard-blocked'):
            box = Box()
            box.script = 'import time; time.sleep(60)'
            started = time.monotonic()
            def guard():
                if failure == 'guard-blocked' and box.process is not None:
                    self.assertTrue(box.stopped.wait(2), 'blocked authorization hid the task deadline')
            with self.subTest(failure=failure), self.assertRaises(Refusal):
                coding_transport._conversation(box, configured(), source.getvalue(), 'agentic-task.' + 'c' * 64,
                    'Approved fixture task', int(time.time()) + 30, guard=guard,
                    cancelled=lambda: failure == 'cancelled', budget=.3)
            self.assertEqual(box.stops, 1)
            self.assertIsNotNone(box.process.poll())
            self.assertLess(time.monotonic() - started, 5)


if __name__ == '__main__': unittest.main()
