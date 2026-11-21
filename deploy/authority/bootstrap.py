"""Human-side GitHub bootstrap. Run only from a trusted release outside coding."""
from __future__ import annotations

import html
import base64
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from urllib import error, request
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai' / 'scripts'))
from trusted_ci_policy import Refusal, ids, loads, positive, require

PERMISSIONS = {
    'admin': {'administration': 'write', 'contents': 'write', 'workflows': 'write', 'actions': 'write',
              'secrets': 'write', 'variables': 'write', 'pull_requests': 'read', 'repository_hooks': 'read'},
    'issuer': {'checks': 'write', 'contents': 'read', 'pull_requests': 'read'},
    'coding': {'contents': 'write', 'pull_requests': 'write'},
    'reader': {'contents': 'read', 'pull_requests': 'read', 'actions': 'read', 'checks': 'read'},
    'merge': {'contents': 'write', 'pull_requests': 'read'},
}


def run(argv, data=None, seconds=60, env=None):
    """Never put credentials in argv or relay remote/CLI diagnostics to a terminal."""
    require(isinstance(argv, list) and argv and all(isinstance(x, str) and '\0' not in x
                                                 for x in argv), 'invalid tool arguments')
    require(data is None or isinstance(data, bytes) and len(data) <= 1024 * 1024,
            'tool input exceeds limit')
    output, overflow = [], threading.Event()
    with subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, env=env) as process:
        def reader():
            size = 0
            while True:
                chunk = process.stdout.read(8192)
                if not chunk:
                    return
                size += len(chunk)
                if size > 1024 * 1024:
                    overflow.set()
                    process.kill()
                    return
                output.append(chunk)

        def writer():
            try:
                if data:
                    process.stdin.write(data)
                    process.stdin.flush()
            except (BrokenPipeError, OSError):
                # The exit status is checked by the supervising thread.
                return
            finally:
                process.stdin.close()

        readers = threading.Thread(target=reader, daemon=True)
        writers = threading.Thread(target=writer, daemon=True)
        readers.start()
        writers.start()
        try:
            process.wait(timeout=seconds)
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.wait()
            raise Refusal('trusted setup tool exceeded deadline') from error
        finally:
            readers.join(timeout=5)
            writers.join(timeout=5)
        require(not readers.is_alive() and not writers.is_alive(), 'setup tool pipes did not close')
        require(not overflow.is_set(), 'setup response exceeds limit')
        require(process.returncode == 0, 'trusted setup tool failed; inspect authenticated provider status')
        return b''.join(output)


class Gh:
    def __init__(self, runner=run, opener=None):
        self.run = runner
        from trusted_ci_github import NoRedirect
        self.opener = opener or request.build_opener(NoRedirect())

    def api(self, path, method='GET', body=None):
        require(path.startswith('/') and not path.startswith('//') and
                not any(ord(c) < 32 for c in path), 'invalid GitHub API path')
        argv = ['gh', 'api', '--hostname', 'github.com', path, '--method', method,
                '-H', 'Accept: application/vnd.github+json',
                '-H', 'X-GitHub-Api-Version: 2022-11-28']
        data = None
        if body is not None:
            argv += ['--input', '-']
            data = json.dumps(body, allow_nan=False).encode()
        raw = self.run(argv, data)
        return loads(raw) if raw.strip() else None

    def secret(self, repository, name, value):
        require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository), 'invalid repository')
        require(re.fullmatch('[A-Z][A-Z0-9_]{0,99}', name), 'invalid secret name')
        require(isinstance(value, str) and value, 'empty secret refused')
        self.run(['gh', 'secret', 'set', name, '--app', 'actions',
                  '--repo', 'github.com/' + repository], value.encode())

    def exchange(self, code):
        require(isinstance(code, str) and re.fullmatch('[A-Za-z0-9_-]{1,256}', code),
                'invalid manifest exchange code')
        # The code redeems a private key. Never expose it in process arguments,
        # an inherited environment or URL diagnostics, even on a shared host.
        req = request.Request('https://api.github.com/app-manifests/' + code + '/conversions',
            data=b'', method='POST', headers={'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'AGENTIC-trusted-bootstrap'})
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read(1024 * 1024 + 1)
            require(len(raw) <= 1024 * 1024, 'manifest conversion response exceeds limit')
            return loads(raw)
        except (error.HTTPError, error.URLError, OSError, ValueError):
            raise Refusal('manifest conversion failed; no enforcement activated') from None


def manifest(purpose, callback):
    require(purpose in PERMISSIONS, 'unknown App purpose')
    url = urlsplit(callback)
    require(url.scheme == 'http' and url.hostname == '127.0.0.1' and url.port and
            not url.username and not url.query and not url.fragment and
            url.path == '/callback/' + purpose, 'invalid bootstrap callback')
    return dict(name='AGENTIC-' + purpose + '-' + secrets.token_hex(5),
                url='https://github.com/enramosjr/agentic', public=False,
                redirect_url=callback,
                hook_attributes={'url': callback, 'active': False},
                default_permissions=dict(PERMISSIONS[purpose]), default_events=[])


class Consent:
    def __init__(self, purpose, exchange, seconds=600):
        require(purpose in PERMISSIONS, 'unknown App purpose')
        self.purpose, self.exchange = purpose, exchange
        self.state = secrets.token_urlsafe(32)
        self.deadline = time.monotonic() + seconds
        self.used = False
        self.lock = threading.Lock()
        self.result = None

    def consume(self, purpose, code, state):
        with self.lock:
            require(not self.used and time.monotonic() < self.deadline and
                    purpose == self.purpose and isinstance(state, str) and
                    secrets.compare_digest(state, self.state), 'expired or mismatched callback')
            require(isinstance(code, str) and re.fullmatch('[A-Za-z0-9_-]{1,256}', code),
                    'invalid callback code')
            self.used = True
            result = self.exchange(code)
            require(isinstance(result, dict) and positive(result.get('id')) and
                    isinstance(result.get('pem'), str) and result['pem'] and
                    isinstance(result.get('slug'), str) and
                    re.fullmatch('[a-zA-Z0-9_-]+', result['slug']), 'invalid registration response')
            permissions = dict(result.get('permissions', {}))
            require(permissions.get('metadata', 'read') == 'read', 'invalid metadata permission')
            permissions.pop('metadata', None)
            require(permissions == PERMISSIONS[self.purpose], 'App permission domain changed')
            self.result = result
            return result


def app_api(app_id, pem):
    """Sign in memory using optional backend crypto, never a temporary PEM file."""
    from trusted_ci_github import GitHub
    require(positive(app_id) and isinstance(pem, str) and len(pem) <= 16 * 1024 and pem.startswith('-----BEGIN '),
            'App signing credentials required')
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.exceptions import UnsupportedAlgorithm
    except ImportError:
        raise Refusal('optional backend cryptography dependency required for App signing') from None
    try:
        key = serialization.load_pem_private_key(pem.encode('utf-8'), password=None)
    except (ValueError, TypeError, UnsupportedAlgorithm):
        raise Refusal('invalid App signing key') from None
    require(isinstance(key, rsa.RSAPrivateKey) and 2048 <= key.key_size <= 8192, 'bounded RSA App signing key required')
    def encode(raw):
        return base64.urlsafe_b64encode(raw).rstrip(b'=')
    now = int(time.time())
    payload = encode(b'{"alg":"RS256","typ":"JWT"}') + b'.' + encode(
        json.dumps(dict(iss=str(app_id), iat=now - 60, exp=now + 540), separators=(',', ':')).encode())
    signature = key.sign(payload, padding.PKCS1v15(), hashes.SHA256())
    return GitHub((payload + b'.' + encode(signature)).decode('ascii'))


def revoke_token(result):
    from trusted_ci_github import GitHub
    token = result.get('token') if isinstance(result, dict) else None
    if isinstance(token, str) and token:
        GitHub(token).fetch('/installation/token', method='DELETE', binary=True)


def installation_token(api, installation, repositories, permissions):
    require(positive(installation), 'invalid installation')
    ids(repositories, 'token repository scope')
    require(isinstance(permissions, dict) and permissions and
            all(isinstance(k, str) and v in ('read', 'write') for k, v in permissions.items()),
            'explicit token permissions required')
    result = api.post('/app/installations/' + str(installation) + '/access_tokens',
                      {'repository_ids': repositories, 'permissions': permissions})
    try:
        granted = dict(result.get('permissions', {}))
        require(granted.pop('metadata', 'read') == 'read', 'invalid token metadata scope')
        require(granted == permissions and
                sorted(r['id'] for r in result.get('repositories', [])) == sorted(repositories),
                'installation token scope differs from request')
        require(isinstance(result.get('token'), str) and result['token'], 'installation token unavailable')
    except Exception:
        revoke_token(result)
        raise
    return result['token']


def await_installation(registration, account_id, seconds=600, before_call=None):
    """Human selects repositories in GitHub; polling avoids a permanent callback server."""
    require(positive(account_id), 'numeric installation owner required')
    require(registration.get('owner', {}).get('id') == account_id, 'App owner changed')
    guard = before_call if before_call is not None else lambda: None
    require(callable(guard), 'installation guard must be callable')
    guard()
    require(webbrowser.open('https://github.com/apps/' + registration['slug'] + '/installations/new'),
            'could not open installation consent')
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        guard()
        api = app_api(registration['id'], registration['pem'])
        guard()
        matches = [i for i in api.pages('/app/installations')
                   if i['account']['id'] == account_id and not i.get('suspended_at')]
        guard()
        require(len(matches) <= 1, 'ambiguous App installation')
        if matches:
            return matches[0]['id']
        time.sleep(2)
    raise Refusal('installation consent deadline expired')


def check_request(host, origin, port):
    require(host == '127.0.0.1:' + str(port), 'unexpected callback Host')
    require(origin in (None, 'https://github.com', 'http://127.0.0.1:' + str(port)),
            'unexpected callback Origin')


def register_app(purpose, gh, organization=None):
    """One browser consent, bound to this temporary loopback listener.

    Returned credentials stay in the trusted caller and are never written into
    workspace files. This flow must be live-qualified before supported activation.
    """
    if organization is not None:
        require(re.fullmatch('[A-Za-z0-9_-]{1,100}', organization), 'invalid organization')
    flow = Consent(purpose, gh.exchange)
    finished = threading.Event()
    failures = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            # HTTP access logs otherwise expose callback exchange codes and state.
            return

        def do_GET(self):
            try:
                check_request(self.headers.get('Host'), self.headers.get('Origin'), self.server.server_port)
                require(len(self.path) <= 4096, 'callback exceeds limit')
                url = urlsplit(self.path)
                query = parse_qs(url.query, strict_parsing=True)
                if url.path == '/start':
                    require(query == {'state': [flow.state]}, 'invalid start request')
                    callback = 'http://127.0.0.1:' + str(self.server.server_port) + '/callback/' + purpose
                    target = ('https://github.com/organizations/' + organization + '/settings/apps/new'
                              if organization else 'https://github.com/settings/apps/new')
                    body = ('<!doctype html><meta charset="utf-8"><title>AGENTIC setup</title>'
                            '<h1>Register ' + purpose + ' credentials</h1><form method="post" action="' +
                            target + '?state=' + html.escape(flow.state, quote=True) + '">' +
                            '<input type="hidden" name="manifest" value="' +
                            html.escape(json.dumps(manifest(purpose, callback)), quote=True) +
                            '"><button>Review permissions on GitHub</button></form>').encode()
                else:
                    require(url.path == '/callback/' + purpose and set(query) == {'code', 'state'} and
                            all(len(v) == 1 for v in query.values()), 'unexpected callback')
                    flow.consume(purpose, query['code'][0], query['state'][0])
                    body = b'<!doctype html><title>AGENTIC setup</title>Registration received. Return to trusted setup.'
                    finished.set()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('Content-Security-Policy', "default-src 'none'; form-action https://github.com; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(body)
            except (Refusal, ValueError, OSError):
                if flow.used and flow.result is None:
                    failures.append('registration callback failed; no enforcement activated')
                    finished.set()
                self.send_error(400, 'Invalid or expired setup request')

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            require(webbrowser.open('http://127.0.0.1:' + str(server.server_port) +
                                    '/start?state=' + flow.state), 'could not open trusted setup browser')
            require(finished.wait(600), 'registration consent deadline expired')
            require(not failures and flow.result is not None, 'registration incomplete')
            return flow.result
        finally:
            server.shutdown()
            thread.join(timeout=5)
