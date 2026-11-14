"""Local stream and HTTP fixtures; never a model/subscription qualification."""
import backend_test_support
import copy
import hashlib
import io
import json
import socket
import tempfile
import unittest
from unittest.mock import patch

from test_authority_codex_harness import configured
from trusted_ci_policy import Refusal, digest
import authority_release
import model_bridge
import model_relay

CAP = 'agentic-task.' + 'c' * 64


def fixture():
    d = configured()
    d.update(state='active', qualification='f' * 64)
    d['resources'].update(model_session='a' * 32, model_account='b' * 64, model_client='oaiapp_synthetic')
    b = dict(deployment=d, deployment_digest=digest(d), configuration_revision='b' * 40)
    task = dict(task_id='d' * 32, run_id=99, attempt=1, deadline=1800, purpose='task')
    lease = dict(schema_version=1, kind='model-access-lease', authority_repository_id=456,
        session_id='a' * 32, identity_digest='b' * 64, client_id='oaiapp_synthetic', auth_generation=1,
        configuration_revision=b['configuration_revision'], deployment_digest=b['deployment_digest'],
        repository_id=d['policy']['repository_id'], target=d['policy']['target'], **task,
        model_id=d['resources']['model_id'], issued=1400, expires=1800,
        access_token='SYNTHETIC-UPSTREAM-ACCESS', scopes=['chatgpt.tokens.use.direct', 'resource.invoke'])
    lease.pop('deadline')
    return b, task, lease


def request():
    return dict(model='fixture-model', store=False, stream=True, input=[{'role': 'user', 'content': 'fixture'}])


def event(kind, **kw):
    return ('event: ' + kind + '\ndata: ' + json.dumps(dict(type=kind, **kw)) + '\n\n').encode()


class Stream(io.BytesIO):
    status = 200
    def getheader(self, name): return 'text/event-stream'


class Transport:
    def __init__(self, raw=None):
        self.raw = raw if raw is not None else event('response.completed', response={'id': 'fixture', 'status': 'completed'})
        self.calls = []
    def open(self, body, token, timeout):
        self.calls.append((json.loads(body), token, timeout))
        return Stream(self.raw)


def relay(raw=None):
    b, task, lease = fixture()
    transport = Transport(raw)
    return model_relay.Relay(lease, b, task, CAP, transport=transport, clock=lambda: 1500), transport


class ModelRelayContracts(unittest.TestCase):
    def test_public_hold_precedes_listener_or_transport(self):
        r, transport = relay()
        with self.assertRaises(authority_release.Held): r.start('irrelevant')
        self.assertEqual(transport.calls, [])

    def test_capability_replaced_by_access_only_for_fixed_model_and_complete_stream(self):
        r, transport = relay()
        output = io.BytesIO()
        r.forward('Bearer ' + CAP, json.dumps(request()).encode(), output.write)
        self.assertEqual(transport.calls[0][1], 'SYNTHETIC-UPSTREAM-ACCESS')
        self.assertNotIn(CAP, json.dumps(transport.calls))
        self.assertNotIn(b'SYNTHETIC-UPSTREAM', output.getvalue())
        self.assertTrue(r.result()['completed_inference'])
        self.assertEqual(r.result()['completed'], 1)
        self.assertEqual(r.result()['response_digests'], [hashlib.sha256(transport.raw).hexdigest()])
        self.assertFalse(r.result()['model_execution_qualified'])
        r.close()
        with self.assertRaises(Refusal): r.forward('Bearer ' + CAP, json.dumps(request()).encode(), output.write)

    def test_wrong_capability_model_profile_and_expiry_never_reach_upstream(self):
        for defect in ('cap', 'model', 'store', 'stream', 'input', 'previous_response_id', 'metadata', 'tool', 'system', 'expired'):
            r, transport = relay()
            value, cap = request(), CAP
            if defect == 'cap': cap = 'agentic-task.' + 'e' * 64
            elif defect == 'expired': r.clock = lambda: 1800
            elif defect == 'model': value['model'] = 'foreign-model'
            elif defect in ('store', 'stream'): value[defect] = not value[defect]
            elif defect == 'input': value['input'] = 'not-an-array'
            elif defect == 'tool': value['tools'] = [{'type': 'tool_search'}]
            elif defect == 'system': value['input'] = [{'type': 'message', 'role': 'system', 'content': 'no'}]
            else: value[defect] = 'unsupported'
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                r.forward('Bearer ' + cap, json.dumps(value).encode(), lambda raw: None)
            self.assertEqual(transport.calls, [])

    def test_late_failure_missing_completion_and_fragmented_events_fail_closed(self):
        for raw in (event('response.output_text.delta', delta='partial'),
                    event('response.output_text.delta', delta='partial') + event('response.failed'),
                    event('response.completed', response={'id': 'fixture', 'status': 'incomplete'})):
            r, _ = relay(raw)
            with self.assertRaises(Refusal): r.forward('Bearer ' + CAP, json.dumps(request()).encode(), lambda raw: None)
            self.assertFalse(r.result()['completed_inference'])
        r, transport = relay()
        class Fragmented(Stream):
            def read1(self, size): return self.read(min(size, 3))
        transport.open = lambda *args: Fragmented(transport.raw.replace(b'\n', b'\r\n') + b'data: [DONE]\r\n\r\n')
        r.forward('Bearer ' + CAP, json.dumps(request()).encode(), lambda raw: None)
        self.assertTrue(r.result()['completed_inference'])

    def test_disconnect_and_request_budget_are_terminal(self):
        r, transport = relay()
        def disconnected(raw): raise BrokenPipeError()
        with self.assertRaises(Refusal): r.forward('Bearer ' + CAP, json.dumps(request()).encode(), disconnected)
        self.assertFalse(r.result()['completed_inference'])
        with self.assertRaises(Refusal): r.forward('Bearer ' + CAP, json.dumps(request()).encode(), lambda raw: None)
        self.assertEqual(len(transport.calls), 1)

    def test_each_admitted_request_and_stream_consumes_bounded_task_budget(self):
        r, transport = relay()
        with patch.object(model_relay, 'MAX_REQUESTS', 1):
            r.forward('Bearer ' + CAP, json.dumps(request()).encode(), lambda raw: None)
            with self.assertRaises(Refusal):
                r.forward('Bearer ' + CAP, json.dumps(request()).encode(), lambda raw: None)
        self.assertEqual(len(transport.calls), 1)
        for limit in ('MAX_TOTAL', 'MAX_RESPONSE', 'MAX_EVENT'):
            r, transport = relay()
            with self.subTest(limit=limit), patch.object(model_relay, limit, 8), self.assertRaises(Refusal):
                r.forward('Bearer ' + CAP, json.dumps(request()).encode(), lambda raw: None)
            self.assertFalse(r.result()['completed_inference'])

    @unittest.skipUnless(hasattr(socket, 'AF_UNIX') and __import__('os').name != 'nt', 'POSIX socket mount profile')
    def test_failed_thread_start_cleans_up_without_joining_unstarted_thread(self):
        import threading
        for kind in ('relay', 'bridge'):
            r, _ = relay()
            with tempfile.TemporaryDirectory() as parent:
                path = r._start(parent) if kind == 'bridge' else None
                target = model_bridge.Bridge(path, 1800, clock=lambda: 1500) if path else r
                try:
                    with self.subTest(kind=kind), patch.object(threading.Thread, 'start', side_effect=OSError('synthetic start refusal')):
                        with self.assertRaises(OSError): target._start(0 if path else parent)
                finally: r.close()
                self.assertEqual(list(__import__('pathlib').Path(parent).iterdir()), [])

    @unittest.skipUnless(hasattr(socket, 'AF_UNIX') and __import__('os').name != 'nt', 'POSIX socket mount profile')
    def test_failed_bridge_listener_closes_allocated_socket(self):
        r, _ = relay()
        real = socket.socket
        allocated = []
        class Broken(real):
            def listen(self, backlog): raise OSError('synthetic listen refusal')
        def allocate(*args):
            result = Broken(*args)
            allocated.append(result)
            return result
        with tempfile.TemporaryDirectory() as parent:
            path = r._start(parent)
            try:
                bridge = model_bridge.Bridge(path, 1800, clock=lambda: 1500)
                with patch.object(model_bridge.socket, 'socket', side_effect=allocate), self.assertRaises(OSError):
                    bridge._start(0)
                self.assertEqual(allocated[0].fileno(), -1)
            finally: r.close()

    @unittest.skipUnless(hasattr(socket, 'AF_UNIX') and __import__('os').name != 'nt', 'POSIX socket mount profile')
    def test_failed_socket_permission_setup_removes_owned_resources(self):
        r, _ = relay()
        import os
        real = os.chmod
        def broken(path, mode):
            if str(path).endswith('/relay.sock'): raise PermissionError('synthetic chmod refusal')
            return real(path, mode)
        with tempfile.TemporaryDirectory() as parent:
            with patch.object(model_relay.os, 'chmod', side_effect=broken), self.assertRaises(PermissionError):
                r._start(parent)
            self.assertEqual(list(__import__('pathlib').Path(parent).iterdir()), [])

    @unittest.skipUnless(hasattr(socket, 'AF_UNIX') and __import__('os').name != 'nt', 'POSIX socket mount profile')
    def test_real_loopback_bridge_to_owned_unix_socket(self):
        r, transport = relay()
        with tempfile.TemporaryDirectory() as parent:
            path = r._start(parent)
            bridge = model_bridge.Bridge(path, 1800, clock=lambda: 1500)
            port = bridge._start(0)
            try:
                import http.client
                client = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                client.request('POST', '/v1/responses', json.dumps(request()),
                               {'Authorization': 'Bearer ' + CAP, 'Content-Type': 'application/json'})
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn(b'response.completed', response.read())
                client.close()
                self.assertTrue(r.result()['completed_inference'])
                self.assertEqual(len(transport.calls), 1)
            finally:
                bridge.close()
                r.close()
            self.assertFalse(__import__('os').path.exists(path))

    def test_http_ambiguity_and_alternate_routes_refuse(self):
        for header in (b'GET /v1/responses HTTP/1.1\r\n',
                       b'POST https://attacker.invalid/v1/responses HTTP/1.1\r\n',
                       b'POST /v1/responses?other HTTP/1.1\r\n',
                       b'POST /v1/responses HTTP/1.1\r\nContent-Length: 2\r\n',
                       b'POST /v1/responses HTTP/1.1\r\nTransfer-Encoding: chunked\r\n'):
            left, right = socket.socketpair()
            try:
                left.sendall(header + b'Content-Length: 2\r\nAuthorization: Bearer fixture\r\nContent-Type: application/json\r\n\r\n{}')
                with self.subTest(header=header), self.assertRaises(Refusal):
                    model_relay.read_request(right, lambda: 2)
            finally:
                left.close(); right.close()


if __name__ == '__main__': unittest.main()
