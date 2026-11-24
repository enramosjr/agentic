"""Local process/stream tests, never an OCI or supported-model qualification."""
import backend_test_support
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from test_authority_codex_harness import configured
from trusted_ci_policy import Refusal
import coding_worker
import coding_stdio


def header(raw, deployment=None):
    return dict(schema_version=2, deployment=deployment or configured(),
                capability='agentic-task.' + 'c' * 64, expires=int(time.time()) + 20,
                source_bytes=len(raw), source_sha256=hashlib.sha256(raw).hexdigest())


class CodingStdioContracts(unittest.TestCase):
    def test_bootstrap_rejects_wrong_digest_expiry_and_unknown_fields_before_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source'
            source.mkdir()
            (source / 'input.txt').write_bytes(b'approved source')
            raw = coding_worker.export_tree(source)
            for field, value in [('source_sha256', 'f' * 64), ('expires', 1),
                                 ('source_bytes', len(raw) + 1), ('command', 'candidate-controlled')]:
                h = header(raw)
                h[field] = value
                with self.subTest(field=field), self.assertRaises(Refusal):
                    coding_stdio.bootstrap(io.BytesIO(json.dumps(h).encode() + b'\n' + raw))

    @unittest.skipUnless(os.name == 'posix', 'POSIX worker process and Unix relay')
    def test_actual_process_roundtrip_edits_export_and_uses_real_model_bridge(self):
        import model_relay
        from test_authority_model_relay import fixture, Transport
        b, task, lease = fixture()
        now = int(time.time())
        lease.update(issued=now - 1, expires=now + 600)
        b['deployment']['expires'] = now + 700
        from trusted_ci_policy import digest
        b['deployment_digest'] = digest(b['deployment'])
        lease['deployment_digest'] = b['deployment_digest']
        task['deadline'] = now + 600
        relay = model_relay.Relay(lease, b, task, 'agentic-task.' + 'c' * 64, transport=Transport())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            (source / 'input.txt').write_bytes(b'approved source')
            raw = coding_worker.export_tree(source)
            fake = root / 'codex'
            fake.write_text('#!' + sys.executable + '\n' + FAKE_CODEX)
            fake.chmod(0o700)
            d = configured()
            d['resources']['codex_sha'] = hashlib.sha256(fake.read_bytes()).hexdigest()
            h = header(raw, d)
            path = relay._start(root)
            home = root / 'home'
            home.mkdir()
            project = root / 'project'
            runner = ('import sys; sys.path[:0]=sys.argv[1:3]; import coding_stdio; '
                      'from pathlib import Path; coding_stdio._stdio(sys.stdin.buffer, sys.stdout.buffer, '
                      'workspace=Path(sys.argv[3]), executable=Path(sys.argv[4]), '
                      'socket_path=Path(sys.argv[5]), home=Path(sys.argv[6]))')
            child = subprocess.Popen([sys.executable, '-c', runner, str(Path(coding_stdio.__file__).parent),
                str(backend_test_support.ROOT / '.ai/scripts'), str(project), str(fake), str(path), str(home)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                child.stdin.write(json.dumps(h).encode() + b'\n' + raw)
                child.stdin.flush()
                ack = json.loads(child.stdout.readline())
                self.assertEqual(ack, {'kind': 'worker-ready', 'source_sha256': h['source_sha256']})
                import codex_harness
                result = codex_harness.conversation(child.stdout, child.stdin, d, 'edit the fixture')
                self.assertEqual(result['turn_id'], 'fixture-turn')
                child.stdin.close()
                self.assertEqual(child.wait(timeout=10), 0, child.stderr.read().decode())
                self.assertEqual(relay.result()['completed'], 1)
                exported = coding_worker.export_tree(project)
                import submission
                self.assertEqual(submission.read_export(exported)['result.bin']['content'], b'\x00\xffactual edit\n')
                self.assertNotIn('GITHUB_TOKEN', (project / 'env.txt').read_text())
                self.assertNotIn('SYNTHETIC-UPSTREAM', (project / 'env.txt').read_text())
            finally:
                if child.poll() is None: child.kill()
                child.wait(timeout=10)
                for stream in (child.stdin, child.stdout, child.stderr): stream.close()
                relay.close()


FAKE_CODEX = r'''
import http.client, json, os, pathlib, re, sys
if sys.argv[1:] == ['--version']:
    print('codex-cli 1.2.3'); raise SystemExit
base = next(a for a in sys.argv if a.startswith('model_providers.agentic_chatgpt_plan.base_url='))
port = int(re.search(r'127\.0\.0\.1:(\d+)', base).group(1))
def emit(value): print(json.dumps(value), flush=True)
for line in sys.stdin:
    v = json.loads(line)
    if v['method'] == 'initialize': emit(dict(id=1, result={}))
    elif v['method'] == 'thread/start': emit(dict(id=2, result=dict(thread=dict(id='fixture-thread'))))
    elif v['method'] == 'turn/start':
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        c.request('POST', '/v1/responses', json.dumps(dict(model='fixture-model', store=False, stream=True,
            input=[dict(role='user', content='edit fixture')])), {'Authorization': 'Bearer ' + os.environ['AGENTIC_MODEL_CAP'],
                                                               'Content-Type': 'application/json'})
        r = c.getresponse()
        assert r.status == 200 and b'response.completed' in r.read()
        c.close()
        pathlib.Path('result.bin').write_bytes(b'\x00\xffactual edit\n')
        pathlib.Path('env.txt').write_text('\n'.join(sorted(os.environ)))
        emit(dict(id=3, result=dict(turn=dict(id='fixture-turn'))))
        emit(dict(method='turn/completed', params=dict(threadId='fixture-thread', turn=dict(id='fixture-turn', status='completed', error=None))))
'''


if __name__ == '__main__': unittest.main()
