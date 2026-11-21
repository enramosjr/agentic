"""Loopback HTTP fixture for the real GitHub transport; no external requests."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from urllib import parse, request


class FixtureServer:
    def __init__(self, host):
        self.host = host

    def __enter__(self):
        host = self.host
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_GET(self):
                try:
                    value = host.get(parse.urlparse(self.path).path)
                    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(raw)
                except (AssertionError, KeyError):
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                result = host.post(parse.urlparse(self.path).path, data)
                self.send_response(201)
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def open(self, req, timeout):
        url = 'http://127.0.0.1:' + str(self.server.server_port) + parse.urlparse(req.full_url).path
        forwarded = request.Request(url, data=req.data, headers=dict(req.header_items()), method=req.method)
        return request.urlopen(forwarded, timeout=timeout)

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
