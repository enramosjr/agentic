"""Trusted setup boundary tests, not proof of GitHub consent or live deployment."""
import backend_test_support  # Establish the explicit source-only test paths.
import json
from pathlib import Path
import sys
import unittest
import tempfile
import html
import io
import re
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

import trusted_ci_fixtures  # installs the stdlib client import path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deploy' / 'authority'))
import bootstrap
from trusted_ci_policy import Refusal


class Bootstrap(unittest.TestCase):
    def test_manifest_redemption_bearer_never_enters_subprocess_argv(self):
        calls = []
        class Opener:
            def open(self, request, timeout):
                self.url = request.full_url
                return io.BytesIO(b'{"id":42}')
        opener = Opener()
        gh = bootstrap.Gh(lambda argv, data=None: calls.append(argv), opener=opener)
        self.assertEqual(gh.exchange('one-use-code'), {'id': 42})
        self.assertEqual(calls, [])
        self.assertTrue(opener.url.endswith('/app-manifests/one-use-code/conversions'))

    def test_real_loopback_callback_does_not_expose_key_or_accept_replay(self):
        class Gh:
            def exchange(self, code):
                self.code = code
                return {'id': 42, 'pem': 'PRIVATE-NEVER-IN-HTTP', 'slug': 'agentic-issuer',
                        'permissions': dict(bootstrap.PERMISSIONS['issuer'])}
        gh = Gh()
        def browser(start):
            with urlopen(start, timeout=5) as response:
                page = response.read().decode()
            encoded = re.search('name="manifest" value="([^"]+)"', page).group(1)
            data = json.loads(html.unescape(encoded))
            state = parse_qs(urlsplit(start).query)['state'][0]
            callback = data['redirect_url'] + '?code=test-code&state=' + state
            for request in [Request(callback, headers={'Host': 'evil.example'})]:
                with self.assertRaises(HTTPError) as refused:
                    urlopen(request, timeout=5)
                self.assertEqual(refused.exception.code, 400)
            with urlopen(callback, timeout=5) as response:
                body = response.read()
                self.assertNotIn(b'PRIVATE', body)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
            with self.assertRaises(HTTPError) as replay:
                urlopen(callback, timeout=5)
            self.assertEqual(replay.exception.code, 400)
            return True
        with patch.object(bootstrap.webbrowser, 'open', side_effect=browser):
            result = bootstrap.register_app('issuer', gh)
        self.assertEqual(result['id'], 42)
        self.assertEqual(gh.code, 'test-code')

    def test_installation_tokens_are_explicitly_restricted(self):
        class App:
            def post(self, path, body):
                self.request = (path, body)
                return {'token': 'scoped', 'permissions': {'checks': 'write'},
                        'repositories': [{'id': 123}]}
        app = App()
        self.assertEqual(bootstrap.installation_token(app, 7, [123], {'checks': 'write'}), 'scoped')
        self.assertEqual(app.request, ('/app/installations/7/access_tokens',
                                     {'repository_ids': [123], 'permissions': {'checks': 'write'}}))
        with self.assertRaises(Refusal):
            bootstrap.installation_token(app, 7, [], {'checks': 'write'})

    def test_installation_token_response_cannot_expand_scope(self):
        class App:
            def post(self, path, body):
                return {'token': 'bad', 'permissions': {'administration': 'write'},
                        'repositories': [{'id': 456}]}
        revoked = []
        class Scoped:
            def __init__(self, token):
                self.token = token
            def fetch(self, path, **kwargs):
                revoked.append((self.token, path, kwargs))
                return b''
        with patch('trusted_ci_github.GitHub', side_effect=Scoped), self.assertRaises(Refusal):
            bootstrap.installation_token(App(), 7, [123], {'checks': 'write'})
        self.assertEqual(revoked, [('bad', '/installation/token', {'method': 'DELETE', 'binary': True})])

    def test_invalid_token_cleanup_negative_control_detects_missing_revocation(self):
        suite = unittest.TestSuite([Bootstrap('test_installation_token_response_cannot_expand_scope')])
        with patch.object(bootstrap, 'revoke_token', return_value=None):
            result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(len(result.errors), 0)

    def test_manifests_have_distinct_minimum_permissions(self):
        for purpose in bootstrap.PERMISSIONS:
            manifest = bootstrap.manifest(purpose, 'http://127.0.0.1:8123/callback/' + purpose)
            permissions = manifest['default_permissions']
            self.assertEqual(manifest['hook_attributes']['active'], False)
            if purpose != 'admin':
                self.assertNotIn('administration', permissions)
            if purpose == 'reader':
                self.assertEqual(permissions.get('checks'), 'read')
            elif purpose != 'issuer':
                self.assertNotIn('checks', permissions)
            if purpose == 'coding':
                self.assertNotIn('statuses', permissions)
                self.assertNotIn('actions', permissions)

    def test_state_single_use_and_no_cross_purpose_exchange(self):
        calls = []
        def exchange(code):
            calls.append(code)
            return {'id': 42, 'pem': 'PRIVATE', 'permissions': {'checks': 'write',
                    'contents': 'read', 'pull_requests': 'read', 'metadata': 'read'},
                    'slug': 'agentic-issuer'}
        flow = bootstrap.Consent('issuer', exchange)
        for state in ('wrong', '', None):
            with self.assertRaises(Refusal):
                flow.consume('issuer', 'code', state)
        with self.assertRaises(Refusal):
            flow.consume('admin', 'code', flow.state)
        self.assertEqual(flow.consume('issuer', 'code', flow.state)['id'], 42)
        with self.assertRaises(Refusal):
            flow.consume('issuer', 'code', flow.state)
        self.assertEqual(calls, ['code'])

    def test_permission_escalation_in_registration_refused(self):
        flow = bootstrap.Consent('issuer', lambda code: {'id': 42, 'pem': 'PRIVATE',
             'slug': 'evil', 'permissions': {'administration': 'write', 'checks': 'write'}})
        with self.assertRaises(Refusal):
            flow.consume('issuer', 'code', flow.state)

    def test_no_secrets_in_callback_response_or_repr(self):
        flow = bootstrap.Consent('issuer', lambda code: {})
        self.assertNotIn(flow.state, repr(flow))
        for host in ('evil.example', '127.0.0.1:8124', 'localhost:8123'):
            with self.assertRaises(Refusal):
                bootstrap.check_request(host, None, 8123)
        bootstrap.check_request('127.0.0.1:8123', None, 8123)
        with self.assertRaises(Refusal):
            bootstrap.check_request('127.0.0.1:8123', 'https://evil.example', 8123)

    def test_secret_wiring_uses_stdin_not_argv(self):
        calls = []
        def runner(argv, data=None):
            calls.append((argv, data))
            return b''
        gh = bootstrap.Gh(runner)
        gh.secret('owner/authority', 'AGENTIC_ISSUER_KEY', 'sensitive-key')
        self.assertEqual(calls[0][1], b'sensitive-key')
        self.assertNotIn('sensitive-key', ' '.join(calls[0][0]))
        self.assertEqual(calls[0][0][-1], 'github.com/owner/authority')


if __name__ == '__main__':
    unittest.main()
