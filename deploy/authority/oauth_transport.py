"""Bounded OpenAI public OAuth/metadata transport, without ambient credentials.

The child receives only the necessary form data over private stdin. No redirects,
proxies, native login cache, arbitrary upstream hosts or automatic POST retry.
Unknown completion must preserve the caller's durable refresh intent.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
from trusted_ci_policy import Refusal, loads, object_fields, require

ISSUER = 'https://auth.openai.com'
RESOURCE = 'https://api.openai.com/v1'
MAX_REQUEST, MAX_BODY, MAX_METADATA = 64 * 1024, 64 * 1024, 512 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _text(value, limit=16 * 1024):
    return isinstance(value, str) and 0 < len(value) <= limit and not any(ord(c) < 32 for c in value)


def validate_jwks_uri(value):
    require(_text(value, 2048), 'bounded issuer key URI required')
    try:
        uri = urlsplit(value)
        port = uri.port
    except ValueError:
        raise Refusal('invalid issuer key URI') from None
    require(uri.scheme == 'https' and uri.hostname == 'auth.openai.com' and port in (None, 443) and
            not uri.username and not uri.password and not uri.query and not uri.fragment and
            uri.path.startswith('/') and not uri.path.startswith('//') and '\\' not in unquote(uri.path) and
            not any(p in ('.', '..') for p in unquote(uri.path).split('/')), 'untrusted issuer key URI')
    return value


def _target(document):
    require(isinstance(document, dict) and type(document.get('schema_version')) is int and
            document['schema_version'] == 1, 'OAuth transport request required')
    purpose = document.get('purpose')
    if purpose == 'discovery':
        object_fields(document, ('schema_version', 'purpose'), 'issuer discovery request')
        return ISSUER + '/.well-known/openid-configuration', None, MAX_METADATA
    if purpose == 'jwks':
        object_fields(document, ('schema_version', 'purpose', 'uri'), 'issuer key request')
        return validate_jwks_uri(document['uri']), None, MAX_METADATA
    require(purpose == 'token', 'unknown OAuth transport purpose')
    object_fields(document, ('schema_version', 'purpose', 'data'), 'token endpoint request')
    data = document['data']
    require(isinstance(data, dict), 'token form object required')
    grant = data.get('grant_type')
    require(grant in ('refresh_token', 'authorization_code'), 'unsupported OAuth grant')
    fields = ['grant_type', 'client_id', 'resource'] + (['refresh_token'] if grant == 'refresh_token' else
             ['code', 'code_verifier', 'redirect_uri'])
    object_fields(data, fields, 'token grant form')
    require(all(_text(v) for v in data.values()) and data['resource'] == RESOURCE and
            _text(data['client_id'], 512) and data['client_id'] != 'dynamic_agent_client', 'issued OAuth client/resource required')
    if grant == 'authorization_code':
        try:
            callback = urlsplit(data['redirect_uri'])
            port = callback.port
        except ValueError:
            raise Refusal('invalid OAuth callback URI') from None
        require(callback.scheme == 'http' and callback.hostname == '127.0.0.1' and
                port is not None and 1024 <= port <= 65535 and
                callback.path == '/auth/callback' and not callback.query and not callback.fragment and
                not callback.username and not callback.password and
                re.fullmatch('[A-Za-z0-9._~-]{43,128}', data['code_verifier']), 'exact loopback and PKCE verifier required')
    body = urlencode(data).encode('ascii')
    require(len(body) <= MAX_REQUEST, 'OAuth form exceeds limit')
    return ISSUER + '/api/accounts/oauth/token', body, MAX_BODY


def request_once(document, opener=None):
    url, body, limit = _target(document)
    opener = opener or build_opener(NoRedirect(), ProxyHandler({}))
    headers = {'Accept': 'application/json', 'User-Agent': 'AGENTIC-authority-OAuth'}
    if body is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    try:
        with opener.open(Request(url, body, headers, method='POST' if body is not None else 'GET'), timeout=30) as response:
            raw = response.read(limit + 1)
            require(response.status == 200 and len(raw) <= limit, 'unexpected OAuth response status or size')
            value = loads(raw)
            require(isinstance(value, dict), 'OAuth response object required')
            return {'ok': True, 'status': 200, 'value': value}
    except HTTPError as error:
        raw = error.read(8193)
        category = 'oauth_refused'
        try:
            value = loads(raw) if len(raw) <= 8192 else {}
            known = ('invalid_grant', 'invalid_client', 'invalid_request', 'invalid_scope', 'access_denied', 'consent_required')
            if isinstance(value, dict) and value.get('error') in known:
                category = value['error']
        except Refusal:
            pass
        return {'ok': False, 'status': error.code, 'error': category}
    except (URLError, OSError, Refusal):
        return {'ok': False, 'status': None, 'error': 'completion_unknown'}


def isolated(document, seconds=30):
    _target(document)  # Refuse invalid requests before starting a child.
    require(type(seconds) in (int, float) and 0 < seconds <= 30, 'bounded OAuth deadline required')
    raw = json.dumps(document, allow_nan=False).encode('utf-8')
    require(len(raw) <= MAX_REQUEST, 'OAuth request exceeds limit')
    env = {k: v for k, v in os.environ.items() if k in ('SystemRoot', 'SYSTEMROOT', 'WINDIR')}
    started = time.monotonic()
    child = None
    try:
        child = subprocess.Popen([sys.executable, '-I', '-S', str(Path(__file__).resolve()), '--child'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        remaining = seconds - (time.monotonic() - started)
        require(remaining > 0, 'OAuth child startup exceeded deadline')
        output, _ = child.communicate(raw, timeout=remaining)
        require(child.returncode == 0 and 0 < len(output) <= 4 * 1024 * 1024, 'OAuth completion unknown')
        value = loads(output)
        require(isinstance(value, dict), 'OAuth child result required')
        return value
    except (OSError, subprocess.TimeoutExpired):
        raise Refusal('OAuth completion unknown; preserve pending refresh and do not retry') from None
    finally:
        if child is not None:
            if child.poll() is None:
                child.kill()
            child.communicate()


class OpenAI:
    def _request(self, document):
        result = isolated(document)
        require(isinstance(result, dict) and result.get('ok') is True and result.get('status') == 200 and
                isinstance(result.get('value'), dict), 'OpenAI authorization or metadata unavailable; do not repeat a grant')
        return result['value']

    def token(self, data):
        return self._request(dict(schema_version=1, purpose='token', data=data))

    def refresh(self, record):
        return self.token(dict(grant_type='refresh_token', client_id=record['identity']['client_id'],
            refresh_token=record['credentials']['refresh_token'], resource=RESOURCE))

    def discovery(self):
        return self._request(dict(schema_version=1, purpose='discovery'))

    def jwks(self, uri):
        return self._request(dict(schema_version=1, purpose='jwks', uri=uri))


def _main():
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
        require(0 < len(raw) <= MAX_REQUEST, 'bounded OAuth child input required')
        result = request_once(loads(raw))
        sys.stdout.write(json.dumps(result, allow_nan=False))
        return 0
    except Exception:
        sys.stdout.write('{"ok":false,"status":null,"error":"completion_unknown"}')
        return 0


if __name__ == '__main__':
    raise SystemExit(_main() if sys.argv[1:] == ['--child'] else 1)
