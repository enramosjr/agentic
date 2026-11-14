"""Task-local public Responses relay. Never accepts a refresh credential.

An already authenticated access lease is supplied by the trusted task parent.
The worker sees only its capability. Public listener startup is release-held.
Local transport success is diagnostic, not isolation or entitlement qualification.
"""
import copy
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import re
import socket
import stat
import tempfile
import threading
import time

import authority_release
from model_vault import validate_lease
from trusted_ci_policy import Refusal, loads, require

MAX_BODY, MAX_RESPONSE, MAX_EVENT = 16 * 1024 * 1024, 32 * 1024 * 1024, 1024 * 1024
MAX_REQUESTS, MAX_TOTAL = 128, 128 * 1024 * 1024
ALLOWED = frozenset(('model', 'input', 'instructions', 'store', 'stream', 'tools', 'tool_choice',
                     'parallel_tool_calls', 'reasoning', 'text', 'include', 'prompt_cache_key'))


def request_body(raw, model):
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BODY, 'bounded model request required')
    value = loads(raw)
    require(isinstance(value, dict) and set(value) <= ALLOWED and value.get('model') == model and
            value.get('store') is False and value.get('stream') is True and isinstance(value.get('input'), list),
            'unsupported model, storage, stream or request fields')
    def tools(items, depth=0):
        require(isinstance(items, list) and len(items) <= 256 and depth <= 1, 'bounded local tool inventory required')
        for item in items:
            require(isinstance(item, dict), 'local tool object required')
            kind = item.get('type')
            require(kind in ('function', 'custom', 'namespace'), 'unsupported hosted tool')
            if kind == 'namespace': tools(item.get('tools'), depth + 1)
    if 'tools' in value: tools(value['tools'])
    for item in value['input']:
        require(isinstance(item, dict) and item.get('role') != 'system', 'unsupported model input item')
        if item.get('type') == 'additional_tools': tools(item.get('tools'))
    # tool_choice cannot introduce a hosted tool absent from the inventory.
    choice = value.get('tool_choice')
    if isinstance(choice, str):
        require(choice in ('auto', 'none', 'required'), 'unsupported tool selection')
    elif choice is not None:
        require(isinstance(choice, dict) and choice.get('type') in ('function', 'custom', 'allowed_tools'),
                'unsupported tool selection')
        if choice['type'] == 'allowed_tools': tools(choice.get('tools'))
    return value


def read_request(connection, remaining):
    """One bounded, unambiguous HTTP request. The connection is never reused."""
    raw = bytearray()
    while b'\r\n\r\n' not in raw:
        connection.settimeout(min(5, remaining()))
        chunk = connection.recv(4096)
        require(chunk, 'incomplete model request')
        raw.extend(chunk)
        require(len(raw) <= MAX_BODY + 16384, 'model request exceeds bounds')
        if b'\r\n\r\n' not in raw: require(len(raw) <= 16384, 'model headers exceed bounds')
    head, body = bytes(raw).split(b'\r\n\r\n', 1)
    require(len(head) <= 16384, 'model headers exceed bounds')
    try: lines = head.decode('ascii').split('\r\n')
    except UnicodeError: raise Refusal('ASCII model headers required') from None
    require(lines.pop(0) == 'POST /v1/responses HTTP/1.1', 'only the fixed Responses route is admitted')
    headers = {}
    for line in lines:
        name, separator, value = line.partition(':')
        require(separator and re.fullmatch('[A-Za-z0-9-]+', name) and
                all(32 <= ord(c) < 127 for c in value), 'invalid model header')
        name, value = name.lower(), value.strip()
        require(name not in headers, 'duplicate model header')
        headers[name] = value
    require(not set(headers) & {'transfer-encoding', 'expect', 'upgrade'} and
            'upgrade' not in headers.get('connection', '').lower() and
            headers.get('content-type') == 'application/json' and
            re.fullmatch('[1-9][0-9]{0,8}', headers.get('content-length', '')),
            'unambiguous bounded JSON framing required')
    length = int(headers['content-length'])
    require(length <= MAX_BODY and len(body) <= length, 'model body length differs')
    while len(body) < length:
        connection.settimeout(min(5, remaining()))
        chunk = connection.recv(min(65536, length - len(body)))
        require(chunk, 'incomplete model body')
        body += chunk
    return headers.get('authorization', ''), body


class OpenAITransport:
    def open(self, body, token, timeout):
        # http.client has no environment proxy, redirect handler or POST retry.
        connection = http.client.HTTPSConnection('api.openai.com', 443, timeout=timeout)
        try:
            connection.request('POST', '/v1/responses', body, {'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json', 'Accept': 'text/event-stream', 'Connection': 'close'})
            stream_socket = connection.sock
            response = connection.getresponse()
        except Exception:
            connection.close()
            raise
        response._agentic_connection = connection
        response._agentic_socket = stream_socket
        return response


class Relay:
    def __init__(self, lease, binding, task, capability, transport=None, clock=None):
        self.clock = clock or (lambda: int(time.time()))
        self.lease = copy.deepcopy(validate_lease(lease, binding, task, self.clock()))
        require(isinstance(capability, str) and re.fullmatch('agentic-task\\.[0-9a-f]{64}', capability),
                'random task capability required')
        self.capability, self.transport = capability, transport or OpenAITransport()
        self.end = time.monotonic() + min(lease['expires'], task['deadline']) - self.clock()
        self.lock, self.stopped = threading.Lock(), threading.Event()
        self.requests = self.total = self.completed = 0
        self.response_digests = []
        self.failed = False
        self.listener = self.thread = self.connection = self.upstream = None
        self.directory = self.path = self.owned = None

    def remaining(self):
        value = min(self.end - time.monotonic(), self.lease['expires'] - self.clock())
        require(not self.stopped.is_set() and value > 0, 'model capability ended')
        return value

    def _count(self, amount):
        self.total += amount
        require(self.total <= MAX_TOTAL, 'task model traffic limit exceeded')

    def forward(self, authorization, raw, write):
        require(self.lock.acquire(blocking=False), 'only one task model request may run')
        response = None
        try:
            self.remaining()
            require(not self.failed and isinstance(authorization, str) and authorization.isascii() and
                    hmac.compare_digest(authorization, 'Bearer ' + self.capability), 'task capability differs')
            self.requests += 1
            require(self.requests <= MAX_REQUESTS, 'task model request limit exceeded')
            value = request_body(raw, self.lease['model_id'])
            self._count(len(raw))
            # Rebuild headers upstream; no worker headers or native credentials.
            response = self.transport.open(json.dumps(value, allow_nan=False).encode(),
                                           self.lease['access_token'], min(30, self.remaining()))
            self.upstream = response
            require(response.status == 200 and isinstance(response.getheader('Content-Type'), str) and
                    response.getheader('Content-Type').split(';', 1)[0] == 'text/event-stream',
                    'model did not return a successful event stream')
            pending, frame, frame_size, received, completed, ended = b'', [], 0, 0, False, False
            stream_digest = hashlib.sha256()
            while True:
                self.remaining()
                stream_socket = getattr(response, '_agentic_socket', None)
                if stream_socket is not None: stream_socket.settimeout(min(5, self.remaining()))
                chunk = response.read1(65536)
                if not chunk: break
                stream_digest.update(chunk)
                received += len(chunk)
                self._count(len(chunk))
                require(received <= MAX_RESPONSE, 'model stream exceeds limit')
                pending += chunk
                while b'\n' in pending:
                    self.remaining()
                    line, pending = pending.split(b'\n', 1)
                    line = line.removesuffix(b'\r')
                    if line:
                        frame.append(line)
                        frame_size += len(line) + 1
                        require(frame_size <= MAX_EVENT, 'model event exceeds limit')
                        continue
                    document = b'\n'.join(frame)
                    frame = []
                    frame_size = 0
                    data = b'\n'.join(line[5:].lstrip(b' ') for line in document.split(b'\n') if line.startswith(b'data:'))
                    if not data: continue
                    require(not ended, 'data after model stream sentinel')
                    if data == b'[DONE]':
                        require(completed, 'model stream sentinel precedes completion')
                        ended = True
                        write(document + b'\n\n')
                        continue
                    require(not completed, 'data after terminal model event')
                    event = loads(data)
                    require(isinstance(event, dict) and isinstance(event.get('type'), str), 'model event object required')
                    kind = event['type']
                    require(kind not in ('error', 'response.failed', 'response.incomplete'), 'model stream did not complete')
                    if kind == 'response.completed':
                        require(isinstance(event.get('response'), dict) and event['response'].get('status') == 'completed' and
                                isinstance(event['response'].get('id'), str) and 0 < len(event['response']['id']) <= 200 and
                                event['response'].get('error') is None,
                                'model terminal state differs')
                        completed = True
                    self.remaining()
                    write(document + b'\n\n')
                require(len(pending) <= MAX_EVENT, 'model event exceeds limit')
            require(completed and not pending.strip() and not frame, 'model stream ended without exact completion')
            self.completed += 1
            self.response_digests.append(stream_digest.hexdigest())
        except Exception:
            self.failed = True
            self.stopped.set()
            raise Refusal('task model request failed; no automatic retry') from None
        finally:
            self.upstream = None
            if response is not None:
                response.close()
                connection = getattr(response, '_agentic_connection', None)
                if connection is not None: connection.close()
            self.lock.release()

    def result(self):
        return dict(completed_inference=self.completed > 0 and not self.failed,
                    requests=self.requests, completed=self.completed,
                    response_digests=list(self.response_digests), model_execution_qualified=False)

    def start(self, parent):
        authority_release.authorize('protected-run')
        return self._start(parent)

    def _start(self, parent):
        require(os.name == 'posix' and self.listener is None, 'fresh POSIX model socket required')
        self.remaining()
        self.directory = Path(tempfile.mkdtemp(prefix='agentic-model-', dir=parent))
        self.owned = (self.directory.lstat(), None)
        self.path = self.directory / 'relay.sock'
        try:
            os.chmod(self.directory, 0o755)
            self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.listener.bind(str(self.path))
            self.owned = (self.owned[0], self.path.lstat())
            os.chmod(self.path, 0o666)
            self.listener.listen(1)
            self.listener.settimeout(.2)
            self.thread = threading.Thread(target=self._serve, daemon=True)
            self.thread.start()
            return str(self.path)
        except Exception:
            self.close()
            raise

    def _serve(self):
        try:
            while not self.stopped.is_set():
                self.remaining()
                try: connection, _ = self.listener.accept()
                except socket.timeout: continue
                self.connection = connection
                with connection:
                    try:
                        authorization, raw = read_request(connection, self.remaining)
                        sent = False
                        def write(chunk):
                            nonlocal sent
                            connection.settimeout(min(5, self.remaining()))
                            if not sent:
                                connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n')
                                sent = True
                            connection.sendall(chunk)
                        self.forward(authorization, raw, write)
                    except Exception:
                        self.failed = True
                        self.stopped.set()
                self.connection = None
        except (OSError, Refusal):
            if not self.stopped.is_set(): self.failed = True
            self.stopped.set()

    def close(self):
        self.stopped.set()
        for connection in (self.connection, self.listener):
            if connection is not None:
                try: connection.shutdown(socket.SHUT_RDWR)
                except OSError: pass
                connection.close()
        upstream = self.upstream
        if upstream is not None:
            stream_socket = getattr(upstream, '_agentic_socket', None)
            if stream_socket is not None:
                try: stream_socket.shutdown(socket.SHUT_RDWR)
                except OSError: pass
        if self.thread is not None and self.thread.ident is not None: self.thread.join(timeout=6)
        require(self.thread is None or not self.thread.is_alive(), 'model relay termination not confirmed')
        if self.owned is not None:
            directory = self.directory.lstat()
            require(stat.S_ISDIR(directory.st_mode) and not self.directory.is_symlink() and
                    (directory.st_dev, directory.st_ino) == (self.owned[0].st_dev, self.owned[0].st_ino),
                    'model socket directory ownership changed')
            if self.owned[1] is not None:
                entry = self.path.lstat()
                require(stat.S_ISSOCK(entry.st_mode) and (entry.st_dev, entry.st_ino) ==
                        (self.owned[1].st_dev, self.owned[1].st_ino), 'model socket ownership changed')
                self.path.unlink()
            self.directory.rmdir()
            self.owned = None
