"""Worker loopback to one Unix socket. No upstream credential or network route."""
import os
from pathlib import Path
import socket
import stat
import threading
import time

import authority_release
from model_relay import MAX_RESPONSE, read_request
from trusted_ci_policy import Refusal, require


class Bridge:
    def __init__(self, path, deadline, clock=None):
        self.path, self.deadline = str(path), deadline
        self.clock = clock or (lambda: int(time.time()))
        self.end = time.monotonic() + deadline - self.clock()
        self.stopped = threading.Event()
        self.listener = self.thread = self.connection = self.upstream = None

    def remaining(self):
        value = min(self.deadline - self.clock(), self.end - time.monotonic())
        require(not self.stopped.is_set() and value > 0, 'worker model bridge ended')
        return value

    def start(self, port):
        authority_release.authorize('protected-run')
        return self._start(port)

    def _start(self, port):
        require(os.name == 'posix' and self.listener is None and type(port) is int and
                (port == 0 or 1024 <= port <= 65535) and Path(self.path).is_absolute() and
                stat.S_ISSOCK(Path(self.path).lstat().st_mode), 'fixed POSIX model socket/loopback port required')
        self.remaining()
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.listener.bind(('127.0.0.1', port))
            self.listener.listen(1)
            self.listener.settimeout(.2)
            self.thread = threading.Thread(target=self._serve, daemon=True)
            self.thread.start()
            return self.listener.getsockname()[1]
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
                    authorization, body = read_request(connection, self.remaining)
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as upstream:
                        self.upstream = upstream
                        upstream.settimeout(min(5, self.remaining()))
                        upstream.connect(self.path)
                        header = ('POST /v1/responses HTTP/1.1\r\nHost: agentic-model\r\nContent-Type: application/json\r\n'
                                  'Content-Length: ' + str(len(body)) + '\r\nAuthorization: ' + authorization +
                                  '\r\nConnection: close\r\n\r\n').encode('ascii')
                        upstream.sendall(header + body)
                        received = 0
                        while True:
                            upstream.settimeout(min(5, self.remaining()))
                            raw = upstream.recv(65536)
                            if not raw: break
                            received += len(raw)
                            require(received <= MAX_RESPONSE + 16384, 'model bridge response exceeds limit')
                            connection.settimeout(min(5, self.remaining()))
                            connection.sendall(raw)
                self.connection = self.upstream = None
        except (OSError, Refusal):
            self.stopped.set()

    def close(self):
        self.stopped.set()
        for connection in (self.connection, self.upstream, self.listener):
            if connection is not None:
                try: connection.shutdown(socket.SHUT_RDWR)
                except OSError: pass
                connection.close()
        if self.thread is not None and self.thread.ident is not None: self.thread.join(timeout=6)
        require(self.thread is None or not self.thread.is_alive(), 'worker model bridge termination not confirmed')
